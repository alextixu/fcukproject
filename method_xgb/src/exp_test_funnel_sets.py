"""漏斗 79 欄 / 36 欄的 2026 測試(tw50 h5 cs,x26 切分:訓練 ≤2024、早停 2025、測試 2026),與 242 / 95 / 43 欄對照。

  每組 10 seeds:集成機率報四大指標(固定 0.5 門檻 + 當日機率中位數門檻),並報單一 seed 的 AUC / Acc 平均 ± 標準差,
  用來判斷特徵集之間的差距是否大於重訓雜訊。

輸出 experiments/test_funnel_sets_x26-tw50-h5-cs.json
"""
import os, sys, json, time
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "method_xgb", "src"))
from common import paths as P
from split import time_split
from train_xgb import fit_xgb, predict_p
from evaluate import clf_metrics, clf_metrics_csmed

TAG = "x26-tw50-h5-cs"
SEEDS = tuple(range(42, 52))

x = json.load(open(os.path.join(P.XGB_EXP, f"{TAG}.json"), encoding="utf-8"))
cfg, ycol, H = x["config"], x["label"], x["config"]["horizon"]
FULL = x["results"]["full"]["features"]
fun = json.load(open(os.path.join(P.XGB_EXP, f"select_funnel_{TAG}.json"), encoding="utf-8"))
sets = {"full_242": FULL, "permpos_95": x["results"]["full_permpos"]["features"],
        "cluster_43": json.load(open(os.path.join(P.XGB_EXP, f"select_{TAG}.json"), encoding="utf-8"))["final"],
        "funnel_79": fun["final"], "funnel_36": next(p["features"] for p in fun["path"] if p["n_feat"] == 36)}
panel = pd.read_parquet(os.path.join(P.FEATURES, f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}.parquet"),
                        columns=FULL + [ycol])
tr, va, te = time_split(panel, cfg["train_end"], cfg["val_end"], H, ycol)
yte = te[ycol].values.astype(int); dte = te.index.get_level_values("date")
print(f"[DATA] 訓練 {len(tr)} / 早停 {len(va)} / 測試 {len(te)};測試正例比例(隨機基準){yte.mean()*100:.2f}%")

t0, out = time.time(), {"tag": TAG, "seeds": SEEDS, "pos_ratio": float(yte.mean()), "sets": {}}
for name, fs in sets.items():
    ps = [predict_p(fit_xgb(tr[fs], tr[ycol].values.astype(int), va[fs], va[ycol].values.astype(int), s, cfg["xgb"]), te[fs]) for s in SEEDS]
    ens = np.mean(ps, axis=0)
    m5, mc = clf_metrics(yte, ens), clf_metrics_csmed(yte, ens, dte)
    auc_s = [roc_auc_score(yte, p) for p in ps]; acc_s = [clf_metrics_csmed(yte, p, dte)["acc"] for p in ps]
    out["sets"][name] = {"n_feat": len(fs), "features": fs, "thr05": m5, "csmed": mc, "auc_seeds": auc_s, "acc_csmed_seeds": acc_s}
    print(f"[{name:11s}] {len(fs):3d} 欄 | 0.5 門檻 Acc {m5['acc']*100:.2f} P {m5['pre_1']*100:.2f} R {m5['rec_1']*100:.2f} F1m {m5['f1_macro']*100:.2f}"
          f" | 中位數門檻 Acc {mc['acc']*100:.2f} P {mc['pre_1']*100:.2f} R {mc['rec_1']*100:.2f} F1m {mc['f1_macro']*100:.2f}"
          f" | AUC 集成 {m5['auc']:.4f} 單 seed {np.mean(auc_s):.4f}±{np.std(auc_s, ddof=1):.4f}"
          f" | 前5% Acc {m5['acc_cov5']*100:.1f}  ({time.time()-t0:.0f}s)", flush=True)
out["elapsed_s"] = round(time.time() - t0)
json.dump(out, open(os.path.join(P.XGB_EXP, f"test_funnel_sets_{TAG}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[DONE] {time.time()-t0:.0f}s")
