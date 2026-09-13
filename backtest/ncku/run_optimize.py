"""勝出股票池的交易邏輯優化(NCKU 框架引擎,扣成本口徑排名)。

兩階段座標搜尋(避免上千組全網格):
  A 結構:檢視頻率 {每日, 每 3 日, 每 5 日} × 持股數 K {5, 8, 10} × 續抱門檻 {不續抱, 2K, 3K}
          (流動性 5 日均量 ≥ 2,000 張、大盤 0050 20 日報酬 > 0、3×ATR 停損 + 30% 停利 固定)
  B 過濾與出場:取 A 的最佳結構,掃 流動性 {1,000 張, 2,000 張, 5,000 張, 成交額 3 億} × 大盤 {不看, MA20, MA60, 20 日報酬}
          × 停損停利 {3×ATR+30%, 2×ATR+20%, 移動 12%+30%}
排名:扣成本後 Sharpe(同時列出扣成本後報酬與 MDD);四個機制(流動性、大盤、汰弱留強、停損停利)都必須開著才列入最終候選。

用法: NCKU_SRC=yf python run_optimize.py --pool tw50 --tag x26-tw50-h5-cs --pcol p_full_permpos
輸出: out/opt_<pool>_<src>/*.xlsx、out/summary_opt_<pool>_<src>.json
"""
import argparse
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
import run_ncku as R                                  # noqa: E402
from run_ncku import assemble_csv, code               # noqa: E402
from run_logic import load_indicators                  # noqa: E402
import run_logic2 as L2                                # noqa: E402
from run_pool_scan import ranking_from                 # noqa: E402
from data_loader import TICKER_SETS                    # noqa: E402

SRC_NAME = os.environ.get("NCKU_SRC", "official")
L2.LIQ.update({"vol1k": lambda r: r["vol5_lots"] >= 1000, "vol5k": lambda r: r["vol5_lots"] >= 5000})
STOPS = {"3ATR|30%": (("atr", 3.0), 0.30), "2ATR|20%": (("atr", 2.0), 0.20), "trail12%|30%": (("trail", 0.12), 0.30)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    ap.add_argument("--key", help="TICKER_SETS key(預設同 --pool)")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--pcol", default="p_full_permpos")
    ap.add_argument("--stage", default="AB")
    a = ap.parse_args()
    key = a.key or a.pool
    out = os.path.join(HERE, "out", f"opt_{a.pool}_{SRC_NAME}")
    os.makedirs(out, exist_ok=True)
    summ_fp = os.path.join(HERE, "out", f"summary_opt_{a.pool}_{SRC_NAME}.json")
    summ = json.load(open(summ_fp, encoding="utf-8")) if os.path.exists(summ_fp) else {}
    fp = os.path.join(R.XGB_EXP, f"{a.tag}_testpred.parquet")
    codes = [code(t) for t in TICKER_SETS[key]]
    avail = assemble_csv(codes + ["0050"])
    uni = [c for c in codes if c in avail]
    ind, liq, mkt = load_indicators(uni), L2.load_liquidity(uni), L2.load_market()
    rks = {}

    def run(freq, k, hys_mult, liq_k, mkt_k, stop_k):
        name = f"f{freq}|K{k}|hys{hys_mult}|{liq_k}|{mkt_k}|{stop_k}"
        if name in summ:
            return summ[name]
        if freq not in rks:
            rks[freq] = ranking_from(fp, a.pcol, freq)
        stop, take = STOPS[stop_k]
        exit_rank = None if hys_mult == 0 else hys_mult * k
        st = L2.Logic2(name, uni, rks[freq], ind, liq, mkt, L2.LIQ[liq_k], L2.MKT[mkt_k], exit_rank, stop, take,
                       topk=k, maxrank=max(30, 3 * k))
        r = L2.run_one(name.replace("|", "_").replace("%", "pct"), st, uni, out)
        r.update({"freq": freq, "K": k, "hys_mult": hys_mult, "liq": liq_k, "mkt": mkt_k, "stops": stop_k})
        summ[name] = r
        json.dump(summ, open(summ_fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{name:40s} 框架 {r['total_return_pct']:+8.2f}%  扣成本 {r['net_return_pct']:+8.2f}%  淨MDD {r['net_max_dd_pct']:6.2f}%  "
              f"淨Sharpe {r['net_sharpe']:5.2f}  持股比 {r['avg_exposure_pct']:5.1f}%  週轉 {r['buy_turnover_x']:5.1f}x  勝率 {r['win_rate']}", flush=True)
        return r

    if "A" in a.stage:
        print("===== A 結構 =====", flush=True)
        for freq, k, hm in itertools.product([1, 3, 5], [5, 8, 10], [0, 2, 3]):
            run(freq, k, hm, "vol2k", "ret20", "3ATR|30%")
    a_rows = {n: r for n, r in summ.items() if r["liq"] == "vol2k" and r["mkt"] == "ret20" and r["stops"] == "3ATR|30%" and r["hys_mult"] > 0}
    best = max(a_rows.values(), key=lambda r: r["net_sharpe"])
    print(f"[A 最佳結構] 每 {best['freq']} 日 / K={best['K']} / 續抱前 {best['hys_mult'] * best['K']} 名 → 淨Sharpe {best['net_sharpe']} 扣成本 {best['net_return_pct']}%", flush=True)
    if "B" in a.stage:
        print("===== B 過濾與出場 =====", flush=True)
        for lk, mk, sk in itertools.product(["vol1k", "vol2k", "vol5k", "to3e"], ["none", "ma20", "ma60", "ret20"], list(STOPS)):
            run(best["freq"], best["K"], best["hys_mult"], lk, mk, sk)
    fin = [r for r in summ.values() if r["mkt"] != "none" and r["hys_mult"] > 0]
    top = sorted(fin, key=lambda r: -r["net_sharpe"])[:5]
    print("\n[四機制都開,扣成本 Sharpe 前 5]")
    for r in top:
        print(f"  每{r['freq']}日 K{r['K']} 續抱{r['hys_mult'] * r['K']} {r['liq']} {r['mkt']} {r['stops']}: 扣成本 {r['net_return_pct']:+.2f}%  淨MDD {r['net_max_dd_pct']}%  淨Sharpe {r['net_sharpe']}")
    print(f"[SAVED] {os.path.relpath(summ_fp, HERE)} ({len(summ)} 組)")


if __name__ == "__main__":
    main()
