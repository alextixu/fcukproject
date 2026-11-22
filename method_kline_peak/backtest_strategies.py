"""用主軸的判斷試不同的交易策略(2024–2025;不訓練新模型或新特徵)。

判斷:主軸,TW200 剔除低波動 168 檔,walk-forward 測 2024 / 2025(前 4 年訓練),種子 42、門檻 0%;
      每年的混淆矩陣須和 results/confusion_2024_2026_tw200.json 相同(腳本內核對)。
交易慣例(同 backtest_top3 / backtest_years.simulate):t 收盤出訊號 → t+1 開盤買;「持有 N 天」= 進場日算第 1 天,第 N 個交易日收盤賣
      (= 訊號日之後第 N 個交易日);訊號出場與停損 = 訊號(或觸發)隔天開盤賣;期末最後一天收盤平倉。還原價;只做多;
      成本一趟來回 0.585%(買 0.1425%、賣 0.1425% + 稅 0.3%),每個結果另列沒扣成本;起始 100 萬,最多同時 K 檔,
      每檔 = 前一天總資產 / K(不超過現金,整股);滿倉或已持有時新訊號跳過;同一天訊號多於空位時分數高者優先、同分隨機(seed 0)。
策略
  A 每天買判低點、分數最高的前 K 檔,持有 N 天(K = 3、5;N = 5、10、20)
  B 判低點買;同一檔判高點隔天開盤賣,或最多持有 20 天(K = 3、5)
  C 判低點後 t+1 ~ t+k 收盤都不低於 t 收盤才在 t+k 收盤確認、隔天開盤買,持有 10 天(k = 1、2、3;K = 5)
  D A(K = 5、N = 10)加過濾:D1 個股收盤 > 60 日均線;D2 0050 收盤 > 60 日均線;D3 兩者都要(都用 t 當天以前的資料)
  E 168 檔等權各一份:一開始全部持有,判高點隔天開盤賣、之後判低點隔天開盤買回(和 168 檔等權買進持有比)
  F A(K = 5、N = 10)只取高信心:當天判低點裡 OC-SVM 分數前 10%(至少 1 檔)
  停損版:A、B、C、D 各加「收盤虧損超過 8%(收盤 < 進場價 × 0.92)→ 隔天開盤賣」
輸出:全部組合(扣成本 / 沒扣成本,合計與逐年)、依扣成本合計排序,另列 0050 買進持有、168 檔等權買進持有
      → results/backtest_strategies_2024_2025.json
用法: python method_kline_peak/backtest_strategies.py
"""
import json
import math
import os
import pickle
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

import mainline as ML
import walkforward as WF
from confusion import summarize
from feasibility import P, clean
from learn5_trade6 import UP, DOWN
from paper_aeocsvm import NAMES

POOL = "tw200"
INIT = 1_000_000.0
STOP = 0.08
CACHE = os.path.join(ML.OUT, ".cache_strategy_signals")             # 每日判斷快取(不進 git)
OUT_JSON = os.path.join(ML.OUT, "backtest_strategies_2024_2025.json")
KEY = "confusion_rows_true_cols_pred(漲,不漲不跌,跌)"


@dataclass(frozen=True)
class Cost:
    buy: float = 0.001425
    sell: float = 0.001425
    tax: float = 0.003


COST, NO_COST = Cost(), Cost(0.0, 0.0, 0.0)


# ─────────────────────────── 市場資料 ───────────────────────────
class Market:
    """一段期間的交易日曆與每天的開盤 / 收盤(先整理好,回測迴圈裡不用逐檔查表)。"""

    def __init__(self, px, start, end):
        self.px, self.start, self.end = px, pd.Timestamp(start), pd.Timestamp(end)
        self.cal = sorted({d for df in px.values() for d in df.index if self.start <= d <= self.end})
        self.last_day = self.cal[-1]
        self.by_day = {}
        for tk, df in px.items():
            sub = df.loc[self.start:self.end]
            for d, o, c in zip(sub.index, sub["open"].to_numpy(), sub["close"].to_numpy()):
                self.by_day.setdefault(d, {})[tk] = (o, c)


