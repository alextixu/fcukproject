"""訓練年份裡幅度最大 / 最小的高點與低點,各畫 11 天 K 線(2026-11-02 使用者要求)。

幅度 = 兩邊較小那邊(paper_aeocsvm.label_amp):
  高點 = min(從前 5 天最低收盤漲到 t, 從 t 跌到後 5 天最低收盤);低點 = min(從前 5 天最高收盤跌到 t, 從 t 漲到後 5 天最高收盤)
四張:最高的高點(幅度最大)、最低的高點(幅度最小)、最低的低點(幅度最大)、最高的低點(幅度最小);同分取日期最早的。
訓練年份 = 測 --test-year 時主軸實際用的訓練資料(前 4 年,剔除最後 5 個交易日)。
用法: python method_kline_peak/report/extreme_windows.py [--test-year 2024]
輸出: results/label_extremes_<起>_<迄>.png
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
from export_windows import ticker_names  # noqa: E402
from feasibility import START, END, load_pool, clean  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402

INK, INK2, MUTED, KNOWN, BAND = "#13202A", "#47545F", "#7A8691", "#EEF2F5", "#E2E8ED"
HI, LO = "#EB6834", "#2A78D6"
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False


def pct(v):
    return "0.00%" if abs(v) < 0.005 else f"{v:+.2f}%"


def draw(ax, df, i, cls, title, sub):
    a, b = i - 5, i + 5
    w = df.iloc[a:b + 1]
    lo, hi = w["low"].min(), w["high"].max()
    pad = (hi - lo) * 0.14 or w["close"].iloc[5] * 0.01
    lo, hi = lo - pad, hi + pad
    ax.add_patch(Rectangle((-0.5, lo), 6, hi - lo, color=KNOWN, zorder=0))
    ax.add_patch(Rectangle((4.5, lo), 1, hi - lo, facecolor=BAND, edgecolor=INK, lw=1, zorder=0.5))
    col = HI if cls == DOWN else LO
    C = w["close"].to_numpy()
    t, L, R = C[5], C[:5], C[6:]
    if cls == DOWN:
        lref, rref = L.min(), R.min()
        left, right = (t / lref - 1) * 100, (1 - rref / t) * 100
        ltxt, rtxt = f"前 5 天最低 → t {pct(left)}", f"t → 後 5 天最低 {pct(-right)}"
    else:
        lref, rref = L.max(), R.max()
        left, right = (1 - t / lref) * 100, (rref / t - 1) * 100
        ltxt, rtxt = f"前 5 天最高 → t {pct(-left)}", f"t → 後 5 天最高 {pct(right)}"
    ax.axhline(t, color=MUTED, ls="--", lw=0.9, zorder=1)
    ax.plot([-0.4, 4.4], [lref, lref], color=col, ls=":", lw=1.4, zorder=1)
    ax.plot([5.6, 10.4], [rref, rref], color=col, ls=":", lw=1.4, zorder=1)
    for k, (o, h, l, c) in enumerate(w[["open", "high", "low", "close"]].to_numpy()):
        e, lw = (col, 2.2) if k == 5 else (INK2, 1.1)
        ax.plot([k, k], [l, h], color=e, lw=lw, zorder=2)
        ax.add_patch(Rectangle((k - 0.3, min(o, c)), 0.6, max(abs(c - o), (hi - lo) * 0.004),
                               facecolor="white" if c >= o else e, edgecolor=e, lw=lw, zorder=3))
    ax.plot(range(11), C, color=col, lw=1, alpha=0.35, zorder=1.5)
    ax.set_xlim(-0.7, 10.7)
    ax.set_ylim(lo, hi)
    ax.set_xticks(range(11))
    ax.set_xticklabels([f"t{k - 5:+d}" if k != 5 else "t" for k in range(11)], fontsize=10, color=MUTED)
    ax.tick_params(axis="y", labelsize=9, colors=MUTED)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(title, loc="left", fontsize=13, color=INK, fontweight="bold", pad=24)
    ax.text(0, 1.01, f"{ltxt}、{rtxt} → {sub}", transform=ax.transAxes, fontsize=10.5, color=INK2, va="bottom", ha="left")
    return min(left, right)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-year", type=int, default=2024)
    test_year = ap.parse_args().test_year
    data = load_pool(ML.POOL, START, END)
    panel, _ = ML.build_panel(data, 6, [])
    tr = WF.year_split(panel, test_year)["train"]
    y0, y1 = tr.date.dt.year.min(), tr.date.dt.year.max()
    names = ticker_names()
    picks = []
    for cls, big, small in ((DOWN, "最高的高點(幅度最大)", "最低的高點(幅度最小)"), (UP, "最低的低點(幅度最大)", "最高的低點(幅度最小)")):
        s = tr[tr.y == cls].sort_values(["amp", "date"])
        n_min = int((s.amp == s.amp.iloc[0]).sum())
        picks += [(cls, big, s.iloc[-1], None), (cls, small, s.iloc[0], n_min)]
    fig, axes = plt.subplots(2, 2, figsize=(15, 10.5), dpi=160, facecolor="white")
    order = [picks[0], picks[1], picks[2], picks[3]]
    for ax, (cls, title, r, n_min) in zip(axes.ravel(), order):
        df = clean(data[r.ticker])
        i = df.index.get_loc(r.date)
        nm = names.get(r.ticker, r.ticker)
        tie = f"(幅度同為 0 的共 {n_min} 個,取最早的)" if n_min and n_min > 1 else ""
        amp = draw(ax, df, i, cls, f"{title}:{r.ticker[:4]} {nm} {r.date:%Y-%m-%d}", f"幅度 {r.amp:.2f}%{tie}")
        assert abs(amp - r.amp) < 1e-6
    fig.suptitle(f"訓練年份 {y0}–{y1}(測 {test_year} 的訓練資料)的極端例子:高點 {(tr.y == DOWN).sum():,} 個、低點 {(tr.y == UP).sum():,} 個",
                 x=0.02, ha="left", fontsize=15, color=INK, y=0.995)
    fig.text(0.02, 0.006, "灰底 = t 日收盤時看得到的 6 天,框 = t 日;虛線 = t 日收盤,點線 = 算幅度用的兩邊最低(高點)/ 最高(低點)收盤;"
             "空心 K 棒 = 收漲,實心 = 收跌。", fontsize=10, color=INK2)
    fig.subplots_adjust(left=0.04, right=0.99, top=0.88, bottom=0.07, hspace=0.42, wspace=0.12)
    out = os.path.join(ML.OUT, f"label_extremes_{y0}_{y1}.png")
    fig.savefig(out, facecolor="white")
    for cls, title, r, _ in order:
        print(title, r.ticker, names.get(r.ticker, ""), r.date.date(), round(float(r.amp), 2))
    print(out)


if __name__ == "__main__":
    main()
