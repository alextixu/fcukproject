"""在最佳模型(XGB tw50 h=5 permpos)的排名後面加交易邏輯層,NCKU 框架上跑 2026 網格。

底層不變:每 5 個交易日(再平衡日 t)依模型機率排序,t+1 開盤等權買 5 檔(前 10%),下一個再平衡日 t+1 開盤全部出清換股。
交易邏輯層(全部用 t 日收盤前可得的官方日資料):
  量價進場過濾(在排名上往下找,最多找到第 15 名,湊滿 5 檔;湊不滿就留現金)
    none      不過濾
    up_vol    量增價漲:當日量 ≥ 20 日均量 且 當日收盤 > 前一日收盤
    no_dist   排除出貨型:當日量 ≥ 1.5 倍 20 日均量 且 收盤 < 前一日收盤 的不買
  停損(進場隔日起每天檢查;跌破 → 以停損價成交,若開盤已跳空跌破則以開盤價)
    none / 5% / 8% / 2×ATR14(進場時的 ATR,價位固定)
  停利(同上;觸及 → 以停利價成交,跳空則開盤價)
    none / 10% / 20%
出場後現金閒置到下一個再平衡日。

用法: python run_logic.py            → 全網格 36 組
      python run_logic.py --only "up_vol|8%|20%"
輸出: out/logic/<組合>.xlsx、out/summary_logic.json
"""
import argparse
import itertools
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
import run_ncku as R                                   # noqa: E402
from run_ncku import Strategy, assemble_csv, code, INIT_CASH, START, END  # noqa: E402
from backtest.backtest import BacktestSystem, Stock_API   # noqa: E402
from data_loader import TICKER_SETS                        # noqa: E402

OUT = os.path.join(HERE, "out", "logic")
os.makedirs(OUT, exist_ok=True)
PRED = os.path.join(R.XGB_EXP, "x26-tw50-h5-cs_testpred.parquet")
PCOL, H, TOPK, MAXRANK = "p_full_permpos", 5, 5, 15


def load_indicators(codes):
    """由官方日資料算 t 日可得的量價指標:vol_ratio_20、ret_1d、atr14。回傳 {code: DataFrame(index=YYYYMMDD)}。"""
    out = {}
    for c in codes:
        fp = os.path.join(R.SRC, f"{c}.parquet")
        if not os.path.exists(fp):
            continue
        x = pd.read_parquet(fp).sort_values("date")
        x["d"] = pd.to_datetime(x["date"]).dt.strftime("%Y%m%d")
        v = x["capacity"].astype(float)
        x["vol_ratio_20"] = v / v.rolling(20, min_periods=10).mean()
        x["ret_1d"] = x["close"].pct_change()
        tr = pd.concat([x["high"] - x["low"], (x["high"] - x["close"].shift()).abs(), (x["low"] - x["close"].shift()).abs()], axis=1).max(axis=1)
        x["atr14"] = tr.rolling(14, min_periods=7).mean()
        out[c] = x.set_index("d")[["vol_ratio_20", "ret_1d", "atr14", "close"]]
    return out


def load_ranking():
    """{再平衡日 YYYYMMDD: [codes 依機率由高到低]}"""
    df = pd.read_parquet(PRED)
    df = df[df.index.get_level_values("date") <= pd.Timestamp("2026-09-10")]
    dates = sorted(df.index.get_level_values("date").unique())
    return {d.strftime("%Y%m%d"): [code(t) for t in df.xs(d, level="date")[PCOL].dropna().sort_values(ascending=False).index]
            for d in dates[::H]}


FILTERS = {
    "none": lambda r: True,
    "up_vol": lambda r: (r["vol_ratio_20"] >= 1.0) and (r["ret_1d"] > 0),
    "no_dist": lambda r: not ((r["vol_ratio_20"] >= 1.5) and (r["ret_1d"] < 0)),
    "vol_only": lambda r: r["vol_ratio_20"] >= 1.0,
    "up_only": lambda r: r["ret_1d"] > 0,
}
STOPS = {"none": None, "5%": ("pct", 0.05), "8%": ("pct", 0.08), "12%": ("pct", 0.12), "15%": ("pct", 0.15),
         "2ATR": ("atr", 2.0), "3ATR": ("atr", 3.0), "trail8%": ("trail", 0.08), "trail12%": ("trail", 0.12)}
TAKES = {"none": None, "10%": 0.10, "20%": 0.20, "30%": 0.30}


