"""v3 原模型 vs 量增訓練模型(tw50、5 日、贏過同池一半)準確率,逐年 2021 ~ 2026。
  A. 量增樣本上(spike 模型 testpred 的列,兩個模型都對同一批列打分):基準線、準確率、AUC、最有把握 10%
  B. 全部樣本上(spike 模型用 fullpred 打分全部):同上 + 前 3 名 5 日超額報酬
標籤中位數一律以全部 tw50 算(v3 的定義)。輸出 results/vf_v3_compare_acc.json
"""
import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
EXP = P.XGB_EXP
RES = P.RESULTS


def met(y, p):
    yhat = (p >= 0.5).astype(int)
    sel = np.argsort(-np.abs(p - 0.5))[: max(len(p) // 10, 1)]
    return {"n": int(len(y)), "floor": max(y.mean(), 1 - y.mean()) * 100, "acc": (yhat == y).mean() * 100,
            "auc": roc_auc_score(y, p) * 100, "acc10": (yhat[sel] == y[sel]).mean() * 100}


def top3(df):
    ex = []
    for d, g in df.groupby(level="date"):
        if g["r_h5"].notna().sum() >= 10:
            ex.append((g.nlargest(3, "p")["r_h5"].mean() - g["r_h5"].mean()) * 100)
    return float(np.mean(ex)), float(np.mean(ex) / np.std(ex, ddof=1) * np.sqrt(len(ex)))


def main():
    out = {}
    for y in range(2021, 2027):
        yy = str(y)[2:]
        v3 = pd.read_parquet(os.path.join(EXP, f"x{yy}-tw50-h5-cs_testpred.parquet")).rename(columns={"p_full_permpos": "p"})[["p", "r_h5"]]
        sp = pd.read_parquet(os.path.join(EXP, f"vf{yy}-tw50-h5-cs-spike12_testpred.parquet")).rename(columns={"p_full_permpos": "p"})[["p", "r_h5"]]
        spf = pd.read_parquet(os.path.join(RES, f"fullpred_vf{yy}-tw50-h5-cs-spike12_full_permpos.parquet"))
        iy = lambda x: x[x.index.get_level_values("date").year == y]
        v3, sp = iy(v3).dropna(subset=["r_h5"]), iy(sp)
        spf = iy(spf).join(v3["r_h5"], how="inner").dropna(subset=["r_h5"])
        lab = lambda x: (x["r_h5"] > x["r_h5"].groupby(level="date").transform("median")).astype(int).values
        yall = lab(v3)
        m = v3.index.isin(sp.index)
        rec = {"A_spike_rows": {"v3": met(yall[m], v3.loc[m, "p"].values), "spike": met(yall[m], sp.reindex(v3.index[m])["p"].values)},
               "B_all_rows": {"v3": met(yall, v3["p"].values), "spike": met(lab(spf), spf["p"].values)}}
        rec["B_all_rows"]["v3"]["top3_ex5"], rec["B_all_rows"]["v3"]["t"] = top3(v3)
        rec["B_all_rows"]["spike"]["top3_ex5"], rec["B_all_rows"]["spike"]["t"] = top3(spf)
        out[y] = rec
        a, b = rec["A_spike_rows"], rec["B_all_rows"]
        print(f"{y} 量增列 n={a['v3']['n']}: v3 AUC {a['v3']['auc']:.1f} acc {a['v3']['acc']:.1f} 前10% {a['v3']['acc10']:.1f} | "
              f"量增訓練 AUC {a['spike']['auc']:.1f} acc {a['spike']['acc']:.1f} 前10% {a['spike']['acc10']:.1f}  ||  "
              f"全部列 n={b['v3']['n']}: v3 AUC {b['v3']['auc']:.1f} acc {b['v3']['acc']:.1f} 前10% {b['v3']['acc10']:.1f} 前3名 {b['v3']['top3_ex5']:+.2f}% (t {b['v3']['t']:.1f}) | "
              f"量增訓練 AUC {b['spike']['auc']:.1f} acc {b['spike']['acc']:.1f} 前10% {b['spike']['acc10']:.1f} 前3名 {b['spike']['top3_ex5']:+.2f}% (t {b['spike']['t']:.1f})")
    json.dump(out, open(os.path.join(RES, "vf_v3_compare_acc.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
