"""把第 3 頁的 29 個特徵畫成圖:上 = 6 根 K 線(相對 t 日收盤的 %),下 = 每天的量 ÷ 10 日均量。"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False
INK, INK2, MUTED, GRID, KNOWN, HI = "#13202A", "#47545F", "#7A8691", "#D9E0E6", "#EEF2F5", "#EB6834"
days = ["t-5", "t-4", "t-3", "t-2", "t-1", "t"]
O = [-11.6, -6.6, -5.3, -2.7, -1.5, 0.0]
H = [-6.3, -4.1, -2.4, -1.1, 0.3, 1.5]
L = [-11.7, -6.7, -5.6, -3.0, -2.4, -0.5]
C = [-7.0, -4.4, -3.0, -2.3, -0.8, 0.0]
V = [0.92, 1.00, 1.08, 1.29, 1.21, 1.35]
fmt = lambda v: f"{v:+.1f}%" if v else "0.0%"
X = [k * 1.4 for k in range(6)]          # 拉開間距,收盤標籤放得下

fig, (ax, av) = plt.subplots(2, 1, figsize=(9, 6.2), dpi=200, sharex=True, gridspec_kw={"height_ratios": [2.4, 1], "hspace": 0.12})
# 上:K 線
ax.axhline(0, color=HI, ls="--", lw=1.1, zorder=1)
ax.text(-1.85, 0.35, "t 日收盤 = 0%(所有價格的基準)", color=HI, fontsize=9.5, va="bottom", ha="left")
for k in range(6):
    col = HI if k == 5 else INK2
    ax.plot([X[k], X[k]], [L[k], H[k]], color=col, lw=1.6 if k == 5 else 1.2, zorder=2)
    body = max(abs(C[k] - O[k]), 0.12)
    ax.add_patch(Rectangle((X[k] - 0.28, min(O[k], C[k])), 0.56, body, facecolor="white" if C[k] >= O[k] else col,
                           edgecolor=col, lw=1.8 if k == 5 else 1.2, zorder=3))
    if k < 5:
        ax.text(X[k] + 0.33, C[k], f"收 {fmt(C[k])}", fontsize=8.5, color=INK, va="center", ha="left")
# 第一根標出開高低收 4 個數字
k = 0
for v, name, dy in ((H[k], "高", 0), (O[k], "開", 0.35), (L[k], "低", -0.35)):
    ax.text(X[k] - 0.36, v + dy, f"{name} {fmt(v)}", fontsize=9, color=INK2, va="center", ha="right")
ax.text(X[5] + 0.36, -1.0, "收盤恆為 0,\n不當特徵(拿掉)", fontsize=9, color=MUTED, va="top", ha="left")
ax.text(X[5] + 0.36, 1.5, f"高 {fmt(H[5])}", fontsize=9, color=INK2, va="center", ha="left")
ax.set_ylim(-13.5, 3.2); ax.set_xlim(-1.9, X[5] + 1.9)
ax.set_ylabel("相對 t 日收盤(%)", color=INK2, fontsize=10)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.grid(axis="y", color=GRID, lw=0.6); ax.set_axisbelow(True)
ax.set_title("模型看到的 29 個數字:廣達 2024-11-08 的 t-5 ~ t", loc="left", fontsize=13, color=INK, fontweight="bold", pad=10)
# 下:量
av.axhline(1, color=MUTED, ls="--", lw=1)
av.text(X[5] + 0.4, 1.04, "1.0× =\n10 日均量", color=MUTED, fontsize=9, va="bottom", ha="left")
for k in range(6):
    av.add_patch(Rectangle((X[k] - 0.28, 0), 0.56, V[k], facecolor=HI if k == 5 else "#9AA5AF", edgecolor="none", zorder=2))
    av.text(X[k], V[k] + 0.05, f"{V[k]:.2f}×", ha="center", va="bottom", fontsize=9, color=INK)
av.set_ylim(0, 1.65); av.set_ylabel("量 ÷ 10 日均量", color=INK2, fontsize=10)
av.grid(axis="y", color=GRID, lw=0.6); av.set_axisbelow(True)
av.set_xticks(X); av.set_xticklabels(days, fontsize=10.5, color=INK)
for a in (ax, av):
    a.tick_params(length=0, colors=MUTED, labelsize=9)
    for s in a.spines.values(): s.set_visible(False)
av.tick_params(axis="x", colors=INK)
fig.text(0.125, 0.015, "每天 5 個數字(開、高、低、收、量)× 6 天 = 30,扣掉恆為 0 的 t 日收盤 = 29 個;價格的圖案只看形狀,不看股價高低。",
         fontsize=9, color=INK2)
fig.savefig("features_chart.png", facecolor="white", bbox_inches="tight", pad_inches=0.15)
print("ok")
