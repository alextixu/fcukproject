"""
十分位多空評估(對齊 Jiang, Kelly & Xiu 2023, JF 的協定)。

把 Chart GCN 的輸出從「二分類 → Accuracy」改成「上漲機率 → 橫斷面排序」:
  每個再平衡日:
    1. 對當日所有股票取 softmax P(漲)
    2. 依 P 由低到高排序,切成 10 等分
    3. 做多第 10 分位、放空第 1 分位(等權)
    4. 持有 h 個交易日,不重疊
  彙總:各分位年化報酬、Sharpe;H-L 價差;單調性(分位序 vs 平均報酬的 Spearman)

判讀重點(執行前定義):
  訊號存在  → 分位平均報酬應「單調遞增」,H-L 顯著 > 0
  訊號不存在 → 分位圖是平的/亂跳,H-L ≈ 0 且 CI 含 0
  單調性 Spearman ρ 是比 H-L 更嚴格的檢驗(H-L 可能被兩端離群值撐起)

輸出: analysis/output/decile_ls.json
"""
import argparse
import glob
import json
import os as _os
import sys as _sys

import numpy as np
import pandas as pd
import torch
from scipy.stats import spearmanr

_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _p in (_root, _os.path.join(_root, "core"), _os.path.join(_root, "test")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from model import ChartGCN                                   # noqa: E402
from data_loader import fetch_tw_stocks, TICKER_SETS         # noqa: E402
from run_paper_repro import load_ds_cache                    # noqa: E402

EXPDIR = _os.environ.get("CGCN_EXPDIR") or _os.path.join(_root, "experiments_paper")   # 2026 回測改指 experiments_2026
TDAYS = 246          # 2024 台股交易日數(年化用)


def cache_path(p):
    key = (f"{p['tickers']}{p.get('n_stocks', 0)}_{p['start']}_"
           f"{p['train_end']}_{p['end']}_w{p['window']}m{p['m_pips']}"
           f"N{p['N']}g{p['g']}s{p.get('stride', 1)}"
           f"{'_raw' if p.get('raw_features') else ''}")
    h = p.get("horizon", 1)
    if h != 1:
        key += f"_h{h}"
    return _os.path.join(EXPDIR, "dscache", key + "_test.npz")


@torch.no_grad()
def predict_proba(model, ds, batch_mode, device, batch_size=128):
    """回傳 softmax P(漲)。batch_mode 必須與訓練一致(attention 跨同批)。"""
    model.eval()
    if batch_mode == "date":
        batches = [np.asarray(v) for _, v in
                   sorted(ds.date_to_indices.items())]
    else:
        n = len(ds)
        batches = [np.arange(i, min(i + batch_size, n))
                   for i in range(0, n, batch_size)]
    out = np.zeros(len(ds), dtype=np.float64)
    for idx in batches:
        X = torch.from_numpy(ds.X[idx]).float().to(device)
        p = torch.softmax(model(X), dim=1)[:, 1].cpu().numpy()
        out[idx] = p
    return out


def forward_returns(price, meta, h):
    """每筆樣本自決策日起算的 h 交易日報酬;不足者 NaN。"""
    pos, cl = {}, {}
    r = np.full(len(meta), np.nan)
    for i, (tk, d) in enumerate(meta):
        if tk not in pos:
            df = price.get(tk)
            if df is None:
                continue
            pos[tk] = {dd: j for j, dd in enumerate(df.index)}
            cl[tk] = df["close"].values.astype(float)
        j = pos[tk].get(pd.Timestamp(d))
        c = cl[tk]
        if j is None or j + h >= len(c) or c[j] <= 0:
            continue
        r[i] = c[j + h] / c[j] - 1.0
    return r


def decile_analysis(dates, probs, rets, tickers, h, n_dec=10, min_n=30,
                    rng=None, tie_eps=1e-6, degen_std=0.01):
    """不重疊再平衡:每 h 個交易日排序一次。

    平手處理(2026-09-05 修正,見 §19 稽核第 1 項):
      原本 `np.argsort(p, kind="stable")` 在機率近乎常數時會保留輸入順序,
      而 ds.meta 依 (決策日, ticker) 排序 → 分位實際上等於「股票代碼字母序」,
      使全押同一邊的退化模型也得到非零 H-L(h5-elec_all-s44 prob_std 0.0008 → H-L +10.76%)。
      改為:先隨機打散再穩定排序(平手隨機分配),並統計「退化日」的比例。
      退化日定義:當日 P 的唯一值數 < n_dec,或 std < degen_std。
    """
    if rng is None:
        rng = np.random.default_rng(0)
    udates = sorted(set(dates))
    rebal = udates[::h]
    rows = []          # 每期各分位的平均報酬
    n_degen = n_used = 0
    for d in rebal:
        m = (dates == d) & np.isfinite(rets)
        if m.sum() < min_n:
            continue
        p, r = probs[m], rets[m]
        n_used += 1
        if len(np.unique(np.round(p / tie_eps))) < n_dec or p.std() < degen_std:
            n_degen += 1
        shuf = rng.permutation(len(p))           # 平手隨機打散
        order = shuf[np.argsort(p[shuf], kind="stable")]
        edges = np.linspace(0, len(p), n_dec + 1).astype(int)
        per = [float(r[order[edges[k]:edges[k + 1]]].mean())
               for k in range(n_dec)]
        rows.append(per + [float(r.mean())])     # 最後一欄 = 等權基準
    if not rows:
        return None
    A = np.asarray(rows)                          # (n_period, 11)
    ppy = TDAYS / h                               # 每年期數
    ann = A.mean(0) * ppy
    vol = A.std(0, ddof=1) * np.sqrt(ppy)
    sr = np.divide(ann, vol, out=np.zeros_like(ann), where=vol > 0)
    hl = A[:, n_dec - 1] - A[:, 0]
    hl_ann = hl.mean() * ppy
    hl_sr = hl.mean() / hl.std(ddof=1) * np.sqrt(ppy) if hl.std(ddof=1) > 0 else 0.0
    t = hl.mean() / (hl.std(ddof=1) / np.sqrt(len(hl))) if hl.std(ddof=1) > 0 else 0.0
    rho, rp = spearmanr(np.arange(n_dec), ann[:n_dec])
    return {
        "n_periods": len(rows), "h": h,
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


def null_distribution(dates, rets, h, reps=200, n_dec=10, min_n=30, seed=0):
    """零假設:機率完全隨機(無訊號)。回傳 H-L 年化報酬與單調 rho 的分佈。

    用途:把實測值放到這個分佈上看百分位,取代「有沒有超過門檻」的二分判定,
    並量化平手/小樣本造成的偽訊號規模(§19.3 實驗 C)。
    """
    rng = np.random.default_rng(seed)
    hls, rhos = [], []
    n = len(dates)
    for _ in range(reps):
        out = decile_analysis(dates, rng.random(n), rets, None, h,
                              n_dec=n_dec, min_n=min_n, rng=rng)
        if out:
            hls.append(out["hl_ann_ret_pct"])
            rhos.append(out["monotonic_spearman"])
    if not hls:
        return None
    hls, rhos = np.array(hls), np.array(rhos)
    return {"reps": len(hls),
            "hl_mean": round(float(hls.mean()), 2),
            "hl_sd": round(float(hls.std(ddof=1)), 2),
            "hl_p05": round(float(np.percentile(hls, 5)), 2),
            "hl_p95": round(float(np.percentile(hls, 95)), 2),
            "rho_sd": round(float(rhos.std(ddof=1)), 3),
            "rho_p05": round(float(np.percentile(rhos, 5)), 3),
            "rho_p95": round(float(np.percentile(rhos, 95)), 3)}


def _norm_pct(x, mu, sd):
    """實測值在零分佈中的位置(以常態近似的 z → 百分位)。"""
    from scipy.stats import norm
    return float(norm.cdf((x - mu) / sd)) if sd > 0 else 0.5


def run_one(exp_tag, horizons, device, null_reps=0):
    fp = glob.glob(_os.path.join(EXPDIR, f"*_{exp_tag}.json"))
    if not fp:
        print(f"[SKIP] 找不到 {exp_tag}.json")
        return None
    d = json.load(open(fp[0], encoding="utf-8"))
    p = d["params"]
    mp = fp[0][:-5] + "_model.pt"
    cp = cache_path(p)
    if not (_os.path.exists(mp) and _os.path.exists(cp)):
        print(f"[SKIP] {exp_tag}: model={_os.path.exists(mp)} "
              f"cache={_os.path.exists(cp)}")
        return None

    ds = load_ds_cache(cp)
    model = ChartGCN(N=p["N"], g=p["g"], F_dim=ds.X.shape[-1],
                     use_attention=not p.get("no_attention", False)
                     ).to(device)
    model.load_state_dict(torch.load(mp, map_location=device))
    probs = predict_proba(model, ds, p.get("batch_mode", "paper"), device)

    price = fetch_tw_stocks(tickers=TICKER_SETS[p["tickers"]],
                            start=p["start"], end=p["end"])
    dates = np.array([str(m[1])[:10] for m in ds.meta])
    tks = np.array([m[0] for m in ds.meta])

    res = {"exp": exp_tag, "params": {k: p.get(k) for k in
           ("tickers", "window", "m_pips", "N", "g", "horizon",
            "batch_mode", "seed")},
           "n_test": len(ds), "n_dates": len(set(dates)),
           "stocks_per_date": round(len(ds) / len(set(dates)), 1),
           "acc": round(d["metrics"]["acc"] * 100, 2),
           "f1_macro": round(d["f1_macro"] * 100, 2),
           "prob_mean": round(float(probs.mean()), 4),
           "prob_std": round(float(probs.std()), 4),
           "by_horizon": {}}
    for h in horizons:
        r = forward_returns(price, ds.meta, h)
        out = decile_analysis(dates, probs, r, tks, h,
                              rng=np.random.default_rng(20260905))
        if out:
            if null_reps:
                out["null"] = null_distribution(dates, r, h, reps=null_reps)
                if out["null"]:
                    nd = out["null"]
                    out["hl_null_pctile"] = round(100 * _norm_pct(
                        out["hl_ann_ret_pct"], nd["hl_mean"], nd["hl_sd"]), 1)
                    out["rho_null_pctile"] = round(100 * _norm_pct(
                        out["monotonic_spearman"], 0.0, nd["rho_sd"]), 1)
            res["by_horizon"][f"h{h}"] = out
            dr = out["decile_ann_ret_pct"]
            print(f"  [{exp_tag} h={h:2d}] 分位 {dr[0]:+.1f} … {dr[-1]:+.1f} | "
                  f"H-L {out['hl_ann_ret_pct']:+.2f}% SR {out['hl_sharpe']:+.2f} "
                  f"t={out['hl_t_stat']:+.2f} | 單調ρ={out['monotonic_spearman']:+.2f}"
                  f" | 基準 {out['bench_ann_ret_pct']:+.1f}%")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exps", default="sector-date-elec455,gridbest-s43,"
                                      "h5-elec_all-s42,h5-elec_all-s43,"
                                      "h5-elec_all-s44,w60-elec_all-s43")
    ap.add_argument("--horizons", default="1,5,20")
    ap.add_argument("--out", default="decile_ls.json")
    ap.add_argument("--null-reps", type=int, default=0,
                    help="每個 (exp,h) 跑幾次隨機機率零假設(§19.3 實驗 C);0 = 不跑")
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[DEVICE] {dev}")
    hs = [int(v) for v in a.horizons.split(",")]
    allres = []
    for tag in a.exps.split(","):
        print(f"\n=== {tag} ===")
        r = run_one(tag.strip(), hs, dev, null_reps=a.null_reps)
        if r:
            allres.append(r)
            od = _os.path.join(_root, "analysis", "output")
            _os.makedirs(od, exist_ok=True)
            with open(_os.path.join(od, a.out), "w", encoding="utf-8") as f:
                json.dump(allres, f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] analysis/output/{a.out}  ({len(allres)} 組)")


if __name__ == "__main__":
    main()
