"""xgb_ta_pipeline 2026 回測彙整:讀 experiments/x26-*_testpred.parquet(test = 2026-01-02 起的 ensemble 機率),
算前 10% 純多頭 / H-L 多空 的 2026 累積報酬(扣成本),與同池等權買進持有、0050 比較。

用法: python backtest_2026/run_xgb_2026.py
輸出: backtest_2026/results/xgb_2026.json、xgb_2026_curves.parquet
"""
import glob
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
XGB = P.METHOD_XGB
CACHE = P.YF_2026_CACHE
OUT = P.RESULTS
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE)
from portfolio import portfolio_curves, buy_hold  # noqa: E402

TEST_START, TEST_END = "2026-01-01", "2026-09-10"


def main():
    c0050 = pd.read_parquet(os.path.join(CACHE, "0050.TW.parquet"))["close"]
    bh_0050 = buy_hold(c0050, TEST_START, TEST_END)
    allres, curves = {}, {}
    for fp in sorted(glob.glob(os.path.join(XGB, "experiments", "x26-*_testpred.parquet"))):
        tag = os.path.basename(fp).replace("_testpred.parquet", "")
        meta = json.load(open(os.path.join(XGB, "experiments", f"{tag}.json"), encoding="utf-8"))
        h = meta["config"]["horizon"]
        df = pd.read_parquet(fp)
        df = df[df.index.get_level_values("date") <= TEST_END]
        # 同池等權買進持有(還原收盤,由 cache_2026 主檔)
        tks = df.index.get_level_values("ticker").unique()
        bh = []
        for tk in tks:
            f = os.path.join(CACHE, f"{tk}.parquet")
            if os.path.exists(f):
                v = buy_hold(pd.read_parquet(f)["close"], TEST_START, TEST_END)
                if v == v:
                    bh.append(v)
        res = {"h": h, "pool": meta["config"]["pool"], "label": meta["label"], "n_stocks": len(tks),
               "ew_buyhold_pct": round(sum(bh) / len(bh) * 100, 2), "bh_0050_pct": round(bh_0050 * 100, 2),
               "sets": {}}
        for col in [c for c in df.columns if c.startswith("p_")]:
            name = col[2:]
            r = portfolio_curves(df, col, h)
            if r is None:
                continue
            cv = r.pop("curve")
            for k, s in cv.items():
                curves[f"{tag}|{name}|{k}"] = s
            r["n_feat"] = meta["results"][name]["n_feat"]
            r["test_auc"] = round(meta["results"][name]["ensemble"]["test"]["auc"], 4)
            r["test_acc"] = round(meta["results"][name]["ensemble"]["test"]["acc"] * 100, 2)
            res["sets"][name] = r
            print(f"{tag:22s} {name:14s} h{h} 期數{r['n_periods']:3d} | 純多頭淨 {r['long_net']['cum_pct']:+7.2f}% "
                  f"(t {r['long_net']['t']:+.2f}) | H-L 淨 {r['hl_net']['cum_pct']:+7.2f}% (t {r['hl_net']['t']:+.2f}) "
                  f"| 等權 {res['ew_buyhold_pct']:+.2f}%  0050 {res['bh_0050_pct']:+.2f}%")
        allres[tag] = res
    json.dump(allres, open(os.path.join(OUT, "xgb_2026.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    if curves:
        pd.DataFrame(curves).to_parquet(os.path.join(OUT, "xgb_2026_curves.parquet"))
    print(f"[SAVED] results/xgb_2026.json ({len(allres)} 個實驗)")


if __name__ == "__main__":
    main()
