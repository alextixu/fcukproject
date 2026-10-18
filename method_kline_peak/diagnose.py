"""feasibility.py 結果的兩個追查。

  1. 候選日內 AUC 的來源:hl 口徑下單一特徵 upper_atr(收盤離當日高點幾個 ATR)就有 AUC ≈ 0.73,
     依 upper_atr 十分位看 P(頂) 與 t+1 開 → t+5 收報酬 —— 「高點難被超過」是否等於「之後會跌」
  2. full 模型前 10% 底 的報酬是否集中在少數月份(2025-04 關稅急跌後反彈)
  3. 同樣在 left_bot 候選日取前 10%,但改用單一因子(波動、近期跌幅、大盤跌幅)排序 ——
     若單一因子報酬 ≥ 模型,模型報酬就不是來自「預測底標籤」

用法: python method_kline_peak/diagnose.py --pool tw50
輸出: method_kline_peak/results/diagnose_<pool>.json
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from feasibility import (P, START, END, SEEDS, TOP, BOTTOM, OUT, load_pool, clean,  # noqa: E402
                         build_panel, split_frames, fit_lgb, causal_features)


def decile_table(c, feat, cls):
    q = pd.qcut(c[feat], 10, labels=False, duplicates="drop")
    g = c.groupby(q)
    return pd.DataFrame({"n": g.size(), "p_label": g["y"].apply(lambda s: (s == cls).mean()),
                         "ret_pct": g["fwd_oc5"].mean() * 100}).round(4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="tw50")
    args = ap.parse_args()
    data = load_pool(args.pool, START, END)
    mkt = clean(pd.read_parquet(os.path.join(P.YF_2026_CACHE, "0050.TW.parquet")))
    panel = build_panel(data, mkt)
    feat_cols = list(causal_features(next(iter(data.values())).head(80), mkt).columns)
    out = {}

    for v in ("hl", "close"):
        sp = split_frames(panel, v, feat_cols)
        te = sp["test"]
        res = {}
        # 1. 單一特徵十分位(test 候選日)
        res["upper_atr_deciles_top"] = decile_table(te[te["lt"] == 1], "upper_atr", TOP).to_dict("index")
        res["lower_atr_deciles_bot"] = decile_table(te[te["lb"] == 1], "lower_atr", BOTTOM).to_dict("index")

        # 2. full 模型前 10% 底 的月份分佈
        full = ["lt", "lb"] + feat_cols
        m = fit_lgb(sp["train"], sp["val"], full, SEEDS[0])
        te = te.assign(p_bot=m.predict_proba(te[full])[:, 2], p_top=m.predict_proba(te[full])[:, 1])
        for key, col, pcol in (("bot", "lb", "p_bot"), ("top", "lt", "p_top")):
            c = te[te[col] == 1]
            pick = c[c[pcol] >= c[pcol].quantile(0.9)]
            month = pick["date"].dt.to_period("M").astype(str)
            by_m = pick.groupby(month)["fwd_oc5"].agg(["size", "mean"])
            excl = pick[month != "2025-04"]
            res[f"top10_{key}"] = {
                "n": len(pick), "ret_pct": float(pick["fwd_oc5"].mean() * 100),
                "share_2025_04": float((month == "2025-04").mean()),
                "ret_excl_2025_04_pct": float(excl["fwd_oc5"].mean() * 100),
                "cand_ret_excl_2025_04_pct": float(
                    c[c["date"].dt.to_period("M").astype(str) != "2025-04"]["fwd_oc5"].mean() * 100),
                "by_month": {k: {"n": int(r["size"]), "ret_pct": round(float(r["mean"]) * 100, 3)}
                             for k, r in by_m.iterrows()},
            }
        # 3. 單一因子排序的前 10% 底 候選
        c = te[te["lb"] == 1]
        c_month = c["date"].dt.to_period("M").astype(str)
        res["factor_top10_bot"] = {}
        for f, sign in (("atr14", 1), ("vol20", 1), ("ret5", -1), ("ret20", -1),
                        ("m_ret5", -1), ("m_ret20", -1), ("lower_atr", 1)):
            s = c[f] * sign
            pick = s >= s.quantile(0.9)
            res["factor_top10_bot"][("-" if sign < 0 else "") + f] = {
                "ret_pct": float(c.loc[pick, "fwd_oc5"].mean() * 100),
                "p_bot": float((c.loc[pick, "y"] == BOTTOM).mean()),
                "share_2025_04": float((c_month[pick] == "2025-04").mean()),
                "ret_excl_2025_04_pct": float(c.loc[pick & (c_month != "2025-04"), "fwd_oc5"].mean() * 100),
            }
        out[v] = res

        print(f"\n== {v} ==")
        print("  upper_atr 十分位(left_top 候選):P(頂) / 報酬%")
        for k, r in res["upper_atr_deciles_top"].items():
            print(f"    d{k}: n={r['n']:>4}  P(頂)={r['p_label']:.3f}  ret={r['ret_pct']:+.2f}%")
        print("  lower_atr 十分位(left_bot 候選):P(底) / 報酬%")
        for k, r in res["lower_atr_deciles_bot"].items():
            print(f"    d{k}: n={r['n']:>4}  P(底)={r['p_label']:.3f}  ret={r['ret_pct']:+.2f}%")
        for key in ("bot", "top"):
            t = res[f"top10_{key}"]
            print(f"  full 前10% {key}: n={t['n']} 報酬 {t['ret_pct']:+.2f}%  2025-04 佔 {t['share_2025_04']:.1%}  "
                  f"排除 2025-04 後 {t['ret_excl_2025_04_pct']:+.2f}%(同期候選 {t['cand_ret_excl_2025_04_pct']:+.2f}%)")
        print("  單一因子前 10% 底 候選:")
        for f, t in res["factor_top10_bot"].items():
            print(f"    {f:<10} 報酬 {t['ret_pct']:+.2f}%  P(底) {t['p_bot']:.3f}  2025-04 佔 {t['share_2025_04']:.0%}  "
                  f"排除後 {t['ret_excl_2025_04_pct']:+.2f}%")

    fp = os.path.join(OUT, f"diagnose_{args.pool}.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n輸出 {fp}")


if __name__ == "__main__":
    main()
