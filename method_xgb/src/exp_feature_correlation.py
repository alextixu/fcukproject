"""242 欄特徵的關聯性:Spearman |ρ| + 階層分群(平均連結),看不同門檻下分成幾組。不訓練模型。

  資料: features_top100 面板,2016 ~ 2025(2026 不用),隨機抽 80,000 列,兩兩用都有值的列計算。
  輸出: experiments/feature_corr_top100.parquet(242×242 的 |ρ|)、feature_groups_top100.csv(每欄在各門檻下的組別)
"""
import os, sys
import numpy as np, pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, R)
from common import paths as P

cat = pd.read_csv(os.path.join(R, "method_xgb", "config", "feature_catalog_top100.csv")); F = cat.name.tolist()
p = pd.read_parquet(os.path.join(P.FEATURES, "features_top100_2016-01-01_2026-09-11.parquet"), columns=F)
p = p[p.index.get_level_values("date") <= pd.Timestamp("2025-12-31")].sample(80000, random_state=0)
const = [f for f in F if p[f].nunique(dropna=True) < 2]
corr = p.rank().corr(min_periods=5000).abs().fillna(0.0)
np.fill_diagonal(corr.values, 1.0)
corr.to_parquet(os.path.join(P.XGB_EXP, "feature_corr_top100.parquet"))
Z = linkage(squareform(1 - corr.values, checks=False), method="average")
THR = [0.95, 0.9, 0.8, 0.7, 0.6, 0.5]
g = pd.DataFrame({"feature": F, "family": cat.family.values})
for t in THR:
    g[f"g{int(t*100)}"] = fcluster(Z, 1 - t, criterion="distance")
g.to_csv(os.path.join(P.XGB_EXP, "feature_groups_top100.csv"), index=False)
print("常數欄:", const)
for t in THR:
    s = g[f"g{int(t*100)}"].value_counts()
    print(f"|ρ| ≥ {t}: {len(s):3d} 組;單獨一欄的 {int((s==1).sum()):3d} 組;最大組 {int(s.max()):2d} 欄;≥5 欄的組 {int((s>=5).sum())} 個")
