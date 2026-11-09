"""專題研究報告:準備資料(data.json)與圖(fig/*.png)。
不跑實驗、不訓練:數字全部讀 results/ 的 json,README 的表格用程式解析;圖為既有 png 裁切,或用既有數字重畫的示意圖。
用法: python3 figs.py <predict-tool 分支的 method_kline_peak> <web 分支的 web/screenshots> <report 目錄(含重排後的混淆矩陣圖)> <輸出目錄>
"""
import json
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from PIL import Image

MK, SHOTS, REPORT, OUT = sys.argv[1:5]
RES = os.path.join(MK, "results")
FIG = os.path.join(OUT, "fig")
os.makedirs(FIG, exist_ok=True)

# 中文字型(圖用黑體,清楚易讀)
for f in font_manager.findSystemFonts():
    if "wqy-zenhei" in f.lower():
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = ["WenQuanYi Zen Hei"]
plt.rcParams["axes.unicode_minus"] = False

INK, MUTED, BLUE, ORANGE, TEAL, PURPLE, LINE = "#13202A", "#5B6670", "#2A78D6", "#EB6834", "#0B7A75", "#6250D6", "#C9D2D9"


def J(name):
    with open(os.path.join(RES, name), encoding="utf-8") as fh:
        return json.load(fh)


# ───────────────────────── 資料 ─────────────────────────
YEARS = ["2024", "2025", "2026"]
data = {}

# 混淆矩陣(三年)
conf = {}
for pool, f in (("34", "confusion_2024_2026_tw50_amp0.json"), ("tw200", "confusion_2024_2026_tw200_amp0.json")):
    c = J(f)
    conf[pool] = {}
    for y in YEARS:
        conf[pool][y] = {}
        for key, m in (("main", "① 主軸"), ("stack", "② Stacking 邏輯迴歸")):
            v = c[y][m]
            cm = v["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"]
            conf[pool][y][key] = {
                "macro_f1": round(v["macro_f1"] * 100, 2), "acc": round(v["acc"] * 100, 2),
                "rec_low": round(v["recall"]["低點"] * 100, 1), "rec_high": round(v["recall"]["高點"] * 100, 1),
                "prec_low": round(v["precision"]["低點"] * 100, 1), "prec_high": round(v["precision"]["高點"] * 100, 1),
                "cm": cm,
            }
        cm = conf[pool][y]["main"]["cm"]
        rows = [sum(r) for r in cm]
        conf[pool][y]["labels"] = {"low": rows[0], "flat": rows[1], "high": rows[2], "n": sum(rows)}
        # 高低點互判:真低判高(cm[0][2])、真高判低(cm[2][0])
        conf[pool][y]["reversed"] = {k: conf[pool][y][k]["cm"][0][2] + conf[pool][y][k]["cm"][2][0] for k in ("main", "stack")}
    # 三年平均(兩位 / 一位小數)
    avg = {}
    for key in ("main", "stack"):
        g = lambda n: sum(conf[pool][y][key][n] for y in YEARS) / 3
        avg[key] = {"macro_f1": round(g("macro_f1"), 2), "rec_low": round(g("rec_low"), 1), "rec_high": round(g("rec_high"), 1),
                    "prec_low": round(g("prec_low"), 1), "prec_high": round(g("prec_high"), 1)}
    conf[pool]["avg"] = avg
data["conf"] = conf

# 三年平均用逐年未四捨五入的值重算(和簡報第 8 頁一致)
for pool, f in (("34", "confusion_2024_2026_tw50_amp0.json"), ("tw200", "confusion_2024_2026_tw200_amp0.json")):
    c = J(f)
    for key, m in (("main", "① 主軸"), ("stack", "② Stacking 邏輯迴歸")):
        a = lambda fn: sum(fn(c[y][m]) for y in YEARS) / 3 * 100
        data["conf"][pool]["avg"][key] = {
            "macro_f1": round(a(lambda v: v["macro_f1"]), 2),
            "rec_low": round(a(lambda v: v["recall"]["低點"]), 1), "rec_high": round(a(lambda v: v["recall"]["高點"]), 1),
            "prec_low": round(a(lambda v: v["precision"]["低點"]), 1), "prec_high": round(a(lambda v: v["precision"]["高點"]), 1)}

