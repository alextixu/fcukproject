"""11 日中心高 / 低點標籤:貼法統計 + 三分類(頂 / 底 / 其他)可行性評估。

步驟
  1. 標籤統計:各口徑類別比例、右側同價(平盤)的頂底數、頂底同日、逐年比例、頂之後的跌幅;
     虛無對照 = 每檔 K 棒(相對前收的 O/H/L/C)時間順序打亂後重建價格再貼標
  2. 決策日可觀測性:頂 ⊆ left_top、底 ⊆ left_bot(t 收盤已知),
     三分類實際上 = 候選日上的兩個二分類;左半規則不學任何東西就能拿到的分數要先算出來當地板
  3. 預測:時間切分 train 2016-2022 / val 2023-2024 / test 2025-01 ~ 2026-09(交界前 5 日 purge)
       rule    左半規則(left_top → 頂、left_bot → 底、其餘 → 其他)
       struct  LightGBM,只用左半結構(left 旗標 + 突破幅度)
       shape   LightGBM,struct + 6 根 K 棒形態(價 + 量)
       full    LightGBM,shape + 背景 / 大盤特徵(seed 42/43/44)
       knn     形態搜尋:候選日上以 6 根 K 棒價格形態找 k 個最相似歷史候選日,鄰居中頂(底)比例當分數
     主要指標 = 候選日內 AUC(頂 vs 非頂 | left_top;底 vs 非底 | left_bot),附 10 日區塊 bootstrap 95% CI
  4. 經濟意義:t 收盤決策 → t+1 開盤進、t+5 收盤出的還原報酬;
     oracle(完美預知標籤)、標籤確認後(t+6 開 → t+10 收)、模型前 10% 分數的報酬

用法: python method_kline_peak/feasibility.py --pool tw50
輸出: method_kline_peak/results/feasibility_<pool>.json
"""
import argparse
import json
import os
import sys
import time

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_recall_fscore_support, roc_auc_score)
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
os.environ.setdefault("TW_CACHE_DIR", P.YF_2026_CACHE)
sys.path.insert(0, P.XGB_SRC)
from data import load_pool  # noqa: E402
sys.path.insert(0, HERE)
from peak_labels import (HALF, OTHER, TOP, BOTTOM, AMBIG, CLASS_NAMES, VARIANTS,  # noqa: E402
                         label_window, causal_features, side_extreme)

OUT = os.path.join(HERE, "results")
START, END = "2016-01-01", "2026-09-11"
SPLITS = {"train": ("2016-01-01", "2022-12-31"),
          "val": ("2023-01-01", "2024-12-31"),
          "test": ("2025-01-01", END)}
COST = 0.0042          # 每筆來回成本,同 method_kline(手續費 0.06% × 2 + 證交稅 0.3%)
BLOCK = 10             # bootstrap 區塊長度(交易日),蓋過標籤的 5 日重疊
N_BOOT = 300
N_NULL = 3             # 虛無對照打亂次數
KNN_K = 50
SEEDS = (42, 43, 44)
CLASSES = [OTHER, TOP, BOTTOM]

SHAPE_PX = [f"{p}{k}" for k in range(HALF + 1) for p in "ohlc" if not (p == "c" and k == 0)]
SHAPE = SHAPE_PX + [f"v{k}" for k in range(HALF + 1)]
STRUCT = {"hl": ["hi_margin", "lo_margin"], "hl_atr": ["hi_margin", "lo_margin"],
          "close": ["chi_margin", "clo_margin"]}
LGB_PARAMS = dict(objective="multiclass", num_class=3, learning_rate=0.05, num_leaves=31,
                  min_child_samples=200, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                  reg_lambda=1.0, n_estimators=2000, class_weight="balanced", n_jobs=4, verbose=-1)


# ── 資料 ─────────────────────────────────────────────────────────────────────

def clean(df):
    """去掉零量日(停牌),修正還原誤差造成的 High < max(O, C) / Low > min(O, C)。"""
    df = df[df["volume"] > 0].copy()
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    return df


