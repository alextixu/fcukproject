"""簡報 v3 新增的圖:聯發科 2025 年 6–9 月的真實高低點與波段價差(第 2 頁主視覺)。
只讀 final 的 results/outputs_2454_2025_tw200.csv(收盤為還原價、真實標籤);不跑模型。
用法: python3 figs_v3.py <final repo root> <out dir>
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from matplotlib import font_manager

ROOT, OUT = sys.argv[1:3]
for f in font_manager.findSystemFonts():
    if "wqy-zenhei" in f.lower():
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = ["WenQuanYi Zen Hei"]
plt.rcParams["axes.unicode_minus"] = False
INK, INK2, GRID, HI, LO = "#1F2A33", "#4A5661", "#E3E8EC", "#E8622C", "#2A6FD6"

d = pd.read_csv(os.path.join(ROOT, "method_kline_peak", "results", "outputs_2454_2025_tw200.csv"), encoding="utf-8-sig", parse_dates=["date"])
w = d[(d.date >= "2025-06-01") & (d.date <= "2025-09-30")].reset_index(drop=True)
fig, ax = plt.subplots(figsize=(12, 3.6))
ax.plot(w.date, w.close, color=INK2, lw=1.8, zorder=2)
pad = (w.close.max() - w.close.min()) * 0.07
for lab, col, mk, sgn in (("高點", HI, "v", 1), ("低點", LO, "^", -1)):
    p = w[w["真實標籤"] == lab]
    ax.scatter(p.date, p.close + sgn * pad, marker=mk, s=95, color=col, zorder=3, label=lab)


def swing(a, b):
    """在低點 a → 高點 b 之間畫波段價差(還原價)"""
    r = w[w.date == a].iloc[0], w[w.date == b].iloc[0]
    x = r[0].date + (r[1].date - r[0].date) / 2
    ax.annotate("", xy=(r[1].date, r[1].close), xytext=(r[0].date, r[0].close),
                arrowprops=dict(arrowstyle="-|>", color=HI, lw=2.2, shrinkA=6, shrinkB=6), zorder=4)
    ax.text(r[0].date - pd.Timedelta(days=1), r[1].close + pad * 0.2, f"+{(r[1].close / r[0].close - 1) * 100:.1f}%",
            fontsize=17, fontweight="bold", color=HI, ha="right", va="bottom")


swing("2025-06-30", "2025-07-11")
swing("2025-09-02", "2025-09-16")
ax.set_ylim(w.close.min() - pad * 2.2, w.close.max() + pad * 2.6)
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%-m 月"))
ax.tick_params(labelsize=13, colors=INK2)
ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.set_yticks([])
ax.legend(loc="upper left", frameon=False, fontsize=13, ncol=2, handletextpad=0.3)
fig.savefig(os.path.join(OUT, "f_swing.png"), dpi=200, bbox_inches="tight", facecolor="white")
print("f_swing.png", len(w), "days")
