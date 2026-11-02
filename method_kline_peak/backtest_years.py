"""逐年投資組合回測:walk-forward 訊號 → 只做多、持有 5 天 → 每年獨立結算,與基準比較。

交易規則(2026-10-30 與使用者確認)
  - 只做多:t 日收盤出現低點訊號 → t+1 開盤買進,持有到 t+5 收盤賣出(該股票自己的交易日);高點訊號不交易
  - 每年獨立:100 萬起算、最多同時 10 檔,每檔用前一天收盤總資產的 1/10(不超過現金);零股可
  - 訊號比空位多時照 score 由高到低取,同分隨機(種子 0)
  - 已持有的股票再出現訊號不加碼;t+1 開盤漲停也照開盤價買進(2026-11-02 使用者取消「漲停買不到」)
  - 成本:買 0.1425%、賣 0.1425% + 證交稅 0.3%(合計 0.585%)
  - 年底(2026 為資料最後一天)還沒到期的持股,用當天收盤結清;t+1 已跨到下一年的訊號不交易
基準:0050 買進持有、TW50 50 檔等權買進持有、隨機訊號(每天買進的檔數同主軸,股票隨機,20 次平均)
另列「扣成本前」報酬(同規則、成本設 0),用來分開「訊號好不好」與「成本吃掉多少」
訓練:每年用前 4 年重新訓練(walkforward.py),同時列出當年的分類指標

訊號來源(--sources,預設 主軸、規則):主軸、規則、Stacking 邏輯迴歸(在 stacking.py)。
每個來源都用前 4 年訓練(Stacking:前 3 年基底層 + 第 4 年元學習器),訓練長度相同。
用法: python method_kline_peak/backtest_years.py [--years 2020 ... 2026] [--random-reps 20] [--sources ...] [--out 檔名]
輸出: results/backtest_years.json(或 --out 指定的檔名)
"""
import argparse
import json
import math
import os
import time
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

import mainline as ML
import walkforward as WF
import stacking as S
from feasibility import P, END, clean
from learn5_trade6 import UP, DOWN
from paper_aeocsvm import NAMES
from confusion import summarize

OUT = os.path.join(ML.OUT, "backtest_years.json")
NO_COST = dict(buy_fee=0.0, sell_fee=0.0, tax=0.0)
SOURCE_FACTORIES = {
    "主軸": WF.MainlineSource,
    "規則": WF.RuleSource,
    "Stacking 邏輯迴歸": lambda: S.StackingSource("lr", "score"),
}
DAYS_PER_YEAR = 246


@dataclass(frozen=True)
class TradeRule:
    hold: int = 5                 # t+1 開盤進場 → t+hold 收盤出場
    slots: int = 10               # 做多(低點訊號)最多同時幾檔
    short_slots: int = 0          # 做空(高點訊號)最多同時幾檔;0 = 不做空。每檔資金 = 前一天總資產 / (slots + short_slots)
    init_cash: float = 1_000_000.0
    buy_fee: float = 0.001425
    sell_fee: float = 0.001425
    tax: float = 0.003


