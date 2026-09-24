"""XGB 超參數網格搜尋(以 val AUC 選,test 不參與)。輸出 config/xgb_tuned_<tag>.json,給 run_pipeline --xgb-json 用。

用法: python src/tune_xgb.py --pool tw50 --horizon 1 --label bin --feature-set full --tag tw50-h1
"""
import argparse
import itertools
import json
import os
import sys
import time

import numpy as np
from sklearn.metrics import roc_auc_score, accuracy_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_pipeline as rp
from split import time_split, filter_features, apply_deadzone
from labels import label_col
from train_xgb import fit_xgb

GRID = {
    "max_depth": [3, 5, 8],
    "learning_rate": [0.03, 0.1],
    "min_child_weight": [10, 100],
    "colsample_bytree": [0.3, 0.8],
    "subsample": [0.8],
    "reg_lambda": [1.0, 10.0],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="tw50"); ap.add_argument("--horizon", type=int, default=1)
    ap.add_argument("--label", default="bin"); ap.add_argument("--feature-set", default="full")
    ap.add_argument("--chip", action="store_true"); ap.add_argument("--deadzone", type=float, default=0.0)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(rp.CFG, "default.json"), encoding="utf-8"))
    cfg.update(pool=a.pool, horizon=a.horizon, label=a.label, feature_sets=[a.feature_set])
    if a.chip:
        cfg["chip"] = True
    panel, fam = rp.get_panel(cfg)
    ycol = label_col(a.label, a.horizon)
    tr, va, te = time_split(panel, cfg["train_end"], cfg["val_end"], a.horizon, ycol)
    del panel
    if a.deadzone > 0:
        tr, va, te = apply_deadzone((tr, va, te), a.horizon, a.deadzone)
    feats, _ = filter_features(tr, rp.feature_list(a.feature_set, fam), cfg["max_nan"])
    Xtr, ytr = tr[feats], tr[ycol].values.astype(int)
    Xva, yva = va[feats], va[ycol].values.astype(int)
    print(f"[TUNE] {a.tag}: {len(feats)} 欄, train {len(tr)} val {len(va)}", flush=True)

    keys = list(GRID)
    rows = []
    t0 = time.time()
    for combo in itertools.product(*GRID.values()):
        params = dict(zip(keys, combo))
        m = fit_xgb(Xtr, ytr, Xva, yva, 42, params)
        p = m.predict_proba(Xva)[:, 1]
        auc = roc_auc_score(yva, p)
        acc = accuracy_score(yva, (p >= 0.5).astype(int))
        rows.append({**params, "val_auc": round(float(auc), 4), "val_acc": round(float(acc), 4),
                     "best_iter": int(m.best_iteration)})
        print(f"  {params} → val AUC {auc:.4f} acc {acc:.4f} iters {m.best_iteration} ({time.time() - t0:.0f}s)", flush=True)
    rows.sort(key=lambda r: -r["val_auc"])
    best = {k: rows[0][k] for k in keys}
    out = os.path.join(rp.CFG, f"xgb_tuned_{a.tag}.json")
    json.dump(best, open(out, "w", encoding="utf-8"), indent=1)
    json.dump(rows, open(os.path.join(rp.EXP, f"tune_{a.tag}.json"), "w", encoding="utf-8"), indent=1)
    print(f"\n[BEST] {best}  val AUC {rows[0]['val_auc']}  (預設約:depth5 lr0.03 mcw50 col0.5 λ5)")
    print(f"[SAVED] {out}")


if __name__ == "__main__":
    main()
