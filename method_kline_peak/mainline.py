"""主軸(2026-10-18 起):論文標籤 + 論文規則框架 + AE + OC-SVM 否決假候選。

流程
  1. 標籤:paper_aeocsvm.paper_label(郭念慈、李俊宏 2.1 節:t 日收盤為 t±5 最高 → 高點、最低 → 低點,並列也算)
  2. 規則挑候選:t 日收盤為 t−5 ~ t 最高 → 高點候選、最低 → 低點候選;非候選一律判非極值(真高低點召回率 100%)
  3. AE + OC-SVM(高點、低點各一組)只用訓練期的候選點訓練;測試時候選點落在範圍內才保留,否則改判非極值
  4. 評估:macro-F1(主要)、BalAcc、acc、各類精確率;真 / 假候選保留率;
     對照 = 規則基準、隨機否決同樣數量(20 次);macro-F1 − 規則基準 的 10 日區塊 bootstrap 95% CI
可調參數(預設值 = 第 8 節的結果)
  --window   輸入 K 棒數(t−N+1 ~ t 的 O/H/L/C/量),預設 6
  --vol-ma   量的基準:每天的量 ÷ 到 t 為止的 N 日均量,預設 20
  --extra    額外特徵組,可多選:
               pos  收盤相對前 5 日最高 / 最低的突破幅度、上 / 下影線(ATR 倍數)
               ctx  5–60 日報酬、距 20 / 60 日高低點、均線乖離、20 日波動、ATR、RSI、量比
               mkt  大盤(0050)1 / 5 / 20 日報酬、距 20 日高點、20 日波動
               chip 三大法人 / 融資券 / 外資持股 40 欄(method_xgb 的 chip_features,整組延後 1 日避免未公布資料)
  --latent / --epochs   AE 潛在維度 / 訓練輪數(原系統 4 / 60)
  --nu       OC-SVM nu,可多個(第一個為主要),--gamma(scale 或數值)
  --weight   OC-SVM 樣本權重:purity(距離 ≤ dist 的相似候選中同為真的比例)/ none
  --dist     相似樣本的歐氏距離門檻(原系統 3.0)
  --splits   paper(論文切分)/ ours(訓練 2020–2023、測試 2025-01 ~ 2026-09)
  --seeds    AE 亂數種子
  --tag      實驗名稱;每次執行在 results/experiments.csv 追加一列,詳細結果存 results/main_<tag>.json
  --mode     oneclass(預設):AE + OC-SVM 只學真候選,候選落在範圍內才保留
             contrast:真候選、假候選各學一組 AE + OC-SVM,分數 = 像真的程度 − 像假的程度
               分數兩種:ocsvm(兩個 OC-SVM 的 decision 在各自訓練集中的百分位數相減)、
                         recon(假候選 AE 的重建誤差 − 真候選 AE 的重建誤差)
               保留規則:分數 > 0,或只留分數最高的 90 / 70 / 50 / 30%;另算保留下來的候選直接交易
               (t+1 開盤進、t+5 收盤出,低點做多、高點放空,扣 0.42% 成本)

用法: python method_kline_peak/mainline.py --tag base
      python method_kline_peak/mainline.py --tag win20 --window 20
      python method_kline_peak/mainline.py --tag chip --extra chip
      python method_kline_peak/mainline.py --tag contrast --mode contrast
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from feasibility import P, START, END, COST, load_pool, clean  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402
from peak_labels import causal_features  # noqa: E402
from confusion import ORDER, SURFACE, INK, plt, draw, summarize  # noqa: E402
from paper_aeocsvm import NAMES, SPLITS, paper_label, rule_pred, mean_metrics  # noqa: E402
import ae_ocsvm  # noqa: E402
import kline.autoencoder as KA  # noqa: E402   (ae_ocsvm 已把 method_kline 加入 sys.path)

OUT = os.path.join(HERE, "results")
LOG = os.path.join(OUT, "experiments.csv")
POOL = "tw50"
CAND = {DOWN: "cand_hi", UP: "cand_lo"}
N_RANDOM, N_BOOT, BLOCK = 20, 500, 10
KEEP_RULES = ("s>0", 0.9, 0.7, 0.5, 0.3)          # contrast 模式的保留規則(數字 = 只留分數最高的比例)
GROUPS = {
    "pos": ["chi_margin", "clo_margin", "upper_atr", "lower_atr"],
    "ctx": ["ret5", "ret10", "ret20", "ret60", "dhi20", "dhi60", "dlo20", "dlo60",
            "ma5", "ma20", "ma60", "vol20", "atr14", "rsi14", "vr5_20"],
    "mkt": ["m_ret1", "m_ret5", "m_ret20", "m_dhi20", "m_vol20"],
}


def shape_features(df, n, vol_ma=20):
    O, H, L, C, V = (df[k] for k in ("open", "high", "low", "close", "volume"))
    lc = np.log(C)
    vbase = V.rolling(vol_ma, min_periods=vol_ma).mean()          # 6 天的量共用「到 t 為止的 vol_ma 日均量」當分母
    f = {}
    for k in range(n):
        f[f"o{k}"] = np.log(O.shift(k)) - lc
        f[f"h{k}"] = np.log(H.shift(k)) - lc
        f[f"l{k}"] = np.log(L.shift(k)) - lc
        if k:
            f[f"c{k}"] = np.log(C.shift(k)) - lc
        f[f"v{k}"] = np.log(V.shift(k) / vbase)
    return pd.DataFrame(f, index=df.index)


def build_panel(data, window, extra, vol_ma=20):
    mkt = clean(pd.read_parquet(os.path.join(P.YF_2026_CACHE, "0050.TW.parquet"))) if "mkt" in extra else None
    chips = {}
    if "chip" in extra:
        os.environ.setdefault("FINMIND_DIR", P.FINMIND_2026)
        from chip_data import load_chip  # noqa: E402  (method_xgb/src,feasibility 已加入 sys.path)
        from features.chip import chip_features  # noqa: E402
        chips = load_chip(list(data), START, END)
    parts = []
    for tk, df in data.items():
        df = clean(df)
        y, cand_hi, cand_lo = paper_label(df["close"])
        feats = [shape_features(df, window, vol_ma)]
        if set(extra) & {"pos", "ctx", "mkt"}:
            cf = causal_features(df, mkt)
            feats.append(cf[[c for g in extra if g in GROUPS for c in GROUPS[g]]])
        if "chip" in extra:
            cp = chip_features(df, chips.get(tk, {})).shift(1)          # 籌碼延後 1 日:t 日只用 t−1 的籌碼
            feats.append(cp.add_prefix("chip_"))
        part = pd.concat(feats, axis=1).replace([np.inf, -np.inf], np.nan)
        part["y"], part["cand_hi"], part["cand_lo"], part["ticker"] = y, cand_hi, cand_lo, tk
        part["r5"] = df["close"].shift(-5) / df["open"].shift(-1) - 1   # 只用於交易評估,不進特徵
        part.index.name = "date"
        parts.append(part.reset_index())
    panel = pd.concat(parts, ignore_index=True)
    shape_cols = list(feats[0].columns)
    panel = panel[panel["y"].notna() & panel[shape_cols].notna().all(axis=1) & (panel["date"] >= START)]
    panel["y"] = panel["y"].astype(int)
    feat_cols = [c for c in panel.columns if c not in ("date", "y", "cand_hi", "cand_lo", "ticker", "r5")]
    return panel.reset_index(drop=True), feat_cols


def split(panel, sp, half=5):
    cal = np.sort(panel["date"].unique())
    i = np.searchsorted(cal, np.datetime64(sp["test"][0]))
    keep = ~panel["date"].isin(cal[max(0, i - half):i])            # t+5 會跨進測試段的樣本
    return {k: panel[keep & panel["date"].between(a, b)].reset_index(drop=True) for k, (a, b) in sp.items()}


def fast_macro_f1(y, p):
    cm = np.bincount(y * 3 + p, minlength=9).reshape(3, 3).astype(float)
    tp, col, row = np.diag(cm), cm.sum(0), cm.sum(1)
    prec = np.divide(tp, col, out=np.zeros(3), where=col > 0)
    rec = np.divide(tp, row, out=np.zeros(3), where=row > 0)
    return float(np.mean(np.divide(2 * prec * rec, prec + rec, out=np.zeros(3), where=(prec + rec) > 0)))


def delta_ci(y, preds, rule, dates, rng):
    """macro-F1(模型,各種子平均)− macro-F1(規則)的 10 日區塊 bootstrap 95% CI(成對,同一組抽樣)。"""
    cal = np.sort(np.unique(dates))
    block = np.searchsorted(cal, dates) // BLOCK
    groups = [np.flatnonzero(block == b) for b in np.unique(block)]
    out = []
    for _ in range(N_BOOT):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        out.append(np.mean([fast_macro_f1(y[idx], p[idx]) for p in preds]) - fast_macro_f1(y[idx], rule[idx]))
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def fit_class(tr, cls, feat_cols, args):
    c = tr[CAND[cls]].to_numpy()
    X = tr.loc[c, feat_cols]
    med = X.median()
    sc = StandardScaler().fit(X.fillna(med))
    Xc = np.clip(sc.transform(X.fillna(med)), -5, 5).astype(np.float32)
    yc = tr["y"].to_numpy()[c]
    seeds, w = ae_ocsvm.neighbor_purity(Xc, yc, cls)
    if args.weight == "none":
        w = np.ones_like(w)
    ae = KA.train_ae(Xc[seeds], Xc.shape[1], lambda s: None)
    ae.eval()
    with torch.no_grad():
        z = ae.encode(torch.FloatTensor(Xc[seeds])).numpy()
    w = np.maximum(w, 1e-3)
    gamma = args.gamma if args.gamma == "scale" else float(args.gamma)
    ocs = {nu: OneClassSVM(kernel="rbf", nu=nu, gamma=gamma).fit(z, sample_weight=w / w.mean()) for nu in args.nu}
    return {"med": med, "sc": sc, "ae": ae, "ocs": ocs}


def run_split(panel, feat_cols, sp_name, sp, args, rng):
    d = split(panel, sp)
    tr, te = d["train"], d["test"]
    yte = te["y"].to_numpy()
    rule_p = rule_pred(te)
    res = {"rule": summarize(yte, rule_p, NAMES), "by_nu": {}}
    preds = {nu: [] for nu in args.nu}
    keep = {nu: {cls: {"真": [], "假": []} for cls in (DOWN, UP)} for nu in args.nu}
    for seed in args.seeds:
        torch.manual_seed(seed)
        np.random.seed(seed)
        pr = {nu: np.full(len(te), FLAT) for nu in args.nu}
        for cls in (DOWN, UP):
            m = fit_class(tr, cls, feat_cols, args)
            c = te[CAND[cls]].to_numpy()
            Xt = np.clip(m["sc"].transform(te.loc[c, feat_cols].fillna(m["med"])), -5, 5).astype(np.float32)
            with torch.no_grad():
                zt = m["ae"].encode(torch.FloatTensor(Xt)).numpy()
            true_c, idx = yte[c] == cls, np.flatnonzero(c)
            for nu, oc in m["ocs"].items():
                inside = oc.predict(zt) == 1
                pr[nu][idx[inside]] = cls
                keep[nu][cls]["真"].append(float(inside[true_c].mean()))
                keep[nu][cls]["假"].append(float(inside[~true_c].mean()))
        for nu in args.nu:
            preds[nu].append(pr[nu])
    for nu in args.nu:
        runs = [summarize(yte, p, NAMES) for p in preds[nu]]
        rand = []
        for p in preds[nu]:
            for _ in range(N_RANDOM):
                rp = np.full(len(te), FLAT)
                for cls in (DOWN, UP):
                    idx = np.flatnonzero(te[CAND[cls]].to_numpy())
                    rp[rng.choice(idx, size=int((p[idx] == cls).sum()), replace=False)] = cls
                rand.append(fast_macro_f1(yte, rp))
        res["by_nu"][str(nu)] = {
            "model": mean_metrics(runs), "random_veto_macro_f1": float(np.mean(rand)),
            "keep_rate": {NAMES[cls]: {k: float(np.mean(v)) for k, v in keep[nu][cls].items()} for cls in (DOWN, UP)},
        }
    main = args.nu[0]
    res["by_nu"][str(main)]["delta_vs_rule_ci"] = delta_ci(yte, preds[main], rule_p, te["date"].to_numpy(), rng)
    res["seed0_main"] = summarize(yte, preds[main][0], NAMES)
    res["n"] = {"train": len(tr), "test": len(te),
                "train_cand": {NAMES[c]: int(tr[CAND[c]].sum()) for c in (DOWN, UP)}}
    return res


def log_row(args, n_feat, sp_name, res):
    main = res["by_nu"][str(args.nu[0])]
    m, kp, ci = main["model"], main["keep_rate"], main["delta_vs_rule_ci"]
    row = {
        "time": time.strftime("%Y-%m-%d %H:%M"), "tag": args.tag, "split": sp_name,
        "window": args.window, "vol_ma": args.vol_ma, "extra": "+".join(args.extra) or "-", "n_features": n_feat,
        "latent": args.latent, "epochs": args.epochs, "nu": args.nu[0], "gamma": args.gamma,
        "weight": args.weight, "dist": args.dist, "seeds": len(args.seeds),
        "rule_macro_f1": round(res["rule"]["macro_f1"] * 100, 2),
        "model_macro_f1": round(m["macro_f1"] * 100, 2), "model_sd": round(m["sd_macro_f1"] * 100, 2),
        "random_veto_macro_f1": round(main["random_veto_macro_f1"] * 100, 2),
        "delta_vs_rule": round((m["macro_f1"] - res["rule"]["macro_f1"]) * 100, 2),
        "delta_ci_lo": round(ci[0] * 100, 2), "delta_ci_hi": round(ci[1] * 100, 2),
        "bal_acc": round(m["bal_acc"] * 100, 2), "acc": round(m["acc"] * 100, 2),
        "prec_high": round(m["precision"]["高點"] * 100, 2), "prec_low": round(m["precision"]["低點"] * 100, 2),
        "keep_true_high": round(kp["高點"]["真"] * 100, 1), "keep_false_high": round(kp["高點"]["假"] * 100, 1),
        "keep_true_low": round(kp["低點"]["真"] * 100, 1), "keep_false_low": round(kp["低點"]["假"] * 100, 1),
    }
    row["mode"] = "oneclass"
    write_log(row)
    return row


def write_log(row):
    """追加一列到 experiments.csv;欄位不同時取聯集重寫(舊列缺的欄位留空)。"""
    old = pd.read_csv(LOG) if os.path.exists(LOG) else pd.DataFrame()
    pd.concat([old, pd.DataFrame([row])], ignore_index=True).to_csv(LOG, index=False)


# ── contrast 模式:真候選、假候選各一組 AE + OC-SVM ───────────────────────────

def fit_pop(X, w, nu, gamma):
    ae = KA.train_ae(X, X.shape[1], lambda s: None)
    ae.eval()
    with torch.no_grad():
        z = ae.encode(torch.FloatTensor(X)).numpy()
    w = np.maximum(w, 1e-3)
    oc = OneClassSVM(kernel="rbf", nu=nu, gamma=gamma).fit(z, sample_weight=w / w.mean())
    return {"ae": ae, "oc": oc, "dec": np.sort(oc.decision_function(z))}


def fit_contrast(tr, cls, feat_cols, args):
    c = tr[CAND[cls]].to_numpy()
    X = tr.loc[c, feat_cols]
    med = X.median()
    sc = StandardScaler().fit(X.fillna(med))
    Xc = np.clip(sc.transform(X.fillna(med)), -5, 5).astype(np.float32)
    yb = (tr["y"].to_numpy()[c] == cls).astype(int)                    # 1 = 真候選、0 = 假候選
    gamma = args.gamma if args.gamma == "scale" else float(args.gamma)
    pops = {}
    for name, lab in (("T", 1), ("F", 0)):
        idx, w = ae_ocsvm.neighbor_purity(Xc, yb, lab)                  # 相似候選中與自己同為真(假)的比例
        if args.weight == "none":
            w = np.ones_like(w)
        pops[name] = fit_pop(Xc[idx], w, args.nu[0], gamma)
    return {"med": med, "sc": sc, **pops}


def contrast_scores(m, X):
    out = {}
    Xt = torch.FloatTensor(X)
    for name in ("T", "F"):
        p = m[name]
        with torch.no_grad():
            rec, z = p["ae"](Xt)
        dec = p["oc"].decision_function(z.numpy())
        out[name] = (np.searchsorted(p["dec"], dec) / len(p["dec"]),           # 在自己訓練集中的百分位
                     ((rec - Xt) ** 2).mean(1).numpy())
    return {"ocsvm": out["T"][0] - out["F"][0], "recon": out["F"][1] - out["T"][1]}


def keep_mask(s, rule):
    return s > 0 if rule == "s>0" else s >= np.quantile(s, 1 - rule)


def trade(r5, side):
    r = r5 if side == "long" else -r5
    return {"n": int(len(r)), "win": float((r > 0).mean()) if len(r) else None,
            "avg_net_pct": float((r - COST).mean() * 100) if len(r) else None}


def run_contrast(panel, feat_cols, sp_name, sp, args, rng):
    d = split(panel, sp)
    tr, te = d["train"], d["test"]
    yte, r5 = te["y"].to_numpy(), te["r5"].to_numpy()
    rule_p = rule_pred(te)
    cand_idx = {cls: np.flatnonzero(te[CAND[cls]].to_numpy()) for cls in (DOWN, UP)}
    side = {UP: "long", DOWN: "short"}
    res = {"rule": summarize(yte, rule_p, NAMES),
           "rule_trade": {NAMES[cls]: trade(r5[cand_idx[cls]], side[cls]) for cls in (DOWN, UP)},
           "contrast": {}}
    scores = []                                                          # 每個種子:{cls: {score: 陣列}}
    for seed in args.seeds:
        torch.manual_seed(seed)
        np.random.seed(seed)
        per = {}
        for cls in (DOWN, UP):
            m = fit_contrast(tr, cls, feat_cols, args)
            Xt = np.clip(m["sc"].transform(te.loc[cand_idx[cls], feat_cols].fillna(m["med"])), -5, 5).astype(np.float32)
            per[cls] = contrast_scores(m, Xt)
        scores.append(per)
    for sname in ("ocsvm", "recon"):
        res["contrast"][sname] = {}
        for rule in KEEP_RULES:
            preds, rand, keep, trades = [], [], {c: {"真": [], "假": []} for c in (DOWN, UP)}, {c: [] for c in (DOWN, UP)}
            for per in scores:
                p = np.full(len(te), FLAT)
                for cls in (DOWN, UP):
                    idx, k = cand_idx[cls], keep_mask(per[cls][sname], rule)
                    p[idx[k]] = cls
                    true_c = yte[idx] == cls
                    keep[cls]["真"].append(float(k[true_c].mean()))
                    keep[cls]["假"].append(float(k[~true_c].mean()))
                    trades[cls].append(trade(r5[idx[k]], side[cls]))
                preds.append(p)
                for _ in range(N_RANDOM):
                    rp = np.full(len(te), FLAT)
                    for cls in (DOWN, UP):
                        idx = cand_idx[cls]
                        rp[rng.choice(idx, size=int((p[idx] == cls).sum()), replace=False)] = cls
                    rand.append(fast_macro_f1(yte, rp))
            runs = [summarize(yte, p, NAMES) for p in preds]
            res["contrast"][sname][str(rule)] = {
                "model": mean_metrics(runs), "random_veto_macro_f1": float(np.mean(rand)),
                "delta_vs_rule_ci": delta_ci(yte, preds, rule_p, te["date"].to_numpy(), rng),
                "keep_rate": {NAMES[c]: {k: float(np.mean(v)) for k, v in keep[c].items()} for c in (DOWN, UP)},
                "trade": {NAMES[c]: {k: float(np.mean([t[k] for t in trades[c] if t[k] is not None] or [np.nan]))
                                     for k in ("n", "win", "avg_net_pct")} for c in (DOWN, UP)},
            }
    res["n"] = {"train": len(tr), "test": len(te),
                "train_cand": {NAMES[c]: int(tr[CAND[c]].sum()) for c in (DOWN, UP)}}
    return res


def log_contrast(args, n_feat, sp_name, res):
    rows = []
    for sname, by_rule in res["contrast"].items():
        for rule, b in by_rule.items():
            m, kp, ci, td = b["model"], b["keep_rate"], b["delta_vs_rule_ci"], b["trade"]
            row = {
                "time": time.strftime("%Y-%m-%d %H:%M"), "tag": args.tag, "mode": "contrast", "score": sname,
                "keep_rule": rule, "split": sp_name, "window": args.window, "vol_ma": args.vol_ma, "extra": "+".join(args.extra) or "-",
                "n_features": n_feat, "latent": args.latent, "epochs": args.epochs, "nu": args.nu[0],
                "gamma": args.gamma, "weight": args.weight, "dist": args.dist, "seeds": len(args.seeds),
                "rule_macro_f1": round(res["rule"]["macro_f1"] * 100, 2),
                "model_macro_f1": round(m["macro_f1"] * 100, 2), "model_sd": round(m["sd_macro_f1"] * 100, 2),
                "random_veto_macro_f1": round(b["random_veto_macro_f1"] * 100, 2),
                "delta_vs_rule": round((m["macro_f1"] - res["rule"]["macro_f1"]) * 100, 2),
                "delta_ci_lo": round(ci[0] * 100, 2), "delta_ci_hi": round(ci[1] * 100, 2),
                "bal_acc": round(m["bal_acc"] * 100, 2), "acc": round(m["acc"] * 100, 2),
                "prec_high": round(m["precision"]["高點"] * 100, 2), "prec_low": round(m["precision"]["低點"] * 100, 2),
                "keep_true_high": round(kp["高點"]["真"] * 100, 1), "keep_false_high": round(kp["高點"]["假"] * 100, 1),
                "keep_true_low": round(kp["低點"]["真"] * 100, 1), "keep_false_low": round(kp["低點"]["假"] * 100, 1),
                "trade_low_win": round(td["低點"]["win"] * 100, 1), "trade_low_net": round(td["低點"]["avg_net_pct"], 2),
                "trade_high_win": round(td["高點"]["win"] * 100, 1), "trade_high_net": round(td["高點"]["avg_net_pct"], 2),
            }
            write_log(row)
            rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--window", type=int, default=6)
    ap.add_argument("--vol-ma", type=int, default=20)
    ap.add_argument("--extra", nargs="*", default=[], choices=["pos", "ctx", "mkt", "chip"])
    ap.add_argument("--latent", type=int, default=4)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--nu", type=float, nargs="+", default=[0.1, 0.2, 0.3, 0.5])
    ap.add_argument("--gamma", default="scale")
    ap.add_argument("--weight", default="purity", choices=["purity", "none"])
    ap.add_argument("--dist", type=float, default=3.0)
    ap.add_argument("--splits", nargs="+", default=["paper", "ours"], choices=["paper", "ours"])
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--mode", default="oneclass", choices=["oneclass", "contrast"])
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()
    KA.LATENT_DIM, KA.EPOCHS = args.latent, args.epochs
    ae_ocsvm.DIST_THRESH = args.dist
    t0 = time.time()
    plt.rcParams["font.family"] = "WenQuanYi Zen Hei"

    panel, feat_cols = build_panel(load_pool(POOL, START, END), args.window, args.extra, args.vol_ma)
    print(f"[{args.tag}] window {args.window}、量基準 {args.vol_ma} 日均量、extra {args.extra or '-'}:{len(feat_cols)} 個特徵,"
          f"latent {args.latent}、epochs {args.epochs}、nu {args.nu}、gamma {args.gamma}、weight {args.weight}、dist {args.dist}"
          f"  ({time.time() - t0:.0f}s)", flush=True)
    names = {"paper": "論文切分", "ours": "我們的切分"}
    rng = np.random.default_rng(0)
    out = {"args": vars(args), "features": feat_cols, "results": {}}
    for key in args.splits:
        sp_name = names[key]
        if args.mode == "contrast":
            res = run_contrast(panel, feat_cols, sp_name, SPLITS[sp_name], args, rng)
            out["results"][sp_name] = res
            rows = log_contrast(args, len(feat_cols), sp_name, res)
            rt, ru = res["rule_trade"], res["rule"]
            print(f"  {sp_name}:規則 macro-F1 {ru['macro_f1']:.2%}、命中率 高 {ru['precision']['高點']:.1%} / 低 {ru['precision']['低點']:.1%};"
                  f"直接交易 低點做多 勝 {rt['低點']['win']:.1%} 淨 {rt['低點']['avg_net_pct']:+.2f}%、"
                  f"高點放空 勝 {rt['高點']['win']:.1%} 淨 {rt['高點']['avg_net_pct']:+.2f}%")
            print(f"    {'分數':<6}{'保留':<6}{'macro-F1':>9}{'隨機':>8}{'差 [95% CI]':>22}  {'命中 高/低':>12}  "
                  f"{'保留率 高 真/假':>14} {'低 真/假':>10}  {'低點做多 勝/淨':>14} {'高點放空 勝/淨':>14}")
            for r in rows:
                print(f"    {r['score']:<6}{str(r['keep_rule']):<6}{r['model_macro_f1']:>8.2f}%{r['random_veto_macro_f1']:>7.2f}%"
                      f"{r['delta_vs_rule']:>+8.2f} [{r['delta_ci_lo']:+.2f}, {r['delta_ci_hi']:+.2f}]"
                      f"  {r['prec_high']:>5.1f}/{r['prec_low']:>5.1f}%  {r['keep_true_high']:>6.0f}/{r['keep_false_high']:<5.0f}"
                      f" {r['keep_true_low']:>5.0f}/{r['keep_false_low']:<4.0f}  {r['trade_low_win']:>6.1f}%/{r['trade_low_net']:+.2f}%"
                      f"  {r['trade_high_win']:>6.1f}%/{r['trade_high_net']:+.2f}%", flush=True)
            continue
        res = run_split(panel, feat_cols, sp_name, SPLITS[sp_name], args, rng)
        out["results"][sp_name] = res
        row = log_row(args, len(feat_cols), sp_name, res)
        print(f"  {sp_name}:規則 {row['rule_macro_f1']:.2f}% → 模型 {row['model_macro_f1']:.2f}% ± {row['model_sd']:.2f}"
              f"(隨機否決 {row['random_veto_macro_f1']:.2f}%),差 {row['delta_vs_rule']:+.2f} 點"
              f" [95% CI {row['delta_ci_lo']:+.2f}, {row['delta_ci_hi']:+.2f}]  "
              f"保留率 高 真 {row['keep_true_high']:.0f}% / 假 {row['keep_false_high']:.0f}%、"
              f"低 真 {row['keep_true_low']:.0f}% / 假 {row['keep_false_low']:.0f}%  (nu {args.nu[0]})", flush=True)
        for nu, b in res["by_nu"].items():
            if float(nu) == args.nu[0]:
                continue
            kp = b["keep_rate"]
            print(f"      nu {nu:<4} macro-F1 {b['model']['macro_f1']:.2%}(隨機 {b['random_veto_macro_f1']:.2%})"
                  f"  保留率 高 {kp['高點']['真']:.0%}/{kp['高點']['假']:.0%}、低 {kp['低點']['真']:.0%}/{kp['低點']['假']:.0%}")
    with open(os.path.join(OUT, f"main_{args.tag}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    if args.plot and args.mode == "oneclass":
        cells = list(out["results"].items())
        fig, axes = plt.subplots(len(cells), 2, figsize=(11.6, 6.3 * len(cells)), facecolor=SURFACE, squeeze=False)
        for i, (sp_name, res) in enumerate(cells):
            sp = SPLITS[sp_name]
            head = f"{sp_name}:訓練 {sp['train'][0][:7]} ~ {sp['train'][1][:7]} · 測試 {sp['test'][0][:7]} ~ {sp['test'][1][:7]}"
            draw(axes[i, 0], res["rule"], f"{head}\n規則基準(論文)", NAMES)
            draw(axes[i, 1], res["seed0_main"], f"{head}\n規則 + AE + OC-SVM [{args.tag}](nu {args.nu[0]},種子 {args.seeds[0]})", NAMES)
        fig.suptitle(f"TW50 主軸 [{args.tag}]", fontsize=14, color=INK, x=0.01, ha="left")
        fig.subplots_adjust(left=0.1, right=0.99, top=0.9, bottom=0.08, wspace=0.45, hspace=0.62)
        fig.savefig(os.path.join(OUT, f"main_{args.tag}.png"), dpi=110, facecolor=SURFACE)
    print(f"[{args.tag}] 完成,記錄於 {LOG}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
