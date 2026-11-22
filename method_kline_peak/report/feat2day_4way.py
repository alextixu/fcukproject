"""一檔股票一年(預設 2024):29 維 / 2 日 K × 主軸 / Stacking 四組對照(2026-11-22 使用者要求;設定同 feat2day_compare.py,8d50f0e)。

TW200 剔除低波動 168 檔、測試 2024、種子 42、訓練門檻 0%;2day10 的 AE 潛在 4 維。四組都是全部 168 檔一起跑的
walk-forward 結果,再取出指定的股票(預設南電 8046)。每日判斷用同一套設定重新產生,並核對:
  168 檔 2024 的混淆矩陣 = feat2day_compare_tw200.json(兩組特徵 × 兩方法);
  南電另核對 29 維兩組 = results/outputs_8046_2024_tw200_amp0.csv、Stacking 數字 = feat2day_compare_tw200.json 的南電。
圖:收盤 + 真實標籤、29 維 · 主軸、29 維 · Stacking、2 日 K · 主軸、2 日 K · Stacking(標在判斷日 t,不畫持有期間)。
用法: python method_kline_peak/report/feat2day_4way.py [3661.TW 1519.TW ...] [--year 2025](預設 8046.TW、2024;可一次多檔,模型只跑一次)
      2025:主軸訓練 2021–2024、Stacking A 2021–2023 / B 2024;2026:主軸 2022–2025、A 2022–2024 / B 2025(walk-forward 前 4 年)
輸出: results/feat2day_<代號>_<年>_tw200_4way.png / .json,以及每日判斷 _4way_daily.csv
"""
import argparse
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
from confusion import summarize  # noqa: E402
from export_windows import ticker_names  # noqa: E402
from feasibility import clean  # noqa: E402
from paper_aeocsvm import NAMES  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402

POOL, YEAR = "tw200", 2024
KEY = "confusion_rows_true_cols_pred(漲,不漲不跌,跌)"
LAB = {"低點": UP, "非極值": FLAT, "高點": DOWN}
GROUPS = [("29 維 · 主軸", "shape29", "主軸"), ("29 維 · Stacking", "shape29", "Stacking 邏輯迴歸"),
          ("2 日 K · 主軸", "2day10", "主軸"), ("2 日 K · Stacking", "2day10", "Stacking 邏輯迴歸")]


def predict_all(data, full):
    """四組(兩組特徵 × 兩方法)168 檔 2024 的每日判斷,並核對 168 檔的混淆矩陣 = feat2day_compare_tw200.json。"""
    sigs, pool_ok = {}, {}
    for f in ("shape29", "2day10"):
        ML.FEATURES = f
        panel, fc = ML.build_panel(data, 6, [], features=f)
        for m in ("主軸", "Stacking 邏輯迴歸"):
            sig, _ = WF.run_year(panel, fc, YEAR, BY.SOURCE_FACTORIES[m]())
            cm = summarize(sig["y"].to_numpy(), sig["pred"].to_numpy(), NAMES)[KEY]
            pool_ok[(f, m)] = cm == full["results"][f][str(YEAR)][m][KEY]           # 168 檔該年 = 上次的結果
            sigs[(f, m)] = sig
    ML.FEATURES = "shape29"
    assert all(pool_ok.values()), pool_ok
    return sigs, pool_ok


def main():
    global YEAR
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*", default=["8046.TW"])
    ap.add_argument("--year", type=int, default=YEAR, choices=[2024, 2025, 2026])
    a = ap.parse_args()
    tickers, YEAR = a.tickers, a.year
    data = ML.load_data(pool=POOL)
    for TK in tickers:
        assert TK in data, f"{TK} 不在 {POOL} 剔除低波動後的股票池"
    full = json.load(open(os.path.join(ML.OUT, "feat2day_compare_tw200.json"), encoding="utf-8"))
    sigs, pool_ok = predict_all(data, full)
    for TK in tickers:
        one(TK, data, sigs, pool_ok, full)


def one(TK, data, sigs, pool_ok, full):
    preds, dates, y = {}, None, None
    for (f, m), sig in sigs.items():
        s = sig[sig.ticker == TK].sort_values("date")
        if dates is None:
            dates, y = s["date"].to_numpy(), s["y"].to_numpy()
        assert (s["date"].to_numpy() == dates).all() and (s["y"].to_numpy() == y).all()
        preds[(f, m)] = s["pred"].to_numpy()
    daily = pd.DataFrame({"date": dates, "y": y, **{f"{f}|{m}": preds[(f, m)] for f, m in preds}})
    daily.to_csv(os.path.join(ML.OUT, f"feat2day_{TK[:4]}_{YEAR}_{POOL}_4way_daily.csv"), index=False)   # 每日判斷(1 低、0 非、2 高)
    close = clean(data[TK])["close"].loc[pd.DatetimeIndex(dates)].to_numpy()
    csv_path = os.path.join(ML.OUT, f"outputs_{TK[:4]}_{YEAR}_{POOL}_amp0.csv")
    if os.path.exists(csv_path):                                                   # 南電:29 維 = 既有的每日輸出
        csv = pd.read_csv(csv_path, parse_dates=["date"])
        assert (csv["date"].to_numpy() == dates).all() and (csv["真實標籤"].map(LAB).to_numpy() == y).all()
        for m in ("主軸", "Stacking 邏輯迴歸"):
            assert (csv[f"{m} 判斷"].map(LAB).to_numpy() == preds[("shape29", m)]).all()

    res = {"pool": POOL, "year": YEAR, "ticker": TK, "groups": {}}
    for title, f, m in GROUPS:
        p = preds[(f, m)]
        c = CP.counts(y, p)
        c["高低點判反"] = int(((p == UP) & (y == DOWN)).sum() + ((p == DOWN) & (y == UP)).sum())
        res["groups"][title] = {"features": f, "method": m, **c}
    ref = full["8046_2024_stack"] if TK == "8046.TW" and YEAR == 2024 else None    # 南電 2024 另核對個股 Stacking 數字
    res["核對_feat2day_compare"] = {f: pool_ok[(f, "主軸")] and pool_ok[(f, m)]
                                    and (ref is None or all(res["groups"][t][s] == ref[f][s] for s in ("低點", "高點")))
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
    fig.suptitle(f"{TK[:4]} {nm} {YEAR}" + ("(1–9 月)" if YEAR == 2026 else "") + ":29 維 vs 2 日 K(10 維)× 主軸 / Stacking(168 檔、訓練門檻 0%、種子 42)",
                 x=0.01, ha="left", fontsize=15, color=CP.INK, y=0.985)
    fig.text(0.01, 0.012, "▼ 判高點、▲ 判低點,標在判斷日 t:實心 = 和真實標籤相同、空心 = 判錯。", fontsize=10, color=CP.MUTED)
    out = os.path.join(ML.OUT, f"feat2day_{TK[:4]}_{YEAR}_{POOL}_4way.png")
    fig.savefig(out, facecolor="white", bbox_inches="tight")
    print(out)


if __name__ == "__main__":
    main()
