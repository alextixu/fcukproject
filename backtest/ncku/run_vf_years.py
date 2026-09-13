"""量增篩選模型 vs v3:同一套 v3 交易規則,逐年回測(2021 ~ 2026,walk-forward 模型)。

交易規則完全沿用 v3(不再調整):每日檢視、抱 3 檔、連續 2 天掉出前 8 名才賣、候選看到前 15 名、
流動性 5 日均量 ≥ 2,000 張、不看大盤、不設停損停利;扣成本(買 0.1425%、賣 0.4425%)。
排名來源:
  v3            x{YY}-tw50-h5-cs full_permpos(2026 用 results/tw50_h5_permpos_fullpred.parquet),tw50
  h1不篩·tw50    vf{YY}-tw200-h1-base full,只在 tw50 內排(同股池對照)
  h1不篩·tw200   vf{YY}-tw200-h1-base full,tw200
  h1量增·tw200   vf{YY}-tw200-h1-spike12 full,tw200;每天只有「當天量 ≥ 1.2 × 20 日均量」的股票有分數,
                 持股當天沒量增 = 不在排名內(算掉出前 8 名)
回測區間:Y 年第一個有預測的交易日 ~ Y 年最後一個交易日(2026 到資料最後一天)。
--pool 換 h1 模型的股池(預設 tw200;electronics = 電子 46 檔,模型 vf{YY}-electronics-h1-*),v3 永遠是 tw50 對照。
用法: NCKU_SRC=yf_hist python run_vf_years.py [--pool electronics]            (2021 ~ 2026,還原價)
      NCKU_SRC=official python run_vf_years.py --years 2026 [--pool electronics] (2026 官方口徑)
輸出: out/vf_years/*.xlsx、out/summary_vf_years.json(tw200)/ summary_vf_years_<pool>.json(key = 資料來源|年)
"""
import argparse
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
import run_ncku as R                                   # noqa: E402
from run_ncku import BuyHoldStrategy, assemble_csv, code  # noqa: E402
from run_logic import load_indicators                   # noqa: E402
import run_logic2 as L2                                 # noqa: E402
from data_loader import TICKER_SETS                     # noqa: E402

RES = os.path.join(HERE, "..", "results")
EXP = R.XGB_EXP
OUT = os.path.join(HERE, "out", "vf_years")
os.makedirs(OUT, exist_ok=True)
SUMM = os.path.join(HERE, "out", "summary_vf_years.json")
SRC = os.environ.get("NCKU_SRC", "official")


POOL_NAME = {"tw200": "tw200", "electronics": "電子"}


def preds(year, pool):
    yy = str(year)[2:]
    v3 = (pd.read_parquet(os.path.join(RES, "tw50_h5_permpos_fullpred.parquet"))["p"] if year == 2026 else
          pd.read_parquet(os.path.join(EXP, f"x{yy}-tw50-h5-cs_testpred.parquet"))["p_full_permpos"])
    base = pd.read_parquet(os.path.join(EXP, f"vf{yy}-{pool}-h1-base_testpred.parquet"))["p_full"]
    spike = pd.read_parquet(os.path.join(EXP, f"vf{yy}-{pool}-h1-spike12_testpred.parquet"))["p_full"]
    return {k: p[p.index.get_level_values("date").year == year] for k, p in (("v3", v3), ("base", base), ("spike", spike))}


def ranking(p, uni):
    keep = set(uni)
    w = p.unstack("ticker").sort_index()
    return {d.strftime("%Y%m%d"): [c for c in (code(t) for t in row.dropna().sort_values(ascending=False).index) if c in keep]
            for d, row in w.iterrows()}


def compound_net(curve, curve_net):
    """run_one 的淨值是「未扣成本資產 − 累積手續費」:手續費按未扣成本的部位大小算,週轉很高時會高估虧損(可跌破 -100%)。
    這裡改成逐日複利:當日淨報酬 = 當日毛報酬 − 當日手續費 ÷ 前一日資產,再連乘。"""
    g = pd.Series(curve) / 100 + 1
    fee = (pd.Series(curve) - pd.Series(curve_net)) / 100
    r = (g - fee.diff().fillna(fee.iloc[0])) / g.shift().fillna(1) - 1
    n = (1 + r).cumprod()
    return round(float(n.iloc[-1] - 1) * 100, 2), round(float((n / n.cummax() - 1).min()) * 100, 2)


