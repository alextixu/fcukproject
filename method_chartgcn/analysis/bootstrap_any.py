# -*- coding: utf-8 -*-
"""以交易日為區塊的 bootstrap 95% CI —— 任意實驗 tag(取代寫死單一 run 的 block_bootstrap.py)。

背景(§19 稽核第 4、9d 項):
  - 原 `analysis/block_bootstrap.py` 把路徑寫死在 elec_all h=1 的快取上,無法套用到 CNN 或別的 run,
    導致 §16.1 的「CNN h=5 高於 floor +1.2~1.7pp」始終只有點估計、沒有信賴區間。
  - 樣本每日一筆、標籤重疊,pooled SE 會嚴重低估;以「交易日」為區塊重抽樣才是正確口徑。

作法:
  對每個交易日算 (n, 答對數, 各混淆格數),再以交易日為單位有放回重抽 B 次,
  每次重算 Accuracy / F1-macro / floor,取 2.5% 與 97.5% 分位為 95% CI,
  並回報 SE 膨脹倍數與有效樣本數 n_eff = n_pooled / 膨脹倍數^2。

用法:
    python analysis/bootstrap_any.py --exps sector-date-elec455,h5-elec_all-s42 --reps 2000
    python analysis/bootstrap_any.py --preds analysis/output/preds_cnn-h5-s42.npz   # CNN(見 --save-preds)
輸出:analysis/output/bootstrap_any.json
"""
import argparse
import glob
import json
import os as _os
import sys as _sys

import numpy as np
import torch

_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _p in (_root, _os.path.join(_root, "core"), _os.path.join(_root, "test")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from model import ChartGCN                       # noqa: E402
from run_paper_repro import load_ds_cache        # noqa: E402
from decile_ls import cache_path                 # noqa: E402

EXPDIR = _os.path.join(_root, "experiments_paper")
OUTDIR = _os.path.join(_root, "analysis", "output")


def f1_macro_from_counts(tp1, fp1, fn1, tp0, fp0, fn0):
    def f1(tp, fp, fn):
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        return 2 * p * r / (p + r) if p + r else 0.0
    return 0.5 * (f1(tp1, fp1, fn1) + f1(tp0, fp0, fn0))


def per_date_counts(y, pred, dates):
    """每個交易日一列:[n, 對, TP1, FP1, FN1, TP0, FP0, FN0, n_pos]"""
    rows = []
    for d in np.unique(dates):
        m = dates == d
        yd, pd_ = y[m], pred[m]
        rows.append([m.sum(), int((yd == pd_).sum()),
                     int(((pd_ == 1) & (yd == 1)).sum()),
                     int(((pd_ == 1) & (yd == 0)).sum()),
                     int(((pd_ == 0) & (yd == 1)).sum()),
                     int(((pd_ == 0) & (yd == 0)).sum()),
                     int(((pd_ == 0) & (yd == 1)).sum()),
                     int(((pd_ == 1) & (yd == 0)).sum()),
                     int((yd == 1).sum())])
    return np.asarray(rows, dtype=np.int64)


def bootstrap(C, reps=2000, seed=20260905):
    """C: per_date_counts 的輸出。回傳 acc / f1m / floor / gap 的點估計與 95% CI。"""
    rng = np.random.default_rng(seed)
    nd = len(C)

    def stats(S):
        n = S[:, 0].sum()
        acc = S[:, 1].sum() / n
        f1m = f1_macro_from_counts(S[:, 2].sum(), S[:, 3].sum(), S[:, 4].sum(),
                                   S[:, 5].sum(), S[:, 6].sum(), S[:, 7].sum())
        pos = S[:, 8].sum() / n
        floor = max(pos, 1 - pos)
        return acc, f1m, floor, acc - floor

    point = stats(C)
    draws = np.empty((reps, 4))
    for b in range(reps):
        draws[b] = stats(C[rng.integers(0, nd, nd)])
    lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)

    n_pool = int(C[:, 0].sum())
    acc = point[0]
    se_pool = np.sqrt(acc * (1 - acc) / n_pool)          # 假設獨立時的 SE
    se_block = draws[:, 0].std(ddof=1)                   # 區塊 bootstrap 的 SE
    infl = se_block / se_pool if se_pool > 0 else float("nan")
    names = ("acc", "f1_macro", "floor", "gap_vs_floor")
    out = {"n_dates": nd, "n_samples": n_pool, "reps": reps,
           "se_pooled_pp": round(se_pool * 100, 3),
           "se_block_pp": round(se_block * 100, 3),
           "se_inflation": round(float(infl), 2),
           "n_eff": int(n_pool / infl ** 2) if infl and np.isfinite(infl) else None}
    for i, k in enumerate(names):
        out[k] = {"point": round(point[i] * 100, 2),
                  "ci95": [round(lo[i] * 100, 2), round(hi[i] * 100, 2)]}
    out["p_gap_gt_0"] = round(float((draws[:, 3] > 0).mean()) * 100, 1)
    return out


