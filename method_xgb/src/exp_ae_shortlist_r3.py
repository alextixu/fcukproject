"""38 欄短名單:原始 / PCA / 三種自編碼器 → XGBoost,在同一套 walk-forward 下比較(2026-09-21 使用者指定的五組)。

  組別: raw38(基準)、pca12 / pca8(線性基準)、ae_12(38→12)、ae_24_12(38→24→12)、ae_20_8(38→20→8)。第 2 ~ 5 類只把潛在特徵交給 XGBoost。
  前處理(PCA 與自編碼器共用): 每日橫斷面標準化(當天 100 檔的 z 分數)、截 ±5、缺值補 0(= 當日平均)。只用當天資料,沒有前視。
  自編碼器: 每層後接 tanh(含最窄層;否則一層版本等於 PCA),解碼器對稱、輸出層線性;Adam 1e-3、權重衰減 1e-5、批次 512、
            最多 200 回合、驗證年還原誤差連 10 回合不降就停。只用訓練段訓練;seed 42/43/44 與 XGBoost 的 seed 一對一配對。
  PCA: 只用訓練段配適。
  切分 / XGBoost / 評分: 同 exp_xgb_shortlist.py(測試年 2019…2025、訓練 ≤ Y−2、驗證 Y−1、各切掉最後 6 個交易日、3 seeds 機率平均)。

輸出 experiments/ae_shortlist_summary.json
"""
import os, sys, json, time, warnings
import numpy as np, pandas as pd
from joblib import Parallel, delayed
from sklearn.decomposition import PCA
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore")
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, R)
from common import paths as P

PURGE, YEARS, SEEDS = 6, list(range(2019, 2026)), (42, 43, 44)
XGB = dict(n_estimators=3000, learning_rate=0.03, max_depth=5, min_child_weight=50, subsample=0.8, colsample_bytree=0.5,
           reg_lambda=5.0, tree_method="hist", eval_metric="logloss", early_stopping_rounds=100, n_jobs=1)
ARCH = {"ae_8": [8], "ae_12": [12], "ae_16": [16], "ae_24": [24]}
PCA_K = ()
F38 = pd.read_csv(os.path.join(P.XGB_EXP, "feature_shortlist_v2.csv")).feature.tolist()
panel = pd.concat([pd.read_parquet(os.path.join(P.FEATURES, "features_top100_2016-01-01_2026-09-11.parquet")),
                   pd.read_parquet(os.path.join(P.FEATURES, "features_top100_extra_2016-01-01_2026-09-11.parquet"))], axis=1)
panel = panel[panel["y_oo_h5"].notna()]
dates = panel.index.get_level_values("date"); ud = pd.DatetimeIndex(sorted(dates.unique()))
y = panel["y_oo_h5"].values.astype(int); r = panel["r_oo_h5"]
RAW = panel[F38].values.astype(np.float32)
g = panel[F38].groupby(level="date")
Z = ((panel[F38] - g.transform("mean")) / g.transform("std").replace(0, np.nan)).clip(-5, 5).fillna(0.0).values.astype(np.float32)
FOLDS = {}
for Y in YEARS:
    tr = ud[ud <= pd.Timestamp(f"{Y-2}-12-31")][:-PURGE]; va = ud[(ud > pd.Timestamp(f"{Y-2}-12-31")) & (ud <= pd.Timestamp(f"{Y-1}-12-31"))][:-PURGE]
    te = ud[(ud > pd.Timestamp(f"{Y-1}-12-31")) & (ud <= pd.Timestamp(f"{Y}-12-31"))]
    FOLDS[Y] = tuple(np.where(dates.isin(d))[0] for d in (tr, va, te))


