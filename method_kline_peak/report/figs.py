import json, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
D = json.load(open(sys.argv[1], encoding="utf-8"))
INK, INK2, MUTED, KNOWN, BAND = "#13202A", "#47545F", "#7A8691", "#EEF2F5", "#E2E8ED"
HI, LO = "#EB6834", "#2A78D6"
LBL = {-1: "窗口不完整", 0: "非極值", 1: "低點", 2: "高點"}

def window(ax, p, i, title=None, sub=None, compact=False):
    a, b = i - 5, i + 5
    lo = min(p["l"][a:b + 1]); hi = max(p["h"][a:b + 1]); pad = (hi - lo) * 0.12; lo -= pad; hi += pad
    ax.add_patch(Rectangle((-0.5, lo), 6, hi - lo, color=KNOWN, zorder=0))
    ax.add_patch(Rectangle((4.5, lo), 1, hi - lo, facecolor=BAND, edgecolor=INK, lw=1, zorder=0.5))
    col = HI if p["y"][i] == 2 else LO if p["y"][i] == 1 else INK2
    ax.axhline(p["c"][i], color=MUTED, ls="--", lw=0.9, zorder=1)
    for k in range(a, b + 1):
        x = k - a; o, h, l, c = p["o"][k], p["h"][k], p["l"][k], p["c"][k]
        e = col if k == i else INK2; w = 2 if k == i else 1.1
        ax.plot([x, x], [l, h], color=e, lw=w, zorder=2)
        ax.add_patch(Rectangle((x - 0.3, min(o, c)), 0.6, max(abs(c - o), (hi - lo) * 0.004),
                               facecolor="white" if c >= o else e, edgecolor=e, lw=w, zorder=3))
    ax.set_xlim(-0.7, 10.7); ax.set_ylim(lo, hi)
    ax.set_xticks(range(11)); ax.set_xticklabels([f"t{k-5:+d}" if k != 5 else "t" for k in range(11)], fontsize=8 if compact else 10, color=MUTED)
    ax.tick_params(axis="y", labelsize=8 if compact else 9, colors=MUTED); ax.tick_params(length=0)
    for s in ax.spines.values(): s.set_visible(False)
    if title: ax.set_title(title, loc="left", fontsize=11 if compact else 13, color=INK, fontweight="bold", pad=6 if compact else 10)
    if sub: ax.text(0, 1.0, sub, transform=ax.transAxes, fontsize=8.5 if compact else 10, color=INK2, va="bottom", ha="left")
    return col

stocks = D["stocks"]
def median_pick(cond):
    rows = [(s, i) for s in stocks for i in range(5, len(s["test"]["d"]) - 5)
            if s["test"]["r5"][i] is not None and cond(s["test"], i)]
    vals = sorted(s["test"]["r5"][i] for s, i in rows)
    med = vals[len(vals) // 2]
    return min(rows, key=lambda x: abs(x[0]["test"]["r5"][x[1]] - med)), med, len(rows)

def find(cond, key):
    best = None
    for s in stocks:
        p = s["test"]
        for i in range(5, len(p["d"]) - 5):
            if p["r5"][i] is None or not cond(p, i): continue
            k = key(p, i)
            if best is None or k > best[0]: best = (k, s, i)
    return best[1], best[2]

def rng_window(p, i):
    a, b = i - 5, i + 5
    return (max(p["h"][a:b+1]) - min(p["l"][a:b+1])) / p["c"][i]

# 1) 標註用的單一窗口:台積電判對的高點中,窗口振幅最大的一個
s, i = find(lambda p, i: p["y"][i] == 2 and p["pred"][i] == 2 and s_is(p), lambda p, i: rng_window(p, i)) if False else (None, None)
# 標註用的窗口:漲上去、再跌下來的典型轉折(∧ 形),模型也判對
ANN = ("2382.TW", "2024-11-08")
s = next(x for x in stocks if x["ticker"] == ANN[0]); p = s["test"]; i = p["d"].index(ANN[1])
assert p["y"][i] == 2 and p["pred"][i] == 2
fig, ax = plt.subplots(figsize=(7.2, 3.9), dpi=200)
window(ax, p, i)
top = ax.get_ylim()[1]; ty = p["c"][i] + (top - p["c"][i]) * 0.45
ax.annotate(f"t 日收盤 {p['c'][i]:.0f} = 11 天最高 → 高點", xy=(4.75, p["c"][i]), xytext=(-0.4, ty), ha="left", va="center",
            fontsize=10.5, color=HI, fontweight="bold", arrowprops=dict(arrowstyle="->", color=HI, lw=1.2, connectionstyle="arc3,rad=-0.15"))
y0 = ax.get_ylim()[0]
ax.text(2.5, ax.get_ylim()[0], "t 日收盤時看得到(t-5 ~ t)", ha="center", va="bottom", fontsize=9.5, color=INK2)
ax.text(8, ax.get_ylim()[0], "未來 5 天:只用來貼標籤", ha="center", va="bottom", fontsize=9.5, color=INK2)
ax.set_title(f"{s['ticker'][:4]} {s['name']}  {p['d'][i]}(測試期)", loc="left", fontsize=11, color=INK)
fig.tight_layout(); fig.savefig("window_annotated.png", transparent=False, facecolor="white"); plt.close(fig)
print("annotated", s["ticker"], p["d"][i])

# 2) 四類例子
picks = [
    ("判對的高點", lambda p, i: p["y"][i] == 2 and p["pred"][i] == 2, lambda p, i: -p["r5"][i]),
    ("判對的低點", lambda p, i: p["y"][i] == 1 and p["pred"][i] == 1, lambda p, i: p["r5"][i]),
    ("正確刪掉的假候選", lambda p, i: p["cand"][i] == 2 and p["y"][i] == 0 and p["pred"][i] == 0, lambda p, i: p["r5"][i]),
    ("誤報:判高點但之後又創新高", lambda p, i: p["pred"][i] == 2 and p["y"][i] == 0, lambda p, i: p["r5"][i]),
]
fig, axes = plt.subplots(2, 2, figsize=(11, 6.2), dpi=200)
for ax, (name, cond, key) in zip(axes.ravel(), picks):
    (s, i), med, n = median_pick(cond); p = s["test"]
    print(name, n, "個,5 日報酬中位數", round(med, 2), "→", s["ticker"], p["d"][i])
    window(ax, p, i, title=name, compact=True)
    ax.text(0.99, 1.02, f"{s['ticker'][:4]} {s['name']} {p['d'][i]} · 之後 5 天 {p['r5'][i]:+.1f}%", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8.5, color=INK2)
fig.tight_layout(h_pad=2.2, w_pad=2.5); fig.savefig("examples.png", facecolor="white"); plt.close(fig)
print("examples ok")