def build_panel(data, mkt):
    parts = []
    for tk, df in data.items():
        df = clean(df)
        O, H, L, C = df["open"], df["high"], df["low"], df["close"]
        feat = causal_features(df, mkt)
        extra = pd.DataFrame({
            "fwd_oc5": C.shift(-HALF) / O.shift(-1) - 1,                  # t+1 開 → t+5 收
            "fwd_conf": C.shift(-2 * HALF) / O.shift(-HALF - 1) - 1,      # 標籤確認後:t+6 開 → t+10 收
            "drop_after": side_extreme(L, HALF, True, "min") / H - 1,     # 之後 5 日最低相對 H[t]
            "rise_after": side_extreme(H, HALF, True, "max") / L - 1,     # 之後 5 日最高相對 L[t]
        }, index=df.index)
        for v in VARIANTS:
            lab = label_window(df, v)
            extra[f"y_{v}"] = lab["label"]
            extra[f"lt_{v}"] = lab["left_top"]
            extra[f"lb_{v}"] = lab["left_bot"]
            extra[f"tt_{v}"] = lab["tie_top"]
            extra[f"tb_{v}"] = lab["tie_bot"]
        part = feat.join(extra)
        part["ticker"] = tk
        part.index.name = "date"
        parts.append(part.reset_index())
    panel = pd.concat(parts, ignore_index=True)
    return panel[panel["date"] >= START].reset_index(drop=True)


def shuffled_bars(df, rng):
    """虛無對照:K 棒(相對前收的 O/H/L/C)時間順序打亂後重建價格,保留單根形狀、去掉時序結構。"""
    cp = df["close"].shift(1)
    rel = np.column_stack([(df[k] / cp).to_numpy() for k in ("open", "high", "low", "close")])[1:]
    rel = rel[rng.permutation(len(rel))]
    c = df["close"].iloc[0] * np.cumprod(rel[:, 3])
    prev = np.r_[df["close"].iloc[0], c[:-1]]
    return pd.DataFrame({"open": prev * rel[:, 0], "high": prev * rel[:, 1], "low": prev * rel[:, 2],
                         "close": c, "volume": 1.0}, index=df.index[1:])


def null_stats(data, seed=0):
    rng = np.random.default_rng(seed)
    acc = {v: {"n": 0, TOP: 0, BOTTOM: 0, "lt": 0, "top_in_lt": 0} for v in VARIANTS}
    for _ in range(N_NULL):
        for df in data.values():
            sh = shuffled_bars(clean(df), rng)
            for v in VARIANTS:
                lab = label_window(sh, v)
                ok = lab["label"].notna()
                y, lt = lab["label"][ok], lab["left_top"][ok] == 1
                a = acc[v]
                a["n"] += int(ok.sum())
                a[TOP] += int((y == TOP).sum())
                a[BOTTOM] += int((y == BOTTOM).sum())
                a["lt"] += int(lt.sum())
                a["top_in_lt"] += int((y[lt] == TOP).sum())
    return {v: {"p_top": a[TOP] / a["n"], "p_bottom": a[BOTTOM] / a["n"],
                "p_left_top": a["lt"] / a["n"], "p_top_given_left_top": a["top_in_lt"] / a["lt"]}
            for v, a in acc.items()}


# ── 標籤統計 ─────────────────────────────────────────────────────────────────

def label_stats(panel, v):
    y = panel[f"y_{v}"]
    ok = y.notna()
    pv = panel[ok]
    y = y[ok]
    n = len(y)
    lt, lb = pv[f"lt_{v}"] == 1, pv[f"lb_{v}"] == 1
    top, bot = y == TOP, y == BOTTOM

    # 同檔相鄰兩個頂的間隔(交易日)
    gaps = []
    for _, g in pv.assign(i=pv.groupby("ticker").cumcount())[top].groupby("ticker"):
        gaps.extend(np.diff(g["i"].to_numpy()).tolist())

    atr_rel = pv["atr14"]
    by_year = pv.groupby(pv["date"].dt.year).apply(
        lambda g: {"頂": float((g[f"y_{v}"] == TOP).mean()), "底": float((g[f"y_{v}"] == BOTTOM).mean())},
        include_groups=False)
    return {
        "n": int(n),
        "proportion": {CLASS_NAMES[c]: float((y == c).mean()) for c in CLASSES},
        "ambiguous_both": int((y == AMBIG).sum()),
        "ties_right_equal": {"頂": int(pv[f"tt_{v}"].sum()), "底": int(pv[f"tb_{v}"].sum())},
        "p_left_top": float(lt.mean()), "p_top_given_left_top": float(top[lt].mean()),
        "p_left_bot": float(lb.mean()), "p_bot_given_left_bot": float(bot[lb].mean()),
        "top_gap_days": {"median": float(np.median(gaps)), "p10": float(np.percentile(gaps, 10))},
        "top_drop_after": {   # 頂之後 5 日內最低價相對 H[t](%)與 ATR 倍數
            "median_pct": float(pv.loc[top, "drop_after"].median() * 100),
            "median_atr": float((-pv.loc[top, "drop_after"] / atr_rel[top]).median()),
            "share_lt_1atr": float(((-pv.loc[top, "drop_after"]) < atr_rel[top]).mean()),
        },
        "by_year": {int(k): val for k, val in by_year.items()},
        "oracle_fwd_oc5_pct": {CLASS_NAMES[c]: float(pv.loc[y == c, "fwd_oc5"].mean() * 100) for c in CLASSES},
        "after_confirm_fwd_pct": {CLASS_NAMES[c]: float(pv.loc[y == c, "fwd_conf"].mean() * 100) for c in CLASSES},
        "all_days_fwd_oc5_pct": float(pv["fwd_oc5"].mean() * 100),
    }


