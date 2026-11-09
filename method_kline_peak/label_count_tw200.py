"""TW200(剔除低波動後 168 檔)各訓練門檻下的標籤數量(2026-11-02 使用者要求;只建 panel、數標籤,不訓練)。

幅度 = paper_aeocsvm.label_amp(兩邊較小那邊,%);門檻 0%、1%、…、15%。
每個測試年 Y(2023–2026)數「幅度 ≥ 門檻」的高點、低點:
  主軸訓練期 = walkforward.year_split(Y) 的訓練期(Y-4 ~ Y-1,剔除最後 5 個交易日,同 run_year)
  Stacking A / B = stacking.split_base_meta(主軸訓練期)(A = 前 3 年、最後 5 天剔除;B = 第 4 年)
  測試年 = Y 整年(原本的真高點 / 真低點裡,幅度 ≥ 門檻的個數)
「每類最少訓練點」= 每個門檻下,4 個年份 × 3 個訓練窗 × 高 / 低兩類裡最小的數字(另列各訓練窗自己的最小值)。
用法: python method_kline_peak/label_count_tw200.py
輸出: results/label_count_tw200.json
"""
import json
import os

import mainline as ML
import walkforward as WF
from learn5_trade6 import UP, DOWN
from stacking import split_base_meta

POOL = "tw200"
YEARS = (2023, 2024, 2025, 2026)
THRESHOLDS = list(range(16))


def count(df, th):
    """幅度 ≥ th 的 高點數、低點數(th = 0 時就是全部高點 / 低點)。"""
    ok = df["amp"] >= th
    return {"高點": int(((df["y"] == DOWN) & ok).sum()), "低點": int(((df["y"] == UP) & ok).sum())}


def main():
    data = ML.load_data(pool=POOL)
    panel, _ = ML.build_panel(data, 6, [])
    windows = {}
    for y in YEARS:
        d = WF.year_split(panel, y)
        A, B = split_base_meta(d["train"])
        windows[y] = {"主軸": d["train"], "Stacking A": A, "Stacking B": B, "測試": d["test"]}
    res = {"pool": POOL, "n_stocks": len(data),
           "windows": {str(y): {k: [str(v.date.min().date()), str(v.date.max().date())] for k, v in w.items()} for y, w in windows.items()},
           "thresholds": {}}
    for th in THRESHOLDS:
        r = {str(y): {k: count(v, th) for k, v in w.items()} for y, w in windows.items()}
        train_keys = ("主軸", "Stacking A", "Stacking B")
        r["每類最少訓練點"] = min(r[str(y)][k][c] for y in YEARS for k in train_keys for c in ("高點", "低點"))
        r["各訓練窗最少"] = {k: min(r[str(y)][k][c] for y in YEARS for c in ("高點", "低點")) for k in train_keys}
        res["thresholds"][str(th)] = r
    out = os.path.join(ML.OUT, "label_count_tw200.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"{len(data)} 檔;訓練窗:{res['windows']}")
    print("門檻 | 最少 | 主軸最少 | A 最少 | B 最少 | " + " | ".join(f"{y} B 高/低" for y in YEARS) + " | " + " | ".join(f"{y} 測試 高/低" for y in YEARS))
    for th, r in res["thresholds"].items():
        m = r["各訓練窗最少"]
        print(f"{th}% | {r['每類最少訓練點']} | {m['主軸']} | {m['Stacking A']} | {m['Stacking B']} | "
              + " | ".join(f"{r[str(y)]['Stacking B']['高點']}/{r[str(y)]['Stacking B']['低點']}" for y in YEARS) + " | "
              + " | ".join(f"{r[str(y)]['測試']['高點']}/{r[str(y)]['測試']['低點']}" for y in YEARS))
    print(out)


if __name__ == "__main__":
    main()
