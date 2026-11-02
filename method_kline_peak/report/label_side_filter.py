"""做法 2「每邊至少 N 天對方向」會留下 / 刪掉哪些標籤(2026-11-02 使用者要求,只畫圖,不訓練)。

高點:前 5 天至少 N 天收盤比前一天高,而且後 5 天至少 N 天收盤比前一天低;低點反之。平盤不算對方向。
上:高點、低點各「保留」3 個例子(剛好 N + N、典型、一路漲跌)與「刪掉」3 個例子(左邊不夠、右邊不夠、兩邊都不夠),
    各取幅度最接近該組中位數的那一個;下:前 5 天 × 後 5 天對方向天數的分布,框起來的是保留的範圍。
股票池 = mainline.load_data()(34 檔),2020-01 ~ 資料最後一天。
用法: python method_kline_peak/report/label_side_filter.py [--min-side 3]
輸出: results/label_side<N>.png
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mainline as ML  # noqa: E402
import extreme_windows as EW  # noqa: E402
import label_shapes as LS  # noqa: E402
from export_windows import ticker_names  # noqa: E402
from feasibility import clean  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402

KEEP_C, DROP_C = "#1c7a4a", "#b3261e"
RAMP = {DOWN: LinearSegmentedColormap.from_list("o", ["#fdf1ea", "#f0956b", "#a8441c"]),
        UP: LinearSegmentedColormap.from_list("b", ["#eef5fd", "#86b6ef", "#104281"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-side", type=int, default=3)
    n = ap.parse_args().min_side
    data = ML.load_data()
    panel, _ = ML.build_panel(data, 6, [])
    d = LS.collect(data, panel)
    names = ticker_names()
    fig = plt.figure(figsize=(22, 30), dpi=140, facecolor="white")
    gs = fig.add_gridspec(5, 6, height_ratios=[1, 1, 1, 1, 1.05], hspace=0.75, wspace=0.5)
    for r0, cls in ((0, DOWN), (2, UP)):
        s = d[d.y == cls]
        ok = (s.left_ok >= n) & (s.right_ok >= n)
        mid_l, mid_r = int(s[ok].left_ok.median()), int(s[ok].right_ok.median())
        groups = [
            (True, f"剛好 {n} + {n} 天", s[(s.left_ok == n) & (s.right_ok == n)]),
            (True, f"典型保留({mid_l} + {mid_r} 天)", s[(s.left_ok == mid_l) & (s.right_ok == mid_r)]),
            (True, "一路" + ("漲、一路跌" if cls == DOWN else "跌、一路漲") + "(5 + 5 天)", s[(s.left_ok == 5) & (s.right_ok == 5)]),
            (False, f"左邊不夠(前 < {n} 天,後 ≥ {n} 天)", s[(s.left_ok < n) & (s.right_ok >= n)]),
            (False, f"右邊不夠(前 ≥ {n} 天,後 < {n} 天)", s[(s.left_ok >= n) & (s.right_ok < n)]),
            (False, "兩邊都不夠", s[(s.left_ok < n) & (s.right_ok < n)]),
        ]
        for k, (keep, label, g) in enumerate(groups):
            ax = fig.add_subplot(gs[r0 + k // 3, (k % 3) * 2:(k % 3) * 2 + 2])
            x = LS.pick(g)
            tag = "保留" if keep else "刪掉"
            if x is None:
                ax.axis("off")
                ax.text(0.5, 0.5, f"{LS.NAME[cls]} {tag}:{label}\n沒有例子", ha="center", va="center", fontsize=12)
                continue
            df = clean(data[x.ticker])
            EW.draw(ax, df, df.index.get_loc(x.date), cls, f"{LS.NAME[cls]} {tag}:{label},{len(g):,} 個({len(g) / len(s):.1%})",
                    f"{x.ticker[:4]} {names.get(x.ticker, '')} {x.date:%Y-%m-%d}:對方向 前 {x.left_ok} + 後 {x.right_ok} 天,幅度 {x.amp:.2f}%",
                    two_lines=True)
            ax.title.set_color(KEEP_C if keep else DROP_C)
            for sp in ("left", "right", "top", "bottom"):
                ax.spines[sp].set_visible(True)
                ax.spines[sp].set_color(KEEP_C if keep else DROP_C)
                ax.spines[sp].set_linewidth(2)
    for c, cls in enumerate((DOWN, UP)):
        ax = fig.add_subplot(gs[4, c * 3:c * 3 + 3])
        s = d[d.y == cls]
        m = np.zeros((6, 6), dtype=int)
        for (a, b), v in s.groupby(["left_ok", "right_ok"]).size().items():
            m[a, b] = v
        ax.imshow(m / len(s), cmap=RAMP[cls], origin="lower", vmin=0)
        for a in range(6):
            for b in range(6):
                if m[a, b]:
                    ax.text(b, a, f"{m[a, b]}\n{m[a, b] / len(s):.1%}", ha="center", va="center", fontsize=9,
                            color="white" if m[a, b] / len(s) > 0.08 else EW.INK)
        ax.add_patch(Rectangle((n - 0.5, n - 0.5), 6 - n, 6 - n, fill=False, ec=KEEP_C, lw=3))
        ok = (s.left_ok >= n) & (s.right_ok >= n)
        ax.set_xticks(range(6))
        ax.set_yticks(range(6))
        ax.set_xlabel("後 5 天對方向的天數(高點 = 收跌的天數)" if cls == DOWN else "後 5 天對方向的天數(低點 = 收漲的天數)", color=EW.MUTED, fontsize=11)
        ax.set_ylabel("前 5 天對方向的天數(高點 = 收漲)" if cls == DOWN else "前 5 天對方向的天數(低點 = 收跌)", color=EW.MUTED, fontsize=11)
        ax.tick_params(colors=EW.MUTED, length=0)
        ax.set_title(f"所有{LS.NAME[cls]} {len(s):,} 個:綠框 = 保留 {int(ok.sum()):,} 個({ok.mean():.1%}),框外刪掉 {int((~ok).sum()):,} 個",
                     loc="left", fontsize=13, color=EW.INK, fontweight="bold", pad=10)
    fig.suptitle(f"做法 2:每邊至少 {n} 天對方向(34 檔,{LS.START[:7]} ~ {d.date.max():%Y-%m});綠色 = 保留、紅色 = 刪掉",
                 x=0.02, ha="left", fontsize=18, color=EW.INK, y=0.997)
    fig.text(0.02, 0.003, "灰底 = t 日收盤時看得到的 6 天,框 = t 日(第 6 天);虛線 = t 收盤,點線 = 算幅度用的兩邊最低(高點)/ 最高(低點)收盤;"
             "空心 K 棒 = 收漲,實心 = 收跌。對方向:高點 = 前 5 天收漲、後 5 天收跌的天數,低點反之;平盤不算。", fontsize=11, color=EW.INK2)
    out = os.path.join(ML.OUT, f"label_side{n}.png")
    fig.savefig(out, facecolor="white", bbox_inches="tight")
    print(out)


if __name__ == "__main__":
    main()
