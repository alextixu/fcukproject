"""訓練門檻一路往上加(每次 +1%),跑到不再提升為止(2026-11-02 使用者要求)。

每個門檻都跑 backtest_top3 的 9 個回測(34 檔、只做多前 3 檔,3 個方法 × 2024–2026,對答案用原本的標籤)。
「提升」看 9 個扣成本報酬的平均;連續 --patience 個門檻都沒有超過目前最好的平均就停,
或某個門檻訓練不起來(某一類的訓練點太少)也停。另外記錄每個門檻的訓練點數(主軸 4 年、Stacking 的 B 1 年,每類)。
注意:這是直接看測試年選門檻,沒有驗證期。
--grid:不提早停,每個方法都跑 --start ~ --max,某個方法訓練不起來或 Stacking B 某一類少於 --min-points 個就不再跑它
        → results/amp_sweep_grid.json、results/amp_sweep_grid.png
用法: python method_kline_peak/amp_sweep.py [--start 0] [--max 20] [--patience 2] [--grid]
輸出: results/amp_sweep.json、results/amp_sweep.png
"""
import argparse
import json
import os
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import stacking as S  # noqa: E402
import backtest_top3 as T  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402

COLORS = {"主軸": "#2a78d6", "Stacking 邏輯迴歸": "#eb6834", "Stacking 門檻": "#1baf7a"}
INK, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False


def train_counts(panel, amp):
    out = {}
    for y in T.YEARS:
        tr = WF.relabel(WF.year_split(panel, y)["train"], amp)
        _, B = S.split_base_meta(tr)
        out[str(y)] = {"主軸 4 年": [int((tr.y == DOWN).sum()), int((tr.y == UP).sum())],
                       "Stacking B": [int((B.y == DOWN).sum()), int((B.y == UP).sum())]}
    return out


def summary(years):
    net = {n: [years[str(y)][n]["扣成本"]["total_return_pct"] for y in T.YEARS] for n in T.SOURCES}
    gross = {n: [years[str(y)][n]["沒扣成本"]["total_return_pct"] for y in T.YEARS] for n in T.SOURCES}
    trades = {n: [years[str(y)][n]["扣成本"]["n_trades"] for y in T.YEARS] for n in T.SOURCES}
    f1 = {n: [years[str(y)][n]["分類"]["macro_f1_pct"] for y in T.YEARS] for n in T.SOURCES}
    allv = [v for n in T.SOURCES for v in net[n]]
    return {"net": net, "gross": gross, "trades": trades, "macro_f1": f1,
            "mean_net": round(float(np.mean(allv)), 2), "mean_gross": round(float(np.mean([v for n in T.SOURCES for v in gross[n]])), 2),
            "n_positive": int(sum(v > 0 for v in allv)),
            "method_mean_net": {n: round(float(np.mean(net[n])), 2) for n in T.SOURCES}}


def figure(res, out):
    ths = [r["amp"] for r in res["sweep"]]
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), dpi=160, facecolor=SURF)
    for ax, key, title in ((axes[0], "method_mean_net", "扣成本報酬:3 年平均(各方法)與 9 個平均"),
                           (axes[1], None, "每年交易筆數(9 個平均)與最少的訓練點(每類)")):
        ax.set_facecolor(SURF)
        for k in ("top", "right"):
            ax.spines[k].set_visible(False)
        for k in ("left", "bottom"):
            ax.spines[k].set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=10, length=0)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.set_title(title, loc="left", fontsize=12.5, color=INK, pad=10)
        ax.set_xlabel("訓練門檻:兩邊幅度至少(%)", color=MUTED, fontsize=10)
        ax.set_xticks(ths)
    ax = axes[0]
    for n, col in COLORS.items():
        v = [r["summary"]["method_mean_net"][n] for r in res["sweep"]]
        ax.plot(ths, v, color=col, lw=2, marker="o", ms=6, mec=SURF, mew=1.5, label=n)
        ax.annotate(n, (ths[-1], v[-1]), xytext=(6, 0), textcoords="offset points", va="center", fontsize=10, color=INK)
    m = [r["summary"]["mean_net"] for r in res["sweep"]]
    ax.plot(ths, m, color=INK, lw=2.4, marker="s", ms=6, mec=SURF, mew=1.5, label="9 個平均")
    b = res["best_amp"]
    ax.annotate(f"9 個平均最好:{b:g}%({max(m):+.1f}%)", (b, max(m)), xytext=(0, 14), textcoords="offset points", ha="center", fontsize=10, color=INK)
    ax.axhline(0, color=MUTED, lw=0.8, ls=":")
    ax.set_ylabel("扣成本報酬(%)", color=MUTED, fontsize=10)
    ax.legend(frameon=False, fontsize=10, labelcolor=INK, loc="upper left")
    ax = axes[1]
    tr = [np.mean([v for n in T.SOURCES for v in r["summary"]["trades"][n]]) for r in res["sweep"]]
    mn = [min(min(c["主軸 4 年"] + c["Stacking B"]) for c in r["train_counts"].values()) for r in res["sweep"]]
    ax.plot(ths, tr, color="#2a78d6", lw=2, marker="o", ms=6, mec=SURF, mew=1.5, label="每年交易筆數(平均)")
    ax.plot(ths, mn, color="#eb6834", lw=2, marker="o", ms=6, mec=SURF, mew=1.5, label="最少的訓練點(Stacking B 某一類)")
    for x, v in zip(ths, mn):
        ax.annotate(f"{v}", (x, v), xytext=(0, -14), textcoords="offset points", ha="center", fontsize=9, color=INK)
    ax.set_ylabel("筆數 / 個數", color=MUTED, fontsize=10)
    ax.legend(frameon=False, fontsize=10, labelcolor=INK, loc="upper right")
    fig.suptitle("訓練門檻每次 +1%(34 檔、只做多前 3 檔、3 個方法 × 2024–2026;直接看測試年,沒有驗證期)",
                 x=0.02, ha="left", fontsize=14, color=INK, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.95), w_pad=3)
    fig.savefig(out, facecolor=SURF)


