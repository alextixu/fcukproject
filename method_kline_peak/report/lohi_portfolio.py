"""南電比較圖那 8 列的「低點進場、高點出場」改成多檔組合回測:34 檔、2025(2026-11-09 使用者要求;不訓練新模型)。

模型 = 34 檔(tw50 經 low_vol 剔除)、訓練門檻 0%、種子 42,同 backtest_long_only.json 2025
(主軸訓練 2021–2024;Stacking A = 2021–2023、B = 2024)。8 列同 report/lohi_compare.py:
真實標籤(用到未來,上限)、A0、1a(用到未來)、1b、2-50(34 檔之間排序)、確認 k = 1、2、3。
交易(backtest_years.simulate(hold=None, exit_on_high=True)):最多同時 3 檔,每檔 = 前一天總資產 × 1/3(不超過現金);
  訊號出現日 = t(1–5 列)或 t+k(確認規則);沒持有該檔時低點訊號出現日隔天開盤買進,空位不夠時依 t 那天的原始分數
  由高到低、同分隨機(seed 0);真實標籤沒有分數,一律隨機(seed 0);持有中該檔高點訊號出現日隔天開盤賣出;
  沒有最長持有、不加碼、沒持有時高點不理會;年底最後一天收盤平倉;漲停照常成交;成本 0.585%,另列沒扣成本。
基準:34 檔等權買進持有(各檔年初第一天開盤買、年底收盤賣,扣成本);前 3 檔持有 5 天(引用 backtest_long_only.json 2025)。
用法: python method_kline_peak/report/lohi_portfolio.py
輸出: results/lohi_compare_34_2025.png、results/lohi_compare_34_2025.json
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
import lohi_compare as LC  # noqa: E402
from confusion import summarize  # noqa: E402
from feasibility import END, clean  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402
from paper_aeocsvm import NAMES  # noqa: E402

POOL, YEAR = "tw50", 2025
INK, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
LINE_COLORS = ["#0b0b0b", "#2a78d6", "#7f4fc9", "#86b6ef", "#e0a106", "#1baf7a", "#0f7a55", "#0a4a33"]
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False


def signals(df, pred, k, px, end):
    """把判斷轉成訊號出現日(t+k)的買進 / 賣出表;分數 = t 那天的原始分數。"""
    out = {}
    for cls in (UP, DOWN):
        rows = np.flatnonzero(pred == cls)
        dates, keep = [], []
        for r in rows:
            idx = px[df["ticker"].iat[r]].index
            j = idx.get_loc(df["date"].iat[r]) + k
            if j < len(idx) and idx[j] <= pd.Timestamp(end):
                dates.append(idx[j])
                keep.append(r)
        keep = np.asarray(keep, dtype=int)
        out[cls] = pd.DataFrame({"date": dates, "ticker": df["ticker"].to_numpy()[keep], "score": df["score"].to_numpy()[keep]})
    return out[UP], out[DOWN]


def buy_hold(px, start, end, rule):
    """34 檔等權買進持有:各檔第一個交易日開盤買、最後一天收盤賣(扣成本)。回傳 (報酬 %, 沒扣成本 %, 每日曲線 %)。"""
    w = 1 / len(px)
    vals, net, gross = [], [], []
    for p in px.values():
        q = p.loc[start:end]
        sh = w / (q["open"].iloc[0] * (1 + rule.buy_fee))
        vals.append(q["close"] * sh)
        net.append(q["close"].iloc[-1] * sh * (1 - rule.sell_fee - rule.tax))
        gross.append(q["close"].iloc[-1] / q["open"].iloc[0] * w)
    curve = pd.concat(vals, axis=1).ffill().sum(axis=1) * 100 - 100
    curve.iloc[-1] = sum(net) * 100 - 100
    return round(sum(net) * 100 - 100, 2), round(sum(gross) * 100 - 100, 2), curve


def main():
    data = ML.load_data(pool=POOL)
    assert len(data) == 34, len(data)
    panel, fc = ML.build_panel(data, 6, [])
    px = {tk: clean(df)[["open", "close"]] for tk, df in data.items()}
    start, end = f"{YEAR}-01-01", min(f"{YEAR}-12-31", END)
    rule = BY.TradeRule(slots=3, hold=None, exit_on_high=True)
    no_cost = BY.TradeRule(slots=3, hold=None, exit_on_high=True, **BY.NO_COST)
    bh, bh_gross, bh_curve = buy_hold(px, start, end, rule)
    ref = json.load(open(os.path.join(ML.OUT, "backtest_long_only.json"), encoding="utf-8"))["years"][str(YEAR)]
    res = {"pool": POOL, "n_stocks": len(data), "year": YEAR, "等權買進持有_pct": bh, "等權買進持有_沒扣_pct": bh_gross,
           "前3檔持有5天_引用": {m: ref[m]["扣成本"]["total_return_pct"] for m in LC.CP.FILES}, "methods": {}}
    curves = {}
    for name in LC.CP.FILES:
        sig, _ = WF.run_year(panel, fc, YEAR, BY.SOURCE_FACTORIES[name]())
        df = sig.sort_values(["ticker", "date"]).reset_index(drop=True)
        f1 = round(summarize(df["y"].to_numpy(), df["pred"].to_numpy(), NAMES)["macro_f1"] * 100, 2)
        res["methods"][name] = {"_核對": {"macro_f1": f1, "回測 json macro_f1": ref[name]["分類"]["macro_f1_pct"],
                                          "判低點數": int((df["pred"] == UP).sum()), "回測 json 低點訊號數": ref[name]["n_low_signals"]}}
        curves[name] = {}
        for title, rl, k in LC.ROWS:
            if rl == "truth":
                pred = df["y"].to_numpy()
            elif rl is None:
                pred = CS.confirm(df, k, px)[0]
            else:
                pred = PP.apply_rule(df, rl)
            lo, hi = signals(df, pred, k, px, end)
            if rl == "truth":
                lo["score"] = 0.0                                   # 沒有分數:同分 → simulate 內 seed 0 隨機
            sim = BY.simulate(px, lo, start, end, rule, sells=hi)
            gross = BY.simulate(px, lo, start, end, no_cost, sells=hi)
            tr = sim["trades"]
            st = BY.stats(sim["equity"], tr)
            hold = [int(px[t.ticker].index.get_loc(t.exit) - px[t.ticker].index.get_loc(t.entry) + 1) for t in tr.itertuples()]
            res["methods"][name][title] = {
                "扣成本_pct": st["total_return_pct"], "沒扣成本_pct": BY.stats(gross["equity"])["total_return_pct"],
                "n_trades": st["n_trades"], "win_rate_pct": st["win_rate_pct"],
                "avg_hold_days": round(float(np.mean(hold)), 1) if hold else None, "max_dd_pct": st["max_dd_pct"],
                "vs_等權買進持有": round(st["total_return_pct"] - bh, 2), "n_low_signals": int(len(lo)), "n_high_signals": int(len(hi))}
            curves[name][title] = sim["equity"] / rule.init_cash * 100 - 100
            r = res["methods"][name][title]
            print(f"{name} {title[:12]:<12} 扣 {r['扣成本_pct']:+7.2f}% 沒扣 {r['沒扣成本_pct']:+7.2f}%  {r['n_trades']} 筆 勝 {r['win_rate_pct']}%"
                  f"  持有 {r['avg_hold_days']} 天  回撤 {r['max_dd_pct']}%", flush=True)
        print(name, res["methods"][name]["_核對"])

    fig, axes = plt.subplots(2, 4, figsize=(22, 10.5), dpi=150, sharex=True, sharey=False, facecolor=SURF)
    for c, (title, _, _) in enumerate(LC.ROWS):
        ax = axes.flat[c]
        ax.set_facecolor(SURF)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=9, length=0)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.axhline(0, color=MUTED, lw=0.8, ls=":")
        ax.plot(bh_curve.index, bh_curve.values, color="#9a9994", lw=1.4, ls="--", label=f"34 檔等權買進持有 {bh:+.1f}%")
        for name, col in (("主軸", "#86b6ef"), ("Stacking 邏輯迴歸", "#f0956b")):
            rc = ref[name]["扣成本"]["curve"]
            ax.plot(pd.to_datetime(list(rc)), list(rc.values()), color=col, lw=1.0, ls=":",
                    label=f"{name} 前 3 檔持有 5 天 {ref[name]['扣成本']['total_return_pct']:+.1f}%")
        txt = []
        for name, col in (("主軸", "#2a78d6"), ("Stacking 邏輯迴歸", "#eb6834")):
            cv = curves[name][title]
            r = res["methods"][name][title]
            ax.plot(cv.index, cv.values, color=col, lw=1.8, label=f"{name} {r['扣成本_pct']:+.1f}%({r['n_trades']} 筆)")
            txt.append(f"{name[:2] if name == '主軸' else 'Stacking'} {r['扣成本_pct']:+.1f}%")
        short = title.split("(")[0] + ("(用到未來)" if "未來" in title else "")
        ax.set_title(short, loc="left", fontsize=11.5, color=INK, fontweight="bold")
        ax.legend(frameon=False, fontsize=8.5, labelcolor=INK, loc="upper left")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m 月"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
        if c % 4 == 0:
            ax.set_ylabel("相對年初 100 萬的報酬(%,扣成本)", color=MUTED, fontsize=9)
        ax.tick_params(labelleft=True)
    vals = [v for t, _, _ in LC.ROWS[1:] for n in curves for v in curves[n][t].values] + list(bh_curve.values)
    vals += [v for n in curves for v in ref[n]["扣成本"]["curve"].values()]
    lo_, hi_ = min(vals), max(vals)
    for ax in list(axes.flat)[1:]:
        ax.set_ylim(lo_ - 5, hi_ + (hi_ - lo_) * 0.55)                # 留空間給圖例
    axes.flat[0].set_title(axes.flat[0].get_title(loc="left") + "(y 軸刻度不同)", loc="left", fontsize=11.5, color=INK, fontweight="bold")
    fig.suptitle(f"34 檔 {YEAR}:低點進場、高點出場(最多同時 3 檔、每檔 1/3;訊號出現日隔天開盤成交、沒有最長持有、成本 0.585%)"
                 f";實線 = 扣成本;參考:前 3 檔持有 5 天 主軸 {res['前3檔持有5天_引用']['主軸']:+.1f}%、"
                 f"Stacking {res['前3檔持有5天_引用']['Stacking 邏輯迴歸']:+.1f}%", x=0.01, ha="left", fontsize=13, color=INK, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.96), h_pad=2.0)
    fig.savefig(os.path.join(ML.OUT, f"lohi_compare_34_{YEAR}.png"), facecolor=SURF)
    with open(os.path.join(ML.OUT, f"lohi_compare_34_{YEAR}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("等權買進持有", bh, bh_gross)


if __name__ == "__main__":
    main()
