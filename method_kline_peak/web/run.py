"""網頁系統的指令。

  python method_kline_peak/web/run.py daily            每日批次(更新 K 線 → 判斷並存檔 → 對答案 → 產生網頁資料)
  python method_kline_peak/web/run.py daily --offline  不連網,只用快取的 K 線
  python method_kline_peak/web/run.py replay --start 2026-01-02 [--end 2026-09-10]
                                                       上線前的日子逐日產生回放存檔(成績追蹤的歷史)
  python method_kline_peak/web/run.py train --year 2026   訓練(重訓)某一年的正式模型
  python method_kline_peak/web/run.py publish          只重新產生網頁資料
  python method_kline_peak/web/run.py serve [--port 8000]  開本機網頁 http://localhost:8000
  python method_kline_peak/web/run.py start            每日批次 + 開本機網頁
共通參數:--universe all(全部上市普通股,預設)/ tw200(研究用 TW200 清單)
          --pool tw200(訓練用股票池,預設;可換 tw100 等 TICKER_SETS 的名稱,一樣剔除低波動股)
          --train-min-amp 0(訓練門檻 %,預設 0)
          也可以用環境變數 KPWEB_POOL、KPWEB_TRAIN_MIN_AMP 設定。每組設定的存檔分開放在 data/<設定>/。
"""
import argparse
import functools
import http.server
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
warnings.filterwarnings("ignore")

from system import config as C  # noqa: E402


def serve(port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=C.SITE)
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"本機網頁:http://localhost:{port}(Ctrl+C 結束)", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def main():
    ap = argparse.ArgumentParser(description="K 線高低點判斷網頁")
    ap.add_argument("cmd", choices=["daily", "replay", "train", "publish", "serve", "start"])
    ap.add_argument("--offline", action="store_true", help="不連網,只用快取")
    ap.add_argument("--date", help="判斷基準日(預設今天;用於補跑或測試)")
    ap.add_argument("--start", help="replay 起日")
    ap.add_argument("--end", help="replay 迄日")
    ap.add_argument("--year", type=int, help="train 的年份")
    ap.add_argument("--universe", default="all", choices=["all", "tw200"])
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--pool", default=C.POOL, help="訓練用股票池(data_loader.TICKER_SETS 的名稱),預設 tw200")
    ap.add_argument("--train-min-amp", type=float, default=C.TRAIN_MIN_AMP, help="訓練門檻(%%),預設 0")
    a = ap.parse_args()
    C.set_profile(a.pool, a.train_min_amp)
    print(f"設定:{C.profile()}(股票池 {C.POOL}、訓練門檻 {C.TRAIN_MIN_AMP:g}%)", flush=True)
    log = functools.partial(print, flush=True)
    from system import pipeline as PL, model as MD, datasource as DS  # noqa: E402
    if a.cmd in ("daily", "start"):
        PL.run_daily(asof=a.date, online=not a.offline, kind=a.universe, log=log)
    if a.cmd == "replay":
        PL.run_replay(a.start or "2026-01-01", a.end, kind=a.universe, log=log)
    if a.cmd == "train":
        MD.train(a.year, DS.PriceStore(), log)
    if a.cmd == "publish":
        import pandas as pd
        from system import store as ST, universe as U  # noqa: E402
        st = DS.PriceStore()
        m = MD.load(int(ST.list_days()[-1][:4])) or MD.load(int(ST.list_days()[-1][:4]) - 1)
        ticks = sorted(set(U.universe(a.universe)) | set(m["pool"]) | set(U.recommend_list()))
        data = st.load_many(ticks, end=ST.list_days()[-1])
        cal = PL._calendar(data, U.recommend_list())
        last = ST.read_day(ST.list_days()[-1])
        from system import publish as PB  # noqa: E402
        PB.publish(data, cal, last.get("check") or {}, log=log)
    if a.cmd in ("serve", "start"):
        serve(a.port)


if __name__ == "__main__":
    main()
