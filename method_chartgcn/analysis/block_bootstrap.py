# -*- coding: utf-8 -*-
"""以交易日為區塊的 bootstrap 95% CI — elec_all h=1 最佳實驗測試集.
前置: 先跑 analysis/span_vs_perf.py 產生 output/span_vs_perf.npz.
結果 (2026-08-11 首跑): Acc 51.29% CI [48.81, 53.71]; Acc−全押跌地板 −3.79pp
CI [−7.27, −0.36], P(高於地板)=1.5%; SE 膨脹 8.1×, 有效樣本數 ≈ 1,599."""
import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "test"))
from run_paper_repro import load_ds_cache

z = np.load(os.path.join(ROOT, "analysis", "output", "span_vs_perf.npz"))
y, p = z["y"], z["pred"]
te = load_ds_cache(os.path.join(ROOT, "experiments_paper", "dscache",
                                "elec_all0_2016-01-01_2023-12-31_2024-12-31"
                                "_w140m80N10g4s1_raw_test.npz"))
assert len(te) == len(y), "順序對齊失敗"
dates = np.array([str(d)[:10] for _, d in te.meta])
udates = np.unique(dates)
print(f"samples={len(y)}, 交易日={len(udates)}")

counts = []
for d in udates:
    m = dates == d
    yd, pd_ = y[m], p[m]
    counts.append([m.sum(), (yd == pd_).sum(),
                   ((pd_ == 1) & (yd == 1)).sum(), ((pd_ == 1) & (yd == 0)).sum(),
                   ((pd_ == 0) & (yd == 1)).sum(), ((pd_ == 0) & (yd == 0)).sum(),
                   (yd == 1).sum()])
C = np.array(counts, dtype=np.float64)

rng = np.random.default_rng(42)
B, D = 10000, len(udates)
acc_bs = np.empty(B); f1m_bs = np.empty(B); floor_bs = np.empty(B)
for b in range(B):
    s = C[rng.integers(0, D, D)].sum(0)
    n, correct, tp, fp, fn, tn, pos = s
    acc_bs[b] = correct / n
    pr1 = tp / (tp + fp) if tp + fp else 0
    rc1 = tp / (tp + fn) if tp + fn else 0
    f11 = 2 * pr1 * rc1 / (pr1 + rc1) if pr1 + rc1 else 0
    pr0 = tn / (tn + fn) if tn + fn else 0
    rc0 = tn / (tn + fp) if tn + fp else 0
    f10 = 2 * pr0 * rc0 / (pr0 + rc0) if pr0 + rc0 else 0
    f1m_bs[b] = (f11 + f10) / 2
    floor_bs[b] = max(pos, n - pos) / n

ci = lambda a: np.percentile(a, [2.5, 97.5])
acc_pt = (y == p).mean()
excess = acc_bs - floor_bs
print(f"Acc {acc_pt*100:.2f}%  CI [{ci(acc_bs)[0]*100:.2f}, {ci(acc_bs)[1]*100:.2f}]")
print(f"F1m CI [{ci(f1m_bs)[0]*100:.2f}, {ci(f1m_bs)[1]*100:.2f}]")
print(f"Acc−地板 {acc_pt*100-55.08:.2f}pp CI [{ci(excess)[0]*100:.2f}, "
      f"{ci(excess)[1]*100:.2f}]  P(Acc>地板)={np.mean(excess > 0)*100:.1f}%")
print(f"P(Acc>50%)={np.mean(acc_bs > .5)*100:.1f}%")
se_b, se_n = acc_bs.std(), np.sqrt(acc_pt * (1 - acc_pt) / len(y))
print(f"SE 膨脹 {se_b/se_n:.1f}× → 有效樣本數 ≈ {len(y)/(se_b/se_n)**2:,.0f} "
      f"(名目 {len(y):,})")
