"""把 chartgcn/cache_2026 的 yfinance 還原價轉成框架官方資料同格式 → tmp/yf/<code>.parquet(大池篩選用)。

欄位對齊 fetchers 輸出:date, stock_code_id, market, capacity(股), turnover(元,量×收盤估算), open, high, low, close,
change(收盤差), transaction_volume(yfinance 無 → 0), close_is_proxy。區間 2025-10-01 ~ 2026-09-10(同官方快取)。
用法: python make_yf_src.py --pools tw50,tw100,tw200,tw500,elec_all
"""
import argparse
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
CACHE = P.YF_2026_CACHE
OUT = None
sys.path.insert(0, P.CHARTGCN_CORE)
from data_loader import TICKER_SETS   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pools", default="tw50,tw100,tw200,tw500,elec_all")
    ap.add_argument("--start", default="2025-10-01")
    ap.add_argument("--end", default="2026-09-10")
    ap.add_argument("--out", default="yf", help="tmp/ 底下的資料夾名(NCKU_SRC 用同名)")
    a = ap.parse_args()
    global OUT
    OUT = os.path.join(P.CACHE, {"yf": "yf_fw"}.get(a.out, a.out))
    os.makedirs(OUT, exist_ok=True)
    tks = ["0050.TW"]
    for p in a.pools.split(","):
        tks += TICKER_SETS[p]
    tks = list(dict.fromkeys(tks))
    n = 0
    for tk in tks:
        fp = os.path.join(CACHE, f"{tk}.parquet")
        if not os.path.exists(fp):
            continue
        x = pd.read_parquet(fp).loc[a.start:a.end]
        if x.empty:
            continue
        c = tk.split(".")[0]
        df = pd.DataFrame({
            "date": pd.to_datetime(x.index), "stock_code_id": c, "market": "YF",
            "capacity": x["volume"].astype(float).values, "turnover": (x["volume"] * x["close"]).astype(float).values,
            "open": x["open"].values, "high": x["high"].values, "low": x["low"].values, "close": x["close"].values,
            "change": x["close"].diff().values, "transaction_volume": 0, "close_is_proxy": False})
        df = df[df["volume" if "volume" in df else "capacity"] > 0]      # 停牌日(量 0)不視為交易日
        df.to_parquet(os.path.join(OUT, f"{c}.parquet"), index=False)
        n += 1
    print(f"[DONE] {n}/{len(tks)} 檔 → tmp/{a.out}/({a.start} ~ {a.end})")


if __name__ == "__main__":
    main()
