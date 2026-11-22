"""專題發表簡報與海報的圖(只用 final 分支的結果檔;不訓練、不重跑模型)。
用法: python3 figs_final.py <final 分支的 repo 根目錄> <輸出目錄> [只用規則的結果 json]
"""
import csv
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.patches import Rectangle, FancyBboxPatch

ROOT, OUT = sys.argv[1], sys.argv[2]
RULE = sys.argv[3] if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
RES = os.path.join(ROOT, "method_kline_peak", "results")
os.makedirs(OUT, exist_ok=True)
for f in font_manager.findSystemFonts():
    if "wqy-zenhei" in f.lower():
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = ["WenQuanYi Zen Hei"]
plt.rcParams["axes.unicode_minus"] = False

HI, LO, INK, INK2, MUTED, GRID, NEU = "#E8622C", "#2A6FD6", "#1F2A33", "#4A5661", "#8A96A1", "#E3E8EC", "#A9B3BC"


def save(fig, name, transparent=False):
    fig.savefig(os.path.join(OUT, name), dpi=250, bbox_inches="tight", pad_inches=0.08,
                facecolor="none" if transparent else "white", transparent=transparent)
    plt.close(fig)


def clean_ax(ax):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, colors=INK2)


# ───────── 數字 ─────────
conf = json.load(open(os.path.join(RES, "confusion_2024_2026_tw200.json"), encoding="utf-8"))
YEARS = ["2024", "2025", "2026"]
KEY = "confusion_rows_true_cols_pred(漲,不漲不跌,跌)"          # 列 = 真實(低點, 非極值, 高點);欄 = 判斷
cms = {y: np.array(conf[y]["主軸"][KEY]) for y in YEARS}
tot = sum(cms.values())
N = int(tot.sum())
share = tot.sum(1) / N                                     # 低點、非極值、高點的比例
low_rec = tot[0, 0] / tot[0].sum(); high_rec = tot[2, 2] / tot[2].sum()
low_prec = tot[0, 0] / tot[:, 0].sum(); high_prec = tot[2, 2] / tot[:, 2].sum()
both_rec = (tot[0, 0] + tot[2, 2]) / (tot[0].sum() + tot[2].sum())
both_prec = (tot[0, 0] + tot[2, 2]) / (tot[:, 0].sum() + tot[:, 2].sum())
rand = (tot[0].sum() + tot[2].sum()) / 2 / N               # 隨便挑一天剛好是低(高)點的機率(兩類平均)
num = {
    "N": N, "share_low": share[0], "share_non": share[1], "share_high": share[2],
    "low_rec": low_rec, "high_rec": high_rec, "low_prec": low_prec, "high_prec": high_prec,
    "both_rec": both_rec, "both_prec": both_prec, "random": rand, "ratio_vs_random": both_prec / rand,
    "reversed": int(tot[0, 2] + tot[2, 0]),
    "majority_acc": {y: conf[y]["主軸"]["majority_acc"] for y in YEARS},
    "yearly": {y: {"macro_f1": conf[y]["主軸"]["macro_f1"], "n": int(cms[y].sum()),
                   "low_rec": conf[y]["主軸"]["recall"]["低點"], "high_rec": conf[y]["主軸"]["recall"]["高點"],
                   "low_prec": conf[y]["主軸"]["precision"]["低點"], "high_prec": conf[y]["主軸"]["precision"]["高點"],
                   "reversed": int(cms[y][0, 2] + cms[y][2, 0])} for y in YEARS},
}
bt = json.load(open(os.path.join(RES, "backtest_strategies_2024_2025.json"), encoding="utf-8"))
rets = [r["total_return_net_pct"] for r in bt["ranking"]]
num["backtest"] = {"n": len(rets), "all_negative": all(r < 0 for r in rets), "best": max(rets), "worst": min(rets),
                   "etf0050": bt["baselines"]["0050 買進持有"]["扣成本"]["合計"]["total_return_pct"],
                   "cost": bt["cost_round_trip_pct"], "period": bt["period"]}
