"""特徵重要性:gain / permutation(val) / SHAP(可選) → 合成排名。"""
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


def gain_importance(model, feats):
    b = model.get_booster()
    sc = b.get_score(importance_type="total_gain")
    s = pd.Series({f: sc.get(f, 0.0) for f in feats}, dtype=float)
    return s / max(s.sum(), 1e-12)


def permutation_importance(model, Xva, yva, feats, n_repeats=3, seed=0):
    rng = np.random.default_rng(seed)
    base = roc_auc_score(yva, model.predict_proba(Xva)[:, 1])
    out = {}
    Xp = Xva.copy()
    for f in feats:
        orig = Xp[f].values.copy()
        drops = []
        for _ in range(n_repeats):
            Xp[f] = rng.permutation(orig)
            drops.append(base - roc_auc_score(yva, model.predict_proba(Xp)[:, 1]))
        Xp[f] = orig
        out[f] = float(np.mean(drops))
    return pd.Series(out), base


def shap_importance(model, Xva, feats, n=5000, seed=0):
    try:
        import shap
    except ImportError:
        return None
    Xs = Xva.sample(min(n, len(Xva)), random_state=seed)
    ex = shap.TreeExplainer(model)
    v = ex.shap_values(Xs)
    if isinstance(v, list):
        v = v[1]
    return pd.Series(np.abs(v).mean(axis=0), index=feats)


def composite_rank(tables: list) -> pd.DataFrame:
    """tables: list of Series(feature → importance, 越大越重要)。回傳 rank_mean / rank_std。"""
    ranks = pd.concat([t.rank(ascending=False) for t in tables], axis=1)
    return pd.DataFrame({"rank_mean": ranks.mean(axis=1), "rank_std": ranks.std(axis=1)})


def dedupe_correlated(Xtr, order: list, thr=0.95, n_sample=30000, seed=0):
    """依 order(重要者在前)逐一納入;與已納入者 |Spearman| > thr 者剔除。"""
    Xs = Xtr[order].sample(min(n_sample, len(Xtr)), random_state=seed)
    corr = Xs.rank().corr().abs().values
    idx = {f: i for i, f in enumerate(order)}
    kept, dropped = [], {}
    for f in order:
        i = idx[f]
        rep = next((k for k in kept if corr[i, idx[k]] > thr), None)
        if rep is None:
            kept.append(f)
        else:
            dropped[f] = rep
    return kept, dropped
