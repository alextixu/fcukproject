"""分類指標 + 十分位多空(移植自 ../chartgcn/analysis/decile_ls.py,含 2026-09-05 平手修正)。"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, norm
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score)

TDAYS = 246
# 台股一趟成本:手續費 0.1425% × 2(不打折)+ 證交稅 0.3% = 0.585%(多空兩腿各自計)
COST_RT = 0.00585


def clf_metrics(y, p):
    yhat = (p >= 0.5).astype(int)
    m = {
        "acc": accuracy_score(y, yhat),
        "auc": roc_auc_score(y, p) if len(np.unique(y)) > 1 else float("nan"),
        "pre_1": precision_score(y, yhat, pos_label=1, zero_division=0),
        "rec_1": recall_score(y, yhat, pos_label=1, zero_division=0),
        "f1_1": f1_score(y, yhat, pos_label=1, zero_division=0),
        "pre_0": precision_score(y, yhat, pos_label=0, zero_division=0),
        "rec_0": recall_score(y, yhat, pos_label=0, zero_division=0),
        "f1_0": f1_score(y, yhat, pos_label=0, zero_division=0),
        "prob_mean": float(np.mean(p)), "prob_std": float(np.std(p)),
        "pred_up_ratio": float(yhat.mean()),
    }
    m["f1_macro"] = (m["f1_1"] + m["f1_0"]) / 2
    # 只對最有把握的樣本下注時的準確率(|p-0.5| 最大的前 cov 比例)
    conf = np.abs(np.asarray(p) - 0.5)
    order = np.argsort(-conf)
    for cov in (0.05, 0.1, 0.2, 0.5):
        k = max(int(len(p) * cov), 1)
        sel = order[:k]
        m[f"acc_cov{int(cov * 100)}"] = accuracy_score(np.asarray(y)[sel], yhat[sel])
    return {k: float(v) for k, v in m.items()}


def decile_analysis(dates, probs, rets, h, n_dec=10, min_n=30, rng=None,
                    tie_eps=1e-6, degen_std=0.01, tickers=None, cost_rt=COST_RT):
    """tickers 給定時額外計算多空兩腿的週轉率與扣成本後的 H-L。

    週轉率定義:本期分位成員中,上一期不在同分位的比例(0 = 完全不動, 1 = 全換)。
    每期成本 = (多腿週轉 + 空腿週轉) × 一趟成本;第一期建倉視為全換。
    """
    if rng is None:
        rng = np.random.default_rng(0)
    udates = sorted(set(dates))
    rebal = udates[::h]
    rows, costs, turns = [], [], []
    n_degen = n_used = 0
    prev_lo = prev_hi = None
    for d in rebal:
        m = (dates == d) & np.isfinite(rets)
        if m.sum() < min_n:
            continue
        p, r = probs[m], rets[m]
        n_used += 1
        if len(np.unique(np.round(p / tie_eps))) < n_dec or p.std() < degen_std:
            n_degen += 1
        shuf = rng.permutation(len(p))
        order = shuf[np.argsort(p[shuf], kind="stable")]
        edges = np.linspace(0, len(p), n_dec + 1).astype(int)
        per = [float(r[order[edges[k]:edges[k + 1]]].mean()) for k in range(n_dec)]
        rows.append(per + [float(r.mean())])
        if tickers is not None:
            tk = tickers[m]
            lo = set(tk[order[edges[0]:edges[1]]])
            hi = set(tk[order[edges[n_dec - 1]:edges[n_dec]]])
            t_lo = 1.0 if prev_lo is None else 1 - len(lo & prev_lo) / max(len(lo), 1)
            t_hi = 1.0 if prev_hi is None else 1 - len(hi & prev_hi) / max(len(hi), 1)
            turns.append((t_hi + t_lo) / 2)
            costs.append((t_hi + t_lo) * cost_rt)
            prev_lo, prev_hi = lo, hi
    if not rows:
        return None
    A = np.asarray(rows)
    ppy = TDAYS / h
    ann = A.mean(0) * ppy
    vol = A.std(0, ddof=1) * np.sqrt(ppy)
    sr = np.divide(ann, vol, out=np.zeros_like(ann), where=vol > 0)
    hl = A[:, n_dec - 1] - A[:, 0]
    hl_ann = hl.mean() * ppy
    sd = hl.std(ddof=1)
    hl_sr = hl.mean() / sd * np.sqrt(ppy) if sd > 0 else 0.0
    t = hl.mean() / (sd / np.sqrt(len(hl))) if sd > 0 else 0.0
    rho, rp = spearmanr(np.arange(n_dec), ann[:n_dec])
    cost_info = {}
    if costs:
        c = np.asarray(costs)
        hl_net = hl - c
        sd_n = hl_net.std(ddof=1)
        cost_info = {
            "turnover_mean": round(float(np.mean(turns)), 3),
            "cost_ann_pct": round(float(c.mean() * ppy * 100), 2),
            "hl_net_ann_ret_pct": round(float(hl_net.mean() * ppy * 100), 2),
            "hl_net_sharpe": round(float(hl_net.mean() / sd_n * np.sqrt(ppy)) if sd_n > 0 else 0.0, 2),
            "hl_net_t_stat": round(float(hl_net.mean() / (sd_n / np.sqrt(len(hl_net)))) if sd_n > 0 else 0.0, 2),
            "breakeven_cost_rt_pct": round(float(hl.mean() / max(np.mean(turns) * 2, 1e-9) * 100), 3),
        }
    return {
        "n_periods": len(rows), "h": h, **cost_info,
        "decile_ann_ret_pct": [round(v * 100, 2) for v in ann[:n_dec]],
        "decile_sharpe": [round(v, 2) for v in sr[:n_dec]],
        "bench_ann_ret_pct": round(ann[n_dec] * 100, 2),
        "bench_sharpe": round(float(sr[n_dec]), 2),
        "hl_ann_ret_pct": round(hl_ann * 100, 2),
        "hl_sharpe": round(float(hl_sr), 2),
        "hl_t_stat": round(float(t), 2),
        "monotonic_spearman": round(float(rho), 3),
        "monotonic_p": float(f"{rp:.3g}"),
        "n_degenerate_dates": n_degen,
        "degenerate_pct": round(100.0 * n_degen / max(n_used, 1), 1),
    }


def null_distribution(dates, rets, h, reps=200, seed=0):
    rng = np.random.default_rng(seed)
    hls, rhos = [], []
    for _ in range(reps):
        out = decile_analysis(dates, rng.random(len(dates)), rets, h, rng=rng)
        if out:
            hls.append(out["hl_ann_ret_pct"])
            rhos.append(out["monotonic_spearman"])
    if not hls:
        return None
    hls, rhos = np.array(hls), np.array(rhos)
    return {"reps": len(hls), "hl_mean": round(float(hls.mean()), 2),
            "hl_sd": round(float(hls.std(ddof=1)), 2),
            "hl_p05": round(float(np.percentile(hls, 5)), 2),
            "hl_p95": round(float(np.percentile(hls, 95)), 2),
            "rho_sd": round(float(rhos.std(ddof=1)), 3),
            "rho_p95": round(float(np.percentile(rhos, 95)), 3)}


def null_pctile(x, mu, sd):
    return round(100 * float(norm.cdf((x - mu) / sd)), 1) if sd > 0 else 50.0


def decile_eval(test: pd.DataFrame, probs, horizons=(1, 5, 20), null_reps=0, null_h=None):
    dates = np.array([str(d)[:10] for d in test.index.get_level_values("date")])
    tickers = np.asarray(test.index.get_level_values("ticker"))
    out = {}
    for h in horizons:
        r = test[f"r_h{h}"].values.astype(float)
        res = decile_analysis(dates, probs, r, h, rng=np.random.default_rng(20260905),
                              tickers=tickers)
        if res and null_reps and (null_h is None or h == null_h):
            nd = null_distribution(dates, r, h, reps=null_reps)
            if nd:
                res["null"] = nd
                res["hl_null_pctile"] = null_pctile(res["hl_ann_ret_pct"], nd["hl_mean"], nd["hl_sd"])
                res["rho_null_pctile"] = null_pctile(res["monotonic_spearman"], 0.0, nd["rho_sd"])
        out[f"h{h}"] = res
    return out