ps = json.load(open(os.path.join(RES, "per_stock_mainline_2024_2026.json"), encoding="utf-8"))
num["mtk"] = ps["每檔"]["2025"]["2454.TW"]
if RULE:
    num["rule"] = json.load(open(RULE, encoding="utf-8"))
json.dump(num, open(os.path.join(OUT, "numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)

# ───────── 1. 三類比例 ─────────
fig, ax = plt.subplots(figsize=(10, 1.9))
x = 0
for lab, v, col in (("低點", share[0], LO), ("非極值", share[1], NEU), ("高點", share[2], HI)):
    ax.barh(0, v, left=x, color=col, height=0.62, edgecolor="white", lw=2)
    ax.text(x + v / 2, 0, f"{lab}\n{v * 100:.1f}%", ha="center", va="center", color="white", fontsize=15 if v > 0.2 else 12,
            fontweight="bold", linespacing=1.15)
    x += v
ax.set_xlim(0, 1); ax.set_ylim(-0.45, 0.45); ax.axis("off")
save(fig, "f_ratio.png")

# ───────── 2. 混淆矩陣(三年) ─────────
NAMES = ["低點", "非極值", "高點"]
fig, axs = plt.subplots(1, 3, figsize=(12.5, 4.3))
for ax, y in zip(axs, YEARS):
    m = cms[y]; rp = m / m.sum(1, keepdims=True)
    ax.imshow(rp, cmap="Blues", vmin=0, vmax=1)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{m[i, j]:,}\n{rp[i, j] * 100:.1f}%", ha="center", va="center", fontsize=10.5,
                    color="white" if rp[i, j] > 0.55 else INK)
    ax.set_xticks(range(3)); ax.set_xticklabels(["判" + n for n in NAMES], fontsize=11)
    ax.set_yticks(range(3)); ax.set_yticklabels(["真" + n for n in NAMES], fontsize=11)
    ax.xaxis.tick_top()
    ax.set_title({"2024": "2024", "2025": "2025", "2026": "2026(1–9 月)"}[y], fontsize=14, color=INK, pad=30, fontweight="bold")
    for i, j in ((0, 2), (2, 0)):                      # 判反的兩格
        ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, ec=HI, lw=2.2))
    clean_ax(ax)
fig.tight_layout(w_pad=2.5)
save(fig, "f_conf.png")

# 三年合計混淆矩陣(單一,字放大:圖以原尺寸放上 A1 時格內數字約 26pt)
fig, ax = plt.subplots(figsize=(6.6, 5.6))
rp = tot / tot.sum(1, keepdims=True)
ax.imshow(rp, cmap="Blues", vmin=0, vmax=1)
for i in range(3):
    for j in range(3):
        ax.text(j, i, f"{tot[i, j]:,}\n{rp[i, j] * 100:.1f}%", ha="center", va="center", fontsize=26, linespacing=1.15,
                color="white" if rp[i, j] > 0.55 else INK)
ax.set_xticks(range(3)); ax.set_xticklabels(["判" + n for n in NAMES], fontsize=24)
ax.set_yticks(range(3)); ax.set_yticklabels(["真" + n for n in NAMES], fontsize=24)
ax.xaxis.tick_top()
for i, j in ((0, 2), (2, 0)):
    ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, ec=HI, lw=4))
clean_ax(ax)
save(fig, "f_conf_total.png")

