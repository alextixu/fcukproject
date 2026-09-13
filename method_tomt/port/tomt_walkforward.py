"""隊友 Tom 的 Qmodel 方法,逐年 walk-forward 重現(直接呼叫 tomt/Qmodel/src/feature 的特徵程式,模型參數照他的程式預設)。

五個模型(全部 LightGBM,參數取自 tomt/Qmodel/src/train/*.py 的預設值;沒有 config/ 裡的 GA / Optuna 結果):
  States  多分類:過去 5 日相對 0050 的超額報酬分三類(後 30% / 中 40% / 前 30%),輸出 P(跌/盤/漲)
  Trend   迴歸:技術指標 + States 機率 → 未來 5 日相對 0050 的超額報酬(照原程式只用訓練期前 80% 的日期擬合)
  Flow    迴歸:籌碼(三大法人、融資券、外資持股;無借券資料)+ States 機率 → 同上
  Meta    迴歸:[Trend 預測, Flow 預測] → 同上(輸入是訓練期內的樣本內預測,與原流程一致)
  Vol     迴歸:未來 5 日年化波動(訓練期最後 20% 日期當 early stopping 驗證)
測試年 Y:只用 Y 年以前的資料訓練;前瞻標籤的最後 5 個交易日剔除(原程式沒剔,這裡補上避免偷看)。
依使用者要求不做流動性篩選(原程式訓練時會濾掉 5 日均量 < 1,000 張)。
用法: python tomt_walkforward.py --pool tw50 [--years 2021-2026]
輸出: backtest_2026/results/tomt_<pool>_preds.parquet(date, stock_id, year, trend, flow, meta_alpha, pred_vol_5d)
"""
import argparse
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
sys.path.insert(0, os.path.join(P.METHOD_TOMT, "Qmodel"))
sys.path.insert(0, P.CHARTGCN_CORE)
import lightgbm as lgb                                                     # noqa: E402
from src.feature.trend import compute_trend, COMPUTED_COLUMNS              # noqa: E402
from src.feature.states import compute_states_features, STATES_FEATURES    # noqa: E402
from src.feature.volatility import compute_volatility_features, VOL_FEATURE_COLUMNS  # noqa: E402
from src.feature.flow import (compute_institutional_features, compute_margin_features,  # noqa: E402
                              compute_shareholding_features, compute_flow_score)
from src.feature.labels import excess_returns, rank_labels                 # noqa: E402
from data_loader import TICKER_SETS                                        # noqa: E402

CACHE = P.YF_2026_CACHE
FINMIND = P.FINMIND_2026
FEAT = os.path.join(HERE, "cache")
RES = P.RESULTS
os.makedirs(FEAT, exist_ok=True)
H = 5

# ── 模型參數:原程式預設 ──
P_STATES = dict(n_estimators=300, learning_rate=0.05, num_leaves=31, max_depth=6, subsample=0.8, colsample_bytree=0.8,
                min_child_samples=50, n_jobs=4, verbosity=-1, random_state=42, objective="multiclass", num_class=3)
P_TREND = dict(n_estimators=200, learning_rate=0.05, num_leaves=31, max_depth=6, subsample=0.8, colsample_bytree=0.8,
               min_child_samples=50, n_jobs=4, verbosity=-1, random_state=42, objective="regression")
P_FLOW = dict(n_estimators=200, learning_rate=0.05, num_leaves=31, max_depth=7, subsample=0.8, colsample_bytree=0.8,
              min_child_samples=50, n_jobs=4, verbosity=-1, random_state=42, objective="regression")
P_META = dict(n_estimators=200, learning_rate=0.05, num_leaves=15, max_depth=5, subsample=0.8, colsample_bytree=0.8,
              min_child_samples=50, n_jobs=4, random_state=42, verbosity=-1)
P_VOL = dict(n_estimators=300, learning_rate=0.05, num_leaves=31, max_depth=6, subsample=0.8, colsample_bytree=0.8,
             min_child_samples=50, random_state=42, n_jobs=4, verbosity=-1)
PROBS = ["states_P_down", "states_P_range", "states_P_up"]


def load_price(pool):
    tks = list(dict.fromkeys(["0050.TW"] + TICKER_SETS[pool]))
    parts = []
    for tk in tks:
        fp = os.path.join(CACHE, f"{tk}.parquet")
        if not os.path.exists(fp):
            continue
        x = pd.read_parquet(fp).loc["2016-01-01":"2026-09-10"]
        if len(x) < 250:
            continue
        parts.append(pd.DataFrame({"date": pd.to_datetime(x.index), "stock_id": tk.split(".")[0], "open": x["open"].values,
                                   "high": x["high"].values, "low": x["low"].values, "close": x["close"].values,
                                   "adj_close": x["close"].values, "volume": x["volume"].astype(float).values}))
    return pd.concat(parts, ignore_index=True).sort_values(["stock_id", "date"]).reset_index(drop=True)


def cached(name, fn):
    fp = os.path.join(FEAT, name)
    if os.path.exists(fp):
        return pd.read_parquet(fp)
    t0 = time.time()
    df = fn()
    df.to_parquet(fp, index=False)
    print(f"  [特徵] {name}: {df.shape}  {time.time() - t0:.0f}s", flush=True)
    return df


