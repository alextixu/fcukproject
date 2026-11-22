"""南電 8046 2024:29 維 / 2 日 K × 主軸 / Stacking 四組對照(2026-11-22 使用者要求;設定同 feat2day_compare.py,8d50f0e)。

TW200 剔除低波動 168 檔、測試 2024、種子 42、訓練門檻 0%。
29 維兩組直接讀 results/outputs_8046_2024_tw200_amp0.csv(不重跑);2day10 的每日判斷上次沒有存檔,
用同一套設定(ML.FEATURES = "2day10"、AE 潛在 4 維)重新產生 2024,並和 feat2day_compare_tw200.json 的南電 Stacking 數字核對。
圖:收盤 + 真實標籤、29 維 · 主軸、29 維 · Stacking、2 日 K · 主軸、2 日 K · Stacking(標在判斷日 t,不畫持有期間)。
用法: python method_kline_peak/report/feat2day_4way.py
輸出: results/feat2day_8046_2024_tw200_4way.png、results/feat2day_8046_2024_tw200_4way.json
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import backtest_years as BY  # noqa: E402
import compare_postproc as CP  # noqa: E402
from export_windows import ticker_names  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402

POOL, YEAR, TK = "tw200", 2024, "8046.TW"
LAB = {"低點": UP, "非極值": FLAT, "高點": DOWN}
GROUPS = [("29 維 · 主軸", "shape29", "主軸"), ("29 維 · Stacking", "shape29", "Stacking 邏輯迴歸"),
          ("2 日 K · 主軸", "2day10", "主軸"), ("2 日 K · Stacking", "2day10", "Stacking 邏輯迴歸")]


def main():
    csv = pd.read_csv(os.path.join(ML.OUT, f"outputs_{TK[:4]}_{YEAR}_{POOL}_amp0.csv"), parse_dates=["date"])
    dates, close = csv["date"].to_numpy(), csv["close"].to_numpy()
    y = csv["真實標籤"].map(LAB).to_numpy()
    preds = {("shape29", m): csv[f"{m} 判斷"].map(LAB).to_numpy() for m in ("主軸", "Stacking 邏輯迴歸")}

    data = ML.load_data(pool=POOL)
    ML.FEATURES = "2day10"
    panel, fc = ML.build_panel(data, 6, [], features="2day10")
    for m in ("主軸", "Stacking 邏輯迴歸"):
        sig, _ = WF.run_year(panel, fc, YEAR, BY.SOURCE_FACTORIES[m]())
        s = sig[sig.ticker == TK].set_index("date").reindex(pd.DatetimeIndex(dates))
        assert s["pred"].notna().all() and (s["y"].to_numpy() == y).all()
        preds[("2day10", m)] = s["pred"].astype(int).to_numpy()
    ML.FEATURES = "shape29"

    res = {"pool": POOL, "year": YEAR, "ticker": TK, "groups": {}}
    for title, f, m in GROUPS:
        p = preds[(f, m)]
        c = CP.counts(y, p)
        c["高低點判反"] = int(((p == UP) & (y == DOWN)).sum() + ((p == DOWN) & (y == UP)).sum())
        res["groups"][title] = {"features": f, "method": m, **c}
    ref = json.load(open(os.path.join(ML.OUT, "feat2day_compare_tw200.json"), encoding="utf-8"))["8046_2024_stack"]
    res["核對_feat2day_compare"] = {f: all(res["groups"][t][s] == {k: v for k, v in ref[f][s].items()} for s in ("低點", "高點"))
                                    for t, f, m in GROUPS if m != "主軸"}
    print(json.dumps(res, ensure_ascii=False))
    with open(os.path.join(ML.OUT, f"feat2day_{TK[:4]}_{YEAR}_{POOL}_4way.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, default=float)

    pad = (close.max() - close.min()) * 0.04
    nm = ticker_names().get(TK, TK)
    fig, axes = plt.subplots(5, 1, figsize=(18, 16.5), dpi=150, sharex=True, facecolor="white", gridspec_kw={"hspace": 0.4})
    fig.subplots_adjust(left=0.05, right=0.99, top=0.93, bottom=0.05)
    for ax in axes:
        ax.plot(dates, close, color="#9a9994", lw=1.1, zorder=1)
        CP.style(ax)
        ax.set_ylim(close.min() - pad * 3, close.max() + pad * 3)
    for cls, mk, col, off, lab in ((DOWN, "v", CP.HI, pad, "真高點"), (UP, "^", CP.LO, -pad, "真低點")):
        mm = y == cls
        axes[0].scatter(dates[mm], close[mm] + off, marker=mk, s=40, color=col, zorder=3, label=f"{lab} {int(mm.sum())} 個")
    axes[0].set_title(f"{TK[:4]} {nm} {YEAR}:收盤與真實標籤(11 天收盤最高 / 最低)", loc="left", fontsize=12, color=CP.INK, fontweight="bold")
    axes[0].legend(frameon=True, facecolor="white", edgecolor=CP.GRID, fontsize=9.5, labelcolor=CP.INK, loc="lower left", ncol=2)
    for ax, (title, f, m) in zip(axes[1:], GROUPS):
        p = preds[(f, m)]
        for cls, mk, col, off in ((DOWN, "v", CP.HI, pad), (UP, "^", CP.LO, -pad)):
            on = p == cls
            hit, miss = on & (y == cls), on & (y != cls)
            ax.scatter(dates[hit], close[hit] + off, marker=mk, s=44, color=col, zorder=3)
            ax.scatter(dates[miss], close[miss] + off, marker=mk, s=44, facecolors="white", edgecolors=col, lw=1.2, zorder=3)
        c = res["groups"][title]
        L, H = c["低點"], c["高點"]
        ax.set_title(f"{title}:判低點 {L['判']} 天(對 {L['對']} / 錯 {L['錯']})、判高點 {H['判']} 天(對 {H['對']} / 錯 {H['錯']})",
                     loc="left", fontsize=11, color=CP.INK, fontweight="bold")
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m 月"))
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator())
    fig.suptitle(f"{TK[:4]} {nm} {YEAR}:29 維 vs 2 日 K(10 維)× 主軸 / Stacking(168 檔、訓練門檻 0%、種子 42)",
                 x=0.01, ha="left", fontsize=15, color=CP.INK, y=0.985)
    fig.text(0.01, 0.012, "▼ 判高點、▲ 判低點,標在判斷日 t:實心 = 和真實標籤相同、空心 = 判錯。", fontsize=10, color=CP.MUTED)
    out = os.path.join(ML.OUT, f"feat2day_{TK[:4]}_{YEAR}_{POOL}_4way.png")
    fig.savefig(out, facecolor="white", bbox_inches="tight")
    print(out)


if __name__ == "__main__":
    main()
