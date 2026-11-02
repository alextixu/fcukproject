"""backtest_top3 結果檔的資產曲線:列 = 方法,欄 = 年;實線 = 扣成本、虛線 = 沒扣成本(相對每年 100 萬的報酬 %)。
用法: python method_kline_peak/report/equity_curves.py results/backtest_long_only_side3.json [--title 每邊至少 3 天對方向]
輸出: 同名 .png(例:results/backtest_long_only_side3_curves.png)
"""
import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

INK, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COLORS = {"主軸": ("#2a78d6", "#86b6ef"), "Stacking 邏輯迴歸": ("#eb6834", "#f0956b")}
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--title", default="")
    a = ap.parse_args()
    res = json.load(open(a.path, encoding="utf-8"))
    years = list(res["years"])
    methods = [m for m in COLORS if m in res["years"][years[0]]]
    fig, axes = plt.subplots(len(methods), len(years), figsize=(6.2 * len(years), 4.6 * len(methods)), dpi=160,
                             facecolor=SURF, sharey=True, squeeze=False)
    for r, m in enumerate(methods):
        dark, light = COLORS[m]
        for c, y in enumerate(years):
            ax = axes[r, c]
            row = res["years"][y][m]
            for key, col, ls, lab in (("沒扣成本", light, "--", "沒扣成本"), ("扣成本", dark, "-", "扣成本")):
                cv = pd.Series(row[key]["curve"])
                cv.index = pd.to_datetime(cv.index)
                ax.plot(cv.index, cv.values, color=col, lw=2, ls=ls, label=lab)
                ax.annotate(f"{cv.iloc[-1]:+.1f}%", (cv.index[-1], cv.iloc[-1]), xytext=(4, 0), textcoords="offset points",
                            va="center", fontsize=10, color=INK)
            ax.axhline(0, color=MUTED, lw=0.8, ls=":")
            ax.set_facecolor(SURF)
            for k in ("top", "right"):
                ax.spines[k].set_visible(False)
            for k in ("left", "bottom"):
                ax.spines[k].set_color(GRID)
            ax.tick_params(colors=MUTED, labelsize=9.5, length=0)
            ax.grid(axis="y", color=GRID, lw=0.8)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m 月"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 3, 5, 7, 9, 11]))
            n = row["扣成本"]
            ax.set_title(f"{m} · {y}{'(1–9 月)' if y == '2026' else ''}\n扣成本 {n['total_return_pct']:+.1f}%,"
                         f"{n['n_trades']} 筆,勝 {n['win_rate_pct']}%,最大回撤 {n['max_dd_pct']:.1f}%",
                         loc="left", fontsize=11.5, color=INK, pad=8)
            if c == 0:
                ax.set_ylabel("相對年初 100 萬的報酬(%)", color=MUTED, fontsize=10)
            if r == 0 and c == 0:
                ax.legend(frameon=False, fontsize=10, labelcolor=INK, loc="lower left")
    t = f"資產曲線:{a.title}" if a.title else "資產曲線"
    fig.suptitle(f"{t}({len(res["pool"])} 檔、只做多前 3 檔、每檔 1/3、t+1 開盤買、t+5 收盤賣;每年獨立 100 萬;實線 = 扣成本 0.585%、虛線 = 沒扣成本)",
                 x=0.01, ha="left", fontsize=14, color=INK, y=0.995)
    fig.tight_layout(rect=(0, 0, 0.985, 0.95), h_pad=3, w_pad=2.5)
    out = os.path.splitext(a.path)[0] + "_curves.png"
    fig.savefig(out, facecolor=SURF)
    print(out)


if __name__ == "__main__":
    main()
