"""在市值前 100 大面板上加三群新特徵(長週期動能、隔夜 / 日內、籌碼)→ features_top100_extra_*.parquet(只存新特徵,索引同主面板)。"""
import os, sys, time
import numpy as np, pandas as pd

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "method_xgb", "src"))
from common import paths as P
import data as D, chip_data as C
from features.extra import extra_single_stock, extra_cross_section

START, END = "2016-01-01", "2026-09-11"
base = pd.read_parquet(os.path.join(P.FEATURES, f"features_top100_{START}_{END}.parquet"), columns=["close"])
tickers = sorted(base.index.get_level_values("ticker").unique())
raw = D.fetch_yfinance(tickers, START, END, cache_dir=D.CACHE_DIR); chips = C.load_chip(tickers, START, END)
t0 = time.time(); parts = []
for tk in tickers:
    df = raw[tk][["open", "high", "low", "close", "volume"]].astype(float); df = df[~df.index.duplicated()].sort_index()
    x = extra_single_stock(df, chips.get(tk, {})); x.index = pd.MultiIndex.from_arrays([df.index, np.repeat(tk, len(df))], names=["date", "ticker"]); parts.append(x)
ex = pd.concat(parts).reindex(base.index)
ex = pd.concat([ex, extra_cross_section(pd.concat([base, ex], axis=1))], axis=1).replace([np.inf, -np.inf], np.nan).astype("float32")
fp = os.path.join(P.FEATURES, f"features_top100_extra_{START}_{END}.parquet"); ex.to_parquet(fp)
fam = {c: ("longmom" if c.startswith(("mom_", "dist_high_250", "mad_", "sma_ratio_250", "fip_", "resid_mom", "persist")) else "overnight" if c.startswith(("on_", "id_")) else "chip") for c in ex.columns}
pd.DataFrame({"name": list(fam), "family": list(fam.values())}).to_csv(os.path.join(R, "method_xgb", "config", "feature_catalog_top100_extra.csv"), index=False)
print(f"[SAVED] {fp} {ex.shape} {time.time()-t0:.0f}s;各群欄數 {pd.Series(fam).value_counts().to_dict()}")
print("缺值率最高的 8 欄:", ex.isna().mean().sort_values(ascending=False).head(8).round(3).to_dict())