def train_ae(arch, Y, seed):
    import torch, torch.nn as nn
    torch.set_num_threads(1); torch.manual_seed(seed); np.random.seed(seed)
    tr, va, te = FOLDS[Y]; dims = [Z.shape[1]] + ARCH[arch]
    enc = []; dec = []
    for a, b in zip(dims[:-1], dims[1:]): enc += [nn.Linear(a, b), nn.Tanh()]
    rd = dims[::-1]
    for i, (a, b) in enumerate(zip(rd[:-1], rd[1:])): dec += [nn.Linear(a, b)] + ([nn.Tanh()] if i < len(rd) - 2 else [])
    E_, D_ = nn.Sequential(*enc), nn.Sequential(*dec); opt = torch.optim.Adam(list(E_.parameters()) + list(D_.parameters()), 1e-3, weight_decay=1e-5)
    Xt, Xv = torch.from_numpy(Z[tr]), torch.from_numpy(Z[va]); best, state, bad, ep = np.inf, None, 0, 0
    for ep in range(1, 201):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 512):
            xb = Xt[perm[i:i + 512]]; opt.zero_grad(); loss = ((D_(E_(xb)) - xb) ** 2).mean(); loss.backward(); opt.step()
        with torch.no_grad(): v = float(((D_(E_(Xv)) - Xv) ** 2).mean())
        if v < best - 1e-5: best, bad, state = v, 0, ({k: t.clone() for k, t in E_.state_dict().items()}, {k: t.clone() for k, t in D_.state_dict().items()})
        else:
            bad += 1
            if bad >= 10: break
    E_.load_state_dict(state[0]); D_.load_state_dict(state[1])
    with torch.no_grad():
        lat = {k: E_(torch.from_numpy(Z[i])).numpy() for k, i in (("tr", tr), ("va", va), ("te", te))}
        te_mse = float(((D_(E_(torch.from_numpy(Z[te]))) - torch.from_numpy(Z[te])) ** 2).mean())
    return (arch, Y, seed), lat, {"epochs": ep, "val_mse": best, "test_mse": te_mse}


def fit_xgb(Xtr, Xva, Xte, Y, seed):
    from xgboost import XGBClassifier
    tr, va, te = FOLDS[Y]
    m = XGBClassifier(random_state=seed, **XGB).fit(Xtr, y[tr], eval_set=[(Xva, y[va])], verbose=False)
    return m.predict_proba(Xte)[:, 1], int(m.best_iteration)


def block_t(s, block=10, nboot=2000, seed=0):
    s = np.asarray(s, float); s = s[~np.isnan(s)]; n = len(s); rng = np.random.default_rng(seed); k = int(np.ceil(n / block))
    st = rng.integers(0, n - block + 1, size=(nboot, k)); idx = (st[:, :, None] + np.arange(block)[None, None, :]).reshape(nboot, -1)[:, :n]
    return float(s.mean() / s[idx].mean(axis=1).std(ddof=1))


def score(prob):
    idx = np.concatenate([FOLDS[Y][2] for Y in YEARS]); ix = panel.index[idx]
    Pw = pd.Series(prob, index=ix).unstack("ticker"); Rw = r.iloc[idx].unstack("ticker"); Yw = pd.Series(y[idx], index=ix).unstack("ticker")
    a, b = Pw.rank(axis=1), Rw.rank(axis=1); a, b = a.sub(a.mean(axis=1), axis=0), b.sub(b.mean(axis=1), axis=0)
    ic = (a * b).sum(axis=1) / np.sqrt((a ** 2).sum(axis=1) * (b ** 2).sum(axis=1))
    pred = Pw.gt(Pw.median(axis=1), axis=0); ok = Pw.notna(); yv = Yw == 1
    tp, fp, fn, tn = [int(v.sum().sum()) for v in (pred & yv & ok, pred & ~yv & ok, ~pred & yv & ok, ~pred & ~yv & ok)]
    pr, rc = tp / (tp + fp), tp / (tp + fn); rk = Pw.rank(axis=1, ascending=False, method="first"); Rd = Rw.sub(Rw.mean(axis=1), axis=0)
    tops = {k: Rd.where(rk <= k).mean(axis=1) * 1e4 for k in (3, 10, 20)}; yr = ic.groupby(ic.index.year).mean()
    summ = {"ic_mean": float(ic.mean()), "ic_t": block_t(ic.values), "ic_by_year": {int(k): round(float(v), 4) for k, v in yr.items()}, "auc": float(roc_auc_score(y[idx], prob)),
            "acc": (tp + tn) / (tp + fp + fn + tn), "precision": pr, "recall": rc, "f1": 2 * pr * rc / (pr + rc),
            **{f"top{k}_bp": float(v.mean()) for k, v in tops.items()}, **{f"top{k}_t": block_t(v.values) for k, v in tops.items()}}
    return summ, ic, tops[10]


