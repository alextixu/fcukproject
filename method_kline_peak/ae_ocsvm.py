"""AE + OC-SVM(method_kline 原系統做法)套到現在的標籤:學第 1–5 天 → 第 6 天是 11 日最高(跌)/ 最低(漲)點。

與原系統相同(直接 import method_kline/kline):
  Autoencoder 結構與訓練 kline.autoencoder.train_ae(輸入 → max(16, 2×輸入) → 8 → 4 → 8 → … → 輸入,MSE,60 輪)、
  潛在維度 4、OC-SVM(rbf,nu = 0.1,gamma = scale)、標準化後截 ±5、漲方向優先、亂數種子 42
與原系統不同:
  輸入 = 第 1–5 天五根 K 的 24 維形態(learn5_trade6.RAW5),不是 1 / 2 / 3 日 K 線特徵
  樣本挑選:原系統先做歐氏距離形態搜尋(距離 ≤ 3 的相似樣本 ≥ 5 個且全部同方向才留)。
    本標籤下相似樣本中位數約 3,000 個、同類只佔約 12%,「全部同類」的型態群為 0,
    所以 AE 用該類全部訓練樣本;原系統的重要性權重改成「距離 ≤ 3 的相似樣本中同類的比例」,當 OC-SVM 的 sample_weight
  漲 / 跌各訓練一組 AE + OC-SVM,只用該類的訓練樣本
判法
  原生  漲的 OC-SVM 判在範圍內 → 漲;否則跌的 OC-SVM 判在範圍內 → 跌;其餘 → 不漲不跌(同原系統 backtest)
  前1%  兩組 OC-SVM 的 decision_function 各取前 1%(與 LightGBM 版的前 1% 判法相同)
切分:confusion.FOLD_SETS["train2020-23"](訓練 2016–2022 與 2020–2023,驗證段不用,測試都是 2025-01 ~ 2026-09)

用法: python method_kline_peak/ae_ocsvm.py --pool tw50
輸出: method_kline_peak/results/aeocsvm_<pool>_peak.json、.png
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.metrics.pairwise import euclidean_distances
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from feasibility import P, START, END, load_pool  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN, NAMES, RAW5, build_panel, split  # noqa: E402
from confusion import (FOLD_SETS, ORDER, SURFACE, INK, plt, draw,  # noqa: E402
                       selective_pred, summarize)
sys.path.insert(0, P.METHOD_KLINE)
from kline.config import DIST_THRESH, OCSVM_NU  # noqa: E402  (載入時固定 torch / numpy 種子 42)
from kline.autoencoder import train_ae  # noqa: E402

OUT = os.path.join(HERE, "results")
FOLDS = FOLD_SETS["train2020-23"]
BATCH = 500


def neighbor_purity(X, y, cls):
    """每個 cls 樣本:距離 ≤ DIST_THRESH 的其他樣本中同為 cls 的比例(原系統重要性權重的替代)。"""
    seeds = np.flatnonzero(y == cls)
    out = np.zeros(len(seeds))
    batch = max(20, min(BATCH, int(2e7 // len(X))))        # 每批距離矩陣約 2,000 萬格,大池不爆記憶體
    same = y == cls
    for i in range(0, len(seeds), batch):
        d = euclidean_distances(X[seeds[i:i + batch]], X)
        d[np.arange(len(d)), seeds[i:i + batch]] = np.inf
        near = d <= DIST_THRESH
        n = near.sum(axis=1)
        out[i:i + batch] = np.where(n > 0, (near & same).sum(axis=1) / np.maximum(n, 1), 0)
    return seeds, out


def fit_direction(X, y, cls, log):
    seeds, w = neighbor_purity(X, y, cls)
    ae = train_ae(X[seeds], X.shape[1], lambda s: None)
    ae.eval()
    with torch.no_grad():
        z = ae.encode(torch.FloatTensor(X[seeds])).numpy()
    w = np.maximum(w, 1e-3)
    oc = OneClassSVM(kernel="rbf", nu=OCSVM_NU, gamma="scale").fit(z, sample_weight=w / w.mean())
    log(f"    [{NAMES[cls]}] AE + OC-SVM:{len(seeds):,} 個樣本,相似樣本同類比例 中位 {np.median(w):.1%}")
    return ae, oc


def predict(models, X):
    inside, score = {}, {}
    for cls, (ae, oc) in models.items():
        with torch.no_grad():
            z = ae.encode(torch.FloatTensor(X)).numpy()
        inside[cls] = oc.predict(z) == 1
        score[cls] = oc.decision_function(z)
    native = np.full(len(X), FLAT)
    native[inside[DOWN]] = DOWN
    native[inside[UP]] = UP                             # 漲方向優先(同原系統)
    rank = np.zeros((len(X), 3))
    for cls in (UP, DOWN):
        rank[:, cls] = pd.Series(score[cls]).rank(pct=True).to_numpy()
    return native, rank, inside


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="tw50")
    args = ap.parse_args()
    t0 = time.time()
    plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
    panel = build_panel(load_pool(args.pool, START, END))
    panel = panel[panel["y_peak"] >= 0]

    lgb_fp = os.path.join(OUT, f"confusion_{args.pool}_peak_train2020-23.json")
    lgb = json.load(open(lgb_fp, encoding="utf-8")) if os.path.exists(lgb_fp) else {}
    out, cells = {}, []
    for fold_name, fold in FOLDS.items():
        sp = split(panel, fold)
        tr, te = sp["train"], sp["test"]
        sc = StandardScaler().fit(tr[RAW5])
        Xtr = np.clip(sc.transform(tr[RAW5]), -5, 5).astype(np.float32)
        Xte = np.clip(sc.transform(te[RAW5]), -5, 5).astype(np.float32)
        ytr, yte = tr["y_peak"].to_numpy(), te["y_peak"].to_numpy()
        print(f"== {fold_name}:train {len(tr):,} / test {len(te):,}", flush=True)
        models = {cls: fit_direction(Xtr, ytr, cls, print) for cls in (UP, DOWN)}
        native, rank, _ = predict(models, Xte)
        key = f"{fold_name}|peak"
        out[key] = {"native": summarize(yte, native), "top1pct": summarize(yte, selective_pred(rank)),
                    "native_signal_rate": {NAMES[c]: float((native == c).mean()) for c in (UP, DOWN)}}
        cells.append((fold, out[key]))
        r = out[key]
        print(f"   原生 acc {r['native']['acc']:.1%}(判漲 {r['native_signal_rate']['漲']:.1%}、判跌 {r['native_signal_rate']['跌']:.1%})"
              f"  前1% acc {r['top1pct']['acc']:.1%}  全猜不漲不跌 {r['native']['majority_acc']:.1%}"
              f"  | LightGBM 前1% 命中 漲 {lgb.get(key, {}).get('top1pct', {}).get('precision', {}).get('漲', float('nan')):.1%}"
              f" 跌 {lgb.get(key, {}).get('top1pct', {}).get('precision', {}).get('跌', float('nan')):.1%}"
              f"  ({time.time() - t0:.0f}s)", flush=True)

    fig, axes = plt.subplots(2, len(cells), figsize=(5.4 * len(cells), 12.5), facecolor=SURFACE)
    for j, (fold, r) in enumerate(cells):
        (tr_a, tr_b), (te_a, te_b) = fold["train"], fold["test"]
        head = f"訓練 {tr_a[:4]}–{tr_b[:4]} · 測試 {te_a[:7]} ~ {te_b[:7]}\n第 6 天 11 日最高 → 跌、最低 → 漲"
        draw(axes[0, j], r["native"], f"{head}\n判法:OC-SVM 判在範圍內就出訊號(原系統)")
        draw(axes[1, j], r["top1pct"], f"{head}\n判法:只有前 1% 判漲 / 跌")
    fig.suptitle(f"{args.pool.upper()}:學第 1–5 天 → 第 6 天是不是 11 日最高(跌)/ 最低(漲)點(AE + OC-SVM)",
                 fontsize=14, color=INK, x=0.01, ha="left")
    fig.subplots_adjust(left=0.09, right=0.99, top=0.9, bottom=0.09, wspace=0.4, hspace=0.62)
    png = os.path.join(OUT, f"aeocsvm_{args.pool}_peak.png")
    fig.savefig(png, dpi=110, facecolor=SURFACE)
    with open(os.path.join(OUT, f"aeocsvm_{args.pool}_peak.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"輸出 {png}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
