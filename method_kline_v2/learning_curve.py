"""學習曲線:股票池 50 → 100 → 200 → 500 → 814 檔,AE 只用大漲樣本訓練,看「AE 有沒有學到大漲的樣子」隨樣本數變不變。
每個池(輸入 C,z=16):
  AE 大漲樣本數、還原 MSE、「誤差小 = 像大漲」AUC(val / test)、潛在 logistic AUC、
  OC-SVM(nu=0.1)前 10% Precision、對照 原始 C + XGB 前 10% Precision;隨機 = 正例比例。
用法:python learning_curve.py --pools tw50,tw100,tw200,tw500,all  → results/bigmove_learning_curve.json
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
sys.path.insert(0, HERE)
from check_separability import split                      # noqa: E402
from train_ae_ocsvm import train_ae, recon, prf, top_frac  # noqa: E402
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

DATA = os.path.join(P.CACHE, "bigmove")
RES = os.path.join(HERE, "results")


def run(pool, z=16):
    t0 = time.time()
    df = pd.read_parquet(os.path.join(DATA, f"samples_{pool}.parquet"))
    meta = json.load(open(os.path.join(DATA, f"samples_{pool}_meta.json"), encoding="utf-8"))
    cols = meta["cols"]["C"]
    tr, va, te = split(df)
    del df
    med = tr[cols].median()
    sc = StandardScaler().fit(tr[cols].fillna(med).values)
    X = {k: np.clip(sc.transform(v[cols].fillna(med).values), -5, 5).astype(np.float32) for k, v in (("tr", tr), ("va", va), ("te", te))}
    y = {k: v["y"].values.astype(int) for k, v in (("tr", tr), ("va", va), ("te", te))}
    del tr, va, te
    pos = {k: y[k] == 1 for k in y}
    rec = {"n_tickers": meta["n_tickers"], "n_cols": len(cols), "n_train": int(len(y["tr"])), "n_pos_train": int(pos["tr"].sum()),
           "base": {k: float(v.mean()) for k, v in y.items()}}
    m, ep, best = train_ae(X["tr"][pos["tr"]], X["va"][pos["va"]], z, log=lambda s: None)
    E, Z = {}, {}
    for k in ("tr", "va", "te"):
        _, E[k], Z[k] = recon(m, X[k])
    rec["epochs"] = ep
    rec["mse_pos"] = {k: float(E[k][pos[k]].mean()) for k in E}
    rec["mse_neg"] = {k: float(E[k][~pos[k]].mean()) for k in E}
    rec["recon_auc"] = {k: float(roc_auc_score(y[k], -E[k])) for k in ("va", "te")}
    lr_z = LogisticRegression(max_iter=500, C=0.1).fit(Z["tr"], y["tr"])
    rec["latent_lr_auc"] = {k: float(roc_auc_score(y[k], lr_z.predict_proba(Z[k])[:, 1])) for k in ("va", "te")}
    oc = OneClassSVM(kernel="rbf", nu=0.1, gamma="scale").fit(Z["tr"][pos["tr"]])
    rec["ocsvm_top10"] = {k: prf(y[k], top_frac(oc.decision_function(Z[k]))) for k in ("va", "te")}
    rec["ocsvm_raw"] = {k: prf(y[k], oc.predict(Z[k]) == 1) for k in ("va", "te")}
    from xgboost import XGBClassifier
    xgb = XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=4, min_child_weight=50, subsample=0.8, colsample_bytree=0.6,
                        reg_lambda=5.0, n_jobs=4, random_state=42, eval_metric="logloss", early_stopping_rounds=50)
    xgb.fit(X["tr"], y["tr"], eval_set=[(X["va"], y["va"])], verbose=False)
    rec["xgb_top10"] = {k: prf(y[k], top_frac(xgb.predict_proba(X[k])[:, 1])) for k in ("va", "te")}
    rec["xgb_auc"] = {k: float(roc_auc_score(y[k], xgb.predict_proba(X[k])[:, 1])) for k in ("va", "te")}
    rec["sec"] = round(time.time() - t0)
    print(f"{pool:6s} {rec['n_tickers']:3d} 檔 | AE 大漲樣本 {rec['n_pos_train']:6,} | 正例 MSE val {rec['mse_pos']['va']:.3f} 非正例 {rec['mse_neg']['va']:.3f} | "
          f"誤差 AUC val {rec['recon_auc']['va']:.3f} test {rec['recon_auc']['te']:.3f} | 潛在 lr AUC val {rec['latent_lr_auc']['va']:.3f} test {rec['latent_lr_auc']['te']:.3f} | "
          f"OC-SVM 前10% P val {rec['ocsvm_top10']['va']['P']:.2f}% test {rec['ocsvm_top10']['te']['P']:.2f}%(隨機 {rec['base']['va']*100:.2f} / {rec['base']['te']*100:.2f}) | "
          f"XGB 前10% P val {rec['xgb_top10']['va']['P']:.2f}% test {rec['xgb_top10']['te']['P']:.2f}% AUC {rec['xgb_auc']['va']:.3f}/{rec['xgb_auc']['te']:.3f} ({rec['sec']}s)", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pools", default="tw50,tw100,tw200,tw500,all")
    a = ap.parse_args()
    fp = os.path.join(RES, "bigmove_learning_curve.json")
    out = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else {}
    for pool in a.pools.split(","):
        out[pool] = run(pool)
        json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[SAVED]", fp)


if __name__ == "__main__":
    main()