def build_trend(price):
    mkt = price[price["stock_id"] == "0050"][["date", "adj_close"]].sort_values("date")
    for d in [1, 5, 20, 60]:
        mkt[f"mkt_ret_{d}d"] = mkt["adj_close"].pct_change(d)
    df = price.merge(mkt.drop(columns="adj_close"), on="date", how="left")
    out = [compute_trend(g.copy()) for _, g in df.groupby("stock_id") if len(g) >= 60]
    comb = pd.concat(out, ignore_index=True)
    keep = ["date", "stock_id"] + [c for c in COMPUTED_COLUMNS if c in comb.columns]
    return comb[keep]


def build_flow(price, codes):
    def cat(key):
        parts = [pd.read_parquet(os.path.join(FINMIND, key, f"{c}.parquet")) for c in codes if os.path.exists(os.path.join(FINMIND, key, f"{c}.parquet"))]
        return pd.concat(parts, ignore_index=True) if parts else None
    vol = price[["date", "stock_id", "volume"]]
    inst = compute_institutional_features(cat("institutional"), vol)
    marg = compute_margin_features(cat("margin"), vol)
    sh = compute_shareholding_features(cat("shareholding"))
    f = inst.merge(marg, on=["date", "stock_id"], how="outer").merge(sh, on=["date", "stock_id"], how="outer")
    sc = compute_flow_score(inst, marg)
    if sc is not None and "flow_score" in sc.columns:
        f = f.merge(sc[["date", "stock_id", "flow_score"]], on=["date", "stock_id"], how="left")
    f["date"] = pd.to_datetime(f["date"])
    f["stock_id"] = f["stock_id"].astype(str)
    return f


def past_excess(price):
    df = price[["date", "stock_id", "adj_close"]].copy()
    df["stk_past"] = df.groupby("stock_id")["adj_close"].transform(lambda x: x / x.shift(H) - 1)
    mkt = df[df["stock_id"] == "0050"][["date", "adj_close"]].copy()
    mkt["mkt_past"] = mkt["adj_close"] / mkt["adj_close"].shift(H) - 1
    df = df.merge(mkt[["date", "mkt_past"]], on="date", how="left")
    df["past_ex"] = df["stk_past"] - df["mkt_past"]
    m, s = df["past_ex"].mean(), df["past_ex"].std()
    df["past_ex"] = df["past_ex"].clip(m - 3 * s, m + 3 * s)
    return df[["date", "stock_id", "past_ex"]]


def fwd_vol(price):
    df = price[["date", "stock_id", "adj_close"]].copy()
    df["ret"] = df.groupby("stock_id")["adj_close"].pct_change()
    df["fwd_vol"] = df.groupby("stock_id")["ret"].transform(lambda x: x.rolling(H, min_periods=3).std().shift(-H) * np.sqrt(252)).clip(0, 2.0)
    return df[["date", "stock_id", "fwd_vol"]]


