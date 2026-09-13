"""系統 A(KLINE main 分支:K 線型態 + AE + OC-SVM)2026 年回測,無 GUI 版。

與 GUI「③ 分析 + 回測」同一套程式(kline 套件),只改時間切分:
  訓練 2016-01-01 ~ 2025-12-22(往前 purge 5 個交易日,避免 5 日標籤看到 2026)
  測試 2026-01-01 ~ 2026-09-10
對 TW50 全部 50 檔逐檔回測(GUI 一次只回測一檔),彙整成等權 50 格組合。

報酬兩種口徑:
  close  = 系統原本定義:訊號日收盤進場、5 日後收盤出場(未還原價,已排除除權息日訊號)
  open   = 可交易口徑:訊號隔日開盤進場、再 5 個交易日後開盤出場(還原權息)
兩種都扣系統原本的每筆成本 0.42%。

用法: python backtest_2026/run_kline_2026.py
輸出: backtest_2026/results/kline_2026.json、kline_2026_trades.parquet、kline_2026_curve.parquet
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
KLINE = P.METHOD_KLINE
RAW_DIR = P.KLINE_RAW
OUT = P.RESULTS
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, KLINE)

import kline.config as C  # noqa: E402

TRAIN_END = "2025-12-22"      # 2025-12-31 往前 5 個交易日(HOLD_DAYS=5 的 purge)
TEST_START, TEST_END = "2026-01-01", "2026-09-10"
C.TRAIN_END, C.TEST_START, C.TEST_END = TRAIN_END, TEST_START, TEST_END

from kline.config import TW50, HOLD_DAYS, TRADE_COST          # noqa: E402
from kline.features import FEATURE_SETS                        # noqa: E402
from kline.data_loader import build_dataset                    # noqa: E402
from kline.pattern_model import find_and_train                 # noqa: E402
from kline.backtest import backtest                            # noqa: E402


def load_raw():
    import yfinance as yf
    raw = {}
    for tk in TW50:
        fp = os.path.join(RAW_DIR, f"{tk}.parquet")
        if os.path.exists(fp):
            raw[tk] = pd.read_parquet(fp)
            continue
        df = yf.download(tk, start="2015-01-01", end="2026-09-11",
                         auto_adjust=False, progress=False, actions=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        need = {"Open", "High", "Low", "Close", "Volume", "Adj Close"}
        if df.empty or len(df) < 100 or not need.issubset(df.columns):
            print(f"  {tk} 跳過")
            continue
        df.to_parquet(fp)
        raw[tk] = df
    return raw


def open_to_open_ret(df):
    """訊號日 t → (t+1 開盤, t+1+HOLD 開盤) 的還原報酬(%)。"""
    adj = df["Adj Close"] / df["Close"]
    o = df["Open"] * adj
    return (o.shift(-(1 + HOLD_DAYS)) / o.shift(-1) - 1) * 100


def main():
    t0 = time.time()
    raw = load_raw()
    print(f"[DATA] {len(raw)} 檔;訓練 ≤ {TRAIN_END},測試 {TEST_START} ~ {TEST_END}", flush=True)
    bench = {tk: df.loc[TEST_START:TEST_END] for tk, df in raw.items()}
    # 等權買進持有(還原收盤,測試期第一天收盤 → 最後一天收盤)
    bh = {tk: float(d["Adj Close"].iloc[-1] / d["Adj Close"].iloc[0] - 1) for tk, d in bench.items() if len(d)}
    ew_bh = float(np.mean(list(bh.values())))

    summary, trades_all, curves = {}, [], {}
    for name, fn in FEATURE_SETS:
        print(f"\n=== {name} ===", flush=True)
        df = build_dataset(raw, fn)
        feat_cols = [c for c in df.columns if c not in ("future_ret", "ticker")]
        models = find_and_train(df, feat_cols, lambda s: print(s, flush=True) if "Epoch" not in s else None)
        rows = []
        for tk in raw:
            res = backtest(df, feat_cols, models, tk)
            if res is None:
                continue
            td = df[(df.index >= TEST_START) & (df.index <= TEST_END) & (df["ticker"] == tk)]
            oo = open_to_open_ret(raw[tk]).reindex(td.index)
            ex = res["signal"]
            for i in np.where(ex != 0)[0]:
                r_open = ex[i] * oo.iloc[i] - TRADE_COST if np.isfinite(oo.iloc[i]) else np.nan
                rows.append({"set": name, "ticker": tk, "date": td.index[i], "side": int(ex[i]),
                             "ret_close": float(res["strategy_ret"][i]), "ret_open": float(r_open)})
        tr = pd.DataFrame(rows)
        trades_all.append(tr)
        s = {"n_trades": int(len(tr)), "n_buy": int((tr["side"] == 1).sum()) if len(tr) else 0,
             "n_sell": int((tr["side"] == -1).sum()) if len(tr) else 0,
             "n_tickers_traded": int(tr["ticker"].nunique()) if len(tr) else 0}
        for k in ("close", "open"):
            col = f"ret_{k}"
            if len(tr) == 0:
                s[k] = None
                continue
            x = tr[col].dropna()
            # 等權 50 格:每檔一格資金 1/N,格內非重疊交易依序複利,閒置持有現金
            sleeve = tr.dropna(subset=[col]).groupby("ticker")[col].apply(lambda r: float(np.prod(1 + r / 100) - 1))
            port = float(sleeve.reindex(list(raw)).fillna(0.0).mean())
            s[k] = {"avg_trade_pct": round(float(x.mean()), 3), "win_rate": round(float((x > 0).mean()), 4),
                    "t_stat": round(float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))), 2) if len(x) > 1 else None,
                    "portfolio_ret_pct": round(port * 100, 2),
                    "long_avg_pct": round(float(tr.loc[tr.side == 1, col].mean()), 3) if s["n_buy"] else None,
                    "short_avg_pct": round(float(tr.loc[tr.side == -1, col].mean()), 3) if s["n_sell"] else None}
        # 日曲線(open 口徑):每筆交易在出場日入帳,組合 = 50 格平均淨值
        if len(tr):
            dates = pd.bdate_range(TEST_START, TEST_END)
            vals = []
            for tk in raw:
                t = tr[(tr.ticker == tk)].dropna(subset=["ret_open"]).sort_values("date")
                v = pd.Series(1.0, index=dates)
                for _, r in t.iterrows():
                    exit_d = r["date"] + pd.tseries.offsets.BDay(1 + HOLD_DAYS)
                    v[v.index >= exit_d] *= 1 + r["ret_open"] / 100
                vals.append(v)
            curves[name] = pd.concat(vals, axis=1).mean(axis=1) - 1
        summary[name] = s
        print(json.dumps(s, ensure_ascii=False), flush=True)

    out = {"system": "KLINE main(K線型態 AE+OC-SVM)", "train_end": TRAIN_END,
           "test": [TEST_START, TEST_END], "n_stocks": len(raw), "trade_cost_pct": TRADE_COST,
           "hold_days": HOLD_DAYS, "ew_buyhold_pct": round(ew_bh * 100, 2),
           "results": summary, "elapsed_s": round(time.time() - t0)}
    json.dump(out, open(os.path.join(OUT, "kline_2026.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    if trades_all:
        pd.concat(trades_all).to_parquet(os.path.join(OUT, "kline_2026_trades.parquet"))
    if curves:
        pd.DataFrame(curves).to_parquet(os.path.join(OUT, "kline_2026_curve.parquet"))
    print(f"\n[SAVED] results/kline_2026.json  ew_buyhold {out['ew_buyhold_pct']}%  ({out['elapsed_s']}s)")


if __name__ == "__main__":
    main()
