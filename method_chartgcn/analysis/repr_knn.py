"""
表示法差分檢驗 (老師的相似度比對, 多面向版; 實驗記錄 §十七).

問題: Chart GCN 管線的哪一步破壞了「圖形相似 → 未來相似」?

三個表示法, 同一批樣本 / 同一組標籤 / 同一個 k-NN 程序, 唯一變因是輸入:
  R0 raw   原始技術指標序列     (140, 9) = 1260 維
  R1 pip   PIP 抽點後            (80,  9) =  720 維
  R2 sub   VG + 子圖 (現行輸入)  (10,4,9) =  360 維

  R0 → R1 差距 = PIP 抽點丟掉的
  R1 → R2 差距 = VG + 子圖切分/排序丟掉的

兩階段執行 (避免三份表示法同時常駐):
  stage=build  建構並存到 analysis/cache_repr/*.npy, 然後行程結束
  stage=knn    以 mmap 逐一載入單一表示法跑 k-NN
  stage=all    依序做完 (build 之後手動釋放)

面向:
  正規化  sample (每樣本每指標欄 z-score, 只比形狀) / global (訓練集逐欄 z-score)
  k       5 / 20 / 50
  標籤    tb (triple-barrier) / nextday
  指標    agree (鄰居標籤一致率) — 主指標, 以標籤置換 ×20 的 SD 為單位
          vote_acc vs floor — 事件日區塊 bootstrap 95% CI
          spearman — 鄰居未來報酬均值 vs 查詢未來報酬 (不丟幅度資訊)

判定門檻 (執行前定死, 見 §17.2):
  |Δσ| >= 3 且 兩種正規化同號 且 三個 k 同號 → 才算有訊號

輸出: analysis/output/repr_knn.json
"""
import argparse
import gc
import json
import os as _os
import sys as _sys
import time

import numpy as np
from scipy.stats import spearmanr
from sklearn.neighbors import NearestNeighbors