# ─────────────────────────── 回測引擎 ───────────────────────────
def run(mkt, orders, K, cost=COST, sells=None, stop=None, seed=0, init=INIT):
    """orders:DataFrame[date(訊號日 t), ticker, score, hold(持有天數;None = 到期末)]。
    sells:DataFrame[date, ticker](訊號日;持有中 → 隔天開盤賣)。stop:收盤 < 進場價 × (1 − stop) → 隔天開盤賣。
    慣例同 backtest_years.simulate(只做多):回傳 {"equity", "trades", "skipped"}。"""
    px, last_day = mkt.px, mkt.last_day
    rng = np.random.default_rng(seed)
    book, skipped = {}, {"已持有": 0, "沒有空位": 0, "錢不夠一股": 0, "跨期": 0}
    for r in orders.itertuples(index=False):
        idx = px[r.ticker].index
        i = idx.searchsorted(r.date)
        if i + 1 >= len(idx) or idx[i] != r.date or idx[i + 1] > last_day or idx[i + 1] < mkt.start:
            skipped["跨期"] += 1
            continue
        hold = None if r.hold is None or (isinstance(r.hold, float) and math.isnan(r.hold)) else int(r.hold)
        exit_d = last_day if hold is None else idx[min(i + hold, len(idx) - 1)]
        book.setdefault(idx[i + 1], []).append((r.score, rng.random(), r.ticker, r.date, min(exit_d, last_day)))
    early = set()
    if sells is not None:
        for r in sells.itertuples(index=False):
            idx = px[r.ticker].index
            i = idx.searchsorted(r.date)
            if i + 1 < len(idx) and idx[i] == r.date:
                early.add((r.ticker, idx[i + 1]))
    cash, held, trades, equity, last_close, flag = init, {}, [], {}, {}, set()
    prev_equity = init

    def close_out(tk, d, p, how):
        nonlocal cash
        h = held.pop(tk)
        proceeds = h["shares"] * p * (1 - cost.sell - cost.tax)
        cash += proceeds
        trades.append({"ticker": tk, "signal": h["signal"], "entry": h["entry"], "exit": d, "shares": h["shares"], "buy_px": h["buy_px"],
                       "sell_px": p, "net_ret": proceeds / h["cost"] - 1, "pnl": proceeds - h["cost"], "how": how})

    for d in mkt.cal:
        today = mkt.by_day[d]
        for tk in [k for k, h in held.items() if k in today and h["entry"] < d and ((k, d) in early or k in flag)]:
            close_out(tk, d, today[tk][0], "停損" if tk in flag else "訊號出場")        # 開盤:訊號出場 / 停損
            flag.discard(tk)
        for score, _, tk, t, exit_d in sorted(book.get(d, []), key=lambda o: (-o[0], o[1])):
            if tk in held:
                skipped["已持有"] += 1
                continue
            if len(held) >= K:
                skipped["沒有空位"] += 1
                continue
            o = today[tk][0]
            sh = math.floor(min(cash, prev_equity / K) / (o * (1 + cost.buy)))
            if sh <= 0:
                skipped["錢不夠一股"] += 1
                continue
            c = sh * o * (1 + cost.buy)
            cash -= c
            held[tk] = {"shares": sh, "cost": c, "entry": d, "signal": t, "exit": exit_d, "buy_px": o}
        for tk, (o, c) in today.items():
            last_close[tk] = c
        for tk in [k for k, h in held.items() if h["exit"] == d or d == last_day]:      # 收盤:到期或期末
            close_out(tk, d, last_close[tk], "期末" if d == last_day else "到期")
            flag.discard(tk)
        if stop:
            for tk, h in held.items():
                if tk in today and today[tk][1] < h["buy_px"] * (1 - stop):
                    flag.add(tk)
        prev_equity = cash + sum(h["shares"] * last_close[tk] for tk, h in held.items())
        equity[d] = prev_equity
    return {"equity": pd.Series(equity), "trades": pd.DataFrame(trades), "skipped": skipped}


