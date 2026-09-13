"""
一次性預下載股價資料到本地快取 (cache/<ticker>.parquet + _manifest.json)。

下載完成後, 所有實驗腳本 (run_paper_repro / grid_search_paper / run_xgb_baseline)
都直接讀本地檔, 不再打網路。

用法:
  python test/download_data.py                          # 全部台股池, 2016-2024
  python test/download_data.py --tickers elec_all       # 只下載全電子池
  python test/download_data.py --end 2025-12-31         # 延長區間 (自動擴充主檔)
  python test/download_data.py --retry-empty            # 重試先前查無資料的股票
"""
import argparse
import os as _os
import sys as _sys

_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.join(_root, "core"))

from data_loader import (TICKER_SETS, fetch_yfinance,
                         load_manifest, save_manifest, DEFAULT_CACHE_DIR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="all",
                    choices=["all"] + list(TICKER_SETS),
                    help="all = 所有台股池聯集 (不含 sse50)")
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default="2024-12-31")
    ap.add_argument("--retry-empty", action="store_true",
                    help="清除「查無資料」標記, 重新嘗試下載這些股票")
    args = ap.parse_args()

    if args.tickers == "all":
        seen = set()
        tickers = []
        for name, lst in TICKER_SETS.items():
            if name == "sse50":     # 上證50 僅 chinatest 用, 需要時單獨指定
                continue
            for tk in lst:
                if tk not in seen:
                    seen.add(tk)
                    tickers.append(tk)
    else:
        tickers = TICKER_SETS[args.tickers]

    if args.retry_empty:
        manifest = load_manifest()
        removed = [tk for tk in tickers
                   if manifest.get(tk, {}).get("empty")]
        for tk in removed:
            del manifest[tk]
        save_manifest(manifest)
        print(f"[RETRY] 已清除 {len(removed)} 檔查無資料標記")

    print(f"[FETCH] {args.tickers}: {len(tickers)} 檔, "
          f"{args.start} ~ {args.end}")
    data = fetch_yfinance(tickers, args.start, args.end)

    manifest = load_manifest()
    empty = [tk for tk in tickers if manifest.get(tk, {}).get("empty")]
    print(f"\n[DONE] 取得 {len(data)} 檔 / 查無資料 {len(empty)} 檔")
    if empty:
        print(f"[EMPTY] {', '.join(empty)}")
    print(f"[CACHE] {DEFAULT_CACHE_DIR}")


if __name__ == "__main__":
    main()
