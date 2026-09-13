"""KLINE 有監督版(kline/supervised_model.py:OC-SVM → 分類器)2026 回測,口徑與 run_kline_2026.py 完全相同。

同 run_kline_2026:訓練 2016-01-01 ~ 2025-12-22、測試 2026-01-01 ~ 2026-09-10、TW50、非重疊持倉 5 日、每筆成本 0.42%,
close / open 兩種報酬口徑、等權 50 格組合。跑 3 個特徵集 × {logistic, xgb} × {AE 4 維, 原始特徵}。
用法: python backtest_2026/run_kline_sup_2026.py
輸出: results/kline_sup_2026.json、kline_sup_2026_trades.parquet
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_kline_2026 import load_raw, open_to_open_ret, TEST_START, TEST_END, TRAIN_END, OUT  # noqa: E402(同時套用時間切分)
from kline.config import HOLD_DAYS, TRADE_COST                     # noqa: E402
from kline.features import FEATURE_SETS                            # noqa: E402
from kline.data_loader import build_dataset                        # noqa: E402
from kline.supervised_model import train_supervised, predict_signal, SIG_FRAC  # noqa: E402

CONFIGS = [(c, s) for c in ('logistic', 'xgb') for s in ('latent', 'raw')]


def non_overlap(signal):
    ex, nxt = np.zeros_like(signal), 0
    for i in range(len(signal)):
        if signal[i] != 0 and i >= nxt:
            ex[i] = signal[i]; nxt = i + HOLD_DAYS
    return ex


def summarize(tr, tickers):
    s = {"n_trades": int(len(tr)), "n_buy": int((tr.side == 1).sum()), "n_sell": int((tr.side == -1).sum())}
    for k in ("close", "open"):
        col = f"ret_{k}"
        x = tr[col].dropna()
        sleeve = tr.dropna(subset=[col]).groupby("ticker")[col].apply(lambda r: float(np.prod(1 + r / 100) - 1))
        s[k] = {"avg_trade_pct": round(float(x.mean()), 3), "win_rate": round(float((x > 0).mean()), 4),
                "t_stat": round(float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))), 2) if len(x) > 1 else None,
                "portfolio_ret_pct": round(float(sleeve.reindex(tickers).fillna(0.0).mean()) * 100, 2),
                "long_avg_pct": round(float(tr.loc[tr.side == 1, col].mean()), 3) if s["n_buy"] else None,
                "short_avg_pct": round(float(tr.loc[tr.side == -1, col].mean()), 3) if s["n_sell"] else None}
    return s


def main():
    t0 = time.time()
    raw = load_raw()
    old = json.load(open(os.path.join(OUT, "kline_2026.json"), encoding="utf-8"))
    print(f"[DATA] {len(raw)} 檔;訓練 ≤ {TRAIN_END},測試 {TEST_START} ~ {TEST_END};等權買進持有 {old['ew_buyhold_pct']}%", flush=True)
    summary, trades = {}, []
    for name, fn in FEATURE_SETS:
        df = build_dataset(raw, fn)
        feat = [c for c in df.columns if c not in ("future_ret", "ticker")]
        te = df[(df.index >= TEST_START) & (df.index <= TEST_END)]
        up_all = float((te["future_ret"] > 0).mean())
        for clf, space in CONFIGS:
            key = f"{name}|{clf}|{space}"
            print(f"\n=== {key} ===", flush=True)
            models = train_supervised(df, feat, lambda s: print(s, flush=True), clf=clf, space=space)
            rows = []
            for tk in raw:
                td = te[te["ticker"] == tk]
                if td.empty:
                    continue
                ex = non_overlap(predict_signal(models, td[feat].values))
                oo = open_to_open_ret(raw[tk]).reindex(td.index)
                for i in np.where(ex != 0)[0]:
                    rc = ex[i] * td["future_ret"].iloc[i] - TRADE_COST
                    ro = ex[i] * oo.iloc[i] - TRADE_COST if np.isfinite(oo.iloc[i]) else np.nan
                    rows.append({"cfg": key, "ticker": tk, "date": td.index[i], "side": int(ex[i]), "ret_close": float(rc), "ret_open": float(ro)})
            tr = pd.DataFrame(rows)
            trades.append(tr)
            s = summarize(tr, list(raw)) if len(tr) else {"n_trades": 0}
            s["val"] = {d: models[d]["val"] for d in ("bull", "bear")}
            s["signal_cover_pct"] = round(len(tr) / len(te) * 100, 2)
            buy = tr[tr.side == 1]
            s["buy_hit_5d_pct"] = round(float(((buy.ret_close + TRADE_COST) > 0).mean()) * 100, 2) if len(buy) else None
            s["up_all_pct"] = round(up_all * 100, 2)
            summary[key] = s
            print(f"  2026:訊號 {s['n_trades']}(買 {s.get('n_buy')} 賣 {s.get('n_sell')},佔股票日 {s['signal_cover_pct']}%)  買訊號 5 日方向命中 {s['buy_hit_5d_pct']}%(隨便買 {s['up_all_pct']}%)"
                  + (f"  組合 close {s['close']['portfolio_ret_pct']:+.2f}% / open {s['open']['portfolio_ret_pct']:+.2f}%  每筆 {s['open']['avg_trade_pct']:+.3f}% t {s['open']['t_stat']}" if s["n_trades"] else ""), flush=True)
    out = {"system": "KLINE 有監督版(AE + 分類器,取代 OC-SVM)", "train_end": TRAIN_END, "test": [TEST_START, TEST_END],
           "sig_frac": SIG_FRAC, "trade_cost_pct": TRADE_COST, "hold_days": HOLD_DAYS, "ew_buyhold_pct": old["ew_buyhold_pct"],
           "original": old["results"], "results": summary, "elapsed_s": round(time.time() - t0)}
    json.dump(out, open(os.path.join(OUT, "kline_sup_2026.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    pd.concat(trades).to_parquet(os.path.join(OUT, "kline_sup_2026_trades.parquet"))
    print(f"\n[SAVED] results/kline_sup_2026.json ({out['elapsed_s']}s)")


if __name__ == "__main__":
    main()
