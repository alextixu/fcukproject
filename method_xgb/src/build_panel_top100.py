"""暫行股票池(2026-08-31 市值前 100 大、名單固定)的特徵面板:242 欄 + 新標籤。

  股票池: common/universe/top100_mktcap_20260831.csv(期交所「加權指數成分股暨市值比重」2026/8/31 的前 100 名)。
  價格:   yfinance 還原價快取(common/cache/yf_2026),以代碼為鍵。
  標籤:   r_oo_h5 = open[t+6] / open[t+1] − 1;y_oo_h5 = r_oo_h5 是否高於當日股票池中位數。
          進場日 t+1 或出場日 t+6 沒有開盤價 → 標籤缺值(該列不產生樣本)。
  特徵:   回看期不足的列設為缺值(features/lookback.py);市場層級特徵(mkt_roc_*)= 當日池內有報酬的股票之等權平均。
  ⚠ 暫行:名單用現在的排名回推,有存活者偏差;結果不作為論文最終結論。

輸出 common/cache/features/features_top100_2016-01-01_2026-09-11.parquet、config/feature_catalog_top100.csv
"""
import os, sys, time
import numpy as np, pandas as pd

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "method_xgb", "src"))
from common import paths as P
import data as D
from features import build_panel

START, END, H = "2016-01-01", "2026-09-11", 5
uni = pd.read_csv(os.path.join(R, "common", "universe", "top100_mktcap_20260831.csv"), dtype={"code": str})
tickers = [f"{c}.TW" for c in uni.code]
raw = D.fetch_yfinance(tickers, START, END, cache_dir=D.CACHE_DIR)
stock = {}
for tk in tickers:
    df = raw[tk][["open", "high", "low", "close", "volume"]].astype(float)
    df = df[~df.index.duplicated()].sort_index()
    assert (df["close"] > 0).all(), tk
    stock[tk] = df
print(f"股票 {len(stock)} 檔;最短 {min(len(v) for v in stock.values())} 列、最長 {max(len(v) for v in stock.values())} 列", flush=True)

t0 = time.time()
panel, fam = build_panel(stock, lookback_mask=True)
panel = panel.drop(columns=[c for c in panel.columns if c.startswith("p9_")])
op = panel["open"].unstack("ticker")
r = (op.shift(-(H + 1)) / op.shift(-1) - 1).stack(future_stack=True).reindex(panel.index)
panel[f"r_oo_h{H}"] = r.astype("float32")
med = r.groupby(level="date").transform("median")
panel[f"y_oo_h{H}"] = (r > med).astype("float32").where(r.notna())
fp = os.path.join(P.FEATURES, f"features_top100_{START}_{END}.parquet")
panel.to_parquet(fp)
feat_cols = [c for c in panel.columns if c in fam and fam[c] != "paper9"]
pd.DataFrame({"name": feat_cols, "family": [fam[c] for c in feat_cols]}).to_csv(
    os.path.join(R, "method_xgb", "config", "feature_catalog_top100.csv"), index=False)
print(f"[SAVED] {fp}  {panel.shape}  特徵 {len(feat_cols)} 欄  {time.time()-t0:.0f}s", flush=True)
