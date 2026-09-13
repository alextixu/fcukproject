"""最終系統只跑一段期間(預設 2026-07-01 ~ 2026-09-11),NCKU 框架 + 證交所官方資料。

全新 100 萬起跑。框架第一天只選股不交易,所以框架從「第一個訊號日」(預設 06-30)開跑,當天全現金,
07-01 開盤才第一次買進;之後每 5 個交易日檢視一次,t+1 開盤下單。基準也是 06-30 選、07-01 開盤買。
模型機率用 results/tw50_h5_permpos_fullpred.parquet(與原 testpred 完全一致,並補到 09-10)。
同期間對照:0050 買進持有、tw50 等權買進持有、只有模型(每 5 日前 5 名全換)。
用法: python run_window.py [--start 20260630 --end 20260911]    (--start = 第一個訊號日)
輸出: out/window_<start>_<end>/*.xlsx、out/summary_window_<start>_<end>.json
"""
import argparse
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
import run_ncku as R                                        # noqa: E402
from run_ncku import BuyHoldStrategy, assemble_csv, code    # noqa: E402
from run_logic import load_indicators                        # noqa: E402
import run_logic2 as L2                                      # noqa: E402
from data_loader import TICKER_SETS                          # noqa: E402

PRED = os.path.join(HERE, "..", "results", "tw50_h5_permpos_fullpred.parquet")


def ranking(start, freq=5):
    df = pd.read_parquet(PRED)
    dates = sorted(df.index.get_level_values("date").unique())
    first = min(d for d in dates if d >= pd.Timestamp(start))     # 框架第一天 = 第一個訊號日
    sched = [d for d in dates if d >= first][::freq]
    return {d.strftime("%Y%m%d"): [code(t) for t in df.xs(d, level="date")["p"].sort_values(ascending=False).index] for d in sched}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20260630")
    ap.add_argument("--end", default="20260911")
    ap.add_argument("--freq", type=int, default=5, help="檢視頻率(交易日);1 = 每日")
    a = ap.parse_args()
    R.START, R.END = a.start, a.end
    L2.START, L2.END = a.start, a.end
    tag = f"{a.start}_{a.end}" + ("" if a.freq == 5 else f"_f{a.freq}")
    out = os.path.join(HERE, "out", f"window_{tag}")
    os.makedirs(out, exist_ok=True)
    R.OUT = out
    tw50 = [code(t) for t in TICKER_SETS["tw50"]]
    avail = assemble_csv(tw50 + ["0050"])
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write(f"end_date: '{a.end}'\nstart_date: '20251001'\n")
    uni = [c for c in tw50 if c in avail]
    ind, liq, mkt = load_indicators(uni), L2.load_liquidity(uni), L2.load_market()
    rk = ranking(pd.Timestamp(a.start), a.freq)
    print(f"[訊號日] 每 {a.freq} 日,{len(rk)} 次", flush=True)
    summ = {}
    for name, strat, u in [("bench_0050", BuyHoldStrategy("bench_0050", uni + ["0050"], ["0050"]), uni + ["0050"]),
                           ("bench_tw50_ew", BuyHoldStrategy("bench_tw50_ew", uni, uni), uni)]:
        r = R.run(strat, u)
        summ[name] = r
        print(f"{name:16s} 總收益 {r['total_return_pct']:+7.2f}%  MDD {r['max_dd_pct']:6.2f}%", flush=True)
    for name, args in [("model_only", dict(liq_f=L2.LIQ["none"], mkt_f=L2.MKT["none"], exit_rank=None, stop=None, take=None, maxrank=5)),
                       ("model_stop", dict(liq_f=L2.LIQ["none"], mkt_f=L2.MKT["none"], exit_rank=None, stop=("atr", 3.0), take=0.30, maxrank=5)),
                       ("system_final", dict(liq_f=L2.LIQ["vol2k"], mkt_f=L2.MKT["ret20"], exit_rank=10, stop=("atr", 3.0), take=0.30, maxrank=15)),
                       ("system_nostop", dict(liq_f=L2.LIQ["vol2k"], mkt_f=L2.MKT["ret20"], exit_rank=10, stop=None, take=None, maxrank=15)),
                       ("hys_only", dict(liq_f=L2.LIQ["vol2k"], mkt_f=L2.MKT["none"], exit_rank=10, stop=None, take=None, maxrank=15))]:
        st = L2.Logic2(name, uni, rk, ind, liq, mkt, args["liq_f"], args["mkt_f"], args["exit_rank"], args["stop"], args["take"], topk=5, maxrank=args["maxrank"])
        r = L2.run_one(name, st, uni, out)
        summ[name] = r
        print(f"{name:16s} 框架 {r['total_return_pct']:+7.2f}%  扣成本 {r['net_return_pct']:+7.2f}%  淨MDD {r['net_max_dd_pct']:6.2f}%  "
              f"持股比 {r['avg_exposure_pct']}%  來回 {r['n_round_trips']}  勝率 {r['win_rate']}  大盤擋 {r['n_mkt_blocked']}  續抱 {r['n_kept']}  "
              f"停損 {r['n_stop_exits']}  停利 {r['n_tp_exits']}", flush=True)
    json.dump(summ, open(os.path.join(HERE, "out", f"summary_window_{tag}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(f"[SAVED] out/summary_window_{tag}.json")


if __name__ == "__main__":
    main()
