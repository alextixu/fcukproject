"""做多前 3 檔 + 做空前 3 檔的回測(2026-11-02 使用者要求):3 個方法 × 2024、2025、2026,共 9 個。

交易規則(其餘同 backtest_years.py)
  - 低點訊號 → 做多:t+1 開盤買,t+5 收盤賣;同時最多 3 檔
  - 高點訊號 → 做空:t+1 開盤放空,t+5 收盤回補;同時最多 3 檔
  - 總共最多持有 6 檔,每檔用前一天收盤總資產的 1/6(不超過現金);空位不夠時照模型分數由高到低取,同分隨機
  - 同一檔股票同時只會有一個部位;不加碼;漲停 / 跌停照樣成交
  - 成本:做多 買 0.1425% + 賣 0.1425% + 稅 0.3%;做空 放空時 0.1425% + 稅 0.3%、回補時 0.1425%(不計借券費)
  - 每年獨立 100 萬,年底結清;另列成本設 0 的結果(扣成本前)
訓練:測哪一年就用前 4 年(主軸 4 年;Stacking 前 3 年基底層 + 第 4 年元學習器)
用法: python method_kline_peak/backtest_long_short.py
輸出: results/backtest_long_short.json
"""
import json
import os
import time
from dataclasses import asdict

import mainline as ML
import walkforward as WF
import backtest_years as BY
from feasibility import START, END, load_pool, clean
from learn5_trade6 import UP, DOWN

YEARS = (2024, 2025, 2026)
SOURCES = ["主軸", "Stacking 邏輯迴歸", "Stacking 門檻"]
RULE = BY.TradeRule(slots=3, short_slots=3)
NO_COST_RULE = BY.TradeRule(slots=3, short_slots=3, **BY.NO_COST)
OUT = os.path.join(ML.OUT, "backtest_long_short.json")
COLS = ["date", "ticker", "score"]


def side_stats(trades, side, init=RULE.init_cash):
    t = trades[trades.side == side] if len(trades) else trades
    n = len(t)
    return {"n_trades": n, "win_rate_pct": round(float((t.net_ret > 0).mean()) * 100, 1) if n else None,
            "pnl_pct_of_init": round(float(t.pnl.sum()) / init * 100, 2) if n else 0.0}


def result(sim):
    tr = sim["trades"]
    return {**BY.stats(sim["equity"], tr), "做多": side_stats(tr, "做多"), "做空": side_stats(tr, "做空")}


def main():
    t0 = time.time()
    data = load_pool(ML.POOL, START, END)
    panel, fc = ML.build_panel(data, 6, [])
    prices = {tk: clean(df)[["open", "close"]] for tk, df in data.items()}
    res = {"rule": asdict(RULE), "years": {}}
    for y in YEARS:
        start, end = f"{y}-01-01", min(f"{y}-12-31", END)
        res["years"][str(y)] = {"period": [start, end]}
        for name in SOURCES:
            sig, n_train = WF.run_year(panel, fc, y, BY.SOURCE_FACTORIES[name]())
            lo, hi = sig[sig.pred == UP][COLS], sig[sig.pred == DOWN][COLS]
            net = result(BY.simulate(prices, lo, start, end, RULE, shorts=hi))
            gross = result(BY.simulate(prices, lo, start, end, NO_COST_RULE, shorts=hi))
            res["years"][str(y)][name] = {"n_train": n_train, "n_low_signals": len(lo), "n_high_signals": len(hi),
                                          "扣成本": net, "沒扣成本": gross}
            print(f"{y} {name:<12} 扣成本 {net['total_return_pct']:+7.2f}%(多 {net['做多']['pnl_pct_of_init']:+.2f} / 空 {net['做空']['pnl_pct_of_init']:+.2f})"
                  f"  沒扣成本 {gross['total_return_pct']:+7.2f}%(多 {gross['做多']['pnl_pct_of_init']:+.2f} / 空 {gross['做空']['pnl_pct_of_init']:+.2f})"
                  f"  {net['n_trades']} 筆(多 {net['做多']['n_trades']} / 空 {net['做空']['n_trades']}),勝 {net['win_rate_pct']}%,"
                  f"回撤 {net['max_dd_pct']}%  ({time.time() - t0:.0f}s)", flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"記錄於 {OUT}")


if __name__ == "__main__":
    main()
