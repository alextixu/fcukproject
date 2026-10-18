"""三日 K(窗格第 5、6、7 天)→ 頂 / 底 / 其他,只看「最有把握」的尾端準不準。

使用者目標(2026-10-18):模型只要能挑出看起來「必漲」與「必跌」的少數型態,
大部分判成不漲不跌也沒關係 → 評估重點是高分尾端的命中率,不是整體 accuracy / macro-F1 / AUC。

設計
  中心日 t = 窗格第 6 天;決策日 d = t+1(第 7 天)收盤,輸入只有第 5、6、7 天三根 K:
    raw3   三根 K 的 O/H/L/C(相對第 7 天收盤的 log 價)+ 量(相對 20 日均量的 log 比),14 維
    kline3 method_kline 原系統的 3 日 12 特徵(features_3day)
  標籤 = peak_labels.label_window(hl 口徑)在 t 的頂 / 底 / 其他;第 7 天收盤時第 8–11 天仍未知。
  漲跌 = 第 8 天開盤進、第 11 天收盤出(窗格剩下的 4 天)的還原報酬
    頂 →「必跌」看報酬 < 0;底 →「必漲」看報酬 > 0;另列扣 0.42% 成本後的平均報酬(頂以放空計)
  分數:LightGBM 三分類(不加類別權重,3 seeds 機率平均)× 兩套輸入、kNN 形態搜尋(raw3,k=50)、
        naive(三日累積漲跌幅:漲最多當頂、跌最多當底)
  兩個測試段:2022–2023(含 2022 空頭)與 2025-01 ~ 2026-09(多頭),各自往前訓練
  尾端:各分數取前 0.1% / 0.5% / 1% / 5% 的日子,算標籤命中率、方向命中率(Wilson 95% CI)、
        平均報酬,與涉及幾個不同日期(尾端常擠在大盤急跌 / 急漲的同幾天)

用法: python method_kline_peak/tail_precision.py --pool tw50
輸出: method_kline_peak/results/tail_<pool>.json
"""
import argparse
import json
import os
import sys
import time

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from feasibility import P, START, END, COST, SEEDS, load_pool, clean  # noqa: E402
from peak_labels import HALF, OTHER, TOP, BOTTOM, AMBIG, label_window  # noqa: E402
sys.path.insert(0, P.METHOD_KLINE)
from kline.features import features_3day  # noqa: E402

OUT = os.path.join(HERE, "results")
FOLDS = {
    "2022-23": {"train": ("2016-01-01", "2020-12-31"), "val": ("2021-01-01", "2021-12-31"),
                "test": ("2022-01-01", "2023-12-31")},
    "2025-26": {"train": ("2016-01-01", "2022-12-31"), "val": ("2023-01-01", "2024-12-31"),
                "test": ("2025-01-01", END)},
}
QS = (0.001, 0.005, 0.01, 0.05)
KNN_K = 50
RAW3 = [f"{p}{k}" for k in range(3) for p in "ohlcv" if not (p == "c" and k == 0)]
LGB_PARAMS = dict(objective="multiclass", num_class=3, learning_rate=0.05, num_leaves=31,
                  min_child_samples=200, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                  reg_lambda=1.0, n_estimators=2000, n_jobs=4, verbose=-1)


def build_panel(data):
    parts = []
    for tk, df in data.items():
        df = clean(df)
        O, H, L, C, V = (df[k] for k in ("open", "high", "low", "close", "volume"))
        lc = np.log(C)
        v20 = V.rolling(20, min_periods=20).mean()
        f = {}
        for k in range(3):                      # k = 0 第 7 天、1 第 6 天、2 第 5 天
            f[f"o{k}"] = np.log(O.shift(k)) - lc
            f[f"h{k}"] = np.log(H.shift(k)) - lc
            f[f"l{k}"] = np.log(L.shift(k)) - lc
            if k:
                f[f"c{k}"] = np.log(C.shift(k)) - lc
            f[f"v{k}"] = np.log(V.shift(k) / v20)
        part = pd.DataFrame(f, index=df.index)
        part = part.join(features_3day(df.rename(columns=str.capitalize)).add_prefix("k3_"))
        part["y"] = label_window(df, "hl")["label"].shift(1)        # 中心日 t = d - 1
        part["fwd"] = C.shift(-4) / O.shift(-1) - 1                 # 第 8 天開 → 第 11 天收
        part["ticker"] = tk
        part.index.name = "date"
        parts.append(part.reset_index())
    panel = pd.concat(parts, ignore_index=True).replace([np.inf, -np.inf], np.nan)
    feats = RAW3 + [c for c in panel.columns if c.startswith("k3_")]
    ok = panel["y"].notna() & (panel["y"] != AMBIG) & panel["fwd"].notna() & panel[feats].notna().all(axis=1)
    panel = panel[ok & (panel["date"] >= START)].reset_index(drop=True)
    panel["y"] = panel["y"].astype(int)
    return panel


def split(panel, fold):
    cal = np.sort(panel["date"].unique())
    purge = []
    for name in ("val", "test"):
        i = np.searchsorted(cal, np.datetime64(fold[name][0]))
        purge.extend(cal[max(0, i - HALF):i])      # 標籤與報酬看到 d+4,跨進下一段的樣本丟掉
    keep = ~panel["date"].isin(purge)
    return {k: panel[keep & (panel["date"] >= a) & (panel["date"] <= b)].reset_index(drop=True)
            for k, (a, b) in fold.items()}


