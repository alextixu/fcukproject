"""門檻曲線:「大漲」定得越嚴,AE 只用大漲樣本訓練後,能不能認出大漲?(使用者假設:2σ 太低,大漲不夠明顯)
用 all 池(812 檔,60 萬列)重新標籤:5 日報酬 > k×σ20×√5(k = 2, 3, 4, 5)以及固定 +10% / +15% / +20%。
每個門檻:正例數、kNN 純度(成群檢查)、AE 誤差 AUC、OC-SVM 前 10% Precision、對照 XGB 前 10% Precision。
用法:python threshold_curve.py [--pool all]  → results/bigmove_threshold_curve.json
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import NearestNeighbors
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
THRS = [("2σ√5", "sigma", 2.0), ("3σ√5", "sigma", 3.0), ("4σ√5", "sigma", 4.0), ("5σ√5", "sigma", 5.0),
        ("固定+10%", "fixed", 0.10), ("固定+15%", "fixed", 0.15), ("固定+20%", "fixed", 0.20)]


def read_low_mem(fp, cols, batch=50000):
    """pyarrow 分批讀取 → float32,避免一次配置整張表(本機 commit 上限很緊)。"""
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(fp)
    blocks, idx = [], []
    for b in pf.iter_batches(batch_size=batch, columns=cols + ["date", "ticker"]):
        d = b.to_pandas()
        if "date" not in d.columns:
            d = d.reset_index()
        idx.append(pd.MultiIndex.from_arrays([pd.to_datetime(d["date"]), d["ticker"]], names=["date", "ticker"]))
        blocks.append(d[cols].to_numpy(dtype=np.float32))
        del d
    X = np.vstack(blocks); del blocks
    return pd.DataFrame(X, index=idx[0].append(idx[1:]), columns=cols)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="all")
    ap.add_argument("--z", type=int, default=16)
    a = ap.parse_args()
    meta = json.load(open(os.path.join(DATA, f"samples_{a.pool}_meta.json"), encoding="utf-8"))
    cols = meta["cols"]["C"]
    df = read_low_mem(os.path.join(DATA, f"samples_{a.pool}.parquet"), cols + ["r_h5", "sigma20", "y"])   # 分批讀、float32,省 commit
    tr, va, te = split(df)
    del df
    med = tr[cols].median()
    sc = StandardScaler().fit(tr[cols].fillna(med).values)
    X = {k: np.clip(sc.transform(v[cols].fillna(med).values), -5, 5).astype(np.float32) for k, v in (("tr", tr), ("va", va), ("te", te))}
    R = {k: v["r_h5"].values for k, v in (("tr", tr), ("va", va), ("te", te))}
    S = {k: v["sigma20"].values for k, v in (("tr", tr), ("va", va), ("te", te))}
    del tr, va, te
    rng = np.random.default_rng(0)
    idx_tr = rng.choice(len(X["tr"]), min(len(X["tr"]), 150000), replace=False)
    pca = PCA(n_components=30).fit(X["tr"][idx_tr])
    Ztr_pca = pca.transform(X["tr"][idx_tr]); Zva_pca = pca.transform(X["va"])
    nn = NearestNeighbors(n_neighbors=20).fit(Ztr_pca)
    from xgboost import XGBClassifier
    fp_out = os.path.join(RES, f"bigmove_threshold_curve_{a.pool}.json")
    out = json.load(open(fp_out, encoding="utf-8")) if os.path.exists(fp_out) else {}
    print(f"===== {a.pool}({meta['n_tickers']} 檔,C {len(cols)} 欄)train {len(X['tr']):,} / val {len(X['va']):,} / test {len(X['te']):,} =====", flush=True)
    for name, kind, v in THRS:
        if name in out and "xgb_auc" in out[name]:
            print(f"  {name:8s} 已有結果,跳過"); continue
        t0 = time.time()
        y = {k: ((R[k] > (v * S[k] * np.sqrt(5))) if kind == "sigma" else (R[k] > v)).astype(int) for k in R}
        pos = {k: y[k] == 1 for k in y}
        rec = {"n_pos": {k: int(pos[k].sum()) for k in pos}, "base": {k: float(pos[k].mean()) for k in pos}}
        if pos["tr"].sum() < 300:
            print(f"  {name:8s} 正例太少({pos['tr'].sum()}),跳過"); continue
        ytr_s = y["tr"][idx_tr]
        pv = np.where(pos["va"])[0]; pv = rng.choice(pv, min(len(pv), 3000), replace=False)
        _, nb = nn.kneighbors(Zva_pca[pv])
        rec["knn_purity"], rec["knn_base"] = float(ytr_s[nb].mean()), float(ytr_s.mean())
        m, ep, _ = train_ae(X["tr"][pos["tr"]], X["va"][pos["va"]], a.z, log=lambda s: None)
        E, Z = {}, {}
        for k in ("tr", "va", "te"):
            _, E[k], Z[k] = recon(m, X[k])
        rec["epochs"] = ep
        rec["mse_pos"] = {k: float(E[k][pos[k]].mean()) for k in E}; rec["mse_neg"] = {k: float(E[k][~pos[k]].mean()) for k in E}
        rec["recon_auc"] = {k: float(roc_auc_score(y[k], -E[k])) for k in ("va", "te")}
        oc = OneClassSVM(kernel="rbf", nu=0.1, gamma="scale").fit(Z["tr"][pos["tr"]])
        rec["ocsvm_top10"] = {k: prf(y[k], top_frac(oc.decision_function(Z[k]))) for k in ("va", "te")}
        rec["ocsvm_top1"] = {k: prf(y[k], top_frac(oc.decision_function(Z[k]), 0.01)) for k in ("va", "te")}
        del m; import gc; gc.collect()
        try:
          xgb = XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=4, min_child_weight=50, subsample=0.8, colsample_bytree=0.6,
                            reg_lambda=5.0, n_jobs=4, random_state=42, eval_metric="logloss", early_stopping_rounds=50)
          xgb.fit(X["tr"], y["tr"], eval_set=[(X["va"], y["va"])], verbose=False)
          px = {k: xgb.predict_proba(X[k])[:, 1] for k in X}
          rec["xgb_auc"] = {k: float(roc_auc_score(y[k], px[k])) for k in ("va", "te")}
          rec["xgb_top10"] = {k: prf(y[k], top_frac(px[k])) for k in ("va", "te")}
          rec["xgb_top1"] = {k: prf(y[k], top_frac(px[k], 0.01)) for k in ("va", "te")}
          del xgb, px; gc.collect()
        except Exception as e:
          print(f"    XGB 記憶體不足,略過對照:{e}"); rec["xgb_auc"] = {"va": float("nan"), "te": float("nan")}; rec["xgb_top10"] = rec["xgb_top1"] = {k: {"P": float("nan")} for k in ("va", "te")}
        rec["sec"] = round(time.time() - t0)
        out[name] = rec
        b = rec["base"]
        print(f"  {name:8s} 正例 train {rec['n_pos']['tr']:6,}({b['tr']*100:.2f}%) | kNN 純度 {rec['knn_purity']*100:.2f}%(基準 {rec['knn_base']*100:.2f}%,{rec['knn_purity']/max(rec['knn_base'],1e-9):.2f}x) | "
              f"MSE 正例 {rec['mse_pos']['va']:.3f} 非正例 {rec['mse_neg']['va']:.3f} 誤差 AUC val {rec['recon_auc']['va']:.3f} test {rec['recon_auc']['te']:.3f} | "
              f"OC-SVM 前10% P val {rec['ocsvm_top10']['va']['P']:.2f} test {rec['ocsvm_top10']['te']['P']:.2f} 前1% test {rec['ocsvm_top1']['te']['P']:.2f}(隨機 {b['va']*100:.2f}/{b['te']*100:.2f}) | "
              f"XGB AUC {rec['xgb_auc']['va']:.3f}/{rec['xgb_auc']['te']:.3f} 前10% P {rec['xgb_top10']['va']['P']:.2f}/{rec['xgb_top10']['te']['P']:.2f} 前1% test {rec['xgb_top1']['te']['P']:.2f} ({rec['sec']}s)", flush=True)
        json.dump(out, open(fp_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[SAVED]", fp_out)


if __name__ == "__main__":
    main()
