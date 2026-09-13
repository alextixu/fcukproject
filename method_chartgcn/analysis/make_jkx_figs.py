"""JKX (JF 2023) 回測結果圖:等權 vs 市值加權,以及週轉率。

數據來源:Jiang, Kelly & Xiu (2023) Table 3 / Table 4 / Table 6。
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "figs", "decile")
os.makedirs(OUT, exist_ok=True)

INK, ACC, NEG, GREY = "#1a1a1a", "#0078D4", "#D13438", "#9aa0a6"

# H-L 年化 Sharpe:(等權, 市值加權);週轉率(月, 等權)
ROWS = [
    ("週頻\nI20/R5", 6.75, 1.74, 834),
    ("月頻\nI20/R20", 2.16, 0.49, 173),
    ("季頻\nI20/R60", 0.37, 0.32, 59),
    ("月頻 動量\nMOM/R20", 0.25, 0.36, 63),
    ("月頻 週反轉\nWSTR/R20", 1.23, 0.30, 167),
]


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#cccccc")
    ax.tick_params(colors="#555555", labelsize=11)
    ax.grid(axis="y", color="#eeeeee", lw=1, zorder=0)
    ax.set_axisbelow(True)


fig, axes = plt.subplots(1, 2, figsize=(13, 5.0),
                         gridspec_kw={"width_ratios": [1.35, 1]})
x = np.arange(len(ROWS))

ax = axes[0]
ax.bar(x - .19, [r[1] for r in ROWS], width=.38, color=ACC,
       label="等權", zorder=3)
ax.bar(x + .19, [r[2] for r in ROWS], width=.38, color=GREY,
       label="市值加權", zorder=3)
for i, r in enumerate(ROWS):
    ax.text(i - .19, r[1] + .12, f"{r[1]:.2f}", ha="center", fontsize=10,
            color=ACC, fontweight="bold")
    ax.text(i + .19, r[2] + .12, f"{r[2]:.2f}", ha="center", fontsize=10,
            color="#666")
ax.axhline(1.0, color=NEG, ls=":", lw=1.5, zorder=4)
ax.text(-0.42, 1.14, "Sharpe = 1.0", color=NEG, fontsize=10,
        ha="left")
ax.set_xticks(x)
ax.set_xticklabels([r[0] for r in ROWS], fontsize=10.5)
ax.set_ylabel("H-L 年化 Sharpe", fontsize=11.5)
ax.set_title("JKX 回測:等權亮眼,市值加權掉到 0.3~1.7",
             fontsize=13, fontweight="bold", pad=12)
ax.legend(frameon=False, fontsize=11, loc="upper right")
ax.set_ylim(0, 7.6)
style(ax)

ax = axes[1]
tn = [("CNN\n週頻", 834), ("CNN\n月頻", 173), ("週反轉\n月頻", 167),
      ("動量\n月頻", 63)]
cols = [NEG, ACC, GREY, "#3aa76d"]
ax.bar(np.arange(len(tn)), [t[1] for t in tn], color=cols, zorder=3, width=.6)
for i, t in enumerate(tn):
    ax.text(i, t[1] + 18, f"{t[1]}%", ha="center", fontsize=11,
            fontweight="bold", color=cols[i])
ax.set_xticks(np.arange(len(tn)))
ax.set_xticklabels([t[0] for t in tn], fontsize=10.5)
ax.set_ylabel("月週轉率 (%)", fontsize=11.5)
ax.set_title("週轉率:CNN 月頻與週反轉相同,績效卻是兩倍",
             fontsize=13, fontweight="bold", pad=12)
ax.set_ylim(0, 980)
style(ax)

fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig4_jkx_backtest.png"), dpi=200,
            facecolor="white")
plt.close(fig)
print("已輸出 figs/decile/fig4_jkx_backtest.png")