class LogicStrategy(Strategy):
    def __init__(self, name, universe, ranking, ind, filt, stop, take):
        super().__init__(name, universe)
        self.ranking, self.ind, self.filt, self.stop, self.take = ranking, ind, filt, stop, take
        self.pos = {}          # code → {"entry":price, "sl":price|None, "tp":price|None, "day":day_idx}
        self.rebal_today = False
        self.n_filtered = 0
        self.n_sl = self.n_tp = 0

    def pick(self, d, prev_pool):
        if d not in self.ranking:
            return []
        out = []
        for c in self.ranking[d][:MAXRANK]:
            r = self.ind.get(c)
            if r is None or d not in r.index:
                continue
            row = r.loc[d]
            if row.isna().any():
                continue
            if self.filt(row):
                out.append(c)
            else:
                self.n_filtered += 1
            if len(out) == TOPK:
                break
        return out

    def trade(self, pool_info, inventory, cash, tool):
        self.day_idx += 1
        held = {u.stock_info.stock_code: u for u in inventory}
        equity = cash + sum(u.shares * (u.stock_info.price_open or u.stock_info.price_close or u.avg_price) for u in held.values())
        rebal = bool(pool_info)
        # 1) 出場
        for c, u in held.items():
            si = u.stock_info
            o, lo, hi = si.price_open, si.price_low, si.price_high
            if o is None:
                continue
            p = self.pos.get(c)
            px = None
            if rebal:
                px = o                                              # 換股日:開盤出清
            elif p and p["day"] < self.day_idx:
                sl = p["sl"]
                if p.get("trail") is not None:                      # 移動停損:以前一日以前的最高價為準
                    sl = p["hwm"] * (1 - p["trail"])
                if sl is not None and lo is not None and lo <= sl:
                    px = min(o, sl)                                 # 跳空跌破用開盤,否則停損價
                    self.n_sl += 1
                elif p["tp"] is not None and hi is not None and hi >= p["tp"]:
                    px = max(o, p["tp"])
                    self.n_tp += 1
            if p is not None and px is None and hi is not None:
                p["hwm"] = max(p.get("hwm", p["entry"]), hi)
            if px is not None:
                tool.sell_stock(c, float(px), u.shares)
                cash += u.shares * float(px)
                self.pos.pop(c, None)
        # 2) 進場(只在換股日)
        if rebal:
            buys = [s for s in pool_info if s.price_open]
            for s in buys:
                alloc = min(cash, equity / TOPK)
                sh = int(alloc // s.price_open)
                if sh <= 0:
                    continue
                tool.buy_stock(s.stock_code, s.price_open, sh)
                cash -= sh * s.price_open
                e = s.price_open
                d = s.init_time.strftime("%Y%m%d")
                atr = None
                r = self.ind.get(s.stock_code)
                if r is not None:
                    prev = r.loc[:d]
                    prev = prev[prev.index < d]
                    if len(prev):
                        atr = prev["atr14"].iloc[-1]
                sl, trail = None, None
                if self.stop:
                    kind, v = self.stop
                    if kind == "pct":
                        sl = e * (1 - v)
                    elif kind == "atr":
                        sl = e - v * atr if atr and not np.isnan(atr) else None
                    else:
                        trail = v
                tp = e * (1 + self.take) if self.take else None
                self.pos[s.stock_code] = {"entry": e, "sl": sl, "tp": tp, "trail": trail, "hwm": e, "day": self.day_idx}
        return tool.transaction_record


def run_one(name, strat, universe):
    Stock_API.get_all_stock_information = staticmethod(lambda: list(universe))
    bt = BacktestSystem("", "")
    bt.set_backtest_period(START, END)
    bt.set_cash_balance(INIT_CASH)
    bt.execute_strategy(name, strat.select, strat.trade)
    perf, detail = bt.calculate_performance()
    bt.save_performance_to_xls(name, perf, detail, os.path.join(OUT, f"{name}.xlsx"))
    daily = pd.DataFrame([{"date": d.record_date, "total": d.stock_assets + d.cash_assets} for d in detail.daily_values_list])
    eq = daily["total"] / INIT_CASH
    r = eq.pct_change().dropna()
    sells = [t for t in detail.historical_transactions_list if t.action == 1 and t.error_status.status]
    n_sl = sum(1 for t in sells if t.sell_price < t.buy_price * 0.999 and t.date.strftime("%Y%m%d") not in strat.ranking and True)
    return {"total_return_pct": round((perf.total_assets - INIT_CASH) / INIT_CASH * 100, 2),
            "max_dd_pct": round(float((eq / eq.cummax() - 1).min()) * 100, 2),
            "daily_sharpe_ann": round(float(r.mean() / r.std() * math.sqrt(246)), 2) if r.std() > 0 else 0.0,
            "n_round_trips": len(sells), "win_rate": round(float(np.mean([t.profit > 0 for t in sells])), 3) if sells else None,
            "avg_trade_ret_pct": round(float(np.mean([t.profit / (t.buy_price * t.shares) * 100 for t in sells])), 2) if sells else None,
            "n_filtered_out": strat.n_filtered, "n_stop_exits": strat.n_sl, "n_tp_exits": strat.n_tp,
            "curve": {d.strftime("%Y-%m-%d"): round(float(v - 1) * 100, 2) for d, v in zip(daily["date"], eq)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    tw50 = [code(t) for t in TICKER_SETS["tw50"]]
    avail = assemble_csv(tw50 + ["0050"])
    uni = [c for c in tw50 if c in avail]
    ind = load_indicators(uni)
    ranking = load_ranking()
    combos = list(itertools.product(FILTERS, STOPS, TAKES))
    if a.only:
        combos = [tuple(a.only.split("|"))]
    summ = {}
    for f, s, t in combos:
        name = f"{f}|{s}|{t}"
        strat = LogicStrategy(name, uni, ranking, ind, FILTERS[f], STOPS[s], TAKES[t])
        res = run_one(name.replace("|", "_").replace("%", "pct"), strat, uni)
        res.update({"filter": f, "stop": s, "take": t})
        summ[name] = res
        print(f"{name:22s} 總收益 {res['total_return_pct']:+8.2f}%  MDD {res['max_dd_pct']:6.2f}%  Sharpe {res['daily_sharpe_ann']:5.2f}  來回 {res['n_round_trips']:3d}  勝率 {res['win_rate']}  過濾掉 {res['n_filtered_out']}  停損 {res['n_stop_exits']} 停利 {res['n_tp_exits']}", flush=True)
    json.dump(summ, open(os.path.join(HERE, "out", "summary_logic.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[SAVED] out/summary_logic.json ({len(summ)} 組)")


if __name__ == "__main__":
    main()
