"""把指定股票池的官方資料補到 --end:沒有檔案的抓 2025-10-01 起全段,已有的只補 9 月並合併去重。"""
import argparse, os, sys, time
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "..", "chartgcn", "core"))
from backtest.stock_api.core import get_taiwan_stock_data
from data_loader import TICKER_SETS
ap = argparse.ArgumentParser(); ap.add_argument("--pools", default="tw100,elec_liq100"); ap.add_argument("--end", default="2026-09-11"); a = ap.parse_args()
codes = list(dict.fromkeys(["0050"] + [t.split(".")[0] for p in a.pools.split(",") for t in TICKER_SETS[p]]))
D = os.path.join(HERE, "tmp", "official"); t0 = time.time(); n_new = n_upd = n_fail = 0
for i, c in enumerate(codes, 1):
    fp = os.path.join(D, f"{c}.parquet")
    try:
        if os.path.exists(fp):
            old = pd.read_parquet(fp); old["date"] = pd.to_datetime(old["date"])
            if old["date"].max() >= pd.Timestamp(a.end):
                continue
            new = get_taiwan_stock_data(c, "2026-09-01", a.end); new["date"] = pd.to_datetime(new["date"])
            m = pd.concat([old, new[[x for x in old.columns if x in new.columns]]], ignore_index=True).drop_duplicates("date", keep="last").sort_values("date")
            m.to_parquet(fp, index=False); n_upd += 1
        else:
            df = get_taiwan_stock_data(c, "2025-10-01", a.end); df.to_parquet(fp, index=False); n_new += 1
    except Exception as e:
        n_fail += 1; print(f"  {c} 失敗: {e}", flush=True)
    if i % 20 == 0:
        print(f"  [{i}/{len(codes)}] 新 {n_new} 更新 {n_upd} 失敗 {n_fail}  {time.time()-t0:.0f}s", flush=True)
print(f"[DONE] 新 {n_new} 更新 {n_upd} 失敗 {n_fail}  {time.time()-t0:.0f}s")
