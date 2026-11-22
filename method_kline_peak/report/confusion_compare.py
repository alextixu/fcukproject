"""混淆矩陣面板的畫法(confusion_2024_2026.py 用):個數 + 列百分比,面板下方找到率 / 命中率,標題列 macro-F1。"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

KEY = "confusion_rows_true_cols_pred(漲,不漲不跌,跌)"
LABELS = ["低點", "非極值", "高點"]
CMAP = LinearSegmentedColormap.from_list("blue", ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#104281"])
INK, MUTED, HI = "#1f1f1d", "#5f5e5a", "#d65a26"
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False


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


