"""Tom 的 PortfolioBuilder 規則放進 NCKU 框架,逐年回測(2021 ~ 2026),模型來自 tomt_port/tomt_walkforward.py。

原規則(tomt/Qmodel/src/inference/portfolio.py 預設值,依使用者要求拿掉流動性門檻,也不處理漲跌停):
  - 每週最後一個交易日收盤出訊號,下一個交易日開盤執行(框架 t+1)
  - 排名分數 = meta_alpha ÷ max(預測波動, 0.05);只買分數 > 0 的股票
  - 持有 3 檔、每檔 1/3 資金(不滿 3 檔就留現金)
  - 汰弱留強:持股分數仍 > 0 且排名 ≤ 12 就續抱
  - 動態停損:每週換股日檢查,開盤價相對進場價跌超過 clip(預測波動 × 4.5%, 1.5%, 4%) 就賣,且當週不再買回
同一年另跑:v3(我們的系統)、0050、同池等權。資料 NCKU_SRC=yf_hist,扣成本。
用法: NCKU_SRC=yf_hist python run_tomt.py --pool tw50
輸出: out/tomt/*.xlsx、out/summary_tomt.json
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
import run_ncku as R                                   # noqa: E402
from run_ncku import Strategy, BuyHoldStrategy, assemble_csv, code  # noqa: E402
from run_logic import load_indicators                   # noqa: E402
import run_logic2 as L2                                 # noqa: E402
from data_loader import TICKER_SETS                     # noqa: E402

RES = os.path.join(HERE, "..", "results")
OUT = os.path.join(HERE, "out", "tomt")
os.makedirs(OUT, exist_ok=True)
SUMM = os.path.join(HERE, "out", "summary_tomt.json")
CFG = dict(top_n=3, exit_rank=12, vol_multiplier=0.045, min_stop=0.015, max_stop=0.040)


class TomtStrategy(Strategy):
    def __init__(self, name, universe, signals, cfg, use_stop=True):
        super().__init__(name, universe)
        self.signals, self.cfg, self.use_stop = signals, cfg, use_stop   # {YYYYMMDD: DataFrame[code, score, vol] 依 score 降冪}
        self.entry, self.cur = {}, None
        self.n_stop = self.n_kept = 0
        self.n_liq = self.n_mkt_block = self.n_sl = self.n_tp = 0     # run_logic2.run_one 會讀這些欄位

    def pick(self, d, prev_pool):
        if d not in self.signals:
            return []
        self.cur = self.signals[d]
        return list(self.cur["code"])            # 全部候選,由 trade() 決定

    def trade(self, pool_info, inventory, cash, tool):
        self.day_idx += 1
        if not pool_info:
            return tool.transaction_record
        ok = lambda v: v is not None and v == v and v > 0
        held = {u.stock_info.stock_code: u for u in inventory}
        info = {s.stock_code: s for s in pool_info}
        sig = self.cur.reset_index(drop=True)
        sig["rank"] = np.arange(1, len(sig) + 1)
        pos = sig[sig["score"] > 0]
        vol = dict(zip(sig["code"], sig["vol"]))
        # 停損(以今天開盤價對進場價)
        stopped = set()
        if self.use_stop:
            for c, u in held.items():
                o = u.stock_info.price_open
                if ok(o) and c in self.entry:
                    sl = float(np.clip(vol.get(c, 0.45) * self.cfg["vol_multiplier"], self.cfg["min_stop"], self.cfg["max_stop"]))
                    if (o - self.entry[c]) / self.entry[c] < -sl:
                        stopped.add(c)
        buffer = set(pos[pos["rank"] <= self.cfg["exit_rank"]]["code"])
        kept = [c for c in held if c in buffer and c not in stopped]
        self.n_kept += len(kept); self.n_stop += len(stopped)
        equity = cash + sum(u.shares * next(v for v in (u.stock_info.price_open, u.stock_info.price_close, u.avg_price) if ok(v)) for u in held.values())
        for c, u in held.items():
            if c in kept:
                continue
            o = u.stock_info.price_open
            if not ok(o):
                continue
            tool.sell_stock(c, float(o), u.shares)
            cash += u.shares * float(o)
            self.entry.pop(c, None)
        need = self.cfg["top_n"] - len(kept)
        cands = [c for c in pos["code"] if c not in kept and c not in stopped and c in info and ok(info[c].price_open)][:max(0, need)]
        for c in cands:
            px = info[c].price_open
            sh = int(min(cash, equity / self.cfg["top_n"]) // px)
            if sh <= 0:
                continue
            tool.buy_stock(c, float(px), sh)
            cash -= sh * px
            self.entry[c] = float(px)
        return tool.transaction_record


def weekly_signals(preds, year):
    p = preds[preds["year"] == year].copy()
    p["score"] = p["meta_alpha"] / p["pred_vol_5d"].fillna(0.45).clip(lower=0.05)
    p["vol"] = p["pred_vol_5d"].fillna(0.45)
    p["wk"] = p["date"].dt.to_period("W")
    last = p.groupby("wk")["date"].max()
    sig = {}
    for d in sorted(last.values):
        x = p[p["date"] == d].sort_values("score", ascending=False)
        sig[pd.Timestamp(d).strftime("%Y%m%d")] = pd.DataFrame({"code": x["stock_id"].astype(str).values, "score": x["score"].values, "vol": x["vol"].values})
    return sig


def v3_ranking(pool, year):
    if pool != "tw50":
        return None
    if year == 2026:
        p = pd.read_parquet(os.path.join(RES, "tw50_h5_permpos_fullpred.parquet"))["p"]
    else:
        p = pd.read_parquet(os.path.join(R.XGB_EXP, f"x{str(year)[2:]}-tw50-h5-cs_testpred.parquet"))["p_full_permpos"]
    w = p[p.index.get_level_values("date").year == year].unstack("ticker").sort_index()
    return {d.strftime("%Y%m%d"): [code(t) for t in row.dropna().sort_values(ascending=False).index] for d, row in w.iterrows()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="tw50")
    a = ap.parse_args()
    summ = json.load(open(SUMM, encoding="utf-8")) if os.path.exists(SUMM) else {}
    preds = pd.read_parquet(os.path.join(RES, f"tomt_{a.pool}_preds.parquet"))
    preds["date"] = pd.to_datetime(preds["date"]); preds["stock_id"] = preds["stock_id"].astype(str)
    codes = [code(t) for t in TICKER_SETS[a.pool]]
    avail = assemble_csv(codes + ["0050"])
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write("end_date: '20261231'\nstart_date: '20200101'\n")
    uni = [c for c in codes if c in avail]
    ind, liq, mkt = load_indicators(uni), L2.load_liquidity(uni), L2.load_market()
    for year in sorted(preds["year"].unique()):
        days = sorted(preds.loc[preds["year"] == year, "date"].unique())
        start, end = pd.Timestamp(days[0]).strftime("%Y%m%d"), pd.Timestamp(days[-1]).strftime("%Y%m%d")
        R.START, R.END, L2.START, L2.END = start, end, start, end
        R.OUT = OUT
        rec = {"pool": a.pool, "year": int(year)}
        for bname, st, u in [("0050", BuyHoldStrategy(f"{a.pool}_b0050_{year}", uni + ["0050"], ["0050"]), uni + ["0050"]),
                             ("等權", BuyHoldStrategy(f"{a.pool}_ew_{year}", uni, uni), uni)]:
            r = R.run(st, u)
            rec[bname] = {"ret": r["total_return_pct"], "mdd": r["max_dd_pct"]}
        sig = weekly_signals(preds, year)
        for vname, use_stop in [("tomt", True), ("tomt無停損", False)]:
            st = TomtStrategy(f"{a.pool}_{vname}_{year}", uni, sig, CFG, use_stop)
            r = L2.run_one(f"{a.pool}_{vname}_{year}", st, uni, OUT)
            rec[vname] = {"ret": r["net_return_pct"], "gross": r["total_return_pct"], "mdd": r["net_max_dd_pct"], "sharpe": r["net_sharpe"],
                          "trade_days": r["n_trade_days"], "trips": r["n_round_trips"], "win": r["win_rate"], "exposure": r["avg_exposure_pct"],
                          "n_stop": st.n_stop, "curve": r["curve_net"] if vname == "tomt" else None}
        rk = v3_ranking(a.pool, int(year))
        if rk:
            st = L2.Logic2(f"{a.pool}_v3_{year}", uni, rk, ind, liq, mkt, L2.LIQ["vol2k"], L2.MKT["none"], 8, None, None, topk=3, maxrank=15, out_days=2)
            r = L2.run_one(f"{a.pool}_v3_{year}", st, uni, OUT)
            rec["v3"] = {"ret": r["net_return_pct"], "mdd": r["net_max_dd_pct"], "sharpe": r["net_sharpe"], "trade_days": r["n_trade_days"]}
        summ[f"{a.pool}|{year}"] = rec
        json.dump(summ, open(SUMM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        t = rec["tomt"]
        print(f"{a.pool} {year}: tomt {t['ret']:+7.1f}% (MDD {t['mdd']:6.1f}%, Sharpe {t['sharpe']:5.2f}, 停損 {t['n_stop']}, 持股比 {t['exposure']}%) | 無停損 {rec['tomt無停損']['ret']:+7.1f}% | "
              + (f"v3 {rec['v3']['ret']:+7.1f}% | " if "v3" in rec else "") + f"0050 {rec['0050']['ret']:+6.1f}%  等權 {rec['等權']['ret']:+6.1f}%", flush=True)
    print(f"[SAVED] {os.path.relpath(SUMM, HERE)}")


if __name__ == "__main__":
    main()
