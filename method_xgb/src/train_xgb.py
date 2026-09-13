"""XGBoost 訓練(early stopping on 時間序 val)。"""
import numpy as np
from xgboost import XGBClassifier

DEFAULT_PARAMS = dict(
    n_estimators=3000, learning_rate=0.03, max_depth=5, min_child_weight=50,
    subsample=0.8, colsample_bytree=0.5, reg_lambda=5.0, reg_alpha=0.0,
    tree_method="hist", eval_metric="logloss", early_stopping_rounds=100,
    n_jobs=4,
)


def fit_xgb(Xtr, ytr, Xva, yva, seed: int, params: dict = None):
    p = dict(DEFAULT_PARAMS)
    if params:
        p.update(params)
    if Xtr.shape[1] <= 4:
        p["colsample_bytree"] = 1.0
    model = XGBClassifier(random_state=seed, **p)
    model.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
    return model


def predict_p(model, X):
    return model.predict_proba(X)[:, 1]