# ── 切分 / 評估 ──────────────────────────────────────────────────────────────

def split_frames(panel, v, feats):
    cols = ["date", "ticker", "fwd_oc5", "fwd_conf"] + feats
    df = panel[cols].copy()
    df["y"], df["lt"], df["lb"] = panel[f"y_{v}"], panel[f"lt_{v}"], panel[f"lb_{v}"]
    df = df[df["y"].notna() & (df["y"] != AMBIG) & panel["ret60"].notna() & panel["dhi60"].notna()]
    df["y"] = df["y"].astype(int)

    cal = np.sort(panel["date"].unique())
    purge = []
    for name in ("val", "test"):
        i = np.searchsorted(cal, np.datetime64(SPLITS[name][0]))
        purge.extend(cal[max(0, i - HALF):i])          # 右半窗格跨進下一段的樣本
    keep = ~df["date"].isin(purge)
    block = pd.Series(np.searchsorted(cal, df["date"].to_numpy()) // BLOCK, index=df.index)
    df["block"] = block
    return {k: df[keep & (df["date"] >= a) & (df["date"] <= b)].reset_index(drop=True)
            for k, (a, b) in SPLITS.items()}


def boot_ci(stat, blocks, rng):
    groups = [np.flatnonzero(blocks == b) for b in np.unique(blocks)]
    vals = []
    for _ in range(N_BOOT):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        try:
            vals.append(stat(idx))
        except ValueError:
            continue
    vals = np.asarray(vals, dtype=float)
    vals = vals[np.isfinite(vals)]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] if len(vals) else None


def candidate_metrics(te, score, cls, cand_col, rng):
    """候選日(left_top 或 left_bot)內:頂(底)vs 其餘的 AUC、前 10% 分數的命中率與報酬。"""
    cand = te[cand_col].to_numpy() == 1
    yc = (te["y"].to_numpy()[cand] == cls).astype(int)
    sc = score[cand]
    ret = te["fwd_oc5"].to_numpy()[cand]
    blocks = te["block"].to_numpy()[cand]
    informative = np.ptp(sc) > 0
    top10 = sc >= np.quantile(sc, 0.9) if informative else np.ones(len(sc), bool)
    out = {
        "n": int(cand.sum()), "base_rate": float(yc.mean()),
        "auc": float(roc_auc_score(yc, sc)) if informative else 0.5,
        "prec_top10": float(yc[top10].mean()),
        "lift_top10": float(yc[top10].mean() / yc.mean()),
        "ret_cand_pct": float(np.nanmean(ret) * 100),
        "ret_top10_pct": float(np.nanmean(ret[top10]) * 100),
    }
    if informative:
        out["auc_ci"] = boot_ci(lambda i: roc_auc_score(yc[i], sc[i]), blocks, rng)
        out["ret_top10_ci"] = boot_ci(lambda i: np.nanmean(ret[i][top10[i]]) * 100, blocks, rng)
    return out


