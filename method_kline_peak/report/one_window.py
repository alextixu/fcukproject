"""單一天的 11 天 K 線,標出每天收盤漲跌與是否「對方向」(做法 2 用的計數)。
用法: python method_kline_peak/report/one_window.py 2379.TW 2023-05-29 [--min-side 3]
輸出: results/window_<代號>_<日期>.png
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mainline as ML  # noqa: E402
import extreme_windows as EW  # noqa: E402
from export_windows import ticker_names  # noqa: E402
from feasibility import clean  # noqa: E402
from paper_aeocsvm import paper_label, label_amp  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402

OK_C, BAD_C = "#1c7a4a", "#b3261e"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("date")
    ap.add_argument("--min-side", type=int, default=3)
    a = ap.parse_args()
    data = ML.load_data()
    df = clean(data[a.ticker])
    i = df.index.get_loc(a.date)
    y, _, _ = paper_label(df["close"])
    cls = int(y.iloc[i])
    assert cls in (UP, DOWN), "這天不是高點或低點"
    amp = float(label_amp(df["close"], y).iloc[i])
    c = df["close"].to_numpy()
    chg = np.diff(c[i - 6:i + 6]) / c[i - 6:i + 5] * 100                # t-5 … t+5 每天的收盤漲跌
    want = np.r_[np.full(6, 1 if cls == DOWN else -1), np.full(5, -1 if cls == DOWN else 1)]
    ok = np.sign(chg) == want
    ok[0] = False                                                        # t-5 那天的漲跌不算(比的是 t-6)
    left_ok, right_ok = int(ok[1:6].sum()), int(ok[6:].sum())
    keep = left_ok >= a.min_side and right_ok >= a.min_side
    nm = {DOWN: "高點", UP: "低點"}[cls]
    fig, ax = plt.subplots(figsize=(13, 7.5), dpi=170, facecolor="white")
    EW.draw(ax, df, i, cls, f"{a.ticker[:4]} {ticker_names().get(a.ticker, '')} {a.date}:{nm},"
            f"對方向 前 {left_ok} + 後 {right_ok} 天 → 做法 2(每邊 ≥ {a.min_side} 天){'保留' if keep else '刪掉'}",
            f"幅度 {amp:.2f}%", two_lines=True)
    ax.title.set_color(OK_C if keep else BAD_C)
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi + (hi - lo) * 0.22)
    top = hi + (hi - lo) * 0.06
    for k in range(11):
        if k == 0:
            ax.text(k, top, f"{chg[k]:+.2f}%\n(不算)", ha="center", va="bottom", fontsize=10, color=EW.MUTED)
            continue
        side_ok = "對" if ok[k] else "不對"
        ax.text(k, top, f"{chg[k]:+.2f}%\n{side_ok}", ha="center", va="bottom", fontsize=10.5,
                color=OK_C if ok[k] else BAD_C, fontweight="bold")
    ax.text(2.5, hi + (hi - lo) * 0.19, f"前 5 天要「{'漲' if cls == DOWN else '跌'}」:{left_ok} 天對", ha="center", fontsize=11, color=EW.INK)
    ax.text(8, hi + (hi - lo) * 0.19, f"後 5 天要「{'跌' if cls == DOWN else '漲'}」:{right_ok} 天對", ha="center", fontsize=11, color=EW.INK)
    for k in range(11):
        o, h, l, cl = df.iloc[i - 5 + k][["open", "high", "low", "close"]]
        ax.text(k, l - (hi - lo) * 0.012, f"{cl:.1f}", ha="center", va="top", fontsize=8.5, color=EW.INK2)
    fig.text(0.01, 0.005, "每根 K 棒上方 = 當天收盤比前一天的漲跌;下方數字 = 收盤價(還原價)。t-5 那天的漲跌比的是 t-6,不算進前 5 天。",
             fontsize=9.5, color=EW.INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = os.path.join(ML.OUT, f"window_{a.ticker[:4]}_{a.date}.png")
    fig.savefig(out, facecolor="white")
    print(out, left_ok, right_ok, round(amp, 2))


if __name__ == "__main__":
    main()
