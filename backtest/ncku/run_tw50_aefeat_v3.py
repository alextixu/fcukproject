"""tw50 h5 三種特徵(原 90 欄 / +AE / 只用 AE)的每日輪動規則回測(每天收盤看排名、抱 3 檔、連續 2 天掉出前 8 名才賣、
隔日開盤成交、5 日均量 ≥ 2,000 張、扣手續費與證交稅;還原價 yf_fw)。輸入 results/fullpred_x25-tw50-h5-cs_aefeat_k{2,3}.parquet。
用法: NCKU_SRC=yf_fw python run_tw50_aefeat_v3.py → out/summary_tw50_aefeat_v3.json"""
import json, os, sys
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, HERE)
import run_ncku as R
from run_ncku import BuyHoldStrategy, assemble_csv, code
from run_logic import load_indicators
import run_logic2 as L2
from data_loader import TICKER_SETS
RES = os.path.join(HERE, "..", "results"); OUT = os.path.join(HERE, "out", "tw50_aefeat_v3"); os.makedirs(OUT, exist_ok=True)
SUMM = os.path.join(HERE, "out", "summary_tw50_aefeat_v3.json"); END = "20260911"

def rankings(fp, pcol, start):
    p = pd.read_parquet(os.path.join(RES, fp))[pcol].unstack("ticker").sort_index()
    p = p[p.index >= pd.Timestamp(start)]
    return {d.strftime("%Y%m%d"): [code(t) for t in row.dropna().sort_values(ascending=False).index] for d, row in p.iterrows()}

def main():
    summ = {}
    codes = [code(t) for t in TICKER_SETS["tw50"]]; avail = assemble_csv(codes + ["0050"])
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write(f"end_date: '{END}'\nstart_date: '20251001'\n")
    uni = [c for c in codes if c in avail]
    ind, liq, mkt = load_indicators(uni), L2.load_liquidity(uni), L2.load_market()
    for win, start in [("全年", "20260102"), ("7月後", "20260630")]:
        R.START, R.END, L2.START, L2.END = start, END, start, END; R.OUT = OUT
        r = R.run(BuyHoldStrategy(f"tw50_ew_{win}", uni, uni), uni)
        summ[f"ew|{win}"] = {"net_return_pct": r["total_return_pct"], "net_max_dd_pct": r["max_dd_pct"]}
        for k in (2, 3):
            fp = f"fullpred_x25-tw50-h5-cs_aefeat_k{k}.parquet"
            for pcol in pd.read_parquet(os.path.join(RES, fp)).columns:
                name = f"k{k}|{pcol}|{win}"
                st = L2.Logic2(name, uni, rankings(fp, pcol, start), ind, liq, mkt, L2.LIQ["vol2k"], L2.MKT["none"], 8, None, None,
                               topk=3, maxrank=15, min_hold=0, out_days=2)
                rr = L2.run_one(name.replace("|", "_"), st, uni, OUT)
                summ[name] = {x: v for x, v in rr.items() if x not in ("curve", "curve_net")}
                print(f"  {name}: 淨 {rr['net_return_pct']:+.1f}% MDD {rr['net_max_dd_pct']} 交易 {rr.get('n_round_trips')} | 等權 {r['total_return_pct']:+.1f}%", flush=True)
    json.dump(summ, open(SUMM, "w", encoding="utf-8"), ensure_ascii=False, indent=1); print(f"[SAVED] {os.path.relpath(SUMM, HERE)}")

if __name__ == "__main__":
    main()
