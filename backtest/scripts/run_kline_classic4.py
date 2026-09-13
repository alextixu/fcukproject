"""KLINE 流程 × 四大指標:把特徵換成 MA / MACD / KD / RSI(定義沿用 xgb_ta_pipeline features.CLASSIC_SETS),
其餘照 KLINE:TW50、正例 = 5 日報酬 > +5%(看漲)/ < -5%(看跌)、訓練 2016 ~ 2025-12-22、測試 2026-01-01 ~ 09-10。
每個指標集各跑:
  原版  AE + OC-SVM(validate.validate_features:80/20 驗證段的 Precision / Recall / Acc)+ pattern_model 2026 回測
  有監督 AE 4 維 + XGB(supervised_model,最有把握 10% 出訊號)驗證 AUC / 命中率 + 2026 回測
用法: python backtest_2026/run_kline_classic4.py   →  results/kline_classic4_2026.json
"""
import json, os, sys, time
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "method_xgb", "src"))
from run_kline_2026 import load_raw, open_to_open_ret, TEST_START, TEST_END, TRAIN_END, OUT   # noqa
from run_kline_sup_2026 import non_overlap, summarize                                          # noqa
from kline.config import HOLD_DAYS, TRADE_COST, RISE_THRESH, FALL_THRESH                       # noqa
from kline.features import features_1day                                                       # noqa
from kline.data_loader import build_dataset                                                    # noqa
from kline.validate import validate_features                                                   # noqa
from kline.pattern_model import find_and_train                                                 # noqa
from kline.backtest import backtest                                                            # noqa
from kline.supervised_model import train_supervised, predict_signal                            # noqa
from features import CLASSIC_SETS                                                              # noqa
from features.trend import trend_features                                                      # noqa
from features.momentum import momentum_features                                                # noqa


def classic_fn(cols):
    def fn(df):
        x = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
        f = {}; f.update(trend_features(x)); f.update(momentum_features(x))
        return pd.DataFrame({c: f[c] for c in cols}, index=df.index)
    return fn


SETS = [("MA", CLASSIC_SETS["ma"]), ("MACD", CLASSIC_SETS["macd"]), ("KD", CLASSIC_SETS["kd"]), ("RSI", CLASSIC_SETS["rsi"]),
        ("四個合併", CLASSIC_SETS["classic4"]), ("K線1日(原特徵)", None)]


