# -*- coding: utf-8 -*-
"""驗證 derive_horizon_ds (由 h=1 快取衍生 h>1 標籤) 與直接建構逐位元一致.
自建小型 h=1 資料集 (8 檔電子股, stride 10) 後衍生 h=5, 與 canonical h=5 比對."""
import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "test"))
from data_loader import fetch_tw_stocks, TICKER_SETS
from dataset import ChartGCNDataset, split_by_date
from run_paper_repro import derive_horizon_ds

H, W, M, N, G, STRIDE = 5, 140, 80, 10, 4, 10
tks = TICKER_SETS["elec_liq100"][:8]

data = fetch_tw_stocks(tickers=tks, start="2016-01-01", end="2024-12-31")
train_data, test_data = split_by_date(data, "2023-12-31", warmup_rows=2 * W)
raw = {tk: (0.0, 1.0) for tk in data}

def build(dd, stride, h, min_date=None):
    return ChartGCNDataset(dd, window=W, m_pips=M, N=N, g=G, stride=stride,
                           n_workers=1, norm_stats=raw, horizon=h,
                           min_date=min_date, verbose=False)

print("=== canonical h=1 → 衍生 h=5 vs canonical h=5 ===")
tr1, te1 = build(train_data, STRIDE, 1), build(test_data, 1, 1, "2023-12-31")
tr5c, te5c = build(train_data, STRIDE, H), build(test_data, 1, H, "2023-12-31")
tr5d = derive_horizon_ds(tr1, train_data, H)
te5d = derive_horizon_ds(te1, test_data, H)

for name, a, b in [("train", tr5c, tr5d), ("test", te5c, te5d)]:
    same_meta = len(a) == len(b) and all(
        am[0] == bm[0] and str(am[1])[:10] == str(bm[1])[:10]
        for am, bm in zip(a.meta, b.meta))
    same_y = np.array_equal(np.asarray(a.y), np.asarray(b.y))
    same_X = np.array_equal(np.asarray(a.X, dtype=np.float32),
                            np.asarray(b.X, dtype=np.float32))
    print(f"{name}: canon={len(a)} derived={len(b)} "
          f"meta={same_meta} y={same_y} X={same_X}")
    assert same_meta and same_y and same_X, f"{name} MISMATCH"
print("PASS: 衍生路徑與直接建構完全一致")
