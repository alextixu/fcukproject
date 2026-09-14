"""K 線 v1(AE+OC-SVM / AE+XGB):訓練 2016 ~ 2024-12-23(purge 5 日),測試 2025-01-01 ~ 2026-09-10,分年報 P/R/Acc/F1。輸出 results/kline_v1_yearly_2025_2026.json"""
import sys, os, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_kline_plus_ta import load_raw, build_dataset, FEATURE_SETS, plus_ta, fit_stage, prf, RISE_THRESH, FALL_THRESH
TRAIN_END, TEST_START, TEST_END = "2024-12-23", "2025-01-01", "2026-09-10"   # purge 5 交易日
raw = load_raw(); out = {}
for name, fn in FEATURE_SETS:
    for tag, f in (("原特徵", fn), ("原特徵+四指標", plus_ta(fn))):
        df = build_dataset(raw, f); feat = [c for c in df.columns if c not in ("future_ret", "ticker")]
        full = df[(df.index >= "2016-01-01") & (df.index <= TRAIN_END)]; te = df[(df.index >= TEST_START) & (df.index <= TEST_END)]
        sig = fit_stage(full, te, feat); yr = te.index.year
        key = f"{name}|{tag}"; out[key] = {"n_train": len(full), "n_test": len(te)}
        for model, s in sig.items():
            for k, lab, cond in (("bull", "看漲", lambda r: r > RISE_THRESH), ("bear", "看跌", lambda r: r < FALL_THRESH)):
                act = cond(te.future_ret.values)
                for y in (2025, 2026):
                    m = yr == y; r = prf(act[m], s[k][m]); out[key][f"{y}|{lab}|{model}"] = r
                    print(f"{key} {y} {lab} {model:10s} P {r['P']:6.2f} R {r['R']:6.2f} Acc {r['Acc']:6.2f} F1 {r['F1']:6.2f} base {r['base']:5.2f} sig {r['sig']:5.1f}", flush=True)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "kline_v1_yearly_2025_2026.json"), "w"), ensure_ascii=False, indent=1)
print("[DONE]")
