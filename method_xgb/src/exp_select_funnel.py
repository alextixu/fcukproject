"""漏斗式特徵篩選(tw50 h5 cs,x26 切分):與 exp_select_features.py(相關分群 + 群組排列重要性)對照。

  1. 靜態過濾:零變異數剔除;|Spearman| ≥ 0.95 的成對指標只留「與標籤單變量相關較高」的那一欄。
  2. 時間序列交叉驗證:折 Y ∈ {2023, 2024, 2025}:訓練 ≤ Y-2、早停 Y-1、評分 Y(與 exp_select_features 同折)。
     樹模型對單調轉換不敏感,不做 Z-score;分群/相關只用訓練段算,不碰評分年。
  3. 動態評分:colsample_bytree = 0.7 的 XGBoost,取 total_gain 排名;SHAP(pred_contribs)看方向,
     三折方向互相矛盾(|corr(x, shap)| 每折 ≥ 0.2 但正負號不一致)的欄位剔除。
  4. 遞迴淘汰:每輪砍 gain 最後 5%(至少 1 欄)重訓,記錄走動 AUC,直到剩 5 欄。
     採用:走動 AUC 在最佳值 TOL 以內、欄數最少的那一輪。
  5. 2026 測試集只在最後看一次,對照 full / permpos / 分群篩選 43 欄。

輸出 experiments/select_funnel_x26-tw50-h5-cs.json
"""
import os, sys, json, time
import numpy as np, pandas as pd
import xgboost as xgb
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
CORR_THR = 0.95
COLSAMPLE = 0.7
DROP_FRAC = 0.05
MIN_FEAT = 5
DIR_MIN = 0.2
TOL = 0.001

x = json.load(open(os.path.join(P.XGB_EXP, f"{TAG}.json"), encoding="utf-8"))
cfg, ycol, H = x["config"], x["label"], x["config"]["horizon"]
FULL = x["results"]["full"]["features"]
XGB_P = dict(cfg["xgb"], colsample_bytree=COLSAMPLE)
panel = pd.read_parquet(os.path.join(P.FEATURES, f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}.parquet"),
                        columns=FULL + [ycol])
dates = panel.index.get_level_values("date")


def make_folds():
    folds = []
    for y in SCORE_YEARS:
        sub = panel[dates <= pd.Timestamp(f"{y}-12-31")]
        folds.append((y,) + time_split(sub, f"{y-2}-12-31", f"{y-1}-12-31", H, ycol))
    return folds


def static_filter(feats, Xtr):
    """零變異數 + 去共線性。回傳 (保留欄, 零變異欄, {被剔欄: 取代它的欄})。"""
    Xs = Xtr[feats + [ycol]].sample(min(30000, len(Xtr)), random_state=0)
    zero = [f for f in feats if Xs[f].nunique(dropna=True) <= 1 or Xs[f].std() < 1e-12]
    cand = [f for f in feats if f not in zero]
    rk = Xs[cand + [ycol]].rank()
    rel = rk[cand].corrwith(rk[ycol]).abs().fillna(0)
    c = rk[cand].corr().abs().fillna(0)
    kept, dropped = [], {}
    for f in rel.sort_values(ascending=False).index:
        hit = [k for k in kept if c.at[f, k] >= CORR_THR]
        if hit:
            dropped[f] = hit[0]
        else:
            kept.append(f)
    return kept, zero, dropped


def wf_eval(feats, shap_dir=False):
    """走動式:回傳各折 AUC(seed 平均)、單欄 total_gain(折 × seed 平均)、各折 SHAP 方向。"""
    aucs, gains, dirs = [], [], []
    for y, tr, es, sc in FOLDS:
        ysc = sc[ycol].values.astype(int)
        a_seed, d_seed = [], []
        for seed in SEEDS:
            m = fit_xgb(tr[feats], tr[ycol].values.astype(int), es[feats], es[ycol].values.astype(int), seed, XGB_P)
            a_seed.append(roc_auc_score(ysc, predict_p(m, sc[feats])))
            g = m.get_booster().get_score(importance_type="total_gain")
            gains.append(pd.Series({f: g.get(f, 0.0) for f in feats}))
            if shap_dir:
                sv = m.get_booster().predict(xgb.DMatrix(sc[feats]), pred_contribs=True)[:, :-1]
                X = sc[feats].rank().values
                d_seed.append([np.corrcoef(X[:, j], sv[:, j])[0, 1] if sv[:, j].std() > 0 else 0.0 for j in range(len(feats))])
        aucs.append(float(np.mean(a_seed)))
        if shap_dir:
            dirs.append(np.nan_to_num(np.mean(d_seed, axis=0)))
    return aucs, pd.concat(gains, axis=1).mean(axis=1), (pd.DataFrame(dirs, columns=feats, index=SCORE_YEARS) if shap_dir else None)


