"""一檔股票一整年的混淆矩陣,直接讀 stock_outputs.py 存下的每日 csv(不重新訓練;2026-11-03 使用者要求)。

列 = 真實標籤(csv 的「真實標籤」,原本的標籤)、欄 = 「主軸 判斷」「Stacking 邏輯迴歸 判斷」,順序 低點 / 非極值 / 高點;
畫法同 confusion_2024_2026.py(confusion_compare.panel:個數 + 列百分比,面板下方找到率 / 命中率,標題列 macro-F1)。
用法: python method_kline_peak/report/confusion_stock.py results/outputs_8046_2024_34_amp6.csv --model "34 檔模型、訓練門檻 6%"
輸出: results/confusion_<代號>_<年>_<後綴>.png / .json(後綴 = csv 檔名 outputs_<代號>_<年> 之後的部分)
"""
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mainline as ML  # noqa: E402
import confusion_compare as CC  # noqa: E402
from export_windows import ticker_names  # noqa: E402

METHODS = [("① 主軸", "主軸 判斷"), ("② Stacking 邏輯迴歸", "Stacking 邏輯迴歸 判斷")]


def matrix(y, p):
    idx = {k: i for i, k in enumerate(CC.LABELS)}
    cm = np.zeros((3, 3), dtype=int)
    for a, b in zip(y, p):
        cm[idx[a], idx[b]] += 1
    return cm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--model", required=True, help="標題裡的模型說明,例:34 檔模型、訓練門檻 6%")
    a = ap.parse_args()
    df = pd.read_csv(a.csv)
    stem = os.path.splitext(os.path.basename(a.csv))[0]           # outputs_8046_2024_34_amp6
    _, code, year, *rest = stem.split("_")
    tag = "_".join(rest)
    nm = ticker_names().get(f"{code}.TW", code)
    res = {"csv": os.path.basename(a.csv), "n_days": len(df), "labels": CC.LABELS, "methods": {}}
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 6.6), dpi=150)
    for ax, (title, col) in zip(axes, METHODS):
        cm = matrix(df["真實標籤"], df[col])
        mf1, rec, prec = CC.metrics(cm)
        res["methods"][title] = {"confusion_rows_true_cols_pred(低點,非極值,高點)": cm.tolist(), "macro_f1_pct": round(mf1 * 100, 2),
                                 "recall_pct": {k: round(rec[i] * 100, 1) for i, k in enumerate(CC.LABELS)},
                                 "precision_pct": {k: round(prec[i] * 100, 1) for i, k in enumerate(CC.LABELS)}}
        CC.panel(ax, title, cm)
    fig.suptitle(f"{code} {nm} {year} 混淆矩陣({a.model},種子 42)\n對答案用原本的標籤;顏色 = 每列比例;測試 {len(df)} 天",
                 fontsize=14, color=CC.INK, x=0.02, ha="left", y=0.99, linespacing=1.4)
    fig.text(0.02, 0.01, "列 = 真實標籤、欄 = 判斷;橘框 = 高低點判反。", fontsize=10, color=CC.MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 0.88), w_pad=3)
    out = os.path.join(ML.OUT, f"confusion_{code}_{year}" + (f"_{tag}" if tag else ""))
    fig.savefig(out + ".png", facecolor="white")
    with open(out + ".json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for t, v in res["methods"].items():
        print(t, v)
    print(out + ".png")


if __name__ == "__main__":
    main()
