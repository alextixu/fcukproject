"""
事件驅動樣本集建構 (共用於 run_event_experiment.py / analysis/knn_similarity.py).

做法 (與 derive_horizon_ds 同精神, X 特徵逐位元沿用 h=1 dscache):
  1. 讀取 elec_all 等族群的 h=1 dscache (train/test)
  2. 對每檔股票用完整序列 (start~end) 做因果 ZigZag 確認 → 事件日集合
     (確認日只用 <= t 的資料, 跨 train/test 邊界無洩漏)
  3. 只保留「決策日 = 事件確認日」的樣本
  4. 標籤: nextday = 沿用 dscache 的 Eq.(11) 標籤 (對照組 B)
          tb      = triple-barrier (+up / -dn / T 日), 以 split 後的 df 計算
                    → 訓練標籤不會越過 train_end (embargo 自動達成)
  5. dir_feat=True 時附加 (swing 方向 ±1, 距轉折日天數/20) 兩個純量 (D 組)
"""
import os as _os
import sys as _sys
import numpy as np
import pandas as pd
import torch

_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _p in (_root, _os.path.join(_root, "core"),
           _os.path.dirname(_os.path.abspath(__file__))):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from data_loader import fetch_tw_stocks, TICKER_SETS
from dataset import split_by_date
from events import zigzag_confirm, triple_barrier
from run_paper_repro import load_ds_cache, ArrayDataset


class EventDataset(ArrayDataset):
    def __init__(self, X, y, meta, extra=None, info=None):
        super().__init__(X, y, meta)
        self.extra = extra
        self.info = info or {}

    def __getitem__(self, idx):
        X = torch.from_numpy(self.X[idx]).float()
        y = torch.tensor(self.y[idx], dtype=torch.long)
        if self.extra is None:
            return X, y
        return X, torch.from_numpy(self.extra[idx]).float(), y


def dscache_paths(tickers, start, train_end, end, window=140, m=80, N=10,
                  g=4, out_dir="experiments_paper"):
    key = f"{tickers}0_{start}_{train_end}_{end}_w{window}m{m}N{N}g{g}s1_raw"
    d = _os.path.join(_root, out_dir, "dscache")
    return (_os.path.join(d, key + "_train.npz"),
            _os.path.join(d, key + "_test.npz"))


def build_event_sets(tickers="elec_all", start="2016-01-01",
                     train_end="2023-12-31", end="2024-12-31",
                     x=0.05, up=0.05, dn=0.05, T=20, label="tb",
                     dir_feat=False, window=140, out_dir="experiments_paper",
                     verbose=True):
    data = fetch_tw_stocks(tickers=TICKER_SETS[tickers], start=start, end=end)
    train_data, test_data = split_by_date(data, train_end,
                                          warmup_rows=2 * window)
    tr_p, te_p = dscache_paths(tickers, start, train_end, end,
                               window=window, out_dir=out_dir)
    if verbose:
        print(f"[EVENT] 讀取 dscache {_os.path.basename(tr_p)}")
    src_tr, src_te = load_ds_cache(tr_p), load_ds_cache(te_p)

    # 事件 (完整序列, 因果)
    ev = {}
    n_ev_total = 0
    gaps = []
    for tk, df in data.items():
        evs = zigzag_confirm(df["close"].values, x)
        n_ev_total += len(evs)
        idx = df.index
        prev = None
        for t, d, turn in evs:
            ev[(tk, idx[t])] = (d, t - turn)
            if prev is not None:
                gaps.append(t - prev)
            prev = t

    def derive(src, split_data):
        pos_maps = {}
        keep, ys, metas, extras, hits, dirs = [], [], [], [], [], []
        for i, (tk, date) in enumerate(src.meta):
            e = ev.get((tk, date))
            if e is None:
                continue
            df = split_data.get(tk)
            if df is None:
                continue
            pm = pos_maps.get(tk)
            if pm is None:
                pm = {d: p for p, d in enumerate(df.index)}
                pos_maps[tk] = pm
            pos = pm.get(date)
            if pos is None:
                continue
            if label == "nextday":
                yv, hit = int(src.y[i]), "nextday"
            elif label == "tb":
                r = triple_barrier(df["close"].values, pos, up, dn, T)
                if r is None:
                    continue
                yv, hit = r
            else:
                raise ValueError(label)
            keep.append(i)
            ys.append(yv)
            metas.append((tk, date))
            hits.append(hit)
            dirs.append(e[0])
            extras.append([float(e[0]), e[1] / 20.0])
        extra = np.asarray(extras, np.float32) if dir_feat else None
        info = {"hits": hits, "dirs": dirs, "src_idx": keep}
        return EventDataset(src.X[keep], np.asarray(ys, dtype=src.y.dtype),
                            metas, extra, info)

    train_ds = derive(src_tr, train_data)
    test_ds = derive(src_te, test_data)

    def _summ(ds):
        hits = np.array(ds.info["hits"])
        dirs = np.array(ds.info["dirs"])
        return {
            "n": len(ds),
            "pos_pct": round(float((ds.y == 1).mean()) * 100, 2),
            "n_dates": len(ds.date_to_indices),
            "per_date_mean": round(len(ds) / max(1, len(ds.date_to_indices)), 1),
            "dir_up_pct": round(float((dirs == 1).mean()) * 100, 1),
            "hit": {str(h): int((hits == h).sum()) for h in np.unique(hits)},
        }
    stats = {
        "x": x, "up": up, "dn": dn, "T": T, "label": label,
        "dir_feat": dir_feat, "n_stocks": len(data),
        "n_events_total": n_ev_total,
        "event_gap_days_median": float(np.median(gaps)) if gaps else None,
        "event_gap_days_mean": round(float(np.mean(gaps)), 1) if gaps else None,
        "src_train": len(src_tr), "src_test": len(src_te),
        "train": _summ(train_ds), "test": _summ(test_ds),
    }
    if verbose:
        print(f"[EVENT] x={x:.0%} 事件 {n_ev_total} 個 / 事件間隔中位 "
              f"{stats['event_gap_days_median']:.0f} 日")
        print(f"[EVENT] train {len(src_tr)} -> {len(train_ds)} "
              f"(漲 {stats['train']['pos_pct']}%) | "
              f"test {len(src_te)} -> {len(test_ds)} "
              f"(漲 {stats['test']['pos_pct']}%)  hit={stats['test']['hit']}")
    return train_ds, test_ds, stats, (train_data, test_data)
