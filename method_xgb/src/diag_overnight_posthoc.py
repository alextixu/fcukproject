"""第 1 步的事後探索分析 A~E(2026-09-21 審查後追加;不訓練模型)。**事後探索,結論只能用來修正第 2 步的假設,不能當判定。**

  A 方向與定義:前 10 檔一律依預期報酬方向取(總報酬斜率的符號);adx_28 另列帶方向的 di_diff_28 = pdi_28 − mdi_28。
  B 報酬分布:前 10 檔可交易段超額報酬的平均 / 中位數 / 複利年化(5 條錯開的不重疊序列取平均)。
  C 扣市場暴露:beta 用過去 250 天收盤報酬對等權市場估(只用 t 以前),報酬扣掉 beta × 當期市場報酬後重算。
  D 因子結構:趨勢 3 + 波動 8 + beta_250 的每日橫斷面 Spearman,取日平均。
  E 時間穩定性:2016–2020、2021–2025 分開。

輸出 experiments/diag_overnight_posthoc_tw50.csv、diag_overnight_posthoc_corr_tw50.csv
"""
import os, sys, json
import numpy as np, pandas as pd

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, R)
from common import paths as P

TAG, H, MIN_N, NBOOT = "x26-tw50-h5-cs", 5, 30, 2000
x = json.load(open(os.path.join(P.XGB_EXP, f"{TAG}.json"), encoding="utf-8")); cfg = x["config"]
BASE = [f for f in x["results"]["full_top20"]["features"] if not f.startswith("mkt_")]
panel = pd.read_parquet(os.path.join(P.FEATURES, f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}.parquet"),
                        columns=BASE + ["pdi_28", "mdi_28", "open", "close"])
panel["di_diff_28"] = panel["pdi_28"] - panel["mdi_28"]
FEATS = BASE + ["di_diff_28", "pdi_28", "mdi_28"]
TREND = ["adx_28", "cs_excess_roc_120", "ema_ratio_120"]
VOL = ["ret_std_120", "gk_vol_20", "parkinson_10", "bb_bw_20", "atr_ratio_28", "cs_idio_std_60", "cs_rank_ret_std_60", "cs_beta_60"]

op, cl = panel["open"].astype("float64").unstack("ticker"), panel["close"].astype("float64").unstack("ticker")
on_s, tr_s = op.shift(-1) / cl - 1, op.shift(-(H + 1)) / op.shift(-1) - 1
r1 = cl.pct_change(); mkt1 = r1.mean(axis=1)
beta = r1.rolling(250, min_periods=120).cov(mkt1).div(mkt1.rolling(250, min_periods=120).var(), axis=0)
adj = lambda s: s.sub(beta.mul(s.mean(axis=1), axis=0))
SEG = {"raw": (np.log1p(on_s), np.log1p(tr_s), tr_s),
       "beta_adj": (np.log1p(adj(on_s).clip(lower=-0.99)), np.log1p(adj(tr_s).clip(lower=-0.99)), adj(tr_s))}


def block_t(s, block=10, seed=0):
    s = np.asarray(s, float); n = len(s); rng = np.random.default_rng(seed); k = int(np.ceil(n / block))
    st = rng.integers(0, n - block + 1, size=(NBOOT, k))
    idx = (st[:, :, None] + np.arange(block)[None, None, :]).reshape(NBOOT, -1)[:, :n]
    return s.mean() / s[idx].mean(axis=1).std(ddof=1)


def ann_compound(port: pd.Series):
    """5 日持有報酬的複利年化:5 條錯開的不重疊序列各自複利,再取平均。"""
    out = []
    for k in range(H):
        s = port.iloc[k::H].dropna()
        if len(s) > 10: out.append((1 + s).prod() ** (250 / (H * len(s))) - 1)
    return float(np.mean(out))


