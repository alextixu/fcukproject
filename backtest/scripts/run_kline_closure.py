"""K 線 v1 收尾:門檻改用驗證段分位數;AE+XGB vs 原始特徵直接 XGB;分年 P/R/Acc/F1。"""
import sys, os, json, numpy as np, pandas as pd, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_kline_plus_ta import load_raw, build_dataset, FEATURE_SETS, plus_ta, prf, RISE_THRESH, FALL_THRESH
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from kline.autoencoder import train_ae
from kline.supervised_model import XGB_PARAMS, SIG_FRAC
TRAIN_END, TEST_START, TEST_END = "2024-12-23", "2025-01-01", "2026-09-10"
def fit_models(fit, val, te, feat):
    sc = StandardScaler().fit(fit[feat].values.astype(np.float32))
    X = {k: np.clip(sc.transform(v[feat].values.astype(np.float32)), -5, 5) for k, v in (("fit", fit), ("val", val), ("te", te))}
    torch.manual_seed(42); ae = train_ae(X["fit"], len(feat), lambda s: None); ae.eval()
    with torch.no_grad(): Z = {k: ae.encode(torch.FloatTensor(v)).numpy() for k, v in X.items()}
    out = {}
    for space, D in (("AE+XGB", Z), ("原始特徵XGB", X)):
        out[space] = {}
        for k, cond in (("bull", lambda r: r > RISE_THRESH), ("bear", lambda r: r < FALL_THRESH)):
            yf, yv = cond(fit.future_ret.values).astype(int), cond(val.future_ret.values).astype(int)
            clf = XGBClassifier(**{**XGB_PARAMS, "n_estimators": 600}, eval_metric="logloss", early_stopping_rounds=50).fit(D["fit"], yf, eval_set=[(D["val"], yv)], verbose=False)
            thr = np.quantile(clf.predict_proba(D["val"])[:, 1], 1 - SIG_FRAC)        # 門檻用驗證段
            out[space][k] = clf.predict_proba(D["te"])[:, 1] >= thr
    return out
raw = load_raw(); res = {}
for name, fn in FEATURE_SETS[:1]:
    for tag, f in (("原特徵", fn), ("原特徵+四指標", plus_ta(fn))):
        df = build_dataset(raw, f); feat = [c for c in df.columns if c not in ("future_ret", "ticker")]
        tr = df[(df.index >= "2016-01-01") & (df.index <= TRAIN_END)]; te = df[(df.index >= TEST_START) & (df.index <= TEST_END)]
        d = tr.index.unique().sort_values(); split = d[int(len(d) * 0.8)]
        fit, val = tr[tr.index < split], tr[tr.index >= split]
        sig = fit_models(fit, val, te, feat); yr = te.index.year; key = f"{name}|{tag}"; res[key] = {}
        for space, s in sig.items():
            for k, lab, cond in (("bull", "看漲", lambda r: r > RISE_THRESH), ("bear", "看跌", lambda r: r < FALL_THRESH)):
                act = cond(te.future_ret.values)
                for y in (2025, 2026):
                    m = yr == y; r = prf(act[m], s[k][m]); res[key][f"{y}|{lab}|{space}"] = r
                    print(f"{key} {y} {lab} {space:10s} P {r['P']:6.2f} R {r['R']:6.2f} Acc {r['Acc']:6.2f} F1 {r['F1']:6.2f} base {r['base']:5.2f} sig {r['sig']:5.1f}", flush=True)
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "kline_v1_closure_2025_2026.json"), "w"), ensure_ascii=False, indent=1); print("[DONE]")
