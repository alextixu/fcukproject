"""我們現在貼的標籤長怎樣:第 6 天是 11 天最高 / 最低,但中間不一定一路漲、一路跌(2026-11-02 使用者要求)。

「對方向的天數」:高點 = 前 5 天裡收盤比前一天高的天數 + 後 5 天裡收盤比前一天低的天數(0–10,10 = 一路漲、一路跌);
低點反之。平盤(收盤和前一天一樣)不算對方向。
上兩排:高點、低點各 3 個例子(對方向 10 天、典型、鋸齒),各取幅度最接近該組中位數的那一個
       (34 檔裡沒有幅度 0 的平台並列點,低波動股已剔除);
下排:所有高點 / 低點的對方向天數分布。
股票池 = mainline.load_data()(34 檔),期間 2020-01 ~ 資料最後一天(訓練與測試用到的年份)。
用法: python method_kline_peak/report/label_shapes.py
輸出: results/label_shapes.png
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mainline as ML  # noqa: E402
import extreme_windows as EW  # noqa: E402
from export_windows import ticker_names  # noqa: E402
from feasibility import clean  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402

START = "2020-01-01"
NAME = {DOWN: "高點", UP: "低點"}


def collect(data, panel):
    rows = []
    p = panel[(panel.date >= START) & (panel.y != 0)]
    for tk, g in p.groupby("ticker"):
        c = clean(data[tk])["close"]
        d = np.sign(c.diff().to_numpy())
        idx = c.index
        for r in g.itertuples():
            i = idx.get_loc(r.date)
            left, right = d[i - 4:i + 1], d[i + 1:i + 6]            # t-5→t-4 … t-1→t、t→t+1 … t+4→t+5
            want = 1 if r.y == DOWN else -1
            rows.append((tk, r.date, r.y, r.amp, int((left == want).sum()), int((right == -want).sum())))
    return pd.DataFrame(rows, columns=["ticker", "date", "y", "amp", "left_ok", "right_ok"]).assign(
        total=lambda x: x.left_ok + x.right_ok)


def pick(s):
    """幅度最接近該組中位數的那一個(同分取日期最早)。"""
    if s.empty:
        return None
    k = (s.amp - s.amp.median()).abs()
    return s.assign(k=k).sort_values(["k", "date"]).iloc[0]


def main():
    data = ML.load_data()
    panel, _ = ML.build_panel(data, 6, [])
    d = collect(data, panel)
    names = ticker_names()
    fig = plt.figure(figsize=(22, 17), dpi=150, facecolor="white")
    gs = fig.add_gridspec(3, 6, height_ratios=[1, 1, 0.85], hspace=0.62, wspace=0.5)
    for r, cls in enumerate((DOWN, UP)):
        s = d[d.y == cls]
        typ = int(s.total.median())
        groups = [(f"一路{'漲、一路跌' if cls == DOWN else '跌、一路漲'}(對方向 10 天)", s[s.total == 10]),
                  (f"典型(對方向 {typ} 天,中位數)", s[(s.total == typ) & (s.amp > 0)]),
                  ("鋸齒(對方向 ≤ 4 天)", s[(s.total <= 4) & (s.amp > 0)])]
        for c, (label, g) in enumerate(groups):
            ax = fig.add_subplot(gs[r, c * 2:c * 2 + 2])
            x = pick(g)
            share = len(g) / len(s)
            if x is None:
                ax.axis("off")
                ax.text(0.5, 0.5, f"{NAME[cls]}:{label}\n沒有例子", ha="center", va="center", fontsize=12, color=EW.INK)
                continue
            df = clean(data[x.ticker])
            EW.draw(ax, df, df.index.get_loc(x.date), cls,
                    f"{NAME[cls]}:{label},佔 {share:.1%}",
                    f"{x.ticker[:4]} {names.get(x.ticker, '')} {x.date:%Y-%m-%d}:對方向 前 {x.left_ok} + 後 {x.right_ok} 天,幅度 {x.amp:.2f}%",
                    two_lines=True)
    for c, cls in enumerate((DOWN, UP)):
        ax = fig.add_subplot(gs[2, c * 3:c * 3 + 3])
        s = d[d.y == cls]
        cnt = s.total.value_counts().reindex(range(11), fill_value=0)
        col = EW.HI if cls == DOWN else EW.LO
        bars = ax.bar(cnt.index, cnt.values / len(s) * 100, color=col, width=0.8)
        for b, v in zip(bars, cnt.values / len(s) * 100):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.4, f"{v:.1f}%", ha="center", fontsize=9.5, color=EW.INK)
        ax.set_xticks(range(11))
        ax.set_xlabel("對方向的天數(前 5 天 + 後 5 天,10 = 一路" + ("漲、一路跌)" if cls == DOWN else "跌、一路漲)"), color=EW.MUTED, fontsize=10.5)
        ax.set_ylabel("佔該類標籤(%)", color=EW.MUTED, fontsize=10.5)
        ax.set_title(f"所有{NAME[cls]} {len(s):,} 個:對方向的天數(中位數 {int(s.total.median())} 天;10 天只有 {(s.total == 10).mean():.1%})",
                     loc="left", fontsize=13, color=EW.INK, fontweight="bold", pad=10)
        for k in ("top", "right"):
            ax.spines[k].set_visible(False)
        ax.tick_params(colors=EW.MUTED, length=0)
        ax.grid(axis="y", color="#e4e3df", lw=0.8)
        ax.set_axisbelow(True)
    fig.suptitle(f"現在的標籤:第 6 天是 11 天收盤最高 / 最低就算,不要求一路漲跌(34 檔,{START[:7]} ~ {d.date.max():%Y-%m})",
                 x=0.02, ha="left", fontsize=17, color=EW.INK, y=0.995)
    fig.text(0.02, 0.005, "灰底 = t 日收盤時看得到的 6 天,框 = t 日(第 6 天);虛線 = t 收盤,點線 = 算幅度用的兩邊最低(高點)/ 最高(低點)收盤;"
             "空心 K 棒 = 收漲,實心 = 收跌。對方向 = 前 5 天收盤比前一天高(高點)+ 後 5 天收盤比前一天低。", fontsize=10.5, color=EW.INK2)
    out = os.path.join(ML.OUT, "label_shapes.png")
    fig.savefig(out, facecolor="white", bbox_inches="tight")
    for cls in (DOWN, UP):
        s = d[d.y == cls]
        print(NAME[cls], len(s), "中位", s.total.median(), "10 天", f"{(s.total == 10).mean():.2%}", "≤4 天", f"{(s.total <= 4).mean():.1%}",
              "幅度 0", f"{(s.amp < 1e-9).mean():.2%}", "分布", s.total.value_counts().sort_index().to_dict())
    print(out)


if __name__ == "__main__":
    main()