def simulate(prices, buys, start, end, rule=TradeRule(), seed=0, shorts=None):
    """prices: {ticker: DataFrame[open, close]};buys / shorts: DataFrame[date(訊號日 t), ticker, score]。
    shorts(高點訊號)只在 rule.short_slots > 0 時使用:t+1 開盤放空、t+hold 收盤回補;
    放空時付賣出手續費 + 證交稅、回補時付買進手續費,保證金 = 股數 × 放空價(不加槓桿,不計借券費)。
    同一檔股票同時只會有一個部位(做多或做空)。
    回傳 {"equity": 每日收盤總資產 Series, "trades": 成交明細(side = 做多 / 做空), "skipped": 放棄原因計數}。"""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    cal = sorted({d for df in prices.values() for d in df.index if start <= d <= end})
    if not cal:
        raise ValueError("回測期間沒有交易日")
    last_day = cal[-1]
    rng = np.random.default_rng(seed)
    orders, skipped = {}, {"已持有": 0, "沒有空位": 0, "錢不夠一股": 0, "跨到下一年": 0}
    sides = [("做多", buys)] + ([("做空", shorts)] if rule.short_slots > 0 and shorts is not None else [])
    for side, sig in sides:
        for r in sig.itertuples(index=False):                 # 訊號日 t → 執行日 t+1、到期日 t+hold(該股自己的交易日)
            idx = prices[r.ticker].index
            i = idx.searchsorted(r.date)
            if i + 1 >= len(idx) or idx[i] != r.date or idx[i + 1] > last_day:
                skipped["跨到下一年"] += 1
                continue
            exit_d = idx[min(i + rule.hold, len(idx) - 1)]
            orders.setdefault((idx[i + 1], side), []).append((r.score, rng.random(), r.ticker, r.date, min(exit_d, last_day)))
    cap = {"做多": rule.slots, "做空": rule.short_slots}
    per_slot = rule.slots + rule.short_slots

    cash, held, trades, equity, last_close = rule.init_cash, {}, [], {}, {}
    prev_equity = rule.init_cash
    by_day = {}                                               # 先把期間內每天的開盤、收盤整理好,迴圈裡不用逐檔查表
    for tk, df in prices.items():
        sub = df.loc[start:end]
        for d, o, c in zip(sub.index, sub["open"].to_numpy(), sub["close"].to_numpy()):
            by_day.setdefault(d, {})[tk] = {"open": o, "close": c}
    def value(tk, h):                                         # 收盤市值:做多 = 股數 × 收盤;做空 = 保證金 + 放空淨收入 − 股數 × 收盤
        if h["side"] == "做多":
            return h["shares"] * last_close[tk]
        return h["cost"] + h["shares"] * (h["buy_px"] * (1 - rule.sell_fee - rule.tax) - last_close[tk])

    for d in cal:
        today = by_day[d]
        for side in ("做多", "做空"):                          # 開盤:先做多、再做空,各自照 score 由高到低
            for score, _, tk, t, exit_d in sorted(orders.get((d, side), []), key=lambda o: (-o[0], o[1])):
                o = today[tk]["open"]
                if tk in held:
                    skipped["已持有"] += 1
                    continue
                if sum(h["side"] == side for h in held.values()) >= cap[side]:
                    skipped["沒有空位"] += 1
                    continue
                fee = rule.buy_fee if side == "做多" else 0.0
                sh = math.floor(min(cash, prev_equity / per_slot) / (o * (1 + fee)))
                if sh <= 0:
                    skipped["錢不夠一股"] += 1
                    continue
                cost = sh * o * (1 + fee)                     # 做多:買進金額含手續費;做空:保證金
                cash -= cost
                held[tk] = {"shares": sh, "cost": cost, "entry": d, "signal": t, "exit": exit_d, "buy_px": o, "side": side}
        for tk, c in today.items():
            last_close[tk] = c["close"]
        for tk in [k for k, h in held.items() if h["exit"] == d or d == last_day]:                # 收盤:出場
            h = held.pop(tk)
            px = last_close[tk]
            if h["side"] == "做多":
                proceeds = h["shares"] * px * (1 - rule.sell_fee - rule.tax)
            else:
                proceeds = h["cost"] + h["shares"] * (h["buy_px"] * (1 - rule.sell_fee - rule.tax) - px * (1 + rule.buy_fee))
            cash += proceeds
            trades.append({"ticker": tk, "signal": h["signal"], "entry": h["entry"], "exit": d, "shares": h["shares"],
                           "buy_px": h["buy_px"], "sell_px": px, "net_ret": proceeds / h["cost"] - 1, "pnl": proceeds - h["cost"],
                           "side": h["side"]})
        prev_equity = cash + sum(value(tk, h) for tk, h in held.items())
        equity[d] = prev_equity
    return {"equity": pd.Series(equity), "trades": pd.DataFrame(trades), "skipped": skipped}


def buy_and_hold(prices, start, end, rule=TradeRule()):
    """第一個交易日開盤等權買進,最後一個交易日收盤賣出(含成本)。"""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    cal = sorted({d for df in prices.values() for d in df.index if start <= d <= end})
    each = rule.init_cash / len(prices)
    pos = {}
    for tk, df in prices.items():
        w = df.loc[cal[0]:cal[-1]]
        pos[tk] = (each / (w["open"].iloc[0] * (1 + rule.buy_fee)), w["close"])
    eq = sum(sh * c.reindex(cal).ffill() for sh, c in pos.values())
    eq.iloc[-1] *= 1 - rule.sell_fee - rule.tax
    return eq


def stats(equity, trades=None, init=TradeRule().init_cash):
    r = equity.pct_change().dropna()
    out = {"total_return_pct": round((equity.iloc[-1] / init - 1) * 100, 2),
           "max_dd_pct": round(float((equity / equity.cummax() - 1).min()) * 100, 2),
           "sharpe": round(float(r.mean() / r.std() * math.sqrt(DAYS_PER_YEAR)), 2) if r.std() > 0 else 0.0}
    if trades is not None:
        n = len(trades)
        out.update({"n_trades": n, "win_rate_pct": round(float((trades.net_ret > 0).mean()) * 100, 1) if n else None,
                    "avg_net_ret_pct": round(float(trades.net_ret.mean()) * 100, 2) if n else None})
    return out