@torch.no_grad()
def gcn_predictions(tag, device):
    fp = glob.glob(_os.path.join(EXPDIR, f"*_{tag}.json"))
    if not fp:
        return None, f"找不到 {tag}.json"
    d = json.load(open(fp[0], encoding="utf-8"))
    p = d["params"]
    mp, cp = fp[0][:-5] + "_model.pt", cache_path(p)
    if not (_os.path.exists(mp) and _os.path.exists(cp)):
        return None, f"model={_os.path.exists(mp)} cache={_os.path.exists(cp)}"
    ds = load_ds_cache(cp)
    model = ChartGCN(N=p["N"], g=p["g"], F_dim=ds.X.shape[-1],
                     use_attention=not p.get("no_attention", False)).to(device)
    model.load_state_dict(torch.load(mp, map_location=device))
    model.eval()
    if p.get("batch_mode", "paper") == "date":
        batches = [np.asarray(v) for _, v in sorted(ds.date_to_indices.items())]
    else:
        batches = [np.arange(i, min(i + 128, len(ds))) for i in range(0, len(ds), 128)]
    pred = np.zeros(len(ds), dtype=np.int64)
    for idx in batches:
        X = torch.from_numpy(ds.X[idx]).float().to(device)
        pred[idx] = model(X).argmax(1).cpu().numpy()
    y = np.asarray(ds.y, dtype=np.int64)
    dates = np.array([str(m[1])[:10] for m in ds.meta])
    return (y, pred, dates), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exps", default="", help="逗號分隔的 GCN 實驗 tag")
    ap.add_argument("--preds", default="", help="逗號分隔的 npz(含 y/pred/dates),供 CNN 等外部模型")
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--out", default="bootstrap_any.json")
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    _os.makedirs(OUTDIR, exist_ok=True)
    res = {}

    for tag in [t.strip() for t in a.exps.split(",") if t.strip()]:
        got, err = gcn_predictions(tag, dev)
        if got is None:
            print(f"[SKIP] {tag}: {err}"); continue
        y, pred, dates = got
        r = bootstrap(per_date_counts(y, pred, dates), a.reps)
        res[tag] = r
        print(f"{tag:28s} Acc {r['acc']['point']:.2f} CI{r['acc']['ci95']} | "
              f"floor {r['floor']['point']:.2f} | gap {r['gap_vs_floor']['point']:+.2f} "
              f"CI{r['gap_vs_floor']['ci95']} P(gap>0)={r['p_gap_gt_0']}% | "
              f"F1m {r['f1_macro']['point']:.2f} CI{r['f1_macro']['ci95']} | "
              f"SE×{r['se_inflation']} n_eff={r['n_eff']}", flush=True)

    for fp in [t.strip() for t in a.preds.split(",") if t.strip()]:
        if not _os.path.exists(fp):
            print(f"[SKIP] {fp} 不存在"); continue
        z = np.load(fp, allow_pickle=True)
        name = _os.path.basename(fp).replace("preds_", "").replace(".npz", "")
        r = bootstrap(per_date_counts(z["y"].astype(np.int64),
                                      z["pred"].astype(np.int64),
                                      np.asarray(z["dates"]).astype(str)), a.reps)
        res[name] = r
        print(f"{name:28s} Acc {r['acc']['point']:.2f} CI{r['acc']['ci95']} | "
              f"floor {r['floor']['point']:.2f} | gap {r['gap_vs_floor']['point']:+.2f} "
              f"CI{r['gap_vs_floor']['ci95']} P(gap>0)={r['p_gap_gt_0']}% | "
              f"F1m {r['f1_macro']['point']:.2f} CI{r['f1_macro']['ci95']} | "
              f"SE×{r['se_inflation']} n_eff={r['n_eff']}", flush=True)

    with open(_os.path.join(OUTDIR, a.out), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"\n[SAVED] {_os.path.join(OUTDIR, a.out)}  ({len(res)} 組)")


if __name__ == "__main__":
    main()
