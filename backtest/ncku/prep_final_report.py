"""最終報告資料:最佳系統(每日檢視、抱 3 檔、掉出前 3 名且抱滿 10 日才換、不看大盤、不設停損停利)
全年與 7/1 起兩段重跑(官方資料、框架、扣成本),連同基準、候選比較、穩健度格點 → results/final_best.json
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
import run_ncku as R                                   # noqa: E402
from run_ncku import assemble_csv, code                 # noqa: E402
from run_logic import load_indicators                   # noqa: E402
import run_logic2 as L2                                 # noqa: E402
from run_window import ranking                          # noqa: E402
from data_loader import TICKER_SETS                     # noqa: E402

OUT = os.path.join(HERE, "out", "final_best")
os.makedirs(OUT, exist_ok=True)
END = "20260911"
NAMES = {k: v["name"] for k, v in json.load(open(os.path.join(HERE, "backtest", "stock_api", "stock_symbol_map.json"), encoding="utf-8")).items()}
CFG = dict(K=3, exit_rank=3, min_hold=10, mkt="none")


def run_cfg(start, name, k, er, mh, mk, stop=None, take=None, liq="vol2k"):
    R.START, R.END, L2.START, L2.END = start, END, start, END
    rk = ranking(pd.Timestamp(start), 1)
    st = L2.Logic2(name, UNI, rk, IND, LIQ, MKT, L2.LIQ[liq], L2.MKT[mk], er, stop, take, topk=k, maxrank=max(15, 2 * k), min_hold=mh)
    return L2.run_one(name, st, UNI, OUT)


def ledger(xlsx):
    x = pd.ExcelFile(xlsx)
    o = x.parse("歷史交易委託")
    o["股票代碼"] = o["股票代碼"].astype(str).str.zfill(4)
    rows, open_pos = [], {}
    for _, w in o.sort_values("交易日期", kind="stable").iterrows():
        c = w["股票代碼"]
        if w["交易動作"] == "買入":
            open_pos[c] = {"code": c, "name": NAMES.get(c, ""), "buy_date": w["交易日期"].strftime("%Y-%m-%d"), "buy": float(w["成交價格"]), "shares": int(w["交易股數"])}
        else:
            p = open_pos.pop(c)
            p.update({"sell_date": w["交易日期"].strftime("%Y-%m-%d"), "sell": float(w["成交價格"])})
            p["ret_pct"] = round((p["sell"] / p["buy"] - 1) * 100, 2)
            p["pnl"] = round((p["sell"] - p["buy"]) * p["shares"])
            p["days"] = int(pd.bdate_range(p["buy_date"], p["sell_date"]).size - 1)
            rows.append(p)
    held = []
    for c, p in open_pos.items():
        x = pd.read_parquet(os.path.join(R.SRC, f"{c}.parquet")).sort_values("date")
        last = x.iloc[-1]
        p.update({"last_date": pd.Timestamp(last["date"]).strftime("%Y-%m-%d"), "last": float(last["close"])})
        p["ret_pct"] = round((p["last"] / p["buy"] - 1) * 100, 2)
        p["pnl"] = round((p["last"] - p["buy"]) * p["shares"])
        held.append(p)
    return rows, held


def monthly(curve):
    s = pd.Series(curve)
    s.index = pd.to_datetime(s.index)
    eq = 1 + s / 100
    m = eq.groupby(eq.index.to_period("M")).last()
    prev = pd.concat([pd.Series([1.0], index=[m.index[0] - 1]), m])
    return {str(k): round(float(v) * 100, 2) for k, v in prev.pct_change().dropna().items()}


def main():
    global UNI, IND, LIQ, MKT
    tw50 = [code(t) for t in TICKER_SETS["tw50"]]
    avail = assemble_csv(tw50 + ["0050"])
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write(f"end_date: '{END}'\nstart_date: '20251001'\n")
    UNI = [c for c in tw50 if c in avail]
    IND, LIQ, MKT = load_indicators(UNI), L2.load_liquidity(UNI), L2.load_market()

    out = {"config": CFG, "end": "2026-09-11", "init_cash": 1_000_000}
    for win, start in [("full", "20260102"), ("jul", "20260630")]:
        best = run_cfg(start, f"best_{win}", CFG["K"], CFG["exit_rank"], CFG["min_hold"], CFG["mkt"])
        peak = run_cfg(start, f"peak_{win}", 3, 10, 15, "none")
        trades, held = ledger(os.path.join(OUT, f"best_{win}.xlsx"))
        bw = json.load(open(os.path.join(HERE, "out", f"summary_window_{start}_20260911.json"), encoding="utf-8"))
        out[win] = {
            "best": {k: v for k, v in best.items() if k not in ("curve", "curve_net")} | {"curve": best["curve_net"], "monthly": monthly(best["curve_net"])},
            "peak": {k: v for k, v in peak.items() if k not in ("curve", "curve_net")} | {"curve": peak["curve_net"]},
            "b0050": {"total_return_pct": bw["bench_0050"]["total_return_pct"], "max_dd_pct": bw["bench_0050"]["max_dd_pct"], "curve": bw["bench_0050"]["curve"], "monthly": monthly(bw["bench_0050"]["curve"])},
            "ew": {"total_return_pct": bw["bench_tw50_ew"]["total_return_pct"], "max_dd_pct": bw["bench_tw50_ew"]["max_dd_pct"], "curve": bw["bench_tw50_ew"]["curve"], "monthly": monthly(bw["bench_tw50_ew"]["curve"])},
            "trades": trades, "held": held,
        }
        print(win, "best", best["total_return_pct"], best["net_return_pct"], best["net_max_dd_pct"], "trades", len(trades), "held", [h["code"] for h in held])

    # 穩健度格點:K3、不看大盤、續抱 × 最短持有(全年扣成本)
    mp = json.load(open(os.path.join(HERE, "out", "summary_maxprofit.json"), encoding="utf-8"))
    grid = [{"exit_rank": r["exit_rank"], "min_hold": r["min_hold"], "net": r["net_return_pct"], "mdd": r["net_max_dd_pct"], "days": r["n_trade_days"]}
            for r in mp.values() if r["window"] == "全年" and r["K"] == 3 and r["mkt"] == "none"]
    out["grid_k3"] = sorted(grid, key=lambda r: (r["exit_rank"], r["min_hold"]))
    byk = pd.DataFrame([r for r in mp.values() if r["window"] == "全年"]).groupby("K")["net_return_pct"].agg(["mean", "median", "min", "max"]).round(1)
    out["by_k"] = [{"K": int(k), **{c: float(v) for c, v in row.items()}} for k, row in byk.iterrows()]

    # 走到這裡的路:各階段代表設定(全年,扣成本;5 日版取 5 種起跑日平均)
    ph = json.load(open(os.path.join(HERE, "out", "fullyear_phase_sensitivity.json"), encoding="utf-8"))
    avg = lambda k: round(sum(r[k] for r in ph) / len(ph), 1)
    nc = json.load(open(os.path.join(HERE, "out", "summary_ncku.json"), encoding="utf-8"))
    dg = json.load(open(os.path.join(HERE, "out", "summary_daily_grid.json"), encoding="utf-8"))
    out["path"] = [
        {"stage": "KLINE K 線型態(系統 A)", "setting": "1 日 7 特徵,訊號做多持有 5 日", "net": None, "gross": nc["kline_1d7"]["total_return_pct"], "note": "框架未扣成本;平均只有四成資金在場"},
        {"stage": "Chart-GCN(系統 B)", "setting": "gridbest h=5,前 10% 每 5 日換", "net": None, "gross": nc["cgcn_h5_rank"]["total_return_pct"], "note": "框架未扣成本;模型輸出近乎常數,排序不可信"},
        {"stage": "XGB + 交易邏輯 v2", "setting": "5 日檢視、抱 5 檔、大盤濾網、前 10 名續抱、3×ATR 停損 + 30% 停利", "net": avg("系統扣成本"), "gross": None, "note": "5 種起跑日平均;1/2 起算那種 +223% 是最幸運的"},
        {"stage": "XGB 只有模型", "setting": "5 日檢視、抱 5 檔、每次全換", "net": avg("只有模型扣成本"), "gross": None, "note": "5 種起跑日平均,範圍 +106% ~ +213%"},
        {"stage": "XGB 每日檢視", "setting": "抱 5 檔、前 10 名續抱、抱滿 10 日、大盤濾網", "net": dg["全年|前10名續抱|最短10日|none"]["net_return_pct"], "gross": None, "note": "每天只有一種跑法,不看起跑日運氣"},
        {"stage": "最佳系統", "setting": "每日檢視、抱 3 檔、掉出前 3 名且抱滿 10 日才換、不看大盤", "net": out["full"]["best"]["net_return_pct"], "gross": None, "note": "參數挪一格平均 +207%"},
        {"stage": "帳面最高(不採用)", "setting": "抱 3 檔、前 10 名續抱、抱滿 15 日、不看大盤", "net": out["full"]["peak"]["net_return_pct"], "gross": None, "note": "孤立高點,7/1 起 -9.5%"},
    ]
    fp = os.path.join(HERE, "..", "results", "final_best.json")
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[SAVED]", os.path.relpath(fp, HERE))


if __name__ == "__main__":
    main()
