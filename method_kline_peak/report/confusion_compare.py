"""2024 測試期的混淆矩陣:規則、主軸、Stacking(拿掉規則)各版本並排(種子 42)。

上排:有規則的資訊(規則本身、主軸、Stacking + 位置特徵)
下排:拿掉規則(老師的版本:只用兩個 OC-SVM 的分數,換不同元學習器)
資料:results/main_test2024.json(主軸)、results/stacking_2024.json(規則與 Stacking)
用法: python method_kline_peak/report/confusion_compare.py
輸出: results/confusion_2024_stacking.png
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(HERE, "results")
KEY = "confusion_rows_true_cols_pred(漲,不漲不跌,跌)"
LABELS = ["低點", "非極值", "高點"]
CMAP = LinearSegmentedColormap.from_list("blue", ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#104281"])
INK, MUTED, HI = "#1f1f1d", "#5f5e5a", "#d65a26"
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False


def load():
    main = json.load(open(os.path.join(RES, "main_test2024.json"), encoding="utf-8"))["results"]["測試 2024"]["seed0_main"]
    st = json.load(open(os.path.join(RES, "stacking_2024.json"), encoding="utf-8"))
    run = lambda k: st["runs"][k]["42"][KEY]
    return [
        ("規則(不用訓練)", st["rule"][KEY]),
        ("主軸:規則 + 兩個 OC-SVM", main[KEY]),
        ("Stacking:分數 + 位置特徵 → 邏輯迴歸 L1", run("score+pos|lr-l1")),
        ("Stacking:分數 → 邏輯迴歸 L2(老師的版本)", run("score|lr")),
        ("Stacking:分數 → 邏輯迴歸 L1", run("score|lr-l1")),
        ("Stacking:分數 + 重建誤差 → 多項式 2 次", run("score+recon|lr-poly2")),
    ]


def metrics(cm):
    cm = np.asarray(cm, dtype=float)
    rec, prec = np.diag(cm) / cm.sum(1), np.diag(cm) / np.maximum(cm.sum(0), 1)
    f1 = np.where(rec + prec > 0, 2 * rec * prec / np.maximum(rec + prec, 1e-12), 0)
    return f1.mean(), rec, prec


def panel(ax, title, cm):
    cm = np.asarray(cm)
    pct = cm / cm.sum(axis=1, keepdims=True)
    ax.imshow(pct, cmap=CMAP, vmin=0, vmax=1)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{cm[i, j]:,}\n{pct[i, j]:.1%}", ha="center", va="center", fontsize=10,
                    color="white" if pct[i, j] > 0.55 else INK)
    for i, j in ((0, 2), (2, 0)):                                   # 高低點判反的兩格
        if cm[i, j]:
            ax.add_patch(plt.Rectangle((j - 0.48, i - 0.48), 0.96, 0.96, fill=False, ec=HI, lw=2))
    mf1, rec, prec = metrics(cm)
    ax.set_title(f"{title}\nmacro-F1 {mf1:.2%}", fontsize=11, color=INK, loc="left", pad=8)
    ax.text(0, 1.0, "", transform=ax.transAxes)
    ax.set_xlabel(f"找到 高 {rec[2]:.1%} / 低 {rec[0]:.1%}  ·  命中 高 {prec[2]:.1%} / 低 {prec[0]:.1%}", fontsize=9.5, color=MUTED, labelpad=8)
    ax.set_xticks(range(3)); ax.set_xticklabels([f"判{x}" for x in LABELS], fontsize=10, color=INK)
    ax.set_yticks(range(3)); ax.set_yticklabels([f"真{x}" for x in LABELS], fontsize=10, color=INK)
    ax.xaxis.set_ticks_position("top")
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)


def main():
    items = load()
    fig, axes = plt.subplots(2, 3, figsize=(15, 10.4), dpi=170)
    for ax, (title, cm) in zip(axes.ravel(), items):
        panel(ax, title, cm)
    fig.text(0.01, 0.73, "有規則的資訊", rotation=90, va="center", fontsize=13, color=INK, fontweight="bold")
    fig.text(0.01, 0.29, "拿掉規則", rotation=90, va="center", fontsize=13, color=INK, fontweight="bold")
    fig.suptitle("2024 測試期混淆矩陣(12,098 個股票日,種子 42;顏色 = 每列比例)", fontsize=14, color=INK, x=0.03, ha="left", y=0.995)
    fig.text(0.03, 0.005, "列 = 真實標籤、欄 = 判斷;橘框 = 高低點判反。訓練 2020–2023;Stacking 的基底層用 2020–2022、元學習器用 2023。",
             fontsize=10, color=MUTED)
    fig.tight_layout(rect=(0.025, 0.02, 1, 0.97), h_pad=3.0, w_pad=2.5)
    out = os.path.join(RES, "confusion_2024_stacking.png")
    fig.savefig(out, facecolor="white")
    print(out)


if __name__ == "__main__":
    main()
