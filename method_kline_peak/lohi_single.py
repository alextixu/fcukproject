"""單一股票「判低點買、判高點賣」回測(2026-11-02 使用者要求):兩個方法 × 一年。

模型:目前的設定(34 檔一起訓練、訓練門檻 0%、前 4 年訓練、種子 42),只取這一檔的判斷來交易。
交易:沒持有時 t 日判低點 → t+1 開盤用全部資金買進;持有中 m 日判高點 → m+1 開盤全部賣出;
      沒有最長持有,持有中再判低點不加碼,沒持有時判高點不理會;期末還沒賣的用最後一天收盤結清。
      成本 買 0.1425% + 賣 0.1425% + 稅 0.3%;另列成本設 0 的結果。引擎 = backtest_years.simulate(hold=None, exit_on_high=True)。
用法: python method_kline_peak/lohi_single.py 2379.TW 2025
輸出: results/lohi_<代號>_<年>.json、results/lohi_<代號>_<年>.png
"""
import argparse
import json
import os
import sys

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

COLS = ["date", "ticker", "score"]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
HI, LO, HOLD = "#eb6834", "#2a78d6", "#1baf7a"
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
    prices = {tk: clean(data[tk])[["open", "close"]]}
    rule = BY.TradeRule(slots=1, hold=None, exit_on_high=True)
    no_cost = BY.TradeRule(slots=1, hold=None, exit_on_high=True, **BY.NO_COST)
    res, sims, sigs = {"ticker": tk, "year": y, "rule": "判低點 → t+1 開盤買;判高點 → 隔天開盤賣;沒有最長持有", "results": {}}, {}, {}
    for name in T.SOURCES:
        sig, _ = WF.run_year(panel, fc, y, BY.SOURCE_FACTORIES[name]())
        s = sig[sig.ticker == tk]
        lo, hi = s[s.pred == UP][COLS], s[s.pred == DOWN][COLS]
        sim = BY.simulate(prices, lo, start, end, rule, sells=hi)
        gross = BY.simulate(prices, lo, start, end, no_cost, sells=hi)
        tr = sim["trades"]
        st = BY.stats(sim["equity"], tr)
        idx = prices[tk].loc[start:end].index
        res["results"][name] = {
            "n_low_days": len(lo), "n_high_days": len(hi), **st, "gross_return_pct": BY.stats(gross["equity"])["total_return_pct"],
            "trades": [{"entry": str(t.entry.date()), "exit": str(t.exit.date()), "buy_px": round(t.buy_px, 2), "sell_px": round(t.sell_px, 2),
                        "hold_days": int(idx.get_loc(t.exit) - idx.get_loc(t.entry) + 1), "net_ret_pct": round(t.net_ret * 100, 2), "how": t.how}
                       for t in tr.itertuples()],
            "curve": {d.strftime("%Y-%m-%d"): round(v / rule.init_cash * 100 - 100, 3) for d, v in sim["equity"].items()},
            "curve_gross": {d.strftime("%Y-%m-%d"): round(v / rule.init_cash * 100 - 100, 3) for d, v in gross["equity"].items()}}
        sims[name], sigs[name] = sim, s
        r = res["results"][name]
        print(f"{name:<12} 扣成本 {r['total_return_pct']:+7.2f}%  沒扣 {r['gross_return_pct']:+7.2f}%  {r['n_trades']} 筆,勝 {r['win_rate_pct']}%,"
              f"回撤 {r['max_dd_pct']}%  判低點 {len(lo)} 天、判高點 {len(hi)} 天", flush=True)
        for t in r["trades"]:
            print(f"    {t['entry']} 買 {t['buy_px']:.1f} → {t['exit']} 賣 {t['sell_px']:.1f}  {t['hold_days']} 天  {t['net_ret_pct']:+.2f}%  {t['how']}")
    base = os.path.join(ML.OUT, f"lohi_{tk[:4]}_{y}")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    nm = ticker_names().get(tk, tk)
    close = clean(data[tk])["close"].loc[start:end]
    pad = (close.max() - close.min()) * 0.03
    fig, axes = plt.subplots(4, 1, figsize=(17, 16), dpi=150, sharex=True, facecolor="white",
                             gridspec_kw={"height_ratios": [1.3, 0.7, 1.3, 0.7], "hspace": 0.45})
    for k, name in enumerate(T.SOURCES):
        ax, ax2 = axes[2 * k], axes[2 * k + 1]
        s, r = sigs[name].set_index("date"), res["results"][name]
        ax.plot(close.index, close.values, color="#9a9994", lw=1.2, zorder=1)
        lo_d, hi_d = s.index[s.pred == UP], s.index[s.pred == DOWN]
        ax.scatter(lo_d, close.reindex(lo_d) - pad, marker="^", s=28, color=LO, alpha=0.55, zorder=2, label=f"判低點 {len(lo_d)} 天")
        ax.scatter(hi_d, close.reindex(hi_d) + pad, marker="v", s=28, color=HI, alpha=0.55, zorder=2, label=f"判高點 {len(hi_d)} 天")
        for t in sims[name]["trades"].itertuples():
            ax.axvspan(t.entry, t.exit, color=HOLD, alpha=0.18, lw=0, zorder=0)
            ax.scatter([t.entry], [t.buy_px], marker="o", s=60, color=HOLD, edgecolor="white", zorder=4)
            ax.scatter([t.exit], [t.sell_px], marker="X", s=70, color="#b3261e", edgecolor="white", zorder=4)
            ax.annotate(f"{t.net_ret * 100:+.1f}%", (t.entry + (t.exit - t.entry) / 2, close.max() + pad * 2.2), ha="center",
                        va="bottom", rotation=90, fontsize=8.5, color=INK)
        ax.set_ylim(close.min() - pad * 3, close.max() + pad * 8)
        ax.set_title(f"{name}:買 {r['n_trades']} 次(綠點 = 買進、紅 X = 賣出、綠底 = 持有期間,上方 = 該筆扣成本報酬)",
                     loc="left", fontsize=12.5, color=INK, fontweight="bold")
        ax.legend(frameon=True, facecolor="white", edgecolor=GRID, fontsize=10, labelcolor=INK, loc="lower right", ncol=2)
        ax.set_ylabel("收盤(還原價)", color=MUTED, fontsize=10)
        for key, ls, lab in (("curve_gross", "--", "沒扣成本"), ("curve", "-", "扣成本")):
            cv = r[key]
            xs = [pd_ts for pd_ts in close.index if pd_ts.strftime("%Y-%m-%d") in cv]
            ax2.plot(xs, [cv[x.strftime("%Y-%m-%d")] for x in xs], color=LO if k == 0 else HI, lw=2, ls=ls, label=lab)
        ax2.axhline(0, color=MUTED, lw=0.8, ls=":")
        ax2.set_title(f"{name} 資產:扣成本 {r['total_return_pct']:+.1f}%、沒扣成本 {r['gross_return_pct']:+.1f}%,最大回撤 {r['max_dd_pct']:.1f}%",
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
    fig.suptitle(f"{tk[:4]} {nm} {y}:判低點買、判高點賣(只交易這一檔、100 萬全部投入、沒有最長持有、成本 0.585%)",
                 x=0.01, ha="left", fontsize=15, color=INK, y=0.995)
    fig.savefig(base + ".png", facecolor="white", bbox_inches="tight")
    print(base + ".png")


if __name__ == "__main__":
    main()
