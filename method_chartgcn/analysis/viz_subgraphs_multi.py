# -*- coding: utf-8 -*-
"""2330.TW 決策日 2024-08-05 ±3 交易日 (共 7 天) 的子圖解剖 + 錨點演變.
輸出 figs/subgraph_viz.html (線上版: claude.ai artifact 543d7dea)."""
import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "core"))
from data_loader import fetch_tw_stocks
from pip_algorithm import extract_pips
from vg_graph import build_visibility_graph
from subgraph import select_top_nodes, bfs_subgraph, normalize_subgraph

TK, CENTER, W, M, N, G_N = "2330.TW", "2024-08-05", 140, 80, 10, 4
OUT = os.path.join(ROOT, "figs", "subgraph_viz.html")

df = fetch_tw_stocks(tickers=[TK], start="2016-01-01", end="2024-12-31")[TK]
close = df["close"].values
all_dates = [str(d)[:10] for d in df.index]
c_pos = df.index.get_loc(np.datetime64(CENTER))

days = []
for d_pos in range(c_pos - 3, c_pos + 4):
    end = d_pos + 1
    series = close[end - W:end]
    dates = all_dates[end - W:end]
    label = 1 if close[end] > close[d_pos] else 0
    chg = (close[end] / close[d_pos] - 1) * 100
    pips, scores = extract_pips(series, m=M)
    G = build_visibility_graph(series, pips)
    anchors = select_top_nodes(G, scores, N)
    sgs = []
    for rank, root in enumerate(anchors, 1):
        swd = bfs_subgraph(G, root, G_N)
        ordered, _ = normalize_subgraph(G, swd, scores, G_N)
        depth = {n: d for n, d in swd}
        slots = []
        for slot, node in enumerate(ordered, 1):
            if node == -1:
                slots.append(None)
                continue
            t = G.nodes[node]["time"]
            slots.append(dict(slot=slot, node=int(node), t=int(t),
                              price=float(series[t]), depth=int(depth[node]),
                              date=dates[t]))
        ns = [s["node"] for s in slots if s]
        edges = [(a, b) for i, a in enumerate(ns) for b in ns[i + 1:]
                 if G.has_edge(a, b)]
        sgs.append(dict(rank=rank, slots=slots, edges=edges))
    days.append(dict(pos=d_pos, ddate=all_dates[d_pos], label=label, chg=chg,
                     series=series, dates=dates, G=G, anchors=anchors, sgs=sgs,
                     anchor_dates={dates[G.nodes[a]["time"]] for a in anchors}))

for i in range(1, len(days)):
    days[i]["overlap"] = len(days[i]["anchor_dates"] & days[i - 1]["anchor_dates"])


def xm(t, w, n, ml=8, mr=8):
    return ml + t / (n - 1) * (w - ml - mr)


def ym(p, h, lo, hi, mt=6, mb=6):
    return mt + (hi - p) / (hi - lo) * (h - mt - mb)


u_lo = min(d["series"].min() for d in days)
u_hi = max(d["series"].max() for d in days)
pad = (u_hi - u_lo) * 0.06
u_lo, u_hi = u_lo - pad, u_hi + pad

u_start = days[0]["pos"] + 1 - W
u_end = days[-1]["pos"]
u_n = u_end - u_start + 1
u_dates = all_dates[u_start:u_end + 1]
LW, LH, LANE_H = 1080, 118 + 7 * 26, 26
lp = []
pl = " ".join(f"{xm(i, LW, u_n, ml=104):.1f},"
              f"{ym(close[u_start + i], 100, u_lo, u_hi, mt=8, mb=4) + 8:.1f}"
              for i in range(u_n))
lp.append(f'<polyline class="price" points="{pl}"/>')
for k in range(0, u_n, 20):
    x = xm(k, LW, u_n, ml=104)
    lp.append(f'<line class="grid" x1="{x:.1f}" y1="8" x2="{x:.1f}" y2="{LH-16}"/>'
              f'<text class="tick" x="{x:.1f}" y="{LH-4}">{u_dates[k][5:]}</text>')
d2u = {d: i for i, d in enumerate(u_dates)}
for li, d in enumerate(days):
    y = 118 + li * LANE_H
    mark = "★" if d["ddate"] == CENTER else ""
    ov = f'{d["overlap"]}/10 同前日' if li > 0 else ""
    lp.append(f'<text class="lanelab" x="98" y="{y+4}">{d["ddate"][5:]}{mark}</text>'
              f'<line class="lanegrid" x1="104" y1="{y}" x2="{LW-8}" y2="{y}"/>'
              f'<text class="laneov" x="{LW-10}" y="{y+4}">{ov}</text>')
    for ad in sorted(d["anchor_dates"]):
        if ad not in d2u:
            continue
        x = xm(d2u[ad], LW, u_n, ml=104)
        cls = "adot hot" if ad == d["ddate"] else "adot"
        lp.append(f'<circle class="{cls}" cx="{x:.1f}" cy="{y}" r="4"/>')
