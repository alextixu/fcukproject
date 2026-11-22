"""4 種走勢代表股 2024 × 四組(29 維 / 2 日 K × 主軸 / Stacking)總表(2026-11-22 使用者要求)。

讀 feat2day_4way.py 存的每日判斷(results/feat2day_<代號>_2024_tw200_4way_daily.csv;168 檔一起 walk-forward 再取出單檔),
每檔 × 每組算:判低 / 判高的天數、對、錯、命中率;真低 / 真高的當天找到率與 ±2 天找到率;單檔三分類 macro-F1;判反次數。
並和各檔 _4way.json 的數字核對。
用法: python method_kline_peak/report/feat2day_summary.py
輸出: results/feat2day_4stocks_2024_summary.json
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mainline as ML  # noqa: E402
import compare_postproc as CP  # noqa: E402
import feat2day_4way as F4  # noqa: E402
from confusion import summarize  # noqa: E402
from export_windows import ticker_names  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402
from paper_aeocsvm import NAMES  # noqa: E402

STOCKS = [("大漲趨勢", "1519.TW"), ("大起大落", "3661.TW"), ("下跌趨勢", "2388.TW"), ("高低點最多", "3653.TW")]


def main():
    names = ticker_names()
    res = {"year": F4.YEAR, "pool": F4.POOL, "stocks": {}}
    for trend, tk in STOCKS:
        d = pd.read_csv(os.path.join(ML.OUT, f"feat2day_{tk[:4]}_{F4.YEAR}_{F4.POOL}_4way_daily.csv"))
        ref = json.load(open(os.path.join(ML.OUT, f"feat2day_{tk[:4]}_{F4.YEAR}_{F4.POOL}_4way.json"), encoding="utf-8"))["groups"]
        y = d["y"].to_numpy()
        out = {"走勢": trend, "名稱": names.get(tk, tk), "真低點": int((y == UP).sum()), "真高點": int((y == DOWN).sum()), "groups": {}}
        for title, f, m in F4.GROUPS:
            p = d[f"{f}|{m}"].to_numpy()
            c = CP.counts(y, p)
            swap = int(((p == UP) & (y == DOWN)).sum() + ((p == DOWN) & (y == UP)).sum())
            assert {**c, "高低點判反": swap} == {k: v for k, v in ref[title].items() if k not in ("features", "method")}, (tk, title)
            g = {"macro_f1": round(summarize(y, p, NAMES)["macro_f1"] * 100, 2), "高低點判反": swap}
            for side in ("低點", "高點"):
                s = c[side]
                g[side] = {"判": s["判"], "對": s["對"], "錯": s["錯"], "命中率": s["命中率"],
                           "找到率_當天": round(s["當天抓到"] / s["真"] * 100, 1), "找到率_±2天": round(s["±2 天抓到"] / s["真"] * 100, 1)}
            out["groups"][title] = g
        out["macro_f1_最高"] = max(out["groups"], key=lambda t: out["groups"][t]["macro_f1"])
        res["stocks"][tk] = out
    with open(os.path.join(ML.OUT, f"feat2day_4stocks_{F4.YEAR}_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, default=float)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