def grid(a, panel, fc, prices, t0):
    curves = {n: {} for n in T.SOURCES}
    alive = list(T.SOURCES)
    for amp in range(a.start, a.max + 1):
        counts = train_counts(panel, amp)
        main_min = min(min(c["主軸 4 年"]) for c in counts.values())
        b_min = min(min(c["Stacking B"]) for c in counts.values())
        if main_min < a.min_points:
            break
        run = [n for n in alive if n == "主軸" or b_min >= a.min_points]
        msg = []
        for n in run:
            try:
                yrs = T.run_all(panel, fc, prices, float(amp), log=lambda m: None, sources=[n])
            except Exception as e:
                alive.remove(n)
                msg.append(f"{n} 訓練不起來({type(e).__name__})")
                continue
            v = [yrs[str(y)][n]["扣成本"]["total_return_pct"] for y in T.YEARS]
            g = [yrs[str(y)][n]["沒扣成本"]["total_return_pct"] for y in T.YEARS]
            tr = [yrs[str(y)][n]["扣成本"]["n_trades"] for y in T.YEARS]
            f1 = [yrs[str(y)][n]["分類"]["macro_f1_pct"] for y in T.YEARS]
            curves[n][str(amp)] = {"net": v, "gross": g, "trades": tr, "macro_f1": f1, "mean_net": round(float(np.mean(v)), 2),
                                   "mean_gross": round(float(np.mean(g)), 2)}
            msg.append(f"{n} {np.mean(v):+6.2f}({'/'.join(f'{x:+.1f}' for x in v)},{sum(tr)} 筆)")
        alive = [n for n in alive if n in run or n == "主軸"]
        print(f"{amp:>2}%  " + "  ".join(msg) + f"  主軸每類最少 {main_min}、Stacking B 每類最少 {b_min}  ({time.time() - t0:.0f}s)", flush=True)
        curves.setdefault("_counts", {})[str(amp)] = counts
    with open(os.path.join(ML.OUT, "amp_sweep_grid.json"), "w", encoding="utf-8") as f:
        json.dump(curves, f, ensure_ascii=False, indent=1)
    grid_figure(curves, os.path.join(ML.OUT, "amp_sweep_grid.png"), a.min_points)
    for n in T.SOURCES:
        c = curves[n]
        b = max(c, key=lambda k: c[k]["mean_net"])
        print(f"{n}:跑到 {max(map(int, c))}%;最好 {b}%({c[b]['mean_net']:+.2f}%)")


