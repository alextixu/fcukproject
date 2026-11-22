"""4 種走勢代表股 2024 × 四組(29 維 / 2 日 K × 主軸 / Stacking)總表(2026-11-22 使用者要求)。

讀 feat2day_4way.py 存的每日判斷(results/feat2day_<代號>_2024_tw200_4way_daily.csv;168 檔一起 walk-forward 再取出單檔),
每檔 × 每組算:判低 / 判高的天數、對、錯、命中率;真低 / 真高的當天找到率與 ±2 天找到率;單檔三分類 macro-F1;判反次數。
並和各檔 _4way.json 的數字核對。
多年(--years 2024 2025 2026):逐年 + 三年合計(三年判斷合併後重算 macro-F1、命中率、找到率)。
用法: python method_kline_peak/report/feat2day_summary.py [--years 2024 2025 2026]
輸出: results/feat2day_4stocks_2024_summary.json(預設)或 results/feat2day_4stocks_2024_2026_summary.json
"""
import argparse
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


def group_stats(y, p):
    c = CP.counts(y, p)
    swap = int(((p == UP) & (y == DOWN)).sum() + ((p == DOWN) & (y == UP)).sum())
    g = {"macro_f1": round(summarize(y, p, NAMES)["macro_f1"] * 100, 2), "高低點判反": swap}
    for side in ("低點", "高點"):
        s = c[side]
        g[side] = {"判": s["判"], "對": s["對"], "錯": s["錯"], "命中率": s["命中率"],
                   "找到率_當天": round(s["當天抓到"] / s["真"] * 100, 1), "找到率_±2天": round(s["±2 天抓到"] / s["真"] * 100, 1)}
    return c, g


def one_year(year, names):
    out_all = {}
    for trend, tk in STOCKS:
        d = pd.read_csv(os.path.join(ML.OUT, f"feat2day_{tk[:4]}_{year}_{F4.POOL}_4way_daily.csv"))
        ref = json.load(open(os.path.join(ML.OUT, f"feat2day_{tk[:4]}_{year}_{F4.POOL}_4way.json"), encoding="utf-8"))["groups"]
        y = d["y"].to_numpy()
        out = {"走勢": trend, "名稱": names.get(tk, tk), "真低點": int((y == UP).sum()), "真高點": int((y == DOWN).sum()), "groups": {}}
        for title, f, m in F4.GROUPS:
            c, g = group_stats(y, d[f"{f}|{m}"].to_numpy())
            assert {**c, "高低點判反": g["高低點判反"]} == {k: v for k, v in ref[title].items() if k not in ("features", "method")}, (tk, title)
            out["groups"][title] = g
        out["macro_f1_最高"] = max(out["groups"], key=lambda t: out["groups"][t]["macro_f1"])
        out_all[tk] = (out, d)
    return out_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="+", default=[2024])
    years = ap.parse_args().years
    names = ticker_names()
    per = {y: one_year(y, names) for y in years}
    if years == [2024]:                                                   # 2024 單年(原本的輸出,格式不變)
        res = {"year": 2024, "pool": F4.POOL, "stocks": {tk: o for tk, (o, _) in per[2024].items()}}
        out = os.path.join(ML.OUT, f"feat2day_4stocks_{F4.YEAR}_summary.json")
    else:                                                                 # 多年:逐年 + 合計(各年判斷合併後重算)
        res = {"years": years, "pool": F4.POOL, "stocks": {}}
        for trend, tk in STOCKS:
            e = {"走勢": trend, "名稱": names.get(tk, tk), "逐年": {str(y): per[y][tk][0] for y in years}, "合計": {"groups": {}}}
            d = pd.concat([per[y][tk][1] for y in years], ignore_index=True)
            yy = d["y"].to_numpy()
            e["合計"].update({"真低點": int((yy == UP).sum()), "真高點": int((yy == DOWN).sum())})
            for title, f, m in F4.GROUPS:
                e["合計"]["groups"][title] = group_stats(yy, d[f"{f}|{m}"].to_numpy())[1]
            g = e["合計"]["groups"]
            e["合計"]["macro_f1_最高"] = max(g, key=lambda t: g[t]["macro_f1"])
            res["stocks"][tk] = e
        res["合計_最高組_檔數"] = {t: sum(res["stocks"][tk]["合計"]["macro_f1_最高"] == t for _, tk in STOCKS) for t, _, _ in F4.GROUPS}
        out = os.path.join(ML.OUT, f"feat2day_4stocks_{years[0]}_{years[-1]}_summary.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, default=float)
    print(out)

if __name__ == "__main__":
    main()
