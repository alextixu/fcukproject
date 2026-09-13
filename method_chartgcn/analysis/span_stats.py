# -*- coding: utf-8 -*-
"""統計真實子圖的時間跨度 (交易日): 多檔股票 × 多個決策日.
結論 (2026-08-11 首跑): 雙峰分佈 — 52% <=20天, 29% >60天; 中位 15 天, 最大 139 天."""
import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "core"))
from data_loader import fetch_tw_stocks
from pip_algorithm import extract_pips
from vg_graph import build_visibility_graph
from subgraph import select_top_nodes, bfs_subgraph, normalize_subgraph

W, M, N, G_N = 140, 80, 10, 4
TICKERS = ["2330.TW", "2317.TW", "3008.TW", "2409.TW", "8046.TW"]  # 高價到低價
DATES = ["2024-03-15", "2024-06-14", "2024-08-05", "2024-11-15"]

data = fetch_tw_stocks(tickers=TICKERS, start="2016-01-01", end="2024-12-31")
all_spans, per_anchor = [], {}
for tk in TICKERS:
    df = data[tk]
    close = df["close"].values
    spans_tk = []
    for ds in DATES:
        try:
            pos = df.index.get_loc(np.datetime64(ds))
        except KeyError:
            continue
        series = close[pos + 1 - W:pos + 1]
        pips, scores = extract_pips(series, m=M)
        G = build_visibility_graph(series, pips)
        anchors = select_top_nodes(G, scores, N)
        for root in anchors:
            swd = bfs_subgraph(G, root, G_N)
            ordered, _ = normalize_subgraph(G, swd, scores, G_N)
            ts = [G.nodes[n]["time"] for n in ordered if n != -1]
            spans_tk.append(max(ts) - min(ts))
            all_spans.append(spans_tk[-1])
    a = np.array(spans_tk)
    print(f"{tk}: mean={a.mean():5.1f} 天  median={np.median(a):5.1f}  "
          f"max={a.max():3d}  局部(<10天)比例={np.mean(a < 10)*100:4.0f}%")

a = np.array(all_spans)
print(f"\n全部 {len(a)} 個子圖: mean={a.mean():.1f} 天  median={np.median(a):.1f}  "
      f"p90={np.percentile(a, 90):.0f}  max={a.max()}")
print("跨度分佈: <5天 {:.0f}% | 5-20 {:.0f}% | 20-60 {:.0f}% | >60 {:.0f}%".format(
    np.mean(a < 5) * 100, np.mean((a >= 5) & (a < 20)) * 100,
    np.mean((a >= 20) & (a < 60)) * 100, np.mean(a >= 60) * 100))