def X(df, cols):
    a = df.reindex(columns=cols).apply(pd.to_numeric, errors="coerce").values.astype(np.float64)
    return np.where(np.isfinite(a), a, 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="tw50")
    ap.add_argument("--years", default="2021-2026")
    a = ap.parse_args()
    y0, y1 = [int(v) for v in a.years.split("-")]
    t_all = time.time()
    price = load_price(a.pool)
    codes = sorted(set(price["stock_id"]) - {"0050"})
    print(f"[資料] {a.pool}: {len(codes)} 檔 + 0050,{price['date'].min().date()} ~ {price['date'].max().date()}", flush=True)
    tr = cached(f"{a.pool}_trend.parquet", lambda: build_trend(price))
    stf = cached(f"{a.pool}_states.parquet", lambda: compute_states_features(price))
    vf = cached(f"{a.pool}_vol.parquet", lambda: compute_volatility_features(price))
    fl = cached(f"{a.pool}_flow.parquet", lambda: build_flow(price, codes))
    for d in (tr, stf, vf, fl):
        d["date"] = pd.to_datetime(d["date"]); d["stock_id"] = d["stock_id"].astype(str)
    lab = excess_returns(price, horizon=H, winsorize=True, market_id="0050")
    lab["date"] = pd.to_datetime(lab["date"]); lab["stock_id"] = lab["stock_id"].astype(str)
    pex = past_excess(price)
    fv = fwd_vol(price)
    vcols = [c for c in VOL_FEATURE_COLUMNS if c in vf.columns]
    tcols = [c for c in COMPUTED_COLUMNS if c in tr.columns]
    fcols = sorted([c for c in fl.columns if c not in ("date", "stock_id")])
    cal = np.sort(price[price["stock_id"] == "0050"]["date"].unique())

    base = stf.merge(pex, on=["date", "stock_id"], how="left")
    base = base[base["stock_id"] != "0050"]
    out = []
    for Y in range(y0, y1 + 1):
        t0 = time.time()
        cut = pd.Timestamp(f"{Y}-01-01")
        pre = cal[cal < cut]
        purge = pd.Timestamp(pre[-(H + 1)])                  # 前瞻 5 日標籤不跨進測試年
        test_end = pd.Timestamp(f"{Y}-12-31")
        # 1) States
        sdat = base.dropna(subset=["past_ex"] + STATES_FEATURES[:5])
        str_ = sdat[sdat["date"] < cut]
        yl = rank_labels(str_["past_ex"], n_bins=3, quantiles=[0, 0.3, 0.7, 1.0])
        ms = lgb.LGBMClassifier(**P_STATES).fit(X(str_, STATES_FEATURES), yl)
        allst = base[base["date"] <= test_end]
        pr = ms.predict_proba(X(allst, STATES_FEATURES))
        st = pd.DataFrame(pr, columns=PROBS); st["date"] = allst["date"].values; st["stock_id"] = allst["stock_id"].values
        # 2) Trend
        td = tr.merge(st, on=["date", "stock_id"], how="inner").merge(lab, on=["date", "stock_id"], how="left")
        tfe = tcols + PROBS
        ttr = td[(td["date"] <= purge)].dropna(subset=["excess_ret"]).sort_values("date")
        ud = np.sort(ttr["date"].unique()); split = ud[len(ud) - int(len(ud) * 0.2)]
        mt = lgb.LGBMRegressor(**P_TREND).fit(X(ttr[ttr["date"] < split], tfe), ttr.loc[ttr["date"] < split, "excess_ret"].values)
        td["trend_reg"] = mt.predict(X(td, tfe))
        # 3) Flow
        fd = fl.merge(st, on=["date", "stock_id"], how="left").merge(lab, on=["date", "stock_id"], how="left")
        fd = fd[fd["date"] <= test_end]
        ffe = fcols + PROBS
        ftr = fd[(fd["date"] <= purge)].dropna(subset=["excess_ret"])
        mf = lgb.LGBMRegressor(**P_FLOW).fit(X(ftr, ffe), ftr["excess_ret"].values)
        fd["flow_reg"] = mf.predict(X(fd, ffe))
        # 4) Meta(outer merge,缺的一邊用另一邊補,與原推論一致)
        al = td[["date", "stock_id", "trend_reg"]].merge(fd[["date", "stock_id", "flow_reg"]], on=["date", "stock_id"], how="outer")
        al["flow_reg"] = al["flow_reg"].fillna(al["trend_reg"]); al["trend_reg"] = al["trend_reg"].fillna(al["flow_reg"])
        al = al.merge(lab, on=["date", "stock_id"], how="left")
        atr = al[(al["date"] <= purge)].dropna(subset=["excess_ret"])
        mm = lgb.LGBMRegressor(**P_META).fit(atr[["trend_reg", "flow_reg"]].values, atr["excess_ret"].values)
        al["meta_alpha"] = mm.predict(al[["trend_reg", "flow_reg"]].values)
        # 5) Vol
        vd = vf[["date", "stock_id"] + vcols].merge(fv, on=["date", "stock_id"], how="left")
        vtr = vd[(vd["date"] <= purge)].dropna(subset=["fwd_vol"]).sort_values("date")
        ud = np.sort(vtr["date"].unique()); split = ud[len(ud) - int(len(ud) * 0.2)]
        a_, b_ = vtr[vtr["date"] < split], vtr[vtr["date"] >= split]
        mv = lgb.LGBMRegressor(**P_VOL).fit(X(a_, vcols), a_["fwd_vol"].values, eval_set=[(X(b_, vcols), b_["fwd_vol"].values)],
                                             callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(-1)])
        vte = vd[(vd["date"] >= cut) & (vd["date"] <= test_end)].copy()
        vte["pred_vol_5d"] = np.maximum(mv.predict(X(vte, vcols)), 0.0)
        # 測試年輸出
        te = al[(al["date"] >= cut) & (al["date"] <= test_end)].merge(vte[["date", "stock_id", "pred_vol_5d"]], on=["date", "stock_id"], how="left")
        te = te[te["stock_id"] != "0050"]
        te["year"] = Y
        out.append(te[["date", "stock_id", "year", "trend_reg", "flow_reg", "meta_alpha", "pred_vol_5d", "excess_ret"]])
        ic = te.dropna(subset=["excess_ret"]).groupby("date").apply(lambda g: g["meta_alpha"].corr(g["excess_ret"], method="spearman")).mean()
        print(f"  {Y}: 訓練 ≤ {purge.date()} | States {len(str_):,} 列  Trend {len(ttr):,}  Flow {len(ftr):,}  Meta {len(atr):,}  Vol 樹 {mv.best_iteration_} | "
              f"測試 {len(te):,} 列,meta 日 IC {ic:+.4f}  ({time.time() - t0:.0f}s)", flush=True)
    res = pd.concat(out, ignore_index=True)
    fp = os.path.join(RES, f"tomt_{a.pool}_preds.parquet")
    res.to_parquet(fp, index=False)
    print(f"[SAVED] {fp}  ({time.time() - t_all:.0f}s)")


if __name__ == "__main__":
    main()