lane_svg = (f'<svg viewBox="0 0 {LW} {LH}" role="img" '
            f'aria-label="七個決策日的錨點日期演變">{"".join(lp)}</svg>')

DC = {0: "d0", 1: "d1"}
sections = ""
for d in days:
    S = d["series"]
    dts = d["dates"]
    G = d["G"]
    lo = S.min() - (S.max() - S.min()) * .06
    hi = S.max() + (S.max() - S.min()) * .06
    W1, H1 = 1080, 210
    pl = " ".join(f"{xm(t, W1, W, ml=40):.1f},{ym(p, H1, lo, hi, mt=8, mb=20):.1f}"
                  for t, p in enumerate(S))
    parts = [f'<polyline class="price" points="{pl}"/>']
    for t in range(0, W, 28):
        x = xm(t, W1, W, ml=40)
        parts.append(f'<line class="grid" x1="{x:.1f}" y1="8" x2="{x:.1f}" '
                     f'y2="{H1-18}"/>'
                     f'<text class="tick" x="{x:.1f}" y="{H1-5}">{dts[t][5:]}</text>')
    for n in G.nodes:
        parts.append(f'<circle class="pip" cx="{xm(G.nodes[n]["time"], W1, W, ml=40):.1f}" '
                     f'cy="{ym(G.nodes[n]["price"], H1, lo, hi, mt=8, mb=20):.1f}" r="2.2"/>')
    for rank, root in enumerate(d["anchors"], 1):
        t, p = G.nodes[root]["time"], G.nodes[root]["price"]
        x, y = xm(t, W1, W, ml=40), ym(p, H1, lo, hi, mt=8, mb=20)
        parts.append(f'<circle class="anchor" cx="{x:.1f}" cy="{y:.1f}" r="8.4"/>'
                     f'<text class="arank" x="{x:.1f}" y="{y+3.4:.1f}">{rank}</text>')
    strip = (f'<svg viewBox="0 0 {W1} {H1}" role="img" '
             f'aria-label="{d["ddate"]} 的 140 日窗與錨點">{"".join(parts)}</svg>')
    minis = ""
    for sg in d["sgs"]:
        W2, H2 = 196, 108
        mpl = " ".join(f"{xm(t, W2, W):.1f},{ym(p, H2, lo, hi):.1f}"
                       for t, p in enumerate(S))
        mp = [f'<polyline class="mprice" points="{mpl}"/>']
        coord = {}
        for s in sg["slots"]:
            if s:
                coord[s["node"]] = (xm(s["t"], W2, W), ym(s["price"], H2, lo, hi))
        for a, b in sg["edges"]:
            (x1, y1), (x2, y2) = coord[a], coord[b]
            mp.append(f'<line class="sedge" x1="{x1:.1f}" y1="{y1:.1f}" '
                      f'x2="{x2:.1f}" y2="{y2:.1f}"/>')
        for s in sg["slots"]:
            if not s:
                continue
            x, y = coord[s["node"]]
            cls = DC.get(s["depth"], "d2")
            mp.append(f'<circle class="snode {cls}" cx="{x:.1f}" cy="{y:.1f}" '
                      f'r="{6.4 if s["depth"] == 0 else 5}"/>'
                      f'<text class="sslot" x="{x:.1f}" y="{y+3:.1f}">{s["slot"]}</text>')
        rd = next(s["date"] for s in sg["slots"] if s and s["depth"] == 0)
        span = (max(s["t"] for s in sg["slots"] if s)
                - min(s["t"] for s in sg["slots"] if s))
        minis += (f'<div class="mini"><div class="mtitle">SG{sg["rank"]}'
                  f'<span>{rd[5:]}・跨{span}天</span></div>'
                  f'<svg viewBox="0 0 {W2} {H2}" role="img" '
                  f'aria-label="子圖{sg["rank"]}">{"".join(mp)}</svg></div>')
    lab = "漲" if d["label"] else "跌"
    labcls = "up" if d["label"] else "dn"
    star = "・★ 原解剖樣本" if d["ddate"] == CENTER else ""
    sections += (f'<section>\n'
                 f'<h2>決策日 {d["ddate"]}{star}'
                 f'<span class="lab {labcls}">隔日{lab} {d["chg"]:+.2f}%</span></h2>\n'
                 f'<figure>{strip}<div class="grid10">{minis}</div></figure>\n'
                 f'</section>')

