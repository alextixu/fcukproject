"""2024–2026 的混淆矩陣:規則、主軸、Stacking 邏輯迴歸,訓練門檻 0%(預設)與 8%(2026-11-02 使用者要求)。

股票池 = mainline.load_data()(34 檔);測哪一年就用前 4 年訓練(Stacking:前 3 年基底層 A + 第 4 年元學習器 B),
訓練期剔除最後 5 個交易日;對答案一律用原本的標籤(只要是 11 天最高 / 最低就算)。種子 42。
--side 3:改畫「每邊至少 3 天對方向」訓練的版本(規則、主軸、Stacking 邏輯迴歸),輸出檔名加 _side3。
--plain:只畫規則、主軸、Stacking 邏輯迴歸(門檻 0%);輸出檔名加股票池名稱(例 _tw100)。
用法: python method_kline_peak/report/confusion_2024_2026.py [--amp 8 | --side 3 | --plain]
輸出: results/confusion_2024_2026.png、results/confusion_2024_2026.json(或 _side3)
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
import backtest_years as BY  # noqa: E402
import confusion_compare as CC  # noqa: E402
from confusion import summarize  # noqa: E402
from paper_aeocsvm import NAMES  # noqa: E402

YEARS = (2024, 2025, 2026)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--amp", type=float, default=8.0)
    ap.add_argument("--side", type=int, default=0)
    ap.add_argument("--plain", action="store_true", help="只畫規則、主軸、Stacking 邏輯迴歸(門檻 0%)")
    a = ap.parse_args()
    amp, side = a.amp, a.side
    data = ML.load_data()
    panel, fc = ML.build_panel(data, 6, [])
    if a.plain:
        cols = [("規則(不用訓練)", "規則", 0.0, 0), ("① 主軸", "主軸", 0.0, 0), ("② Stacking 邏輯迴歸", "Stacking 邏輯迴歸", 0.0, 0)]
    elif side:
        cols = [("規則(不用訓練)", "規則", 0.0, 0), (f"① 主軸,每邊 ≥ {side} 天", "主軸", 0.0, side),
                (f"② Stacking 邏輯迴歸,每邊 ≥ {side} 天", "Stacking 邏輯迴歸", 0.0, side)]
    else:
        cols = [("規則(不用訓練)", "規則", 0.0, 0), ("① 主軸,門檻 0%", "主軸", 0.0, 0), (f"① 主軸,門檻 {amp:g}%", "主軸", amp, 0),
                ("② Stacking 邏輯迴歸,門檻 0%", "Stacking 邏輯迴歸", 0.0, 0), (f"② Stacking 邏輯迴歸,門檻 {amp:g}%", "Stacking 邏輯迴歸", amp, 0)]
    res, ndays = {}, {}
    fig, axes = plt.subplots(len(YEARS), len(cols), figsize=(5.2 * len(cols), 16), dpi=150)
    for r, y in enumerate(YEARS):
        d = WF.year_split(panel, y)
        a0, a1 = d["train"].date.dt.year.min(), d["train"].date.dt.year.max()
        res[str(y)] = {}
        for c, (title, src, th, sd) in enumerate(cols):
            sig, _ = WF.run_year(panel, fc, y, BY.SOURCE_FACTORIES[src](), train_min_amp=th, train_min_side=sd)
            s = summarize(sig.y.to_numpy(), sig.pred.to_numpy(), NAMES)
            res[str(y)][title] = s
            ndays[y] = len(sig)
            sub = "" if src == "規則" else (f"(訓練 {a0}–{a1})" if src == "主軸" else f"(A {a0}–{a1 - 1}、B {a1})")
            CC.panel(axes[r, c], f"{title}{sub}", s[CC.KEY])
        fig.text(0.004, 1 - (r + 0.5) / len(YEARS) * 0.95 - 0.02, f"測試 {y}" + ("(1–9 月)" if y == 2026 else ""), rotation=90,
                 va="center", fontsize=15, color=CC.INK, fontweight="bold")
    what = "訓練門檻 0%" if a.plain else (f"訓練:每邊至少 {side} 天對方向" if side else f"訓練門檻 0% 與 {amp:g}%")
    fig.suptitle(f"2024–2026 混淆矩陣({ML.POOL.upper()} 剔除低波動股後 {len(data)} 檔,種子 42;{what};對答案都用原本的標籤;顏色 = 每列比例)",
                 fontsize=16, color=CC.INK, x=0.02, ha="left", y=0.997)
    fig.text(0.02, 0.003, "列 = 真實標籤、欄 = 判斷;橘框 = 高低點判反。測試天數:"
             + "、".join(f"{y} 年 {n:,} 天" for y, n in ndays.items()) + "。", fontsize=11, color=CC.MUTED)
    fig.tight_layout(rect=(0.012, 0.015, 1, 0.975), h_pad=3.0, w_pad=2.2)
    tag = f"_{ML.POOL}" + ("" if a.plain else (f"_side{side}" if side else ""))
    out = os.path.join(ML.OUT, f"confusion_2024_2026{tag}.png")
    fig.savefig(out, facecolor="white")
    with open(os.path.join(ML.OUT, f"confusion_2024_2026{tag}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for y in YEARS:
        print(y, {t: round(v["macro_f1"] * 100, 2) for t, v in res[str(y)].items()})
    print(out)


if __name__ == "__main__":
    main()
