"""KLINE(AE)原特徵 + 四大指標(MA / MACD / KD / RSI,定義沿用 xgb_ta_pipeline features.CLASSIC_SETS,共 15 欄),
其他全部不變:TW50、訓練 2016-01-01 ~ 2025-12-22、測試 2026-01-01 ~ 09-10、標籤 5 日 ±5%、持有 5 日、成本 0.42%。
每個特徵集(1/2/3 日)各跑「原特徵」與「原特徵 + 四指標」,後段各跑原版 AE+OC-SVM 與有監督 AE+XGB(前 10% 出訊號):
  四大評估指標 Precision / Recall / Accuracy / F1(驗證段 80/20 後段、2026 樣本外)+ 2026 組合報酬(open 口徑)。
用法: python backtest_2026/run_kline_plus_ta.py  →  results/kline_plus_ta.json
"""
import json, os, sys, time, warnings
import numpy as np, pandas as pd, torch
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM
from xgboost import XGBClassifier
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "..", "method_xgb", "src"))
from run_kline_2026 import load_raw, open_to_open_ret, TEST_START, TEST_END, TRAIN_END, OUT    # noqa
from run_kline_sup_2026 import non_overlap, summarize                                           # noqa
from kline.config import HOLD_DAYS, TRADE_COST, RISE_THRESH, FALL_THRESH, OCSVM_NU              # noqa
from kline.features import FEATURE_SETS                                                         # noqa
from kline.data_loader import build_dataset                                                     # noqa
from kline.autoencoder import train_ae                                                          # noqa
from kline.supervised_model import XGB_PARAMS, SIG_FRAC                                         # noqa
from features import CLASSIC_SETS                                                               # noqa
from features.trend import trend_features                                                       # noqa
from features.momentum import momentum_features                                                 # noqa
TA = CLASSIC_SETS["classic4"]


def plus_ta(fn):
    def f(df):
        x = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
        t = {}; t.update(trend_features(x)); t.update(momentum_features(x))
        return pd.concat([fn(df), pd.DataFrame({c: t[c] for c in TA}, index=df.index)], axis=1)
    return f


def prf(actual, pred):
    TP = int((pred & actual).sum()); TN = int((~pred & ~actual).sum()); FP = int((pred & ~actual).sum()); FN = int((~pred & actual).sum())
    P = TP / (TP + FP) if TP + FP else 0.0; R = TP / (TP + FN) if TP + FN else 0.0
    return dict(P=P * 100, R=R * 100, Acc=(TP + TN) / len(actual) * 100, F1=(2 * P * R / (P + R) * 100) if P + R else 0.0,
                sig=pred.mean() * 100, base=actual.mean() * 100)


def fit_stage(A, B, feat):
    """回傳 {模型: {'bull': pred_bool, 'bear': pred_bool}} 對 B 的訊號。"""
    sc = StandardScaler().fit(A[feat].values.astype(np.float32))
    Xa = np.clip(sc.transform(A[feat].values.astype(np.float32)), -5, 5); Xb = np.clip(sc.transform(B[feat].values.astype(np.float32)), -5, 5)
    torch.manual_seed(42); ae = train_ae(Xa, len(feat), lambda s: None); ae.eval()
    with torch.no_grad(): Za, Zb = ae.encode(torch.FloatTensor(Xa)).numpy(), ae.encode(torch.FloatTensor(Xb)).numpy()
    out = {"原版 OC-SVM": {}, "有監督 AE+XGB": {}}
    for k, cond in (("bull", lambda r: r > RISE_THRESH), ("bear", lambda r: r < FALL_THRESH)):
        pa = cond(A.future_ret.values)
        out["原版 OC-SVM"][k] = OneClassSVM(kernel="rbf", nu=OCSVM_NU, gamma="scale").fit(Za[pa]).predict(Zb) == 1
        p = XGBClassifier(**{**XGB_PARAMS, "n_estimators": 200}).fit(Za, pa.astype(int)).predict_proba(Zb)[:, 1]
        out["有監督 AE+XGB"][k] = p >= np.quantile(p, 1 - SIG_FRAC)
    return out


