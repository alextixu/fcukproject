"""族群消融 + SHAP(tw50 h5 cs,x26 切分),補 exp_select_features.py 沒做的兩項。

A. 族群消融(走動式:折 Y ∈ {2023, 2024, 2025},訓練 ≤ Y-2、早停 Y-1、評分 Y;2 seeds)
     基底 full(242 欄)與 selected(43 欄)各做:
       nofamily:X  拿掉整族重訓 → ΔAUC = 基底 − 拿掉後(正 = 這族有貢獻)
       family:X    只用這一族   → 這族單獨能做到多少
     另附標準切分的 2026 測試 AUC 當參考(不拿來做決定)。
B. SHAP(標準切分:訓練 ≤2024、早停 2025;在 2025 驗證集上算,3 seeds 平均)
     mean|SHAP| = 平均影響幅度;dir_rho = 特徵值與 SHAP 值的 Spearman(正 = 值越高越看漲)。
     full 242 欄補上原管線缺的 shap 欄;selected 43 欄另存一份。

輸出 experiments/family_shap_x26-tw50-h5-cs.json、experiments/shap_{full,selected}_x26-tw50-h5-cs.csv
"""
import os, sys, json, time
import numpy as np, pandas as pd
import shap
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "method_xgb", "src"))
from common import paths as P
from split import time_split
from train_xgb import fit_xgb, predict_p

TAG = "x26-tw50-h5-cs"
SCORE_YEARS = (2023, 2024, 2025)
SEEDS = (42, 43)

x = json.load(open(os.path.join(P.XGB_EXP, f"{TAG}.json"), encoding="utf-8"))
sel = json.load(open(os.path.join(P.XGB_EXP, f"select_{TAG}.json"), encoding="utf-8"))
cfg, ycol, H = x["config"], x["label"], x["config"]["horizon"]
FULL, SELECTED = x["results"]["full"]["features"], sel["final"]
fam = pd.read_csv(os.path.join(P.XGB_EXP, f"{TAG}_importance.csv"), index_col=0)["family"].to_dict()
group_of = {f: i for i, g in enumerate(sel["final_groups"]) for f in g}
panel = pd.read_parquet(os.path.join(P.FEATURES, f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}.parquet"),
                        columns=FULL + [ycol])
dates = panel.index.get_level_values("date")
FOLDS = [time_split(panel[dates <= pd.Timestamp(f"{y}-12-31")], f"{y-2}-12-31", f"{y-1}-12-31", H, ycol) for y in SCORE_YEARS]
TR, VA, TE = time_split(panel, cfg["train_end"], cfg["val_end"], H, ycol)
Y = lambda df: df[ycol].values.astype(int)


def wf_auc(feats):
    return [float(np.mean([roc_auc_score(Y(sc), predict_p(fit_xgb(tr[feats], Y(tr), es[feats], Y(es), s, cfg["xgb"]), sc[feats]))
                           for s in SEEDS])) for tr, es, sc in FOLDS]


def test_auc(feats):
    ps = [predict_p(fit_xgb(TR[feats], Y(TR), VA[feats], Y(VA), s, cfg["xgb"]), TE[feats]) for s in cfg["seeds"]]
    return float(roc_auc_score(Y(TE), np.mean(ps, axis=0)))


t0 = time.time()
ablation = {}
for base_name, base in (("full", FULL), ("selected", SELECTED)):
    b_wf, b_te = wf_auc(base), test_auc(base)
    print(f"[{base_name}] {len(base)} 欄  走動 AUC {np.mean(b_wf):.4f} {[round(a,4) for a in b_wf]}  測試 AUC {b_te:.4f}", flush=True)
    rows = []
    for f in sorted({fam[c] for c in base}, key=lambda k: -sum(fam[c] == k for c in base)):
        inn, out = [c for c in base if fam[c] == f], [c for c in base if fam[c] != f]
        o_wf, i_wf = wf_auc(out), wf_auc(inn)
        d = [b - o for b, o in zip(b_wf, o_wf)]
        rows.append({"family": f, "n": len(inn), "drop_wf": o_wf, "delta_mean": float(np.mean(d)), "delta_folds": d,
                     "n_pos": int(sum(v > 0 for v in d)), "drop_test": test_auc(out), "only_wf": i_wf, "only_wf_mean": float(np.mean(i_wf)),
                     "only_test": test_auc(inn)})
        r = rows[-1]
        print(f"  {f:14s} {len(inn):3d} 欄 | 拿掉 ΔAUC {r['delta_mean']:+.4f} {[round(v,4) for v in d]} 測試 {r['drop_test']:.4f}"
              f" | 只用 走動 {r['only_wf_mean']:.4f} 測試 {r['only_test']:.4f}  ({time.time()-t0:.0f}s)", flush=True)
    ablation[base_name] = {"n_feat": len(base), "base_wf": b_wf, "base_test": b_te, "families": rows}

shap_out = {}
for name, feats in (("full", FULL), ("selected", SELECTED)):
    absm, rho = [], []
    for s in cfg["seeds"]:
        m = fit_xgb(TR[feats], Y(TR), VA[feats], Y(VA), s, cfg["xgb"])
        v = shap.TreeExplainer(m).shap_values(VA[feats])
        v = v[1] if isinstance(v, list) else v
        absm.append(np.abs(v).mean(axis=0))
        Xv = VA[feats].values
        rho.append([spearmanr(Xv[:, j], v[:, j], nan_policy="omit")[0] if np.ptp(v[:, j]) > 0 else np.nan for j in range(len(feats))])
    df = pd.DataFrame({"shap_mean": np.mean(absm, axis=0), "dir_rho": np.nanmean(rho, axis=0)}, index=feats)
    df["shap_share"] = df["shap_mean"] / df["shap_mean"].sum()
    df["family"] = [fam[f] for f in feats]
    if name == "selected":
        df["group"] = [group_of[f] for f in feats]
    df = df.sort_values("shap_mean", ascending=False)
    df.to_csv(os.path.join(P.XGB_EXP, f"shap_{name}_{TAG}.csv"))
    shap_out[name] = {"family_share": df.groupby("family")["shap_share"].sum().sort_values(ascending=False).round(4).to_dict()}
    print(f"\n[SHAP {name}] 前 15 名:\n{df.head(15).round(4).to_string()}\n族群佔比:{shap_out[name]['family_share']}", flush=True)
    if name == "selected":
        g = df.groupby("group")["shap_share"].sum().sort_values(ascending=False)
        shap_out[name]["group_share"] = {"+".join(sel["final_groups"][i][:2]) + (f"(+{len(sel['final_groups'][i])-2})" if len(sel["final_groups"][i]) > 2 else ""): round(float(v), 4) for i, v in g.items()}
        print(f"群佔比:{shap_out[name]['group_share']}")

json.dump({"tag": TAG, "score_years": SCORE_YEARS, "seeds": SEEDS, "ablation": ablation, "shap": shap_out, "elapsed_s": round(time.time() - t0)},
          open(os.path.join(P.XGB_EXP, f"family_shap_{TAG}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[DONE] {time.time()-t0:.0f}s")
