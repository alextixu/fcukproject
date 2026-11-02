"""單一股票反手交易回測:判高點 → 做多、判低點 → 反手做空(2026-11-02 使用者要求),兩個方法 × 一年。

模型:目前的設定(34 檔一起訓練、訓練門檻 0%、前 4 年訓練、種子 42),只取這一檔的判斷。交易規則見 reversal.py;
100 萬全部投入、成本 0.585%(另列成本設 0)。
用法: python method_kline_peak/reversal_single.py 2379.TW 2025
輸出: results/reversal_<代號>_<年>.json、results/reversal_<代號>_<年>.png
"""
import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import backtest_years as BY  # noqa: E402
import backtest_top3 as T  # noqa: E402
from export_windows import ticker_names  # noqa: E402
from feasibility import END, clean  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402
from reversal import simulate_reversal  # noqa: E402

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
HI, LO, LONG_C, SHORT_C = "#eb6834", "#2a78d6", "#1baf7a", "#e34948"
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("year", type=int)
    a = ap.parse_args()
    tk, y = a.ticker, a.year
    data, panel, fc, _ = T.load()
    start, end = f"{y}-01-01", min(f"{y}-12-31", END)
    px = clean(data[tk])[["open", "close"]]
    res = {"ticker": tk, "year": y, "rule": "判高點 → 隔天開盤做多;做多中判低點 → 隔天開盤賣出並反手做空;做空中判高點 → 回補並反手做多",
           "results": {}}
    sims, sigs = {}, {}
    for name in T.SOURCES:
        sig, _ = WF.run_year(panel, fc, y, BY.SOURCE_FACTORIES[name]())
        s = sig[sig.ticker == tk].set_index("date")
        sim = simulate_reversal(px, s.pred, start, end, BY.TradeRule())
        gross = simulate_reversal(px, s.pred, start, end, BY.TradeRule(**BY.NO_COST))
        tr = sim["trades"]
        st = BY.stats(sim["equity"], tr)
        idx = px.loc[start:end].index
        by_side = {sd: {"n": int((tr.side == sd).sum()), "win_pct": round(float((tr[tr.side == sd].net_ret > 0).mean()) * 100, 1)
                        if (tr.side == sd).any() else None, "pnl_pct_of_init": round(float(tr[tr.side == sd].pnl.sum()) / 1e4, 2)}
                   for sd in ("做多", "做空")}
        res["results"][name] = {
            "n_low_days": int((s.pred == UP).sum()), "n_high_days": int((s.pred == DOWN).sum()), **st,
            "gross_return_pct": BY.stats(gross["equity"])["total_return_pct"], "by_side": by_side,
            "trades": [{"side": t.side, "entry": str(t.entry.date()), "exit": str(t.exit.date()), "entry_px": round(t.entry_px, 2),
                        "exit_px": round(t.exit_px, 2), "hold_days": int(idx.get_loc(t.exit) - idx.get_loc(t.entry) + 1),
                        "net_ret_pct": round(t.net_ret * 100, 2), "how": t.how} for t in tr.itertuples()],
            "curve": {d.strftime("%Y-%m-%d"): round(v / 1e4 - 100, 3) for d, v in sim["equity"].items()},
            "curve_gross": {d.strftime("%Y-%m-%d"): round(v / 1e4 - 100, 3) for d, v in gross["equity"].items()}}
        sims[name], sigs[name] = sim, s
        r = res["results"][name]
        print(f"{name:<12} 扣成本 {r['total_return_pct']:+7.2f}%  沒扣 {r['gross_return_pct']:+7.2f}%  {r['n_trades']} 筆,勝 {r['win_rate_pct']}%,"
              f"回撤 {r['max_dd_pct']}%  做多 {by_side['做多']}  做空 {by_side['做空']}", flush=True)
        for t in r["trades"]:
            print(f"    {t['side']} {t['entry']} {t['entry_px']:.1f} → {t['exit']} {t['exit_px']:.1f}  {t['hold_days']} 天  {t['net_ret_pct']:+.2f}%  {t['how']}")
    base = os.path.join(ML.OUT, f"reversal_{tk[:4]}_{y}")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    nm = ticker_names().get(tk, tk)
    close = px["close"].loc[start:end]
    pad = (close.max() - close.min()) * 0.03
    fig, axes = plt.subplots(4, 1, figsize=(17, 16), dpi=150, sharex=True, facecolor="white",
                             gridspec_kw={"height_ratios": [1.3, 0.7, 1.3, 0.7], "hspace": 0.45})
    for k, name in enumerate(T.SOURCES):
        ax, ax2 = axes[2 * k], axes[2 * k + 1]
        s, r = sigs[name], res["results"][name]
        ax.plot(close.index, close.values, color="#9a9994", lw=1.2, zorder=1)
        lo_d, hi_d = s.index[s.pred == UP], s.index[s.pred == DOWN]
        ax.scatter(lo_d, close.reindex(lo_d) - pad, marker="^", s=26, color=LO, alpha=0.55, zorder=2, label=f"判低點 {len(lo_d)} 天")
        ax.scatter(hi_d, close.reindex(hi_d) + pad, marker="v", s=26, color=HI, alpha=0.55, zorder=2, label=f"判高點 {len(hi_d)} 天")
        for t in sims[name]["trades"].itertuples():
            col = LONG_C if t.side == "做多" else SHORT_C
            ax.axvspan(t.entry, t.exit, color=col, alpha=0.16, lw=0, zorder=0)
            ax.annotate(f"{'多' if t.side == '做多' else '空'} {t.net_ret * 100:+.1f}%", (t.entry + (t.exit - t.entry) / 2, close.max() + pad * 2.2),
                        ha="center", va="bottom", rotation=90, fontsize=8.5, color=INK)
        ax.set_ylim(close.min() - pad * 3, close.max() + pad * 10)
        b = r["by_side"]
        ax.set_title(f"{name}:做多 {b['做多']['n']} 筆(綠底)、做空 {b['做空']['n']} 筆(紅底);上方 = 該筆扣成本報酬",
                     loc="left", fontsize=12.5, color=INK, fontweight="bold")
        ax.legend(frameon=True, facecolor="white", edgecolor=GRID, fontsize=10, labelcolor=INK, loc="lower right", ncol=2)
        ax.set_ylabel("收盤(還原價)", color=MUTED, fontsize=10)
        for key, ls, lab in (("curve_gross", "--", "沒扣成本"), ("curve", "-", "扣成本")):
            cv = r[key]
            xs = [d for d in close.index if d.strftime("%Y-%m-%d") in cv]
            ax2.plot(xs, [cv[d.strftime("%Y-%m-%d")] for d in xs], color=LO if k == 0 else HI, lw=2, ls=ls, label=lab)
        ax2.axhline(0, color=MUTED, lw=0.8, ls=":")
        ax2.set_title(f"{name} 資產:扣成本 {r['total_return_pct']:+.1f}%、沒扣成本 {r['gross_return_pct']:+.1f}%,最大回撤 {r['max_dd_pct']:.1f}%"
                      f"(做多損益 {b['做多']['pnl_pct_of_init']:+.1f}、做空損益 {b['做空']['pnl_pct_of_init']:+.1f} 個百分點)",
                      loc="left", fontsize=11.5, color=INK)
        ax2.set_ylabel("報酬(%)", color=MUTED, fontsize=10)
        ax2.legend(frameon=False, fontsize=10, labelcolor=INK, loc="upper left", ncol=2)
        for a_ in (ax, ax2):
            for kk in ("top", "right"):
                a_.spines[kk].set_visible(False)
            for kk in ("left", "bottom"):
                a_.spines[kk].set_color(GRID)
            a_.tick_params(colors=MUTED, labelsize=10, length=0)
            a_.grid(axis="y", color=GRID, lw=0.8)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m 月"))
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator())
    fig.suptitle(f"{tk[:4]} {nm} {y}:判高點做多、判低點反手做空(只交易這一檔、100 萬全部投入、隔天開盤執行、成本 0.585%)",
                 x=0.01, ha="left", fontsize=15, color=INK, y=0.995)
    fig.savefig(base + ".png", facecolor="white", bbox_inches="tight")
    print(base + ".png")


if __name__ == "__main__":
    main()
