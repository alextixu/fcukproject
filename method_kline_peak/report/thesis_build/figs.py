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
    ("股票池", "34 檔(台灣50 剔除 16 檔低波動股)\nTW200 剔除低波動股後 168 檔"),
    ("標籤", "11 天視窗,t = 第 6 天\n高點 / 低點 / 非極值"),
    ("特徵", "t-5 ~ t 六根 K 線,29 維"),
    ("模型", "① 主軸:規則候選 + AE + OC-SVM\n② Stacking:兩組 AE + OC-SVM → 邏輯迴歸"),
    ("walk-forward 評估", "前 4 年訓練、測下一年(2024、2025、2026)\n混淆矩陣、macro-F1、找到率、命中率"),
    ("交易模擬", "只做多前 3 檔回測、個案、後處理分析"),
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

# 圖 3.2 主軸架構
fig, ax = plt.subplots(figsize=(10, 4.2))
ax.set_xlim(0, 20); ax.set_ylim(0, 8.4); ax.axis("off")
box(ax, 0.2, 3.4, 2.6, 1.6, "t 日收盤後\n29 維特徵", size=10.5)
box(ax, 3.4, 3.4, 3.0, 1.6, "規則挑候選\nt 收盤為 t-5 ~ t\n最高 / 最低", size=10)
arrow(ax, 2.8, 4.2, 3.4, 4.2)
for k, (lab, col, yy) in enumerate((("高點候選", ORANGE, 6.0), ("低點候選", BLUE, 0.8))):
    box(ax, 7.2, yy, 2.4, 1.6, lab, fc="white", ec=col, color=col, size=10.5, bold=True)
    box(ax, 10.2, yy, 2.4, 1.6, "標準化\n缺值補中位數", size=9.5)
    box(ax, 13.2, yy, 2.4, 1.6, "線性 AE\n29 → 16", size=10)
    box(ax, 16.2, yy, 3.7, 1.6, "OC-SVM\n(RBF, ν = 0.1, 相似度權重)\n分數 = decision_function", size=8.5)
    arrow(ax, 6.4, 4.2, 7.2, yy + 0.8)
    for x1, x2 in ((9.6, 10.2), (12.6, 13.2), (15.6, 16.2)):
        arrow(ax, x1, yy + 0.8, x2, yy + 0.8)
box(ax, 7.2, 3.4, 12.5, 1.6, "分數 > 0 → 判為該類;分數 ≤ 0 → 改判非極值\n分數也用來排序(回測取每天前 3 檔)",
    fc=INK, ec=INK, color="white", size=10.5)
ax.text(3.4, 2.7, "非候選一律判非極值", fontsize=9.5, color=MUTED)
save(fig, "fig3_2_main_arch.png")

# 圖 3.3 Stacking 架構
fig, ax = plt.subplots(figsize=(10, 4.4))
ax.set_xlim(0, 20); ax.set_ylim(0, 8.8); ax.axis("off")
box(ax, 0.2, 3.6, 2.8, 1.6, "每一天\n29 維特徵\n(不用規則)", size=10)
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
    for y_ in range(ty - 4, ty):
        ax.add_patch(plt.Rectangle((y_, yy + 0.38), 0.96, 0.32, color=TEAL, alpha=0.85))
    for y_ in range(ty - 4, ty - 1):
        ax.add_patch(plt.Rectangle((y_, yy + 0.02), 0.96, 0.32, color=PURPLE, alpha=0.55))
    ax.add_patch(plt.Rectangle((ty - 1, yy + 0.02), 0.96, 0.32, color=PURPLE, alpha=0.95))
    ax.add_patch(plt.Rectangle((ty, yy + 0.02), 0.96 if ty < 2026 else 0.7, 0.68, color=ORANGE, alpha=0.9))
    ax.text(2019.9, yy + 0.36, f"測試 {ty}", ha="right", va="center", fontsize=10.5)
ax.set_xlim(2018.8, 2027.1); ax.set_ylim(-0.1, 2.9)
ax.set_xticks([y_ + 0.48 for y_ in yrs]); ax.set_xticklabels([str(y_) for y_ in yrs])
ax.set_yticks([])
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=TEAL, alpha=0.85, label="主軸訓練(前 4 年)"), Patch(color=PURPLE, alpha=0.55, label="Stacking 第一層 A(3 年)"),
                   Patch(color=PURPLE, alpha=0.95, label="Stacking 第二層 B(1 年)"), Patch(color=ORANGE, alpha=0.9, label="測試年")],
          loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=4, fontsize=9, frameon=False)
save(fig, "fig3_4_walkforward.png")