if __name__ == "__main__":
    T0 = time.time()
    jobs = [(a, Y, s) for a in ARCH for Y in YEARS for s in SEEDS]
    ae = Parallel(n_jobs=10, verbose=5)(delayed(train_ae)(*j) for j in jobs)
    LAT = {k: v for k, v, _ in ae}; AEINFO = {f"{k[0]}|{k[1]}|{k[2]}": i for k, _, i in ae}
    print(f"自編碼器 {len(jobs)} 個訓練完 {time.time()-T0:.0f}s", flush=True)
    PCAINFO = {}; PCL = {}
    for Y in YEARS:
        tr, va, te = FOLDS[Y]
        for k in PCA_K:
            p = PCA(n_components=k, random_state=0).fit(Z[tr]); PCL[(f"pca{k}", Y)] = {"tr": p.transform(Z[tr]), "va": p.transform(Z[va]), "te": p.transform(Z[te])}
            rec = p.inverse_transform(p.transform(Z[te])); PCAINFO[f"pca{k}|{Y}"] = {"explained_var": float(p.explained_variance_ratio_.sum()), "test_mse": float(((rec - Z[te]) ** 2).mean())}

    def feats(arm, Y, seed):
        tr, va, te = FOLDS[Y]
        if arm == "raw38": return RAW[tr], RAW[va], RAW[te]
        L = PCL[(arm, Y)] if arm.startswith("pca") else LAT[(arm, Y, seed)]
        return L["tr"], L["va"], L["te"]
    ARMS = ["raw38"] + list(ARCH) + [f"pca{k}" for k in PCA_K]
    xj = [(arm, Y, s) for arm in ARMS for Y in YEARS for s in SEEDS]
    xr = Parallel(n_jobs=10, verbose=5)(delayed(fit_xgb)(*feats(arm, Y, s), Y, s) for arm, Y, s in xj)
    PR = {k: v for k, v in zip(xj, xr)}; out = {"arms": {}, "diff_vs_raw38": {}, "ae_info": {}, "pca_info": {}}; S = {}
    for arm in ARMS:
        prob = np.concatenate([np.mean([PR[(arm, Y, s)][0] for s in SEEDS], axis=0) for Y in YEARS])
        summ, ic, top = score(prob); summ["trees_median"] = int(np.median([PR[(arm, Y, s)][1] for Y in YEARS for s in SEEDS])); out["arms"][arm] = summ; S[arm] = (ic, top)
    for a, b in [(x, "raw38") for x in ARMS[1:]] + [(x, "ae_12") for x in ARMS[1:] if x != "ae_12"]:
        d, dt = (S[a][0] - S[b][0]).dropna(), (S[a][1] - S[b][1]).dropna()
        out["diff_vs_raw38" if b == "raw38" else "diff_other"] = {**out.get("diff_vs_raw38" if b == "raw38" else "diff_other", {}),
            f"{a} − {b}": {"ic_mean": float(d.mean()), "ic_t": block_t(d.values), "top10_bp": float(dt.mean()), "top10_t": block_t(dt.values), "corr_daily_ic": float(np.corrcoef(S[a][0], S[b][0])[0, 1])}}
    for a in ARCH:
        v = [AEINFO[f"{a}|{Y}|{s}"] for Y in YEARS for s in SEEDS]; out["ae_info"][a] = {"epochs_median": int(np.median([x["epochs"] for x in v])), "val_mse": float(np.mean([x["val_mse"] for x in v])), "test_mse": float(np.mean([x["test_mse"] for x in v]))}
    for k in PCA_K:
        v = [PCAINFO[f"pca{k}|{Y}"] for Y in YEARS]; out["pca_info"][f"pca{k}"] = {"explained_var": float(np.mean([x["explained_var"] for x in v])), "test_mse": float(np.mean([x["test_mse"] for x in v]))}
    out["elapsed_s"] = round(time.time() - T0)
    json.dump(out, open(os.path.join(P.XGB_EXP, "ae_shortlist_summary_r3.json"), "w"), ensure_ascii=False, indent=1)
    print("[DONE]", out["elapsed_s"], "s", flush=True)
