"""後處理:減少多判的訊號(2026-11-08 使用者要求;只整理現有模型的判斷,不改模型、不調參數)。

模型 = TW200(168 檔)、訓練門檻 0%、種子 42、walk-forward 前 4 年訓練(同 backtest_long_only_tw200.json);
測試 2024 / 2025 / 2026,主軸、Stacking 邏輯迴歸。高點、低點分開,每檔股票各自、每個方法各自處理;
被拿掉的訊號改判「非極值」。對答案一律用原本的標籤。

規則
  A0 原始:不處理(基準)
  1a 合併連續訊號・事後最高分(上限參考,會用到未來資訊):一段 = 同一檔、同一類、相鄰交易日都有訊號;每段只留分數最高的一天(同分取最早)
  1b 合併連續訊號・即時版:段內某天只有分數高於這段之前每一天才保留;第一天一定保留(只用當天以前的資訊)
  2-X 只看分數最高的一段:每天把同一類的訊號依分數由高到低排,只留前 X%(個數 = max(1, floor(訊號數 × X%));同分依代號),X = 50 / 25 / 10
「相鄰交易日」= 該檔股票測試期裡相鄰的兩列(各股自己的交易日)。

每年 × 方法 × 規則,判低點、判高點各一份:訊號數、命中率、找到率(精確:真轉折點當天有同類訊號)、
找到率(±2 天:真轉折點前後 2 個交易日內有同類訊號)、三分類 macro-F1、隨機猜的命中率基準(該年真低點 / 真高點占全部股票日的比例)。
用法: python method_kline_peak/postproc_signals.py
輸出: results/postproc_signals_tw200.json
"""
import json
import os
import time

import numpy as np
import pandas as pd

import mainline as ML
import walkforward as WF
import backtest_years as BY
from confusion import summarize
from learn5_trade6 import FLAT, UP, DOWN
from paper_aeocsvm import NAMES

POOL, YEARS, SOURCES = "tw200", (2024, 2025, 2026), ["主軸", "Stacking 邏輯迴歸"]
TOPS = (50, 25, 10)
RULES = ["A0 原始", "1a 合併連續・事後最高分(上限參考)", "1b 合併連續・即時版"] + [f"2 每天前 {x}%" for x in TOPS]
SIDES = {"低點": UP, "高點": DOWN}
NEAR = 2


def runs(df, cls):
    """每檔股票內,同一類的連續訊號編段號;沒有訊號的列為 -1。df 已依 ticker、date 排序。"""
    on = (df["pred"] == cls).to_numpy()
    tk = df["ticker"].to_numpy()
    new_tk = np.r_[True, tk[1:] != tk[:-1]]
    start = on & (new_tk | ~np.r_[False, on[:-1]])
    rid = np.cumsum(start) - 1
    return np.where(on, rid, -1)


def keep_1a(df, cls):
    rid = runs(df, cls)
    keep = np.zeros(len(df), bool)
    m = rid >= 0
    sub = pd.DataFrame({"rid": rid[m], "score": df["score"].to_numpy()[m]}, index=np.flatnonzero(m))
    keep[sub.groupby("rid")["score"].idxmax().to_numpy()] = True     # idxmax:同分取最早
    return keep


def keep_1b(df, cls):
    rid = runs(df, cls)
    sc = df["score"].to_numpy()
    keep = np.zeros(len(df), bool)
    best, cur = -np.inf, -1
    for i in np.flatnonzero(rid >= 0):
        if rid[i] != cur:
            cur, best = rid[i], sc[i]
            keep[i] = True
        elif sc[i] > best:
            best = sc[i]
            keep[i] = True
    return keep


def keep_top(df, cls, x):
    keep = np.zeros(len(df), bool)
    on = df["pred"] == cls
    sub = df[on].sort_values(["date", "score", "ticker"], ascending=[True, False, True])
    rank = sub.groupby("date").cumcount().to_numpy()
    n = sub.groupby("date")["ticker"].transform("size").to_numpy()
    k = np.maximum(1, np.floor(n * x / 100)).astype(int)
    keep[sub.index[rank < k]] = True
    return keep


