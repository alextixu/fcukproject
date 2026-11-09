"""Stacking 邏輯迴歸的輸入與輸出:擷取真實數字當說明範例(2026-11-03 使用者要求;只擷取數字,不改研究程式)。

模型 = TW200(168 檔)、訓練門檻 0%、測試 2025、種子 42,與 backtest_long_only_tw200.json 2025 同一套
(WF.year_split(2025) → stacking.StackingSource("lr", "score").fit;A = 2021–2023、B = 2024)。
輸出:(1) B 的列數與三類個數、class_weight、StandardScaler(s_high、s_low)的 mean / std、三類的 coef 與 intercept;
      (2) 南電 8046 2025 的 4 個例子,逐步列出 s_high、s_low → 標準化 → z = coef · x + intercept → softmax 機率 → 判斷,
          手算機率與 model.predict_proba 核對。
挑例子:每一種(真實, 判斷)組合中,取「判斷那一類的機率」最接近該組中位數的那一天(= 該組最典型的一天)。
用法: python method_kline_peak/report/lr_example.py
輸出: results/lr_example_tw200_2025.json
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import stacking as S  # noqa: E402
from confusion import summarize  # noqa: E402
from feasibility import clean  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402
from paper_aeocsvm import NAMES  # noqa: E402

POOL, YEAR, TK = "tw200", 2025, "8046.TW"
CASES = [("a", "真低點,判低點(對)", UP, UP), ("b", "真高點,判高點(對)", DOWN, DOWN),
         ("c", "真非極值,判非極值(對)", FLAT, FLAT), ("d", "真非極值,判低點(錯)", FLAT, UP)]
R = lambda v: round(float(v), 4)  # noqa: E731


def main():
    data = ML.load_data(pool=POOL)
    panel, fc = ML.build_panel(data, 6, [])
    d = WF.year_split(panel, YEAR)
    src = S.StackingSource("lr", "score")
    src.fit(d["train"], fc)
    A, B = S.split_base_meta(d["train"])
    meta = src.meta
    lr, sc, cols = meta.model, meta.fsc, S.INPUTS["score"]
    yB = B["y"].to_numpy()
    cw = S.class_weight(yB)

    # 全部測試年的判斷:核對和回測同一套模型
    te = d["test"]
    pred_all, _ = meta.predict(src.base.transform(te))
    f1 = round(summarize(te["y"].to_numpy(), pred_all, NAMES)["macro_f1"] * 100, 2)

    order = [UP, FLAT, DOWN]                                      # 低點 / 非極值 / 高點
    k = {c: list(lr.classes_).index(c) for c in order}
    model = {
        "B_years": [int(B.date.dt.year.min()), int(B.date.dt.year.max())], "A_years": [int(A.date.dt.year.min()), int(A.date.dt.year.max())],
        "B_rows": int(len(B)), "B_class_counts": {NAMES[c]: int((yB == c).sum()) for c in order},
        "class_weight": {NAMES[c]: R(cw[c]) for c in order},
        "scaler": {c: {"mean": R(m), "std": R(s)} for c, m, s in zip(cols, sc.mean_, sc.scale_)},
        "coef": {NAMES[c]: {col: R(w) for col, w in zip(cols, lr.coef_[k[c]])} for c in order},
        "intercept": {NAMES[c]: R(lr.intercept_[k[c]]) for c in order},
        "test_macro_f1_pct": f1,
    }

    s = te[te.ticker == TK].reset_index(drop=True)
    F = src.base.transform(s)
    X = F[cols].to_numpy()
    Xs = sc.transform(X)
    z = Xs @ lr.coef_.T + lr.intercept_
    p = np.exp(z - z.max(1, keepdims=True))
    p /= p.sum(1, keepdims=True)
    pp = lr.predict_proba(Xs)
    pred = lr.classes_[pp.argmax(1)]
    close = clean(data[TK])["close"]
    cases, max_err = {}, float(np.abs(p - pp).max())
    for key, desc, yt, yp in CASES:
        idx = np.where((s["y"].to_numpy() == yt) & (pred == yp))[0]
        if not len(idx):
            cases[key] = {"說明": desc, "天數": 0}
            continue
        conf = pp[idx, k[yp]]
        i = int(idx[np.argmin(np.abs(conf - np.median(conf)))])
        day = s["date"].iloc[i]
        cases[key] = {
            "說明": desc, "這一組天數": int(len(idx)), "這一組判斷類機率中位數": R(np.median(conf)),
            "日期": str(day.date()), "收盤": round(float(close.loc[day]), 2),
            "s_high": R(X[i, 0]), "s_low": R(X[i, 1]), "標準化 s_high": R(Xs[i, 0]), "標準化 s_low": R(Xs[i, 1]),
            "z": {NAMES[c]: R(z[i, k[c]]) for c in order}, "機率": {NAMES[c]: R(p[i, k[c]]) for c in order},
            "判斷": NAMES[int(pred[i])], "分數": R(pp[i].max()), "真實": NAMES[int(s["y"].iloc[i])],
            "手算 vs predict_proba 最大誤差": float(np.abs(p[i] - pp[i]).max()),
        }
    res = {"pool": POOL, "n_stocks": len(data), "test_year": YEAR, "seed": S.SEED, "model": model,
           "ticker": TK, "ticker_days": int(len(s)), "手算 vs predict_proba 最大誤差(全年每天)": max_err,
           "與回測一致:南電這年判斷同 predict": bool((pred == meta.predict(F)[0]).all()), "cases": cases}
    out = os.path.join(ML.OUT, f"lr_example_{POOL}_{YEAR}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print(out)


if __name__ == "__main__":
    main()