# 回測
bt = {}
for pool, f in (("34", "backtest_long_only.json"), ("tw200", "backtest_long_only_tw200.json")):
    b = J(f)
    bt[pool] = {"rule": b["rule"], "pool_n": b["pool"] if not isinstance(b["pool"], list) else len(b["pool"]),
                "excluded_n": b["excluded"] if not isinstance(b["excluded"], list) else len(b["excluded"])}
    for y in YEARS:
        bt[pool][y] = {}
        for key, m in (("main", "主軸"), ("stack", "Stacking 邏輯迴歸")):
            v = b["years"][y][m]
            bt[pool][y][key] = {
                "net": v["扣成本"]["total_return_pct"], "gross": v["沒扣成本"]["total_return_pct"],
                "dd": v["扣成本"]["max_dd_pct"], "win": v["扣成本"]["win_rate_pct"], "n": v["扣成本"]["n_trades"],
                "avg_net": v["扣成本"]["avg_net_ret_pct"], "n_low": v["n_low_signals"], "n_high": v["n_high_signals"],
                "n_train": v["n_train"]}
        bt[pool][y]["period"] = b["years"][y]["period"]
    bt[pool]["avg"] = {k: round(sum(bt[pool][y][k]["net"] for y in YEARS) / 3, 2) for k in ("main", "stack")}
data["bt"] = bt
data["pool34_list"] = J("backtest_long_only.json")["pool"]
data["pool34_excluded"] = J("backtest_long_only.json")["excluded"]

# 邏輯迴歸範例
data["lr"] = J("lr_example_tw200_2025.json")

# 南電 2024 單檔混淆
data["nandian"] = {}
for pool, f in (("34", "confusion_8046_2024_34_amp0.json"), ("tw200", "confusion_8046_2024_tw200_amp0.json")):
    c = J(f)
    data["nandian"][pool] = {"n_days": c["n_days"]}
    for key, m in (("main", "① 主軸"), ("stack", "② Stacking 邏輯迴歸")):
        v = c["methods"][m]
        cm = v["confusion_rows_true_cols_pred(低點,非極值,高點)"]
        data["nandian"][pool][key] = {"cm": cm, "macro_f1": v["macro_f1_pct"], "rec": v["recall_pct"], "prec": v["precision_pct"]}

# README 表格(後處理、等確認、機率門檻、低點進高點出)
readme = open(os.path.join(MK, "README.md"), encoding="utf-8").read().splitlines()


def table_after(marker, skip=0):
    i = next(k for k, ln in enumerate(readme) if marker in ln)
    found = 0
    while True:
        while not readme[i].startswith("|"):
            i += 1
        rows = []
        while i < len(readme) and readme[i].startswith("|"):
            cells = [c.strip() for c in readme[i].strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                rows.append(cells)
            i += 1
        if found == skip:
            return rows
        found += 1


T = {
    "post_main": table_after("**主軸**(三年平均;逐年 macro-F1"),
    "post_stack": table_after("**Stacking 邏輯迴歸**(三年平均;逐年 macro-F1"),
    "conf_cls": table_after("**分類成績**(三年平均;訊號數"),
    "conf_bt": table_after("**回測**(只做多前 3 檔,t+k+1"),
    "delay": table_after("**晚進場代價**"),
    "nd_post": table_after("南電 2024:每種後處理拿掉了哪些訊號"),
    "nd_lohi": table_after("同 8 列各自做「低點進場、高點出場」"),
    "lohi34": table_after("同 8 列改成 34 檔多檔組合"),
    "prob_nd": table_after("**南電 2024**(真低點 16、真高點 17)"),
    "prob_all": table_after("**全部 168 檔,2024–2026 三年平均**"),
}
data["readme"] = T
data["random_line"] = next(ln for ln in readme if ln.startswith("隨機猜的命中率基準"))
data["lohi_bh_line"] = next(ln for ln in readme if ln.startswith("買進持有(第一天開盤買"))
data["lohi34_base_line"] = next(ln for ln in readme if ln.startswith("基準:34 檔等權買進持有"))
data["prob_median_line"] = next(ln for ln in readme if ln.startswith("判低點 / 判高點那天最大機率的中位數"))
for k, v in T.items():
    for row in v:
        for cell in row:
            assert "訓練門檻" not in cell, (k, cell)

# 南電 2024(TW200 模型)Stacking 原始判斷:判斷天數、對錯、當天 / 前後 2 天內抓到
data["nd_cmp"] = J("compare_8046_2024_tw200.json")["methods"]["Stacking 邏輯迴歸"]["A0 原始"]

with open(os.path.join(OUT, "data.json"), "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False, indent=1)


# ───────────────────────── 自繪圖 ─────────────────────────
def box(ax, x, y, w, h, text, fc="#EEF2F5", ec=LINE, color=INK, size=11, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=color,
            fontweight="bold" if bold else "normal", linespacing=1.4)


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14, color=MUTED, lw=1.4))


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
    ("特徵", "t-5 ~ t 六根 K 線,29 維"),
    ("模型", "Stacking 第一層:高點、低點兩組 AE + OC-SVM\n對每一天打分數 → 第二層邏輯迴歸輸出三類機率"),
    ("walk-forward 評估", "前 4 年訓練(第一層 3 年、第二層 1 年)、測下一年\n混淆矩陣、macro-F1、找到率、命中率"),
    ("個案分析", "南電(8046)2024 年:真實高低點與 Stacking 判斷"),
    ("系統實作", "網頁系統:每日判斷、個股查詢、成績追蹤"),
]
y = 12.2
for i, (h, t) in enumerate(steps):
    box(ax, 0.3, y - 0.55, 2.6, 1.1, h, fc=INK if i in (4,) else "#EEF2F5", color="white" if i in (4,) else INK, size=12, bold=True)
    box(ax, 3.2, y - 0.55, 6.5, 1.1, t, fc="white", size=10.5)
    if i < len(steps) - 1:
        arrow(ax, 1.6, y - 0.6, 1.6, y - 0.95)
    y -= 1.55