rows = []
for feat in FEATS:
    F = panel[feat].unstack("ticker")
    for mode, (lon, ltr, str_) in SEG.items():
        ok = F.notna() & lon.notna() & ltr.notna(); ok = ok & (ok.sum(axis=1) >= MIN_N).values[:, None]
        z = F.where(ok).rank(axis=1); z = z.sub(z.mean(axis=1), axis=0).div(z.std(axis=1, ddof=0), axis=0)
        dm = lambda r: r.where(ok).sub(r.where(ok).mean(axis=1), axis=0)
        d = pd.DataFrame({"on": (z * dm(lon)).mean(axis=1), "tr": (z * dm(ltr)).mean(axis=1)}).dropna()
        d = d[d.index.year <= 2025]
        sign = np.sign((d.on + d.tr).mean())
        rk = (z * sign).rank(axis=1, ascending=False)
        top_ret = str_.where(ok).where(rk <= 10).mean(axis=1); uni_ret = str_.where(ok).mean(axis=1)
        for name, m in (("2016-2025", d.index.year >= 2016), ("2016-2020", d.index.year <= 2020), ("2021-2025", d.index.year >= 2021)):
            s = d[m]; ex = (top_ret - uni_ret).loc[s.index].dropna()
            mean_bp, med_bp, t_ex = ex.mean() * 1e4, ex.median() * 1e4, block_t(ex.values)
            rows.append({"feature": feat, "mode": mode, "period": name, "direction": "高→漲" if sign > 0 else "低→漲", "n_days": len(s),
                         "slope_on_bp": s.on.mean() * 1e4, "slope_tr_bp": s.tr.mean() * 1e4, "t_on": block_t(s.on.values), "t_tr": block_t(s.tr.values),
                         "top10_mean_bp": mean_bp, "top10_median_bp": med_bp, "t_top10": t_ex,
                         "top10_ann_compound_pct": (ann_compound(top_ret.loc[s.index]) - ann_compound(uni_ret.loc[s.index])) * 100,
                         "right_tail": bool(abs(t_ex) >= 2 and med_bp < mean_bp / 3)})
res = pd.DataFrame(rows); res.to_csv(os.path.join(P.XGB_EXP, "diag_overnight_posthoc_tw50.csv"), index=False)

G = TREND + VOL; W = {f: panel[f].unstack("ticker") for f in G}; W["beta_250"] = beta; G = G + ["beta_250"]
days = [d for d in cl.index if 2016 <= d.year <= 2025][::5]
acc = np.zeros((len(G), len(G))); n = 0
for d in days:
    df = pd.DataFrame({g: W[g].loc[d] for g in G}).dropna()
    if len(df) >= MIN_N: acc += df.rank().corr().values; n += 1
corr = pd.DataFrame(acc / n, index=G, columns=G); corr.to_csv(os.path.join(P.XGB_EXP, "diag_overnight_posthoc_corr_tw50.csv"))

pd.set_option("display.width", 260); pd.set_option("display.max_rows", 400)
show = ["feature", "direction", "slope_on_bp", "slope_tr_bp", "t_tr", "top10_mean_bp", "top10_median_bp", "t_top10", "top10_ann_compound_pct", "right_tail"]
for mode in ("raw", "beta_adj"):
    print(f"\n=== {mode} 2016-2025 ==="); print(res[(res["mode"] == mode) & (res.period == "2016-2025")][show].round(2).to_string(index=False))
print("\n=== E 分期(raw):slope_tr_bp / t_tr / top10_mean_bp ===")
e = res[(res["mode"] == "raw") & (res.period != "2016-2025")].pivot(index="feature", columns="period", values=["slope_tr_bp", "t_tr", "top10_mean_bp"]).round(2)
print(e.loc[FEATS].to_string())
print("\n=== E 分期(beta_adj):slope_tr_bp / t_tr ===")
e2 = res[(res["mode"] == "beta_adj") & (res.period != "2016-2025")].pivot(index="feature", columns="period", values=["slope_tr_bp", "t_tr", "top10_mean_bp"]).round(2)
print(e2.loc[FEATS].to_string())
print(f"\n=== D 每日橫斷面 Spearman 日平均({n} 天)==="); print(corr.round(2).to_string())
