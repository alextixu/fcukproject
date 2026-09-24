"""FinMind 籌碼資料下載與讀取(三大法人、融資融券、外資持股)。

- 免 token 可用;有 FINMIND_TOKEN 環境變數時自動帶上(額度較高)。
- 每檔每個 dataset 一次抓全區間,存 data/finmind/<dataset>/<stock_id>.parquet;已存在者跳過(可中斷續跑)。
- 遇 402 / 429(額度用完)休息 10 分鐘再試。

用法: python src/chip_data.py --pool tw200 [--start 2016-01-01 --end 2024-12-31]
"""
import argparse
import json
import os
import sys
import time

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.dirname(ROOT))
from common import paths as P
DATA_DIR = os.environ.get("FINMIND_DIR") or P.FINMIND
BASE_URL = "https://api.finmindtrade.com/api/v4/data"

DATASETS = {
    "institutional": "TaiwanStockInstitutionalInvestorsBuySell",
    "margin": "TaiwanStockMarginPurchaseShortSale",
    "shareholding": "TaiwanStockShareholding",
}


def stock_id(ticker: str) -> str:
    return ticker.split(".")[0]


def _path(key, sid):
    return os.path.join(DATA_DIR, key, f"{sid}.parquet")


def fetch_one(key, sid, start, end, sleep=1.0, max_retry=6):
    fp = _path(key, sid)
    if os.path.exists(fp):
        return "cached"
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    params = {"dataset": DATASETS[key], "data_id": sid, "start_date": start, "end_date": end}
    headers = {}
    tok = os.environ.get("FINMIND_TOKEN", "").strip()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    for attempt in range(max_retry):
        try:
            r = requests.get(BASE_URL, params=params, headers=headers, timeout=90)
        except requests.RequestException as e:
            print(f"    網路錯誤 {e},60s 後重試", flush=True)
            time.sleep(60)
            continue
        if r.status_code in (402, 429):
            print(f"    額度限制 HTTP {r.status_code},休息 600s (attempt {attempt + 1})", flush=True)
            time.sleep(600)
            continue
        if r.status_code != 200:
            print(f"    HTTP {r.status_code}: {r.text[:200]}", flush=True)
            time.sleep(30)
            continue
        d = r.json()
        if d.get("status") != 200:
            print(f"    API status {d.get('status')}: {d.get('msg')}", flush=True)
            time.sleep(30)
            continue
        df = pd.DataFrame(d.get("data", []))
        if df.empty:
            df = pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]")})
        df.to_parquet(fp)
        time.sleep(sleep)
        return "ok" if len(df) else "empty"
    return "failed"


def download_pool(pool, start, end, keys=None):
    sys.path.insert(0, HERE)
    from data import TICKER_SETS
    tickers = TICKER_SETS[pool]
    keys = keys or list(DATASETS)
    total = len(tickers) * len(keys)
    done = 0
    t0 = time.time()
    stats = {}
    for key in keys:
        for tk in tickers:
            sid = stock_id(tk)
            s = fetch_one(key, sid, start, end)
            stats[s] = stats.get(s, 0) + 1
            done += 1
            if s != "cached" and done % 10 == 0 or s == "failed":
                print(f"  [{key}] {done}/{total} {sid} {s}  ({time.time() - t0:.0f}s)", flush=True)
    print(f"[DONE] {stats}  {time.time() - t0:.0f}s", flush=True)


def load_chip(tickers, start, end):
    """回傳 {ticker: {"institutional": df, "margin": df, "shareholding": df}};缺檔者略過。"""
    out = {}
    for tk in tickers:
        sid = stock_id(tk)
        parts = {}
        for key in DATASETS:
            fp = _path(key, sid)
            if not os.path.exists(fp):
                continue
            df = pd.read_parquet(fp)
            if df.empty or "date" not in df.columns:
                continue
            df["date"] = pd.to_datetime(df["date"])
            df = df[(df["date"] >= start) & (df["date"] <= end)]
            if len(df):
                parts[key] = df
        if parts:
            out[tk] = parts
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="tw200")
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default="2024-12-31")
    ap.add_argument("--keys", default=None, help="逗號分隔: institutional,margin,shareholding")
    a = ap.parse_args()
    download_pool(a.pool, a.start, a.end, a.keys.split(",") if a.keys else None)
