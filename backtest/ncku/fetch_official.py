"""用框架自己的 fetchers(證交所 / 櫃買官方 JSON)抓股票池的日資料,寫成框架格式 tmp/stock_data.csv。

框架原本的 load_all_stock_data() 下載路徑有 utcfromtimestamp 殘留 bug,且會抓全市場 2,000 檔(數小時),
這裡改成只抓指定池,其餘格式、資料源與框架完全相同。可續跑(每檔一個 parquet 快取在 tmp/official/)。

用法: python fetch_official.py --pools tw50,tw200 --start 20251001 --end 20260910
"""
import argparse
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from common import paths as P  # noqa: E402
sys.path.insert(0, P.CHARTGCN_CORE)
from backtest.stock_api.core import get_taiwan_stock_data, to_legacy_schema   # noqa: E402
from backtest.stock_api.symbols import get_stock_market                      # noqa: E402
from data_loader import TICKER_SETS                                          # noqa: E402

RAW = P.OFFICIAL
os.makedirs(RAW, exist_ok=True)


def fetch_one(code, start, end):
    fp = os.path.join(RAW, f"{code}.parquet")
    if os.path.exists(fp):
        return pd.read_parquet(fp)
    s = f"{start[:4]}-{start[4:6]}-{start[6:]}"
    e = f"{end[:4]}-{end[4:6]}-{end[6:]}"
    df = get_taiwan_stock_data(code, s, e)
    df.to_parquet(fp)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pools", default="tw50")
    ap.add_argument("--start", default="20251001")
    ap.add_argument("--end", default="20260910")
    a = ap.parse_args()
    codes = ["0050"]
    for p in a.pools.split(","):
        codes += [t.split(".")[0] for t in TICKER_SETS[p]]
    codes = list(dict.fromkeys(codes))
    print(f"[FETCH] {len(codes)} 檔  {a.start}~{a.end}", flush=True)
    t0 = time.time()
    frames = []
    for i, c in enumerate(codes, 1):
        try:
            df = fetch_one(c, a.start, a.end)
        except Exception as e:
            print(f"  {c} 失敗: {e}", flush=True)
            continue
        if df.empty:
            print(f"  {c} 無資料", flush=True)
            continue
        frames.append(df)
        if i % 10 == 0 or i == len(codes):
            print(f"  [{i}/{len(codes)}] {c} {len(df)} 列  {time.time() - t0:.0f}s", flush=True)
    all_df = pd.concat(frames, ignore_index=True)
    all_df["date"] = pd.to_datetime(all_df["date"]).dt.strftime("%Y%m%d")
    all_df["stock_code"] = all_df["stock_code_id"].astype(str)
    cols = ["stock_code", "date", "capacity", "turnover", "high", "low", "close", "change",
            "transaction_volume", "stock_code_id", "open"]
    all_df = all_df[cols].sort_values(["stock_code", "date"])
    all_df.to_csv(os.path.join(HERE, "tmp", "stock_data.csv"), index=False)
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write(f"end_date: '{a.end}'\nstart_date: '{a.start}'\n")
    print(f"[DONE] {len(all_df)} 列, {all_df.stock_code.nunique()} 檔 → tmp/stock_data.csv  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
