"""把 v3 交易規則(每日檢視、抱 K 檔、連續 M 天掉出前 N 名才賣、不看大盤、不設停損停利、流動性 2,000 張)
套到 tw500 h20 系統(x25-tw500-h20-cs / full_permpos,訓練 ≤2023、2024 早停)上,與 tw50 h5 版同資料源對照。
資料源:NCKU_SRC=yf_fw(還原價轉框架格式,815 檔;官方資料只有 251 檔,蓋不住 tw500)。
用法: NCKU_SRC=yf_fw python run_tw500_v3.py [--only tw500]
輸出: out/tw500_v3/*.xlsx、out/summary_tw500_v3.json
"""
import argparse, itertools, json, os, sys
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, HERE)
import run_ncku as R
from run_ncku import BuyHoldStrategy, assemble_csv, code
from run_logic import load_indicators
import run_logic2 as L2
from data_loader import TICKER_SETS
from run_pools_v3 import rankings
RES = os.path.join(HERE, "..", "results"); OUT = os.path.join(HERE, "out", "tw500_v3"); os.makedirs(OUT, exist_ok=True)
SUMM = os.path.join(HERE, "out", "summary_tw500_v3.json"); END = "20260911"
POOLS = {"tw500": ("tw500", "fullpred_x25-tw500-h20-cs_full_permpos.parquet"),
         "tw50": ("tw50", "tw50_h5_permpos_fullpred.parquet")}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); a = ap.parse_args()
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
        print(f"\n######## {pname}:{len(uni)}/{len(codes)} 檔有資料(源 {os.environ.get('NCKU_SRC','official')}) ########", flush=True)
        for win, start in [("全年", "20260102"), ("7月後", "20260630")]:
            R.START, R.END, L2.START, L2.END = start, END, start, END; R.OUT = OUT
            r = R.run(BuyHoldStrategy(f"{pname}_ew_{win}", uni, uni), uni)
            summ[f"{pname}|{win}|ew"] = {"pool": pname, "window": win, "kind": "ew", "net_return_pct": r["total_return_pct"], "net_max_dd_pct": r["max_dd_pct"], "n_stocks": len(uni)}
            rk = rankings(fp, start)
            for k, n, m in itertools.product([3, 5], [8, 10, 15, 20], [2, 3]):
                name = f"{pname}|{win}|K{k}|前{n}名|連{m}天"
                st = L2.Logic2(name, uni, rk, ind, liq, mkt, L2.LIQ["vol2k"], L2.MKT["none"], n, None, None,
                               topk=k, maxrank=max(15, 3 * k), min_hold=0, out_days=m)
                rr = L2.run_one(name.replace("|", "_"), st, uni, OUT)
                summ[name] = {x: v for x, v in rr.items() if x not in ("curve", "curve_net")} | {"pool": pname, "window": win, "kind": "sys", "K": k, "N": n, "M": m, "n_stocks": len(uni)}
                print(f"  {name}: 淨 {rr['net_return_pct']:+.1f}% MDD {rr['net_max_dd_pct']} 交易 {rr.get('n_round_trips')}", flush=True)
            json.dump(summ, open(SUMM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            v3 = summ[f"{pname}|{win}|K3|前8名|連2天"]
            print(f"  == {pname} {win}: 等權 {r['total_return_pct']:+.1f}% | v3 規則 {v3['net_return_pct']:+.1f}% (MDD {v3['net_max_dd_pct']})", flush=True)
    print(f"[SAVED] {os.path.relpath(SUMM, HERE)} ({len(summ)})")

if __name__ == "__main__":
    main()
