"""Chart-GCN 2026 回測彙整(系統 B)。

讀 chartgcn/experiments_2026/ 裡 c26-gridbest-date-h{h}-s{seed} 三個 seed 的模型,對 2026 測試集推論 P(漲),
取 3-seed 平均機率後算兩種選股法:
  (1) 排名選股(JKX 十分位法,與 xgb / decile_ls 同協定):每 h 日再平衡,做多機率前 10%、放空後 10%,扣週轉成本。
  (2) 論文 §6.3 交易模擬(Li et al. 2022 原始法):逐檔「預測漲 → 買進;預測跌或 MACD<0 → 賣出」,50 檔等權平均淨值。
      論文原版無成本;另算扣成本版(買 0.1425%、賣 0.4425%,合計一趟來回 0.585%)。
基準:tw50 等權買進持有、0050。

用法(需先跑完 cgcn_chain):TW_CACHE_DIR=...cache_2026 python backtest_2026/run_cgcn_2026.py
輸出: backtest_2026/results/cgcn_2026.json、cgcn_2026_curves.parquet、cgcn_testpred_h{h}.parquet
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
CGCN = P.METHOD_CHARTGCN
CACHE = P.YF_2026_CACHE
EXPDIR = os.path.join(CGCN, "experiments_2026")
OUT = P.RESULTS
os.makedirs(OUT, exist_ok=True)
os.environ.setdefault("TW_CACHE_DIR", CACHE)
os.environ["CGCN_EXPDIR"] = EXPDIR
for p in (HERE, CGCN, os.path.join(CGCN, "core"), os.path.join(CGCN, "test"), os.path.join(CGCN, "analysis")):
    sys.path.insert(0, p)

from portfolio import portfolio_curves, buy_hold                 # noqa: E402
from model import ChartGCN                                        # noqa: E402
from data_loader import fetch_tw_stocks, TICKER_SETS             # noqa: E402
from run_paper_repro import load_ds_cache                         # noqa: E402
from decile_ls import cache_path, predict_proba, forward_returns  # noqa: E402
from backtest import compute_macd_signal                          # noqa: E402

TEST_START, TEST_END = "2026-01-01", "2026-09-10"
BUY_COST, SELL_COST = 0.001425, 0.004425     # 手續費 0.1425% 買賣各一次 + 證交稅 0.3% 賣出


def load_runs(h):
    runs = []
    for fp in sorted(glob.glob(os.path.join(EXPDIR, f"EXP-*_c26-gridbest-date-h{h}-s*.json"))):
        d = json.load(open(fp, encoding="utf-8"))
        mp = fp[:-5] + "_model.pt"
        if os.path.exists(mp):
            runs.append((d, mp))
    return runs


def ensemble_probs(runs, device="cpu"):
    p, ds = None, None
    accs = []
    for d, mp in runs:
        prm = d["params"]
        if ds is None:
            ds = load_ds_cache(cache_path(prm))
        m = ChartGCN(N=prm["N"], g=prm["g"], F_dim=ds.X.shape[-1],
                     use_attention=not prm.get("no_attention", False)).to(device)
        m.load_state_dict(torch.load(mp, map_location=device))
        pr = predict_proba(m, ds, prm.get("batch_mode", "paper"), device)
        p = pr if p is None else p + pr
        accs.append({"seed": prm["seed"], "acc": d["metrics"]["acc"], "f1_macro": d["f1_macro"],
                     "pred_up_ratio": round(float((pr > 0.5).mean()), 4)})
    return p / len(runs), ds, accs


def paper_sim(price, sub_df, pcol, with_cost):
    """論文 §6.3:逐檔長/空手,MACD(n=100) 輔助出場;回傳各檔淨值日序列。"""
    curves = {}
    n_trades = {}
    for tk, g in sub_df.groupby(level="ticker"):
        df = price.get(tk)
        if df is None:
            continue
        close = df["close"]
        macd = compute_macd_signal(close, n=100)
        pos, cash, shares, nt = 0, 1.0, 0.0, 0
        nv = {}
        for (d, _), row in g.iterrows():
            if d not in close.index:
                continue
            px = float(close.loc[d])
            pred = 1 if row[pcol] > 0.5 else 0
            if pred == 1 and pos == 0:
                shares = cash * (1 - BUY_COST if with_cost else 1) / px
                cash, pos, nt = 0.0, 1, nt + 1
            elif pos == 1 and (pred == 0 or macd.loc[d] < 0):
                cash = shares * px * (1 - SELL_COST if with_cost else 1)
                shares, pos, nt = 0.0, 0, nt + 1
            nv[d] = cash + shares * px
        if nv:
            curves[tk] = pd.Series(nv)
            n_trades[tk] = nt
    nvdf = pd.concat(curves, axis=1).sort_index().ffill()
    avg = nvdf.mean(axis=1)
    x = avg.pct_change().dropna()
    return {"final_ret_pct": round(float(avg.iloc[-1] - 1) * 100, 2),
            "max_dd_pct": round(float((avg / avg.cummax() - 1).min()) * 100, 2),
            "sharpe_daily_ann": round(float(x.mean() / x.std() * np.sqrt(246)), 2) if x.std() > 0 else 0.0,
            "avg_trades_per_stock": round(float(np.mean(list(n_trades.values()))), 1),
            "n_stocks": len(curves)}, avg - 1


def main():
    device = "cpu"
    price = fetch_tw_stocks(tickers=TICKER_SETS["tw50"], start="2016-01-01", end="2026-09-11")
    bh = [buy_hold(df["close"], TEST_START, TEST_END) for df in price.values()]
    bh = [v for v in bh if v == v]
    c0050 = pd.read_parquet(os.path.join(CACHE, "0050.TW.parquet"))["close"]
    allres = {"pool": "tw50", "ew_buyhold_pct": round(float(np.mean(bh)) * 100, 2),
              "bh_0050_pct": round(buy_hold(c0050, TEST_START, TEST_END) * 100, 2), "models": {}}
    curves = {}
    for h in (1, 5):
        runs = load_runs(h)
        if not runs:
            print(f"[SKIP] h={h} 沒有完成的 run")
            continue
        p, ds, accs = ensemble_probs(runs, device)
        meta = ds.meta
        df = pd.DataFrame({"date": [pd.Timestamp(m[1]) for m in meta], "ticker": [m[0] for m in meta],
                           "p_cgcn": p.astype("float32")})
        for hh in (1, 5, 20):
            df[f"r_h{hh}"] = forward_returns(price, meta, hh)
        df = df.set_index(["date", "ticker"]).sort_index()
        df = df[df.index.get_level_values("date") <= TEST_END]
        df.to_parquet(os.path.join(OUT, f"cgcn_testpred_h{h}.parquet"))
        res = {"n_seeds": len(runs), "per_seed": accs, "n_test": int(len(df)),
               "prob_mean": round(float(p.mean()), 4), "prob_std": round(float(p.std()), 4),
               "ens_acc": round(float(((p > 0.5) == (ds.y == 1)).mean()) * 100, 2)}
        r = portfolio_curves(df, "p_cgcn", h)
        if r:
            cv = r.pop("curve")
            for k, s in cv.items():
                curves[f"cgcn_h{h}|rank|{k}"] = s
            res["rank_decile"] = r
        sim_g, cg = paper_sim(price, df, "p_cgcn", with_cost=False)
        sim_n, cn = paper_sim(price, df, "p_cgcn", with_cost=True)
        curves[f"cgcn_h{h}|paper63|gross"] = cg
        curves[f"cgcn_h{h}|paper63|net"] = cn
        res["paper_sec63"] = {"gross": sim_g, "net": sim_n}
        allres["models"][f"h{h}"] = res
        print(f"[h{h}] ens acc {res['ens_acc']}%  prob_std {res['prob_std']} | 排名前10%淨 "
              f"{r['long_net']['cum_pct'] if r else 'NA'}%  H-L淨 {r['hl_net']['cum_pct'] if r else 'NA'}% | "
              f"§6.3 毛 {sim_g['final_ret_pct']}% 淨 {sim_n['final_ret_pct']}% | 等權 {allres['ew_buyhold_pct']}%")
    json.dump(allres, open(os.path.join(OUT, "cgcn_2026.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    if curves:
        pd.DataFrame(curves).to_parquet(os.path.join(OUT, "cgcn_2026_curves.parquet"))
    print("[SAVED] results/cgcn_2026.json")


if __name__ == "__main__":
    main()
