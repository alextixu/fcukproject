"""最佳系統 v3 逐年回測(2021 ~ 2026),每年都用「當年以前」的資料訓練的模型(walk-forward)。

模型:測試年 Y 用 train ≤ Y-2、val = Y-1 重訓的 XGB(x{YY}-tw50-h5-cs、permpos 在 val 重選);2026 用現行模型。
交易規則完全沿用 2026 選出的 v3,不再調整:每日檢視、抱 3 檔、連續 2 天掉出前 8 名才賣、不看大盤、不設停損停利、流動性 2,000 張。
資料:NCKU 框架引擎 + yfinance 還原價(NCKU_SRC=yf_hist,2020-09 ~ 2026-09-10);扣成本(買 0.1425%、賣 0.4425%)。
用法: NCKU_SRC=yf_hist python run_years.py
輸出: out/years/*.xlsx、out/summary_years.json(含每年曲線)
"""
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
EXP = R.XGB_EXP
OUT = os.path.join(HERE, "out", "years")
os.makedirs(OUT, exist_ok=True)
SUMM = os.path.join(HERE, "out", "summary_years.json")
VARIANTS = {
    "v3": dict(K=3, N=8, M=2, mh=0),
    "前10名連2天": dict(K=3, N=10, M=2, mh=0),
    "前8名連3天": dict(K=3, N=8, M=3, mh=0),
    "抱5檔": dict(K=5, N=8, M=2, mh=0),
    "上一版": dict(K=3, N=3, M=1, mh=10),
    "5日前5檔全換": dict(K=5, N=None, M=1, mh=0, freq=5),
    "5日前5檔續抱前10": dict(K=5, N=10, M=1, mh=0, freq=5),
}


def probs(year):
    if year == 2026:
        return pd.read_parquet(os.path.join(RES, "tw50_h5_permpos_fullpred.parquet"))["p"]
    tp = pd.read_parquet(os.path.join(EXP, f"x{str(year)[2:]}-tw50-h5-cs_testpred.parquet"))
    return tp["p_full_permpos"]


def main():
    summ = json.load(open(SUMM, encoding="utf-8")) if os.path.exists(SUMM) else {}
    tw50 = [code(t) for t in TICKER_SETS["tw50"]]
    avail = assemble_csv(tw50 + ["0050"])
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write("end_date: '20261231'\nstart_date: '20200101'\n")
    uni = [c for c in tw50 if c in avail]
    ind, liq, mkt = load_indicators(uni), L2.load_liquidity(uni), L2.load_market()
    for year in range(2021, 2027):
        try:
            p = probs(year)
        except FileNotFoundError:
            print(f"[SKIP] {year}: 模型尚未訓練完", flush=True)
            continue
        p = p[(p.index.get_level_values("date").year == year)]
        w = p.unstack("ticker").sort_index()
        dates = list(w.index)
        start, end = dates[0].strftime("%Y%m%d"), dates[-1].strftime("%Y%m%d")
        rk = {d.strftime("%Y%m%d"): [code(t) for t in row.dropna().sort_values(ascending=False).index] for d, row in w.iterrows()}
        rk5 = {k: v for i, (k, v) in enumerate(rk.items()) if i % 5 == 0}
        R.START, R.END, L2.START, L2.END = start, end, start, end
        R.OUT = OUT
        rec = {"year": year, "start": start, "end": end, "n_days": len(dates)}
        for bname, st, u in [("0050", BuyHoldStrategy(f"b0050_{year}", uni + ["0050"], ["0050"]), uni + ["0050"]),
                             ("tw50等權", BuyHoldStrategy(f"ew_{year}", uni, uni), uni)]:
            r = R.run(st, u)
            rec[bname] = {"ret": r["total_return_pct"], "mdd": r["max_dd_pct"], "curve": r["curve"]}
        for vname, c in VARIANTS.items():
            st = L2.Logic2(f"{vname}_{year}", uni, rk5 if c.get("freq") == 5 else rk, ind, liq, mkt, L2.LIQ["vol2k"], L2.MKT["none"], c["N"], None, None,
                           topk=c["K"], maxrank=max(15, 3 * c["K"]), min_hold=c["mh"], out_days=c["M"])
            r = L2.run_one(f"{vname}_{year}", st, uni, OUT)
            rec[vname] = {"ret": r["net_return_pct"], "gross": r["total_return_pct"], "mdd": r["net_max_dd_pct"], "sharpe": r["net_sharpe"],
                          "trade_days": r["n_trade_days"], "trips": r["n_round_trips"], "win": r["win_rate"], "fees": r["fees_total"],
                          "exposure": r["avg_exposure_pct"], "curve": r["curve_net"] if vname == "v3" else None}
        meta = None if year == 2026 else json.load(open(os.path.join(EXP, f"x{str(year)[2:]}-tw50-h5-cs.json"), encoding="utf-8"))
        rec["model"] = ({"tag": "x26-tw50-h5-cs", "train_end": "2024-12-31", "val_end": "2025-12-31"} if meta is None else
                        {"tag": meta["tag"], "train_end": meta["config"]["train_end"], "val_end": meta["config"]["val_end"],
                         "n_feat": meta["results"]["full_permpos"]["n_feat"], "auc": round(meta["results"]["full_permpos"]["ensemble"]["test"]["auc"], 4),
                         "iters": [s["best_iter"] for s in meta["results"]["full_permpos"]["per_seed"]]})
        summ[str(year)] = rec
        json.dump(summ, open(SUMM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        v = rec["v3"]
        print(f"{year}: v3 {v['ret']:+7.1f}%  MDD {v['mdd']:6.1f}%  Sharpe {v['sharpe']:5.2f}  下單 {v['trade_days']:3d} 天 | 0050 {rec['0050']['ret']:+6.1f}%  等權 {rec['tw50等權']['ret']:+6.1f}% | "
              + "  ".join(f"{k} {rec[k]['ret']:+.1f}%" for k in VARIANTS if k != "v3"), flush=True)
    print(f"[SAVED] {os.path.relpath(SUMM, HERE)}")


if __name__ == "__main__":
    main()