def grid_figure(curves, out, min_points):
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), dpi=160, facecolor=SURF)
    for ax in axes:
        ax.set_facecolor(SURF)
        for k in ("top", "right"):
            ax.spines[k].set_visible(False)
        for k in ("left", "bottom"):
            ax.spines[k].set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=10, length=0)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.set_xlabel("訓練門檻:兩邊幅度至少(%)", color=MUTED, fontsize=10)
    ax = axes[0]
    for n, col in COLORS.items():
        xs = sorted(map(int, curves[n]))
        v = [curves[n][str(x)]["mean_net"] for x in xs]
        ax.plot(xs, v, color=col, lw=2, marker="o", ms=6, mec=SURF, mew=1.5, label=n)
        b = xs[int(np.argmax(v))]
        ax.annotate(f"{max(v):+.1f}%", (b, max(v)), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9.5, color=INK)
    ax.axhline(0, color=MUTED, lw=0.8, ls=":")
    ax.set_ylabel("扣成本報酬,3 年平均(%)", color=MUTED, fontsize=10)
    ax.set_title("各方法的 3 年平均扣成本報酬(標出各自最高點)", loc="left", fontsize=12.5, color=INK, pad=10)
    ax.legend(frameon=False, fontsize=10, labelcolor=INK, loc="upper left")
    ax.set_xticks(sorted(map(int, curves["主軸"])))
    ax = axes[1]
    cnt = curves["_counts"]
    xs = sorted(map(int, cnt))
    m = [min(min(c["主軸 4 年"]) for c in cnt[str(x)].values()) for x in xs]
    b = [min(min(c["Stacking B"]) for c in cnt[str(x)].values()) for x in xs]
    ax.plot(xs, m, color="#2a78d6", lw=2, marker="o", ms=6, mec=SURF, mew=1.5, label="主軸(4 年)每類最少")
    ax.plot(xs, b, color="#eb6834", lw=2, marker="o", ms=6, mec=SURF, mew=1.5, label="Stacking B(1 年)每類最少")
    for x, v in zip(xs, b):
        ax.annotate(f"{v}", (x, v), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9, color=INK)
    ax.axhline(min_points, color=MUTED, lw=1, ls="--")
    ax.set_yscale("log")
    ax.set_ylabel("訓練點數(對數刻度)", color=MUTED, fontsize=10)
    ax.set_title(f"訓練點越來越少(虛線 = {min_points} 個,少於就不再跑)", loc="left", fontsize=12.5, color=INK, pad=10)
    ax.legend(frameon=False, fontsize=10, labelcolor=INK, loc="upper right")
    ax.set_xticks(xs)
    xs_all = sorted(map(int, curves["主軸"]))
    fig.suptitle(f"訓練門檻每次 +1%({xs_all[0]}%–{xs_all[-1]}%;34 檔、只做多前 3 檔、2024–2026;直接看測試年,沒有驗證期)",
                 x=0.02, ha="left", fontsize=14, color=INK, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.95), w_pad=3)
    fig.savefig(out, facecolor=SURF)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--patience", type=int, default=2)
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--min-points", type=int, default=10)
    a = ap.parse_args()
    t0 = time.time()
    data, panel, fc, prices = T.load()
    if a.grid:
        return grid(a, panel, fc, prices, t0)
    res = {"pool": sorted(data), "patience": a.patience, "sweep": []}
    best, best_amp, since = -np.inf, None, 0
    for amp in range(a.start, a.max + 1):
        counts = train_counts(panel, amp)
        try:
            years = T.run_all(panel, fc, prices, float(amp), log=lambda m: None)
        except Exception as e:                                  # 訓練點太少、某一類沒有樣本
            res["stopped"] = f"{amp}% 訓練不起來:{type(e).__name__}: {e}"
            print(res["stopped"], flush=True)
            break
        sm = summary(years)
        res["sweep"].append({"amp": amp, "summary": sm, "train_counts": counts, "years": years})
        mn = min(min(c["主軸 4 年"] + c["Stacking B"]) for c in counts.values())
        print(f"{amp:>2}%  9 個平均 {sm['mean_net']:+6.2f}%(沒扣 {sm['mean_gross']:+6.2f}%,{sm['n_positive']} 個為正)  "
              + "  ".join(f"{n} {sm['method_mean_net'][n]:+6.2f}" for n in T.SOURCES)
              + f"  最少訓練點 {mn}  ({time.time() - t0:.0f}s)", flush=True)
        if sm["mean_net"] > best:
            best, best_amp, since = sm["mean_net"], amp, 0
        else:
            since += 1
            if since >= a.patience:
                res["stopped"] = f"連續 {a.patience} 個門檻({amp - a.patience + 1}%–{amp}%)都沒有超過 {best_amp}% 的 {best:+.2f}%"
                print(res["stopped"], flush=True)
                break
    res["best_amp"], res["best_mean_net"] = best_amp, best
    with open(os.path.join(ML.OUT, "amp_sweep.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    png = os.path.join(ML.OUT, "amp_sweep.png")
    figure(res, png)
    print(png)


if __name__ == "__main__":
    main()
