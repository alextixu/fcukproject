"""系統架構圖(四個管線):資料 / 特徵 / 訓練 / 判斷與服務。內容依 final 分支的實際流程(mainline.py、walkforward.py、web/run.py)。
畫布 12.15 × 5.6 英寸 = 投影片上的實際尺寸,所以字級(pt)就是投影片上的字級。
用法: python3 figs_arch.py <輸出目錄>   → f_arch_v2.png(投影片用,300 dpi)
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Ellipse, Rectangle, Polygon, Circle, PathPatch
from matplotlib.path import Path

OUT = sys.argv[1]
for f in font_manager.findSystemFonts():
    if "wqy-zenhei" in f.lower():
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = ["WenQuanYi Zen Hei"]

W, H = 12.15, 5.6
INK, MUTED = "#22303A", "#5B6670"
FILL = {"proc": "#FCE3D3", "io": "#FFF2C2", "svc": "#D9F0DC", "model": "#ECEEF0"}
HI, LO = "#E8622C", "#2A6FD6"
FS_MOD, FS_TITLE, FS_LAB = 13, 17, 11
BOLD = [pe.withStroke(linewidth=0.55, foreground=INK)]

fig = plt.figure(figsize=(W, H))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
BOXES = {}                                   # 名稱 → (x0, y0, x1, y1),最後檢查箭頭不穿過方塊


def text(x, y, s, size=FS_MOD, bold=True, color=INK, ha="center", va="center", z=6):
    t = ax.text(x, y, s, fontsize=size, color=color, ha=ha, va=va, zorder=z, linespacing=1.25)
    if bold:
        t.set_path_effects([pe.withStroke(linewidth=0.5, foreground=color)])
    return t


def pipeline(x0, y0, x1, y1, title):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0,rounding_size=0.14",
                                fc="white", ec=INK, lw=1.1, zorder=1))
    text((x0 + x1) / 2, y1 - 0.27, title, size=FS_TITLE)


def mod(name, cx, cy, w, h, label, kind, edge=INK, lw=1.0, sub=None):
    x0, y0 = cx - w / 2, cy - h / 2
    ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0,rounding_size=0.07",
                                fc=FILL[kind], ec=edge, lw=lw, zorder=3))
    if sub:
        text(cx, cy + 0.11, label)
        text(cx, cy - 0.15, sub, size=FS_LAB, bold=False, color=MUTED)
    else:
        text(cx, cy, label)
    BOXES[name] = (x0, y0, x0 + w, y0 + h)
    return BOXES[name]


def diamond(name, cx, cy, w, h, label):
    ax.add_patch(Polygon([(cx - w / 2, cy), (cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2)], closed=True,
                         fc=FILL["svc"], ec=INK, lw=1.0, zorder=3))
    text(cx, cy, label, size=FS_LAB + 1)
    BOXES[name] = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def cylinder(name, cx, cy, w, h, label):
    e = 0.09                                  # 橢圓半高
    x0, y0 = cx - w / 2, cy - h / 2
    for k in range(3):                        # 三層疊起來
        yb = y0 + k * h / 3
        ax.add_patch(Rectangle((x0, yb), w, h / 3, fc="white", ec="none", zorder=3))
        ax.add_patch(Ellipse((cx, yb), w, 2 * e, fc="white", ec=INK, lw=1.1, zorder=3 + k * 0.1))
        ax.plot([x0, x0], [yb, yb + h / 3], color=INK, lw=1.1, zorder=3.5)
        ax.plot([x0 + w, x0 + w], [yb, yb + h / 3], color=INK, lw=1.1, zorder=3.5)
    ax.add_patch(Ellipse((cx, y0 + h), w, 2 * e, fc="white", ec=INK, lw=1.1, zorder=4))
    for k in range(3):                        # 每層的下緣弧線畫在最上面
        yb = y0 + k * h / 3
        ax.add_patch(Ellipse((cx, yb), w, 2 * e, fc="none", ec=INK, lw=1.1, zorder=4.2, theta1=180, theta2=360) if False else
                     matplotlib.patches.Arc((cx, yb), w, 2 * e, theta1=180, theta2=360, ec=INK, lw=1.1, zorder=4.2))
    text(cx, y0 - e - 0.15, label)
    BOXES[name] = (x0, y0 - e, x0 + w, y0 + h + e)


def person(cx, cy):
    ax.add_patch(Circle((cx, cy + 0.2), 0.1, fc="white", ec=INK, lw=1.2, zorder=4))
    ax.add_patch(FancyBboxPatch((cx - 0.16, cy - 0.2), 0.32, 0.27, boxstyle="round,pad=0,rounding_size=0.12",
                                fc="white", ec=INK, lw=1.2, zorder=4))
    text(cx, cy - 0.37, "使用者", size=FS_LAB + 1)
    BOXES["user"] = (cx - 0.16, cy - 0.2, cx + 0.16, cy + 0.3)


SEGS = []                                     # 每條箭頭的線段,最後檢查


def route(pts, dashed=False, dot=True, both=False, color=INK, r=0.09):
    """pts:折線的點;直角轉彎處用圓角;起點小實心圓點;終點箭頭。"""
    verts, codes = [pts[0]], [Path.MOVETO]
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        d1 = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5; d2 = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        rr = min(r, d1 / 2, d2 / 2)
        a = (x1 - (x1 - x0) / d1 * rr, y1 - (y1 - y0) / d1 * rr)
        b = (x1 + (x2 - x1) / d2 * rr, y1 + (y2 - y1) / d2 * rr)
        verts += [a, (x1, y1), b]; codes += [Path.LINETO, Path.CURVE3, Path.CURVE3]
    verts.append(pts[-1]); codes.append(Path.LINETO)
    style = "<|-|>" if both else "-|>"
    ax.add_patch(FancyArrowPatch(path=Path(verts, codes), arrowstyle=style, mutation_scale=13, color=color, lw=1.3,
                                 linestyle=(0, (4, 3)) if dashed else "-", zorder=5, shrinkA=0, shrinkB=0))
    if dot and not both:
        ax.add_patch(Circle(pts[0], 0.045, fc=color, ec=color, zorder=5.5))
    SEGS.extend(zip(pts[:-1], pts[1:]))


def label(x, y, s, ha="center", va="bottom"):
    t = text(x, y, s, size=FS_LAB, bold=False, color=MUTED, ha=ha, va=va, z=7)
    t.set_bbox(dict(fc="white", ec="none", pad=1.2))


# ═════ 管線大框 ═════
TOP0, TOP1, BOT0, BOT1 = 3.4, 5.55, 0.05, 2.95
AX1, BX0 = 4.4, 4.75                          # A | B
CX1, DX0 = 6.2, 6.55                          # C | D
pipeline(0.05, TOP0, AX1, TOP1, "A 資料管線")
pipeline(BX0, TOP0, W - 0.05, TOP1, "B 特徵管線")
pipeline(0.05, BOT0, CX1, BOT1, "C 訓練管線")
pipeline(DX0, BOT0, W - 0.05, BOT1, "D 判斷與服務管線")

# ═════ A 資料管線 ═════
ya = 4.72
mod("yahoo", 0.8, ya, 0.95, 0.56, "Yahoo\n股價", "io")
mod("update", 2.05, ya, 1.0, 0.56, "每日更新", "proc")
cylinder("kdb", 3.15, ya + 0.02, 0.6, 0.52, "K 線資料庫")
route([(BOXES["yahoo"][2], ya), (BOXES["update"][0], ya)])
route([(BOXES["update"][2], ya), (BOXES["kdb"][0], ya)])

# ═════ B 特徵管線 ═════
yb = 4.72
mod("k6", 5.5, yb, 1.1, 0.56, "6 根 K 線", "proc")
diamond("rule", 6.98, yb, 1.62, 0.92, "最近 6 天\n最高 / 最低?")
mod("feat", 9.3, yb, 1.75, 0.56, "29 維型態特徵", "proc")
mod("flat", 6.98, 3.76, 1.05, 0.38, "非極值", "io")
route([(BOXES["kdb"][2], ya), (BOXES["k6"][0], yb)])
label(3.95, ya + 0.06, "日 K 線")
route([(BOXES["k6"][2], yb), (BOXES["rule"][0], yb)])
route([(BOXES["rule"][2], yb), (BOXES["feat"][0], yb)])
label((BOXES["rule"][2] + BOXES["feat"][0]) / 2, yb + 0.05, "是")
route([(6.98, BOXES["rule"][1]), (6.98, BOXES["flat"][3])])
label(7.06, (BOXES["rule"][1] + BOXES["flat"][3]) / 2, "否", ha="left", va="center")

# 圖例(B 右側空白處)
lx, ly, dy = 10.62, 5.12, 0.245
legend = [("proc", "處理步驟", INK), ("io", "輸入 / 輸出", INK), ("svc", "服務 / 判斷", INK), ("model", "模型", INK),
          ("white", "高點組", HI), ("white", "低點組", LO)]
for i, (k, s, ec) in enumerate(legend):
    yy = ly - i * dy
    ax.add_patch(FancyBboxPatch((lx, yy - 0.075), 0.26, 0.15, boxstyle="round,pad=0,rounding_size=0.03",
                                fc=FILL.get(k, "white"), ec=ec, lw=0.8 if ec == INK else 1.6, zorder=3))
    text(lx + 0.36, yy, s, size=FS_LAB, bold=False, color=MUTED, ha="left")
ax.plot([lx, lx + 0.26], [ly - 6 * dy] * 2, color=INK, lw=1.2, linestyle=(0, (4, 3)))
text(lx + 0.36, ly - 6 * dy, "5 天後對答案", size=FS_LAB, bold=False, color=MUTED, ha="left")

# ═════ B → C / D:特徵 + 候選 ═════
yj = 3.15
route([(9.3, BOXES["feat"][1]), (9.3, yj)], dot=True)
route([(9.3, yj), (0.85, yj), (0.85, 1.66)], dot=False)
label(3.0, yj + 0.04, "特徵 + 候選(前 4 年,訓練用)")
route([(9.3, yj), (11.25, yj), (11.25, 2.43)], dot=False)
label(10.3, yj + 0.04, "今日特徵 + 候選")

# ═════ C 訓練管線 ═════
ym, yh, yl = 1.35, 2.05, 0.62
mod("data4", 0.85, ym, 1.0, 0.62, "前 4 年\n資料", "io")
mod("label", 2.25, ym, 1.3, 0.62, "標籤", "proc", sub="11 天最高/最低")
for lane, yy, c in (("h", yh, HI), ("l", yl, LO)):
    mod("ae" + lane, 3.75, yy, 1.05, 0.56, "AE", "model", edge=c, lw=1.8, sub="29 → 16")
    mod("oc" + lane, 4.92, yy, 0.92, 0.56, "OC-SVM", "model", edge=c, lw=1.8)
cylinder("mdb", 5.84, ym + 0.02, 0.52, 0.5, "模型庫")
route([(BOXES["data4"][2], ym), (BOXES["label"][0], ym)])
xf = BOXES["label"][2] + 0.16
route([(BOXES["label"][2], ym), (xf, ym), (xf, yh), (BOXES["aeh"][0], yh)])
route([(xf, ym), (xf, yl), (BOXES["ael"][0], yl)], dot=True)
for lane, yy in (("h", yh), ("l", yl)):
    route([(BOXES["ae" + lane][2], yy), (BOXES["oc" + lane][0], yy)])
xm = BOXES["och"][2] + 0.1
route([(BOXES["och"][2], yh), (xm, yh), (xm, ym + 0.12), (BOXES["mdb"][0], ym + 0.12)])
route([(BOXES["ocl"][2], yl), (xm, yl), (xm, ym - 0.08), (BOXES["mdb"][0], ym - 0.08)])

# ═════ D 判斷與服務管線 ═════
y1, y2, y3 = 2.15, 1.36, 0.55
mod("load", 9.55, y1, 1.2, 0.52, "載入模型", "svc")
mod("score", 11.25, y1, 1.2, 0.52, "打分數", "proc")
mod("result", 11.25, y2, 1.4, 0.62, "高點 / 低點", "io", sub="/ 非極值")
cylinder("jdb", 11.25, y3 + 0.12, 0.56, 0.38, "判斷存檔")
mod("grade", 9.55, y3, 1.3, 0.56, "5 天後對答案", "proc")
mod("web", 8.45, y2, 2.2, 0.68, "網頁系統", "svc", sub="今日判斷・個股查詢・成績追蹤")
person(6.95, y2 + 0.04)
# 模型:C 模型庫 → D 載入模型
xg = (CX1 + DX0) / 2
route([(BOXES["mdb"][2], ym + 0.02), (xg, ym + 0.02), (xg, y1), (BOXES["load"][0], y1)])
label(7.6, y1 + 0.05, "模型")
route([(BOXES["load"][2], y1), (BOXES["score"][0], y1)])
route([(11.25, BOXES["score"][1]), (11.25, BOXES["result"][3])])
route([(BOXES["result"][0], y2), (BOXES["web"][2], y2)])
label((BOXES["result"][0] + BOXES["web"][2]) / 2, y2 + 0.05, "每日判斷")
route([(11.25, BOXES["result"][1]), (11.25, BOXES["jdb"][3])])
route([(BOXES["jdb"][0], y3 + 0.12), (BOXES["grade"][2], y3 + 0.12)])
route([(BOXES["grade"][0], y3), (8.45, y3), (8.45, BOXES["web"][1])], dashed=True)
label(8.53, (y3 + BOXES["web"][1]) / 2, "對錯", ha="left", va="center")
route([(BOXES["user"][2] + 0.06, y2), (BOXES["web"][0], y2)], both=True)

fig.savefig(os.path.join(OUT, "f_arch_v2.png"), dpi=300, facecolor="white")


# ═════ 檢查:箭頭線段不穿過方塊內部(端點接在邊上可以) ═════
def crosses(seg, box, eps=0.02):
    (x0, y0), (x1, y1) = seg
    bx0, by0, bx1, by1 = box[0] + eps, box[1] + eps, box[2] - eps, box[3] - eps
    if x0 == x1:
        return bx0 < x0 < bx1 and max(min(y0, y1), by0) < min(max(y0, y1), by1)
    return by0 < y0 < by1 and max(min(x0, x1), bx0) < min(max(x0, x1), bx1)


bad = [(s, n) for s in SEGS for n, b in BOXES.items() if crosses(s, b)]
print("arrow-through-box:", bad if bad else "none")
for n, b in BOXES.items():
    print(f"{n:7s} x {b[0]:.2f}–{b[2]:.2f}  y {b[1]:.2f}–{b[3]:.2f}")
