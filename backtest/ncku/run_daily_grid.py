"""每日檢視、不一定動作:續抱門檻 × 最短持有天數 網格(tw50、流動性 2,000 張、0050 20 日報酬 > 0 才買)。

每天收盤後重新排名;持股若(還在前 exit_rank 名)或(持有未滿 min_hold 個交易日)就不動,
只有被判出場的名額才在隔日開盤換成排名前段的新股。停損停利:預設不設,另跑一組 3×ATR + 30% 對照。
期間:全年(1/2 起)與 7/1 起兩段,都到 9/11,官方資料,扣成本。
用法: NCKU_SRC=official python run_daily_grid.py
輸出: out/daily_grid/*.xlsx、out/summary_daily_grid.json
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
from run_ncku import BuyHoldStrategy, assemble_csv, code  # noqa: E402
from run_logic import load_indicators                   # noqa: E402
import run_logic2 as L2                                 # noqa: E402
from run_window import ranking                          # noqa: E402
from data_loader import TICKER_SETS                     # noqa: E402

OUT = os.path.join(HERE, "out", "daily_grid")
os.makedirs(OUT, exist_ok=True)
SUMM = os.path.join(HERE, "out", "summary_daily_grid.json")
END = "20260911"


def main():
    summ = {}
    tw50 = [code(t) for t in TICKER_SETS["tw50"]]
    avail = assemble_csv(tw50 + ["0050"])
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write(f"end_date: '{END}'\nstart_date: '20251001'\n")
    uni = [c for c in tw50 if c in avail]
    ind, liq, mkt = load_indicators(uni), L2.load_liquidity(uni), L2.load_market()
    for wname, start in [("全年", "20260102"), ("7月後", "20260630")]:
        R.START, R.END, L2.START, L2.END = start, END, start, END
        rk = ranking(pd.Timestamp(start), 1)
        for bname, strat, u in [("tw50等權", BuyHoldStrategy("ew", uni, uni), uni), ("0050", BuyHoldStrategy("b0050", uni + ["0050"], ["0050"]), uni + ["0050"])]:
            R.OUT = OUT
            r = R.run(strat, u)
            summ[f"{wname}|{bname}"] = {"window": wname, "kind": bname, "net_return_pct": r["total_return_pct"], "net_max_dd_pct": r["max_dd_pct"]}
        combos = [(er, mh, "none") for er, mh in itertools.product([10, 15, 20, 50], [0, 3, 5, 10])] + [(10, 5, "3ATR"), (15, 5, "3ATR")]
        for er, mh, stp in combos:
            name = f"{wname}|前{er}名續抱|最短{mh}日|{stp}"
            st = L2.Logic2(name, uni, rk, ind, liq, mkt, L2.LIQ["vol2k"], L2.MKT["ret20"], er if er < 50 else 50,
                           ("atr", 3.0) if stp == "3ATR" else None, 0.30 if stp == "3ATR" else None, topk=5, maxrank=15, min_hold=mh)
            r = L2.run_one(f"{'full' if wname == '全年' else 'jul'}_er{er}_mh{mh}_{stp}", st, uni, OUT)
            summ[name] = {k: v for k, v in r.items() if k != "curve"} | {"window": wname, "exit_rank": er, "min_hold": mh, "stops": stp}
            print(f"{name:28s} 扣成本 {r['net_return_pct']:+8.2f}%  淨MDD {r['net_max_dd_pct']:6.2f}%  淨Sharpe {r['net_sharpe']:5.2f}  "
                  f"下單天數 {r['n_trade_days']:3d}/{r['n_days']}  週轉 {r['buy_turnover_x']:5.1f}x  來回 {r['n_round_trips']:3d}  持股比 {r['avg_exposure_pct']}%", flush=True)
        json.dump(summ, open(SUMM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[SAVED] {os.path.relpath(SUMM, HERE)}")


if __name__ == "__main__":
    main()