def v3_rules(name, uni, rk, ind, liq, mkt):
    return L2.Logic2(name, uni, rk, ind, liq, mkt, L2.LIQ["vol2k"], L2.MKT["none"], 8, None, None, topk=3, maxrank=15, out_days=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2021,2022,2023,2024,2025,2026")
    ap.add_argument("--pool", default="tw200")
    a = ap.parse_args()
    pn = POOL_NAME.get(a.pool, a.pool)
    summ_fp = SUMM if a.pool == "tw200" else SUMM.replace(".json", f"_{a.pool}.json")
    summ = json.load(open(summ_fp, encoding="utf-8")) if os.path.exists(summ_fp) else {}
    tw50 = [code(t) for t in TICKER_SETS["tw50"]]
    pcodes = [code(t) for t in TICKER_SETS[a.pool]]
    avail = assemble_csv(list(dict.fromkeys(pcodes + tw50 + ["0050"])))
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write("end_date: '20261231'\nstart_date: '20200101'\n")
    uni50 = [c for c in tw50 if c in avail]
    unip = [c for c in pcodes if c in avail]
    ind, mkt = load_indicators(list(dict.fromkeys(unip + uni50))), L2.load_market()
    liq = L2.load_liquidity(list(ind))
    cal = pd.to_datetime(pd.read_parquet(os.path.join(R.SRC, "2330.parquet"))["date"]).sort_values()
    variants = ["v3"] + (["h1不篩·tw50"] if a.pool == "tw200" else []) + [f"h1不篩·{pn}", f"h1量增·{pn}"]
    for year in [int(y) for y in a.years.split(",")]:
        P = preds(year, a.pool)
        first = min(p.index.get_level_values("date").min() for p in P.values())
        last = cal[cal.dt.year == year].max()
        start, end = max(first, cal[cal.dt.year == year].min()).strftime("%Y%m%d"), last.strftime("%Y%m%d")
        R.START, R.END, L2.START, L2.END = start, end, start, end
        R.OUT = OUT
        rec = {"year": year, "src": SRC, "pool": a.pool, "start": start, "end": end, "n_pool": len(unip)}
        both = list(dict.fromkeys(unip + uni50))
        for bname, st, u in [("0050", BuyHoldStrategy(f"{SRC}_{a.pool}_b0050_{year}", both + ["0050"], ["0050"]), both + ["0050"]),
                             ("tw50等權", BuyHoldStrategy(f"{SRC}_{a.pool}_ew50_{year}", uni50, uni50), uni50),
                             (f"{pn}等權", BuyHoldStrategy(f"{SRC}_{a.pool}_ewp_{year}", unip, unip), unip)]:
            r = R.run(st, u)
            rec[bname] = {"ret": r["total_return_pct"], "mdd": r["max_dd_pct"]}
        src_of = {"v3": (P["v3"], uni50), "h1不篩·tw50": (P["base"], uni50), f"h1不篩·{pn}": (P["base"], unip), f"h1量增·{pn}": (P["spike"], unip)}
        for vname in variants:
            p, u = src_of[vname]
            nm = f"{SRC}_{a.pool}_{vname.replace('·', '_')}_{year}"
            st = v3_rules(nm, u, ranking(p, u), ind, liq, mkt)
            r = L2.run_one(nm, st, u, OUT)
            cmp_ret, cmp_mdd = compound_net(r["curve"], r["curve_net"])
            rec[vname] = {"ret": r["net_return_pct"], "ret_cmp": cmp_ret, "mdd_cmp": cmp_mdd, "gross": r["total_return_pct"], "mdd": r["net_max_dd_pct"], "sharpe": r["net_sharpe"],
                          "trade_days": r["n_trade_days"], "trips": r["n_round_trips"], "win": r["win_rate"], "fees": r["fees_total"],
                          "turnover_x": r["buy_turnover_x"], "exposure": r["avg_exposure_pct"], "avg_trade": r["avg_trade_ret_pct"],
                          "curve": r["curve_net"]}
        summ[f"{SRC}|{year}"] = rec
        json.dump(summ, open(summ_fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{SRC} {year} ({start}~{end}): " + "  ".join(f"{k} {rec[k]['ret']:+.1f}%/複利 {rec[k]['ret_cmp']:+.1f}%" for k in variants)
              + "  | " + "  ".join(f"{b} {rec[b]['ret']:+.1f}%" for b in ("0050", "tw50等權", f"{pn}等權")), flush=True)
    print(f"[SAVED] {os.path.relpath(summ_fp, HERE)}")


if __name__ == "__main__":
    main()
