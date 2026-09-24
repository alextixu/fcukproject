"""特徵篩選(tw50 h5 cs,x26 切分):確定哪些特徵有用 → 保留,其餘剔除。

單欄排列重要性會低估互相相關的指標(打亂一個,其他的補上),所以改成:
  1. 相關分群:|Spearman| ≥ 0.7 的欄位併成一群,整群一起打亂。
  2. 走動式評分(篩選全程不碰 2026 測試集):
       折 Y ∈ {2023, 2024, 2025}:訓練 ≤ Y-2、早停 Y-1、評分 Y。
     早停與評分用不同年份,評分年的 AUC 不會被早停偷看。
  3. 逐輪剔除:群的「打亂後 AUC 下降」三折平均 ≤ 0,或只在不到 2 折為正 → 剔除;重訓,直到沒有群被剔。
  4. 群內只留代表欄(單欄 gain 最高者),若走動 AUC 沒掉就採用。
  5. 逐群拿掉重訓(leave-one-group-out),確認留下來的每一群都真的有貢獻。
  6. 最後才用標準切分(訓練 ≤2024、早停 2025、測試 2026)對照 full / top20 / permpos。

輸出 experiments/select_x26-tw50-h5-cs.json
"""
import os, sys, json, time
import numpy as np, pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
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
CORR_THR = 0.7
N_REPEATS = 3
TOL = 0.001

x = json.load(open(os.path.join(P.XGB_EXP, f"{TAG}.json"), encoding="utf-8"))
cfg, ycol, H = x["config"], x["label"], x["config"]["horizon"]
FULL = x["results"]["full"]["features"]
fam = pd.read_csv(os.path.join(P.XGB_EXP, f"{TAG}_importance.csv"), index_col=0)["family"].to_dict()
panel = pd.read_parquet(os.path.join(P.FEATURES, f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}.parquet"),
                        columns=FULL + [ycol])
dates = panel.index.get_level_values("date")


def make_folds():
    folds = []
    for y in SCORE_YEARS:
        sub = panel[dates <= pd.Timestamp(f"{y}-12-31")]
        folds.append((y,) + time_split(sub, f"{y-2}-12-31", f"{y-1}-12-31", H, ycol))
    return folds


def cluster_features(feats, Xtr):
    Xs = Xtr[feats].sample(min(30000, len(Xtr)), random_state=0)
    c = Xs.rank().corr().abs().fillna(0).values
    np.fill_diagonal(c, 1.0)
    d = np.clip(1 - (c + c.T) / 2, 0, None); np.fill_diagonal(d, 0.0)
    lab = fcluster(linkage(squareform(d, checks=False), "average"), 1 - CORR_THR, "distance")
    groups = {}
    for f, l in zip(feats, lab):
        groups.setdefault(int(l), []).append(f)
    return list(groups.values())


def wf_eval(feats, groups=None):
    """走動式:回傳各折 AUC(seed 平均)、群重要性(折 × 群)、單欄 gain。"""
    aucs, imps, gains = [], [], []
    for y, tr, es, sc in FOLDS:
        ysc = sc[ycol].values.astype(int)
        a_seed, i_seed = [], []
        for seed in SEEDS:
            m = fit_xgb(tr[feats], tr[ycol].values.astype(int), es[feats], es[ycol].values.astype(int), seed, cfg["xgb"])
            base = roc_auc_score(ysc, predict_p(m, sc[feats]))
            a_seed.append(base)
            g = m.get_booster().get_score(importance_type="total_gain")
            gains.append(pd.Series({f: g.get(f, 0.0) for f in feats}))
            if groups:
                rng = np.random.default_rng(seed); Xp = sc[feats].copy(); imp = []
                for grp in groups:
                    orig = Xp[grp].values.copy(); drops = []
                    for _ in range(N_REPEATS):
                        Xp[grp] = orig[rng.permutation(len(Xp))]
                        drops.append(base - roc_auc_score(ysc, predict_p(m, Xp)))
                    Xp[grp] = orig
                    imp.append(np.mean(drops))
                i_seed.append(imp)
        aucs.append(float(np.mean(a_seed)))
        if groups:
            imps.append(np.mean(i_seed, axis=0))
    return aucs, (np.array(imps) if groups else None), pd.concat(gains, axis=1).mean(axis=1)


def gname(grp, gain):
    rep = gain.reindex(grp).idxmax()
    return rep if len(grp) == 1 else f"{rep} (+{len(grp)-1})"


t0 = time.time()
FOLDS = make_folds()
for y, tr, es, sc in FOLDS:
    print(f"[FOLD {y}] 訓練 {len(tr)} / 早停 {len(es)} / 評分 {len(sc)}")
groups = cluster_features(FULL, FOLDS[-1][1])
print(f"[CLUSTER] {len(FULL)} 欄 → {len(groups)} 群 (|ρ| ≥ {CORR_THR})")

