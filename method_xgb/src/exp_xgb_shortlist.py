"""篩出來的短名單(38 欄:209 欄裡重要性至少 5/7 年為正;8 欄:其中跨年 t 值最高的 8 個)各自訓練 XGBoost,和 209 欄配對比較。不量重要性。

  欄位: experiments/feature_set_v2_g90.csv(合併後再做 |ρ| ≥ 0.9 過濾的 209 欄);對照 = feature_representatives_g90.csv 的 162 欄。
  切分: 測試年 Y = 2019…2025;訓練 ≤ Y−2 年底、驗證(早停 + 量重要性)Y−1 年,兩段各切掉最後 6 個交易日;3 個 seed,機率取平均。
  模型: 專題一貫的 XGBoost 設定(樹深 5、學習率 0.03、每片葉子至少 50 筆、抽列 0.8、抽欄 0.5、L2 懲罰 5、早停 100 回合)。
  重要性: 驗證年上,把該欄在**每日內部**打亂(同日內為常數的 mkt_roc_*、dow_* 改成以日期為單位交換),
          看每日 rank IC 平均掉多少;每個 seed 打亂 2 次取平均。另記 gain 占比。
  評分: 7 個測試年合併——每日 rank IC 與 t 值(區塊 bootstrap)、AUC、四大指標(機率高於當日中位數判漲)、每日前 10 檔減池內平均。

輸出 experiments/xgb_shortlist_summary.json
"""
import os, sys, json, time, warnings
import numpy as np, pandas as pd
from xgboost import XGBClassifier
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore")
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, R)
from common import paths as P

PURGE, YEARS, SEEDS, NREP = 6, range(2019, 2026), (42, 43, 44), 2
XGB = dict(n_estimators=3000, learning_rate=0.03, max_depth=5, min_child_weight=50, subsample=0.8, colsample_bytree=0.5,
           reg_lambda=5.0, tree_method="hist", eval_metric="logloss", early_stopping_rounds=100, n_jobs=10)
cat = pd.concat([pd.read_csv(os.path.join(R, "method_xgb", "config", f)) for f in ("feature_catalog_top100.csv", "feature_catalog_top100_extra.csv")])
OLD162 = pd.read_csv(os.path.join(P.XGB_EXP, "feature_representatives_g90.csv")).representative.tolist()
REPS = pd.read_csv(os.path.join(P.XGB_EXP, "feature_set_v2_g90.csv")).representative.tolist()
panel = pd.concat([pd.read_parquet(os.path.join(P.FEATURES, "features_top100_2016-01-01_2026-09-11.parquet")),
                   pd.read_parquet(os.path.join(P.FEATURES, "features_top100_extra_2016-01-01_2026-09-11.parquet"))], axis=1)
panel = panel[panel["y_oo_h5"].notna()]
dates = panel.index.get_level_values("date"); ud = pd.DatetimeIndex(sorted(dates.unique()))
y = panel["y_oo_h5"].values.astype(int); r = panel["r_oo_h5"]
DAYCONST = lambda f: f.startswith(("mkt_roc_", "dow_"))


def folds():
    for Y in YEARS:
        tr = ud[ud <= pd.Timestamp(f"{Y-2}-12-31")][:-PURGE]
        va = ud[(ud > pd.Timestamp(f"{Y-2}-12-31")) & (ud <= pd.Timestamp(f"{Y-1}-12-31"))][:-PURGE]
        te = ud[(ud > pd.Timestamp(f"{Y-1}-12-31")) & (ud <= pd.Timestamp(f"{Y}-12-31"))]
        yield Y, np.where(dates.isin(tr))[0], np.where(dates.isin(va))[0], np.where(dates.isin(te))[0]


def daily_ic(prob, idx):
    Pw = pd.Series(prob, index=panel.index[idx]).unstack("ticker").rank(axis=1); Rw = r.iloc[idx].unstack("ticker").rank(axis=1)
    m = Pw.notna() & Rw.notna(); a, b = Pw.where(m), Rw.where(m)
    a, b = a.sub(a.mean(axis=1), axis=0), b.sub(b.mean(axis=1), axis=0)
    return (a * b).sum(axis=1) / np.sqrt((a ** 2).sum(axis=1) * (b ** 2).sum(axis=1))


def block_t(s, block=10, nboot=2000, seed=0):
    s = np.asarray(s, float); s = s[~np.isnan(s)]; n = len(s); rng = np.random.default_rng(seed); k = int(np.ceil(n / block))
    st = rng.integers(0, n - block + 1, size=(nboot, k)); idx = (st[:, :, None] + np.arange(block)[None, None, :]).reshape(nboot, -1)[:, :n]
    return float(s.mean() / s[idx].mean(axis=1).std(ddof=1))


def shuffle_col(x, idx, const, rng):
    d = dates[idx]
    if const:
        u = d.unique(); v = pd.Series(x, index=d).groupby(level=0).first(); mp = dict(zip(u, v.loc[u].values[rng.permutation(len(u))]))
        return d.map(mp).values.astype(np.float32)
    out = x.copy(); order = np.argsort(d.values, kind="stable"); bounds = np.flatnonzero(np.diff(d.values[order]).astype(bool)) + 1
    for seg in np.split(order, bounds):
        out[seg] = x[seg][rng.permutation(len(seg))]
    return out