save(fig, "fig1_1_flow.png")

# 圖 3.1 標籤示意(數值為虛構)
fig, axs = plt.subplots(1, 3, figsize=(10, 3.2), sharey=False)
examples = [("高點", [52, 55, 58, 63, 70, 82, 74, 66, 60, 57, 54], ORANGE),
            ("低點", [80, 76, 72, 66, 60, 50, 56, 61, 64, 67, 70], BLUE),
            ("非極值", [55, 57, 60, 62, 65, 68, 71, 73, 76, 78, 80], MUTED)]
for ax, (name, vals, col) in zip(axs, examples):
    xs = list(range(-5, 6))
    ax.plot(xs, vals, color=LINE, lw=1.5, zorder=1)
    ax.scatter(xs, vals, color=[col if x == 0 else "#9AA5AE" for x in xs], s=[70 if x == 0 else 22 for x in xs], zorder=2)
    ax.set_xticks(xs); ax.set_xticklabels([("t" if x == 0 else f"t{x:+d}") for x in xs], fontsize=8)
    ax.set_yticks([]); ax.set_title(f"{name}", fontsize=12, color=col if name != "非極值" else INK)
    ax.axvspan(-5.5, 5.5, color="#F4F6F8", zorder=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
fig.suptitle("收盤價示意(數值為虛構)", fontsize=10, color=MUTED, y=0.02)
save(fig, "fig3_1_label.png")

# 圖 3.3 Stacking 架構
fig, ax = plt.subplots(figsize=(10, 4.4))
ax.set_xlim(0, 20); ax.set_ylim(0, 8.8); ax.axis("off")
box(ax, 0.2, 3.6, 2.8, 1.6, "每一天\n29 維特徵\n(不經規則篩選)", size=10)
for lab, col, yy, tag in (("高點 AE + OC-SVM", ORANGE, 6.2, "s_high"), ("低點 AE + OC-SVM", BLUE, 1.0, "s_low")):
    box(ax, 4.0, yy, 4.6, 1.6, f"第一層:{lab}\n只用 A 期真{lab[:2]}訓練", fc="white", ec=col, color=INK, size=10)
    box(ax, 9.4, yy, 2.6, 1.6, f"分數\n{tag}", fc="white", ec=col, color=col, size=10.5, bold=True)
    arrow(ax, 3.0, 4.4, 4.0, yy + 0.8)
    arrow(ax, 8.6, yy + 0.8, 9.4, yy + 0.8)
    arrow(ax, 12.0, yy + 0.8, 13.0, 4.4)
box(ax, 13.0, 3.4, 3.4, 2.0, "第二層:\n多類別邏輯迴歸\n(B 期訓練)", fc=INK, ec=INK, color="white", size=10.5, bold=True)
box(ax, 17.0, 3.4, 2.8, 2.0, "softmax 三類機率\n判斷 = 最大機率類\n分數 = 最大機率", size=9.5)
arrow(ax, 16.4, 4.4, 17.0, 4.4)
save(fig, "fig3_3_stack_arch.png")

# 圖 3.4 walk-forward 時間軸
fig, ax = plt.subplots(figsize=(10, 3.3))
yrs = list(range(2020, 2027))
for i, ty in enumerate((2024, 2025, 2026)):
    yy = 2 - i
    for y_ in range(ty - 4, ty - 1):
        ax.add_patch(plt.Rectangle((y_, yy + 0.12), 0.96, 0.5, color=PURPLE, alpha=0.55))
    ax.add_patch(plt.Rectangle((ty - 1, yy + 0.12), 0.96, 0.5, color=PURPLE, alpha=0.95))
    ax.add_patch(plt.Rectangle((ty, yy + 0.12), 0.96 if ty < 2026 else 0.7, 0.5, color=ORANGE, alpha=0.9))
    ax.text(2019.9, yy + 0.36, f"測試 {ty}", ha="right", va="center", fontsize=10.5)
ax.set_xlim(2018.8, 2027.1); ax.set_ylim(-0.1, 2.9)
ax.set_xticks([y_ + 0.48 for y_ in yrs]); ax.set_xticklabels([str(y_) for y_ in yrs])
ax.set_yticks([])
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=PURPLE, alpha=0.55, label="Stacking 第一層 A(3 年)"),
                   Patch(color=PURPLE, alpha=0.95, label="Stacking 第二層 B(1 年)"), Patch(color=ORANGE, alpha=0.9, label="測試年")],
          loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=3, fontsize=9, frameon=False)