# ───────── 3. 比較:隨機猜 / 只用規則 / 本系統(三年合計,由 baseline 檔逐年數字加總) ─────────
def pooled(years, src):
    t = {"days": 0, "lo_t": 0, "lo_p": 0, "lo_c": 0, "hi_t": 0, "hi_p": 0, "hi_c": 0}
    for y in YEARS:
        r = years[y][src]
        t["days"] += r["天數"]
        for k, cls in (("lo", "低點"), ("hi", "高點")):
            t[k + "_t"] += r[cls]["真"]; t[k + "_p"] += r[cls]["判"]; t[k + "_c"] += r[cls]["對"]
    f1 = lambda p, r_: 2 * p * r_ / (p + r_) if p + r_ else 0
    non_t = t["days"] - t["lo_t"] - t["hi_t"]; non_p = t["days"] - t["lo_p"] - t["hi_p"]
    non_c = non_t - ((t["lo_p"] - t["lo_c"]) + (t["hi_p"] - t["hi_c"]))          # 判反 = 0,錯誤都來自非極值
    out = {"low_rec": t["lo_c"] / t["lo_t"], "high_rec": t["hi_c"] / t["hi_t"], "low_prec": t["lo_c"] / t["lo_p"],
           "high_prec": t["hi_c"] / t["hi_p"], "both_rec": (t["lo_c"] + t["hi_c"]) / (t["lo_t"] + t["hi_t"]),
           "both_prec": (t["lo_c"] + t["hi_c"]) / (t["lo_p"] + t["hi_p"]), "signal_days": t["lo_p"] + t["hi_p"], "days": t["days"]}
    out["macro_f1"] = (f1(out["low_prec"], out["low_rec"]) + f1(out["high_prec"], out["high_rec"]) + f1(non_c / non_p, non_c / non_t)) / 3
    return out


