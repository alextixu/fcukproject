"""第 0 步:按日期抓證交所「每日收盤行情」(全市場上市股票)與三張參考價表(除權息 / 減資 / 面額變更)。

  規格見 docs/2026-09-21_新流程事前登記_…md 第二節。每交易日一個 parquet,可續跑;非交易日記在 _no_data.json 不重抓。
  間隔 3 秒 + 0~1 秒抖動;失敗 10 秒起指數退避、最多 5 次,仍失敗就中止(不硬打)。
  **2026-10-01 以後屬於凍結段,本腳本拒絕抓取。**

用法: python common/fetch_twse_daily.py [--start 20140102] [--end 20260921]
輸出: common/cache/twse_daily/YYYYMMDD.parquet、common/cache/twse_events/{exright,reduction,parchange}.parquet
"""
import argparse, json, os, random, sys, time
import pandas as pd, requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from common import paths as P

OUT, EVT = os.path.join(P.CACHE, "twse_daily"), os.path.join(P.CACHE, "twse_events")
FROZEN_FROM = pd.Timestamp("2026-10-01")
UA = {"User-Agent": "Mozilla/5.0"}
QUOTES = "https://www.twse.com.tw/exchangeReport/MI_INDEX"
EVENTS = {"exright": "https://www.twse.com.tw/rwd/zh/exRight/TWT49U",
          "reduction": "https://www.twse.com.tw/rwd/zh/reducation/TWTAUU",
          "parchange": "https://www.twse.com.tw/rwd/zh/change/TWTB8U"}


def get_json(url, params):
    wait = 10
    for attempt in range(5):
        time.sleep(3 + random.random())
        try:
            r = requests.get(url, params=params, headers=UA, timeout=30)
            return r.json()
        except Exception as e:                       # 連線失敗或回傳不是 JSON(被擋時會回 HTML)
            print(f"  [retry {attempt + 1}] {type(e).__name__}: {str(e)[:80]};等 {wait}s", flush=True)
            time.sleep(wait); wait *= 2
    raise SystemExit("連續 5 次失敗,中止(不硬打);稍後用同一指令續跑")


def num(s):
    return pd.to_numeric(pd.Series(s, dtype="object").astype(str).str.replace(",", "", regex=False).replace({"--": None, "": None}), errors="coerce")


def fetch_quotes(d: pd.Timestamp):
    j = get_json(QUOTES, {"response": "json", "date": d.strftime("%Y%m%d"), "type": "ALLBUT0999"})
    if j.get("stat") != "OK":
        return None
    tabs = [t for t in j.get("tables", []) if t.get("fields") and "證券代號" in t["fields"] and "收盤價" in t["fields"]]
    if not tabs:
        return None
    t = max(tabs, key=lambda x: len(x.get("data") or [])); f = t["fields"]; raw = pd.DataFrame(t["data"], columns=f)
    return pd.DataFrame({"date": d, "code": raw["證券代號"].str.strip(), "name": raw["證券名稱"].str.strip(),
                         "volume": num(raw["成交股數"]), "trades": num(raw["成交筆數"]), "turnover": num(raw["成交金額"]),
                         "open": num(raw["開盤價"]), "high": num(raw["最高價"]), "low": num(raw["最低價"]), "close": num(raw["收盤價"])})


def fetch_events(start: pd.Timestamp, end: pd.Timestamp):
    os.makedirs(EVT, exist_ok=True)
    for name, url in EVENTS.items():
        rows, fields = [], None
        for y in range(start.year, end.year + 1):                      # 一年一次請求
            s, e = max(start, pd.Timestamp(f"{y}-01-01")), min(end, pd.Timestamp(f"{y}-12-31"))
            j = get_json(url, {"response": "json", "startDate": s.strftime("%Y%m%d"), "endDate": e.strftime("%Y%m%d")})
            if j.get("stat") == "OK" and j.get("data"):
                fields = j["fields"]; rows += j["data"]
            print(f"[events] {name} {y}: {len(j.get('data') or [])} 筆", flush=True)
        if rows:
            pd.DataFrame(rows, columns=fields).astype(str).to_parquet(os.path.join(EVT, f"{name}.parquet"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--start", default="20140102"); ap.add_argument("--end", default="20260921")
    a = ap.parse_args(); start, end = pd.Timestamp(a.start), pd.Timestamp(a.end)
    assert end < FROZEN_FROM, "2026-10-01 以後是凍結段,這支腳本不抓"
    os.makedirs(OUT, exist_ok=True)
    nd_fp = os.path.join(OUT, "_no_data.json"); no_data = set(json.load(open(nd_fp))) if os.path.exists(nd_fp) else set()
    fetch_events(start, end)
    days = [d for d in pd.bdate_range(start, end) if d.strftime("%Y%m%d") not in no_data
            and not os.path.exists(os.path.join(OUT, d.strftime("%Y%m%d") + ".parquet"))]
    print(f"[quotes] 待抓 {len(days)} 個平日", flush=True)
    for i, d in enumerate(days):
        df = fetch_quotes(d); key = d.strftime("%Y%m%d")
        if df is None or df.empty:
            no_data.add(key); json.dump(sorted(no_data), open(nd_fp, "w"))
        else:
            df.to_parquet(os.path.join(OUT, key + ".parquet"))
        if i % 50 == 0:
            print(f"[quotes] {i}/{len(days)} {key} {'無資料' if df is None else len(df)}  {time.strftime('%H:%M:%S')}", flush=True)
    print("[DONE]", time.strftime("%H:%M:%S"), flush=True)
