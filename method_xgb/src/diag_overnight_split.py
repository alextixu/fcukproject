"""第 1 步診斷:特徵的預測力落在「隔夜段 close[t]→open[t+1]」還是「可交易段 open[t+1]→open[t+6]」。不訓練模型。

  判準與範圍見 docs/2026-09-21_第1步_隔夜段與可交易段拆解_事前登記與結果.md(事前登記,不可事後更動)。
  每日橫斷面:特徵→當日排名→標準化;兩段對數報酬各自減當日平均;斜率 = mean(z * r)。兩段斜率相加 = 總報酬斜率。
  t 值:每日斜率序列的移動區塊 bootstrap(2000 次,區塊 10 / 20 天)。

輸出 experiments/diag_overnight_split_tw50.csv
"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import norm

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, R)
from common import paths as P

TAG = "x26-tw50-h5-cs"
H, MIN_N, NBOOT, COST_BP = 5, 30, 2000, 58.5
PRIMARY = "close_pos"

x = json.load(open(os.path.join(P.XGB_EXP, f"{TAG}.json"), encoding="utf-8"))
cfg = x["config"]
FEATS = [f for f in x["results"]["full_top20"]["features"] if not f.startswith("mkt_")]
panel = pd.read_parquet(os.path.join(P.FEATURES, f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}.parquet"),
                        columns=FEATS + ["open", "close"])
op, cl = panel["open"].astype("float64").unstack("ticker"), panel["close"].astype("float64").unstack("ticker")
seg = {"on": np.log(op.shift(-1) / cl), "tr": np.log(op.shift(-(H + 1)) / op.shift(-1))}
tr_simple = op.shift(-(H + 1)) / op.shift(-1) - 1
assert np.allclose((seg["on"] + seg["tr"]).values, np.log(op.shift(-(H + 1)) / cl).values, atol=1e-9, equal_nan=True)


def block_t(s: np.ndarray, block: int, seed=0):
    rng = np.random.default_rng(seed); n = len(s); k = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(NBOOT, k))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(NBOOT, -1)[:, :n]
    se = s[idx].mean(axis=1).std(ddof=1)
    return s.mean() / se


def daily(feat: str):
    F = panel[feat].unstack("ticker")
    ok = F.notna() & seg["on"].notna() & seg["tr"].notna()
    ok = ok & (ok.sum(axis=1) >= MIN_N).values[:, None]
    Fz = F.where(ok).rank(axis=1)
    Fz = Fz.sub(Fz.mean(axis=1), axis=0).div(Fz.std(axis=1, ddof=0), axis=0)
    out = {}
    for k, r in seg.items():
        rd = r.where(ok); rd = rd.sub(rd.mean(axis=1), axis=0)
        out[k] = (Fz * rd).mean(axis=1)
    ex = tr_simple.where(ok); ex = ex.sub(ex.mean(axis=1), axis=0)
    d = pd.DataFrame(out).dropna()
    return d, Fz, ex


rows = []
for feat in FEATS:
    d, Fz, ex = daily(feat)
    for name, m in (("2016-2025", d.index.year <= 2025), ("2026", d.index.year == 2026)):
        s = d[m]
        if len(s) < 60: continue
        on, tr = s["on"].values, s["tr"].values; tot = on + tr
        sign = np.sign(tot.mean())
        rk = (Fz * sign).loc[s.index].rank(axis=1, ascending=False)
        top = ex.loc[s.index].where(rk <= 10).mean(axis=1).dropna().values * 1e4
        same = np.sign(on.mean()) == np.sign(tr.mean())
        rows.append({"feature": feat, "period": name, "role": "primary" if feat == PRIMARY else "exploratory", "n_days": len(s),
                     "slope_on_bp": on.mean() * 1e4, "slope_tr_bp": tr.mean() * 1e4, "slope_total_bp": tot.mean() * 1e4,
                     "t_on_b10": block_t(on, 10), "t_tr_b10": block_t(tr, 10), "t_tr_b20": block_t(tr, 20), "t_total_b10": block_t(tot, 10),
                     "overnight_share": on.mean() / tot.mean() if same else np.nan,
                     "top10_excess_tr_bp": top.mean(), "t_top10_b10": block_t(top, 10), "beats_cost": bool(top.mean() > COST_BP)})
res = pd.DataFrame(rows)
main = res[(res.period == "2016-2025") & (res.role == "exploratory")].copy()
p = 2 * norm.sf(main["t_tr_b10"].abs()); order = np.argsort(p); m = len(p)
adj = np.minimum(1, np.maximum.accumulate((m - np.arange(m)) * p[order])); holm = np.empty(m); holm[order] = adj
res.loc[main.index, "p_tr_holm"] = holm
res.to_csv(os.path.join(P.XGB_EXP, "diag_overnight_split_tw50.csv"), index=False)
pd.set_option("display.width", 250)
print(res.round(3).to_string(index=False))