def evaluate(te, proba, rng):
    y = te["y"].to_numpy()
    pred = np.array(CLASSES)[proba.argmax(axis=1)]
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=CLASSES, zero_division=0)
    return {
        "acc": float(accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, labels=CLASSES, average="macro", zero_division=0)),
        "per_class": {CLASS_NAMES[c]: {"precision": float(p[i]), "recall": float(r[i]),
                                       "f1": float(f[i]), "n": int(s[i])} for i, c in enumerate(CLASSES)},
        "confusion_other_top_bottom": confusion_matrix(y, pred, labels=CLASSES).tolist(),
        "auc_top_all_days": float(roc_auc_score(y == TOP, proba[:, 1])),
        "auc_bot_all_days": float(roc_auc_score(y == BOTTOM, proba[:, 2])),
        "top_cand": candidate_metrics(te, proba[:, 1], TOP, "lt", rng),
        "bot_cand": candidate_metrics(te, proba[:, 2], BOTTOM, "lb", rng),
    }


def rule_proba(te):
    lt, lb = te["lt"].to_numpy() == 1, te["lb"].to_numpy() == 1
    proba = np.zeros((len(te), 3))
    proba[:, 0] = 0.5
    proba[lt & ~lb, 1] = 1.0
    proba[lb & ~lt, 2] = 1.0
    return proba


def fit_lgb(tr, va, feats, seed):
    m = lgb.LGBMClassifier(**LGB_PARAMS, random_state=seed)
    m.fit(tr[feats], tr["y"], eval_set=[(va[feats], va["y"])],
          callbacks=[lgb.early_stopping(100, verbose=False)])
    return m


def knn_proba(fit_df, te):
    """形態搜尋:在歷史候選日中找 6 根 K 棒價格形態最近的 KNN_K 個,鄰居裡頂(底)的比例當分數。"""
    proba = np.zeros((len(te), 3))
    for cls, col in ((TOP, "lt"), (BOTTOM, "lb")):
        a = fit_df[fit_df[col] == 1]
        b_mask = te[col].to_numpy() == 1
        sc = StandardScaler().fit(a[SHAPE_PX])
        knn = KNeighborsClassifier(n_neighbors=KNN_K, n_jobs=4)
        knn.fit(sc.transform(a[SHAPE_PX].fillna(0)), (a["y"] == cls).astype(int))
        proba[b_mask, cls] = knn.predict_proba(sc.transform(te.loc[b_mask, SHAPE_PX].fillna(0)))[:, 1]
    proba[:, 0] = 1 - proba[:, 1:].max(axis=1)
    return proba


def single_feature_auc(te, feats):
    """候選日內單一特徵的 AUC(> 0.5 = 數值越大越像頂 / 底)。"""
    out = {}
    for cls, col, key in ((TOP, "lt", "頂"), (BOTTOM, "lb", "底")):
        c = te[te[col] == 1]
        yc = (c["y"] == cls).astype(int)
        out[key] = {f: float(roc_auc_score(yc, c[f].fillna(c[f].median()))) for f in feats}
    return out


# ── 主程式 ───────────────────────────────────────────────────────────────────

def run_variant(panel, v, feat_cols):
    rng = np.random.default_rng(0)
    struct = ["lt", "lb"] + STRUCT[v]
    shape = struct + SHAPE
    full = ["lt", "lb"] + feat_cols
    sp = split_frames(panel, v, feat_cols)
    tr, va, te = sp["train"], sp["val"], sp["test"]
    res = {"n_split": {k: len(d) for k, d in sp.items()}}

    res["rule"] = evaluate(te, rule_proba(te), rng)
    for name, feats in (("struct", struct), ("shape", shape)):
        m = fit_lgb(tr, va, feats, SEEDS[0])
        res[name] = evaluate(te, m.predict_proba(te[feats]), rng)
        res[name]["best_iter"] = int(m.best_iteration_)

    runs = []
    for seed in SEEDS:
        m = fit_lgb(tr, va, full, seed)
        r = evaluate(te, m.predict_proba(te[full]), rng)
        r["best_iter"] = int(m.best_iteration_)
        runs.append(r)
        if seed == SEEDS[0]:
            imp = pd.Series(m.booster_.feature_importance("gain"), index=full)
            res["full_importance_top15"] = (imp / imp.sum()).sort_values(ascending=False).head(15).round(4).to_dict()
    res["full"] = {"seeds": runs, "mean": {
        k: float(np.mean([g(r) for r in runs])) for k, g in {
            "macro_f1": lambda r: r["macro_f1"],
            "auc_top_cand": lambda r: r["top_cand"]["auc"],
            "auc_bot_cand": lambda r: r["bot_cand"]["auc"],
            "ret_top10_top_pct": lambda r: r["top_cand"]["ret_top10_pct"],
            "ret_top10_bot_pct": lambda r: r["bot_cand"]["ret_top10_pct"]}.items()},
        "sd_auc_top_cand": float(np.std([r["top_cand"]["auc"] for r in runs])),
        "sd_auc_bot_cand": float(np.std([r["bot_cand"]["auc"] for r in runs]))}

    res["knn"] = evaluate(te, knn_proba(pd.concat([tr, va]), te), rng)
    res["single_feature_auc"] = single_feature_auc(
        te, ["upper_atr", "lower_atr", STRUCT[v][0], STRUCT[v][1], "atr14", "ret5", "ret20", "dhi20", "rsi14", "v0"])
    return res


