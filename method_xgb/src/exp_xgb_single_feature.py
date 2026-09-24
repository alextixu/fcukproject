"""XGBoost 單一特徵掃描:242 欄每次只放一欄,看哪些特徵單獨就有預測力。

  資料: features_top100_2016-01-01_2026-09-11.parquet(2026-08-31 市值前 100 大,暫行股票池,有存活者偏差)。
  標籤: y_oo_h5 = open[t+6]/open[t+1]−1 是否高於當日池內中位數;評分用連續報酬 r_oo_h5。
  切分: 測試年 Y = 2019…2025;訓練 ≤ Y−2 年底、早停 Y−1 年,兩段各切掉最後 6 個交易日;7 年測試預測合併評分。
  指標: 每日 rank IC(預測機率 vs 實際報酬的 Spearman)平均與 t 值(區塊 bootstrap,10 天)、IC 為正的年數、
        AUC、四大指標(機率高於當日中位數判漲)、每日前 10 檔減池內平均(基點)、原始特徵自己的每日 IC(看方向)。
  同日內為常數的特徵(mkt_roc_*、dow_*)單獨用時同一天所有股票分數相同,無法排序,IC 無定義。

模型: 輕量 XGBoost(樹深 3、學習率 0.05、每片葉子至少 200 筆、最多 500 棵、早停 50 回合),單一 seed。

輸出 experiments/xgb_single_feature_top100.csv
"""
import os, sys, time, warnings
import numpy as np, pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore")
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, R)
from common import paths as P

H, PURGE, YEARS = 5, 6, range(2019, 2026)
XGB = dict(n_estimators=500, learning_rate=0.05, max_depth=3, min_child_weight=200, subsample=0.8, reg_lambda=5.0,
           tree_method="hist", eval_metric="logloss", early_stopping_rounds=50, n_jobs=1, random_state=42)

panel = pd.read_parquet(os.path.join(P.FEATURES, "features_top100_2016-01-01_2026-09-11.parquet"))
FEATS = pd.read_csv(os.path.join(R, "method_xgb", "config", "feature_catalog_top100.csv"))
fam = dict(zip(FEATS.name, FEATS.family)); FEATS = FEATS.name.tolist()
panel = panel[panel["y_oo_h5"].notna()]
dates = panel.index.get_level_values("date"); udates = pd.DatetimeIndex(sorted(dates.unique()))
y_all, r_all = panel["y_oo_h5"].values.astype(int), panel["r_oo_h5"]
FOLDS = []
for Y in YEARS:
    tr_d = udates[udates <= pd.Timestamp(f"{Y-2}-12-31")][:-PURGE]
    va_d = udates[(udates > pd.Timestamp(f"{Y-2}-12-31")) & (udates <= pd.Timestamp(f"{Y-1}-12-31"))][:-PURGE]
    te_d = udates[(udates > pd.Timestamp(f"{Y-1}-12-31")) & (udates <= pd.Timestamp(f"{Y}-12-31"))]
    FOLDS.append((Y, np.where(dates.isin(tr_d))[0], np.where(dates.isin(va_d))[0], np.where(dates.isin(te_d))[0]))
TE = np.concatenate([f[3] for f in FOLDS]); te_index = panel.index[TE]
R_W = r_all.iloc[TE].unstack("ticker"); Y_W = pd.Series(y_all[TE], index=te_index).unstack("ticker")
R_RK = R_W.rank(axis=1); R_DM = R_W.sub(R_W.mean(axis=1), axis=0)


def row_corr(a: pd.DataFrame, b: pd.DataFrame) -> pd.Series:
    m = a.notna() & b.notna(); a, b = a.where(m), b.where(m)
    a, b = a.sub(a.mean(axis=1), axis=0), b.sub(b.mean(axis=1), axis=0)
    return (a * b).sum(axis=1) / np.sqrt((a ** 2).sum(axis=1) * (b ** 2).sum(axis=1))


def block_t(s, block=10, nboot=1000, seed=0):
    s = np.asarray(s, float); s = s[~np.isnan(s)]; n = len(s)
    if n < 50 or s.std() == 0: return np.nan
    rng = np.random.default_rng(seed); k = int(np.ceil(n / block)); st = rng.integers(0, n - block + 1, size=(nboot, k))
    idx = (st[:, :, None] + np.arange(block)[None, None, :]).reshape(nboot, -1)[:, :n]
    return s.mean() / s[idx].mean(axis=1).std(ddof=1)


def one(feat):
    from xgboost import XGBClassifier
    x = panel[feat].values.astype(np.float32).reshape(-1, 1); prob = np.full(len(TE), np.nan); trees = []; pos = 0
    for Y, tr, va, te in FOLDS:
        m = XGBClassifier(**XGB).fit(x[tr], y_all[tr], eval_set=[(x[va], y_all[va])], verbose=False)
        prob[pos:pos + len(te)] = m.predict_proba(x[te])[:, 1]; pos += len(te); trees.append(int(m.best_iteration))
    Pw = pd.Series(prob, index=te_index).unstack("ticker")
    Fw = pd.Series(x[TE, 0], index=te_index).unstack("ticker")
    const_day = bool((Pw.std(axis=1) < 1e-12).mean() > 0.5)
    ic = row_corr(Pw.rank(axis=1), R_RK); ic_raw = row_corr(Fw.rank(axis=1), R_RK)
    yr = ic.groupby(ic.index.year).mean()
    pred = Pw.gt(Pw.median(axis=1), axis=0); yv = Y_W == 1; ok = Pw.notna() & Y_W.notna()
    tp = int((pred & yv & ok).sum().sum()); fp = int((pred & ~yv & ok).sum().sum()); fn = int((~pred & yv & ok).sum().sum()); tn = int((~pred & ~yv & ok).sum().sum())
    prec = tp / max(tp + fp, 1); rec = tp / max(tp + fn, 1)
    top = R_DM.where(Pw.rank(axis=1, ascending=False, method="first") <= 10).mean(axis=1) * 1e4
    return {"feature": feat, "family": fam[feat], "ic_mean": ic.mean(), "ic_t": block_t(ic.values), "ic_pos_years": int((yr > 0).sum()),
            "ic_min_year": yr.min(), "raw_ic_mean": ic_raw.mean(), "auc": roc_auc_score(y_all[TE], prob),
            "acc": (tp + tn) / max(tp + fp + fn + tn, 1), "precision": prec, "recall": rec, "f1": 2 * prec * rec / max(prec + rec, 1e-12),
            "pred_up_ratio": (tp + fp) / max(tp + fp + fn + tn, 1), "top10_excess_bp": top.mean(), "top10_t": block_t(top.values),
            "trees_median": int(np.median(trees)), "const_within_day": const_day, **{f"ic_{int(k)}": v for k, v in yr.items()}}


if __name__ == "__main__":
    t0 = time.time()
    print(f"樣本 {len(panel)};測試列 {len(TE)}({R_W.shape[0]} 天);正例比例 {y_all[TE].mean():.4f};特徵 {len(FEATS)} 欄", flush=True)
    res = Parallel(n_jobs=10, batch_size=4, verbose=5)(delayed(one)(f) for f in FEATS)
    df = pd.DataFrame(res).sort_values("ic_t", ascending=False)
    df.to_csv(os.path.join(P.XGB_EXP, "xgb_single_feature_top100.csv"), index=False)
    print(f"[DONE] {time.time()-t0:.0f}s", flush=True)
