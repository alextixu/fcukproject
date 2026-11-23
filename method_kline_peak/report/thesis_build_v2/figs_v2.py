"""專題研究報告 v2:準備資料(data.json)與圖(fig/*.png)。
不跑實驗、不訓練:數字全部讀 final 分支 method_kline_peak/results/ 的 json;圖為自繪示意圖、
簡報 v2 的圖(final_build/fig,同樣只讀 final 的結果檔)與網頁截圖的裁切(不塗改)。
用法: python3 figs_v2.py <final 分支根目錄> <web-app 的 web/screenshots> <final_build/fig> <輸出目錄>
"""
import json
import os
import shutil
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Patch
from PIL import Image

ROOT, SHOTS, FFIG, OUT = sys.argv[1:5]
RES = os.path.join(ROOT, "method_kline_peak", "results")
FIG = os.path.join(OUT, "fig")
os.makedirs(FIG, exist_ok=True)

for f in font_manager.findSystemFonts():
    if "wqy-zenhei" in f.lower():
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = ["WenQuanYi Zen Hei"]
plt.rcParams["axes.unicode_minus"] = False
INK, MUTED, BLUE, ORANGE, TEAL, LINE = "#13202A", "#5B6670", "#2A78D6", "#EB6834", "#0B7A75", "#C9D2D9"


def J(name):
    with open(os.path.join(RES, name), encoding="utf-8") as fh:
        return json.load(fh)


# ───────────────────────── 資料 ─────────────────────────
CMK = "confusion_rows_true_cols_pred(漲,不漲不跌,跌)"     # 列 / 欄順序:低點、非極值、高點
conf = J("confusion_2024_2026_tw200.json")
base = J("baseline_rule_vs_mainline_2024_2026.json")
timing = J("timing_mainline.json")
bts = J("backtest_strategies_2024_2025.json")
top3 = J("backtest_long_only_tw200.json")
pst = J("per_stock_mainline_2024_2026.json")
Y = ["2024", "2025", "2026"]


def metrics(m):
    """混淆矩陣 → 找到率、命中率、F1、macro-F1(%)"""
    out = {}
    f1s = []
    for i, k in enumerate(["低點", "非極值", "高點"]):
        tp = m[i][i]
        rec = tp / sum(m[i]); prec = tp / sum(r[i] for r in m)
        f1 = 2 * prec * rec / (prec + rec)
        f1s.append(f1)
        out[k] = {"rec": rec * 100, "prec": prec * 100, "f1": f1 * 100}
    out["macro_f1"] = sum(f1s) / 3 * 100
    return out


data = {"years": {}, "total": {}}
tot = [[0] * 3 for _ in range(3)]
for y in Y:
    m = conf[y]["主軸"][CMK]
    for i in range(3):
        for j in range(3):
            tot[i][j] += m[i][j]
    mt = metrics(m)
    assert abs(mt["macro_f1"] - conf[y]["主軸"]["macro_f1"] * 100) < 1e-9
    data["years"][y] = {"cm": m, "n": sum(map(sum, m)), "labels": [sum(r) for r in m], "m": mt,
                        "reversed": m[0][2] + m[2][0], "rule": base["years"][y]["規則"], "main": base["years"][y]["主軸"],
                        "random": base["years"][y]["隨機"], "vs": base["years"][y]["主軸相對規則"]}
data["total"] = {"cm": tot, "n": sum(map(sum, tot)), "labels": [sum(r) for r in tot], "m": metrics(tot), "reversed": tot[0][2] + tot[2][0]}
# 三年合計的「只用規則」與本系統:逐年個數相加
agg = {}
for meth in ("規則", "主軸"):
    a = {"判高低合計天數": 0, "低點": {"真": 0, "判": 0, "對": 0}, "高點": {"真": 0, "判": 0, "對": 0}}
    for y in Y:
        v = base["years"][y][meth]
        a["判高低合計天數"] += v["判高低合計天數"]
        for k in ("低點", "高點"):
            for q in ("真", "判", "對"):
                a[k][q] += v[k][q]
    for k in ("低點", "高點"):
        a[k]["找到率"] = a[k]["對"] / a[k]["真"] * 100
        a[k]["命中率"] = a[k]["對"] / a[k]["判"] * 100
    a["both_rec"] = (a["低點"]["對"] + a["高點"]["對"]) / (a["低點"]["真"] + a["高點"]["真"]) * 100
    a["both_prec"] = (a["低點"]["對"] + a["高點"]["對"]) / (a["低點"]["判"] + a["高點"]["判"]) * 100
    agg[meth] = a
