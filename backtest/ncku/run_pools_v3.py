"""v3 系統(每日檢視、連續 M 天掉出前 N 名才賣、不看大盤、不設停損停利、流動性 2,000 張)換股票池比較。

池子:tw50(現行)、tw100、electronics(tw100 裡的 46 檔電子股)、elec_liq100(電子股流動性前 100)
網格:持股 K {3, 5} × 續抱名次 N {8, 10, 15, 20} × 連續天數 M {2, 3};全年(1/2 起)與 7/1 起兩段,官方資料,扣成本。
用法: NCKU_SRC=official python run_pools_v3.py [--only tw100,electronics]
輸出: out/pools_v3/*.xlsx、out/summary_pools_v3.json
"""
import argparse
import itertools
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
OUT = os.path.join(HERE, "out", "pools_v3")
os.makedirs(OUT, exist_ok=True)
SUMM = os.path.join(HERE, "out", "summary_pools_v3.json")
END = "20260911"
POOLS = {
    "tw50": ("tw50", "tw50_h5_permpos_fullpred.parquet"),
    "tw100": ("tw100", "fullpred_x26-tw100-h5-cs_full_permpos.parquet"),
    "electronics": ("electronics", "fullpred_x26-electronics-h5-cs_full_permpos.parquet"),
    "elec_liq100": ("elec_liq100", "fullpred_x26-elecliq100-h5-cs_full_permpos.parquet"),
    "tw50_elec": ("tw50_elec", "fullpred_x26-tw50elec-h5-cs_full_permpos.parquet"),
}


def rankings(fp, start):
    p = pd.read_parquet(os.path.join(RES, fp))["p"].unstack("ticker").sort_index()
    p = p[p.index >= pd.Timestamp(start)]
    return {d.strftime("%Y%m%d"): [code(t) for t in row.dropna().sort_values(ascending=False).index] for d, row in p.iterrows()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    summ = json.load(open(SUMM, encoding="utf-8")) if os.path.exists(SUMM) else {}
    for pname, (key, fp) in POOLS.items():
        if a.only and pname not in a.only.split(","):
            continue
        codes = [code(t) for t in TICKER_SETS[key]]
        avail = assemble_csv(codes + ["0050"])
        with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
            f.write(f"end_date: '{END}'\nstart_date: '20251001'\n")
        uni = [c for c in codes if c in avail]
        ind, liq, mkt = load_indicators(uni), L2.load_liquidity(uni), L2.load_market()
        print(f"\n######## {pname}:{len(uni)}/{len(codes)} 檔有官方資料 ########", flush=True)
        for win, start in [("全年", "20260102"), ("7月後", "20260630")]:
            R.START, R.END, L2.START, L2.END = start, END, start, END
            R.OUT = OUT
            r = R.run(BuyHoldStrategy(f"{pname}_ew_{win}", uni, uni), uni)
            summ[f"{pname}|{win}|ew"] = {"pool": pname, "window": win, "kind": "ew", "net_return_pct": r["total_return_pct"], "net_max_dd_pct": r["max_dd_pct"], "n_stocks": len(uni)}
            rk = rankings(fp, start)
            for k, n, m in itertools.product([3, 5], [8, 10, 15, 20], [2, 3]):
                name = f"{pname}|{win}|K{k}|前{n}名|連{m}天"
                st = L2.Logic2(name, uni, rk, ind, liq, mkt, L2.LIQ["vol2k"], L2.MKT["none"], n, None, None,
                               topk=k, maxrank=max(15, 3 * k), min_hold=0, out_days=m)
                rr = L2.run_one(name.replace("|", "_"), st, uni, OUT)
                summ[name] = {x: v for x, v in rr.items() if x not in ("curve", "curve_net")} | {"pool": pname, "window": win, "kind": "sys", "K": k, "N": n, "M": m, "n_stocks": len(uni)}
            json.dump(summ, open(SUMM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            best = max((v for v in summ.values() if v["pool"] == pname and v["window"] == win and v["kind"] == "sys"), key=lambda v: v["net_return_pct"])
            v3 = summ[f"{pname}|{win}|K3|前8名|連2天"]
            print(f"  {win}: 等權 {r['total_return_pct']:+.1f}% | v3 規則 {v3['net_return_pct']:+.1f}% (MDD {v3['net_max_dd_pct']}) | 池內最佳 K{best['K']} 前{best['N']} 連{best['M']} {best['net_return_pct']:+.1f}% (MDD {best['net_max_dd_pct']})", flush=True)
    print(f"[SAVED] {os.path.relpath(SUMM, HERE)} ({len(summ)})")


if __name__ == "__main__":
    main()
