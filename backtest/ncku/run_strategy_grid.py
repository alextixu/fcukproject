"""買進 / 賣出策略網格(測試標準與最好那版相同:tw50、官方日資料、每天收盤看排名、隔日開盤成交、扣手續費與證交稅、5 日均量 ≥ 2,000 張)。
模型固定,只調策略:持股 K {3,5} × 續抱名次 N {3,5,8,10,15} × 連續掉出天數 M {1,2,3} × 停損停利 {無, 3×ATR+30%} × 大盤濾網 {無, 0050 20 日報酬 > 0}。
先掃全年(1/2 起),再對每個模型前 5 名與 v3 規則跑 7/1 起。
用法: NCKU_SRC=official python run_strategy_grid.py <tag> <fullpred.parquet>:<pcol> [<fullpred.parquet>:<pcol> ...]
輸出: out/strategy_grid_<tag>/*.xlsx、out/summary_strategy_grid_<tag>.json"""
import itertools, json, os, sys, time
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, HERE)
import run_ncku as R
from run_ncku import BuyHoldStrategy, assemble_csv, code
from run_logic import load_indicators
import run_logic2 as L2
from data_loader import TICKER_SETS
from run_tw50_aefeat_v3 import rankings
END = "20260911"; STOPS = {"none": (None, None), "3ATR|30%": (("atr", 3.0), 0.30)}

def main():
    tag, specs = sys.argv[1], [s.split(":") for s in sys.argv[2:]]
    OUT = os.path.join(HERE, "out", f"strategy_grid_{tag}"); os.makedirs(OUT, exist_ok=True); summ = {}
    codes = [code(t) for t in TICKER_SETS["tw50"]]; avail = assemble_csv(codes + ["0050"])
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write(f"end_date: '{END}'\nstart_date: '20251001'\n")
    uni = [c for c in codes if c in avail]; ind, liq, mkt = load_indicators(uni), L2.load_liquidity(uni), L2.load_market()
    print(f"tw50 {len(uni)}/50 檔(源 {os.environ.get('NCKU_SRC','official')})", flush=True)
    def run_one(model, rk, k, n, m, sk, mk, win):
        name = f"{model}|{win}|K{k}|前{n}名|連{m}天|{sk}|{mk}"
        stop, take = STOPS[sk]
        st = L2.Logic2(name, uni, rk, ind, liq, mkt, L2.LIQ["vol2k"], L2.MKT[mk], n, stop, take, topk=k, maxrank=max(15, 3 * k), min_hold=0, out_days=m)
        rr = L2.run_one(name.replace("|", "_").replace("%", "pct"), st, uni, OUT)
        summ[name] = {x: v for x, v in rr.items() if x not in ("curve", "curve_net")} | {"model": model, "window": win, "K": k, "N": n, "M": m, "stops": sk, "mkt": mk}
        return summ[name]
    for win, start in [("全年", "20260102")]:
        R.START, R.END, L2.START, L2.END = start, END, start, END; R.OUT = OUT
        r = R.run(BuyHoldStrategy(f"ew_{win}", uni, uni), uni); summ[f"ew|{win}"] = {"net_return_pct": r["total_return_pct"], "net_max_dd_pct": r["max_dd_pct"], "window": win}
        for fp, pcol in specs:
            model = fp.replace("fullpred_", "").replace(".parquet", "") + ":" + pcol; rk = rankings(fp, pcol, start); t0 = time.time()
            for k, n, m, sk, mk in itertools.product([3, 5], [3, 5, 8, 10, 15], [1, 2, 3], list(STOPS), ["none", "ret20"]):
                run_one(model, rk, k, n, m, sk, mk, win)
            rows = sorted((v for v in summ.values() if v.get("model") == model and v["window"] == win), key=lambda v: -v["net_return_pct"])
            v3 = summ[f"{model}|{win}|K3|前8名|連2天|none|none"]
            print(f"== {model} 全年 ({time.time()-t0:.0f}s):v3 規則 {v3['net_return_pct']:+.1f}% (MDD {v3['net_max_dd_pct']}) | 等權 {r['total_return_pct']:+.1f}%", flush=True)
            for v in rows[:8]:
                print(f"   K{v['K']} 前{v['N']}名 連{v['M']}天 停損{v['stops']} 大盤{v['mkt']}: 淨 {v['net_return_pct']:+.1f}% MDD {v['net_max_dd_pct']} 交易 {v.get('n_round_trips')}", flush=True)
            json.dump(summ, open(os.path.join(HERE, "out", f"summary_strategy_grid_{tag}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 7/1 起:每個模型全年前 5 名 + v3 規則
    win, start = "7月後", "20260630"; R.START, R.END, L2.START, L2.END = start, END, start, END
    r = R.run(BuyHoldStrategy(f"ew_{win}", uni, uni), uni); summ[f"ew|{win}"] = {"net_return_pct": r["total_return_pct"], "net_max_dd_pct": r["max_dd_pct"], "window": win}
    for fp, pcol in specs:
        model = fp.replace("fullpred_", "").replace(".parquet", "") + ":" + pcol; rk = rankings(fp, pcol, start)
        rows = sorted((v for v in summ.values() if v.get("model") == model and v["window"] == "全年"), key=lambda v: -v["net_return_pct"])[:5]
        cands = [(v["K"], v["N"], v["M"], v["stops"], v["mkt"]) for v in rows] + [(3, 8, 2, "none", "none")]
        for k, n, m, sk, mk in dict.fromkeys(cands):
            v = run_one(model, rk, k, n, m, sk, mk, win)
            print(f"   [7月後] {model} K{k} 前{n}名 連{m}天 停損{sk} 大盤{mk}: 淨 {v['net_return_pct']:+.1f}% MDD {v['net_max_dd_pct']} | 等權 {r['total_return_pct']:+.1f}%", flush=True)
    fp = os.path.join(HERE, "out", f"summary_strategy_grid_{tag}.json"); json.dump(summ, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); print(f"[SAVED] {os.path.relpath(fp, HERE)} ({len(summ)})")

if __name__ == "__main__":
    main()