def run_switch(mkt, sig, cost=COST, init=INIT, use_signals=True):
    """E:每檔一份等額子帳戶,第一天開盤全部買進;判高點隔天開盤賣、之後判低點隔天開盤買回;期末收盤賣。
    use_signals=False = 168 檔等權買進持有。回傳 {"equity", "trades"}。"""
    tickers = [tk for tk, df in mkt.px.items() if mkt.cal[0] in df.index]
    each = init / len(tickers)
    s = sig[sig.pred.isin([UP, DOWN])] if use_signals else sig.iloc[0:0]
    nxt = {}                                                          # (ticker, 執行日) → UP 買回 / DOWN 賣出
    for r in s.itertuples(index=False):
        idx = mkt.px[r.ticker].index
        i = idx.searchsorted(r.date)
        if i + 1 < len(idx) and idx[i] == r.date and mkt.start <= idx[i + 1] <= mkt.last_day:
            nxt[(r.ticker, idx[i + 1])] = r.pred
    curves, trades = [], []
    for tk in tickers:
        w = mkt.px[tk].loc[mkt.start:mkt.end]
        cash, sh, entry, cost_in, vals = 0.0, each / (w["open"].iloc[0] * (1 + cost.buy)), w.index[0], each, []
        for d, o, c in zip(w.index, w["open"].to_numpy(), w["close"].to_numpy()):
            a = nxt.get((tk, d))
            if a == DOWN and sh > 0 and entry < d:
                cash = sh * o * (1 - cost.sell - cost.tax)
                trades.append({"ticker": tk, "entry": entry, "exit": d, "net_ret": cash / cost_in - 1})
                sh = 0.0
            elif a == UP and sh == 0 and cash > 0:
                sh, entry, cost_in, cash = cash / (o * (1 + cost.buy)), d, cash, 0.0
            vals.append(cash + sh * c)
        if sh > 0:                                                    # 期末收盤賣
            final = sh * w["close"].iloc[-1] * (1 - cost.sell - cost.tax)
            trades.append({"ticker": tk, "entry": entry, "exit": w.index[-1], "net_ret": final / cost_in - 1})
            vals[-1] = final
        curves.append(pd.Series(vals, index=w.index))
    eq = pd.concat(curves, axis=1).reindex(mkt.cal).ffill().sum(axis=1)
    return {"equity": eq, "trades": pd.DataFrame(trades)}


def buy_hold_one(mkt, tk_df, cost=COST, init=INIT):
    """單一標的買進持有(0050):第一天開盤買、最後一天收盤賣。"""
    w = tk_df.loc[mkt.start:mkt.end]
    sh = init / (w["open"].iloc[0] * (1 + cost.buy))
    eq = (sh * w["close"]).reindex(mkt.cal).ffill()
    eq.iloc[-1] = sh * w["close"].iloc[-1] * (1 - cost.sell - cost.tax)
    return {"equity": eq, "trades": pd.DataFrame([{"entry": w.index[0], "exit": w.index[-1], "net_ret": eq.iloc[-1] / init - 1}])}


# ─────────────────────────── 績效 ───────────────────────────
def perf(equity, trades, init=INIT):
    eq = equity.dropna()
    n = len(eq)
    tot = eq.iloc[-1] / init - 1
    t = trades if len(trades) else pd.DataFrame({"net_ret": []})
    return {"total_return_pct": round(tot * 100, 2), "annualized_pct": round(((1 + tot) ** (252 / n) - 1) * 100, 2) if n else None,
            "max_dd_pct": round(float((eq / eq.cummax() - 1).min()) * 100, 2), "n_trades": int(len(t)),
            "win_rate_pct": round(float((t.net_ret > 0).mean()) * 100, 1) if len(t) else None,
            "avg_trade_pct": round(float(t.net_ret.mean()) * 100, 2) if len(t) else None}


