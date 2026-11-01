"""Stacking 基底層兩個 OC-SVM 的混淆矩陣(種子 42)。

左上 / 右上:高點、低點 OC-SVM 各自的判斷(範圍內 +1 / 範圍外 −1),依真實標籤分列:同方向的真點、非極值、反方向的真點
左下:兩個 OC-SVM 直接組合成三分類(不接第三個模型;兩個都 +1 時看分數大的)
右下:接第三個模型(多類別邏輯迴歸,只用兩個分數 = 老師的版本)
切分:2024 → A 2020–2022、B 2023;2025 → A 2020–2022、B 2023–2024(起點同為 2020)
用法: python method_kline_peak/report/ocsvm_confusion.py [--year 2024 | 2025]
輸出: results/ocsvm_confusion_<年>.png
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import stacking as S  # noqa: E402
from feasibility import START, END, load_pool  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402
from confusion import summarize  # noqa: E402
from paper_aeocsvm import NAMES  # noqa: E402
from confusion_compare import CMAP, INK, MUTED, KEY  # noqa: E402

plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False
LABELS = ["低點", "非極值", "高點"]


def binary_table(y, inside, cls):
    me, other = ("高", "低") if cls == DOWN else ("低", "高")
    groups = [(f"真{me}點", y == cls), ("非極值", y == FLAT), (f"真{other}點(反方向)", y == (UP if cls == DOWN else DOWN))]
    rows = [[int((inside & g).sum()), int((~inside & g).sum())] for _, g in groups]
    return [n for n, _ in groups], np.array(rows)


def draw(ax, cm, rows, cols, title, sub):
    pct = cm / cm.sum(axis=1, keepdims=True)
    ax.imshow(pct, cmap=CMAP, vmin=0, vmax=1, aspect="auto")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, f"{cm[i, j]:,}\n{pct[i, j]:.1%}", ha="center", va="center", fontsize=10.5,
                    color="white" if pct[i, j] > 0.55 else INK)
    ax.set_title(title, fontsize=12, color=INK, loc="left", pad=8)
    ax.set_xlabel(sub, fontsize=9.5, color=MUTED, labelpad=8)
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, fontsize=10, color=INK)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows, fontsize=10, color=INK)
    ax.xaxis.set_ticks_position("top")
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)


def three_class(ax, y, pred, title):
    r = summarize(y, pred, NAMES)
    cm = np.array(r[KEY])
    sub = (f"macro-F1 {r['macro_f1']:.2%} · 找到 高 {r['recall']['高點']:.1%} / 低 {r['recall']['低點']:.1%}"
           f" · 命中 高 {r['precision']['高點']:.1%} / 低 {r['precision']['低點']:.1%}")
    draw(ax, cm, [f"真{x}" for x in LABELS], [f"判{x}" for x in LABELS], title, sub)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024, choices=[2024, 2025])
    year = ap.parse_args().year
    panel, fc = ML.build_panel(load_pool(ML.POOL, START, END), 6, [])
    d = WF.year_split(panel, year, year - 2020)
    A, B = S.split_base_meta(d["train"], year - 2023)
    C = d["test"]
    y = C["y"].to_numpy()
    base = S.BaseScorers(42).fit(A, fc)
    FB, FC = base.transform(B), base.transform(C)

    fig, axes = plt.subplots(2, 2, figsize=(14, 11), dpi=170, gridspec_kw={"height_ratios": [3, 3]})
    inside = {}
    for ax, cls, col, name in ((axes[0, 0], DOWN, "s_high", "高點"), (axes[0, 1], UP, "s_low", "低點")):
        s = FC[col].to_numpy()
        inside[cls] = s >= 0
        rows, cm = binary_table(y, inside[cls], cls)
        tp, n_in = cm[0, 0], inside[cls].sum()
        from sklearn.metrics import roc_auc_score
        sub = f"判範圍內 {n_in:,} 天 · 找到率 {tp / cm[0].sum():.1%} · 命中率 {tp / n_in:.1%} · AUC {roc_auc_score(y == cls, s):.3f}"
        draw(ax, cm, rows, ["範圍內(+1)", "範圍外(-1)"], f"{name} OC-SVM(只學過真{name})", sub)
    hi, lo = inside[DOWN], inside[UP]
    pred = np.full(len(y), FLAT)
    pred[hi & ~lo], pred[lo & ~hi] = DOWN, UP
    both = hi & lo
    pred[both] = np.where(FC["s_high"].to_numpy()[both] >= FC["s_low"].to_numpy()[both], DOWN, UP)
    three_class(axes[1, 0], y, pred, "兩個 OC-SVM 直接組合(不接第三個模型)")
    meta_pred, _ = S.MetaLearner("lr", "score").fit(FB, B["y"].to_numpy()).predict(FC)
    three_class(axes[1, 1], y, meta_pred, "接第三個模型:邏輯迴歸(老師的版本)")

    yA, yB = (A.date.dt.year.min(), A.date.dt.year.max()), (B.date.dt.year.min(), B.date.dt.year.max())
    fig.suptitle(f"Stacking 的兩個 OC-SVM:{year} 測試期({len(C):,} 個股票日,種子 42;顏色 = 每列比例)",
                 fontsize=14, color=INK, x=0.02, ha="left", y=0.995)
    span = lambda a, b: f"{a}" if a == b else f"{a}–{b}"
    fig.text(0.02, 0.005, f"基底層 A {span(*yA)}、第三個模型 B {span(*yB)};沒有規則,OC-SVM 對每一天都給分數。",
             fontsize=10, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97), h_pad=3.2, w_pad=3.0)
    out = os.path.join(ML.OUT, f"ocsvm_confusion_{year}.png")
    fig.savefig(out, facecolor="white")
    print(out)


if __name__ == "__main__":
    main()