def lgb_proba(tr, va, te, feats):
    proba = np.zeros((len(te), 3))
    for seed in SEEDS:
        m = lgb.LGBMClassifier(**LGB_PARAMS, random_state=seed)
        m.fit(tr[feats], tr["y"], eval_set=[(va[feats], va["y"])],
              callbacks=[lgb.early_stopping(100, verbose=False)])
        proba += m.predict_proba(te[feats]) / len(SEEDS)
    return proba


def knn_proba(fit_df, te):
    sc = StandardScaler().fit(fit_df[RAW3])
    knn = KNeighborsClassifier(n_neighbors=KNN_K, n_jobs=4).fit(sc.transform(fit_df[RAW3]), fit_df["y"])
    return knn.predict_proba(sc.transform(te[RAW3]))    # 欄位順序 = classes_ = [0, 1, 2]


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [float((c - r) / d), float((c + r) / d)]


def tail_table(te, score, cls):
    y, fwd, dates = te["y"].to_numpy(), te["fwd"].to_numpy(), te["date"].to_numpy()
    good = fwd < 0 if cls == TOP else fwd > 0
    sign = -1 if cls == TOP else 1
    order = np.argsort(-score, kind="stable")
    rows = {}
    for q in QS:
        idx = order[:max(1, int(round(len(te) * q)))]
        n, k = len(idx), int(good[idx].sum())
        vc = pd.Series(dates[idx]).value_counts(normalize=True)
        rows[f"{q:.1%}"] = {
            "n": n, "n_dates": int(len(vc)), "top_date_share": float(vc.iloc[0]),
            "label_prec": float((y[idx] == cls).mean()),
            "dir_hit": k / n, "dir_hit_ci": wilson(k, n),
            "ret_pct": float(fwd[idx].mean() * 100),
            "net_pct": float((sign * fwd[idx] - COST).mean() * 100),
        }
    return rows


def run_fold(panel, name, fold):
    sp = split(panel, fold)
    tr, va, te = sp["train"], sp["val"], sp["test"]
    k3 = [c for c in panel.columns if c.startswith("k3_")]
    scores = {
        "lgb_raw3": lgb_proba(tr, va, te, RAW3),
        "lgb_kline3": lgb_proba(tr, va, te, k3),
        "knn_raw3": knn_proba(pd.concat([tr, va]), te),
    }
    cum = te["k3_cum_return"].to_numpy()
    naive = np.zeros((len(te), 3))
    naive[:, TOP], naive[:, BOTTOM] = cum, -cum
    scores["naive_cum3"] = naive

    fwd = te["fwd"].to_numpy()
    res = {"n_split": {k: len(d) for k, d in sp.items()},
           "base": {"頂_rate": float((te["y"] == TOP).mean()), "底_rate": float((te["y"] == BOTTOM).mean()),
                    "跌_rate": float((fwd < 0).mean()), "漲_rate": float((fwd > 0).mean()),
                    "ret_pct": float(fwd.mean() * 100)},
           "models": {}}
    for m, pr in scores.items():
        res["models"][m] = {"頂(必跌)": tail_table(te, pr[:, TOP], TOP), "底(必漲)": tail_table(te, pr[:, BOTTOM], BOTTOM)}
    return res


def show(name, res):
    b = res["base"]
    print(f"\n== 測試段 {name}  test n={res['n_split']['test']:,}  基準:頂 {b['頂_rate']:.1%} 底 {b['底_rate']:.1%}  "
          f"4 日跌 {b['跌_rate']:.1%} 漲 {b['漲_rate']:.1%}  平均 {b['ret_pct']:+.2f}%")
    for side, word in (("頂(必跌)", "跌"), ("底(必漲)", "漲")):
        print(f"  {side}          前%    n  日期數 最多同日  標籤命中  {word}命中 [95% CI]      報酬    扣成本")
        for m, t in res["models"].items():
            for q, r in t[side].items():
                ci = r["dir_hit_ci"]
                print(f"    {m:<11} {q:>5} {r['n']:>5} {r['n_dates']:>6} {r['top_date_share']:>7.0%}  "
                      f"{r['label_prec']:>7.1%}  {r['dir_hit']:>6.1%} [{ci[0]:.0%}, {ci[1]:.0%}]  "
                      f"{r['ret_pct']:>+6.2f}%  {r['net_pct']:>+6.2f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="tw50")
    args = ap.parse_args()
    t0 = time.time()
    panel = build_panel(load_pool(args.pool, START, END))
    print(f"[DATA] {args.pool}: panel {panel.shape}  ({time.time() - t0:.0f}s)", flush=True)
    out = {"pool": args.pool, "folds": FOLDS, "quantiles": QS, "results": {}}
    for name, fold in FOLDS.items():
        out["results"][name] = res = run_fold(panel, name, fold)
        show(name, res)
        print(f"  ({time.time() - t0:.0f}s)", flush=True)
    fp = os.path.join(OUT, f"tail_{args.pool}.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n輸出 {fp}")


if __name__ == "__main__":
    main()
