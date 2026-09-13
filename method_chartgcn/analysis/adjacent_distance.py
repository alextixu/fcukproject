"""
相鄰日樣本在模型輸入空間 (X, 10x4x9, 每樣本 z-score) 的距離 vs. k-NN 距離.

問題: §12.1 顯示相鄰日子圖錨點重疊 7-8/10, 但 k-NN 顯示同檔 ±5 日幾乎不是最近鄰.
這裡直接量: 對隨機 2,000 個訓練樣本, 找同檔「隔 1 / 5 / 20 個交易日」的樣本,
計算歐氏距離, 與該樣本在 10 萬庫中的第 1 / 第 20 近鄰距離比較.
同時量「槽位不變量」距離: 把 10 個子圖視為集合 (對槽位排序不敏感) 的最佳配對距離,
看槽位重排是否是造成「相鄰日看起來很遠」的主因.

輸出: analysis/output/adjacent_distance.json
"""
import json
import os as _os
import sys as _sys
import time

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.neighbors import NearestNeighbors

_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _p in (_root, _os.path.join(_root, "core"), _os.path.join(_root, "test")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from event_data import dscache_paths
from run_paper_repro import load_ds_cache


def znorm(X):
    mu = X.mean(axis=(1, 2), keepdims=True)
    sd = X.std(axis=(1, 2), keepdims=True) + 1e-8
    return (X - mu) / sd


def set_distance(a, b):
    """槽位不變: 10 個子圖 (各 36 維) 的最佳一對一配對距離."""
    A, B = a.reshape(10, -1), b.reshape(10, -1)
    C = np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(-1))
    r, c = linear_sum_assignment(C)
    return float(np.sqrt((C[r, c] ** 2).sum()))


def main():
    rng = np.random.default_rng(0)
    t0 = time.time()
    tr_p, _ = dscache_paths("elec_all", "2016-01-01", "2023-12-31",
                            "2024-12-31")
    src = load_ds_cache(tr_p)
    print(f"[LOAD] {len(src)} samples ({time.time()-t0:.0f}s)")

    # 同檔依日期排序的索引
    by_tk = {}
    for i, (tk, d) in enumerate(src.meta):
        by_tk.setdefault(tk, []).append((d, i))
    for tk in by_tk:
        by_tk[tk].sort()
    pos_in_tk = {}
    for tk, lst in by_tk.items():
        for p, (_, i) in enumerate(lst):
            pos_in_tk[i] = (tk, p)

    lib = np.sort(rng.choice(len(src), 100000, replace=False))
    Xz = znorm(src.X.astype(np.float32))
    F_lib = Xz[lib].reshape(len(lib), -1)
    nn = NearestNeighbors(n_neighbors=20, algorithm="brute", n_jobs=-1).fit(F_lib)

    q = rng.choice(len(src), 2000, replace=False)
    Fq = Xz[q].reshape(len(q), -1)
    dist, _ = nn.kneighbors(Fq)
    d1, d20 = dist[:, 0], dist[:, -1]

    res = {"n_query": int(len(q)), "lib": int(len(lib)),
           "nn1_median": float(np.median(d1)),
           "nn20_median": float(np.median(d20))}
    for lag in [1, 5, 20]:
        eu, st, rank_lt_nn1, rank_lt_nn20 = [], [], [], []
        for j, i in enumerate(q):
            tk, p = pos_in_tk[i]
            lst = by_tk[tk]
            if p + lag >= len(lst):
                continue
            i2 = lst[p + lag][1]
            d = float(np.linalg.norm(Fq[j] - Xz[i2].reshape(-1)))
            eu.append(d)
            st.append(set_distance(Xz[i], Xz[i2]))
            rank_lt_nn1.append(d < d1[j])
            rank_lt_nn20.append(d < d20[j])
        eu, st = np.array(eu), np.array(st)
        res[f"lag{lag}"] = {
            "n": int(len(eu)),
            "euclid_median": float(np.median(eu)),
            "euclid_over_nn20_median": float(np.median(eu / d20[:len(eu)]))
            if len(eu) else None,
            "set_dist_median": float(np.median(st)),
            "pct_closer_than_nn1": round(float(np.mean(rank_lt_nn1)) * 100, 1),
            "pct_closer_than_nn20": round(float(np.mean(rank_lt_nn20)) * 100, 1),
        }
        print(f"[LAG {lag:2d}] euclid median {np.median(eu):.1f} "
              f"(nn1 {np.median(d1):.1f}, nn20 {np.median(d20):.1f}) | "
              f"set-dist median {np.median(st):.1f} | "
              f"closer than nn1: {res[f'lag{lag}']['pct_closer_than_nn1']}%, "
              f"than nn20: {res[f'lag{lag}']['pct_closer_than_nn20']}%")

    # 對照: 隨機配對 (不同股票) 的歐氏與集合距離
    r1 = rng.choice(len(src), 500, replace=False)
    r2 = rng.choice(len(src), 500, replace=False)
    eu_r = [float(np.linalg.norm((Xz[a] - Xz[b]).reshape(-1))) for a, b in zip(r1, r2)]
    st_r = [set_distance(Xz[a], Xz[b]) for a, b in zip(r1, r2)]
    res["random_pair"] = {"euclid_median": float(np.median(eu_r)),
                          "set_dist_median": float(np.median(st_r))}
    print(f"[RANDOM] euclid median {np.median(eu_r):.1f} | "
          f"set-dist median {np.median(st_r):.1f}")

    od = _os.path.join(_root, "analysis", "output")
    _os.makedirs(od, exist_ok=True)
    with open(_os.path.join(od, "adjacent_distance.json"), "w",
              encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print(f"[SAVED] analysis/output/adjacent_distance.json ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