def summarize(v, st, nl, res):
    f = res["full"]["mean"]
    line = lambda name, r: (f"    {name:<7} macroF1 {r['macro_f1']:.3f}   "
                            f"頂|候選 AUC {r['top_cand']['auc']:.3f}  底|候選 AUC {r['bot_cand']['auc']:.3f}   "
                            f"前10%頂 報酬 {r['top_cand']['ret_top10_pct']:+.2f}%  前10%底 報酬 {r['bot_cand']['ret_top10_pct']:+.2f}%")
    print(f"\n== {v} ==  n={st['n']:,}  比例 " + " / ".join(f"{k} {p:.1%}" for k, p in st["proportion"].items())
          + f"  (虛無 頂 {nl['p_top']:.1%} 底 {nl['p_bottom']:.1%})")
    print(f"    P(頂|left_top) {st['p_top_given_left_top']:.1%}(虛無 {nl['p_top_given_left_top']:.1%})"
          f"  P(底|left_bot) {st['p_bot_given_left_bot']:.1%}  候選比例 {st['p_left_top']:.1%} / {st['p_left_bot']:.1%}")
    print(f"    oracle t+1開→t+5收: " + "  ".join(f"{k} {x:+.2f}%" for k, x in st["oracle_fwd_oc5_pct"].items())
          + "   確認後 t+6→t+10: " + "  ".join(f"{k} {x:+.2f}%" for k, x in st["after_confirm_fwd_pct"].items()))
    for name in ("rule", "struct", "shape", "knn"):
        print(line(name, res[name]))
    print(f"    full    macroF1 {f['macro_f1']:.3f}   頂|候選 AUC {f['auc_top_cand']:.3f}±{res['full']['sd_auc_top_cand']:.3f}"
          f"  底|候選 AUC {f['auc_bot_cand']:.3f}±{res['full']['sd_auc_bot_cand']:.3f}   "
          f"前10%頂 報酬 {f['ret_top10_top_pct']:+.2f}%  前10%底 報酬 {f['ret_top10_bot_pct']:+.2f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="tw50")
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS))
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()

    data = load_pool(args.pool, START, END)
    mkt = clean(pd.read_parquet(os.path.join(P.YF_2026_CACHE, "0050.TW.parquet")))
    panel = build_panel(data, mkt)
    feat_cols = list(causal_features(next(iter(data.values())).head(80), mkt).columns)
    print(f"[DATA] {args.pool}: {len(data)} 檔, panel {panel.shape}, "
          f"{panel['date'].min().date()} ~ {panel['date'].max().date()}  ({time.time() - t0:.0f}s)", flush=True)

    nulls = null_stats(data)
    out = {"pool": args.pool, "n_tickers": len(data), "splits": SPLITS, "half": HALF,
           "cost_roundtrip_pct": COST * 100, "variants": {}}
    for v in args.variants:
        st = label_stats(panel, v)
        res = run_variant(panel, v, feat_cols)
        out["variants"][v] = {"label_stats": st, "null_shuffled_bars": nulls[v], "models": res}
        summarize(v, st, nulls[v], res)
        print(f"    ({time.time() - t0:.0f}s)", flush=True)

    fp = os.path.join(OUT, f"feasibility_{args.pool}.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n輸出 {fp}  總耗時 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