def apply_rule(df, rule):
    pred = df["pred"].to_numpy().copy()
    if rule == RULES[0]:
        return pred
    for cls in (UP, DOWN):
        if rule.startswith("1a"):
            kp = keep_1a(df, cls)
        elif rule.startswith("1b"):
            kp = keep_1b(df, cls)
        else:
            kp = keep_top(df, cls, int(rule.split("前 ")[1].rstrip("%")))
        pred[(pred == cls) & ~kp] = FLAT
    return pred


def near_hit(df, pred, cls):
    """真轉折點(cls)前後 NEAR 個交易日內(同一檔)有同類訊號的比例。"""
    hit, tot = 0, 0
    y = df["y"].to_numpy()
    tk = df["ticker"].to_numpy()
    for t in np.unique(tk):
        idx = np.flatnonzero(tk == t)
        sig = (pred[idx] == cls).astype(int)
        cs = np.r_[0, np.cumsum(sig)]
        pos = np.flatnonzero(y[idx] == cls)
        lo, hi = np.maximum(pos - NEAR, 0), np.minimum(pos + NEAR + 1, len(idx))
        hit += int(((cs[hi] - cs[lo]) > 0).sum())
        tot += len(pos)
    return hit / tot * 100 if tot else None


def metrics(df, pred):
    y = df["y"].to_numpy()
    out = {"macro_f1": round(summarize(y, pred, NAMES)["macro_f1"] * 100, 2)}
    for side, cls in SIDES.items():
        n, true = int((pred == cls).sum()), int((y == cls).sum())
        hit = int(((pred == cls) & (y == cls)).sum())
        out[side] = {"訊號數": n, "命中率": round(hit / n * 100, 2) if n else None,
                     "找到率_精確": round(hit / true * 100, 2) if true else None,
                     "找到率_±2天": round(near_hit(df, pred, cls), 2), "隨機基準": round(true / len(y) * 100, 2)}
    return out


def main():
    t0 = time.time()
    data = ML.load_data(pool=POOL)
    panel, fc = ML.build_panel(data, 6, [])
    res = {"pool": POOL, "n_stocks": len(data), "train_min_amp": 0, "near_days": NEAR, "rules": RULES, "years": {}}
    for y in YEARS:
        res["years"][str(y)] = {}
        for name in SOURCES:
            sig, _ = WF.run_year(panel, fc, y, BY.SOURCE_FACTORIES[name]())
            df = sig.sort_values(["ticker", "date"]).reset_index(drop=True)
            res["years"][str(y)][name] = {r: metrics(df, apply_rule(df, r)) for r in RULES}
            a0 = res["years"][str(y)][name][RULES[0]]
            print(f"{y} {name} A0 macro-F1 {a0['macro_f1']}  ({time.time() - t0:.0f}s)", flush=True)
    avg = {}                                                    # 三年平均(逐年數字的平均)
    for name in SOURCES:
        avg[name] = {}
        for r in RULES:
            ys = [res["years"][str(y)][name][r] for y in YEARS]
            e = {"macro_f1": round(float(np.mean([v["macro_f1"] for v in ys])), 2)}
            for side in SIDES:
                e[side] = {k: (round(float(np.mean([v[side][k] for v in ys])), 2) if all(v[side][k] is not None for v in ys) else None)
                           for k in ys[0][side]}
            avg[name][r] = e
    res["三年平均"] = avg
    out = os.path.join(ML.OUT, f"postproc_signals_{POOL}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for name in SOURCES:
        print(f"\n== {name}(三年平均)==")
        for r in RULES:
            e = avg[name][r]
            print(f"{r:<26} F1 {e['macro_f1']:6.2f} | " + " | ".join(
                f"{s} 訊號 {e[s]['訊號數']:>9,.0f} 命中 {e[s]['命中率']:5.2f} 找到 {e[s]['找到率_精確']:5.2f} ±2 {e[s]['找到率_±2天']:5.2f}" for s in SIDES))
    print(out)


if __name__ == "__main__":
    main()
