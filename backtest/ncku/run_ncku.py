"""把三套方法 + 基準全部套進 NCKU 回測框架(backtest/backtest.py,原封不動的 BacktestSystem)跑 2026。

框架規則(全部沿用,不另加成本):
  - 第 t 日 select_stock() 選出的池,第 t+1 日 trade() 才能下單;委託價落在當日 [low, high] 即成交。
  - 無手續費、無證交稅、無滑價;零股可;現金不足拒單。
  - 績效 = 框架 calculate_performance() 的總收益率(以每日資產表最後一天的 現金+持股市值 計)。
統一執行口徑:訊號用 t 日收盤前資訊(模型機率 / K 線型態),t+1 日以「開盤價」下單。
持股市值用框架自己的每日資產表(當日收盤),這也是它算總收益率的來源。

用法(cwd 必須是本資料夾,框架用相對路徑 ./tmp):
  python run_ncku.py --strategies all
輸出:out/<策略>.xlsx(框架原生 5 張表)、out/summary_ncku.json
"""
import argparse
import glob
import json
import math
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
os.chdir(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
sys.path.insert(0, P.CHARTGCN_CORE)
from data_loader import TICKER_SETS                                              # noqa: E402
from backtest.backtest import BacktestSystem, Stock_API, Stock_Information_Memory  # noqa: E402

START, END = "20260102", "20260910"
INIT_CASH = 1_000_000.0
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
RES = os.path.join(HERE, "..", "results")
XGB_EXP = P.XGB_EXP
# 資料來源:official = 框架 fetchers 抓的證交所/櫃買官方日資料(正式口徑);yf = cache_2026 還原價(大池篩選用)
SRC = P.ncku_src()


# ─────────────────────────── 資料 ───────────────────────────
def assemble_csv(codes):
    """由 tmp/official/<code>.parquet(框架 fetchers 抓的官方資料)組成框架格式 tmp/stock_data.csv。"""
    frames, missing = [], []
    for c in codes:
        fp = os.path.join(SRC, f"{c}.parquet")
        if not os.path.exists(fp):
            missing.append(c)
            continue
        frames.append(pd.read_parquet(fp))
    if missing:
        print(f"[WARN] 官方資料缺 {len(missing)} 檔: {missing[:10]}")
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y%m%d")
    df["stock_code"] = df["stock_code_id"].astype(str)
    cols = ["stock_code", "date", "capacity", "turnover", "high", "low", "close", "change",
            "transaction_volume", "stock_code_id", "open"]
    df = df[cols].sort_values(["stock_code", "date"]).drop_duplicates(["stock_code", "date"])
    df.to_csv(os.path.join(HERE, "tmp", "stock_data.csv"), index=False)
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write("end_date: '20260910'\nstart_date: '20251001'\n")
    Stock_Information_Memory.stock_data = None
    return sorted(set(df["stock_code"]))


def code(tk):
    return tk.split(".")[0]


# ─────────────────────────── 訊號 ───────────────────────────
def load_rank_signal(parquet, pcol, h, top_frac=0.10):
    """(date, ticker) 機率 → {YYYYMMDD: [codes]},只在每 h 個交易日的再平衡日給名單(與十分位分析同節奏)。"""
    df = pd.read_parquet(parquet)
    df = df[df.index.get_level_values("date") <= pd.Timestamp("2026-09-10")]
    dates = sorted(df.index.get_level_values("date").unique())
    sig = {}
    for d in dates[::h]:
        sub = df.xs(d, level="date")[pcol].dropna()
        k = max(1, int(len(sub) * top_frac))
        sig[d.strftime("%Y%m%d")] = [code(t) for t in sub.nlargest(k).index]
    return sig


def load_kline_signal(setname):
    t = pd.read_parquet(os.path.join(RES, "kline_2026_trades.parquet"))
    t = t[(t["set"] == setname) & (t["side"] == 1)]      # 框架無法放空,只取做多訊號
    sig = {}
    for d, g in t.groupby("date"):
        sig[pd.Timestamp(d).strftime("%Y%m%d")] = [code(x) for x in g["ticker"]]
    return sig


def load_cgcn_pred(h):
    fp = os.path.join(RES, f"cgcn_testpred_h{h}.parquet")
    if not os.path.exists(fp):
        return None
    return pd.read_parquet(fp)


# ─────────────────────────── 策略 ───────────────────────────
class Strategy:
    """封裝 select / trade 兩個框架回呼;共用「持股帳」(進場交易日序號)。"""

    def __init__(self, name, universe):
        self.name = name
        self.universe = universe          # 框架的全市場清單(本池)
        self.day_idx = 0                  # 第幾個交易日(trade() 每呼叫一次 +1)
        self.entry = {}                   # code → 進場 day_idx

    # 框架回呼 ------------------------------------------------
    def select(self, all_stock_info, prev_pool, cash):
        d = all_stock_info[0].init_time.strftime("%Y%m%d") if all_stock_info else None
        return self.pick(d, prev_pool)

    def trade(self, pool_info, inventory, cash, tool):
        self.day_idx += 1
        held = {u.stock_info.stock_code: u for u in inventory}
        equity = cash + sum(u.shares * (u.stock_info.price_open or u.stock_info.price_close or u.avg_price) for u in held.values())
        sells = self.exits(held, pool_info)
        for c in sells:
            u = held[c]
            tool.sell_stock(c, u.stock_info.price_open, u.shares)
            cash += u.shares * u.stock_info.price_open
            self.entry.pop(c, None)
        buys = [s for s in pool_info if s.stock_code not in held or s.stock_code in sells]
        buys = [s for s in buys if s.price_open is not None and s.price_open > 0]
        n_alloc = self.n_slots(len(buys), len(held) - len(sells))
        for s in buys:
            alloc = min(cash, equity / n_alloc) if n_alloc else 0
            sh = int(alloc // s.price_open)
            if sh <= 0:
                continue
            tool.buy_stock(s.stock_code, s.price_open, sh)
            cash -= sh * s.price_open
            self.entry[s.stock_code] = self.day_idx
        return tool.transaction_record

    # 子類覆寫 ------------------------------------------------
    def pick(self, d, prev_pool):
        return []

    def exits(self, held, pool_info):
        return []

    def n_slots(self, n_buys, n_kept):
        return n_buys + n_kept


class RankStrategy(Strategy):
    """每 h 個交易日換一次:賣光舊持股,買進機率前 10%(等權)。"""

    def __init__(self, name, universe, signal):
        super().__init__(name, universe)
        self.signal = signal

    def pick(self, d, prev_pool):
        return self.signal.get(d, [])

    def exits(self, held, pool_info):
        return list(held) if pool_info else []

    def n_slots(self, n_buys, n_kept):
        return n_buys


class HoldNStrategy(Strategy):
    """訊號制:有訊號就買(隔日開盤),持有 N 個交易日後隔日開盤賣;每檔一格,格數 = 池大小。"""

    def __init__(self, name, universe, signal, hold):
        super().__init__(name, universe)
        self.signal, self.hold = signal, hold

    def pick(self, d, prev_pool):
        return [c for c in self.signal.get(d, []) if c not in self.entry]

    def exits(self, held, pool_info):
        return [c for c in held if c in self.entry and self.day_idx - self.entry[c] >= self.hold]

    def n_slots(self, n_buys, n_kept):
        return len(self.universe)


class PaperSec63Strategy(Strategy):
    """Li et al. 2022 §6.3:預測漲且空手 → 買;持有且(預測跌 或 MACD<0)→ 賣。逐檔一格。"""

    def __init__(self, name, universe, pred, close_df):
        super().__init__(name, universe)
        self.pred = pred                         # {(YYYYMMDD, code): p}
        macd = {}
        for c, s in close_df.items():
            e12, e26 = s.ewm(span=12, adjust=False).mean(), s.ewm(span=26, adjust=False).mean()
            macd[c] = (e12 - e26).ewm(span=100, adjust=False).mean()
        self.macd = macd
        self.today = None

    def pick(self, d, prev_pool):
        self.today = d
        return [c for c in self.universe if self.pred.get((d, c), 0.5) > 0.5 and c not in self.entry]

    def exits(self, held, pool_info):
        d = self.today
        out = []
        for c in held:
            p = self.pred.get((d, c))
            m = self.macd.get(c, pd.Series(dtype=float)).get(d, 0.0)
            if p is not None and (p <= 0.5 or m < 0):
                out.append(c)
        return out

    def n_slots(self, n_buys, n_kept):
        return len(self.universe)


class BuyHoldStrategy(Strategy):
    def __init__(self, name, universe, codes):
        super().__init__(name, universe)
        self.codes, self.done = codes, False

    def pick(self, d, prev_pool):
        if self.done:
            return []
        self.done = True
        return self.codes

    def n_slots(self, n_buys, n_kept):
        return n_buys


# ─────────────────────────── 執行 ───────────────────────────
def run(strategy: Strategy, universe):
    Stock_API.get_all_stock_information = staticmethod(lambda: list(universe))
    bt = BacktestSystem("", "")
    bt.set_backtest_period(START, END)
    bt.set_cash_balance(INIT_CASH)
    bt.execute_strategy(strategy.name, strategy.select, strategy.trade)
    perf, detail = bt.calculate_performance()
    xlsx = os.path.join(OUT, f"{strategy.name}.xlsx")
    bt.save_performance_to_xls(strategy.name, perf, detail, xlsx)
    daily = pd.DataFrame([{"date": d.record_date, "stock": d.stock_assets, "cash": d.cash_assets} for d in detail.daily_values_list])
    daily["total"] = daily["stock"] + daily["cash"]
    eq = daily["total"] / INIT_CASH
    r = eq.pct_change().dropna()
    n_ok = sum(1 for t in detail.historical_transactions_list if t.error_status.status)
    n_fail = sum(1 for t in detail.historical_transactions_list if not t.error_status.status)
    n_sell = sum(1 for t in detail.historical_transactions_list if t.action == 1 and t.error_status.status)
    wins = [t.profit for t in detail.historical_transactions_list if t.action == 1 and t.error_status.status]
    return {
        "total_return_pct": round((perf.total_assets - INIT_CASH) / INIT_CASH * 100, 2),
        "realized": round(perf.realized_profit, 0), "unrealized": round(perf.unrealized_profit, 0),
        "final_cash": round(perf.cash_assets, 0), "final_total": round(perf.total_assets, 0),
        "max_dd_pct": round(float((eq / eq.cummax() - 1).min()) * 100, 2),
        "daily_sharpe_ann": round(float(r.mean() / r.std() * math.sqrt(246)), 2) if r.std() > 0 else 0.0,
        "n_orders_ok": n_ok, "n_orders_rejected": n_fail, "n_round_trips": n_sell,
        "win_rate": round(float(np.mean([w > 0 for w in wins])), 3) if wins else None,
        "xlsx": os.path.relpath(xlsx, HERE),
        "curve": {d.strftime("%Y-%m-%d"): round(float(v - 1) * 100, 2) for d, v in zip(daily["date"], eq)},
    }


def build_strategies(which):
    tw50 = [code(t) for t in TICKER_SETS["tw50"]]
    tw200 = [code(t) for t in TICKER_SETS["tw200"]]
    S = {}
    # 基準
    S["bench_0050"] = (BuyHoldStrategy("bench_0050", tw50 + ["0050"], ["0050"]), tw50 + ["0050"])
    S["bench_tw50_ew"] = (BuyHoldStrategy("bench_tw50_ew", tw50, tw50), tw50)
    S["bench_tw200_ew"] = (BuyHoldStrategy("bench_tw200_ew", tw200, tw200), tw200)
    # KLINE(系統 A)
    for name, tag in [("1日-7特徵", "kline_1d7"), ("2日-10特徵", "kline_2d10"), ("3日-12特徵", "kline_3d12")]:
        S[tag] = (HoldNStrategy(tag, tw50, load_kline_signal(name), 5), tw50)
    # XGB(老師的方法)
    xgb_sets = [("x26-tw50-h5-cs", "p_frozen:e4-tw50-h5-cs:full_top20", 5, "xgb_tw50_h5_top20frozen", tw50),
                ("x26-tw50-h5-cs", "p_full_permpos", 5, "xgb_tw50_h5_permpos", tw50),
                ("x26-tw50-h5-cs", "p_full", 5, "xgb_tw50_h5_full", tw50),
                ("x26-tw50-h1", "p_full_permpos", 1, "xgb_tw50_h1_permpos", tw50),
                ("x26-tw200-h5-cs", "p_full_top20", 5, "xgb_tw200_h5_top20", tw200),
                ("x26-tw200-h5-cs", "p_full_permpos", 5, "xgb_tw200_h5_permpos", tw200),
                ("x26-tw200-h5-cs-frozen", "p_frozen:e5b-tw200-h5-cs:full_top20", 5, "xgb_tw200_h5_top20frozen", tw200),
                ("x26-tw200-h5-cs", "p_full", 5, "xgb_tw200_h5_full", tw200),
                ("x26-tw200-h20-cs", "p_full_top20", 20, "xgb_tw200_h20_top20", tw200),
                ("x26-tw200-h20-cs", "p_full_permpos", 20, "xgb_tw200_h20_permpos", tw200),
                ("x26-tw200-h20-cs-chip", "p_frozen:e6c-tw200-h20-cs-chip:full_top20", 20, "xgb_tw200_h20_chip_top20frozen", tw200),
                ("x26-tw200-h20-cs-chip", "p_full", 20, "xgb_tw200_h20_chip_full", tw200)]
    for tag, pcol, h, name, uni in xgb_sets:
        fp = os.path.join(XGB_EXP, f"{tag}_testpred.parquet")
        if os.path.exists(fp) and pcol in pd.read_parquet(fp).columns:
            S[name] = (RankStrategy(name, uni, load_rank_signal(fp, pcol, h)), uni)
    # Chart-GCN(系統 B)
    for h in (1, 5):
        pred = load_cgcn_pred(h)
        if pred is None:
            continue
        fp = os.path.join(RES, f"cgcn_testpred_h{h}.parquet")
        S[f"cgcn_h{h}_rank"] = (RankStrategy(f"cgcn_h{h}_rank", tw50, load_rank_signal(fp, "p_cgcn", h)), tw50)
        if h == 1:
            pm = {(d.strftime("%Y%m%d"), code(t)): float(p) for (d, t), p in pred["p_cgcn"].items()}
            closes = {}
            for c in tw50:
                f = os.path.join(SRC, f"{c}.parquet")
                if os.path.exists(f):
                    x = pd.read_parquet(f)
                    closes[c] = pd.Series(x["close"].values, index=pd.to_datetime(x["date"]).dt.strftime("%Y%m%d"))
            S["cgcn_h1_paper63"] = (PaperSec63Strategy("cgcn_h1_paper63", tw50, pm, closes), tw50)
    if which != "all":
        S = {k: v for k, v in S.items() if k in which.split(",")}
    return S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", default="all")
    a = ap.parse_args()
    S = build_strategies(a.strategies)
    summ_fp = os.path.join(OUT, "summary_ncku.json")
    summary = json.load(open(summ_fp, encoding="utf-8")) if os.path.exists(summ_fp) else {}
    for name, (strat, uni) in S.items():
        print(f"\n========== {name}  (池 {len(uni)} 檔) ==========", flush=True)
        avail = assemble_csv(uni + (["0050"] if "0050" not in uni else []))
        uni_ok = [c for c in uni if c in avail]
        strat.universe = uni_ok
        t0 = datetime.now()
        res = run(strat, uni_ok)
        res["pool_size"] = len(uni_ok)
        res["elapsed_s"] = round((datetime.now() - t0).total_seconds())
        summary[name] = res
        print(f"  總收益率 {res['total_return_pct']:+.2f}%  MDD {res['max_dd_pct']}%  委託 {res['n_orders_ok']} 成 / {res['n_orders_rejected']} 拒  "
              f"來回 {res['n_round_trips']}  勝率 {res['win_rate']}  ({res['elapsed_s']}s)", flush=True)
        json.dump(summary, open(summ_fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[SAVED] out/summary_ncku.json ({len(summary)} 個策略)")


if __name__ == "__main__":
    main()