_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _p in (_root, _os.path.join(_root, "core"), _os.path.join(_root, "test")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

WINDOW = 140
M_PIPS = 80
CACHE = _os.path.join(_root, "analysis", "cache_repr")
OUTDIR = _os.path.join(_root, "analysis", "output")
REPRS = ["R0_raw", "R1_pip", "R2_sub"]


def _mem():
    try:
        import psutil
        return f"{psutil.Process().memory_info().rss / 2**30:.2f}GB"
    except Exception:
        return "?"


# ============================================================ stage: build
def stage_build(args):
    from indicators import compute_indicators
    from pip_algorithm import extract_pips
    from event_data import build_event_sets

    t0 = time.time()
    _os.makedirs(CACHE, exist_ok=True)

    tr_tb, te_tb, stats, (train_data, test_data) = build_event_sets(
        tickers=args.tickers, x=args.x, up=args.up, dn=args.dn, T=args.T,
        label="tb")
    tr_nd, te_nd, _, _ = build_event_sets(
        tickers=args.tickers, x=args.x, label="nextday", verbose=False)

    def align(ref, other):
        pos = {m: i for i, m in enumerate(other.meta)}
        return other.y[np.array([pos[m] for m in ref.meta])]

    y_tb = (tr_tb.y.copy(), te_tb.y.copy())
    y_nd = (align(tr_tb, tr_nd), align(te_tb, te_nd))
    del tr_nd, te_nd
    gc.collect()
    print(f"[BUILD] lib={len(tr_tb)} query={len(te_tb)} "
          f"({time.time()-t0:.0f}s, rss {_mem()})", flush=True)

    def one_split(ds, split_data, name):
        """回傳 (R0, R1, ok); 同時把 R2 存檔."""
        n = len(ds.meta)
        R0 = np.zeros((n, WINDOW, 9), dtype=np.float32)
        R1 = np.zeros((n, M_PIPS, 9), dtype=np.float32)
        ok = np.zeros(n, dtype=bool)
        feats, posmap, closes = {}, {}, {}
        t1 = time.time()
        for i, (tk, date) in enumerate(ds.meta):
            f = feats.get(tk)
            if f is None:
                df = split_data.get(tk)
                if df is None:
                    continue
                # raw 模式: run_paper_repro.py 用 norm_stats={tk:(0.0,1.0)}
                f = compute_indicators(df, n=WINDOW,
                                       stats=(0.0, 1.0)).astype(np.float32)
                feats[tk] = f
                posmap[tk] = {d: p for p, d in enumerate(df.index)}
                closes[tk] = df["close"].values.astype(np.float64)
            pos = posmap[tk].get(date)
            if pos is None or pos + 1 - WINDOW < 0:
                continue
            end = pos + 1
            start = end - WINDOW
            fw = f[start:end]
            R0[i] = fw
            pips, _ = extract_pips(closes[tk][start:end], m=M_PIPS)
            pips = np.asarray(pips, dtype=int)
            if len(pips) != M_PIPS:
                continue
            R1[i] = fw[pips]
            ok[i] = True
            if (i + 1) % 20000 == 0:
                print(f"    [{name}] {i+1}/{n} ({time.time()-t1:.0f}s)",
                      flush=True)
        del feats, closes
        gc.collect()
        print(f"  [{name}] {ok.sum()}/{n} ({time.time()-t1:.0f}s, "
              f"rss {_mem()})", flush=True)
        return R0, R1, ok, posmap

    R0tr, R1tr, ok_tr, pm_tr = one_split(tr_tb, train_data, "train")
    R0te, R1te, ok_te, pm_te = one_split(te_tb, test_data, "test")

    # 未來報酬 (幅度面向)
    def fwd(ds, split_data, h, posmap):
        r = np.full(len(ds.meta), np.nan, dtype=np.float64)
        cl = {}
        for i, (tk, date) in enumerate(ds.meta):
            if tk not in cl:
                df = split_data.get(tk)
                if df is None:
                    continue
                cl[tk] = df["close"].values.astype(np.float64)
            pos = posmap.get(tk, {}).get(date)
            c = cl[tk]
            if pos is None or pos + h >= len(c) or c[pos] <= 0:
                continue
            r[i] = c[pos + h] / c[pos] - 1.0
        return r

    ret = {
        "tb": (fwd(tr_tb, train_data, args.T, pm_tr),
               fwd(te_tb, test_data, args.T, pm_te)),
        "nextday": (fwd(tr_tb, train_data, 1, pm_tr),
                    fwd(te_tb, test_data, 1, pm_te)),
    }

    # 逐一存檔並立刻釋放
    def dump(name, arr):
        np.save(_os.path.join(CACHE, name + ".npy"), arr)

    dump("R0_raw_train", R0tr[ok_tr]); del R0tr; gc.collect()
    dump("R0_raw_test", R0te[ok_te]); del R0te; gc.collect()
    dump("R1_pip_train", R1tr[ok_tr]); del R1tr; gc.collect()
    dump("R1_pip_test", R1te[ok_te]); del R1te; gc.collect()
    dump("R2_sub_train", tr_tb.X[ok_tr])
    dump("R2_sub_test", te_tb.X[ok_te])
    for lab, (a, b) in {"tb": y_tb, "nextday": y_nd}.items():
        dump(f"y_{lab}_train", a[ok_tr])
        dump(f"y_{lab}_test", b[ok_te])
    for lab, (a, b) in ret.items():
        dump(f"ret_{lab}_train", a[ok_tr])
        dump(f"ret_{lab}_test", b[ok_te])

    meta_te = [m for m, o in zip(te_tb.meta, ok_te) if o]
    date_idx = {}
    for j, m in enumerate(meta_te):
        date_idx.setdefault(str(m[1])[:10], []).append(j)
    info = {
        "params": {**vars(args), "window": WINDOW, "m_pips": M_PIPS},
        "event_stats": stats,
        "n_lib": int(ok_tr.sum()), "n_query": int(ok_te.sum()),
        "date_idx": date_idx,
    }
    with open(_os.path.join(CACHE, "info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False)
    print(f"[BUILD] 完成 lib={info['n_lib']} query={info['n_query']} "
          f"({time.time()-t0:.0f}s, rss {_mem()})", flush=True)


# ============================================================ 特徵正規化
def featurize_inplace(A, norm, scaler=None):
    """A 必須是本函式可以就地改寫的 float32 陣列 (呼叫端負責複製)."""
    if norm == "sample":
        ax = tuple(range(1, A.ndim - 1))
        A -= A.mean(axis=ax, keepdims=True)
        A /= (A.std(axis=ax, keepdims=True) + 1e-8)
        return A.reshape(len(A), -1), None
    F = A.reshape(len(A), -1)
    if scaler is None:
        scaler = (F.mean(0), F.std(0) + 1e-8)
    F -= scaler[0]
    F /= scaler[1]
    return F, scaler


# ============================================================ 評估
def evaluate(idx, ytr, yte, k, date_idx, rng, ret_tr=None, ret_te=None,
             n_perm=20, n_boot=3000):
    ii = idx[:, :k]
    nb_y = ytr[ii]
    agree = float((nb_y == yte[:, None]).mean())
    vote = (nb_y.mean(1) > 0.5).astype(int)
    vote_acc = float((vote == yte).mean())
    p_tr, p_te = float(ytr.mean()), float(yte.mean())
    chance = p_te * p_tr + (1 - p_te) * (1 - p_tr)
    floor = max(p_te, 1 - p_te)

    perm = [float((rng.permutation(ytr)[ii] == yte[:, None]).mean())
            for _ in range(n_perm)]
    pm, ps = float(np.mean(perm)), float(np.std(perm))
    dsig = (agree - pm) / ps if ps > 0 else 0.0

    dates = sorted(date_idx)
    n_d = np.array([len(date_idx[d]) for d in dates], float)
    c_d = np.array([(vote[date_idx[d]] == yte[date_idx[d]]).sum()
                    for d in dates], float)
    p_d = np.array([(yte[date_idx[d]] == 1).sum() for d in dates], float)
    s = rng.integers(0, len(dates), (n_boot, len(dates)))
    nn_, cc, pp = n_d[s].sum(1), c_d[s].sum(1), p_d[s].sum(1)
    gaps = cc / nn_ - np.maximum(pp / nn_, 1 - pp / nn_)

    out = {
        "k": k,
        "agree_pct": round(agree * 100, 3),
        "agree_chance_pct": round(chance * 100, 3),
        "perm_mean_pct": round(pm * 100, 3),
        "perm_sd_pct": round(ps * 100, 3),
        "delta_sigma": round(dsig, 2),
        "vote_acc_pct": round(vote_acc * 100, 2),
        "floor_pct": round(floor * 100, 2),
        "vote_gap_pp": round((vote_acc - floor) * 100, 2),
        "vote_gap_ci95": [round(float(np.percentile(gaps, 2.5)) * 100, 2),
                          round(float(np.percentile(gaps, 97.5)) * 100, 2)],
        "p_gap_above_0": round(float((gaps > 0).mean()), 4),
        "vote_pos_pct": round(float(vote.mean()) * 100, 2),
    }
    if ret_tr is not None:
        nb_r = np.nanmean(ret_tr[ii], axis=1)
        m = np.isfinite(nb_r) & np.isfinite(ret_te)
        if m.sum() > 100:
            rho, pv = spearmanr(nb_r[m], ret_te[m])
            out["spearman_rho"] = round(float(rho), 4)
            out["spearman_p"] = float(f"{pv:.3g}")
            out["spearman_n"] = int(m.sum())
    return out


# ============================================================ stage: knn
def stage_knn(args):
    t0 = time.time()
    ks = [int(v) for v in args.ks.split(",")]
    kmax = max(ks)
    rng = np.random.default_rng(args.seed)
    info = json.load(open(_os.path.join(CACHE, "info.json"), encoding="utf-8"))
    date_idx = {d: np.asarray(v) for d, v in info["date_idx"].items()}
    L = lambda n: np.load(_os.path.join(CACHE, n + ".npy"))   # noqa: E731

    Y = {lab: (L(f"y_{lab}_train"), L(f"y_{lab}_test"))
         for lab in ["tb", "nextday"]}
    RET = {lab: (L(f"ret_{lab}_train"), L(f"ret_{lab}_test"))
           for lab in ["tb", "nextday"]}

    out = {"params": {**info["params"], "ks": args.ks, "seed": args.seed},
           "event_stats": info["event_stats"],
           "n_lib": info["n_lib"], "n_query": info["n_query"],
           "dims": {}, "results": {}}

    for rname in REPRS:
        for norm in ["sample", "global"]:
            t1 = time.time()
            A_tr = L(f"{rname}_train").astype(np.float32, copy=False)
            A_te = L(f"{rname}_test").astype(np.float32, copy=False)
            out["dims"][rname] = int(np.prod(A_tr.shape[1:]))
            Ftr, sc = featurize_inplace(A_tr, norm)
            Fte, _ = featurize_inplace(A_te, norm, sc)
            nn = NearestNeighbors(n_neighbors=kmax, algorithm="brute",
                                  n_jobs=-1).fit(Ftr)
            _, idx = nn.kneighbors(Fte)
            del nn, Ftr, Fte, A_tr, A_te
            gc.collect()
            print(f"  ({rname}/{norm} kNN {time.time()-t1:.0f}s, "
                  f"rss {_mem()})", flush=True)
            for lab in ["tb", "nextday"]:
                ytr, yte = Y[lab]
                rtr, rte = RET[lab]
                for k in ks:
                    r = evaluate(idx, ytr, yte, k, date_idx, rng,
                                 ret_tr=rtr, ret_te=rte)
                    key = f"{rname}/{norm}/{lab}/k{k}"
                    out["results"][key] = r
                    print(f"[{key:32s}] agree {r['agree_pct']:.3f}% "
                          f"perm {r['perm_mean_pct']:.3f}±"
                          f"{r['perm_sd_pct']:.3f}%  Δ={r['delta_sigma']:+.2f}σ"
                          f" | vote {r['vote_acc_pct']:.2f} vs floor "
                          f"{r['floor_pct']:.2f} ({r['vote_gap_pp']:+.2f}pp)"
                          f" | rho={r.get('spearman_rho')}", flush=True)
            del idx
            gc.collect()
            _os.makedirs(OUTDIR, exist_ok=True)
            with open(_os.path.join(OUTDIR, args.out), "w",
                      encoding="utf-8") as f:
                json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"[SAVED] analysis/output/{args.out} ({time.time()-t0:.0f}s)",
          flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["build", "knn", "all"])
    ap.add_argument("--tickers", default="elec_all")
    ap.add_argument("--x", type=float, default=0.05)
    ap.add_argument("--up", type=float, default=0.05)
    ap.add_argument("--dn", type=float, default=0.05)
    ap.add_argument("--T", type=int, default=20)
    ap.add_argument("--ks", default="5,20,50")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="repr_knn.json")
    args = ap.parse_args()
    if args.stage in ("build", "all"):
        stage_build(args)
    if args.stage in ("knn", "all"):
        stage_knn(args)


if __name__ == "__main__":
    main()