path, rnd = [], 0
while True:
    feats = [f for g in groups for f in g]
    aucs, imps, gain = wf_eval(feats, groups)
    mean_imp, n_pos = imps.mean(axis=0), (imps > 0).sum(axis=0)
    keep = [(mean_imp[i] > 0) and (n_pos[i] >= 2) for i in range(len(groups))]
    path.append({"round": rnd, "n_groups": len(groups), "n_feat": len(feats), "wf_auc": aucs, "wf_auc_mean": float(np.mean(aucs)),
                 "groups": [{"members": g, "imp_mean": float(mean_imp[i]), "imp_folds": [float(v) for v in imps[:, i]], "kept": bool(keep[i])}
                            for i, g in enumerate(groups)]})
    print(f"[ROUND {rnd}] {len(groups)} 群 / {len(feats)} 欄  走動 AUC {np.mean(aucs):.4f} {[round(a,4) for a in aucs]}  "
          f"→ 剔 {len(groups)-sum(keep)} 群  ({time.time()-t0:.0f}s)", flush=True)
    if all(keep) or rnd >= 12:
        break
    groups = [g for g, k in zip(groups, keep) if k]; rnd += 1

best = max(p["wf_auc_mean"] for p in path)
chosen = min((p for p in path if p["wf_auc_mean"] >= best - TOL), key=lambda p: p["n_feat"])
groups = [g["members"] for g in chosen["groups"]]
print(f"[CHOSEN] round {chosen['round']}:{chosen['n_groups']} 群 / {chosen['n_feat']} 欄,走動 AUC {chosen['wf_auc_mean']:.4f}(最佳 {best:.4f})")

feats_all = [f for g in groups for f in g]
_, _, gain = wf_eval(feats_all)
reps = [gain.reindex(g).idxmax() for g in groups]
auc_rep, _, _ = wf_eval(reps)
use_reps = np.mean(auc_rep) >= chosen["wf_auc_mean"] - TOL
print(f"[REPS] 全部成員 {len(feats_all)} 欄 AUC {chosen['wf_auc_mean']:.4f} vs 只留代表 {len(reps)} 欄 AUC {np.mean(auc_rep):.4f} → {'採用代表欄' if use_reps else '保留全部成員'}")
final_groups = [[r] for r in reps] if use_reps else groups
FINAL = [f for g in final_groups for f in g]

base_aucs, _, gain = wf_eval(FINAL)
logo = []
for g in final_groups:
    rest = [f for f in FINAL if f not in g]
    a, _, _ = wf_eval(rest)
    d = [b - v for b, v in zip(base_aucs, a)]
    logo.append({"group": g, "family": fam.get(g[0]), "delta_mean": float(np.mean(d)), "delta_folds": [float(v) for v in d]})
    print(f"  [LOGO] 拿掉 {gname(g, gain):32s} {fam.get(g[0], ''):14s} ΔAUC {np.mean(d):+.4f}  {[round(v,4) for v in d]}", flush=True)
core = [f for l in logo if l["delta_mean"] > 0 and sum(v > 0 for v in l["delta_folds"]) >= 2 for f in l["group"]]
auc_core = wf_eval(core)[0] if core and len(core) < len(FINAL) else base_aucs
print(f"[CORE] 拿掉會讓 AUC 下降(≥2 折)的群:{len(core)} 欄,走動 AUC {np.mean(auc_core):.4f}(final {np.mean(base_aucs):.4f})")

tr, va, te = time_split(panel, cfg["train_end"], cfg["val_end"], H, ycol)
yte = te[ycol].values.astype(int)
sets = {"full": FULL, "full_top20": x["results"]["full_top20"]["features"], "full_permpos": x["results"]["full_permpos"]["features"],
        "selected": FINAL, "selected_core": core, "close_pos_only": ["close_pos"], "selected_no_close_pos": [f for f in FINAL if f != "close_pos"]}
test = {}
for name, fs in sets.items():
    if not fs:
        continue
    ps = [predict_p(fit_xgb(tr[fs], tr[ycol].values.astype(int), va[fs], va[ycol].values.astype(int), s, cfg["xgb"]), te[fs]) for s in cfg["seeds"]]
    m = clf_metrics(yte, np.mean(ps, axis=0)); m["n_feat"] = len(fs)
    m["auc_seed_std"] = float(np.std([roc_auc_score(yte, p) for p in ps], ddof=1))
    test[name] = m
    print(f"  [TEST {name:22s}] {len(fs):3d} 欄  Acc {m['acc']*100:.2f}  P {m['pre_1']*100:.2f}  R {m['rec_1']*100:.2f}  F1m {m['f1_macro']*100:.2f}  "
          f"AUC {m['auc']:.4f}  前5% Acc {m['acc_cov5']*100:.1f}", flush=True)

json.dump({"tag": TAG, "score_years": SCORE_YEARS, "seeds": SEEDS, "corr_thr": CORR_THR, "path": path, "chosen_round": chosen["round"],
           "use_reps": bool(use_reps), "wf_auc_reps": auc_rep, "final": FINAL, "final_groups": final_groups, "final_family": {f: fam.get(f) for f in FINAL},
           "wf_auc_final": base_aucs, "logo": logo, "core": core, "wf_auc_core": auc_core, "test": test, "elapsed_s": round(time.time() - t0)},
          open(os.path.join(P.XGB_EXP, f"select_{TAG}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[DONE] {time.time()-t0:.0f}s")