def random_buys(sig, prices, rng):
    """隨機對照:每天買進訊號的檔數跟 sig 一樣,但從當天有交易的股票中隨機挑。"""
    rows = []
    for d, k in sig.groupby("date").size().items():
        pool = [tk for tk, df in prices.items() if d in df.index]
        for tk in rng.choice(pool, size=min(k, len(pool)), replace=False):
            rows.append((d, tk, rng.random()))
    return pd.DataFrame(rows, columns=["date", "ticker", "score"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="+", default=list(WF.YEARS))
    ap.add_argument("--random-reps", type=int, default=20)
    ap.add_argument("--sources", nargs="+", default=list(WF.SOURCES), choices=list(SOURCE_FACTORIES))
    ap.add_argument("--out", default=os.path.basename(OUT))
    args = ap.parse_args()
    out_path = os.path.join(ML.OUT, args.out)
    t0 = time.time()
    data = ML.load_data()
    panel, fc = ML.build_panel(data, 6, [])
    prices = {tk: clean(df)[["open", "close"]] for tk, df in data.items()}
    etf = clean(pd.read_parquet(os.path.join(P.YF_2026_CACHE, "0050.TW.parquet")))[["open", "close"]]
    rule = TradeRule()
    res = {"rule": asdict(rule), "sources": args.sources, "years": {}}
    for y in args.years:
        start, end = f"{y}-01-01", min(f"{y}-12-31", END)
        yr = {"period": [start, end]}
        for name in args.sources:
            sig, n_train = WF.run_year(panel, fc, y, SOURCE_FACTORIES[name]())
            cm = summarize(sig.y.to_numpy(), sig.pred.to_numpy(), NAMES)
            buys = sig[sig.pred == UP][["date", "ticker", "score"]]
            sim = simulate(prices, buys, start, end, rule)
            gross = stats(simulate(prices, buys, start, end, TradeRule(**NO_COST))["equity"])["total_return_pct"]
            yr[name] = {"n_train": n_train, "n_buy_signals": len(buys), **stats(sim["equity"], sim["trades"]), "gross_return_pct": gross,
                        "skipped": sim["skipped"], "macro_f1_pct": round(cm["macro_f1"] * 100, 2),
                        "recall_pct": {k: round(cm["recall"][k] * 100, 1) for k in ("高點", "低點")},
                        "precision_pct": {k: round((cm["precision"][k] or 0) * 100, 1) for k in ("高點", "低點")},
                        "curve": {d.strftime("%Y-%m-%d"): round(v / rule.init_cash * 100 - 100, 2) for d, v in sim["equity"].items()}}
            if name == args.sources[0]:
                ref_name, ref_sig = name, buys                          # 隨機對照:每天買的檔數跟第一個來源一樣
        rng = np.random.default_rng(y)
        rand, rand0 = [], []
        for _ in range(args.random_reps):
            rb = random_buys(ref_sig, prices, rng)
            rand.append(stats(simulate(prices, rb, start, end, rule)["equity"])["total_return_pct"])
            rand0.append(stats(simulate(prices, rb, start, end, TradeRule(**NO_COST))["equity"])["total_return_pct"])
        yr["隨機"] = {"mean_return_pct": round(float(np.mean(rand)), 2), "sd": round(float(np.std(rand)), 2),
                     "gross_mean_return_pct": round(float(np.mean(rand0)), 2),
                     "對照來源": ref_name, "對照來源贏過的比例": round(float(np.mean([yr[ref_name]["total_return_pct"] > x for x in rand])), 2)}
        yr["0050 買進持有"] = stats(buy_and_hold({"0050.TW": etf}, start, end, rule))
        yr["TW50 等權買進持有"] = stats(buy_and_hold(prices, start, end, rule))
        res["years"][str(y)] = yr
        print(f"{y}({time.time() - t0:.0f}s)  隨機 {yr['隨機']['mean_return_pct']:+.2f}%(扣成本前 {yr['隨機']['gross_mean_return_pct']:+.2f}%)"
              f"  0050 {yr['0050 買進持有']['total_return_pct']:+.2f}%  TW50 等權 {yr['TW50 等權買進持有']['total_return_pct']:+.2f}%", flush=True)
        for name in args.sources:
            m = yr[name]
            print(f"   {name:<14} 報酬 {m['total_return_pct']:+7.2f}%(扣成本前 {m['gross_return_pct']:+7.2f}%,回撤 {m['max_dd_pct']:6.2f}%,"
                  f"{m['n_trades']} 筆,勝 {m['win_rate_pct']}%)  macro-F1 {m['macro_f1_pct']:.2f}  找到 高 / 低 {m['recall_pct']['高點']} / {m['recall_pct']['低點']}"
                  f"  命中 高 / 低 {m['precision_pct']['高點']} / {m['precision_pct']['低點']}", flush=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"記錄於 {out_path}")


if __name__ == "__main__":
    main()