save(fig, "fig3_4_walkforward.png")

# ───────────────────────── 既有圖裁切 ─────────────────────────
def crop(src, dst, top=0.0, bottom=0.0, left=0, right=0, abs_top=None, abs_bottom=None):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    t = abs_top if abs_top is not None else int(h * top)
    b = h - (abs_bottom if abs_bottom is not None else int(h * bottom))
    im.crop((left, t, w - right, b)).save(os.path.join(FIG, dst), optimize=True)


# 混淆矩陣:TW200,只取下排 Stacking(y ≥ 705),標題前的「②」編號塗白
crop(os.path.join(REPORT, "kline_peak_confusion_tw200.png"), "fig4_2_conf_tw200.png", abs_top=705)
from PIL import ImageDraw
import numpy as np
im = Image.open(os.path.join(FIG, "fig4_2_conf_tw200.png")).convert("RGB")
dr = ImageDraw.Draw(im)
g = np.asarray(im.convert("L"))[0:34]
dark = (g < 160).any(axis=0)
for c0 in (60, 740, 1420):
    x = c0 + int(np.argmax(dark[c0:c0 + 200]))
    x1 = x
    while dark[x1 + 1] or dark[x1 + 2] or dark[x1 + 3]:
        x1 += 1
    dr.rectangle((x - 1, 0, x1 + 1, 39), fill="white")
im.save(os.path.join(FIG, "fig4_2_conf_tw200.png"), optimize=True)


def stitch(src, ranges, dst, box=None):
    im = Image.open(src).convert("RGB")
    if box:
        im = im.crop(box)
    w = im.size[0]
    parts = [im.crop((0, a, w, b)) for a, b in ranges]
    c = Image.new("RGB", (w, sum(p.size[1] for p in parts)), "white")
    y = 0
    for p in parts:
        c.paste(p, (0, y)); y += p.size[1]
    c.save(os.path.join(FIG, dst), optimize=True)


# 南電 2024(TW200 模型):收盤與真實標籤 + Stacking 原始判斷 + 月份軸(取自 compare_8046_2024_tw200_stack.png,略過標題列與後處理各段)
stitch(os.path.join(RES, "compare_8046_2024_tw200_stack.png"), [(70, 430), (555, 880), (3590, 3615)], "fig4_3_nandian.png")
# 南電 2024 混淆矩陣:只取 Stacking 面板(略過含編號的方法名稱列)
stitch(os.path.join(RES, "confusion_8046_2024_tw200_amp0.png"), [(197, 940)], "fig4_4_nandian_conf.png", box=(800, 0, 1560, 990))

# 網頁截圖(分支 claude/kline-peak-web-app 881d92d,預設 Stacking)。
# 方法切換鈕與兩方法對照的區塊含另一方法的名稱,以垂直拼接略過那些列。
S = lambda f: os.path.join(SHOTS, f)
stitch(S("today_desktop.png"), [(0, 130), (205, 1200)], "fig4_5_web_today.png")
stitch(S("stock_pool_8454_desktop.png"), [(0, 372), (1036, 1500)], "fig4_6_web_stock.png")
stitch(S("track_desktop.png"), [(0, 130), (250, 986)], "fig4_7_web_track.png")
# 附錄
stitch(S("today_mobile.png"), [(0, 480), (625, 2220)], "appB_today_mobile.png")
crop(S("search_autocomplete_desktop.png"), "appB_search.png")
stitch(S("stock_outpool_2618_desktop.png"), [(0, 440)], "appB_stock_outpool.png")
stitch(S("stock_lowvol_2412_desktop.png"), [(0, 465)], "appB_stock_lowvol.png")
stitch(S("track_desktop.png"), [(0, 130), (1100, 2455)], "appB_track.png")
stitch(S("findings_desktop.png"), [(0, 130), (255, 410)], "appB_findings.png")
stitch(S("about_desktop.png"), [(0, 460), (1465, 1873)], "appB_about.png")

print("ok", len(os.listdir(FIG)), "figs")
