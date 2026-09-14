"""使用者切法(2026-09-14):10 天視窗,第 8 天 = 起漲日(前 7 天 + 起漲日 + 後 2 天),AE 只用「之後續漲」的視窗訓練。
起漲日 d:當日報酬 > k0 × σ20(前一日),且是最近 5 天第一個這樣的日子(避免同一波重複取樣)。
決策日 = d+2 收盤(視窗最後一天);標籤 = d+2 → d+7 再漲 > k × σ20 × √5。
訓練 2016 ~ 2025(快取無 2015;最後 10% 交易日當 AE 早停與 nu 選擇用的驗證),測試 2026-01 ~ 09-11。
用法:python breakout_window10.py [--k0 2] [--k-label 2] [--before 7 --after 2]  → results/breakout_window10_k0<k0>_lab<k>.json
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
from train_ae_ocsvm import train_ae, recon, prf, top_frac  # noqa: E402

RES = os.path.join(HERE, "results")
H = 5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k0", type=float, default=2.0, help="起漲日:單日漲 > k0 σ20")
    ap.add_argument("--k-label", type=float, default=2.0)
    ap.add_argument("--before", type=int, default=7)
    ap.add_argument("--after", type=int, default=2)
    ap.add_argument("--z", type=int, default=8)
    ap.add_argument("--train-end", default="2025-12-31")
    ap.add_argument("--min-lots", type=float, default=2000, help="5 日均量門檻(張);0 = 不篩")
    a = ap.parse_args()
    _d.TICKER_SETS["all"] = list(dict.fromkeys(_d.TICKER_SETS["tw500"] + _d.TICKER_SETS["elec_all"]))
    D = _d.load_pool("all", "2016-01-01", "2026-09-11")
    B, A_ = a.before, a.after
    rows = []
    for tk, df in D.items():
        C, V = df["close"], df["volume"]
        r1 = C.pct_change()
        s20 = r1.rolling(20, min_periods=15).std().shift(1)
        liq = V.rolling(5, min_periods=5).mean() / 1000
        jump = r1 > a.k0 * s20
        first = jump & ~jump.shift(1, fill_value=False).rolling(5, min_periods=1).max().astype(bool)
        d_idx = np.where((first & (liq >= a.min_lots)).values)[0]
        if len(d_idx) == 0:
            continue
        v60 = V.rolling(60, min_periods=30).mean()
        # 視窗以決策日 e = d + after 的收盤為基準
        e_idx = d_idx + A_
        e_idx = e_idx[e_idx < len(df)]
        Ce = C.iloc[e_idx].values
        cols = {"s20": s20.iloc[d_idx[: len(e_idx)]].values, "jump": r1.iloc[d_idx[: len(e_idx)]].values,
                "r_h5": (C.shift(-H).iloc[e_idx].values / Ce - 1), "post2": Ce / C.iloc[d_idx[: len(e_idx)]].values - 1}
        for k in range(B + A_ + 1):        # k = 0 決策日 … k = before+after 視窗第一天
            for nm in ("open", "high", "low", "close"):
                cols[f"w_{nm[0]}{k}"] = df[nm].shift(k).iloc[e_idx].values / Ce - 1
            cols[f"w_v{k}"] = (np.log1p(V.shift(k)) - np.log1p(v60)).iloc[e_idx].values
        x = pd.DataFrame(cols, index=pd.MultiIndex.from_arrays([df.index[e_idx], [tk] * len(e_idx)], names=["date", "ticker"]))
        rows.append(x)
    A = pd.concat(rows).dropna().sort_index()
    A["y"] = (A["r_h5"] > a.k_label * A["s20"] * np.sqrt(H)).astype(int)
    feat = [c for c in A.columns if c.startswith("w_")]
    dates = A.index.get_level_values("date")
    trall = A[dates <= pd.Timestamp(a.train_end)]
    te = A[dates > pd.Timestamp(a.train_end)]
    ud = np.array(sorted(trall.index.get_level_values("date").unique()))
    cut = ud[int(len(ud) * 0.9)]
    tr = trall[trall.index.get_level_values("date") < cut]
    va = trall[trall.index.get_level_values("date") >= cut]
    sc = StandardScaler().fit(tr[feat].values)
    X = {k: np.clip(sc.transform(v[feat].values), -5, 5).astype(np.float32) for k, v in (("tr", tr), ("va", va), ("te", te))}
    y = {k: v["y"].values for k, v in (("tr", tr), ("va", va), ("te", te))}
    pos = {k: y[k] == 1 for k in y}
    out = {"k0": a.k0, "k_label": a.k_label, "before": B, "after": A_, "train_end": a.train_end, "n_feat": len(feat), "min_lots": a.min_lots,
           "n": {k: int(len(v)) for k, v in y.items()}, "n_pos": {k: int(pos[k].sum()) for k in pos}, "base": {k: float(v.mean()) for k, v in y.items()},
           "median_r_h5_test": float(te["r_h5"].median()), "median_post2": float(A["post2"].median())}
    print(f"視窗 {B}+1+{A_} 天,起漲日 = 單日漲 > {a.k0:g}σ20:train {len(tr):,}(續漲 {pos['tr'].sum():,},{out['base']['tr']*100:.1f}%)/ 早停驗證 {len(va):,}({out['base']['va']*100:.1f}%)/ test 2026 {len(te):,}(續漲 {pos['te'].sum():,},{out['base']['te']*100:.1f}%)", flush=True)
    print(f"  起漲日 → 決策日 2 天中位 {out['median_post2']*100:+.1f}%;決策日後 5 日中位(test){out['median_r_h5_test']*100:+.2f}%", flush=True)
    lr = LogisticRegression(max_iter=1000, C=0.1).fit(X["tr"], y["tr"])
    xgb = XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=3, min_child_weight=30, subsample=0.8, colsample_bytree=0.6,
                        reg_lambda=5.0, n_jobs=8, random_state=42, eval_metric="logloss", early_stopping_rounds=50)
    xgb.fit(X["tr"], y["tr"], eval_set=[(X["va"], y["va"])], verbose=False)
    for nm, m in (("logistic", lr), ("xgb", xgb)):
        p = {k: m.predict_proba(X[k])[:, 1] for k in X}
        out[nm] = {"auc": {k: float(roc_auc_score(y[k], p[k])) for k in ("va", "te")},
                   "top10": {k: prf(y[k], top_frac(p[k])) for k in ("va", "te")}, "top1": {k: prf(y[k], top_frac(p[k], 0.01)) for k in ("va", "te")}}
        print(f"  {nm:8s} AUC val {out[nm]['auc']['va']:.3f} test {out[nm]['auc']['te']:.3f} | 前10% P test {out[nm]['top10']['te']['P']:.1f}%(隨機 {out['base']['te']*100:.1f}%)| 前1% test {out[nm]['top1']['te']['P']:.1f}%", flush=True)
    pca = PCA(n_components=min(20, len(feat))).fit(X["tr"])
    nn = NearestNeighbors(n_neighbors=20).fit(pca.transform(X["tr"]))
    _, nb = nn.kneighbors(pca.transform(X["te"][pos["te"]]))
    out["knn_purity"], out["knn_base"] = float(y["tr"][nb].mean()), float(y["tr"].mean())
    print(f"  kNN 純度(test 續漲視窗的訓練鄰居){out['knn_purity']*100:.1f}%(基準 {out['knn_base']*100:.1f}%,{out['knn_purity']/out['knn_base']:.2f}x)", flush=True)
    m, ep, _ = train_ae(X["tr"][pos["tr"]], X["va"][pos["va"]], a.z, log=lambda s: None)
    E, Z = {}, {}
    for k in X:
        _, E[k], Z[k] = recon(m, X[k])
    out["ae"] = {"epochs": ep, "recon_auc": {k: float(roc_auc_score(y[k], -E[k])) for k in ("va", "te")},
                 "mse_pos": {k: float(E[k][pos[k]].mean()) for k in E}, "mse_neg": {k: float(E[k][~pos[k]].mean()) for k in E}}
    print(f"  AE(只用續漲視窗,z={a.z}){ep} 輪:test 正例 MSE {out['ae']['mse_pos']['te']:.3f} 非正例 {out['ae']['mse_neg']['te']:.3f} | 「誤差小 = 像續漲」AUC val {out['ae']['recon_auc']['va']:.3f} test {out['ae']['recon_auc']['te']:.3f}", flush=True)
    out["ocsvm"] = {}
    for nu in (0.1, 0.2, 0.5):
        oc = OneClassSVM(kernel="rbf", nu=nu, gamma="scale").fit(Z["tr"][pos["tr"]])
        Dd = {k: oc.decision_function(Z[k]) for k in ("va", "te")}
        r = {"raw": {k: prf(y[k], Dd[k] >= 0) for k in Dd}, "top10": {k: prf(y[k], top_frac(Dd[k])) for k in Dd}, "top1": {k: prf(y[k], top_frac(Dd[k], 0.01)) for k in Dd}}
        out["ocsvm"][str(nu)] = r
        print(f"  OC-SVM nu={nu}: 原判法 test 出訊號 {r['raw']['te']['sig']:.0f}% P {r['raw']['te']['P']:.1f}% R {r['raw']['te']['R']:.0f}% Acc {r['raw']['te']['Acc']:.0f}% F1 {r['raw']['te']['F1']:.1f}% | 前10% P test {r['top10']['te']['P']:.1f}% | 前1% test {r['top1']['te']['P']:.1f}%(隨機 {out['base']['te']*100:.1f}%)", flush=True)
    fp = os.path.join(RES, f"breakout_window10_k0{a.k0:g}_lab{a.k_label:g}" + (f"_lots{a.min_lots:g}" if a.min_lots != 2000 else "") + ".json")
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[SAVED]", fp)


if __name__ == "__main__":
    main()
