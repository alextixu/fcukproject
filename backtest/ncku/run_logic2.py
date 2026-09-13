"""交易邏輯層 v2:流動性過濾 + 大盤濾網 + 汰弱留強,接在 XGB tw50 h=5 permpos 排名後,NCKU 框架 2026 網格。

底層同 run_logic.py:再平衡日 t 依機率排序,t+1 開盤下單。
  流動性(t 日可得):5 日均成交額 ≥ 1 億 / 3 億,或 5 日均量 ≥ 2,000 張;不及格者不列入候選(往下找到第 15 名)
  大盤濾網(0050,t 日收盤):close > MA20 / close > MA60 / 20 日報酬 > 0;大盤弱 → 換股日只賣不買(現金閒置)
  汰弱留強(exit_rank):換股日持股若仍排在前 exit_rank 名就續抱(保留原進場價與停損停利價),只補空出來的名額;
                       exit_rank=none → 每次全部出清重買(v1 行為)
  停損/停利:3×ATR14 + 30%(v1 定案)、移動停損 12% + 30%、不設
用法: python run_logic2.py [--only "liq|mkt|hys|stops"]
輸出: out/logic2/*.xlsx、out/summary_logic2.json
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
import run_ncku as R                                                    # noqa: E402
from run_ncku import Strategy, assemble_csv, code, INIT_CASH, START, END  # noqa: E402
from run_logic import load_indicators, load_ranking, TOPK, MAXRANK       # noqa: E402
from backtest.backtest import BacktestSystem, Stock_API                  # noqa: E402
from data_loader import TICKER_SETS                                      # noqa: E402

OUT = os.path.join(HERE, "out", "logic2")
FEE_BUY, FEE_SELL = 0.001425, 0.001425 + 0.003
os.makedirs(OUT, exist_ok=True)


def load_liquidity(codes):
    out = {}
    for c in codes:
        fp = os.path.join(R.SRC, f"{c}.parquet")
        if not os.path.exists(fp):
            continue
        x = pd.read_parquet(fp).sort_values("date")
        x["d"] = pd.to_datetime(x["date"]).dt.strftime("%Y%m%d")
        x["vol5_lots"] = (x["capacity"].astype(float) / 1000).rolling(5).mean()
        x["to5_yi"] = (x["turnover"].astype(float) / 1e8).rolling(5).mean()
        out[c] = x.set_index("d")[["vol5_lots", "to5_yi"]]
    return out


def load_market():
    x = pd.read_parquet(os.path.join(R.SRC, "0050.parquet")).sort_values("date")
    x["d"] = pd.to_datetime(x["date"]).dt.strftime("%Y%m%d")
    c = x["close"].astype(float)
    x["ma20"], x["ma60"], x["ret20"] = c.rolling(20).mean(), c.rolling(60).mean(), c.pct_change(20)
    return x.set_index("d")[["close", "ma20", "ma60", "ret20"]]


LIQ = {"none": lambda r: True, "to1e": lambda r: r["to5_yi"] >= 1.0, "to3e": lambda r: r["to5_yi"] >= 3.0, "vol2k": lambda r: r["vol5_lots"] >= 2000}
MKT = {"none": lambda m: True, "ma20": lambda m: m["close"] > m["ma20"], "ma60": lambda m: m["close"] > m["ma60"], "ret20": lambda m: m["ret20"] > 0}
HYS = {"none": None, "10": 10, "15": 15, "20": 20}
STOPS = {"3ATR|30%": (("atr", 3.0), 0.30), "trail12%|30%": (("trail", 0.12), 0.30), "none": (None, None)}


class Logic2(Strategy):
    def __init__(self, name, universe, ranking, ind, liq, mkt, liq_f, mkt_f, exit_rank, stop, take, topk=None, maxrank=None, min_hold=0, out_days=1, limit_aware=False):
        super().__init__(name, universe)
        self.limit_aware = limit_aware    # True:開盤漲停且全天鎖死買不到、開盤跌停且全天鎖死賣不掉
        self.n_limit_skip_buy = self.n_limit_skip_sell = 0
        self.out_days = out_days          # 連續幾個檢視日掉出 exit_rank 才賣(1 = 一掉出就賣)
        self.out_cnt = {}
        self.min_hold = min_hold          # 買進後至少持有幾個交易日才允許因排名下滑賣出(停損停利不受限)
        self.topk, self.maxrank = topk or TOPK, maxrank or MAXRANK
        self.ranking, self.ind, self.liq, self.mkt = ranking, ind, liq, mkt
        self.liq_f, self.mkt_f, self.exit_rank, self.stop, self.take = liq_f, mkt_f, exit_rank, stop, take
        self.pos, self.cur_key = {}, None
        self.n_sl = self.n_tp = self.n_liq = self.n_mkt_block = self.n_kept = 0

    def pick(self, d, prev_pool):
        if d not in self.ranking:
            return []
        self.cur_key = d
        out = []
        for c in self.ranking[d][:self.maxrank]:
            r = self.liq.get(c)
            if r is None or d not in r.index or r.loc[d].isna().any():
                continue
            if self.liq_f(r.loc[d]):
                out.append(c)
            else:
                self.n_liq += 1
        return out                      # 有序候選(最多 15 檔);買幾檔在 trade() 決定

    def trade(self, pool_info, inventory, cash, tool):
        self.day_idx += 1
        ok_px = lambda v: v is not None and v == v and v > 0          # 排除 None / NaN(櫃買無成交日開盤為空)
        held = {u.stock_info.stock_code: u for u in inventory}
        equity = cash + sum(u.shares * next(v for v in (u.stock_info.price_open, u.stock_info.price_close, u.avg_price) if ok_px(v)) for u in held.values())
        rebal = bool(pool_info)
        keep = set()
        if rebal:
            rank = {c: i + 1 for i, c in enumerate(self.ranking[self.cur_key])}
            if self.exit_rank:
                for c in held:
                    self.out_cnt[c] = 0 if rank.get(c, 999) <= self.exit_rank else self.out_cnt.get(c, 0) + 1
                keep = {c for c in held if self.out_cnt[c] < self.out_days}
                self.n_kept += len(keep)
            if self.min_hold:
                keep |= {c for c in held if c in self.pos and self.day_idx - self.pos[c]["day"] < self.min_hold}
        # 1) 出場
        for c, u in held.items():
            si = u.stock_info
            o, lo, hi = si.price_open, si.price_low, si.price_high
            if not ok_px(o):
                continue
            lo = lo if ok_px(lo) else None
            hi = hi if ok_px(hi) else None
            p = self.pos.get(c)
            px = None
            if rebal and c not in keep:
                px = o
            elif p and p["day"] < self.day_idx:
                sl = p["hwm"] * (1 - p["trail"]) if p.get("trail") is not None else p["sl"]
                if sl is not None and lo is not None and lo <= sl:
                    px = min(o, sl); self.n_sl += 1
                elif p["tp"] is not None and hi is not None and hi >= p["tp"]:
                    px = max(o, p["tp"]); self.n_tp += 1
            if p is not None and px is None and hi is not None:
                p["hwm"] = max(p.get("hwm", p["entry"]), hi)
            if px is not None and self.limit_aware and self._locked(c, si, "down"):
                self.n_limit_skip_sell += 1
                px = None
            if px is not None:
                tool.sell_stock(c, float(px), u.shares)
                cash += u.shares * float(px)
                self.pos.pop(c, None)
        # 2) 進場(換股日,且大盤不弱)
        if rebal:
            m = self.mkt.loc[self.cur_key] if self.cur_key in self.mkt.index else None
            ok = m is not None and not m.isna().any() and self.mkt_f(m)
            slots = self.topk - len(keep)
            if not ok:
                self.n_mkt_block += slots
                slots = 0
            cands = [s for s in pool_info if s.stock_code not in keep and ok_px(s.price_open)]
            if self.limit_aware:
                kept = [s for s in cands if not self._locked(s.stock_code, s, "up")]
                self.n_limit_skip_buy += len(cands[:slots]) - len([s for s in cands[:slots] if s in kept])
                cands = kept
            buys = cands[:slots]
            for s in buys:
                alloc = min(cash, equity / self.topk)
                sh = int(alloc // s.price_open)
                if sh <= 0:
                    continue
                tool.buy_stock(s.stock_code, s.price_open, sh)
                cash -= sh * s.price_open
                e, d = s.price_open, s.init_time.strftime("%Y%m%d")
                atr = None
                r = self.ind.get(s.stock_code)
                if r is not None:
                    prev = r[r.index < d]
                    if len(prev):
                        atr = prev["atr14"].iloc[-1]
                sl, trail = None, None
                if self.stop:
                    kind, v = self.stop
                    if kind == "atr":
                        sl = e - v * atr if atr and not np.isnan(atr) else None
                    elif kind == "pct":
                        sl = e * (1 - v)
                    else:
                        trail = v
                tp = e * (1 + self.take) if self.take else None
                self.pos[s.stock_code] = {"entry": e, "sl": sl, "tp": tp, "trail": trail, "hwm": e, "day": self.day_idx}
        return tool.transaction_record


def _locked(self, c, si, side):
    """當日開盤即在漲(跌)停且最高 = 最低(全天鎖死)。前一日收盤取自 ind 的 close 序列。"""
    r = self.ind.get(c)
    if r is None:
        return False
    d = si.init_time.strftime("%Y%m%d")
    prev = r[r.index < d]["close"]
    if prev.empty:
        return False
    pc, o, hi, lo = float(prev.iloc[-1]), si.price_open, si.price_high, si.price_low
    if not all(v is not None and v == v for v in (o, hi, lo)):
        return False
    hit = o >= pc * 1.095 if side == "up" else o <= pc * 0.905
    return bool(hit and hi == lo)


Logic2._locked = _locked


def run_one(name, strat, universe, out_dir=OUT):
    Stock_API.get_all_stock_information = staticmethod(lambda: list(universe))
    bt = BacktestSystem("", "")
    bt.set_backtest_period(START, END)
    bt.set_cash_balance(INIT_CASH)
    bt.execute_strategy(name, strat.select, strat.trade)
    perf, detail = bt.calculate_performance()
    bt.save_performance_to_xls(name, perf, detail, os.path.join(out_dir, f"{name}.xlsx"))
    daily = pd.DataFrame([{"date": d.record_date, "stock": d.stock_assets, "total": d.stock_assets + d.cash_assets} for d in detail.daily_values_list])
    eq = daily["total"] / INIT_CASH
    r = eq.pct_change().dropna()
    sells = [t for t in detail.historical_transactions_list if t.action == 1 and t.error_status.status]
    # 框架不扣成本 → 由委託紀錄逐筆估算:買 0.1425%、賣 0.1425% + 證交稅 0.3%,按日累計後從資產扣除
    fee = {}
    for t in detail.historical_transactions_list:
        if not t.error_status.status:
            continue
        if t.action == 2:
            v = t.buy_price * t.shares * FEE_BUY
        elif t.action == 1:
            v = t.sell_price * t.shares * FEE_SELL
        else:
            continue
        fee[t.date] = fee.get(t.date, 0.0) + v
    cumfee = pd.Series([fee.get(d, 0.0) for d in daily["date"]]).cumsum()
    eq_net = (daily["total"] - cumfee) / INIT_CASH
    traded = sum(t.buy_price * t.shares for t in detail.historical_transactions_list if t.action == 2 and t.error_status.status)
    trade_days = len({t.date for t in detail.historical_transactions_list if t.error_status.status and t.action in (1, 2)})
    return {"total_return_pct": round((perf.total_assets - INIT_CASH) / INIT_CASH * 100, 2),
            "net_return_pct": round(float(eq_net.iloc[-1] - 1) * 100, 2),
            "net_max_dd_pct": round(float((eq_net / eq_net.cummax() - 1).min()) * 100, 2),
            "net_sharpe": round(float(eq_net.pct_change().dropna().mean() / eq_net.pct_change().dropna().std() * math.sqrt(246)), 2),
            "fees_total": round(float(cumfee.iloc[-1]), 0),
            "buy_turnover_x": round(traded / float(daily["total"].mean()), 1),
            "n_trade_days": trade_days, "n_days": len(daily),
            "max_dd_pct": round(float((eq / eq.cummax() - 1).min()) * 100, 2),
            "daily_sharpe_ann": round(float(r.mean() / r.std() * math.sqrt(246)), 2) if r.std() > 0 else 0.0,
            "avg_exposure_pct": round(float((daily["stock"] / daily["total"]).mean()) * 100, 1),
            "n_round_trips": len(sells), "win_rate": round(float(np.mean([t.profit > 0 for t in sells])), 3) if sells else None,
            "avg_trade_ret_pct": round(float(np.mean([t.profit / (t.buy_price * t.shares) * 100 for t in sells])), 2) if sells else None,
            "n_liq_filtered": strat.n_liq, "n_mkt_blocked": strat.n_mkt_block, "n_kept": strat.n_kept,
            "n_stop_exits": strat.n_sl, "n_tp_exits": strat.n_tp,
            "curve": {d.strftime("%Y-%m-%d"): round(float(v - 1) * 100, 2) for d, v in zip(daily["date"], eq)},
            "curve_net": {d.strftime("%Y-%m-%d"): round(float(v - 1) * 100, 2) for d, v in zip(daily["date"], eq_net)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    tw50 = [code(t) for t in TICKER_SETS["tw50"]]
    avail = assemble_csv(tw50 + ["0050"])
    uni = [c for c in tw50 if c in avail]
    ind, liq, mkt, ranking = load_indicators(uni), load_liquidity(uni), load_market(), load_ranking()
    combos = list(itertools.product(LIQ, MKT, HYS, STOPS))
    if a.only:
        combos = [tuple(a.only.split("|", 3))]
    summ = {}
    for l, m, h, s in combos:
        name = f"{l}|{m}|{h}|{s}"
        stop, take = STOPS[s]
        strat = Logic2(name, uni, ranking, ind, liq, mkt, LIQ[l], MKT[m], HYS[h], stop, take)
        res = run_one(name.replace("|", "_").replace("%", "pct"), strat, uni)
        res.update({"liq": l, "mkt": m, "hys": h, "stops": s})
        summ[name] = res
        print(f"{name:28s} 總收益 {res['total_return_pct']:+8.2f}%  MDD {res['max_dd_pct']:6.2f}%  Sharpe {res['daily_sharpe_ann']:5.2f}  持股比 {res['avg_exposure_pct']:5.1f}%  來回 {res['n_round_trips']:3d}  勝率 {res['win_rate']}  流動性濾 {res['n_liq_filtered']} 大盤擋 {res['n_mkt_blocked']} 續抱 {res['n_kept']} 停損 {res['n_stop_exits']} 停利 {res['n_tp_exits']}", flush=True)
    json.dump(summ, open(os.path.join(HERE, "out", "summary_logic2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[SAVED] out/summary_logic2.json ({len(summ)} 組)")


if __name__ == "__main__":
    main()
