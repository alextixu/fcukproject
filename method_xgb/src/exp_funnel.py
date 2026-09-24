"""漏斗式特徵篩選(五階段)— tw50 h5 cs、x26 切分。

依指定順序實作,每一階段同時跑「原規格」與「修正版」,由資料決定採用哪一個:
  S1 靜態過濾   零變異/高缺值 → |Spearman| ≥ THR 去共線(原規格:群內只留與目標單變量相關最高的一欄)
                 附診斷:把訓練期切兩半,檢查「群內冠軍」在前後半是否是同一欄(選擇穩定度)
  S2 切分框架   原規格月尺度 vs 年尺度走動式(訓練 ≤Y-2、早停 Y-1、評分 Y,標籤重疊以 h 天 purge)
                 附診斷:月尺度 AUC 的折間標準差 vs 訊號大小
  S3 動態評分   XGBoost colsample_bytree=0.7 → total_gain 排名 + SHAP 幅度與方向
                 方向檢查改為「跨 seed / 跨折的符號一致性」(不用先驗方向,見 docs)
  S4 遞迴淘汰   每輪砍 gain 最後 5%,重訓記錄走動 AUC;選點同時報「原規格 argmax」與「one-SE 規則」
  S5 盲測       2026 測試集只在最後看一次,報 P/R/Acc/F1(含隨機基準)與 AUC,對照 242/95/43 欄

輸出 experiments/funnel_x26-tw50-h5-cs.json、funnel_shap_x26-tw50-h5-cs.csv
用法: python method_xgb/src/exp_funnel.py [--corr-thr 0.75] [--skip-shap]
"""
import os, sys, json, time, argparse
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "method_xgb", "src"))
from common import paths as P
from split import time_split, filter_features
from train_xgb import fit_xgb, predict_p
from evaluate import clf_metrics, clf_metrics_csmed

TAG = "x26-tw50-h5-cs"
SCORE_YEARS = (2023, 2024, 2025)
SEEDS = (42, 43)
RFE_CUT = 0.05
RFE_MIN = 8
COLSAMPLE = 0.7

ap = argparse.ArgumentParser()
ap.add_argument("--corr-thr", type=float, default=0.75)
ap.add_argument("--skip-shap", action="store_true")
a = ap.parse_args()

x = json.load(open(os.path.join(P.XGB_EXP, f"{TAG}.json"), encoding="utf-8"))
cfg, ycol, H = x["config"], x["label"], x["config"]["horizon"]
FULL = x["results"]["full"]["features"]
PERMPOS = x["results"]["full_permpos"]["features"]
SEL43 = json.load(open(os.path.join(P.XGB_EXP, f"select_{TAG}.json"), encoding="utf-8"))["final"]
fam = pd.read_csv(os.path.join(P.XGB_EXP, f"{TAG}_importance.csv"), index_col=0)["family"].to_dict()
XGB = dict(cfg["xgb"]); XGB["colsample_bytree"] = COLSAMPLE

panel = pd.read_parquet(os.path.join(P.FEATURES, f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}.parquet"),
                        columns=FULL + [ycol])
dates = panel.index.get_level_values("date")
Y = lambda df: df[ycol].values.astype(int)
t0 = time.time()
log = lambda s: print(s, flush=True)

FOLDS = [(y,) + time_split(panel[dates <= pd.Timestamp(f"{y}-12-31")], f"{y-2}-12-31", f"{y-1}-12-31", H, ycol)
         for y in SCORE_YEARS]
TR, VA, TE = time_split(panel, cfg["train_end"], cfg["val_end"], H, ycol)
log(f"[DATA] panel {panel.shape}  標準切分 訓練 {len(TR)} / 早停 {len(VA)} / 測試 {len(TE)}(正例 {TE[ycol].mean():.4f})")
for y, tr, es, sc in FOLDS:
    log(f"[FOLD {y}] 訓練 {len(tr)} / 早停 {len(es)} / 評分 {len(sc)}")


def wf_eval(feats, want_gain=False):
    """年尺度走動式:回傳(各折 AUC 的 seed 平均, 各折各 seed 的 AUC, total_gain 平均)。"""
    fold_auc, flat, gains = [], [], []
    for y, tr, es, sc in FOLDS:
        per = []
        for seed in SEEDS:
            m = fit_xgb(tr[feats], Y(tr), es[feats], Y(es), seed, XGB)
            per.append(roc_auc_score(Y(sc), predict_p(m, sc[feats])))
            if want_gain:
                g = m.get_booster().get_score(importance_type="total_gain")
                gains.append(pd.Series({f: g.get(f, 0.0) for f in feats}))
        fold_auc.append(float(np.mean(per))); flat.append([float(v) for v in per])
    return fold_auc, flat, (pd.concat(gains, axis=1).mean(axis=1) if want_gain else None)


