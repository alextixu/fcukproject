# -*- coding: utf-8 -*-
"""子圖時間跨度 vs 預測表現 — elec_all h=1 最佳實驗 (EXP-20260726-232550) 測試集.
每個測試樣本: (1) 重算 10 個子圖時間跨度; (2) 以已存模型 date 批次推論;
(3) 分層統計. 結果 (2026-08-11 首跑): 四分位 Acc 全距 0.65pp, r=-0.0002 → 無關.
輸出: analysis/output/span_vs_perf.npz (供 block_bootstrap.py 使用)."""
import os
import sys
import time
import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("", "core", "test"):
    sys.path.insert(0, os.path.join(ROOT, p))
from data_loader import fetch_tw_stocks, TICKER_SETS
from dataset import split_by_date
from pip_algorithm import extract_pips
from vg_graph import build_visibility_graph
from subgraph import select_top_nodes, bfs_subgraph, normalize_subgraph
from model import ChartGCN
from run_paper_repro import load_ds_cache

W, M, N, G_N = 140, 80, 10, 4
MODEL_PT = os.path.join(ROOT, "experiments_paper",
                        "EXP-20260726-232550_sector-date-elec455_model.pt")
TE_NPZ = os.path.join(ROOT, "experiments_paper", "dscache",
                      "elec_all0_2016-01-01_2023-12-31_2024-12-31"
                      "_w140m80N10g4s1_raw_test.npz")
OUT = os.path.join(ROOT, "analysis", "output", "span_vs_perf.npz")

te = load_ds_cache(TE_NPZ)
print(f"test samples: {len(te)}")

model = ChartGCN(N=N, g=G_N, F_dim=9, paper_exact=True, use_attention=True)
model.load_state_dict(torch.load(MODEL_PT, map_location="cpu"))
model.eval()
preds = np.zeros(len(te), dtype=np.int64)
with torch.no_grad():
    for date_key, idxs in te.date_to_indices.items():
        X = torch.from_numpy(te.X[idxs]).float()
        preds[idxs] = model(X).argmax(1).numpy()
print(f"inference: pred_up={preds.mean()*100:.1f}%, acc={(preds==te.y).mean()*100:.2f}%")

data = fetch_tw_stocks(tickers=TICKER_SETS["elec_all"],
                       start="2016-01-01", end="2024-12-31")
_, test_data = split_by_date(data, "2023-12-31", warmup_rows=2 * W)
close_by_tk = {tk: df["close"].values for tk, df in test_data.items()}
pos_maps = {tk: {d: p for p, d in enumerate(df.index)}
            for tk, df in test_data.items()}

mean_span = np.full(len(te), np.nan)
t0 = time.time()
for i, (tk, ddate) in enumerate(te.meta):
    pos = pos_maps[tk].get(ddate)
    if pos is None or pos < W - 1:
        continue
    series = close_by_tk[tk][pos + 1 - W:pos + 1]
    pips, scores = extract_pips(series, m=M)
    G = build_visibility_graph(series, pips)
    spans = []
    for root in select_top_nodes(G, scores, N):
        swd = bfs_subgraph(G, root, G_N)
        ordered, _ = normalize_subgraph(G, swd, scores, G_N)
        ts = [G.nodes[n]["time"] for n in ordered if n != -1]
        spans.append(max(ts) - min(ts))
    mean_span[i] = float(np.mean(spans))
    if (i + 1) % 10000 == 0:
        print(f"  spans {i+1}/{len(te)} ({time.time()-t0:.0f}s)")

ok = ~np.isnan(mean_span)
y, p, ms = te.y[ok], preds[ok], mean_span[ok]
correct = (y == p).astype(float)
qs = np.percentile(ms, [25, 50, 75])
edges = [-np.inf, *qs, np.inf]
from sklearn.metrics import f1_score
for b in range(4):
    m = (ms > edges[b]) & (ms <= edges[b + 1])
    f1m = (f1_score(y[m], p[m], pos_label=1, zero_division=0)
           + f1_score(y[m], p[m], pos_label=0, zero_division=0)) / 2
    print(f"Q{b+1}: n={m.sum()} 漲先驗={y[m].mean()*100:.1f}% "
          f"Acc={correct[m].mean()*100:.2f}% F1m={f1m*100:.2f}%")
print(f"跨度 vs 對錯 r={np.corrcoef(ms, correct)[0,1]:+.4f}")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
np.savez(OUT, y=y, pred=p, mean_span=ms)
print("saved:", OUT)
