"""主軸每檔股票的成績與排名(不改模型:把 168 檔 walk-forward 2024 / 2025 / 2026 的每日判斷按股票拆開統計)。

判斷取自 backtest_strategies 的每日判斷快取(每年的混淆矩陣先核對 confusion_2024_2026_tw200.json),
並核對 168 檔逐檔混淆矩陣加總 = confusion_2024_2026_tw200.json。
每檔 × 每年、以及三年合計:
  真高點 / 真低點數;判高 / 判低的天數、對、錯;高 / 低當天找到率、±2 天找到率(真點前後 2 個交易日內有同方向判斷);
  高 / 低命中率;單檔 macro-F1(三類);判反次數;該期間漲跌幅(前一年最後收盤 → 期末收盤)、年化波動(日報酬標準差 × √252)。
排名(單年與三年合計各一份):
  (a) 當天找到的真高點 + 真低點個數最多  (b) 找到率(高低平均)最高  (c) 命中率(高低平均)最高  (d) macro-F1 最高
  (b)(c) 只列真高點、真低點各至少 12 個的股票。
用法: python method_kline_peak/report/per_stock_rank.py
輸出: results/per_stock_mainline_2024_2026.json
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mainline as ML  # noqa: E402
import backtest_strategies as BS  # noqa: E402
from confusion import summarize  # noqa: E402
from feasibility import clean  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402
from paper_aeocsvm import NAMES  # noqa: E402
from stock_outputs import ticker_names  # noqa: E402

YEARS = (2024, 2025, 2026)
MIN_TRUE = 12
TOP = 10
KEY = BS.KEY
OUT = os.path.join(ML.OUT, "per_stock_mainline_2024_2026.json")


def near(y, p, cls, k=2):
    """真 cls 點中,前後 k 個交易日內有判 cls 的個數。"""
    on = np.flatnonzero(p == cls)
    return int(sum(np.any(np.abs(on - i) <= k) for i in np.flatnonzero(y == cls))) if len(on) else 0


def side(y, p, cls, n2):
    n_true, n_pred = int((y == cls).sum()), int((p == cls).sum())
    hit = int(((p == cls) & (y == cls)).sum())
    pct = lambda a, b: round(a / b * 100, 1) if b else None   # noqa: E731
    return {"真": n_true, "判": n_pred, "對": hit, "錯": n_pred - hit, "找到率_當天": pct(hit, n_true),
            "找到率_±2天": pct(n2, n_true), "命中率": pct(hit, n_pred)}


def market(close, start, end):
    prev = close.loc[:pd.Timestamp(start) - pd.Timedelta(days=1)]
    c = close.loc[start:end]
    base = prev.iloc[-1] if len(prev) else c.iloc[0]
    return {"漲跌幅_pct": round((c.iloc[-1] / base - 1) * 100, 1),
            "年化波動_pct": round(float(c.pct_change().std() * np.sqrt(252) * 100), 1)}


def stats(parts, close, start, end):
    """parts:[(y, p)](每年一段,±2 天在各年內算)。"""
    y, p = np.concatenate([a for a, _ in parts]), np.concatenate([b for _, b in parts])
    s = summarize(y, p, NAMES)
    r = {"高點": side(y, p, DOWN, sum(near(a, b, DOWN) for a, b in parts)),
         "低點": side(y, p, UP, sum(near(a, b, UP) for a, b in parts)),
         "macro_f1": round(s["macro_f1"] * 100, 2),
         "判反": int(((p == UP) & (y == DOWN)).sum() + ((p == DOWN) & (y == UP)).sum()),
         **market(close, start, end), "_cm": s[KEY]}
    h, lo = r["高點"], r["低點"]
    r["找到個數_高加低"] = h["對"] + lo["對"]
    r["找到率_平均"] = round((h["找到率_當天"] + lo["找到率_當天"]) / 2, 1) if h["真"] and lo["真"] else None
    r["命中率_平均"] = round(((h["命中率"] or 0) + (lo["命中率"] or 0)) / 2, 1) if h["真"] and lo["真"] else None
    return r


def ranking(rows, names):
    """rows:{代號: stats}。"""
    ok = {tk: r for tk, r in rows.items() if r["高點"]["真"] >= MIN_TRUE and r["低點"]["真"] >= MIN_TRUE}

    def top(src, key):
        order = sorted(src, key=lambda tk: (-(src[tk][key] if src[tk][key] is not None else -1), tk))[:TOP]
        return [{"代號": tk, "名稱": names.get(tk, tk), key: src[tk][key], "找到率_平均": src[tk]["找到率_平均"],
                 "命中率_平均": src[tk]["命中率_平均"], "macro_f1": src[tk]["macro_f1"], "真高點": src[tk]["高點"]["真"],
                 "真低點": src[tk]["低點"]["真"], "漲跌幅_pct": src[tk]["漲跌幅_pct"], "年化波動_pct": src[tk]["年化波動_pct"]}
                for tk in order]
    return {"a_找到個數": top(rows, "找到個數_高加低"), "b_找到率": top(ok, "找到率_平均"),
            "c_命中率": top(ok, "命中率_平均"), "d_macro_f1": top(rows, "macro_f1")}


def main():
    data = ML.load_data(pool=BS.POOL)
    sig = BS.load_signals(YEARS, data)
    ref = json.load(open(os.path.join(ML.OUT, "confusion_2024_2026_tw200.json"), encoding="utf-8"))
    names = ticker_names()
    close = {tk: clean(df)["close"] for tk, df in data.items()}
    per = {str(y): {} for y in YEARS}
    parts = {tk: [] for tk in data}
    for y in YEARS:
        s = sig[sig.date.dt.year == y]
        total = np.zeros((3, 3), int)
        for tk, g in s.sort_values("date").groupby("ticker"):
            yy, pp = g["y"].to_numpy(), g["pred"].to_numpy()
            per[str(y)][tk] = stats([(yy, pp)], close[tk], f"{y}-01-01", g["date"].max())
            total += np.array(per[str(y)][tk]["_cm"])
            parts[tk].append((yy, pp))
        assert total.tolist() == ref[str(y)]["主軸"][KEY], y                 # 逐檔加總 = 168 檔的混淆矩陣
    end = sig["date"].max()
    per["合計"] = {tk: stats(v, close[tk], f"{YEARS[0]}-01-01", end) for tk, v in parts.items() if v}
    res = {"pool": BS.POOL, "n_stocks": len(data), "years": list(YEARS), "min_true_for_b_c": MIN_TRUE, "核對_混淆矩陣加總": True,
           "排名": {k: ranking(v, names) for k, v in per.items()},
           "每檔": {k: {tk: {"名稱": names.get(tk, tk), **{a: b for a, b in r.items() if a != "_cm"}} for tk, r in v.items()}
                  for k, v in per.items()}}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for k, rk in res["排名"].items():
        for name, rows in rk.items():
            print(k, name, [(r["代號"][:4], r["名稱"], r[list(r)[2]]) for r in rows])
    print(OUT)


if __name__ == "__main__":
    main()