def perf_by_year(res, init=INIT):
    """合計 + 每年(每年報酬 = 該年底資產 / 上一年底資產;交易依進場年份)。"""
    eq, tr = res["equity"], res["trades"]
    out = {"合計": perf(eq, tr, init)}
    base = init
    for y in sorted({d.year for d in eq.index}):
        e = eq[eq.index.year == y]
        t = tr[pd.to_datetime(tr["entry"]).dt.year == y] if len(tr) else tr
        out[str(y)] = perf(pd.concat([pd.Series([base], index=[e.index[0] - pd.Timedelta(days=1)]), e]), t, base)
        base = e.iloc[-1]
    return out


# ─────────────────────────── 判斷與策略 ───────────────────────────
def load_signals(years, data):
    """每年 walk-forward 的主軸每日判斷,並核對混淆矩陣 = confusion_2024_2026_tw200.json。"""
    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, ".gitignore"), "w") as f:                 # 快取不進 git
        f.write("*\n")
    ref = json.load(open(os.path.join(ML.OUT, "confusion_2024_2026_tw200.json"), encoding="utf-8"))
    out, panel = [], None
    for y in years:
        path = os.path.join(CACHE, f"{POOL}_{y}_main.pkl")
        if os.path.exists(path):
            sig = pickle.load(open(path, "rb"))
        else:
            if panel is None:
                panel, fc = ML.build_panel(data, 6, [])
            sig, _ = WF.run_year(panel, fc, y, WF.MainlineSource())
            pickle.dump(sig, open(path, "wb"))
        cm = summarize(sig["y"].to_numpy(), sig["pred"].to_numpy(), NAMES)[KEY]
        assert cm == ref[str(y)]["主軸"][KEY], y
        out.append(sig)
    return pd.concat(out, ignore_index=True)


def ma_filter(px, mkt_px, sig, kind):
    """D 的過濾:t 當天收盤 > 60 日均線(個股 / 0050 / 兩者)。"""
    keep = np.ones(len(sig), bool)
    if kind in ("D1", "D3"):
        above = {tk: (df["close"] > df["close"].rolling(60, min_periods=60).mean()) for tk, df in px.items()}
        keep &= np.array([bool(above[r.ticker].get(r.date, False)) for r in sig.itertuples(index=False)])
    if kind in ("D2", "D3"):
        c = mkt_px["close"]
        up = (c > c.rolling(60, min_periods=60).mean()).reindex(sig["date"]).fillna(False).astype(bool).to_numpy()
        keep &= up
    return sig[keep]


def confirm_orders(px, lows, k):
    """C:t+1 ~ t+k 收盤都 ≥ t 收盤 → 訊號日改成 t+k(確認日);否則取消。"""
    rows = []
    for r in lows.itertuples(index=False):
        idx, c = px[r.ticker].index, px[r.ticker]["close"].to_numpy()
        i = idx.searchsorted(r.date)
        if idx[i] != r.date or i + k >= len(idx):
            continue
        if (c[i + 1:i + k + 1] >= c[i]).all():
            rows.append((idx[i + k], r.ticker, r.score))
    return pd.DataFrame(rows, columns=["date", "ticker", "score"])


def strategies():
    """全部組合(名稱 → 參數)。"""
    out = {}
    for stop in (None, STOP):
        sfx = "+停損" if stop else ""
        for K in (3, 5):
            for N in (5, 10, 20):
                out[f"A K{K} N{N}{sfx}"] = dict(kind="A", K=K, N=N, stop=stop)
        for K in (3, 5):
            out[f"B K{K} 高點出場或20天{sfx}"] = dict(kind="B", K=K, N=20, stop=stop)
        for k in (1, 2, 3):
            out[f"C k{k} K5 N10{sfx}"] = dict(kind="C", K=5, N=10, k=k, stop=stop)
        for d in ("D1", "D2", "D3"):
            out[f"{d} K5 N10{sfx}"] = dict(kind="D", K=5, N=10, filt=d, stop=stop)
    out["E 高點出場、低點買回(168 檔等權)"] = dict(kind="E")
    out["F 高信心 K5 N10"] = dict(kind="F", K=5, N=10, stop=None)
    return out


