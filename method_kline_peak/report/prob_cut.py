"""Stacking 邏輯迴歸:最大機率 ≥ 門檻才出訊號(2026-11-09 使用者要求;不訓練新模型、不跑回測)。

模型 = TW200(168 檔)、訓練門檻 0%、種子 42,同 compare_8046_2024_tw200_stack.png。Stacking 的 score = 最大那一類的機率,
判斷 = 最大機率那一類;設門檻 c 時,score < c 的判斷一律改成非極值。對答案用原本的標籤。
圖(南電 2024):真實標籤、原始(不設門檻 = A0,判對的訊號旁標當天機率)、≥ 0.7、≥ 0.8。
表:南電 2024 與全部 168 檔 2024–2026(三年平均)× 門檻 不設 / 0.6 / 0.7 / 0.8 / 0.9。
用法: python method_kline_peak/report/prob_cut.py
輸出: results/prob_cut_8046_2024_tw200_stack.png、results/prob_cut_tw200.json
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import backtest_years as BY  # noqa: E402
import postproc_signals as PP  # noqa: E402
import compare_postproc as CP  # noqa: E402
from export_windows import ticker_names  # noqa: E402
from feasibility import clean  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402

POOL, TK, YEARS, NAME = "tw200", "8046.TW", (2024, 2025, 2026), "Stacking 邏輯迴歸"
CUTS = [None, 0.6, 0.7, 0.8, 0.9]
PLOT = [None, 0.7, 0.8]
INK, MUTED, GRID = CP.INK, CP.MUTED, CP.GRID
HI, LO = CP.HI, CP.LO
label = lambda c: "不設門檻(原始)" if c is None else f"最大機率 ≥ {c}"  # noqa: E731


def cut(df, c):
    pred = df["pred"].to_numpy().copy()
    if c is not None:
        pred[df["score"].to_numpy() < c] = FLAT
    return pred


def main():
    data = ML.load_data(pool=POOL)
    panel, fc = ML.build_panel(data, 6, [])
    res = {"pool": POOL, "method": NAME, "ticker": TK, "南電 2024": {}, "全部": {}, "全部_三年平均": {}, "機率中位數": {}}
    for y in YEARS:
        sig, _ = WF.run_year(panel, fc, y, BY.SOURCE_FACTORIES[NAME]())
        df = sig.sort_values(["ticker", "date"]).reset_index(drop=True)
        res["全部"][str(y)] = {label(c): PP.metrics(df, cut(df, c)) for c in CUTS}
        res["機率中位數"][str(y)] = {s: round(float(df.loc[df.pred == cls, "score"].median()), 4) for s, cls in PP.SIDES.items()}
        if y == 2024:
            s = df[df.ticker == TK].reset_index(drop=True)
            keep = s
    for c in CUTS:
        ys = [res["全部"][str(y)][label(c)] for y in YEARS]
        e = {"macro_f1": round(float(np.mean([v["macro_f1"] for v in ys])), 2)}
        for side in PP.SIDES:
            e[side] = {k: (round(float(np.mean([v[side][k] for v in ys])), 2) if all(v[side][k] is not None for v in ys) else None)
                       for k in ys[0][side]}
        res["全部_三年平均"][label(c)] = e
    res["機率中位數_三年平均"] = {side: round(float(np.mean([res["機率中位數"][str(y)][side] for y in YEARS])), 4) for side in PP.SIDES}

    s = keep
    y_, dates = s["y"].to_numpy(), s["date"].to_numpy()
    for c in CUTS:
        res["南電 2024"][label(c)] = CP.counts(y_, cut(s, c))
    close = clean(data[TK])["close"]
    cl = close.loc[s["date"]].to_numpy()
    pad = (cl.max() - cl.min()) * 0.04
    nm = ticker_names().get(TK, TK)
    n = len(PLOT) + 1
    fig, axes = plt.subplots(n, 1, figsize=(18, 3.6 * n), dpi=150, sharex=True, facecolor="white", gridspec_kw={"hspace": 0.42})
    fig.subplots_adjust(left=0.05, right=0.99, top=0.93, bottom=0.06)
    for ax in axes:
        ax.plot(dates, cl, color="#9a9994", lw=1.1, zorder=1)
        CP.style(ax)
        ax.set_ylim(cl.min() - pad * 5, cl.max() + pad * 5)
    ax = axes[0]
    for cls, mk, col, off, lab in ((DOWN, "v", HI, pad, "真高點"), (UP, "^", LO, -pad, "真低點")):
        m = y_ == cls
        ax.scatter(dates[m], cl[m] + off, marker=mk, s=40, color=col, zorder=3, label=f"{lab} {int(m.sum())} 個")
    ax.set_title(f"{TK[:4]} {nm} 2024:收盤與真實標籤(11 天收盤最高 / 最低)", loc="left", fontsize=12, color=INK, fontweight="bold")
    ax.legend(frameon=True, facecolor="white", edgecolor=GRID, fontsize=9.5, labelcolor=INK, loc="lower left", ncol=2)
    sc = s["score"].to_numpy()
    for r, (ax, c) in enumerate(zip(axes[1:], PLOT)):
        p = cut(s, c)
        cnt = res["南電 2024"][label(c)]
        for cls, mk, col, off in ((DOWN, "v", HI, pad), (UP, "^", LO, -pad)):
            on = p == cls
            hit, miss = on & (y_ == cls), on & (y_ != cls)
            ax.scatter(dates[hit], cl[hit] + off, marker=mk, s=44, color=col, zorder=3)
            ax.scatter(dates[miss], cl[miss] + off, marker=mk, s=44, facecolors="white", edgecolors=col, lw=1.2, zorder=3)
            if r == 0:                                              # 原始那列:判對的訊號標當天機率(全部標太擠)
                for i in np.flatnonzero(hit):
                    strong = sc[i] >= 0.7
                    ax.annotate(f"{sc[i]:.2f}", (dates[i], cl[i] + off * 2.2), ha="center", va="bottom" if cls == DOWN else "top",
                                rotation=0, fontsize=8, color=INK if strong else MUTED, fontweight="bold" if strong else "normal")
        L, H = cnt["低點"], cnt["高點"]
        ax.set_title(f"{label(c)}:判低點 {L['判']} 天(對 {L['對']} / 錯 {L['錯']})、判高點 {H['判']} 天(對 {H['對']} / 錯 {H['錯']})"
                     + ("  · 數字 = 判對那天的最大機率(粗黑 = ≥ 0.7)" if r == 0 else ""), loc="left", fontsize=11, color=INK, fontweight="bold")
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m 月"))
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator())
    fig.suptitle(f"{TK[:4]} {nm} 2024:Stacking 邏輯迴歸 最大機率 ≥ 門檻才出訊號(168 檔、訓練門檻 0%、種子 42)",
                 x=0.01, ha="left", fontsize=15, color=INK, y=0.985)
    fig.text(0.01, 0.012, "▼ 判高點、▲ 判低點,標在判斷日 t:實心 = 和真實標籤相同、空心 = 判錯。不到門檻的改判非極值(圖上不畫)。",
             fontsize=10, color=MUTED)
    out = os.path.join(ML.OUT, "prob_cut_8046_2024_tw200_stack.png")
    fig.savefig(out, facecolor="white", bbox_inches="tight")
    with open(os.path.join(ML.OUT, "prob_cut_tw200.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("南電 2024", "全部_三年平均", "機率中位數", "機率中位數_三年平均")}, ensure_ascii=False))
    print(out)


if __name__ == "__main__":
    main()