# 圖 4.3 主軸 vs Stacking macro-F1(逐年)
fig, axs = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
for ax, pool, title in zip(axs, ("34", "tw200"), ("34 檔", "TW200(168 檔)")):
    xs = range(3)
    m = [data["conf"][pool][y]["main"]["macro_f1"] for y in YEARS]
    s = [data["conf"][pool][y]["stack"]["macro_f1"] for y in YEARS]
    b1 = ax.bar([x - 0.18 for x in xs], m, 0.34, color=TEAL, label="主軸")
    b2 = ax.bar([x + 0.18 for x in xs], s, 0.34, color=PURPLE, label="Stacking")
    for bars in (b1, b2):
        for r in bars:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.3, f"{r.get_height():.2f}", ha="center", fontsize=9)
    ax.set_xticks(list(xs)); ax.set_xticklabels(["2024", "2025", "2026(1–9 月)"])
    ax.set_ylim(40, 58); ax.set_title(title, fontsize=12)
    ax.grid(axis="y", color="#E3E8EC"); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
axs[0].set_ylabel("macro-F1(%)")
axs[0].legend(frameon=False, fontsize=10, loc="upper left")
save(fig, "fig4_3_macro_f1.png")


# ───────────────────────── 既有圖裁切 ─────────────────────────
def crop(src, dst, top=0.0, bottom=0.0, left=0, right=0, abs_top=None, abs_bottom=None):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    t = abs_top if abs_top is not None else int(h * top)
    b = h - (abs_bottom if abs_bottom is not None else int(h * bottom))
    im.crop((left, t, w - right, b)).save(os.path.join(FIG, dst), optimize=True)


# 混淆矩陣:用簡報已裁掉標題、重排成 3 × 2 的版本
crop(os.path.join(REPORT, "kline_peak_confusion_tw50.png"), "fig4_1_conf_34.png")
crop(os.path.join(REPORT, "kline_peak_confusion_tw200.png"), "fig4_2_conf_tw200.png")
# 資產曲線、南電、後處理、低點進高點出:裁掉最上方標題列(含「訓練門檻」字樣)
crop(os.path.join(RES, "backtest_long_only_curves.png"), "fig4_4_curves_34.png", abs_top=95)
crop(os.path.join(RES, "backtest_long_only_tw200_curves.png"), "fig4_5_curves_tw200.png", abs_top=95)
crop(os.path.join(RES, "outputs_8046_2024_34_amp0.png"), "fig4_6_nandian_34.png", abs_top=200)
crop(os.path.join(RES, "outputs_8046_2024_tw200_amp0.png"), "fig4_7_nandian_tw200.png", abs_top=200)
crop(os.path.join(RES, "compare_8046_2024_tw200_main.png"), "fig4_8_post_nandian.png", abs_top=62)
crop(os.path.join(RES, "prob_cut_8046_2024_tw200_stack.png"), "fig4_9_probcut.png", abs_top=62)
crop(os.path.join(RES, "lohi_compare_8046_2024_tw200_main.png"), "fig4_10_lohi_nandian.png", abs_top=62)
crop(os.path.join(RES, "lohi_compare_34_2025.png"), "fig4_11_lohi_34.png", abs_top=72)

# 網頁截圖
S = lambda f: os.path.join(SHOTS, f)
crop(S("today_desktop.png"), "fig4_12_web_today.png", abs_bottom=2445 - 1000)
crop(S("stock_pool_8454_desktop.png"), "fig4_13_web_stock.png", abs_bottom=2123 - 1240)
crop(S("track_desktop.png"), "fig4_14_web_track.png", abs_bottom=2360 - 1000)
# 附錄
crop(S("today_desktop.png"), "appB_today.png")
crop(S("today_mobile.png"), "appB_today_mobile.png", abs_bottom=Image.open(S("today_mobile.png")).size[1] - 1650)
crop(S("search_autocomplete_desktop.png"), "appB_search.png")
crop(S("stock_pool_8454_desktop.png"), "appB_stock_pool.png")
crop(S("stock_outpool_2618_desktop.png"), "appB_stock_outpool.png", abs_bottom=2186 - 1100)
crop(S("stock_lowvol_2412_desktop.png"), "appB_stock_lowvol.png", abs_bottom=2175 - 1100)
crop(S("track_desktop.png"), "appB_track.png", abs_bottom=2360 - 1250)
# 方法與說明:略過含「訓練門檻」字樣的小字列(約 y 628–688)
im = Image.open(S("about_desktop.png")).convert("RGB")
w, h = im.size
a, b = im.crop((0, 0, w, 628)), im.crop((0, 690, w, h))
c = Image.new("RGB", (w, a.size[1] + b.size[1]), "white")
c.paste(a, (0, 0)); c.paste(b, (0, a.size[1]))
c.save(os.path.join(FIG, "appB_about.png"), optimize=True)
# 研究發現:略過開頭含「訓練門檻」的說明列,只取結論卡片
crop(S("findings_desktop.png"), "appB_findings.png", abs_top=200, abs_bottom=5640 - 700)
im = Image.open(S("findings_desktop.png")).convert("RGB")
hdr = im.crop((0, 0, 1280, 120))
body = im.crop((0, 205, 1280, 700))
c = Image.new("RGB", (1280, hdr.size[1] + body.size[1]), "white")
c.paste(hdr, (0, 0)); c.paste(body, (0, hdr.size[1]))
c.save(os.path.join(FIG, "appB_findings.png"), optimize=True)

print("ok", len(os.listdir(FIG)), "figs")
