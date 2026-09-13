"""階段一過關檢查(計畫 §2.4):資料裡「大漲 vs 其他」到底分不分得開,AE / OC-SVM 之前先用最簡單的方法看。

對每個池、每套輸入(A / B / C):
  1. 可分性:logistic 回歸(標準化、截 ±5)與 XGB(上限參考),時間切分 train ≤ 2022 / val 2023–2024 / test 2025–2026-09,
     報 AUC、Precision@10%(最有把握的 10% 裡真的大漲的比例)、對照隨機(正例比例)。
  2. 成群檢查:在標準化 + PCA 30 維空間,對驗證段正例找訓練段最近的 20 個鄰居,鄰居裡正例的比例(kNN 純度)
     vs 訓練段正例比例;純度 ≈ 比例 → 正例沒有自成一群,One-Class 不會有用。
過關門檻(計畫):logistic 驗證 AUC ≥ 0.60、kNN 純度明顯高於正例比例(≥ 1.5 倍)。
用法:python check_separability.py --pools tw50,tw200,elec_all  → results/bigmove_stage1.json
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

DATA = os.path.join(P.CACHE, "bigmove")
RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)
TRAIN_END, VAL_END = "2022-12-31", "2024-12-31"
H = 5


def split(df):
    d = df.index.get_level_values("date")
    ud = np.array(sorted(d.unique()))
    tr_d = ud[ud <= pd.Timestamp(TRAIN_END)][:-H]
    va_d = ud[(ud > pd.Timestamp(TRAIN_END)) & (ud <= pd.Timestamp(VAL_END))][:-H]
    te_d = ud[ud > pd.Timestamp(VAL_END)]
    return df[d.isin(tr_d)], df[d.isin(va_d)], df[d.isin(te_d)]


def prec_at(y, p, frac=0.10):
    top = np.argsort(-p)[: max(int(len(p) * frac), 1)]
    return float(y[top].mean())


def evaluate(pool, df, cols, name):
    tr, va, te = split(df.dropna(subset=cols))
    sc = StandardScaler().fit(tr[cols].values)
    X = {k: np.clip(sc.transform(v[cols].values), -5, 5).astype(np.float32) for k, v in (("tr", tr), ("va", va), ("te", te))}
    y = {k: v["y"].values.astype(int) for k, v in (("tr", tr), ("va", va), ("te", te))}
    rec = {"n_cols": len(cols), "n": {k: int(len(v)) for k, v in y.items()}, "base": {k: float(v.mean()) for k, v in y.items()}}
    t0 = time.time()
    lr = LogisticRegression(max_iter=500, C=0.1).fit(X["tr"], y["tr"])
    for k in ("va", "te"):
        p = lr.predict_proba(X[k])[:, 1]
        rec[f"lr_auc_{k}"] = float(roc_auc_score(y[k], p)); rec[f"lr_p10_{k}"] = prec_at(y[k], p)
    from xgboost import XGBClassifier
    xgb = XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=4, min_child_weight=50, subsample=0.8, colsample_bytree=0.6,
                        reg_lambda=5.0, n_jobs=4, random_state=42, eval_metric="logloss", early_stopping_rounds=50)
    xgb.fit(X["tr"], y["tr"], eval_set=[(X["va"], y["va"])], verbose=False)
    for k in ("va", "te"):
        p = xgb.predict_proba(X[k])[:, 1]
        rec[f"xgb_auc_{k}"] = float(roc_auc_score(y[k], p)); rec[f"xgb_p10_{k}"] = prec_at(y[k], p)
    rec["xgb_iters"] = int(xgb.best_iteration)
    # 成群檢查:PCA 30 維,驗證段正例的 20 個訓練鄰居
    rng = np.random.default_rng(0)
    idx_tr = rng.choice(len(X["tr"]), min(len(X["tr"]), 150000), replace=False)
    pca = PCA(n_components=min(30, len(cols))).fit(X["tr"][idx_tr])
    Ztr = pca.transform(X["tr"][idx_tr]); ytr = y["tr"][idx_tr]
    nn = NearestNeighbors(n_neighbors=20).fit(Ztr)
    pos_va = np.where(y["va"] == 1)[0]; pos_va = rng.choice(pos_va, min(len(pos_va), 3000), replace=False)
    neg_va = np.where(y["va"] == 0)[0]; neg_va = rng.choice(neg_va, min(len(neg_va), 3000), replace=False)
    Zva = pca.transform(X["va"])
    _, nb_pos = nn.kneighbors(Zva[pos_va]); _, nb_neg = nn.kneighbors(Zva[neg_va])
    rec["knn_purity_pos"] = float(ytr[nb_pos].mean())     # 驗證段正例的鄰居裡,訓練正例比例
    rec["knn_purity_neg"] = float(ytr[nb_neg].mean())     # 驗證段非正例的鄰居裡,訓練正例比例(對照)
    rec["knn_base"] = float(ytr.mean())
    rec["sec"] = round(time.time() - t0)
    print(f"  {pool:8s} {name:2s} 欄 {len(cols):3d} | 正例 val {rec['base']['va']*100:5.2f}% test {rec['base']['te']*100:5.2f}% | "
          f"logistic AUC val {rec['lr_auc_va']:.3f} test {rec['lr_auc_te']:.3f} P@10% val {rec['lr_p10_va']*100:5.2f}% test {rec['lr_p10_te']*100:5.2f}% | "
          f"XGB AUC val {rec['xgb_auc_va']:.3f} test {rec['xgb_auc_te']:.3f} P@10% val {rec['xgb_p10_va']*100:5.2f}% test {rec['xgb_p10_te']*100:5.2f}% ({rec['xgb_iters']} 棵) | "
          f"kNN 純度 正例鄰居 {rec['knn_purity_pos']*100:5.2f}% 非正例鄰居 {rec['knn_purity_neg']*100:5.2f}% 基準 {rec['knn_base']*100:5.2f}% ({rec['sec']}s)", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pools", default="tw50,tw200,elec_all")
    ap.add_argument("--sets", default="A,B,C")
    a = ap.parse_args()
    fp = os.path.join(RES, "bigmove_stage1.json")
    out = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else {}
    for pool in a.pools.split(","):
        df = pd.read_parquet(os.path.join(DATA, f"samples_{pool}.parquet"))
        meta = json.load(open(os.path.join(DATA, f"samples_{pool}_meta.json"), encoding="utf-8"))
        print(f"\n===== {pool}:{meta['rows']:,} 列,正例 {meta['pos_rate']*100:.2f}%,標籤 {meta['label']} =====", flush=True)
        for s in a.sets.split(","):
            cols = meta["cols"].get(s) or []
            if not cols:
                print(f"  {pool} {s}: 無此輸入(跳過)"); continue
            out[f"{pool}|{s}"] = evaluate(pool, df, cols, s)
            json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[SAVED] {fp}")


if __name__ == "__main__":
    main()
