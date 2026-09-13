"""不設停損停利、追求最大報酬:每日檢視網格(tw50,流動性 2,000 張,官方資料,扣成本)。

維度:持股 K {3,4,5,6,8} × 續抱門檻 exit_rank(≥K){K, 8, 10, 12, 15} × 最短持有 {0,5,10,15,20} 日 × 大盤濾網 {不看, 0050 20 日報酬>0}
排名:全年(1/2~9/11)扣成本報酬;前 10 名再跑 7/1~9/11 看近期表現。
用法: NCKU_SRC=official python run_maxprofit.py
輸出: out/maxprofit/*.xlsx、out/summary_maxprofit.json
"""
import itertools
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

OUT = os.path.join(HERE, "out", "maxprofit")
os.makedirs(OUT, exist_ok=True)
SUMM = os.path.join(HERE, "out", "summary_maxprofit.json")
END = "20260911"


def main():
    summ = json.load(open(SUMM, encoding="utf-8")) if os.path.exists(SUMM) else {}
    tw50 = [code(t) for t in TICKER_SETS["tw50"]]
    avail = assemble_csv(tw50 + ["0050"])
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write(f"end_date: '{END}'\nstart_date: '20251001'\n")
    uni = [c for c in tw50 if c in avail]
    ind, liq, mkt = load_indicators(uni), L2.load_liquidity(uni), L2.load_market()
    rks = {s: ranking(pd.Timestamp(s), 1) for s in ("20260102", "20260630")}

    def run(win, k, er, mh, mk):
        key = f"{win}|K{k}|前{er}名|最短{mh}日|{mk}"
        if key in summ:
            return summ[key]
        start = "20260102" if win == "全年" else "20260630"
        R.START, R.END, L2.START, L2.END = start, END, start, END
        st = L2.Logic2(key, uni, rks[start], ind, liq, mkt, L2.LIQ["vol2k"], L2.MKT[mk], er, None, None,
                       topk=k, maxrank=max(15, 2 * k), min_hold=mh)
        r = L2.run_one(key.replace("|", "_"), st, uni, OUT)
        summ[key] = {x: v for x, v in r.items() if x != "curve"} | {"window": win, "K": k, "exit_rank": er, "min_hold": mh, "mkt": mk}
        json.dump(summ, open(SUMM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return summ[key]

    grid = [(k, er, mh, mk) for k, er, mh, mk in itertools.product([3, 4, 5, 6, 8], [3, 4, 5, 6, 8, 10, 12, 15], [0, 5, 10, 15, 20], ["none", "ret20"])
            if er >= k and (er == k or er in (8, 10, 12, 15))]
    print(f"全年網格 {len(grid)} 組", flush=True)
    for i, g in enumerate(grid, 1):
        r = run("全年", *g)
        if i % 25 == 0:
            print(f"  {i}/{len(grid)}", flush=True)
    full = sorted([r for r in summ.values() if r["window"] == "全年"], key=lambda r: -r["net_return_pct"])
    print("\n[全年前 15]")
    for r in full[:15]:
        j = run("7月後", r["K"], r["exit_rank"], r["min_hold"], r["mkt"])
        print(f"  K{r['K']} 前{r['exit_rank']:>2}名 最短{r['min_hold']:>2}日 大盤{r['mkt']:5s} 扣成本 {r['net_return_pct']:+8.2f}%  淨MDD {r['net_max_dd_pct']:6.2f}%  "
              f"淨Sharpe {r['net_sharpe']:5.2f}  下單 {r['n_trade_days']:3d} 天  週轉 {r['buy_turnover_x']:4.1f}x  | 7月後 {j['net_return_pct']:+6.2f}%  MDD {j['net_max_dd_pct']:6.2f}%", flush=True)
    print(f"[SAVED] {os.path.relpath(SUMM, HERE)} ({len(summ)} 組)")


if __name__ == "__main__":
    main()
