"""v3 規則 × 量增篩選訓練的模型,逐年回測 2021 ~ 2026(walk-forward)。四個版本:
  v3                原模型(x{YY}-tw50-h5-cs full_permpos),原規則
  量增訓練           模型只用「當天量 ≥ 1.2 × 20 日均量」的樣本訓練,打分全部股票
                    (results/fullpred_vf{YY}-tw50-h5-cs-spike12_full_permpos.parquet),規則不變
  量增訓練+只買量增   同上,但買新倉時只在「當天量增」的股票裡挑(持股續抱與否仍看完整排名)
  原模型+只買量增     原模型,買新倉只挑當天量增的股票(隔離交易端篩量的效果)
規則同 v3:每日檢視、抱 3 檔、連 2 天掉出前 8 名才賣、候選前 15、流動性 2,000 張、不看大盤、不設停損停利;扣成本,逐日複利。
用法: NCKU_SRC=yf_hist python run_vf_v3.py ; NCKU_SRC=official python run_vf_v3.py --years 2026
輸出: out/vf_v3/*.xlsx、out/summary_vf_v3.json(key = 資料來源|年)
"""
import argparse
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
import run_ncku as R                                      # noqa: E402
from run_ncku import BuyHoldStrategy, assemble_csv, code  # noqa: E402
from run_logic import load_indicators                     # noqa: E402
import run_logic2 as L2                                   # noqa: E402
from run_vf_years import ranking, compound_net            # noqa: E402
from data_loader import TICKER_SETS                       # noqa: E402

RES = os.path.join(HERE, "..", "results")
EXP = R.XGB_EXP
OUT = os.path.join(HERE, "out", "vf_v3")
os.makedirs(OUT, exist_ok=True)
SUMM = os.path.join(HERE, "out", "summary_vf_v3.json")
SRC = os.environ.get("NCKU_SRC", "official")


def preds(year):
    yy = str(year)[2:]
    v3 = (pd.read_parquet(os.path.join(RES, "tw50_h5_permpos_fullpred.parquet"))["p"] if year == 2026 else
          pd.read_parquet(os.path.join(EXP, f"x{yy}-tw50-h5-cs_testpred.parquet"))["p_full_permpos"])
    sp = pd.read_parquet(os.path.join(RES, f"fullpred_vf{yy}-tw50-h5-cs-spike12_full_permpos.parquet"))["p"]
    return {k: p[p.index.get_level_values("date").year == year] for k, p in (("v3", v3), ("spike", sp))}


def load_liq_spike(codes):
    """run_logic2.load_liquidity 再加一欄 spike = 當天量 / 20 日均量(t 日可得)。"""
    liq = L2.load_liquidity(codes)
    for c, x in liq.items():
        v = pd.read_parquet(os.path.join(R.SRC, f"{c}.parquet")).sort_values("date")
        v["d"] = pd.to_datetime(v["date"]).dt.strftime("%Y%m%d")
        cap = v["capacity"].astype(float)
        x["spike"] = (cap / cap.rolling(20, min_periods=10).mean()).set_axis(v["d"]).reindex(x.index)
    return liq


def liq_spike(r):
    return r["vol5_lots"] >= 2000 and r["spike"] >= 1.2


VARIANTS = [("v3", "v3", L2.LIQ["vol2k"]), ("量增訓練", "spike", L2.LIQ["vol2k"]),
            ("量增訓練+只買量增", "spike", liq_spike), ("原模型+只買量增", "v3", liq_spike)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2021,2022,2023,2024,2025,2026")
    a = ap.parse_args()
    summ = json.load(open(SUMM, encoding="utf-8")) if os.path.exists(SUMM) else {}
    tw50 = [code(t) for t in TICKER_SETS["tw50"]]
    avail = assemble_csv(tw50 + ["0050"])
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write("end_date: '20261231'\nstart_date: '20200101'\n")
    uni = [c for c in tw50 if c in avail]
    ind, liq, mkt = load_indicators(uni), load_liq_spike(uni), L2.load_market()
    cal = pd.to_datetime(pd.read_parquet(os.path.join(R.SRC, "2330.parquet"))["date"]).sort_values()
    for year in [int(y) for y in a.years.split(",")]:
        P = preds(year)
        first = min(p.index.get_level_values("date").min() for p in P.values())
        start = max(first, cal[cal.dt.year == year].min()).strftime("%Y%m%d")
        end = cal[cal.dt.year == year].max().strftime("%Y%m%d")
        R.START, R.END, L2.START, L2.END = start, end, start, end
        R.OUT = OUT
        rec = {"year": year, "src": SRC, "start": start, "end": end}
        for bname, st, u in [("0050", BuyHoldStrategy(f"{SRC}_b0050_{year}", uni + ["0050"], ["0050"]), uni + ["0050"]),
                             ("tw50等權", BuyHoldStrategy(f"{SRC}_ew50_{year}", uni, uni), uni)]:
            r = R.run(st, u)
            rec[bname] = {"ret": r["total_return_pct"], "mdd": r["max_dd_pct"]}
        for vname, pk, lf in VARIANTS:
            nm = f"{SRC}_{vname}_{year}"
            st = L2.Logic2(nm, uni, ranking(P[pk], uni), ind, liq, mkt, lf, L2.MKT["none"], 8, None, None, topk=3, maxrank=15, out_days=2)
            r = L2.run_one(nm, st, uni, OUT)
            cr, cm = compound_net(r["curve"], r["curve_net"])
            rec[vname] = {"ret_cmp": cr, "mdd_cmp": cm, "gross": r["total_return_pct"], "sharpe": r["net_sharpe"],
                          "trade_days": r["n_trade_days"], "trips": r["n_round_trips"], "win": r["win_rate"],
                          "turnover_x": r["buy_turnover_x"], "exposure": r["avg_exposure_pct"], "n_liq": r["n_liq_filtered"],
                          "curve": r["curve_net"]}
        summ[f"{SRC}|{year}"] = rec
        json.dump(summ, open(SUMM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{SRC} {year}: " + "  ".join(f"{v} {rec[v]['ret_cmp']:+.1f}% (MDD {rec[v]['mdd_cmp']:.0f}%, {rec[v]['trade_days']}天)" for v, _, _ in VARIANTS)
              + f" | 0050 {rec['0050']['ret']:+.1f}%  等權 {rec['tw50等權']['ret']:+.1f}%", flush=True)
    print(f"[SAVED] {os.path.relpath(SUMM, HERE)}")


if __name__ == "__main__":
    main()
