"""
相似度比對檢驗 (老師建議; 實驗記錄 §十三).

問題: 「圖形相似的樣本, 未來是否也相似?」 — 不訓練模型, 直接用 k-NN 量.
  庫: 訓練期事件樣本 (2016-2023), 查詢: 測試期事件樣本 (2024).
  特徵: 子圖張量 X (10x4x9) 攤平成 360 維.
    norm=global: 以訓練集逐欄 z-score (跨股票尺度仍不同, 價格欄由大股主導)
    norm=sample: 每個樣本、每個指標欄在 40 個節點內 z-score → 只比「形狀」
  指標:
    agree      = 鄰居標籤與查詢標籤一致的比例
                 (對照: 獨立時期望值 p_te*p_tr + (1-p_te)(1-p_tr))
    vote_acc   = k 鄰居多數決準確率 (對照: floor = max(p,1-p));
                 事件日 block bootstrap CI
    perm       = 訓練標籤隨機置換 20 次後的 agree 分布 (label randomization 對照)
    same_tk    = 鄰居與查詢同一檔股票的比例; adj = 同檔且 |日期差| <= 5 日 (影本指標)
  對照: --calendar-contrast 在日曆取樣 (全部交易日) 子樣本上做同樣的事, 顯示影本效應.

輸出: analysis/output/knn_similarity.json
"""
import argparse
import json
import os as _os
import sys as _sys
import time

import numpy as np
from sklearn.neighbors import NearestNeighbors