def run(name, feats, importance):
    X = panel[feats].values.astype(np.float32); te_prob, te_idx, imp, gain, trees = [], [], {f: [] for f in feats}, {f: [] for f in feats}, []
    for Y, tr, va, te in folds():
        miss = np.isnan(X[tr]).mean(axis=0); keep = np.where(miss <= 0.30)[0]
        ps = []
        for seed in SEEDS:
            m = XGBClassifier(random_state=seed, **XGB).fit(X[tr][:, keep], y[tr], eval_set=[(X[va][:, keep], y[va])], verbose=False)
            ps.append(m.predict_proba(X[te][:, keep])[:, 1]); trees.append(int(m.best_iteration))
            g = m.get_booster().get_score(importance_type="total_gain"); tot = sum(g.values()) or 1.0
            for j, k in enumerate(keep): gain[feats[k]].append(g.get(f"f{j}", 0.0) / tot)
            if importance:
                Xv = X[va][:, keep].copy(); base = daily_ic(m.predict_proba(Xv)[:, 1], va).mean(); rng = np.random.default_rng(seed)
                for j, k in enumerate(keep):
                    col = Xv[:, j].copy(); drops = []
                    for _ in range(NREP):
                        Xv[:, j] = shuffle_col(col, va, DAYCONST(feats[k]), rng); drops.append(base - daily_ic(m.predict_proba(Xv)[:, 1], va).mean())
                    Xv[:, j] = col; imp[feats[k]].append((Y, float(np.mean(drops))))
        te_prob.append(np.mean(ps, axis=0)); te_idx.append(te)
        print(f"[{name}] {Y}: 用 {len(keep)}/{len(feats)} 欄,棵數 {trees[-3:]},測試 IC {daily_ic(te_prob[-1], te).mean():.4f}  ({time.time()-T0:.0f}s)", flush=True)
    prob, idx = np.concatenate(te_prob), np.concatenate(te_idx); ic = daily_ic(prob, idx)
    Pw = pd.Series(prob, index=panel.index[idx]).unstack("ticker"); Yw = pd.Series(y[idx], index=panel.index[idx]).unstack("ticker"); Rw = r.iloc[idx].unstack("ticker")
    pred = Pw.gt(Pw.median(axis=1), axis=0); ok = Pw.notna(); yv = Yw == 1
    tp, fp, fn, tn = [int(v.sum().sum()) for v in (pred & yv & ok, pred & ~yv & ok, ~pred & yv & ok, ~pred & ~yv & ok)]
    pr, rc = tp / (tp + fp), tp / (tp + fn); top = (Rw.sub(Rw.mean(axis=1), axis=0)).where(Pw.rank(axis=1, ascending=False, method="first") <= 10).mean(axis=1) * 1e4
    yr = ic.groupby(ic.index.year).mean()
    summ = {"n_feat": len(feats), "ic_mean": float(ic.mean()), "ic_t": block_t(ic.values), "ic_by_year": {int(k): round(float(v), 4) for k, v in yr.items()},
            "auc": float(roc_auc_score(y[idx], prob)), "acc": (tp + tn) / (tp + fp + fn + tn), "precision": pr, "recall": rc, "f1": 2 * pr * rc / (pr + rc),
            "top10_excess_bp": float(top.mean()), "top10_t": block_t(top.values), "trees_median": int(np.median(trees)), "n_test_days": int(len(ic))}
    return summ, imp, gain, ic, top


T0 = time.time()
imp209 = pd.read_csv(os.path.join(P.XGB_EXP, "xgb_v2_209.csv"))
S38 = imp209[(imp209.perm_pos_folds >= 5) & (imp209.perm_mean > 0)]
F38 = S38.feature.tolist(); F8 = S38.sort_values("perm_t", ascending=False).feature.head(8).tolist()
print("8 欄:", F8, flush=True)
res = {}
for name, feats in (("209 欄", REPS), ("38 欄", F38), ("8 欄", F8)):
    summ, _, _, ic, top = run(name, feats, importance=False); res[name] = (summ, ic, top)
out = {k: v[0] for k, v in res.items()}; out["features_8"] = F8; out["features_38"] = F38
for k in ("38 欄", "8 欄"):
    d = (res[k][1] - res["209 欄"][1]).dropna(); dt = (res[k][2] - res["209 欄"][2]).dropna()
    out[f"diff_{k}_minus_209"] = {"ic_mean": float(d.mean()), "ic_t": block_t(d.values), "corr_daily_ic": float(np.corrcoef(res[k][1].loc[d.index], res["209 欄"][1].loc[d.index])[0, 1]),
                                   "top10_bp": float(dt.mean()), "top10_t": block_t(dt.values)}
out["elapsed_s"] = round(time.time() - T0)
json.dump(out, open(os.path.join(P.XGB_EXP, "xgb_shortlist_summary.json"), "w"), ensure_ascii=False, indent=1)
print("[DONE]", round(time.time() - T0), "s", flush=True)
