"""測試期的混淆矩陣:規則、主軸、Stacking(拿掉規則)各版本並排(種子 42)。

上排:有規則的資訊(規則本身、主軸、Stacking + 位置特徵)
下排:拿掉規則(老師的版本:只用兩個 OC-SVM 的分數)
  2024:資料 results/main_test2024.json、results/stacking_2024.json
  2025:資料 results/stacking_2025_A2020-2022_B2023-2024.json(含主軸對照)、results/stacking_2025_A2020-2023_B2024-2024.json
--methods:三個方法並排(列 = 2024、2025;欄 = 規則、主軸、Stacking 邏輯迴歸、Stacking 門檻),訓練都是前 4 年
  資料 results/stacking_2024.json、results/stacking_2025_A2021-2023_B2024-2024.json
用法: python method_kline_peak/report/confusion_compare.py [--year 2024 | 2025] [--methods]
輸出: results/confusion_<年>_stacking.png;--methods → results/confusion_methods_2024_2025.png
"""
import argparse
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


def _json(name):
    return json.load(open(os.path.join(RES, name), encoding="utf-8"))


def load_2024():
    main = _json("main_test2024.json")["results"]["測試 2024"]["seed0_main"]
    st = _json("stacking_2024.json")
    run = lambda k: st["runs"][k]["42"][KEY]
    panels = [
        ("規則(不用訓練)", st["rule"][KEY]),
        ("主軸:規則 + 兩個 OC-SVM", main[KEY]),
        ("Stacking:分數 + 位置特徵 → 邏輯迴歸 L1", run("score+pos|lr-l1")),
        ("Stacking:分數 → 邏輯迴歸 L2(老師的版本)", run("score|lr")),
        ("Stacking:分數 → 邏輯迴歸 L1", run("score|lr-l1")),
        ("Stacking:分數 + 重建誤差 → 多項式 2 次", run("score+recon|lr-poly2")),
    ]
    return panels, 12098, "訓練 2020–2023;Stacking 的基底層用 2020–2022、元學習器用 2023。"


def load_2025():
    b2 = _json("stacking_2025_A2020-2022_B2023-2024.json")
    b1 = _json("stacking_2025_A2020-2023_B2024-2024.json")
    run = lambda st, k: st["runs"][k]["42"][KEY]
    panels = [
        ("規則(不用訓練)", b2["rule"][KEY]),
        ("主軸:規則 + 兩個 OC-SVM(訓練 2020–2024)", b2["mainline"]["42"][KEY]),
        ("Stacking:分數 + 位置特徵 → 梯度提升樹(B 2023–24)", run(b2, "score+pos|hgb")),
        ("Stacking:分數 → 邏輯迴歸(老師的版本,B 2023–24)", run(b2, "score|lr")),
        ("Stacking:分數 → 邏輯迴歸(B 只有 2024)", run(b1, "score|lr")),
        ("Stacking:分數 → SVM(B 2023–24)", run(b2, "score|svm")),
    ]
    return panels, 12089, "Stacking:基底層 A 2020–2022、元學習器 B 2023–2024;對照組 A 2020–2023、B 2024。"


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


def methods_figure():
    files = {2024: "stacking_2024.json", 2025: "stacking_2025_A2021-2023_B2024-2024.json"}
    train = {2024: ("2020–2023", "A 2020–2022、B 2023"), 2025: ("2021–2024", "A 2021–2023、B 2024")}
    fig, axes = plt.subplots(2, 4, figsize=(21, 10.6), dpi=160)
    for r, (year, f) in enumerate(files.items()):
        st = _json(f)
        run = lambda k: st["runs"][k]["42"][KEY]
        items = [("規則(不用訓練)", st["rule"][KEY]),
                 (f"① 主軸(訓練 {train[year][0]})", st["mainline"]["42"][KEY]),
                 (f"② Stacking 邏輯迴歸({train[year][1]})", run("score|lr")),
                 (f"③ Stacking 門檻({train[year][1]})", run("score|threshold"))]
        for ax, (title, cm) in zip(axes[r], items):
            panel(ax, title, cm)
        fig.text(0.005, 0.74 - r * 0.47, f"測試 {year}", rotation=90, va="center", fontsize=14, color=INK, fontweight="bold")
    fig.suptitle("三個方法的混淆矩陣(種子 42;每個方法都用前 4 年訓練;顏色 = 每列比例)", fontsize=15, color=INK, x=0.02, ha="left", y=0.995)
    fig.text(0.02, 0.004, "列 = 真實標籤、欄 = 判斷;橘框 = 高低點判反。測試 2024 共 12,098 天、2025 共 12,089 天。", fontsize=10.5, color=MUTED)
    fig.tight_layout(rect=(0.015, 0.02, 1, 0.97), h_pad=3.0, w_pad=2.2)
    out = os.path.join(RES, "confusion_methods_2024_2025.png")
    fig.savefig(out, facecolor="white")
    print(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024, choices=[2024, 2025])
    ap.add_argument("--methods", action="store_true")
    a = ap.parse_args()
    if a.methods:
        return methods_figure()
    year = a.year
    items, n_days, note = {2024: load_2024, 2025: load_2025}[year]()
    fig, axes = plt.subplots(2, 3, figsize=(15, 10.4), dpi=170)
    for ax, (title, cm) in zip(axes.ravel(), items):
        panel(ax, title, cm)
    fig.text(0.01, 0.73, "有規則的資訊", rotation=90, va="center", fontsize=13, color=INK, fontweight="bold")
    fig.text(0.01, 0.29, "拿掉規則", rotation=90, va="center", fontsize=13, color=INK, fontweight="bold")
    fig.suptitle(f"{year} 測試期混淆矩陣({n_days:,} 個股票日,種子 42;顏色 = 每列比例)", fontsize=14, color=INK, x=0.03, ha="left", y=0.995)
    fig.text(0.03, 0.005, f"列 = 真實標籤、欄 = 判斷;橘框 = 高低點判反。{note}", fontsize=10, color=MUTED)
    fig.tight_layout(rect=(0.025, 0.02, 1, 0.97), h_pad=3.0, w_pad=2.5)
    out = os.path.join(RES, f"confusion_{year}_stacking.png")
    fig.savefig(out, facecolor="white")
    print(out)


if __name__ == "__main__":
    main()
