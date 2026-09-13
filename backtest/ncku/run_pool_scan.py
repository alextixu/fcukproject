"""股票池階梯篩選:同一套 XGB(h=5 cs,各池各自在 2016~2024 重訓)在不同股票池的 2026 表現,NCKU 框架引擎。

每個 (池, 特徵集, 檢視頻率 5 日 / 每日) 跑:
  ew     同池等權買進持有(基準)
  model  只有模型:每 5 個交易日取機率前 5 名等權,t+1 開盤全換(= tw50 版的 xgb_tw50_h5_permpos)
  v2     最終系統 v2:5 日均量 ≥ 2,000 張 + 0050 20 日報酬 > 0 才買 + 前 10 名續抱 + 3×ATR 停損 + 30% 停利
         (大池子前幾名常是冷門股,候選往下找到第 30 名湊滿 5 檔)
資料源由 NCKU_SRC 決定(yf = cache_2026 還原價篩選;official = 證交所官方,正式口徑)。

用法: NCKU_SRC=yf python run_pool_scan.py [--only tw50,tw200]
輸出: out/pool_scan_<src>/*.xlsx、out/summary_pool_scan_<src>.json
"""
import argparse
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
import run_ncku as R                                         # noqa: E402
from run_ncku import BuyHoldStrategy, assemble_csv, code     # noqa: E402
from run_logic import load_indicators                         # noqa: E402
import run_logic2 as L2                                       # noqa: E402
from data_loader import TICKER_SETS                           # noqa: E402

SRC_NAME = os.environ.get("NCKU_SRC", "official")
OUT = os.path.join(HERE, "out", f"pool_scan_{SRC_NAME}")
os.makedirs(OUT, exist_ok=True)
SUMM = os.path.join(HERE, "out", f"summary_pool_scan_{SRC_NAME}.json")

# (池名, TICKER_SETS key, XGB 實驗 tag)
POOLS = [
    ("tw50", "tw50", "x26-tw50-h5-cs"),
    ("tw100", "tw100", "x26-tw100-h5-cs"),
    ("tw200", "tw200", "x26-tw200-h5-cs"),
    ("tw500", "tw500", "x26-tw500-h5-cs"),
    ("electronics", "electronics", "x26-electronics-h5-cs"),
    ("semi", "semi", "x26-semi-h5-cs"),
    ("elec_liq100", "elec_liq100", "x26-elecliq100-h5-cs"),
    ("elec_liq200", "elec_liq200", "x26-elecliq200-h5-cs"),
    ("elec_all", "elec_all", "x26-elec-h5-cs"),
]
PCOLS = ["p_full_permpos", "p_full_top20", "p_full"]
FREQS = [5, 1]          # 5 = 每 5 個交易日檢視一次;1 = 每日檢視(使用者 2026-09-11 要求可每日交易)


def ranking_from(fp, pcol, step):
    df = pd.read_parquet(fp)
    df = df[df.index.get_level_values("date") <= pd.Timestamp("2026-09-10")]
    dates = sorted(df.index.get_level_values("date").unique())
    return {d.strftime("%Y%m%d"): [code(t) for t in df.xs(d, level="date")[pcol].dropna().sort_values(ascending=False).index]
            for d in dates[::step]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    summ = json.load(open(SUMM, encoding="utf-8")) if os.path.exists(SUMM) else {}
    pools = [p for p in POOLS if not a.only or p[0] in a.only.split(",")]
    for pname, key, tag in pools:
        fp = os.path.join(R.XGB_EXP, f"{tag}_testpred.parquet")
        if not os.path.exists(fp):
            print(f"[SKIP] {pname}: 尚無 {tag}_testpred")
            continue
        meta = json.load(open(os.path.join(R.XGB_EXP, f"{tag}.json"), encoding="utf-8"))
        codes = [code(t) for t in TICKER_SETS[key]]
        avail = assemble_csv(codes + ["0050"])
        uni = [c for c in codes if c in avail]
        ind, liq, mkt = load_indicators(uni), L2.load_liquidity(uni), L2.load_market()
        print(f"\n######## {pname}  ({len(uni)} 檔, {SRC_NAME}) ########", flush=True)
        bh = BuyHoldStrategy(f"{pname}_ew", uni, uni)
        # 基準用 run_ncku.run(與前面報告同一個函式)
        r = R.run(bh, uni)
        summ[f"{pname}|ew"] = {k: v for k, v in r.items() if k != "xlsx"} | {"pool": pname, "n_stocks": len(uni), "kind": "ew"}
        print(f"  ew                      總收益 {r['total_return_pct']:+8.2f}%  MDD {r['max_dd_pct']:6.2f}%", flush=True)
        pd_df = pd.read_parquet(fp)
        for pcol, freq in [(c, f) for c in PCOLS if c in pd_df.columns for f in FREQS]:
            rk = ranking_from(fp, pcol, freq)
            name = pcol[2:]
            auc = round(meta["results"][name]["ensemble"]["test"]["auc"], 4)
            nfeat = meta["results"][name]["n_feat"]
            for kind, args in [("model", dict(liq_f=L2.LIQ["none"], mkt_f=L2.MKT["none"], exit_rank=None, stop=None, take=None, maxrank=5)),
                               ("v2", dict(liq_f=L2.LIQ["vol2k"], mkt_f=L2.MKT["ret20"], exit_rank=10, stop=("atr", 3.0), take=0.30, maxrank=30))]:
                sname = f"{pname}_{name}_f{freq}_{kind}"
                st = L2.Logic2(sname, uni, rk, ind, liq, mkt, args["liq_f"], args["mkt_f"], args["exit_rank"], args["stop"], args["take"],
                               topk=5, maxrank=args["maxrank"])
                rr = L2.run_one(sname, st, uni, OUT)
                summ[f"{pname}|{name}|f{freq}|{kind}"] = rr | {"pool": pname, "featset": name, "freq": freq, "kind": kind, "n_stocks": len(uni), "test_auc": auc, "n_feat": nfeat}
                print(f"  {name:13s} {'每日' if freq == 1 else '5日'} {kind:5s} 框架 {rr['total_return_pct']:+8.2f}%  扣成本 {rr['net_return_pct']:+8.2f}%  "
                      f"MDD {rr['net_max_dd_pct']:6.2f}%  淨Sharpe {rr['net_sharpe']:5.2f}  持股比 {rr['avg_exposure_pct']:5.1f}%  週轉 {rr['buy_turnover_x']:5.1f}x  "
                      f"來回 {rr['n_round_trips']:4d}  勝率 {rr['win_rate']}  AUC {auc}", flush=True)
        json.dump(summ, open(SUMM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[SAVED] {os.path.relpath(SUMM, HERE)} ({len(summ)} 筆)")


if __name__ == "__main__":
    main()
