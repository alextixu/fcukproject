"""模型準確率對比(2021 ~ 2026,每年 walk-forward:train ≤ Y-2、val Y-1、只看 Y 年內的預測)。

三個模型:
  v3 模型  = x{YY}-tw50-h5-cs  full_permpos(預測 5 日後報酬是否贏過同池中位數,tw50)
  h1 不篩  = vf{YY}-tw200-h1-base    full(預測隔天漲跌,tw200,全部樣本)
  h1 量增  = vf{YY}-tw200-h1-spike12 full(同上,只用「當天量 ≥ 1.2 × 20 日均量」的樣本訓練與測試)
輸出三組指標:
  A. 各自題目的準確率:基準線(全猜同一邊)、準確率、AUC、最有把握 10% 的準確率
  B. 同一把尺(tw50 同一批股票日):AUC 對「隔天漲跌」與對「5 日贏過半數」
  C. 選股能力(各模型實際交易的股池):每日排序相關 IC(對隔天、5 日報酬)、前 3 名 5 日超額報酬
用法: python compare_vf_acc.py [--pool electronics]  → results/vf_compare_acc.json / vf_compare_acc_<pool>.json
(pool ≠ tw200 時,B 與「h1不篩@tw50」改在「該池 ∩ tw50」的股票上比)
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
EXP = P.XGB_EXP
YEARS = range(2021, 2027)


def load(tag, col):
    x = pd.read_parquet(os.path.join(EXP, f"{tag}_testpred.parquet"))
    return x.rename(columns={col: "p"})[["p", "r_h1", "r_h5"]]


def models(y, pool):
    yy = str(y)[2:]
    return {"v3模型": load(f"x{yy}-tw50-h5-cs", "p_full_permpos"),
            "h1不篩": load(f"vf{yy}-{pool}-h1-base", "p_full"),
            "h1量增": load(f"vf{yy}-{pool}-h1-spike12", "p_full")}


def in_year(x, y):
    return x[x.index.get_level_values("date").year == y]


def own_metrics(x, kind):
    x = x.dropna(subset=["r_h1" if kind == "bin" else "r_h5"])
    if kind == "bin":
        yv = (x["r_h1"] > 0).astype(int).values
    else:
        med = x["r_h5"].groupby(level="date").transform("median")
        yv = (x["r_h5"] > med).astype(int).values
    p = x["p"].values
    yhat = (p >= 0.5).astype(int)
    sel = np.argsort(-np.abs(p - 0.5))[:max(int(len(p) * 0.1), 1)]
    return {"n": len(yv), "floor": max(yv.mean(), 1 - yv.mean()) * 100, "acc": (yhat == yv).mean() * 100,
            "auc": roc_auc_score(yv, p) * 100, "acc10": (yhat[sel] == yv[sel]).mean() * 100,
            "up10": yhat[sel].mean() * 100}


def common_auc(x):
    """同一批 tw50 股票日上,對兩個題目的 AUC(5 日題目的中位數在 tw50 內算)。"""
    a = x.dropna(subset=["r_h1"])
    b = x.dropna(subset=["r_h5"])
    med = b["r_h5"].groupby(level="date").transform("median")
    return {"auc_h1": roc_auc_score((a["r_h1"] > 0).astype(int), a["p"]) * 100,
            "auc_cs5": roc_auc_score((b["r_h5"] > med).astype(int), b["p"]) * 100}


def pick_metrics(x, pool_ret):
    """x: 模型在交易股池的預測;pool_ret: 同股池全部股票的 r_h1 / r_h5(算當天等權平均)。"""
    ic1, ic5, ex5, ex1 = [], [], [], []
    m5 = pool_ret["r_h5"].groupby(level="date").mean()
    m1 = pool_ret["r_h1"].groupby(level="date").mean()
    for d, g in x.groupby(level="date"):
        if len(g) >= 5:
            g1 = g.dropna(subset=["r_h1"])
            if len(g1) >= 5:
                ic1.append(spearmanr(g1["p"], g1["r_h1"])[0])
            g5 = g.dropna(subset=["r_h5"])
            if len(g5) >= 5:
                ic5.append(spearmanr(g5["p"], g5["r_h5"])[0])
        top = g.nlargest(3, "p")
        if top["r_h5"].notna().all() and d in m5.index:
            ex5.append((top["r_h5"].mean() - m5[d]) * 100)
        if top["r_h1"].notna().all() and d in m1.index:
            ex1.append((top["r_h1"].mean() - m1[d]) * 100)
    t = lambda v: float(np.mean(v) / np.std(v, ddof=1) * np.sqrt(len(v))) if len(v) > 2 else float("nan")
    return {"ic1": float(np.nanmean(ic1)), "ic1_t": t(ic1), "ic5": float(np.nanmean(ic5)), "ic5_t": t(ic5),
            "top3_ex1": float(np.mean(ex1)), "top3_ex5": float(np.mean(ex5)), "top3_ex5_t": t(ex5), "days": len(ex5)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="tw200")
    pool = ap.parse_args().pool
    out = {}
    for y in YEARS:
        M = {k: in_year(v, y) for k, v in models(y, pool).items()}
        tw50 = set(M["v3模型"].index.get_level_values("ticker"))
        is50 = lambda x: x[x.index.get_level_values("ticker").isin(tw50)]
        rec = {"A": {"v3模型": own_metrics(M["v3模型"], "cs"), "h1不篩": own_metrics(M["h1不篩"], "bin"), "h1量增": own_metrics(M["h1量增"], "bin")},
               "B": {"v3模型": common_auc(is50(M["v3模型"]) if pool == "tw200" else M["v3模型"][M["v3模型"].index.get_level_values("ticker").isin(set(M["h1不篩"].index.get_level_values("ticker")))]), "h1不篩": common_auc(is50(M["h1不篩"]))},
               "C": {"v3模型@tw50": pick_metrics(M["v3模型"], M["v3模型"]),
                     "h1不篩@tw50": pick_metrics(is50(M["h1不篩"]), is50(M["h1不篩"])),
                     f"h1不篩@{pool}": pick_metrics(M["h1不篩"], M["h1不篩"]),
                     f"h1量增@{pool}": pick_metrics(M["h1量增"], M["h1不篩"])}}
        out[y] = rec
        a, b, c = rec["A"], rec["B"], rec["C"]
        print(f"\n===== {y} =====")
        for k, v in a.items():
            print(f"  A {k:6s} n {v['n']:6d} 基準 {v['floor']:5.2f} 準確 {v['acc']:5.2f} ({v['acc'] - v['floor']:+5.2f}) AUC {v['auc']:5.2f} 前10% {v['acc10']:5.2f} ({v['acc10'] - v['floor']:+5.2f},猜漲 {v['up10']:4.1f}%)")
        for k, v in b.items():
            print(f"  B {k:6s} tw50 AUC 隔天漲跌 {v['auc_h1']:5.2f}  5日贏半數 {v['auc_cs5']:5.2f}")
        for k, v in c.items():
            print(f"  C {k:12s} IC1 {v['ic1']:+.4f} (t {v['ic1_t']:+5.2f})  IC5 {v['ic5']:+.4f} (t {v['ic5_t']:+5.2f})  前3名超額 隔天 {v['top3_ex1']:+.3f}%  5日 {v['top3_ex5']:+.3f}% (t {v['top3_ex5_t']:+5.2f})")
    fp = os.path.join(P.RESULTS, "vf_compare_acc.json" if pool == "tw200" else f"vf_compare_acc_{pool}.json")
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[SAVED]", fp)


if __name__ == "__main__":
    main()