data["agg_rule"], data["agg_main"] = agg["規則"], agg["主軸"]
data["fewer_signals_pct"] = (1 - agg["主軸"]["判高低合計天數"] / agg["規則"]["判高低合計天數"]) * 100
# 規則候選以外直接判非極值的股票日比例
data["rule_filtered_pct"] = (1 - agg["規則"]["判高低合計天數"] / data["total"]["n"]) * 100
data["random_pct"] = (data["total"]["labels"][0] + data["total"]["labels"][2]) / 2 / data["total"]["n"] * 100
data["timing"] = timing
res = bts["results"]
net = {k: v["扣成本"]["合計"]["total_return_pct"] for k, v in res.items()}
data["bt"] = {"n": len(net), "n_negative": sum(1 for v in net.values() if v < 0), "period": bts["period"], "cost": bts["cost_round_trip_pct"],
              "ranking": bts["ranking"], "best": bts["ranking"][0], "second": bts["ranking"][1], "worst": bts["ranking"][-1],
              "best_gross": res[bts["ranking"][0]["key"]]["沒扣成本"]["合計"]["total_return_pct"],
              "second_gross": res[bts["ranking"][1]["key"]]["沒扣成本"]["合計"]["total_return_pct"],
              "worst_gross": res[bts["ranking"][-1]["key"]]["沒扣成本"]["合計"]["total_return_pct"],
              "etf0050": bts["baselines"]["0050 買進持有"]["扣成本"]["合計"]["total_return_pct"],
              "eq168": bts["baselines"]["168 檔等權買進持有"]["扣成本"]["合計"]["total_return_pct"]}
