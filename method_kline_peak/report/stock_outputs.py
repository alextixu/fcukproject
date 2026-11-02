"""一檔股票一整年每天的模型輸出(2026-11-02 使用者要求)。

目前的設定:34 檔、訓練門檻 0%、前 4 年訓練(主軸;Stacking = 前 3 年 A + 第 4 年 B)、種子 42。
上:收盤價與真實標籤(▼ 真高點、▲ 真低點)。中、下:主軸、Stacking 邏輯迴歸每天的判斷
(▼ 判高點、▲ 判低點;實心 = 和真實標籤相同、空心 = 判錯),綠色區塊 = 前 3 檔只做多回測裡這檔真的被買進的持有期間。
用法: python method_kline_peak/report/stock_outputs.py 2379.TW 2024
輸出: results/outputs_<代號>_<年>.png、results/outputs_<代號>_<年>.csv(每天一列)
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import backtest_years as BY  # noqa: E402
import backtest_top3 as T  # noqa: E402
from export_windows import ticker_names  # noqa: E402
from feasibility import END, clean  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
HI, LO, BUY = "#eb6834", "#2a78d6", "#1baf7a"
LBL = {UP: "低點", FLAT: "非極值", DOWN: "高點"}
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("year", type=int)
    a = ap.parse_args()
    tk, y = a.ticker, a.year
    data, panel, fc, prices = T.load()
    start, end = f"{y}-01-01", min(f"{y}-12-31", END)
    px = clean(data[tk]).loc[start:end]
    rule = BY.TradeRule(slots=3)
    out = pd.DataFrame({"close": px["close"]})
    trades, info = {}, {}
    for name in T.SOURCES:
        sig, _ = WF.run_year(panel, fc, y, BY.SOURCE_FACTORIES[name]())
        sim = BY.simulate(prices, sig[sig.pred == UP][T.COLS], start, end, rule)
        trades[name] = sim["trades"][sim["trades"].ticker == tk]
        s = sig[sig.ticker == tk].set_index("date")
        out["真實標籤"] = s["y"].map(LBL)
        out[f"{name} 判斷"] = s["pred"].map(LBL)
        out[f"{name} 分數"] = s["score"].round(4)
        out[f"{name} 買進日(t+1 開盤)"] = out.index.isin(trades[name].entry)
        info[name] = (s, sim["trades"])
    out.index.name = "date"
    base = os.path.join(ML.OUT, f"outputs_{tk[:4]}_{y}")
    out.to_csv(base + ".csv", encoding="utf-8-sig")

    nm = ticker_names().get(tk, tk)
    fig, axes = plt.subplots(3, 1, figsize=(18, 13), dpi=160, sharex=True, facecolor="white",
                             gridspec_kw={"height_ratios": [1, 1, 1], "hspace": 0.32})
    yv = out["真實標籤"]
    for ax in axes:
        ax.plot(out.index, out.close, color="#9a9994", lw=1.2, zorder=1)
        for k in ("top", "right"):
            ax.spines[k].set_visible(False)
        for k in ("left", "bottom"):
            ax.spines[k].set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=10, length=0)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_ylabel("收盤(還原價)", color=MUTED, fontsize=10)
    pad = (out.close.max() - out.close.min()) * 0.03
    ax = axes[0]
    h, l = out[yv == "高點"], out[yv == "低點"]
    ax.scatter(h.index, h.close + pad, marker="v", s=46, color=HI, zorder=3, label=f"真高點 {len(h)} 個")
    ax.scatter(l.index, l.close - pad, marker="^", s=46, color=LO, zorder=3, label=f"真低點 {len(l)} 個")
    ax.set_title(f"{tk[:4]} {nm} {y}:收盤與真實標籤(11 天收盤最高 / 最低)", loc="left", fontsize=13.5, color=INK, fontweight="bold")
    ax.legend(frameon=True, facecolor="white", edgecolor=GRID, fontsize=10.5, labelcolor=INK, loc="lower right", ncol=2)
    for ax, name in zip(axes[1:], T.SOURCES):
        s, all_tr = info[name]
        p = out[f"{name} 判斷"]
        for lab, mk, col, off in (("高點", "v", HI, pad), ("低點", "^", LO, -pad)):
            hit = out[(p == lab) & (yv == lab)]
            miss = out[(p == lab) & (yv != lab)]
            ax.scatter(hit.index, hit.close + off, marker=mk, s=50, color=col, zorder=3, label=f"判{lab}·判對 {len(hit)}")
            ax.scatter(miss.index, miss.close + off, marker=mk, s=50, facecolors="white", edgecolors=col, lw=1.3, zorder=3,
                       label=f"判{lab}·判錯 {len(miss)}")
        tr = trades[name]
        for t in tr.itertuples():
            ax.axvspan(t.entry, t.exit, color=BUY, alpha=0.18, lw=0, zorder=0)
            ax.annotate(f"{t.net_ret * 100:+.1f}%", (t.entry, out.close.max() + pad * 2), fontsize=8.5, color=INK, rotation=90,
                        va="bottom", ha="center")
        ax.set_ylim(out.close.min() - pad * 3, out.close.max() + pad * 9)
        tot = tr.net_ret.add(1).prod() - 1 if len(tr) else 0
        ax.set_title(f"{name}:判低點 {int((p == '低點').sum())} 天、判高點 {int((p == '高點').sum())} 天;"
                     f"前 3 檔回測裡這檔被買 {len(tr)} 次(綠色 = 持有期間,上方數字 = 該筆扣成本報酬;全部 34 檔共 {len(all_tr)} 筆)",
                     loc="left", fontsize=12, color=INK, fontweight="bold")
        ax.legend(frameon=True, facecolor="white", edgecolor=GRID, fontsize=10, labelcolor=INK, loc="lower right", ncol=2)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m 月"))
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator())
    fig.suptitle(f"{tk[:4]} {nm} {y} 每天的模型輸出(34 檔、訓練門檻 0%、前 4 年訓練、種子 42;只做多前 3 檔、t+1 開盤買、t+5 收盤賣)",
                 x=0.01, ha="left", fontsize=15, color=INK, y=0.995)
    fig.text(0.01, 0.005, "▼ 判高點、▲ 判低點:實心 = 和真實標籤相同、空心 = 判錯。只有判低點會買;同一天訊號多於空位時挑分數最高的,所以判低點不一定買得到。",
             fontsize=10.5, color=MUTED)
    fig.savefig(base + ".png", facecolor="white", bbox_inches="tight")
    for name in T.SOURCES:
        tr = trades[name]
        print(name, "判低點", int((out[f"{name} 判斷"] == "低點").sum()), "判高點", int((out[f"{name} 判斷"] == "高點").sum()),
              "買進", len(tr), "各筆", [round(x * 100, 2) for x in tr.net_ret])
    print(base + ".png")


if __name__ == "__main__":
    main()