if RULE:
    bl = json.load(open(RULE, encoding="utf-8"))["years"]
    rule, mine = pooled(bl, "規則"), pooled(bl, "主軸")
    num["rule"] = rule; num["mine_from_baseline"] = mine
    num["rule_filtered_share"] = 1 - rule["signal_days"] / rule["days"]          # 規則判為非極值(不是候選)的比例
    num["signal_days_fewer"] = 1 - mine["signal_days"] / rule["signal_days"]
    json.dump(num, open(os.path.join(OUT, "numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)

fig, axs = plt.subplots(1, 2, figsize=(10, 4.2))
labs = ["隨機猜", "只用規則", "本系統"]; cols = [NEU, "#7C9CC8", INK]
for ax, (title, vals) in zip(axs, (("找到率", [rand * 100, num["rule"]["both_rec"] * 100 if RULE else None, both_rec * 100]),
                                    ("命中率", [rand * 100, num["rule"]["both_prec"] * 100 if RULE else None, both_prec * 100]))):
    top_ = 118 if title == "找到率" else 38
    for k, (l, v, c) in enumerate(zip(labs, vals, cols)):
        if v is None:
            ax.add_patch(Rectangle((k - 0.32, 0), 0.64, top_ * 0.5, fill=False, ls="--", ec=MUTED, lw=1.6))
            ax.text(k, top_ * 0.25, "待補", ha="center", va="center", fontsize=15, color=MUTED)
        else:
            ax.bar(k, v, width=0.64, color=c)
            ax.text(k, v + top_ * 0.02, f"{v:.1f}%", ha="center", va="bottom", fontsize=16, fontweight="bold", color=INK)
    ax.set_xticks(range(3)); ax.set_xticklabels(labs, fontsize=14, color=INK)
    ax.set_ylim(0, top_); ax.set_yticks([]); ax.set_title(title, fontsize=16, color=INK, fontweight="bold")
    clean_ax(ax); ax.spines["bottom"].set_visible(True); ax.spines["bottom"].set_color(GRID)
fig.tight_layout(w_pad=3)
save(fig, "f_compare.png")

# ───────── 4. 聯發科 2025(乾淨版) ─────────
rows = list(csv.DictReader(open(os.path.join(RES, "outputs_2454_2025_tw200.csv"), encoding="utf-8-sig")))
d = pd.to_datetime([r["date"] for r in rows]); c = np.array([float(r["close"]) for r in rows])
true = [r["真實標籤"] for r in rows]; pred = [r["主軸 判斷"] for r in rows]
fig, axs = plt.subplots(2, 1, figsize=(13, 6.6), sharex=True, gridspec_kw={"hspace": 0.08})
lo, hi = c.min(), c.max(); pad = (hi - lo) * 0.07
for ax, kind in zip(axs, ("true", "pred")):
    ax.plot(d, c, color="#5B6670", lw=1.3, zorder=1)
    for k in range(len(rows)):
        lab = true[k] if kind == "true" else pred[k]
        if lab not in ("高點", "低點"):
            continue
        col = HI if lab == "高點" else LO
        mk = "v" if lab == "高點" else "^"
        y = c[k] + pad * 0.55 if lab == "高點" else c[k] - pad * 0.55
        ok = kind == "true" or true[k] == lab
        ax.scatter([d[k]], [y], marker=mk, s=70, color=col if ok else "white", edgecolors=col, linewidths=1.6, zorder=3)
    ax.set_ylim(lo - pad * 1.8, hi + pad * 1.8)
    ax.grid(axis="y", color=GRID, lw=0.7); ax.set_axisbelow(True)
    clean_ax(ax)
    ax.text(0.005, 0.97, "真實高低點" if kind == "true" else "系統判斷", transform=ax.transAxes, fontsize=14, fontweight="bold",
            color=INK, va="top", ha="left", bbox=dict(fc="white", ec="none", pad=2))
axs[1].xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m 月"))
axs[1].tick_params(axis="x", labelsize=11)
from matplotlib.lines import Line2D
h = [Line2D([], [], ls="", marker="v", ms=9, color=HI, label="高點"), Line2D([], [], ls="", marker="^", ms=9, color=LO, label="低點"),
     Line2D([], [], ls="", marker="o", ms=9, color=INK2, label="實心 = 判對"),
     Line2D([], [], ls="", marker="o", ms=9, mfc="white", mec=INK2, mew=1.5, label="空心 = 判錯")]
fig.legend(handles=h, loc="lower center", ncol=4, frameon=False, fontsize=12, bbox_to_anchor=(0.5, -0.04))
save(fig, "f_2454.png")

# ───────── 5. 型態特徵:聯發科 2025-02-26 的 t-5 ~ t → 29 格 ─────────
px = pd.read_parquet(os.path.join(ROOT, "common", "cache", "yf_2026", "2454.TW.parquet"))
t = px.index.get_loc(pd.Timestamp("2025-02-26"))
w = px.iloc[t - 5:t + 1]
vb = px["volume"].rolling(10, min_periods=10).mean().iloc[t]
ct = w["close"].iloc[-1]
P = {k: np.log(w[k].to_numpy() / ct) * 100 for k in ("open", "high", "low", "close")}
V = np.log(w["volume"].to_numpy() / vb)
num["feature_day"] = {"date": "2025-02-26", "open": P["open"].round(2).tolist(), "high": P["high"].round(2).tolist(),
                      "low": P["low"].round(2).tolist(), "close": P["close"].round(2).tolist(), "vol_log": V.round(2).tolist()}
json.dump(num, open(os.path.join(OUT, "numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
days = ["t-5", "t-4", "t-3", "t-2", "t-1", "t"]
fig, ax = plt.subplots(figsize=(6.4, 4.6))
for k in range(6):
    o, h_, l, cl = P["open"][k], P["high"][k], P["low"][k], P["close"][k]
    col = "#D23B3B" if cl >= o else "#1E9E5A"              # 台股:紅漲綠跌
    ax.plot([k, k], [l, h_], color=col, lw=1.6, zorder=2)
    ax.add_patch(Rectangle((k - 0.3, min(o, cl)), 0.6, max(abs(cl - o), 0.08), facecolor=col, edgecolor=col, zorder=3))
ax.axhline(0, color=HI, ls="--", lw=1.2, zorder=1)
ax.text(-0.55, 0.12, "t 日收盤 = 0", color=HI, fontsize=11, va="bottom")
ax.set_xticks(range(6)); ax.set_xticklabels(days, fontsize=12, color=INK)
ax.set_xlim(-0.6, 5.6)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.grid(axis="y", color=GRID, lw=0.7); ax.set_axisbelow(True); clean_ax(ax)
save(fig, "f_feat_kline.png")
# 29 格
fig, ax = plt.subplots(figsize=(7.4, 4.6))
rowsn = [("開", P["open"], "%"), ("高", P["high"], "%"), ("低", P["low"], "%"), ("收", P["close"], "%"), ("量", V, "")]
for i, (rn, vals, u) in enumerate(rowsn):
    for k in range(6):
        removed = rn == "收" and k == 5
        fc = "#F1F3F5" if removed else ("#FDECE4" if rn != "量" else "#E7EEF9")
        ax.add_patch(FancyBboxPatch((k + 0.06, -i - 0.94), 0.88, 0.88, boxstyle="round,pad=0,rounding_size=0.08", fc=fc, ec="white"))
        v_ = 0.0 if abs(vals[k]) < (0.05 if u else 0.005) else vals[k]
        txt = "—" if removed else (("0.0" if v_ == 0 else f"{v_:+.1f}") if u else ("0.00" if v_ == 0 else f"{v_:+.2f}"))
        ax.text(k + 0.5, -i - 0.5, txt, ha="center", va="center", fontsize=12.5, color=MUTED if removed else INK)
    ax.text(-0.15, -i - 0.5, rn, ha="right", va="center", fontsize=14, fontweight="bold", color=INK)
for k, dname in enumerate(days):
    ax.text(k + 0.5, 0.25, dname, ha="center", va="bottom", fontsize=12, color=INK2)
ax.set_xlim(-0.8, 6.05); ax.set_ylim(-5.1, 0.8); ax.axis("off")
save(fig, "f_feat_grid.png")

# ───────── 6. 30 種策略 vs 0050 ─────────
fig, ax = plt.subplots(figsize=(10, 4.4))
rs = sorted(rets, reverse=True)
ax.bar(range(len(rs)), rs, color="#1E9E5A", width=0.75)
ax.bar(len(rs) + 1.2, num["backtest"]["etf0050"], color="#D23B3B", width=1.4)
ax.axhline(0, color=INK2, lw=1)
ax.text(len(rs) / 2, min(rs) - 8, "30 種只做多策略(扣成本)", ha="center", va="top", fontsize=13, color=INK)
ax.text(len(rs) + 1.2, num["backtest"]["etf0050"] + 3, f"+{num['backtest']['etf0050']:.2f}%", ha="center", va="bottom", fontsize=14,
        fontweight="bold", color="#D23B3B")
ax.text(len(rs) + 1.2, -8, "0050", ha="center", va="top", fontsize=13, color=INK)
ax.annotate(f"最好 {max(rs):.2f}%", xy=(0, max(rs)), xytext=(0, 28), ha="left", va="bottom", fontsize=13, color="#1E9E5A",
            fontweight="bold", arrowprops=dict(arrowstyle="-", color="#1E9E5A", lw=1))
ax.set_ylim(min(rs) - 22, num["backtest"]["etf0050"] + 22); ax.set_xticks([])
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.grid(axis="y", color=GRID, lw=0.7); ax.set_axisbelow(True); clean_ax(ax)
save(fig, "f_backtest.png")

# ───────── 7. K 線插圖(裝飾) ─────────
rng = np.random.default_rng(7)
cl = 100 + np.cumsum(rng.normal(0, 1.6, 26)); cl[6] = cl[:12].max() + 3; cl[16] = cl[10:22].min() - 3
op = np.r_[cl[0] - 1, cl[:-1]]
fig, ax = plt.subplots(figsize=(6, 3))
for k in range(len(cl)):
    col = "#D23B3B" if cl[k] >= op[k] else "#1E9E5A"
    hi_, lo_ = max(cl[k], op[k]) + abs(rng.normal(0, 0.8)), min(cl[k], op[k]) - abs(rng.normal(0, 0.8))
    ax.plot([k, k], [lo_, hi_], color=col, lw=1.4)
    ax.add_patch(Rectangle((k - 0.32, min(cl[k], op[k])), 0.64, max(abs(cl[k] - op[k]), 0.3), fc=col, ec=col))
ax.scatter([6], [max(cl[6], op[6]) + 3.2], marker="v", s=160, color=HI)
ax.scatter([16], [min(cl[16], op[16]) - 3.2], marker="^", s=160, color=LO)
ax.axis("off")
save(fig, "f_illus.png", transparent=True)
print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in num.items() if k not in ("yearly", "mtk", "backtest", "feature_day", "majority_acc")}, ensure_ascii=False))