t0 = time.time()
FOLDS = make_folds()
for y, tr, es, sc in FOLDS:
    print(f"[FOLD {y}] 訓練 {len(tr)} / 早停 {len(es)} / 評分 {len(sc)}")

kept, zero, dropped = static_filter(FULL, FOLDS[-1][1])
print(f"[STATIC] {len(FULL)} 欄 → 零變異 {len(zero)} 欄、共線(|ρ| ≥ {CORR_THR}) {len(dropped)} 欄 → 剩 {len(kept)} 欄")

auc_full, _, _ = wf_eval(FULL)
auc_static, gain, dirs = wf_eval(kept, shap_dir=True)
strong = dirs.abs().min(axis=0) >= DIR_MIN
flip = [f for f in kept if strong[f] and abs(np.sign(dirs[f]).sum()) < len(SCORE_YEARS)]
print(f"[SCORE] 走動 AUC:full {len(FULL)} 欄 {np.mean(auc_full):.4f} / 靜態過濾後 {len(kept)} 欄 {np.mean(auc_static):.4f}")
print(f"[SHAP] 方向三折矛盾 {len(flip)} 欄:{flip}")
feats = [f for f in kept if f not in flip]

path = []
while True:
    aucs, gain, _ = wf_eval(feats)
    path.append({"n_feat": len(feats), "wf_auc": aucs, "wf_auc_mean": float(np.mean(aucs)), "features": list(feats)})
    print(f"[RFE] {len(feats):3d} 欄  走動 AUC {np.mean(aucs):.4f} {[round(a, 4) for a in aucs]}  ({time.time()-t0:.0f}s)", flush=True)
    if len(feats) <= MIN_FEAT:
        break
    n_drop = max(1, int(len(feats) * DROP_FRAC))
    order = gain.sort_values(ascending=False).index.tolist()
    feats = order[:max(MIN_FEAT, len(feats) - n_drop)]

best = max(p["wf_auc_mean"] for p in path)
chosen = min((p for p in path if p["wf_auc_mean"] >= best - TOL), key=lambda p: p["n_feat"])
FINAL = chosen["features"]
print(f"[CHOSEN] {chosen['n_feat']} 欄,走動 AUC {chosen['wf_auc_mean']:.4f}(最佳 {best:.4f})")
print(f"         {FINAL}")

tr, va, te = time_split(panel, cfg["train_end"], cfg["val_end"], H, ycol)
yte = te[ycol].values.astype(int)
sel_path = os.path.join(P.XGB_EXP, f"select_{TAG}.json")
sets = {"full": FULL, "full_permpos": x["results"]["full_permpos"]["features"], "static_only": kept, "funnel": FINAL}
if os.path.exists(sel_path):
    sets["cluster_selected"] = json.load(open(sel_path, encoding="utf-8"))["final"]
test = {}
for name, fs in sets.items():
    ps = [predict_p(fit_xgb(tr[fs], tr[ycol].values.astype(int), va[fs], va[ycol].values.astype(int), s, cfg["xgb"]), te[fs]) for s in cfg["seeds"]]
    m = clf_metrics(yte, np.mean(ps, axis=0)); m["n_feat"] = len(fs)
    m["auc_seed_std"] = float(np.std([roc_auc_score(yte, p) for p in ps], ddof=1))
    test[name] = m
    print(f"  [TEST {name:18s}] {len(fs):3d} 欄  Acc {m['acc']*100:.2f}  P {m['pre_1']*100:.2f}  R {m['rec_1']*100:.2f}  F1m {m['f1_macro']*100:.2f}  "
          f"AUC {m['auc']:.4f}  前5% Acc {m['acc_cov5']*100:.1f}", flush=True)

json.dump({"tag": TAG, "score_years": SCORE_YEARS, "seeds": SEEDS, "corr_thr": CORR_THR, "colsample_bytree": COLSAMPLE,
           "zero_var": zero, "collinear_dropped": dropped, "static_kept": kept, "wf_auc_full": auc_full, "wf_auc_static": auc_static,
           "shap_dir": dirs.round(3).to_dict(), "shap_flip": flip, "path": path, "final": FINAL, "wf_auc_final": chosen["wf_auc"],
           "test": test, "elapsed_s": round(time.time() - t0)},
          open(os.path.join(P.XGB_EXP, f"select_funnel_{TAG}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[DONE] {time.time()-t0:.0f}s")