def backtest_2026(te, sig, raw, tickers):
    rows = []
    for tk in tickers:
        m = (te.ticker == tk).values
        if not m.any(): continue
        s = np.zeros(m.sum(), dtype=np.float32); s[sig["bull"][m]] = 1; s[sig["bear"][m] & (s != 1)] = -1
        ex = non_overlap(s); td = te[m]; oo = open_to_open_ret(raw[tk]).reindex(td.index)
        for i in np.where(ex != 0)[0]:
            rows.append({"ticker": tk, "side": int(ex[i]), "ret_close": float(ex[i] * td.future_ret.iloc[i] - TRADE_COST),
                         "ret_open": float(ex[i] * oo.iloc[i] - TRADE_COST) if np.isfinite(oo.iloc[i]) else np.nan})
    t = pd.DataFrame(rows)
    if not len(t): return {"n_buy": 0, "n_sell": 0}
    s = summarize(t, tickers)
    return {"n_buy": s["n_buy"], "n_sell": s["n_sell"], "buy_avg_open": round(float(t[t.side == 1].ret_open.mean()), 3) if s["n_buy"] else None,
            "sell_avg_open": round(float(t[t.side == -1].ret_open.mean()), 3) if s["n_sell"] else None, "portfolio_open": s["open"]["portfolio_ret_pct"]}


def main():
    t0 = time.time(); raw = load_raw(); tickers = list(raw); out = {}
    for name, fn in FEATURE_SETS:
        for tag, f in (("原特徵", fn), ("原特徵+四指標", plus_ta(fn))):
            df = build_dataset(raw, f); feat = [c for c in df.columns if c not in ("future_ret", "ticker")]
            tr = df[(df.index >= "2016-01-01") & (df.index <= "2024-12-31")]
            d = tr.index.unique().sort_values(); split = d[int(len(d) * 0.8)]
            fit, val = tr[tr.index < split], tr[tr.index >= split]
            full = df[(df.index >= "2016-01-01") & (df.index <= TRAIN_END)]; te = df[(df.index >= TEST_START) & (df.index <= TEST_END)]
            key = f"{name}|{tag}"; rec = {"n_feat": len(feat), "features": feat, "metrics": {}, "bt2026": {}}
            print(f"\n===== {key}({len(feat)} 特徵)=====", flush=True)
            for stage, (A, B) in (("驗證段", (fit, val)), ("2026樣本外", (full, te))):
                sig = fit_stage(A, B, feat)
                for model, s in sig.items():
                    for k, lab, cond in (("bull", "看漲", lambda r: r > RISE_THRESH), ("bear", "看跌", lambda r: r < FALL_THRESH)):
                        r = prf(cond(B.future_ret.values), s[k]); rec["metrics"][f"{stage}|{lab}|{model}"] = r
                        print(f"  {stage} {lab} {model:12s} Precision {r['P']:6.2f}%(隨機 {r['base']:5.2f}%) Recall {r['R']:6.2f}% Accuracy {r['Acc']:6.2f}% F1 {r['F1']:6.2f}% 出訊號 {r['sig']:5.1f}%", flush=True)
                    if stage == "2026樣本外":
                        b = backtest_2026(te, s, raw, tickers); rec["bt2026"][model] = b
                        print(f"  2026 回測 {model:12s} 買 {b['n_buy']} 賣 {b['n_sell']} 買每筆 {b.get('buy_avg_open')}% 賣每筆 {b.get('sell_avg_open')}% 組合 {b.get('portfolio_open', 0):+.2f}%", flush=True)
            out[key] = rec
    json.dump(out, open(os.path.join(OUT, "kline_plus_ta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[SAVED] results/kline_plus_ta.json ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
