"""
有監督版型態模型:把 One-Class SVM 換成有反例的分類器,其餘流程不動。

流程:特徵 → StandardScaler → Autoencoder(全部訓練樣本)壓到 LATENT_DIM 維
      → 看漲分類器(正例 future_ret > RISE_THRESH,其餘為反例)
      → 看跌分類器(正例 future_ret < FALL_THRESH,其餘為反例)
訊號:分類器機率 ≥ 門檻才出訊號;門檻 = 驗證段機率的 (1 - SIG_FRAC) 分位數,
      也就是「只在最有把握的 SIG_FRAC 比例情況下出手」。看漲優先於看跌(同 backtest.py)。
訓練:訓練期依日期切 80/20,前 80% 訓練、後 20% 驗證(算指標、早停、定門檻),
      之後用整段訓練期重訓一次當最終模型(門檻沿用驗證段分位數)。
原本的 pattern_model.py / validate.py / backtest.py 完全不動。
"""

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

from kline.config import TRAIN_START, TRAIN_END, RISE_THRESH, FALL_THRESH, LATENT_DIM
from kline.autoencoder import train_ae

SIG_FRAC = 0.10      # 出訊號比例(最有把握的前 10%)
XGB_PARAMS = dict(n_estimators=600, learning_rate=0.05, max_depth=4, min_child_weight=50,
                  subsample=0.8, colsample_bytree=0.8, reg_lambda=5.0, n_jobs=4, random_state=42)


def _make_clf(kind, n_pos, n_all):
    if kind == 'logistic':
        return LogisticRegression(max_iter=2000, C=1.0)
    from xgboost import XGBClassifier
    return XGBClassifier(**XGB_PARAMS, eval_metric='logloss', early_stopping_rounds=50)


def _fit(kind, X, y, X_val=None, y_val=None, n_iter=None):
    clf = _make_clf(kind, y.sum(), len(y))
    if kind == 'logistic':
        return clf.fit(X, y)
    if n_iter is not None:                       # 重訓:固定棵數、不早停
        from xgboost import XGBClassifier
        p = dict(XGB_PARAMS); p['n_estimators'] = int(n_iter)
        return XGBClassifier(**p).fit(X, y)
    return clf.fit(X, y, eval_set=[(X_val, y_val)], verbose=False)


def _metrics(y, p, frac):
    top = np.argsort(-p)[: max(int(len(p) * frac), 1)]
    return {'auc': float(roc_auc_score(y, p)), 'base_rate': float(y.mean()),
            'prec_top': float(y[top].mean()), 'n_top': int(len(top))}


def train_supervised(df, feat_cols, log_fn, clf='xgb', space='latent', sig_frac=SIG_FRAC):
    """回傳 {'scaler','ae','space','bull':{'clf','thr','val'}, 'bear':{...}}。"""
    train_df = df[(df.index >= TRAIN_START) & (df.index <= TRAIN_END)]
    dates = train_df.index.unique().sort_values()
    split = dates[int(len(dates) * 0.8)]
    fit_df, val_df = train_df[train_df.index < split], train_df[train_df.index >= split]
    log_fn(f"  訓練段 {len(fit_df):,} 筆(< {str(split)[:10]})  驗證段 {len(val_df):,} 筆  分類器 {clf}  空間 {space}")

    scaler = StandardScaler().fit(fit_df[feat_cols].values.astype(np.float32))
    Xs = lambda d: np.clip(scaler.transform(d[feat_cols].values.astype(np.float32)), -5, 5)
    X_fit, X_val, X_all = Xs(fit_df), Xs(val_df), Xs(train_df)
    ae = None
    if space == 'latent':
        torch.manual_seed(42)
        ae = train_ae(X_fit, len(feat_cols), lambda s: None); ae.eval()
        enc = lambda X: ae.encode(torch.FloatTensor(X)).numpy()
        with torch.no_grad():
            X_fit, X_val, X_all = enc(X_fit), enc(X_val), enc(X_all)
    y_fit_r, y_val_r, y_all_r = (d['future_ret'].values.astype(np.float32) for d in (fit_df, val_df, train_df))

    models = {'scaler': scaler, 'ae': ae, 'space': space, 'clf': clf, 'sig_frac': sig_frac}
    for direction, lab, cond in (('bull', '看漲', lambda r: r > RISE_THRESH), ('bear', '看跌', lambda r: r < FALL_THRESH)):
        y_fit, y_val, y_all = (cond(r).astype(int) for r in (y_fit_r, y_val_r, y_all_r))
        m = _fit(clf, X_fit, y_fit, X_val, y_val)
        p_val = m.predict_proba(X_val)[:, 1]
        met = _metrics(y_val, p_val, sig_frac)
        n_iter = getattr(m, 'best_iteration', None)
        n_iter = None if n_iter is None else n_iter + 1
        final = _fit(clf, X_all, y_all, n_iter=n_iter)
        thr = float(np.quantile(final.predict_proba(X_val)[:, 1], 1 - sig_frac))
        log_fn(f"  [{lab}] 驗證 AUC {met['auc']:.3f}  最有把握 {sig_frac:.0%} 命中 {met['prec_top']:.2%}(隨機 {met['base_rate']:.2%})"
               + (f"  棵數 {n_iter}" if n_iter else "") + f"  門檻 {thr:.3f}")
        models[direction] = {'clf': final, 'thr': thr, 'val': met, 'n_iter': n_iter}
    return models


def predict_signal(models, X_raw):
    """X_raw: 未標準化特徵矩陣 → signal(+1 看漲 / -1 看跌 / 0)。"""
    X = np.clip(models['scaler'].transform(X_raw.astype(np.float32)), -5, 5)
    if models['ae'] is not None:
        with torch.no_grad():
            X = models['ae'].encode(torch.FloatTensor(X)).numpy()
    signal = np.zeros(len(X), dtype=np.float32)
    for direction, v in (('bull', 1.0), ('bear', -1.0)):
        p = models[direction]['clf'].predict_proba(X)[:, 1]
        mask = p >= models[direction]['thr']
        if direction == 'bull':
            signal[mask] = v
        else:
            signal[mask & (signal != 1.0)] = v
    return signal
