"""把 65 個新特徵和 162 個代表合併,再做一次 |ρ| ≥ 0.9 的相關過濾(Spearman、平均連結),確認新舊之間沒有新的雙胞胎。不訓練模型。

輸出 experiments/feature_corr_v2.parquet、feature_set_v2_g90.csv(合併後每組的代表與成員)
"""
import os, sys
import numpy as np, pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "method_xgb", "src"))
from common import paths as P
from features.lookback import required_rows

OLD = pd.read_csv(os.path.join(P.XGB_EXP, "feature_representatives_g90.csv")).representative.tolist()
xc = pd.read_csv(os.path.join(R, "method_xgb", "config", "feature_catalog_top100_extra.csv")); NEW = xc.name.tolist(); newfam = dict(zip(xc.name, xc.family))
oc = pd.read_csv(os.path.join(R, "method_xgb", "config", "feature_catalog_top100.csv")); oldfam = dict(zip(oc.name, oc.family))
a = pd.read_parquet(os.path.join(P.FEATURES, "features_top100_2016-01-01_2026-09-11.parquet"), columns=OLD)
b = pd.read_parquet(os.path.join(P.FEATURES, "features_top100_extra_2016-01-01_2026-09-11.parquet"))
p = pd.concat([a, b], axis=1); F = OLD + NEW
p = p[p.index.get_level_values("date") <= pd.Timestamp("2025-12-31")].sample(80000, random_state=0)
corr = p.rank().corr(min_periods=5000).abs().fillna(0.0); np.fill_diagonal(corr.values, 1.0)
corr.to_parquet(os.path.join(P.XGB_EXP, "feature_corr_v2.parquet"))
gid = fcluster(linkage(squareform(1 - corr.values, checks=False), method="average"), 0.1, criterion="distance")


def lb(f):
    if f in oldfam: return required_rows(f)
    import re; n = [int(x) for x in re.findall(r"\d+", f)]; return (max(n) if n else 1) + 1


rows = []
for g in np.unique(gid):
    n = [f for f, k in zip(F, gid) if k == g]
    if len(n) == 1: rep, cen = n[0], np.nan
    else:
        sub = corr.loc[n, n]; mr = (sub.sum(axis=1) - 1) / (len(n) - 1); cand = mr[mr >= mr.max() - 0.005].index.tolist()
        rep = sorted(cand, key=lambda x: (lb(x), x))[0]; cen = float(mr[rep])
    rows.append({"group": int(g), "size": len(n), "representative": rep, "rep_is_new": rep in newfam, "family": newfam.get(rep) or oldfam[rep],
                 "n_old": sum(f in oldfam for f in n), "n_new": sum(f in newfam for f in n), "rep_mean_corr": cen, "members": "、".join(n)})
out = pd.DataFrame(rows).sort_values(["size"], ascending=False); out.to_csv(os.path.join(P.XGB_EXP, "feature_set_v2_g90.csv"), index=False)
print(f"合併 {len(OLD)} + {len(NEW)} = {len(F)} 欄 → {len(out)} 組")
print("舊代表 162 欄裡仍是代表的:", int((~out.rep_is_new).sum()), ";新特徵當代表的:", int(out.rep_is_new.sum()), "(", out[out.rep_is_new].family.value_counts().to_dict(), ")")
mix = out[(out.n_old > 0) & (out.n_new > 0)]; nn = out[(out.n_old == 0) & (out["size"] > 1)]; oo = out[(out.n_new == 0) & (out["size"] > 1)]
print(f"\n新舊混在一起的組 {len(mix)} 個:"); [print(f"   [{r['size']}] 代表 {r.representative}:{r.members}") for _, r in mix.iterrows()]
print(f"\n新特徵彼此成組的 {len(nn)} 個:"); [print(f"   [{r['size']}] 代表 {r.representative}:{r.members}") for _, r in nn.iterrows()]
print(f"\n舊代表彼此成組的 {len(oo)} 個:"); [print(f"   [{r['size']}] 代表 {r.representative}:{r.members}") for _, r in oo.iterrows()]
cx = corr.loc[NEW, OLD]; top = cx.stack().sort_values(ascending=False).head(15)
print("\n新特徵 vs 舊代表,|ρ| 最高的 15 對:"); [print(f"   {i[0]:24s} {i[1]:22s} {v:.3f}") for i, v in top.items()]
reps = out.representative.tolist(); sub = corr.loc[reps, reps].values; off = sub[np.triu_indices(len(reps), 1)]
print(f"\n最終 {len(reps)} 個代表彼此 |ρ|:最大 {off.max():.3f};> 0.9 的 {int((off>0.9).sum())} 對;> 0.8 的 {int((off>0.8).sum())} 對;中位 {np.median(off):.3f}")
lone = cx.max(axis=1).sort_values(); print("和所有舊代表都不像(最高 |ρ| < 0.3)的新特徵:", lone[lone < 0.3].round(2).to_dict())
