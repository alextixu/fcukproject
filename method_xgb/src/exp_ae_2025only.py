"""2026-09-22:只看 2025 測試年(訓練 2016~2023、驗證 2024、測試 2025;唯一沒被拿來挑 38 欄的年份)。
各自編碼器結構 + 原始 38 欄的四個指標,並存下每檔每天的機率。設定與 exp_ae_shortlist_r3.py 相同。"""
import os, sys, json, time
import numpy as np, pandas as pd
from joblib import Parallel, delayed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exp_ae_shortlist_r3 as M

Y = 2025
ARCH = {"ae_8": [8], "ae_12": [12], "ae_16": [16], "ae_24": [24], "ae_24_12": [24, 12], "ae_20_8": [20, 8]}


def train_ae(arch, seed):
    M.ARCH.update(ARCH); return M.train_ae(arch, Y, seed)


def four(prob, idx):
    P = pd.Series(prob, index=M.panel.index[idx]).unstack("ticker"); Yw = pd.Series(M.y[idx], index=M.panel.index[idx]).unstack("ticker")
    pred = P.gt(P.median(axis=1), axis=0); ok = P.notna(); yv = Yw == 1
    tp, fp, fn, tn = [int(v.sum().sum()) for v in (pred & yv & ok, pred & ~yv & ok, ~pred & yv & ok, ~pred & ~yv & ok)]
    pr, rc = tp / (tp + fp), tp / (tp + fn)
    return {"acc": (tp + tn) / (tp + fp + fn + tn), "precision": pr, "recall": rc, "f1": 2 * pr * rc / (pr + rc), "n_days": int(P.shape[0]), "n_rows": int(ok.sum().sum())}


if __name__ == "__main__":
    T0 = time.time(); tr, va, te = M.FOLDS[Y]
    ae = Parallel(n_jobs=10)(delayed(train_ae)(a, s) for a in ARCH for s in M.SEEDS)
    LAT = {(k[0], k[2]): v for k, v, _ in ae}
    jobs = [("raw38", s) for s in M.SEEDS] + [(a, s) for a in ARCH for s in M.SEEDS]
    feats = lambda a, s: (M.RAW[tr], M.RAW[va], M.RAW[te]) if a == "raw38" else (LAT[(a, s)]["tr"], LAT[(a, s)]["va"], LAT[(a, s)]["te"])
    xr = Parallel(n_jobs=10)(delayed(M.fit_xgb)(*feats(a, s), Y, s) for a, s in jobs); PR = dict(zip(jobs, xr))
    out, probs = {}, {}
    for a in ["raw38"] + list(ARCH):
        p = np.mean([PR[(a, s)][0] for s in M.SEEDS], axis=0); probs[a] = p; out[a] = four(p, te)
    pd.DataFrame({**{f"prob_{a}": v for a, v in probs.items()}, "y": M.y[te], "r": M.r.values[te]}, index=M.panel.index[te]).to_parquet(os.path.join(M.P.XGB_EXP, "probs_2025_test.parquet"))
    json.dump({"test_year": Y, "train": "2016-01 ~ 2023-12(去尾 6 日)", "valid": "2024(去尾 6 日)", "arms": out, "elapsed_s": round(time.time() - T0)},
              open(os.path.join(M.P.XGB_EXP, "ae_2025only_summary.json"), "w"), ensure_ascii=False, indent=1)
    for a, v in out.items(): print(a, *[f"{v[m]*100:.2f}%" for m in ("acc", "precision", "recall", "f1")], v["n_days"], v["n_rows"])
    print("[DONE]", round(time.time() - T0), "s", flush=True)
