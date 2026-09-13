"""產生十分位多空簡報用圖表。"""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "figs", "decile")
D = {d["exp"]: d for d in json.load(
    open(os.path.join(ROOT, "analysis", "output", "decile_ls.json"),
         encoding="utf-8"))}

INK, ACC, NEG, GREY = "#1a1a1a", "#0078D4", "#D13438", "#9aa0a6"
# JKX (JF 2023) Table 3, I20/R20 等權,年化報酬 %
JKX = [-2, 5, 7, 9, 11, 11, 13, 14, 15, 18]


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#cccccc")
    ax.tick_params(colors="#555555", labelsize=11)
    ax.grid(axis="y", color="#eeeeee", lw=1, zorder=0)
    ax.set_axisbelow(True)


# ---------- Fig 1: JKX 單調 vs 我們亂跳 ----------
fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
x = np.arange(1, 11)

ax = axes[0]
ax.bar(x, JKX, color=[NEG if v < 0 else ACC for v in JKX], zorder=3, width=.68)
ax.plot(x, JKX, color=INK, lw=2, marker="o", ms=5, zorder=4)
ax.set_title("JKX (Journal of Finance 2023)\n美股 CRSP・20 日圖・20 日持有・等權",
             fontsize=13, fontweight="bold", pad=12)
ax.set_xlabel("預測上漲機率的十等分位", fontsize=11)
ax.set_ylabel("年化報酬 (%)", fontsize=11)
ax.text(.03, .95, "單調 ρ = +1.00\nH-L = +21%,Sharpe 2.16", transform=ax.transAxes,
        va="top", fontsize=11.5, color=ACC, fontweight="bold")
style(ax)

v = D["sector-date-elec455"]["by_horizon"]["h1"]
ours = v["decile_ann_ret_pct"]
ax = axes[1]
ax.bar(x, ours, color=[NEG if q < 0 else GREY for q in ours], zorder=3, width=.68)
ax.plot(x, ours, color=INK, lw=2, marker="o", ms=5, zorder=4)
ax.axhline(v["bench_ann_ret_pct"], color=NEG, ls="--", lw=1.6, zorder=5)
ax.text(0.55, v["bench_ann_ret_pct"] + 1.8,
        f"等權買進持有基準 {v['bench_ann_ret_pct']:.1f}%",
        color=NEG, fontsize=10.5, va="bottom", ha="left")
ax.set_title("我們的 Chart GCN\n台股電子 455 檔・140 日窗・1 日持有・等權",
             fontsize=13, fontweight="bold", pad=12)
ax.set_xlabel("預測上漲機率的十等分位", fontsize=11)
ax.set_ylabel("年化報酬 (%)", fontsize=11)
ax.text(.03, .95, f"單調 ρ = {v['monotonic_spearman']:+.2f} (p={v['monotonic_p']})\n"
        f"H-L = {v['hl_ann_ret_pct']:+.1f}%,t = {v['hl_t_stat']:+.2f}",
        transform=ax.transAxes, va="top", fontsize=11.5, color=INK, fontweight="bold")
ax.set_ylim(0, max(ours) * 1.28)
style(ax)
for a in axes:
    a.set_xticks(x)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig1_jkx_vs_ours.png"), dpi=200,
            facecolor="white")
plt.close(fig)

# ---------- Fig 2: 24 個組合的單調性 ρ ----------
labs, rhos, ts = [], [], []
for e, d in D.items():
    for hk, vv in d["by_horizon"].items():
        labs.append(f"{e}\n{hk}")
        rhos.append(vv["monotonic_spearman"])
        ts.append(vv["hl_t_stat"])
fig, ax = plt.subplots(figsize=(13, 4.6))
xs = np.arange(len(rhos))
ax.bar(xs, rhos, color=[NEG if r < 0 else ACC for r in rhos], zorder=3, width=.7)
ax.axhline(0, color=INK, lw=1.2)
for y, s in [(0.65, "顯著門檻 ρ≈±0.65 (n=10, p<0.05)"), (-0.65, "")]:
    ax.axhline(y, color="#888", ls=":", lw=1.4)
ax.text(len(rhos) - .5, .68, "顯著門檻 ρ = ±0.65 (n=10, p<0.05)", ha="right",
        fontsize=10.5, color="#555")
ax.set_ylim(-1, 1)
ax.set_xticks(xs)
ax.set_xticklabels([l.replace("-elec_all", "").replace("sector-date-", "")
                    .replace("gridbest-", "gb-").replace("liq-date-", "liq-")
                    for l in labs], rotation=90, fontsize=7.5)
ax.set_ylabel("十分位單調性 Spearman ρ", fontsize=11)
ax.set_title("24 個組合(8 實驗 × 3 持有期)的單調性 —— 符號隨設定翻轉,無一顯著",
             fontsize=13, fontweight="bold", pad=12)
style(ax)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig2_monotonicity.png"), dpi=200, facecolor="white")
plt.close(fig)

# ---------- Fig 3: H-L vs 等權買進持有 ----------
rows = []
for e, d in D.items():
    vv = d["by_horizon"].get("h5") or list(d["by_horizon"].values())[0]
    rows.append((e, vv["hl_ann_ret_pct"], vv["bench_ann_ret_pct"]))
rows.sort(key=lambda r: -r[1])
fig, ax = plt.subplots(figsize=(12, 5))
xs = np.arange(len(rows))
ax.bar(xs - .19, [r[1] for r in rows], width=.38, color=ACC,
       label="Chart GCN 十分位多空 (H-L)", zorder=3)
ax.bar(xs + .19, [r[2] for r in rows], width=.38, color=GREY,
       label="等權買進持有(基準)", zorder=3)
ax.axhline(0, color=INK, lw=1.2)
ax.set_xticks(xs)
ax.set_xticklabels([r[0].replace("-elec_all", "").replace("sector-date-", "")
                    for r in rows], rotation=20, ha="right", fontsize=9.5)
ax.set_ylabel("年化報酬 (%)", fontsize=11)
ax.set_title("多空價差 vs 無腦買進持有(持有 5 日)—— 八組全數落後基準",
             fontsize=13, fontweight="bold", pad=12)
ax.legend(frameon=False, fontsize=11)
style(ax)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig3_hl_vs_bench.png"), dpi=200, facecolor="white")
plt.close(fig)

print("圖表已產生:")
for f in sorted(os.listdir(OUT)):
    print("  figs/decile/" + f)
print("\n=== 摘要統計 ===")
print(f"單調性 ρ: min {min(rhos):+.2f} max {max(rhos):+.2f} "
      f"| 正 {sum(1 for r in rhos if r>0)} 負 {sum(1 for r in rhos if r<0)}")
print(f"|ρ| >= 0.65 (顯著) 的組合數: {sum(1 for r in rhos if abs(r)>=0.65)} / {len(rhos)}")
print(f"H-L t 統計量: min {min(ts):+.2f} max {max(ts):+.2f} "
      f"| |t|>=2 的組合數: {sum(1 for t in ts if abs(t)>=2)} / {len(ts)}")