CSS = """
:root{--paper:#FAFAF8;--card:#FFF;--ink:#1E2530;--muted:#5B6472;--line:#D8DCE2;
--faint:#EEF0F3;--blue:#2563EB;--green:#0E8A6A;--amber:#C2690A;--red:#C23B3B}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
--paper:#12151A;--card:#1A1E25;--ink:#E8EAEE;--muted:#9AA3B0;--line:#333A45;
--faint:#232830;--blue:#7AA2F7;--green:#4FC49B;--amber:#E5A155;--red:#E07A7A}}
:root[data-theme="dark"]{
--paper:#12151A;--card:#1A1E25;--ink:#E8EAEE;--muted:#9AA3B0;--line:#333A45;
--faint:#232830;--blue:#7AA2F7;--green:#4FC49B;--amber:#E5A155;--red:#E07A7A}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
font-family:"Segoe UI","Microsoft JhengHei","PingFang TC",system-ui,sans-serif;font-size:14px}
.wrap{max-width:1140px;margin:0 auto;padding:26px 18px 40px}
h1{font-size:22px;margin:0 0 4px} .sub{color:var(--muted);margin:0 0 12px}
h2{font-size:15px;margin:26px 0 8px}
h2 .lab{margin-left:10px;font-size:12.5px;padding:2px 9px;border-radius:5px;font-weight:600}
.lab.up{color:var(--red);background:var(--faint);border:1px solid var(--line)}
.lab.dn{color:var(--green);background:var(--faint);border:1px solid var(--line)}
figure{margin:0;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:12px}
figcaption{color:var(--muted);font-size:12.5px;margin-top:8px;line-height:1.55}
svg{display:block;max-width:100%;height:auto}
.price{fill:none;stroke:var(--muted);stroke-width:1.5}
.mprice{fill:none;stroke:var(--line);stroke-width:1.1}
.pip{fill:var(--paper);stroke:var(--muted);stroke-width:1}
.anchor{fill:var(--blue);stroke:var(--paper);stroke-width:1.5}
.arank{fill:var(--paper);font-size:9.5px;font-weight:700;text-anchor:middle}
.grid{stroke:var(--faint);stroke-width:1}
.tick{fill:var(--muted);font-size:10px;text-anchor:middle}
.sedge{stroke:var(--blue);stroke-width:1.5;opacity:.65}
.snode.d0{fill:var(--blue)} .snode.d1{fill:var(--green)} .snode.d2{fill:var(--amber)}
.snode{stroke:var(--paper);stroke-width:1.3}
.sslot{fill:var(--paper);font-size:8.5px;font-weight:700;text-anchor:middle}
.grid10{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:10px}
@media (max-width:900px){.grid10{grid-template-columns:repeat(2,1fr)}}
.mini{border:1px solid var(--line);border-radius:8px;padding:6px;background:var(--card)}
.mtitle{font-size:11.5px;font-weight:700;margin-bottom:3px}
.mtitle span{color:var(--muted);font-weight:400;float:right;font-size:10.5px}
.lanelab{fill:var(--ink);font-size:11px;text-anchor:end;font-weight:600}
.laneov{fill:var(--muted);font-size:10.5px;text-anchor:end}
.lanegrid{stroke:var(--faint);stroke-width:1}
.adot{fill:var(--blue)} .adot.hot{fill:var(--red)}
.leg{display:flex;gap:16px;margin:0 0 6px;font-size:12px;color:var(--muted);flex-wrap:wrap}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px;vertical-align:-1px}
"""

html = f'''<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>子圖解剖:2330.TW @ 2024-08-05 ±3 日</title>
<style>{CSS}</style>
<div class="wrap">
<h1>子圖解剖:2330.TW 決策日 2024-08-05 前後三天</h1>
<p class="sub">7 個決策日(7/31 ~ 8/8)・每天各自的 140 日窗、80 個 PIP、10 個錨點子圖・管線原始碼實算</p>
<h2>圖 A:錨點怎麼隨窗滑動而變</h2>
<figure>
<div class="leg"><span><span class="dot" style="background:var(--blue)"></span>該日的 10 個錨點日期</span>
<span><span class="dot" style="background:var(--red)"></span>決策日自己(端點規則必為錨)</span>
<span>右側 = 與前一日錨點集合的重疊數・★ = 原解剖樣本</span></div>
{lane_svg}
<figcaption>上方灰線是聯集期間的收盤價。每一列是一個決策日的 10 個錨點落點:窗每滑一天,理論上結構只多一天資訊,但 8/5 崩盤當天新極值出現後,錨點排名被重新洗牌——重疊數顯示結構的日間穩定度。</figcaption>
</figure>
{sections}
<figure style="margin-top:18px"><figcaption><b>讀法:</b>每個決策日一節:上方為該日 140 日窗與 10 個錨點(藍圈數字 = importance 排名),下方 10 格為各子圖(藍=錨點、綠=BFS 深度 1、橙=深度 ≥2,藍線=子圖內可見邊,格標「跨 n 天」= 該子圖成員的時間跨度)。七天並排可見:(1) 決策日永遠是錨點之一(端點規則);(2) 崩盤前後,錨點與子圖結構大幅重組——同一支股票相鄰兩天的「模型視角」可以差很多;(3) 山頂型子圖跨月、盤整型子圖跨日的雙峰現象在每一天都成立。</figcaption></figure>
</div>'''

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
for d in days:
    print(f'{d["ddate"]} 隔日{"漲" if d["label"] else "跌"} {d["chg"]:+.2f}% '
          f'重疊={d.get("overlap", "-")}')
print("saved:", OUT)
