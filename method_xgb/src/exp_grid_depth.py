"""XGBoost 深度 × 學習率小網格(tw50 h5 cs,x26 切分,A 系統現用的 full_permpos 95 欄)。

  走動式:折 Y ∈ {2023, 2024, 2025}:訓練 ≤ Y-2、早停 Y-1、評分 Y(與 exp_select_features 同折),2 seeds。
  選參數只看走動 AUC;2026 測試集(標準切分、3 seeds 集成)最後列出供對照,不拿來選。

輸出 experiments/grid_depth_x26-tw50-h5-cs.json
"""
import os, sys, json, time
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "method_xgb", "src"))
from common import paths as P
from split import time_split
from train_xgb import fit_xgb, predict_p
from evaluate import clf_metrics

TAG = "x26-tw50-h5-cs"
SCORE_YEARS = (2023, 2024, 2025)
SEEDS = (42, 43)
DEPTHS = (3, 5, 7)
LRS = (0.01, 0.03)

x = json.load(open(os.path.join(P.XGB_EXP, f"{TAG}.json"), encoding="utf-8"))
cfg, ycol, H = x["config"], x["label"], x["config"]["horizon"]
FEATS = x["results"]["full_permpos"]["features"]
panel = pd.read_parquet(os.path.join(P.FEATURES, f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}.parquet"),
                        columns=FEATS + [ycol])
dates = panel.index.get_level_values("date")

FOLDS = []
for y in SCORE_YEARS:
    sub = panel[dates <= pd.Timestamp(f"{y}-12-31")]
    FOLDS.append((y,) + time_split(sub, f"{y-2}-12-31", f"{y-1}-12-31", H, ycol))
tr_s, va_s, te_s = time_split(panel, cfg["train_end"], cfg["val_end"], H, ycol)
yte = te_s[ycol].values.astype(int)

t0 = time.time()
rows = []
for d in DEPTHS:
    for lr in LRS:
        prm = dict(cfg["xgb"], max_depth=d, learning_rate=lr)
        aucs, seed_sd, iters = [], [], []
        for y, tr, es, sc in FOLDS:
            ysc = sc[ycol].values.astype(int); a = []
            for seed in SEEDS:
                m = fit_xgb(tr[FEATS], tr[ycol].values.astype(int), es[FEATS], es[ycol].values.astype(int), seed, prm)
                a.append(roc_auc_score(ysc, predict_p(m, sc[FEATS]))); iters.append(int(m.best_iteration))
            aucs.append(float(np.mean(a))); seed_sd.append(float(np.std(a, ddof=1)))
        ms = [fit_xgb(tr_s[FEATS], tr_s[ycol].values.astype(int), va_s[FEATS], va_s[ycol].values.astype(int), s, prm) for s in cfg["seeds"]]
        test = clf_metrics(yte, np.mean([predict_p(m, te_s[FEATS]) for m in ms], axis=0))
        rows.append({"max_depth": d, "learning_rate": lr, "wf_auc": aucs, "wf_auc_mean": float(np.mean(aucs)), "wf_seed_sd": float(np.mean(seed_sd)),
                     "wf_best_iter": iters, "test_best_iter": [int(m.best_iteration) for m in ms], "test": test})
        print(f"[depth {d} lr {lr}] 走動 AUC {np.mean(aucs):.4f} {[round(v, 4) for v in aucs]}  棵數 {int(np.median(iters))}  |  "
              f"2026 Acc {test['acc']*100:.2f}  P {test['pre_1']*100:.2f}  R {test['rec_1']*100:.2f}  F1m {test['f1_macro']*100:.2f}  AUC {test['auc']:.4f}  "
              f"({time.time()-t0:.0f}s)", flush=True)

json.dump({"tag": TAG, "features": "full_permpos", "n_feat": len(FEATS), "score_years": SCORE_YEARS, "seeds": SEEDS, "grid": rows,
           "elapsed_s": round(time.time() - t0)},
          open(os.path.join(P.XGB_EXP, f"grid_depth_{TAG}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[DONE] {time.time()-t0:.0f}s")
