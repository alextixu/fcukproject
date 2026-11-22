"""主軸 2024–2026 的混淆矩陣(每年一格)。

股票池 = mainline.load_data(pool)(剔除每日漲跌幅中位數 < 0.725% 的低波動股;TW200 → 168 檔);
測哪一年就用前 4 年訓練,訓練期剔除最後 5 個交易日;訓練門檻 0%;對答案用原本的標籤(11 天收盤最高 / 最低)。種子 42。
用法: python method_kline_peak/report/confusion_2024_2026.py --pool tw200 [--years 2025]
輸出: results/confusion_2024_2026_<股票池>.png / .json(--years 非預設時檔名改用年份,例 confusion_2025_tw200)
"""
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import confusion_compare as CC  # noqa: E402
from confusion import summarize  # noqa: E402
from paper_aeocsvm import NAMES  # noqa: E402

YEARS = (2024, 2025, 2026)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="+", default=list(YEARS), help="測試年份")
    ap.add_argument("--pool", default=ML.POOL, help="股票池(預設 mainline.POOL)")
    a = ap.parse_args()
    years = tuple(a.years)
    data = ML.load_data(pool=a.pool)
    panel, fc = ML.build_panel(data, 6, [])
    res, ndays = {}, {}
    fig, axes = plt.subplots(1, len(years), figsize=(5.6 * len(years), 6.4), dpi=150, squeeze=False)
    for c, y in enumerate(years):
        d = WF.year_split(panel, y)
        a0, a1 = d["train"].date.dt.year.min(), d["train"].date.dt.year.max()
        sig, _ = WF.run_year(panel, fc, y, WF.MainlineSource())
        s = summarize(sig.y.to_numpy(), sig.pred.to_numpy(), NAMES)
        res[str(y)] = {"主軸": s}
        ndays[y] = len(sig)
        CC.panel(axes[0, c], f"測試 {y}" + ("(1–9 月)" if y == 2026 else "") + f",訓練 {a0}–{a1}", s[CC.KEY])
    span = f"{years[0]}" if len(years) == 1 else f"{years[0]}–{years[-1]}"
    fig.suptitle(f"主軸 {span} 混淆矩陣({a.pool.upper()} 剔除低波動股後 {len(data)} 檔,訓練門檻 0%,種子 42)\n"
                 "對答案用原本的標籤;顏色 = 每列比例", fontsize=15, color=CC.INK, x=0.02, ha="left", y=0.99, linespacing=1.4)
    fig.text(0.02, 0.01, "列 = 真實標籤、欄 = 判斷;橘框 = 高低點判反。測試天數:"
             + "、".join(f"{y} 年 {n:,} 天" for y, n in ndays.items()) + "。", fontsize=10.5, color=CC.MUTED)
    fig.tight_layout(rect=(0, 0.08, 1, 0.86), w_pad=2.5)
    stem = "confusion_2024_2026" if years == YEARS else "confusion_" + "_".join(map(str, years))
    out = os.path.join(ML.OUT, f"{stem}_{a.pool}.png")
    fig.savefig(out, facecolor="white")
    with open(os.path.join(ML.OUT, f"{stem}_{a.pool}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for y in years:
        print(y, round(res[str(y)]["主軸"]["macro_f1"] * 100, 2))
    print(out)


if __name__ == "__main__":
    main()
