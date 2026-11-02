"""只交易模型前 3 檔的回測(2026-11-02 使用者要求):3 個方法 × 2024、2025、2026,共 9 個。

交易規則(其餘同 backtest_years.py)
  - 低點訊號 → 做多:t+1 開盤買,t+5 收盤賣;同時最多 3 檔
  - 預設只做多(--short-slots 0):每檔用前一天收盤總資產的 1/3(不超過現金)
  - --short-slots 3:高點訊號 → 做空(t+1 開盤放空,t+5 收盤回補),同時最多 3 檔;總共 6 檔,每檔 1/6
  - 空位不夠時照模型分數由高到低取,同分隨機
  - 同一檔股票同時只會有一個部位;不加碼;漲停 / 跌停照樣成交
  - 成本:做多 買 0.1425% + 賣 0.1425% + 稅 0.3%;做空 放空時 0.1425% + 稅 0.3%、回補時 0.1425%(不計借券費)
  - 每年獨立 100 萬,年底結清;另列成本設 0 的結果(扣成本前)
訓練:測哪一年就用前 4 年(主軸 4 年;Stacking 前 3 年基底層 + 第 4 年元學習器)
股票池:mainline.load_data()(TW50 剔除 mainline.EXCLUDE 的 16 檔低波動股,34 檔);同時記錄分類分數(用原本的標籤對答案)
--train-min-amp 3:訓練時只把兩邊幅度 ≥ 3% 的點當高點 / 低點(對答案仍用原本的標籤),輸出檔名加 _amp3
用法: python method_kline_peak/backtest_top3.py [--short-slots 0 | 3] [--train-min-amp 3]
輸出: results/backtest_long_only.json(只做多)或 results/backtest_long_short.json(做多 + 做空)
      剔除前(TW50 50 檔)的結果保留在 results/backtest_long_only_tw50.json、results/backtest_long_short_tw50.json
"""
import argparse
import json
import os
import time
from dataclasses import asdict

import mainline as ML
import walkforward as WF
import backtest_years as BY
from confusion import summarize
from feasibility import END, clean
from learn5_trade6 import UP, DOWN
from paper_aeocsvm import NAMES

YEARS = (2024, 2025, 2026)
SOURCES = ["主軸", "Stacking 邏輯迴歸", "Stacking 門檻"]
COLS = ["date", "ticker", "score"]


def side_stats(trades, side, init=BY.TradeRule().init_cash):
    t = trades[trades.side == side] if len(trades) else trades
    n = len(t)
    return {"n_trades": n, "win_rate_pct": round(float((t.net_ret > 0).mean()) * 100, 1) if n else None,
            "pnl_pct_of_init": round(float(t.pnl.sum()) / init * 100, 2) if n else 0.0}


def result(sim):
    tr = sim["trades"]
    return {**BY.stats(sim["equity"], tr), "做多": side_stats(tr, "做多"), "做空": side_stats(tr, "做空")}


def cls_metrics(sig):
    s = summarize(sig.y.to_numpy(), sig.pred.to_numpy(), NAMES)
    return {"macro_f1_pct": round(s["macro_f1"] * 100, 2),
            "recall_pct": {k: round(s["recall"][k] * 100, 1) for k in ("高點", "低點")},
            "precision_pct": {k: round((s["precision"][k] or 0) * 100, 1) for k in ("高點", "低點")}}


def run_all(panel, fc, prices, amp=0.0, k=0, log=print, sources=SOURCES, years=YEARS):
    """3 個方法 × YEARS 的回測;回傳 {年: {方法: 結果}}。amp = 訓練門檻(%),k = 做空格數。"""
    rule, no_cost = BY.TradeRule(slots=3, short_slots=k), BY.TradeRule(slots=3, short_slots=k, **BY.NO_COST)
    t0, out = time.time(), {}
    for y in years:
        start, end = f"{y}-01-01", min(f"{y}-12-31", END)
        out[str(y)] = {"period": [start, end]}
        for name in sources:
            sig, n_train = WF.run_year(panel, fc, y, BY.SOURCE_FACTORIES[name](), train_min_amp=amp)
            lo, hi = sig[sig.pred == UP][COLS], sig[sig.pred == DOWN][COLS]
            net = result(BY.simulate(prices, lo, start, end, rule, shorts=hi))
            gross = result(BY.simulate(prices, lo, start, end, no_cost, shorts=hi))
            cm = cls_metrics(sig)
            out[str(y)][name] = {"n_train": n_train, "n_low_signals": len(lo), "n_high_signals": len(hi),
                                   "分類": cm, "扣成本": net, "沒扣成本": gross}
            log(f"{y} {name:<12} 扣成本 {net['total_return_pct']:+7.2f}%(多 {net['做多']['pnl_pct_of_init']:+.2f} / 空 {net['做空']['pnl_pct_of_init']:+.2f})"
                f"  沒扣成本 {gross['total_return_pct']:+7.2f}%(多 {gross['做多']['pnl_pct_of_init']:+.2f} / 空 {gross['做空']['pnl_pct_of_init']:+.2f})"
                f"  {net['n_trades']} 筆(多 {net['做多']['n_trades']} / 空 {net['做空']['n_trades']}),勝 {net['win_rate_pct']}%,"
                f"回撤 {net['max_dd_pct']}%  macro-F1 {cm['macro_f1_pct']}  找到 高/低 {cm['recall_pct']['高點']}/{cm['recall_pct']['低點']}"
                f"  命中 高/低 {cm['precision_pct']['高點']}/{cm['precision_pct']['低點']}  ({time.time() - t0:.0f}s)")
    return out


def load():
    data = ML.load_data()
    panel, fc = ML.build_panel(data, 6, [])
    return data, panel, fc, {tk: clean(df)[["open", "close"]] for tk, df in data.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--short-slots", type=int, default=0, choices=[0, 3])
    ap.add_argument("--train-min-amp", type=float, default=0.0)
    a = ap.parse_args()
    k, amp = a.short_slots, a.train_min_amp
    out_path = os.path.join(ML.OUT, ("backtest_long_short" if k else "backtest_long_only") + (f"_amp{amp:g}" if amp else "") + ".json")
    data, panel, fc, prices = load()
    res = {"rule": asdict(BY.TradeRule(slots=3, short_slots=k)), "train_min_amp": amp, "pool": sorted(data), "excluded": list(ML.EXCLUDE),
           "years": run_all(panel, fc, prices, amp, k, log=lambda m: print(m, flush=True))}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"記錄於 {out_path}")


if __name__ == "__main__":
    main()
