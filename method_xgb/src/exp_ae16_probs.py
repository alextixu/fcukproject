"""2026-09-22:AE 38→16 + XGBoost,存下測試年每檔每天的機率(看信心度用)。設定與 exp_ae_shortlist_r3.py 相同。"""
import os, sys, time
import numpy as np, pandas as pd
from joblib import Parallel, delayed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exp_ae_shortlist_r3 as M

if __name__ == "__main__":
    T0 = time.time(); arch = "ae_16"
    ae = Parallel(n_jobs=10)(delayed(M.train_ae)(arch, Y, s) for Y in M.YEARS for s in M.SEEDS)
    LAT = {k: v for k, v, _ in ae}
    xr = Parallel(n_jobs=10)(delayed(M.fit_xgb)(LAT[(arch, Y, s)]["tr"], LAT[(arch, Y, s)]["va"], LAT[(arch, Y, s)]["te"], Y, s)
                             for Y in M.YEARS for s in M.SEEDS)
    PR = dict(zip([(Y, s) for Y in M.YEARS for s in M.SEEDS], xr)); parts = []
    for Y in M.YEARS:
        te = M.FOLDS[Y][2]
        parts.append(pd.DataFrame({"prob": np.mean([PR[(Y, s)][0] for s in M.SEEDS], axis=0), "y": M.y[te], "r": M.r.values[te]}, index=M.panel.index[te]))
    out = pd.concat(parts); out.to_parquet(os.path.join(M.P.XGB_EXP, "probs_ae16_test.parquet"))
    print("[DONE]", round(time.time() - T0), "s", len(out), flush=True)
