"""階段一:收「大漲」資料集(計畫 docs/計畫_大漲AE_OCSVM_2026-09-12.md §2)。

標籤(使用者 2026-09-12 決定):5 日固定持有,上牆 = 2 × σ20 × √5(σ20 = 近 20 日日報酬標準差),
    y = 1 若 close(t+5)/close(t) − 1 > 上牆;先不設下牆。
輸入三套(同一列都算好,之後各自取欄):
    A  K 線 1 日 7 特徵(method_kline features_1day 同定義)+ 4 個相對大盤 / 同池欄
    B  最近 20 天 OHLC(以當天收盤正規化)+ 20 天量(對 60 日均量的 log 比)= 100 欄 + 同 4 欄
    C  B + method_xgb 的 240 個技術指標(只有 tw50 / tw200 有現成特徵面板;elec_all 暫無)
排除:5 日均量 < 2,000 張、任何欄 NaN。漲停樣本不排除(使用者決定)。
股票池:tw50 / tw200 / elec_all(全電子股),資料 common/cache/yf_2026(2016 ~ 2026-09-11)。
輸出:common/cache/bigmove/samples_<pool>.parquet(index = date, ticker)+ samples_<pool>_meta.json(欄位分組、正例比例)
用法:python build_dataset.py --pool tw50   (每個池約 1 ~ 5 分鐘)
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
os.environ.setdefault("TW_CACHE_DIR", P.YF_2026_CACHE)
sys.path.insert(0, P.XGB_SRC)
from data import load_pool  # noqa: E402

OUT = os.path.join(P.CACHE, "bigmove")
os.makedirs(OUT, exist_ok=True)
START, END = "2016-01-01", "2026-09-11"
H, K_SIGMA, WIN, MIN_LOTS = 5, 2.0, 20, 2000


def kline7(df):
    O, Hh, L, C, V = df["open"], df["high"], df["low"], df["close"], df["volume"]
    Cp = C.shift(1)
    v5 = V.rolling(5, min_periods=5).mean()
    return pd.DataFrame({
        "a_upper": (Hh - np.maximum(O, C)) / C * 100, "a_lower": (np.minimum(O, C) - L) / C * 100,
        "a_body": (C - O) / C * 100, "a_gap": (O - Cp) / C * 100, "a_close_chg": (C - Cp) / C * 100,
        "a_vol_ratio": (V - v5) / v5.replace(0, np.nan), "a_trend": (C.shift(2) - C.shift(7)) / C.shift(7) * 100,
    }, index=df.index)


def window(df, n=WIN):
    C, V = df["close"], df["volume"]
    v60 = V.rolling(60, min_periods=30).mean()
    cols = {}
    for k in range(n):
        for nm in ("open", "high", "low", "close"):
            cols[f"b_{nm[0]}{k}"] = df[nm].shift(k) / C - 1
        cols[f"b_v{k}"] = np.log1p(V.shift(k)) - np.log1p(v60)
    return pd.DataFrame(cols, index=df.index)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    a = ap.parse_args()
    if a.pool == "all":                      # 快取裡全部:tw500 ∪ elec_all(814 檔)
        import data as _d
        _d.TICKER_SETS["all"] = list(dict.fromkeys(_d.TICKER_SETS["tw500"] + _d.TICKER_SETS["elec_all"]))
    data = load_pool(a.pool, START, END)
    print(f"[{a.pool}] {len(data)} 檔", flush=True)
    parts = []
    for tk, df in data.items():
        C = df["close"]
        r1 = C.pct_change()
        base = pd.DataFrame({
            "r_h5": C.shift(-H) / C - 1, "sigma20": r1.rolling(20, min_periods=15).std(),
            "roc_5": C / C.shift(5) - 1, "roc_20": C / C.shift(20) - 1,
            "vol5_lots": df["volume"].rolling(5, min_periods=5).mean() / 1000,
        }, index=df.index)
        x = pd.concat([base, kline7(df), window(df)], axis=1)
        x = x[x["vol5_lots"] >= MIN_LOTS]          # 逐檔先做流動性篩選,大池才放得進記憶體(相對大盤欄用篩後的池算)
        x["ticker"] = tk
        parts.append(x.astype({c: np.float32 for c in x.columns if c != "ticker"}))
    panel = pd.concat(parts).set_index("ticker", append=True)
    panel.index.names = ["date", "ticker"]
    panel = panel.sort_index()
    # 相對大盤(同池等權)與同池排名:t 日可得
    g = panel.groupby(level="date")
    panel["m_mkt_roc_5"] = g["roc_5"].transform("mean")
    panel["m_mkt_roc_20"] = g["roc_20"].transform("mean")
    panel["m_cs_rank_roc_5"] = g["roc_5"].rank(pct=True)
    panel["m_cs_rank_roc_20"] = g["roc_20"].rank(pct=True)
    panel["thr"] = K_SIGMA * panel["sigma20"] * np.sqrt(H)
    panel["y"] = (panel["r_h5"] > panel["thr"]).astype(float).where(panel["r_h5"].notna() & panel["thr"].notna())
    # C:接 method_xgb 特徵面板(有才接)
    fp = os.path.join(P.FEATURES, f"features_{a.pool}_{START}_{END}.parquet")
    c_cols = []
    if os.path.exists(fp):
        feat = pd.read_parquet(fp)
        c_cols = [c for c in feat.columns if c not in ("open", "high", "low", "close", "volume") and not c.startswith(("r_h", "y_", "p9_"))]
        feat = feat[c_cols].add_prefix("c_")
        c_cols = list(feat.columns)
        panel = panel.join(feat, how="left")
        print(f"  接上 {len(c_cols)} 個技術指標欄", flush=True)
    n0 = len(panel)
    panel = panel[panel["vol5_lots"] >= MIN_LOTS]
    n1 = len(panel)
    core = [c for c in panel.columns if not c.startswith("c_")]
    panel = panel.dropna(subset=core)
    if c_cols:
        panel = panel[panel[c_cols].isna().mean(axis=1) < 0.3]            # 技術指標缺太多的列丟掉,少量缺值留給模型
    meta = {"pool": a.pool, "n_tickers": len(data), "label": f"r_h{H} > {K_SIGMA}*sigma20*sqrt({H})",
            "rows_raw": n0, "rows_after_liq": n1, "rows": len(panel), "pos_rate": float(panel["y"].mean()),
            "n_pos": int(panel["y"].sum()),
            "cols": {"A": [c for c in panel.columns if c.startswith("a_")] + [c for c in panel.columns if c.startswith("m_")],
                     "B": [c for c in panel.columns if c.startswith("b_")] + [c for c in panel.columns if c.startswith("m_")],
                     "C": [c for c in panel.columns if c.startswith(("b_", "m_", "c_"))] if c_cols else []}}
    panel.to_parquet(os.path.join(OUT, f"samples_{a.pool}.parquet"))
    json.dump(meta, open(os.path.join(OUT, f"samples_{a.pool}_meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    yrs = panel.index.get_level_values("date").year
    print(f"  列數 {n0:,} → 流動性後 {n1:,} → 去 NaN 後 {len(panel):,};正例 {meta['n_pos']:,}({meta['pos_rate']*100:.2f}%);"
          f"每年正例 {panel.groupby(yrs)['y'].sum().astype(int).to_dict()}", flush=True)
    print(f"[SAVED] {os.path.join(OUT, f'samples_{a.pool}.parquet')}  欄 A {len(meta['cols']['A'])} / B {len(meta['cols']['B'])} / C {len(meta['cols']['C'])}")


if __name__ == "__main__":
    main()