def main():
    t0 = time.time(); raw = load_raw(); tickers = list(raw)
    out = {}
    for name, cols in SETS:
        fn = features_1day if cols is None else classic_fn(cols)
        df = build_dataset(raw, fn)
        feat = [c for c in df.columns if c not in ("future_ret", "ticker")]
        te = df[(df.index >= TEST_START) & (df.index <= TEST_END)]
        base26 = {"up5": float((te.future_ret > RISE_THRESH).mean()), "dn5": float((te.future_ret < FALL_THRESH).mean()), "up0": float((te.future_ret > 0).mean())}
        print(f"\n===== {name}: {feat} =====", flush=True)
        rec = {"features": feat, "base26": base26}
        # 原版驗證
        v = validate_features(df, feat, lambda s: None)
        tr = df[(df.index >= "2016-01-01") & (df.index <= "2024-12-31")]
        d = tr.index.unique().sort_values(); val = tr[tr.index >= d[int(len(d) * 0.8)]]
        rec["ocsvm_val"] = {k: {**v[k], "base": float((val.future_ret > RISE_THRESH).mean() if k == "bull" else (val.future_ret < FALL_THRESH).mean())} for k in ("bull", "bear") if v.get(k)}
        for k, lab in (("bull", "看漲"), ("bear", "看跌")):
            r = rec["ocsvm_val"].get(k)
            if r: print(f"  原版 OC-SVM 驗證 {lab}:Acc {r['accuracy']*100:.1f}%(全猜否 {100-r['base']*100:.1f}%) Precision {r['precision']*100:.2f}%(隨機 {r['base']*100:.2f}%) Recall {r['recall']*100:.1f}%  出訊號 {(r['TP']+r['FP'])/len(val)*100:.1f}%", flush=True)
        # 原版 2026 回測
        models = find_and_train(df, feat, lambda s: None)
        rows = []
        for tk in tickers:
            res = backtest(df, feat, models, tk)
            if res is None: continue
            td = te[te.ticker == tk]; oo = open_to_open_ret(raw[tk]).reindex(td.index); ex = res["signal"]
            for i in np.where(ex != 0)[0]:
                rows.append({"ticker": tk, "side": int(ex[i]), "ret_close": float(res["strategy_ret"][i]),
                             "ret_open": float(ex[i] * oo.iloc[i] - TRADE_COST) if np.isfinite(oo.iloc[i]) else np.nan})
        t = pd.DataFrame(rows)
        rec["ocsvm_2026"] = _oos(t, te, base26, tickers)
        print("  原版 OC-SVM 2026:" + _fmt(rec["ocsvm_2026"]), flush=True)
        # 有監督
        sm = train_supervised(df, feat, lambda s: None, clf="xgb", space="latent")
        rows = []
        for tk in tickers:
            td = te[te.ticker == tk]
            if td.empty: continue
            ex = non_overlap(predict_signal(sm, td[feat].values)); oo = open_to_open_ret(raw[tk]).reindex(td.index)
            for i in np.where(ex != 0)[0]:
                rows.append({"ticker": tk, "side": int(ex[i]), "ret_close": float(ex[i] * td.future_ret.iloc[i] - TRADE_COST),
                             "ret_open": float(ex[i] * oo.iloc[i] - TRADE_COST) if np.isfinite(oo.iloc[i]) else np.nan})
        t = pd.DataFrame(rows)
        rec["sup_val"] = {k: sm[k]["val"] for k in ("bull", "bear")}
        rec["sup_2026"] = _oos(t, te, base26, tickers)
        print(f"  有監督 AE+XGB 驗證:看漲 AUC {sm['bull']['val']['auc']:.3f} 前10%命中 {sm['bull']['val']['prec_top']*100:.1f}%(隨機 {sm['bull']['val']['base_rate']*100:.1f}%) | 看跌 AUC {sm['bear']['val']['auc']:.3f} 前10%命中 {sm['bear']['val']['prec_top']*100:.1f}%(隨機 {sm['bear']['val']['base_rate']*100:.1f}%)", flush=True)
        print("  有監督 AE+XGB 2026:" + _fmt(rec["sup_2026"]), flush=True)
        out[name] = rec
    json.dump(out, open(os.path.join(OUT, "kline_classic4_2026.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(f"\n[SAVED] results/kline_classic4_2026.json ({time.time()-t0:.0f}s)")


def _oos(t, te, base, tickers):
    if not len(t): return {"n_buy": 0, "n_sell": 0}
    g = t.ret_close + TRADE_COST; b, s = t[t.side == 1], t[t.side == -1]
    r = {"n_buy": int(len(b)), "n_sell": int(len(s)), "cover_pct": round(len(t) / len(te) * 100, 2),
         "buy_hit_up5": round(float((g[t.side == 1] > RISE_THRESH).mean()) * 100, 2) if len(b) else None,
         "buy_hit_up0": round(float((g[t.side == 1] > 0).mean()) * 100, 2) if len(b) else None,
         "sell_hit_dn5": round(float((-g[t.side == -1] < FALL_THRESH).mean()) * 100, 2) if len(s) else None,
         "buy_avg_open": round(float(b.ret_open.mean()), 3) if len(b) else None,
         "sell_avg_open": round(float(s.ret_open.mean()), 3) if len(s) else None}
    r.update({k: v for k, v in summarize(t, tickers).items() if k in ("close", "open")})
    return r


def _fmt(r):
    if not r.get("n_buy") and not r.get("n_sell"): return "無訊號"
    return (f"買 {r['n_buy']} 賣 {r['n_sell']}(佔 {r['cover_pct']}%) 買訊號漲>5% {r['buy_hit_up5']}%、漲>0 {r['buy_hit_up0']}%"
            + (f"、賣訊號跌>5% {r['sell_hit_dn5']}%" if r["n_sell"] else "") + f";買每筆 {r['buy_avg_open']}%;組合 open {r['open']['portfolio_ret_pct']:+.2f}%")


if __name__ == "__main__":
    main()