_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _p in (_root, _os.path.join(_root, "core"), _os.path.join(_root, "test")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from event_data import build_event_sets, dscache_paths
from run_paper_repro import load_ds_cache


def featurize(X, norm, scaler=None):
    X = X.astype(np.float32)
    if norm == "sample":
        mu = X.mean(axis=(1, 2), keepdims=True)
        sd = X.std(axis=(1, 2), keepdims=True) + 1e-8
        return ((X - mu) / sd).reshape(len(X), -1), None
    F = X.reshape(len(X), -1)
    if scaler is None:
        scaler = (F.mean(0), F.std(0) + 1e-8)
    return (F - scaler[0]) / scaler[1], scaler


def knn_eval(Ftr, ytr, mtr, Fte, yte, mte, k, date_idx, rng, n_perm=20,
             n_boot=3000, self_idx=None):
    """self_idx: 查詢在庫中的索引 (within-library 模式, 排除自身)."""
    kq = k + 1 if self_idx is not None else k
    nn = NearestNeighbors(n_neighbors=kq, algorithm="brute", n_jobs=-1).fit(Ftr)
    _, idx = nn.kneighbors(Fte)
    if self_idx is not None:
        keep = idx != self_idx[:, None]
        idx = np.array([row[m][:k] for row, m in zip(idx, keep)])
    nb_y = ytr[idx]                                  # (n_te, k)
    agree = (nb_y == yte[:, None]).mean()
    vote = (nb_y.mean(1) > 0.5).astype(int)
    vote_acc = (vote == yte).mean()
    p_tr, p_te = ytr.mean(), yte.mean()
    chance = p_te * p_tr + (1 - p_te) * (1 - p_tr)
    floor = max(p_te, 1 - p_te)
    perm = []
    for _ in range(n_perm):
        ys = rng.permutation(ytr)
        perm.append(float((ys[idx] == yte[:, None]).mean()))
    tk_tr = np.array([m[0] for m in mtr])
    tk_te = np.array([m[0] for m in mte])
    d_tr = np.array([np.datetime64(m[1], "D") for m in mtr])
    d_te = np.array([np.datetime64(m[1], "D") for m in mte])
    same_tk = tk_tr[idx] == tk_te[:, None]
    ddiff = np.abs((d_tr[idx] - d_te[:, None]).astype(int))
    adj = same_tk & (ddiff <= 5)
    adj20 = same_tk & (ddiff <= 20)
    # block bootstrap (by test date) on vote_acc - floor
    dates = sorted(date_idx)
    n_d = np.array([len(date_idx[d]) for d in dates], float)
    c_d = np.array([(vote[date_idx[d]] == yte[date_idx[d]]).sum()
                    for d in dates], float)
    p_d = np.array([(yte[date_idx[d]] == 1).sum() for d in dates], float)
    gaps = []
    for _ in range(n_boot):
        b = rng.integers(0, len(dates), len(dates))
        n, c, p = n_d[b].sum(), c_d[b].sum(), p_d[b].sum()
        gaps.append(c / n - max(p / n, 1 - p / n))
    gaps = np.array(gaps)
    return {
        "n_lib": int(len(Ftr)), "n_query": int(len(Fte)), "k": k,
        "agree_pct": round(float(agree) * 100, 2),
        "agree_chance_pct": round(float(chance) * 100, 2),
        "agree_perm_mean_pct": round(float(np.mean(perm)) * 100, 2),
        "agree_perm_sd_pct": round(float(np.std(perm)) * 100, 2),
        "vote_acc_pct": round(float(vote_acc) * 100, 2),
        "floor_pct": round(float(floor) * 100, 2),
        "vote_gap_pp": round(float(vote_acc - floor) * 100, 2),
        "vote_gap_ci95": [round(float(np.percentile(gaps, 2.5)) * 100, 2),
                          round(float(np.percentile(gaps, 97.5)) * 100, 2)],
        "p_vote_above_floor": round(float((gaps > 0).mean()), 4),
        "vote_pos_pct": round(float(vote.mean()) * 100, 2),
        "same_ticker_pct": round(float(same_tk.mean()) * 100, 2),
        "same_ticker_adjacent5d_pct": round(float(adj.mean()) * 100, 2),
        "same_ticker_adjacent20d_pct": round(float(adj20.mean()) * 100, 2),
    }


def within_train(X, y, meta, k, rng, n_query, lib_size=None, norm="sample"):
    """訓練集內部 leave-one-out: 影本效應的正確量測 (查詢與庫同期)."""
    n = len(X)
    lib = (np.sort(rng.choice(n, min(lib_size, n), replace=False))
           if lib_size else np.arange(n))
    q = lib[np.sort(rng.choice(len(lib), min(n_query, len(lib)), replace=False))]
    F, sc = featurize(X[lib], norm)
    pos = {int(g): i for i, g in enumerate(lib)}
    qi = np.array([pos[int(g)] for g in q])
    mlib = [meta[i] for i in lib]
    mq = [meta[i] for i in q]
    date_idx = {}
    for j, m in enumerate(mq):
        date_idx.setdefault(str(m[1])[:10], []).append(j)
    return knn_eval(F, y[lib], mlib, F[qi], y[q], mq, k, date_idx, rng,
                    n_boot=500, self_idx=qi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="elec_all")
    ap.add_argument("--x", type=float, default=0.05)
    ap.add_argument("--up", type=float, default=0.05)
    ap.add_argument("--dn", type=float, default=0.05)
    ap.add_argument("--T", type=int, default=20)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--calendar-contrast", action="store_true")
    ap.add_argument("--cal-lib", type=int, default=100000)
    ap.add_argument("--cal-query", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    out = {"params": vars(args), "event": {}, "calendar": {}}

    t0 = time.time()
    tr_tb, te_tb, stats, _ = build_event_sets(
        tickers=args.tickers, x=args.x, up=args.up, dn=args.dn, T=args.T,
        label="tb")
    tr_nd, te_nd, _, _ = build_event_sets(
        tickers=args.tickers, x=args.x, label="nextday", verbose=False)
    out["event_stats"] = stats

    # 對齊同一事件集合 (tb 丟掉尾端不足 T 日者)
    def align(ds_ref, ds_other):
        pos = {m: i for i, m in enumerate(ds_other.meta)}
        idx = np.array([pos[m] for m in ds_ref.meta])
        return ds_other.y[idx]
    ytr = {"tb": tr_tb.y, "nextday": align(tr_tb, tr_nd)}
    yte = {"tb": te_tb.y, "nextday": align(te_tb, te_nd)}
    print(f"[KNN] 事件樣本 lib={len(tr_tb)} query={len(te_tb)} "
          f"({time.time()-t0:.0f}s)")

    for norm in ["sample", "global"]:
        Ftr, sc = featurize(tr_tb.X, norm)
        Fte, _ = featurize(te_tb.X, norm, sc)
        for lab in ["tb", "nextday"]:
            t1 = time.time()
            r = knn_eval(Ftr, ytr[lab], tr_tb.meta, Fte, yte[lab], te_tb.meta,
                         args.k, te_tb.date_to_indices, rng)
            out["event"][f"{norm}/{lab}"] = r
            print(f"[EVENT {norm:6s} {lab:7s}] agree {r['agree_pct']}% "
                  f"(chance {r['agree_chance_pct']}%, perm "
                  f"{r['agree_perm_mean_pct']}+-{r['agree_perm_sd_pct']}%) | "
                  f"vote {r['vote_acc_pct']}% vs floor {r['floor_pct']}% "
                  f"gap {r['vote_gap_pp']:+.2f}pp CI {r['vote_gap_ci95']} | "
                  f"same_tk {r['same_ticker_pct']}% adj5d "
                  f"{r['same_ticker_adjacent5d_pct']}%  ({time.time()-t1:.0f}s)")

    # 訓練集內部 (同期) — 影本效應
    out["within_train"] = {}
    for lab in ["tb", "nextday"]:
        r = within_train(tr_tb.X, ytr[lab], tr_tb.meta, args.k, rng,
                         n_query=8000)
        out["within_train"][f"event/{lab}"] = r
        print(f"[WITHIN event {lab:7s}] agree {r['agree_pct']}% "
              f"(chance {r['agree_chance_pct']}%, perm "
              f"{r['agree_perm_mean_pct']}+-{r['agree_perm_sd_pct']}%) | "
              f"same_tk {r['same_ticker_pct']}% adj5d "
              f"{r['same_ticker_adjacent5d_pct']}% adj20d "
              f"{r['same_ticker_adjacent20d_pct']}%")

    if args.calendar_contrast:
        tr_p, te_p = dscache_paths(args.tickers, "2016-01-01", "2023-12-31",
                                   "2024-12-31")
        src_tr, src_te = load_ds_cache(tr_p), load_ds_cache(te_p)
        r = within_train(src_tr.X, src_tr.y, src_tr.meta, args.k, rng,
                         n_query=8000, lib_size=args.cal_lib)
        out["within_train"]["calendar/nextday"] = r
        print(f"[WITHIN cal   nextday] agree {r['agree_pct']}% "
              f"(chance {r['agree_chance_pct']}%, perm "
              f"{r['agree_perm_mean_pct']}+-{r['agree_perm_sd_pct']}%) | "
              f"same_tk {r['same_ticker_pct']}% adj5d "
              f"{r['same_ticker_adjacent5d_pct']}% adj20d "
              f"{r['same_ticker_adjacent20d_pct']}%")
        li = np.sort(rng.choice(len(src_tr), min(args.cal_lib, len(src_tr)),
                                replace=False))
        qi = np.sort(rng.choice(len(src_te), min(args.cal_query, len(src_te)),
                                replace=False))
        mtr = [src_tr.meta[i] for i in li]
        mte = [src_te.meta[i] for i in qi]
        date_idx = {}
        for j, m in enumerate(mte):
            date_idx.setdefault(str(m[1])[:10], []).append(j)
        for norm in ["sample", "global"]:
            Ftr, sc = featurize(src_tr.X[li], norm)
            Fte, _ = featurize(src_te.X[qi], norm, sc)
            t1 = time.time()
            r = knn_eval(Ftr, src_tr.y[li], mtr, Fte, src_te.y[qi], mte,
                         args.k, date_idx, rng)
            out["calendar"][f"{norm}/nextday"] = r
            print(f"[CAL   {norm:6s} nextday] agree {r['agree_pct']}% "
                  f"(chance {r['agree_chance_pct']}%) | vote "
                  f"{r['vote_acc_pct']}% vs floor {r['floor_pct']}% "
                  f"gap {r['vote_gap_pp']:+.2f}pp | same_tk "
                  f"{r['same_ticker_pct']}% adj5d "
                  f"{r['same_ticker_adjacent5d_pct']}%  ({time.time()-t1:.0f}s)")

    od = _os.path.join(_root, "analysis", "output")
    _os.makedirs(od, exist_ok=True)
    with open(_os.path.join(od, "knn_similarity.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"[SAVED] analysis/output/knn_similarity.json  "
          f"total {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
