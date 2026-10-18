"""11 日窗格:學第 1–5 天、第 6 天交易、看第 11 天比第 6 天高還是低(漲 / 跌 / 不漲不跌)。

使用者設計(2026-10-18):
  輸入  = 第 1–5 天五根 K(第 5 天收盤時全部已知)
  交易  = 第 6 天開盤進場
  結果  = 第 11 天收盤相對第 6 天開盤:r = C[11] / O[6] - 1
  三分類(兩種「不漲不跌」帶寬,都在第 5 天收盤就能算出)
    pct3  漲 r > +3%、跌 r < -3%,其餘不漲不跌
    sig1  漲 r > +σ20×√6、跌 r < -σ20×√6(σ20 = 第 5 天為止 20 日日報酬標準差,依各股波動調整)
  目標  = 只要最有把握的少數挑得出「必漲 / 必跌」,大部分判成不漲不跌沒關係 → 評估高分尾端

輸入特徵 raw5:五根 K 的 O/H/L/C(相對第 5 天收盤的 log 價)+ 量(相對 20 日均量的 log 比),24 維
分數
  lgb    LightGBM 三分類(不加類別權重,3 seeds 機率平均),P(漲) / P(跌)
  knn    形態搜尋:五根 K 最相似的 50 個歷史樣本中漲(跌)的比例
  反轉   第 1–5 天跌最多 → 漲、漲最多 → 跌(不學任何東西;反過來的「動能」就是同一批股票、方向相反)
兩個測試段各自往前訓練:2022–2023(含 2022 空頭)、2025-01 ~ 2026-09(多頭)。
尾端:各分數取前 0.1% / 0.5% / 1% / 5%,算標籤命中、方向命中(第 11 天收 vs 第 6 天開,Wilson 95% CI)、
      平均報酬、扣 0.42% 成本(跌以放空計)、涉及幾個不同日期。
注意:相鄰日的樣本持有期重疊,同檔連續幾天被挑中並非獨立,CI 偏窄。

用法: python method_kline_peak/learn5_trade6.py --pool tw50
輸出: method_kline_peak/results/learn5_<pool>.json
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from feasibility import START, END, COST, load_pool, clean  # noqa: E402
from tail_precision import FOLDS, QS, KNN_K, lgb_proba, wilson  # noqa: E402
from peak_labels import OTHER, TOP, BOTTOM, label_window  # noqa: E402

OUT = os.path.join(HERE, "results")
N_IN, HOLD = 5, 6                  # 輸入第 1–5 天;持有第 6 天開 → 第 11 天收
FLAT, UP, DOWN = 0, 1, 2
NAMES = {FLAT: "不漲不跌", UP: "漲", DOWN: "跌"}
LABELS = ("pct3", "sig1")
RAW5 = [f"{p}{k}" for k in range(N_IN) for p in "ohlcv" if not (p == "c" and k == 0)]


def build_panel(data):
    parts = []
    for tk, df in data.items():
        df = clean(df)
        O, H, L, C, V = (df[k] for k in ("open", "high", "low", "close", "volume"))
        lc = np.log(C)
        v20 = V.rolling(20, min_periods=20).mean()
        f = {}
        for k in range(N_IN):                       # k = 0 第 5 天 … 4 第 1 天
            f[f"o{k}"] = np.log(O.shift(k)) - lc
            f[f"h{k}"] = np.log(H.shift(k)) - lc
            f[f"l{k}"] = np.log(L.shift(k)) - lc
            if k:
                f[f"c{k}"] = np.log(C.shift(k)) - lc
            f[f"v{k}"] = np.log(V.shift(k) / v20)
        part = pd.DataFrame(f, index=df.index)
        part["ret_win"] = lc - np.log(O.shift(N_IN - 1))           # 第 1 天開 → 第 5 天收
        part["sig20"] = lc.diff().rolling(20, min_periods=20).std()
        part["fwd"] = C.shift(-HOLD) / O.shift(-1) - 1              # 第 6 天開 → 第 11 天收
        # 形態版標籤(confusion.py --labels peak 用):第 6 天是 11 日最高點 → 跌、最低點 → 漲、其餘不漲不跌
        peak = label_window(df, "hl")["label"].shift(-1)            # 中心日 = 第 6 天 = 第 5 天 + 1
        part["y_peak"] = peak.map({OTHER: FLAT, TOP: DOWN, BOTTOM: UP}).fillna(-1).astype(int)  # 頂底同日 → -1
        part["ticker"] = tk
        part.index.name = "date"
        parts.append(part.reset_index())
    panel = pd.concat(parts, ignore_index=True).replace([np.inf, -np.inf], np.nan)
    panel = panel[panel[RAW5 + ["ret_win", "sig20", "fwd"]].notna().all(axis=1) & (panel["date"] >= START)]
    panel = panel.reset_index(drop=True)
    bands = {"pct3": 0.03, "sig1": panel["sig20"] * np.sqrt(HOLD)}
    for name, band in bands.items():
        y = np.full(len(panel), FLAT)
        y[panel["fwd"] > band] = UP
        y[panel["fwd"] < -band] = DOWN
        panel[f"y_{name}"] = y
    return panel


def split(panel, fold):
    cal = np.sort(panel["date"].unique())
    purge = []
    for name in ("val", "test"):
        i = np.searchsorted(cal, np.datetime64(fold[name][0]))
        purge.extend(cal[max(0, i - HOLD):i])        # 報酬看到第 5 天 + 6,跨進下一段的樣本丟掉
    keep = ~panel["date"].isin(purge)
    return {k: panel[keep & (panel["date"] >= a) & (panel["date"] <= b)].reset_index(drop=True)
            for k, (a, b) in fold.items()}


def knn_proba(fit_df, te, ycol):
    sc = StandardScaler().fit(fit_df[RAW5])
    knn = KNeighborsClassifier(n_neighbors=KNN_K, n_jobs=4).fit(sc.transform(fit_df[RAW5]), fit_df[ycol])
    return knn.predict_proba(sc.transform(te[RAW5]))     # 欄位順序 = classes_ = [0, 1, 2]


def tail_table(te, score, side, ycol):
    y, fwd, dates = te[ycol].to_numpy(), te["fwd"].to_numpy(), te["date"].to_numpy()
    good = fwd > 0 if side == UP else fwd < 0
    sign = 1 if side == UP else -1
    order = np.argsort(-score, kind="stable")
    rows = {}
    for q in QS:
        idx = order[:max(1, int(round(len(te) * q)))]
        n, k = len(idx), int(good[idx].sum())
        vc = pd.Series(dates[idx]).value_counts(normalize=True)
        rows[f"{q:.1%}"] = {
            "n": n, "n_dates": int(len(vc)), "top_date_share": float(vc.iloc[0]),
            "label_prec": float((y[idx] == side).mean()),
            "dir_hit": k / n, "dir_hit_ci": wilson(k, n),
            "ret_pct": float(fwd[idx].mean() * 100),
            "net_pct": float((sign * fwd[idx] - COST).mean() * 100),
        }
    return rows


def run(panel, fold, label):
    ycol = f"y_{label}"
    sp = {k: d.assign(y=d[ycol]) for k, d in split(panel, fold).items()}
    tr, va, te = sp["train"], sp["val"], sp["test"]
    scores = {"lgb": lgb_proba(tr, va, te, RAW5), "knn": knn_proba(pd.concat([tr, va]), te, "y")}
    rw = te["ret_win"].to_numpy()
    scores["反轉"] = np.column_stack([np.zeros(len(te)), -rw, rw])
    fwd = te["fwd"].to_numpy()
    res = {"n_split": {k: len(d) for k, d in sp.items()},
           "label_dist_test": {NAMES[c]: float((te[ycol] == c).mean()) for c in (UP, FLAT, DOWN)},
           "base": {"漲_rate": float((fwd > 0).mean()), "跌_rate": float((fwd < 0).mean()),
                    "ret_pct": float(fwd.mean() * 100)},
           "models": {}}
    for m, pr in scores.items():
        res["models"][m] = {"漲": tail_table(te, pr[:, UP], UP, ycol), "跌": tail_table(te, pr[:, DOWN], DOWN, ycol)}
    return res


def show(fold_name, label, res):
    b, d = res["base"], res["label_dist_test"]
    print(f"\n== 測試段 {fold_name} / 標籤 {label}  test n={res['n_split']['test']:,}  "
          f"標籤 漲 {d['漲']:.1%} 平 {d['不漲不跌']:.1%} 跌 {d['跌']:.1%}  "
          f"| 第11收>第6開 {b['漲_rate']:.1%}  平均 {b['ret_pct']:+.2f}%")
    for side in ("漲", "跌"):
        print(f"  {side}    前%     n  日期數 最多同日  標籤命中  方向對 [95% CI]      報酬   扣成本")
        for m, t in res["models"].items():
            if label != LABELS[0] and m == "反轉":
                continue                                  # 不依標籤,只在第一種標籤列一次
            for q, r in t[side].items():
                ci = r["dir_hit_ci"]
                print(f"    {m:<4} {q:>5} {r['n']:>5} {r['n_dates']:>6} {r['top_date_share']:>7.0%}  "
                      f"{r['label_prec']:>7.1%}  {r['dir_hit']:>6.1%} [{ci[0]:.0%}, {ci[1]:.0%}]  "
                      f"{r['ret_pct']:>+6.2f}%  {r['net_pct']:>+6.2f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="tw50")
    args = ap.parse_args()
    t0 = time.time()
    panel = build_panel(load_pool(args.pool, START, END))
    print(f"[DATA] {args.pool}: panel {panel.shape}  ({time.time() - t0:.0f}s)")
    for label in LABELS:
        y = panel[f"y_{label}"]
        by_year = panel.groupby(panel["date"].dt.year)[f"y_{label}"].agg(
            lambda s: f"{(s == UP).mean():.0%}/{(s == FLAT).mean():.0%}/{(s == DOWN).mean():.0%}")
        print(f"  {label} 全期 漲 {(y == UP).mean():.1%} 平 {(y == FLAT).mean():.1%} 跌 {(y == DOWN).mean():.1%}"
              f"  逐年(漲/平/跌) " + " ".join(f"{k}:{v}" for k, v in by_year.items()), flush=True)

    out = {"pool": args.pool, "folds": FOLDS, "quantiles": QS, "results": {}}
    for fold_name, fold in FOLDS.items():
        for label in LABELS:
            res = run(panel, fold, label)
            out["results"][f"{fold_name}|{label}"] = res
            show(fold_name, label, res)
            print(f"  ({time.time() - t0:.0f}s)", flush=True)
    fp = os.path.join(OUT, f"learn5_{args.pool}.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n輸出 {fp}")


if __name__ == "__main__":
    main()
