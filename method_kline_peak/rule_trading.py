"""論文規則基準當交易訊號,勝率有沒有比較高?(TW50)

訊號(t 日收盤後判斷,只用到 t 日):
  低點候選 = t 日收盤為 t−5 ~ t 最低 → 買進(做多)
  高點候選 = t 日收盤為 t−5 ~ t 最高 → 賣出 / 放空
交易:t+1 開盤進場,持有到 t+h 收盤出場(h = 1 / 3 / 5),還原價報酬 r = C[t+h] / O[t+1] − 1
勝:做多 r > 0、放空 r < 0;另列扣 0.42% 成本(手續費 0.06% × 2 + 證交稅 0.3%)後仍賺的比例
對照:同期間每一天都做多 / 都放空(不挑時點)
拆解:候選裡「真的是 11 日高(低)點」與「之後 5 天被超越的假候選」各自的勝率
另列「不重疊」:同一檔持有中出現的新訊號略過(實際一次只能持有一筆)

用法: python method_kline_peak/rule_trading.py
輸出: method_kline_peak/results/rule_trading_tw50.json
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from feasibility import START, END, COST, load_pool, clean  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402
from paper_aeocsvm import paper_label  # noqa: E402

OUT = os.path.join(HERE, "results")
HOLDS = (1, 3, 5)
PERIODS = {"全期 2016–2026": (START, END), "2022–2023": ("2022-01-01", "2023-12-31"),
           "2025-01 ~ 2026-09": ("2025-01-01", END)}


def build(data):
    parts = []
    for tk, df in data.items():
        df = clean(df)
        y, cand_hi, cand_lo = paper_label(df["close"])
        part = pd.DataFrame({"y": y, "cand_hi": cand_hi, "cand_lo": cand_lo}, index=df.index)
        for h in HOLDS:
            part[f"r{h}"] = df["close"].shift(-h) / df["open"].shift(-1) - 1
        part["ticker"] = tk
        part.index.name = "date"
        parts.append(part.reset_index())
    p = pd.concat(parts, ignore_index=True)
    return p[p["y"].notna() & p[[f"r{h}" for h in HOLDS]].notna().all(axis=1)].reset_index(drop=True)


def non_overlap(sub, h):
    """同一檔持有期間(t+1 ~ t+h)內的新訊號略過。"""
    keep = []
    for _, g in sub.groupby("ticker"):
        dates = g["date"].to_numpy()
        busy_until = np.datetime64("1900-01-01")
        for i, d in zip(g.index, dates):
            if d > busy_until:
                keep.append(i)
                pos = np.searchsorted(dates, d)
                busy_until = dates[min(pos + h, len(dates) - 1)]
    return sub.loc[keep]


def stats(r, side):
    win = (r > 0) if side == "long" else (r < 0)
    net = (r - COST) if side == "long" else (-r - COST)
    return {"n": int(len(r)), "win": float(win.mean()), "win_after_cost": float((net > 0).mean()),
            "avg_pct": float(r.mean() * 100 * (1 if side == "long" else -1)), "avg_net_pct": float(net.mean() * 100)}


def main():
    p = build(load_pool("tw50", START, END))
    out = {}
    for pname, (a, b) in PERIODS.items():
        q = p[p["date"].between(a, b)]
        res = {}
        print(f"\n== {pname}(共 {len(q):,} 個股票日)")
        for h in HOLDS:
            r = q[f"r{h}"]
            row = {"每天都做多": stats(r, "long"), "每天都放空": stats(r, "short")}
            lo, hi = q[q["cand_lo"]], q[q["cand_hi"]]
            row["低點訊號做多"] = stats(lo[f"r{h}"], "long")
            row["  其中真低點"] = stats(lo.loc[lo["y"] == UP, f"r{h}"], "long")
            row["  其中假候選"] = stats(lo.loc[lo["y"] != UP, f"r{h}"], "long")
            row["高點訊號放空"] = stats(hi[f"r{h}"], "short")
            row["  其中真高點"] = stats(hi.loc[hi["y"] == DOWN, f"r{h}"], "short")
            row["  其中假候選 "] = stats(hi.loc[hi["y"] != DOWN, f"r{h}"], "short")
            row["低點訊號做多(不重疊)"] = stats(non_overlap(lo, h)[f"r{h}"], "long")
            row["高點訊號放空(不重疊)"] = stats(non_overlap(hi, h)[f"r{h}"], "short")
            res[f"持有 {h} 天"] = row
            print(f"  持有 {h} 天:{'':<14}{'筆數':>8} {'勝率':>7} {'扣成本後勝':>9} {'平均報酬':>9} {'扣成本後':>8}")
            for k, s in row.items():
                print(f"    {k:<18}{s['n']:>8,} {s['win']:>7.1%} {s['win_after_cost']:>9.1%} "
                      f"{s['avg_pct']:>+8.2f}% {s['avg_net_pct']:>+7.2f}%")
        out[pname] = res
    with open(os.path.join(OUT, "rule_trading_tw50.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
