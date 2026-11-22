"""主軸實測時間與記憶體(不改模型)。

1. 訓練:168 檔、walk-forward 測 2026 的模型(訓練 2022–2025),計時 MainlineSource.fit(高、低各一組 AE + OC-SVM)。
2. 一天的判斷:已訓練好的模型,對 168 檔做 2026 年最後一個有完整標籤的交易日(2026-09-03,可和 walk-forward 核對)的判斷,包含
   每檔取最後 30 根 K → 29 維特徵 + 規則候選 → 標準化 → AE 編碼 → OC-SVM;跑 5 次取中位數。
   結果和 walk-forward 的判斷(backtest_strategies 快取)逐檔核對。
3. 記憶體:訓練行程的 RSS 峰值;另開一個只做判斷的行程(讀價格 + 載入模型 + 判斷)量 RSS 峰值。
用法: python method_kline_peak/report/timing_mainline.py
輸出: results/timing_mainline.json
"""
import json
import os
import pickle
import platform
import statistics
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import torch

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import backtest_strategies as BS  # noqa: E402
from feasibility import clean  # noqa: E402
from paper_aeocsvm import paper_label  # noqa: E402

YEAR, REPS, TAIL = 2026, 5, 30
OUT = os.path.join(ML.OUT, "timing_mainline.json")


def rss_mb():
    """本行程的 RSS 峰值(/proc/self/status 的 VmHWM;exec 後重新計算,不會繼承父行程)。"""
    for line in open("/proc/self/status"):
        if line.startswith("VmHWM:"):
            return round(int(line.split()[1]) / 1024, 1)


def one_day(src, data, fc, day, clock=None):
    """168 檔在 day 這一天的判斷(只用到 day 為止的最後 TAIL 根 K)。clock:list,有給的話記下(特徵秒數, 模型秒數)。"""
    t0 = time.perf_counter()
    rows = []
    for tk, df in data.items():
        d = clean(df.loc[:day].tail(TAIL))
        if d.index[-1] != pd.Timestamp(day):
            continue
        f = ML.shape_features(d, 6).iloc[[-1]]
        _, hi, lo = paper_label(d["close"])
        rows.append(f.assign(cand_hi=bool(hi.iloc[-1]), cand_lo=bool(lo.iloc[-1]), ticker=tk, date=d.index[-1]))
    x = pd.concat(rows, ignore_index=True)[["date", "ticker", "cand_hi", "cand_lo", *fc]]
    t1 = time.perf_counter()
    out = src.predict(x)
    if clock is not None:
        clock.append((t1 - t0, time.perf_counter() - t1))
    return out


def infer_only(model_path):
    """另一個行程:讀價格 + 載入模型 + 判斷一天,回報 RSS 峰值。"""
    t0 = time.perf_counter()
    data = ML.load_data(pool=BS.POOL)
    src, fc, day = pickle.load(open(model_path, "rb"))
    out = one_day(src, data, fc, day)
    print(json.dumps({"rss_peak_mb": rss_mb(), "seconds_total": round(time.perf_counter() - t0, 2), "n": len(out)}))


def cpu_name():
    for line in open("/proc/cpuinfo"):
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor()


def main():
    data = ML.load_data(pool=BS.POOL)
    panel, fc = ML.build_panel(data, 6, [])
    d = WF.year_split(panel, YEAR)
    src = WF.MainlineSource()
    t0 = time.perf_counter()
    src.fit(d["train"], fc)
    train_s = time.perf_counter() - t0
    rss_train = rss_mb()

    sig = BS.load_signals((YEAR,), data)
    day = sig["date"].max()
    times, parts, out = [], [], None
    for _ in range(REPS):
        t0 = time.perf_counter()
        out = one_day(src, data, fc, day, parts)
        times.append(time.perf_counter() - t0)
    ref = sig[sig.date == day].set_index("ticker")
    got = out.set_index("ticker")
    same = bool((ref.loc[got.index, "pred"].to_numpy() == got["pred"].to_numpy()).all())
    assert same and len(got) == len(ref), "一天的判斷 ≠ walk-forward 的判斷"

    scratch = os.environ.get("TMPDIR", "/tmp")
    path = os.path.join(scratch, "mainline_timing_model.pkl")
    pickle.dump((src, fc, day), open(path, "wb"))
    sub = json.loads(subprocess.run([sys.executable, __file__, "--infer-only", path], capture_output=True, text=True,
                                    check=True).stdout.strip().splitlines()[-1])
    os.remove(path)

    med = statistics.median(times)
    res = {"環境": {"cpu": cpu_name(), "邏輯核心數": os.cpu_count(), "torch_threads": torch.get_num_threads(),
                  "python": platform.python_version(), "torch": torch.__version__},
           "股票數": len(data),
           "訓練": {"測試年": YEAR, "訓練期": f"{YEAR - 4}–{YEAR - 1}", "訓練樣本數(股票日)": int(len(d["train"])),
                  "秒": round(train_s, 1), "說明": "MainlineSource.fit:高、低各一組(相似樣本權重 + AE 60 輪 + OC-SVM),不含讀資料與建特徵表"},
           "一天的判斷": {"日期": str(day.date()), "檔數": int(len(got)), "重複": REPS, "每次秒數": [round(t, 3) for t in times],
                      "中位數_秒": round(med, 3), "平均每檔_毫秒": round(med / len(got) * 1000, 2),
                      "其中_特徵與規則候選_中位數_秒": round(statistics.median(a for a, _ in parts), 3),
                      "其中_標準化AE與OCSVM_中位數_秒": round(statistics.median(b for _, b in parts), 3),
                      "判高點": int((got.pred == 2).sum()), "判低點": int((got.pred == 1).sum()), "和 walk-forward 判斷相同": same,
                      "說明": "已訓練好的模型;每檔取最後 30 根 K 算 29 維特徵與規則候選 → 標準化 → AE → OC-SVM;不含讀價格檔"},
           "記憶體_RSS峰值_MB": {"訓練行程(讀 168 檔 + 建特徵表 + 訓練)": rss_train,
                             "只做判斷的行程(讀 168 檔價格 + 載入模型 + 判斷一天)": sub["rss_peak_mb"]},
           "只做判斷的行程_總秒數(含讀價格與載入套件後的模型)": sub["seconds_total"]}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--infer-only":
        infer_only(sys.argv[2])
    else:
        main()
