"""使用者假設(2026-09-14):大漲前都長得一樣,拉出之後型態才不同 → 改學「起漲點前後 3 天」的視窗。
做法:起漲點 = 過去 3 天漲幅 > k0 × σ20(起漲前)× √3 的日子 d(d-3 → d 為起漲段);輸入 = d-6 ~ d 共 7 天 OHLC(相對 d 收盤)+ 7 天量(對 60 日均量 log 比)
      + 起漲段漲幅 / 量比 + 起漲前 20 日報酬;標籤 = d → d+5 再漲 > 2σ√5(續漲)。只在起漲日上比較:
      logistic / XGB 可分性、kNN 純度、AE(只用續漲正例訓練)誤差 AUC、OC-SVM 前 10% / 前 1% Precision,對照隨機 = 續漲比例。
用法:python breakout_window.py [--k0 3] [--k-label 2]  → results/breakout_window_k0<k0>_lab<k>.json
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM
from xgboost import XGBClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
os.environ.setdefault("TW_CACHE_DIR", P.YF_2026_CACHE)
sys.path.insert(0, P.XGB_SRC)
sys.path.insert(0, HERE)
import data as _d  # noqa: E402
from check_separability import split  # noqa: E402
from train_ae_ocsvm import train_ae, recon, prf, top_frac  # noqa: E402

RES = os.path.join(HERE, "results")
W, H = 7, 5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k0", type=float, default=3.0, help="起漲門檻:3 日漲 > k0 σ20 √3")
    ap.add_argument("--k-label", type=float, default=2.0, help="續漲標籤:d→d+5 > k σ20 √5")
    ap.add_argument("--z", type=int, default=8)
    a = ap.parse_args()
    _d.TICKER_SETS["all"] = list(dict.fromkeys(_d.TICKER_SETS["tw500"] + _d.TICKER_SETS["elec_all"]))
    D = _d.load_pool("all", "2016-01-01", "2026-09-11")
    rows = []
    for tk, df in D.items():
        C, V = df["close"], df["volume"]
        s20 = C.pct_change().rolling(20, min_periods=15).std().shift(3)      # 起漲前的波動
        liq = V.rolling(5, min_periods=5).mean() / 1000
        p3 = C / C.shift(3) - 1
        surge = (p3 > a.k0 * s20 * np.sqrt(3)) & (liq >= 2000)
        if surge.sum() == 0:
            continue
        v60 = V.rolling(60, min_periods=30).mean()
        cols = {"s20": s20, "p3": p3, "v3": V.rolling(3).mean() / v60, "pre20": C.shift(3) / C.shift(23) - 1,
                "r_h5": C.shift(-H) / C - 1}
        for k in range(W):
            for nm in ("open", "high", "low", "close"):
                cols[f"w_{nm[0]}{k}"] = df[nm].shift(k) / C - 1
            cols[f"w_v{k}"] = np.log1p(V.shift(k)) - np.log1p(v60)
        x = pd.DataFrame(cols, index=df.index)[surge]
        x["ticker"] = tk
        rows.append(x)
    A = pd.concat(rows).set_index("ticker", append=True).dropna()
    A.index.names = ["date", "ticker"]
    A = A.sort_index()
    A["y"] = (A["r_h5"] > a.k_label * A["s20"] * np.sqrt(H)).astype(int)
    feat = [c for c in A.columns if c.startswith("w_")] + ["p3", "v3", "pre20"]
    tr, va, te = split(A)
    sc = StandardScaler().fit(tr[feat].values)
    X = {k: np.clip(sc.transform(v[feat].values), -5, 5).astype(np.float32) for k, v in (("tr", tr), ("va", va), ("te", te))}
    y = {k: v["y"].values for k, v in (("tr", tr), ("va", va), ("te", te))}
    pos = {k: y[k] == 1 for k in y}
    out = {"k0": a.k0, "k_label": a.k_label, "n": {k: int(len(v)) for k, v in y.items()}, "n_pos": {k: int(pos[k].sum()) for k in pos},
           "base": {k: float(v.mean()) for k, v in y.items()}, "median_r_h5": {k: float(v["r_h5"].median()) for k, v in (("tr", tr), ("va", va), ("te", te))}}
    print(f"起漲日(3 日漲 > {a.k0:g}σ√3):train {len(tr):,}(續漲 {pos['tr'].sum():,},{out['base']['tr']*100:.1f}%)/ val {len(va):,}({out['base']['va']*100:.1f}%)/ test {len(te):,}({out['base']['te']*100:.1f}%);"
          f"起漲日後 5 日中位報酬 train {out['median_r_h5']['tr']*100:+.2f}%", flush=True)
    lr = LogisticRegression(max_iter=1000, C=0.1).fit(X["tr"], y["tr"])
    xgb = XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=3, min_child_weight=30, subsample=0.8, colsample_bytree=0.6,
                        reg_lambda=5.0, n_jobs=8, random_state=42, eval_metric="logloss", early_stopping_rounds=50)
    xgb.fit(X["tr"], y["tr"], eval_set=[(X["va"], y["va"])], verbose=False)
    for nm, m in (("logistic", lr), ("xgb", xgb)):
        p = {k: m.predict_proba(X[k])[:, 1] for k in X}
        out[nm] = {"auc": {k: float(roc_auc_score(y[k], p[k])) for k in ("va", "te")},
                   "top10": {k: prf(y[k], top_frac(p[k])) for k in ("va", "te")}, "top1": {k: prf(y[k], top_frac(p[k], 0.01)) for k in ("va", "te")}}
        print(f"  {nm:8s} AUC val {out[nm]['auc']['va']:.3f} test {out[nm]['auc']['te']:.3f} | 前10% P val {out[nm]['top10']['va']['P']:.1f}% test {out[nm]['top10']['te']['P']:.1f}% | 前1% test {out[nm]['top1']['te']['P']:.1f}%(隨機 {out['base']['te']*100:.1f}%)", flush=True)
    pca = PCA(n_components=min(20, len(feat))).fit(X["tr"])
    nn = NearestNeighbors(n_neighbors=20).fit(pca.transform(X["tr"]))
    _, nb = nn.kneighbors(pca.transform(X["va"][pos["va"]]))
    out["knn_purity"], out["knn_base"] = float(y["tr"][nb].mean()), float(y["tr"].mean())
    print(f"  kNN 純度 {out['knn_purity']*100:.1f}%(基準 {out['knn_base']*100:.1f}%,{out['knn_purity']/out['knn_base']:.2f}x)", flush=True)
    m, ep, _ = train_ae(X["tr"][pos["tr"]], X["va"][pos["va"]], a.z, log=lambda s: None)
    E, Z = {}, {}
    for k in X:
        _, E[k], Z[k] = recon(m, X[k])
    out["ae"] = {"epochs": ep, "recon_auc": {k: float(roc_auc_score(y[k], -E[k])) for k in ("va", "te")},
                 "mse_pos": {k: float(E[k][pos[k]].mean()) for k in E}, "mse_neg": {k: float(E[k][~pos[k]].mean()) for k in E}}
    print(f"  AE(只用續漲正例,z={a.z}){ep} 輪:正例 MSE val {out['ae']['mse_pos']['va']:.3f} 非正例 {out['ae']['mse_neg']['va']:.3f} | 「誤差小 = 像續漲」AUC val {out['ae']['recon_auc']['va']:.3f} test {out['ae']['recon_auc']['te']:.3f}", flush=True)
    out["ocsvm"] = {}
    for nu in (0.1, 0.2, 0.5):
        oc = OneClassSVM(kernel="rbf", nu=nu, gamma="scale").fit(Z["tr"][pos["tr"]])
        Dd = {k: oc.decision_function(Z[k]) for k in ("va", "te")}
        out["ocsvm"][str(nu)] = {"raw": {k: prf(y[k], Dd[k] >= 0) for k in Dd}, "top10": {k: prf(y[k], top_frac(Dd[k])) for k in Dd}, "top1": {k: prf(y[k], top_frac(Dd[k], 0.01)) for k in Dd}}
        r = out["ocsvm"][str(nu)]
        print(f"  OC-SVM nu={nu}: 原判法 出訊號 val {r['raw']['va']['sig']:.0f}% P {r['raw']['va']['P']:.1f}% / test {r['raw']['te']['sig']:.0f}% P {r['raw']['te']['P']:.1f}% | 前10% P val {r['top10']['va']['P']:.1f}% test {r['top10']['te']['P']:.1f}% | 前1% test {r['top1']['te']['P']:.1f}%", flush=True)
    fp = os.path.join(RES, f"breakout_window_k0{a.k0:g}_lab{a.k_label:g}.json")
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[SAVED]", fp)


if __name__ == "__main__":
    main()
