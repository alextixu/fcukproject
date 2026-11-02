"""用幅度門檻訓練、用原本的標籤對答案(2026-11-02 使用者要求)。

訓練:兩邊幅度 ≥ 3% 的點才當高點 / 低點,其餘改成非極值(主軸的 OC-SVM、Stacking 的基底層與元學習器都一樣)。
對答案:測試期用原本的標籤(只要是 11 天的最高 / 最低就算對)。
兩個方法(主軸、Stacking 邏輯迴歸)× 測試 2024、2025、2026;對照目前的 0%(不設門檻)。
用法: python method_kline_peak/amp_train_eval.py [--min-amp 3]
輸出: results/amp_train_eval.json
"""
import argparse
import json
import os
import time

import mainline as ML
import walkforward as WF
import backtest_years as BY
from confusion import summarize
from paper_aeocsvm import NAMES

YEARS = (2024, 2025, 2026)
SOURCES = ["主軸", "Stacking 邏輯迴歸"]
KEY = "confusion_rows_true_cols_pred(漲,不漲不跌,跌)"


def metrics(sig):
    s = summarize(sig.y.to_numpy(), sig.pred.to_numpy(), NAMES)
    return {"macro_f1_pct": round(s["macro_f1"] * 100, 2),
            "recall_pct": {k: round(s["recall"][k] * 100, 1) for k in ("高點", "低點")},
            "precision_pct": {k: round((s["precision"][k] or 0) * 100, 1) for k in ("高點", "低點")},
            "n_pred": {"高點": int((sig.pred == 2).sum()), "低點": int((sig.pred == 1).sum())}, KEY: s[KEY]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-amp", type=float, default=3.0)
    th = ap.parse_args().min_amp
    t0 = time.time()
    data = ML.load_data()
    panel, fc = ML.build_panel(data, 6, [])
    res = {"train_min_amp": [0.0, th], "years": {}}
    for y in YEARS:
        res["years"][str(y)] = {}
        for name in SOURCES:
            row = {}
            for amp in (0.0, th):
                sig, _ = WF.run_year(panel, fc, y, BY.SOURCE_FACTORIES[name](), train_min_amp=amp)
                row[f"{amp:g}%"] = metrics(sig)
            res["years"][str(y)][name] = row
            a, b = row["0%"], row[f"{th:g}%"]
            print(f"{y} {name:<12} macro-F1 {a['macro_f1_pct']:.2f} → {b['macro_f1_pct']:.2f}"
                  f"  找到 高/低 {a['recall_pct']['高點']}/{a['recall_pct']['低點']} → {b['recall_pct']['高點']}/{b['recall_pct']['低點']}"
                  f"  命中 高/低 {a['precision_pct']['高點']}/{a['precision_pct']['低點']} → {b['precision_pct']['高點']}/{b['precision_pct']['低點']}"
                  f"  判幾個 高/低 {a['n_pred']['高點']}/{a['n_pred']['低點']} → {b['n_pred']['高點']}/{b['n_pred']['低點']}  ({time.time() - t0:.0f}s)", flush=True)
    out = os.path.join(ML.OUT, "amp_train_eval.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"記錄於 {out}")


if __name__ == "__main__":
    main()