def build(spec, sig, px, mkt_px):
    """策略參數 → (orders, sells)。"""
    lows = sig[sig.pred == UP][["date", "ticker", "score"]]
    sells = None
    if spec["kind"] == "C":
        lows = confirm_orders(px, lows, spec["k"])
    elif spec["kind"] == "D":
        lows = ma_filter(px, mkt_px, lows, spec["filt"])
    elif spec["kind"] == "F":
        s = lows.sort_values(["date", "score", "ticker"], ascending=[True, False, True])
        rank = s.groupby("date").cumcount().to_numpy()
        n = s.groupby("date")["ticker"].transform("size").to_numpy()
        lows = s[rank < np.maximum(1, np.floor(n * 0.10))]
    if spec["kind"] == "B":
        sells = sig[sig.pred == DOWN][["date", "ticker"]]
    return lows.assign(hold=spec["N"]), sells


def run_spec(spec, sig, px, mkt_px, mkt, cost=COST):
    if spec["kind"] == "E":
        return run_switch(mkt, sig, cost)
    orders, sells = build(spec, sig, px, mkt_px)
    return run(mkt, orders, spec["K"], cost, sells=sells, stop=spec.get("stop"))


# ─────────────────────────── 執行 ───────────────────────────
def setup(years):
    data = ML.load_data(pool=POOL)
    px = {tk: clean(df)[["open", "close"]] for tk, df in data.items()}
    mkt_px = clean(pd.read_parquet(os.path.join(P.YF_2026_CACHE, "0050.TW.parquet")))[["open", "close"]]
    return data, px, mkt_px, load_signals(years, data)


def explore():
    t0 = time.time()
    data, px, mkt_px, sig = setup((2024, 2025))
    ref = json.load(open(os.path.join(ML.OUT, "backtest_long_only_tw200.json"), encoding="utf-8"))["years"]
    for y in (2024, 2025):                                        # 核對:A K3 N5 單年 = backtest_top3 的 TW200 回測
        s = sig[sig.date.dt.year == y]
        r = run(Market(px, f"{y}-01-01", f"{y}-12-31"), s[s.pred == UP][["date", "ticker", "score"]].assign(hold=5), 3)
        assert round(r["equity"].iloc[-1] / INIT * 100 - 100, 2) == ref[str(y)]["主軸"]["扣成本"]["total_return_pct"], y
    mkt = Market(px, "2024-01-01", "2025-12-31")
    res = {"period": ["2024-01-01", "2025-12-31"], "init_cash": INIT, "cost_round_trip_pct": 0.585, "results": {}, "baselines": {}}
    for name, spec in strategies().items():
        net = run_spec(spec, sig, px, mkt_px, mkt, COST)
        gross = run_spec(spec, sig, px, mkt_px, mkt, NO_COST)
        res["results"][name] = {"spec": spec, "扣成本": perf_by_year(net), "沒扣成本": perf_by_year(gross)}
        r = res["results"][name]["扣成本"]["合計"]
        print(f"{name:<28} 扣成本 {r['total_return_pct']:+8.2f}%  回撤 {r['max_dd_pct']}%  {r['n_trades']} 筆  ({time.time() - t0:.0f}s)", flush=True)
    res["baselines"]["0050 買進持有"] = {"扣成本": perf_by_year(buy_hold_one(mkt, mkt_px)), "沒扣成本": perf_by_year(buy_hold_one(mkt, mkt_px, NO_COST))}
    res["baselines"]["168 檔等權買進持有"] = {"扣成本": perf_by_year(run_switch(mkt, sig, COST, use_signals=False)),
                                         "沒扣成本": perf_by_year(run_switch(mkt, sig, NO_COST, use_signals=False))}
    rank = sorted(res["results"], key=lambda k: -res["results"][k]["扣成本"]["合計"]["total_return_pct"])
    res["ranking"] = [{"key": k, "total_return_net_pct": res["results"][k]["扣成本"]["合計"]["total_return_pct"],
                       "max_dd_net_pct": res["results"][k]["扣成本"]["合計"]["max_dd_pct"]} for k in rank]
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("前 3 名:", rank[:3])


def main():
    explore()


if __name__ == "__main__":
    main()
