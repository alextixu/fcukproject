"""南電 2024:比較圖那 8 列各自做「低點進場、高點出場」的單一股票回測(2026-11-09 使用者要求;不訓練新模型)。

判斷同 compare_postproc.py(TW200 168 檔、訓練門檻 0%、種子 42;2-50 先對 168 檔套規則再取南電)。
8 列:真實標籤(事先知道答案,上限)、A0、1a(用到未來)、1b、2-50、確認 k = 1、2、3。
訊號出現日:1–5 列 = t;確認規則 = t+k(確認那天)。
交易(同 lohi_single.py,引擎 backtest_years.simulate(hold=None, exit_on_high=True)):只交易南電、100 萬全部投入;
  沒持有時低點訊號出現日的隔天開盤全部買進;持有中高點訊號出現日的隔天開盤全部賣出;沒有最長持有;
  持有中再出現低點不加碼、沒持有時高點不理會;年底最後一天收盤平倉;成本 0.585%,另列沒扣成本。
基準:南電 2024 買進持有(第一個交易日開盤買、最後一天收盤賣,扣成本)。
用法: python method_kline_peak/report/lohi_compare.py
輸出: results/lohi_compare_8046_2024_tw200_main.png、_stack.png、results/lohi_compare_8046_2024_tw200.json
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import backtest_years as BY  # noqa: E402
import postproc_signals as PP  # noqa: E402
import confirm_signals as CS  # noqa: E402
import compare_postproc as CP  # noqa: E402
from export_windows import ticker_names  # noqa: E402
from feasibility import END, clean  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402

POOL, YEAR, TK = CP.POOL, CP.YEAR, CP.TK
INK, MUTED, GRID, HOLDC = "#0b0b0b", "#52514e", "#e4e3df", "#1baf7a"
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False
ROWS = [("真實標籤(事先知道答案,用到未來資訊,實際用不了)", "truth", 0)] + [
    (t.replace("(用到未來資訊,實際用不了)", "(用到未來資訊,實際用不了)"), r, k) for t, r, k in CP.RULES]


def main():
    data = ML.load_data(pool=POOL)
    panel, fc = ML.build_panel(data, 6, [])
    px = {tk: clean(df)[["open", "close"]] for tk, df in data.items()}
    start, end = f"{YEAR}-01-01", min(f"{YEAR}-12-31", END)
    prices = {TK: px[TK]}
    idx = px[TK].index
    rule = BY.TradeRule(slots=1, hold=None, exit_on_high=True)
    no_cost = BY.TradeRule(slots=1, hold=None, exit_on_high=True, **BY.NO_COST)
    p = px[TK].loc[start:end]
    bh = p["close"].iloc[-1] * (1 - rule.sell_fee - rule.tax) / (p["open"].iloc[0] * (1 + rule.buy_fee)) * 100 - 100
    bh_gross = p["close"].iloc[-1] / p["open"].iloc[0] * 100 - 100
    res = {"pool": POOL, "year": YEAR, "ticker": TK, "buy_hold_pct": round(bh, 2), "buy_hold_gross_pct": round(bh_gross, 2), "methods": {}}
    nm = ticker_names().get(TK, TK)
    close = p["close"]
    for name, tag in CP.FILES.items():
        sig, _ = WF.run_year(panel, fc, YEAR, BY.SOURCE_FACTORIES[name]())
        df = sig.sort_values(["ticker", "date"]).reset_index(drop=True)
        rows = np.flatnonzero(df["ticker"].to_numpy() == TK)
        s = df.iloc[rows]
        res["methods"][name], sims = {}, {}
        for title, rl, k in ROWS:
            if rl == "truth":
                pred = s["y"].to_numpy()
            elif rl is None:
                pred = CS.confirm(df, k, px)[0][rows]
            else:
                pred = PP.apply_rule(df, rl)[rows]
            pos = idx.get_indexer(s["date"]) + k                     # 訊號出現日 = t(+k)
            ok = pos < len(idx)
            day = pd.DatetimeIndex(idx[np.minimum(pos, len(idx) - 1)])
            mk = lambda cls: pd.DataFrame({"date": day[(pred == cls) & ok], "ticker": TK, "score": 0.0})  # noqa: E731
            lo, hi = mk(UP), mk(DOWN)
            lo, hi = lo[lo.date <= pd.Timestamp(end)], hi[hi.date <= pd.Timestamp(end)]
            sim = BY.simulate(prices, lo, start, end, rule, sells=hi)
            gross = BY.simulate(prices, lo, start, end, no_cost, sells=hi)
            tr = sim["trades"]
            st = BY.stats(sim["equity"], tr)
            hold = [int(idx.get_loc(t.exit) - idx.get_loc(t.entry) + 1) for t in tr.itertuples()]
            r = {"扣成本_pct": st["total_return_pct"], "沒扣成本_pct": BY.stats(gross["equity"])["total_return_pct"],
                 "n_trades": st["n_trades"], "win_rate_pct": st["win_rate_pct"], "avg_hold_days": round(float(np.mean(hold)), 1) if hold else None,
                 "max_dd_pct": st["max_dd_pct"], "vs_buy_hold_pct": round(st["total_return_pct"] - bh, 2),
                 "n_low_signals": int(len(lo)), "n_high_signals": int(len(hi)),
                 "trades": [{"entry": str(t.entry.date()), "exit": str(t.exit.date()), "hold_days": h, "net_ret_pct": round(t.net_ret * 100, 2),
                             "how": t.how} for t, h in zip(tr.itertuples(), hold)]}
            res["methods"][name][title] = r
            sims[title] = sim
            print(f"{name} {title[:14]:<14} 扣 {r['扣成本_pct']:+7.2f}% 沒扣 {r['沒扣成本_pct']:+7.2f}%  {r['n_trades']} 筆 勝 {r['win_rate_pct']}%"
                  f"  持有 {r['avg_hold_days']} 天  回撤 {r['max_dd_pct']}%", flush=True)

        n = len(ROWS)
        fig, axes = plt.subplots(n, 1, figsize=(18, 3.1 * n), dpi=150, sharex=True, facecolor="white", gridspec_kw={"hspace": 0.45})
        fig.subplots_adjust(left=0.05, right=0.99, top=0.965, bottom=0.03)
        pad = (close.max() - close.min()) * 0.04
        for ax, (title, _, k) in zip(axes, ROWS):
            ax.plot(close.index, close.values, color="#9a9994", lw=1.1, zorder=1)
            CP.style(ax)
            for t in sims[title]["trades"].itertuples():
                ax.axvspan(t.entry, t.exit, color=HOLDC, alpha=0.2, lw=0, zorder=0)
                ax.annotate(f"{t.net_ret * 100:+.1f}%", (t.entry + (t.exit - t.entry) / 2, close.max() + pad * 1.2), ha="center",
                            va="bottom", rotation=90, fontsize=7.5, color=INK)
            ax.set_ylim(close.min() - pad * 2, close.max() + pad * 7)
            r = res["methods"][name][title]
            ax.set_title(f"{title}:扣成本 {r['扣成本_pct']:+.1f}% / 沒扣 {r['沒扣成本_pct']:+.1f}%,{r['n_trades']} 筆",
                         loc="left", fontsize=11, color=INK, fontweight="bold")
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m 月"))
        axes[-1].xaxis.set_major_locator(mdates.MonthLocator())
        fig.suptitle(f"{TK[:4]} {nm} {YEAR}:低點進場、高點出場 — {name}(168 檔模型、訓練門檻 0%;只交易南電、100 萬全部投入、"
                     f"訊號出現日隔天開盤成交、成本 0.585%;買進持有 {bh:+.1f}%)", x=0.01, ha="left", fontsize=14, color=INK, y=0.99)
        fig.text(0.01, 0.008, "綠底 = 持有期間,上方數字 = 該筆扣成本報酬。確認規則的訊號出現日 = 確認日 t+k。", fontsize=10, color=MUTED)
        out = os.path.join(ML.OUT, f"lohi_compare_{TK[:4]}_{YEAR}_{POOL}_{tag}.png")
        fig.savefig(out, facecolor="white", bbox_inches="tight")
        print(out)
    with open(os.path.join(ML.OUT, f"lohi_compare_{TK[:4]}_{YEAR}_{POOL}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("買進持有", round(bh, 2), "沒扣", round(bh_gross, 2))


if __name__ == "__main__":
    main()