kept, stats = filter_features(TR, FULL, cfg["max_nan"])
log(f"[S1] 零變異/高缺值過濾:{len(FULL)} → {len(kept)} 欄")
Xs = TR[kept].sample(min(40000, len(TR)), random_state=0)
rk = Xs.rank()
corr = rk.corr(method="pearson").abs().fillna(0.0)
uni = pd.Series({f: abs(spearmanr(TR[f].values, Y(TR), nan_policy="omit")[0]) for f in kept}).fillna(0.0)
order = uni.sort_values(ascending=False).index.tolist()
survivors, dropped_by = [], {}
for f in order:
    hit = next((s for s in survivors if corr.loc[f, s] >= a.corr_thr), None)
    if hit is None:
        survivors.append(f)
    else:
        dropped_by[f] = hit
S1 = [f for f in kept if f in set(survivors)]
log(f"[S1] 去共線 |ρ| ≥ {a.corr_thr}:{len(kept)} → {len(S1)} 欄(保留與目標單變量相關較高者)")

half = TR.index.get_level_values("date")
mid = half[len(half) // 2]
A, B = TR[half <= mid], TR[half > mid]
uniA = pd.Series({f: abs(spearmanr(A[f].values, Y(A), nan_policy="omit")[0]) for f in kept}).fillna(0.0)
uniB = pd.Series({f: abs(spearmanr(B[f].values, Y(B), nan_policy="omit")[0]) for f in kept}).fillna(0.0)
clusters = {}
for f, s in dropped_by.items():
    clusters.setdefault(s, []).append(f)
agree, tot = 0, 0
for s, members in clusters.items():
    grp = [s] + members
    if len(grp) < 2:
        continue
    tot += 1
    agree += int(uniA.reindex(grp).idxmax() == uniB.reindex(grp).idxmax())
s1_stab = {"n_multi_groups": tot, "argmax_agree": agree, "agree_rate": round(agree / tot, 3) if tot else None,
           "uni_corr_median": round(float(uni.median()), 4), "uni_corr_max": round(float(uni.max()), 4)}
log(f"[S1-診斷] 多成員群 {tot} 個,前後半訓練期『單變量冠軍』同一欄只有 {agree} 個({s1_stab['agree_rate']});"
    f"單變量 |ρ| 中位數 {s1_stab['uni_corr_median']}、最大 {s1_stab['uni_corr_max']}")

m0 = fit_xgb(TR[S1], Y(TR), VA[S1], Y(VA), 42, XGB)
p0 = predict_p(m0, TE[S1]); dte = TE.index.get_level_values("date"); mo = dte.to_period("M").astype(str)
mon = {k: float(roc_auc_score(Y(TE)[mo == k], p0[mo == k])) for k in sorted(set(mo))}
s2 = {"monthly_auc": {k: round(v, 4) for k, v in mon.items()}, "monthly_std": round(float(np.std(list(mon.values()))), 4),
      "pooled_auc": round(float(roc_auc_score(Y(TE), p0)), 4), "rows_per_month": int(len(TE) / len(mon))}
s2["signal"] = round(s2["pooled_auc"] - 0.5, 4)
s2["noise_to_signal"] = round(s2["monthly_std"] / max(s2["signal"], 1e-9), 2)
log(f"[S2-診斷] 月尺度 AUC 標準差 {s2['monthly_std']}(每月約 {s2['rows_per_month']} 列),訊號僅 {s2['signal']} "
    f"→ 雜訊/訊號 = {s2['noise_to_signal']}×,月尺度折不可用;採年尺度走動式")

base_auc, base_flat, gain = wf_eval(S1, want_gain=True)
seed_sd = float(np.mean([np.std(v, ddof=1) for v in base_flat]))
log(f"[S3] {len(S1)} 欄 走動 AUC {np.mean(base_auc):.4f} {[round(v,4) for v in base_auc]}(seed 內標準差 {seed_sd:.4f}){time.time()-t0:.0f}s")

shap_rows = {}
if not a.skip_shap:
    import shap
    Xsh = VA[S1].sample(min(15000, len(VA)), random_state=0)
    vals, dirs = [], []
    for seed in (42, 43, 44):
        m = fit_xgb(TR[S1], Y(TR), VA[S1], Y(VA), seed, XGB)
        sv = shap.TreeExplainer(m).shap_values(Xsh)
        vals.append(np.abs(sv).mean(axis=0))
        dirs.append([spearmanr(Xsh[f].values, sv[:, i], nan_policy="omit")[0] for i, f in enumerate(S1)])
    dirs = np.array(dirs, dtype=float)
    shap_rows = {f: {"mean_abs_shap": float(np.mean([v[i] for v in vals])),
                     "dir_rho_mean": float(np.nanmean(dirs[:, i])),
                     "dir_sign_consistent": bool(np.all(np.sign(dirs[:, i]) == np.sign(dirs[0, i])) and abs(np.nanmean(dirs[:, i])) > 0.1)}
                 for i, f in enumerate(S1)}
    flip = [f for f, v in shap_rows.items() if not v["dir_sign_consistent"]]
    log(f"[S3-SHAP] 方向跨 3 seed 一致且 |ρ|>0.1 的欄:{len(S1)-len(flip)}/{len(S1)};方向不穩或近乎無方向 {len(flip)} 欄")
    pd.DataFrame(shap_rows).T.assign(family=lambda d: [fam.get(f) for f in d.index]) \
        .sort_values("mean_abs_shap", ascending=False).to_csv(os.path.join(P.XGB_EXP, f"funnel_shap_{TAG}.csv"))

cur, rfe = list(S1), []
cur_auc, cur_flat, cur_gain = base_auc, base_flat, gain
while True:
    rfe.append({"n_feat": len(cur), "feats": list(cur), "wf_auc": cur_auc, "wf_auc_mean": float(np.mean(cur_auc)),
                "fold_se": float(np.std(cur_auc, ddof=1) / np.sqrt(len(cur_auc)))})
    log(f"  [RFE] {len(cur):3d} 欄  走動 AUC {np.mean(cur_auc):.4f} {[round(v,4) for v in cur_auc]}  ({time.time()-t0:.0f}s)")
    n_cut = max(1, int(round(len(cur) * RFE_CUT)))
    if len(cur) - n_cut < RFE_MIN:
        break
    cur = cur_gain.reindex(cur).sort_values(ascending=False).index[:len(cur) - n_cut].tolist()
    cur_auc, cur_flat, cur_gain = wf_eval(cur, want_gain=True)

best = max(rfe, key=lambda r: r["wf_auc_mean"])
se = best["fold_se"]
one_se = min((r for r in rfe if r["wf_auc_mean"] >= best["wf_auc_mean"] - se), key=lambda r: r["n_feat"])
log(f"[S4] argmax:{best['n_feat']} 欄 AUC {best['wf_auc_mean']:.4f}(折間 SE {se:.4f});"
    f"one-SE:{one_se['n_feat']} 欄 AUC {one_se['wf_auc_mean']:.4f}")

sets = {"funnel_argmax": best["feats"], "funnel_1se": one_se["feats"], "S1_static": S1,
        "sel43_0918": SEL43, "permpos95": PERMPOS, "full242": FULL}
test = {}
for name, fs in sets.items():
    ps = [predict_p(fit_xgb(TR[fs], Y(TR), VA[fs], Y(VA), s, XGB), TE[fs]) for s in cfg["seeds"]]
    pm = np.mean(ps, axis=0)
    m = clf_metrics(Y(TE), pm); m |= {f"csmed_{k}": v for k, v in clf_metrics_csmed(Y(TE), pm, dte).items()}
    m["n_feat"] = len(fs); m["auc_seed_std"] = float(np.std([roc_auc_score(Y(TE), p) for p in ps], ddof=1))
    test[name] = m
    log(f"  [S5 {name:14s}] {len(fs):3d} 欄  AUC {m['auc']:.4f}±{m['auc_seed_std']:.4f}  "
        f"Acc {m['acc']*100:.2f}  P {m['pre_1']*100:.2f}  R {m['rec_1']*100:.2f}  F1m {m['f1_macro']*100:.2f}  |  "
        f"當日中位數 Acc {m['csmed_acc']*100:.2f} F1m {m['csmed_f1_macro']*100:.2f}")
log(f"  [S5 隨機基準] 正例比例 {TE[ycol].mean()*100:.2f}%  → Acc/P/R/F1 基準 ≈ 50")

json.dump({"tag": TAG, "corr_thr": a.corr_thr, "colsample": COLSAMPLE, "score_years": SCORE_YEARS, "seeds": SEEDS,
           "s1_static": S1, "s1_dropped_by": dropped_by, "s1_stability": s1_stab, "s2_fold_scale": s2,
           "s3_wf_auc": base_auc, "s3_seed_sd": seed_sd, "s3_shap": shap_rows,
           "s4_rfe": rfe, "s4_argmax_n": best["n_feat"], "s4_1se_n": one_se["n_feat"],
           "funnel_argmax": best["feats"], "funnel_1se": one_se["feats"],
           "funnel_1se_family": {f: fam.get(f) for f in one_se["feats"]},
           "test": test, "test_pos_ratio": float(TE[ycol].mean()), "elapsed_s": round(time.time() - t0)},
          open(os.path.join(P.XGB_EXP, f"funnel_{TAG}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
log(f"[DONE] {time.time()-t0:.0f}s")