data["top3"] = {y: {k: top3["years"][y]["主軸"]["扣成本"][k] for k in ("total_return_pct", "max_dd_pct", "n_trades", "win_rate_pct")} for y in Y}
data["n_excluded"] = len(top3["excluded"])
data["mtk"] = pst["每檔"]["2025"]["2454.TW"]
data["n_stocks"] = base["n_stocks"]
json.dump(data, open(os.path.join(OUT, "data.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ───────────────────────── 自繪圖 ─────────────────────────
def box(ax, x, y, w, h, text, fc="#EEF2F5", ec=LINE, color=INK, size=11, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=color,
            fontweight="bold" if bold else "normal", linespacing=1.4)


def arrow(ax, x1, y1, x2, y2, label=None):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14, color=MUTED, lw=1.4))
    if label:
        ax.text((x1 + x2) / 2 + 0.12, (y1 + y2) / 2, label, fontsize=9.5, color=MUTED, va="center")


def save(fig, name):
    fig.savefig(os.path.join(FIG, name), dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# 圖 1.1 研究流程
fig, ax = plt.subplots(figsize=(7.2, 9.4))
ax.set_xlim(0, 10); ax.set_ylim(0, 13.2); ax.axis("off")
steps = [
    ("資料蒐集", "台股日 K 線(還原價)2016-01 ~ 2026-09"),
    ("股票池", "TW200 剔除低波動股後 168 檔"),
    ("標籤", "11 天視窗,t = 第 6 天\n高點 / 低點 / 非極值"),
    ("規則候選", "t 收盤是最近 6 天最高 / 最低才是候選\n其他日子判為非極值"),
    ("特徵與模型", "t-5 ~ t 六根 K 線 → 29 維特徵\n高點、低點各一組 AE(29 → 16)+ OC-SVM"),
    ("walk-forward 評估", "測哪一年就用前 4 年訓練(2024–2026)\n混淆矩陣、macro-F1、找到率、命中率"),
    ("比較與個案", "與隨機、只用規則比較;聯發科 2025;回測"),
    ("系統實作", "網頁系統:今日判斷、個股查詢、成績追蹤"),
]
y = 12.2
for i, (h, t) in enumerate(steps):
    hl = i in (3, 4)
    box(ax, 0.3, y - 0.55, 2.6, 1.1, h, fc=INK if hl else "#EEF2F5", color="white" if hl else INK, size=12, bold=True)
    box(ax, 3.2, y - 0.55, 6.5, 1.1, t, fc="white", size=10.5)
    if i < len(steps) - 1:
        arrow(ax, 1.6, y - 0.6, 1.6, y - 0.95)
    y -= 1.55
save(fig, "fig1_1_flow.png")

# 圖 3.1 標籤示意(數值為虛構)
fig, axs = plt.subplots(1, 3, figsize=(10, 3.2))
examples = [("高點", [52, 55, 58, 63, 70, 82, 74, 66, 60, 57, 54], ORANGE),
            ("低點", [80, 76, 72, 66, 60, 50, 56, 61, 64, 67, 70], BLUE),
            ("非極值", [55, 57, 60, 62, 65, 68, 71, 73, 76, 78, 80], MUTED)]
for ax, (name, vals, col) in zip(axs, examples):
    xs = list(range(-5, 6))
    ax.plot(xs, vals, color=LINE, lw=1.5, zorder=1)
    ax.scatter(xs, vals, color=[col if x == 0 else "#9AA5AE" for x in xs], s=[70 if x == 0 else 22 for x in xs], zorder=2)
    ax.set_xticks(xs); ax.set_xticklabels([("t" if x == 0 else f"t{x:+d}") for x in xs], fontsize=8)
    ax.set_yticks([]); ax.set_title(name, fontsize=12, color=col if name != "非極值" else INK)
    ax.axvspan(-5.5, 5.5, color="#F4F6F8", zorder=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
fig.suptitle("收盤價示意(數值為虛構)", fontsize=10, color=MUTED, y=0.02)
save(fig, "fig3_1_label.png")

# 圖 3.2 本系統的判斷流程
fig, ax = plt.subplots(figsize=(10, 4.6))
ax.set_xlim(0, 20); ax.set_ylim(0, 9.2); ax.axis("off")
box(ax, 0.1, 3.8, 2.6, 1.6, "t 日收盤後\n每一檔股票", size=10.5)
box(ax, 3.4, 3.6, 3.4, 2.0, "規則候選\nt 收盤是最近 6 天\n最高 / 最低?", fc=INK, ec=INK, color="white", size=10.5, bold=True)
arrow(ax, 2.7, 4.6, 3.4, 4.6)
box(ax, 3.6, 0.3, 3.0, 1.2, "非極值", size=10.5)
arrow(ax, 5.1, 3.6, 5.1, 1.5, "否")
for lab, col, yy in (("高點", ORANGE, 6.6), ("低點", BLUE, 2.0)):
    box(ax, 7.8, yy, 2.6, 1.6, f"{lab}候選\n29 維特徵", fc="white", ec=col, size=10)
    box(ax, 11.1, yy, 3.0, 1.6, f"AE 29 → 16\n(只學真{lab})", fc="white", ec=col, size=10)
    box(ax, 14.8, yy, 2.6, 1.6, f"OC-SVM\n像真{lab}?", fc="white", ec=col, color=col, size=10.5, bold=True)
    arrow(ax, 6.8, 4.6, 7.8, yy + 0.8)
    arrow(ax, 10.4, yy + 0.8, 11.1, yy + 0.8)
    arrow(ax, 14.1, yy + 0.8, 14.8, yy + 0.8)
    box(ax, 18.0, yy + 0.9, 1.9, 0.9, f"判{lab}", fc=col, ec=col, color="white", size=10, bold=True)
    box(ax, 18.0, yy - 0.3, 1.9, 0.9, "非極值", size=9.5)
    arrow(ax, 17.4, yy + 1.0, 18.0, yy + 1.3)
    arrow(ax, 17.4, yy + 0.6, 18.0, yy + 0.15)
ax.text(5.6, 5.85, "是", fontsize=9.5, color=MUTED)
ax.text(17.55, 8.55, "像", fontsize=9, color=MUTED); ax.text(17.45, 6.25, "不像", fontsize=9, color=MUTED)
ax.text(17.55, 3.95, "像", fontsize=9, color=MUTED); ax.text(17.45, 1.65, "不像", fontsize=9, color=MUTED)
save(fig, "fig3_2_arch.png")

# 圖 3.4 walk-forward 時間軸(測哪一年就用前 4 年訓練)
fig, ax = plt.subplots(figsize=(10, 3.3))
yrs = list(range(2020, 2027))
for i, ty in enumerate((2024, 2025, 2026)):
    yy = 2 - i
    for y_ in range(ty - 4, ty):
        ax.add_patch(plt.Rectangle((y_, yy + 0.12), 0.96, 0.5, color=TEAL, alpha=0.75))
    ax.add_patch(plt.Rectangle((ty, yy + 0.12), 0.96 if ty < 2026 else 0.7, 0.5, color=ORANGE, alpha=0.9))
    ax.text(2019.9, yy + 0.36, f"測試 {ty}", ha="right", va="center", fontsize=10.5)
ax.set_xlim(2018.8, 2027.1); ax.set_ylim(-0.1, 2.9)
ax.set_xticks([y_ + 0.48 for y_ in yrs]); ax.set_xticklabels([str(y_) for y_ in yrs])
ax.set_yticks([])
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.legend(handles=[Patch(color=TEAL, alpha=0.75, label="訓練(前 4 年)"), Patch(color=ORANGE, alpha=0.9, label="測試年")],
          loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=2, fontsize=9, frameon=False)
save(fig, "fig3_4_walkforward.png")

# ───────────────────────── 簡報 v2 的圖(同樣只讀 final 結果檔) ─────────────────────────
for src, dst in (("f_feat_kline.png", "fig3_3a_feat_kline.png"), ("f_feat_grid.png", "fig3_3b_feat_grid.png"),
                 ("f_conf.png", "fig4_1_conf_years.png"), ("f_conf_total.png", "fig4_2_conf_total.png"),
                 ("f_compare.png", "fig4_3_compare.png"), ("f_2454.png", "fig4_4_2454.png"), ("f_backtest.png", "fig4_5_backtest.png")):
    shutil.copy(os.path.join(FFIG, src), os.path.join(FIG, dst))


# ───────────────────────── 網頁截圖(只裁切,不塗改) ─────────────────────────
def crop(src, box_, dst, scale=None):
    im = Image.open(os.path.join(SHOTS, src)).convert("RGB").crop(box_)
    if scale:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    im.save(os.path.join(FIG, dst), optimize=True)
    print(dst, box_, im.size)


crop("today_desktop.png", (0, 0, 1280, 926), "fig4_6_web_today.png")
crop("stock_pool_2454_desktop.png", (60, 240, 1220, 1126), "fig4_7_web_2454.png")      # 從股票列開始,不含快捷鈕列
crop("track_desktop.png", (0, 0, 1280, 1328), "fig4_8_web_track.png")
crop("today_mobile.png", (0, 0, 780, 1460), "appB_today_mobile.png", scale=0.5)
crop("stock_otc_3374_desktop.png", (60, 240, 1220, 700), "appB_otc_3374.png")
crop("findings_desktop.png", (0, 0, 1280, 860), "appB_findings.png")
crop("about_desktop.png", (0, 0, 1280, 820), "appB_about.png")
print("ok")
