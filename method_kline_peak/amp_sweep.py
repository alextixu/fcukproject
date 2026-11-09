"""訓練門檻一路往上加(每次 +1%),跑到不再提升為止(2026-11-02 使用者要求)。

每個門檻都跑 backtest_top3 的 6 個回測(34 檔、只做多前 3 檔,2 個方法 × 2024–2026,對答案用原本的標籤)。
「提升」看 6 個扣成本報酬的平均;連續 --patience 個門檻都沒有超過目前最好的平均就停,
或某個門檻訓練不起來(某一類的訓練點太少)也停。另外記錄每個門檻的訓練點數(主軸 4 年、Stacking 的 B 1 年,每類)。
注意:這是直接看測試年選門檻,沒有驗證期。
--grid:不提早停,每個方法、每一年都跑 --start ~ --max;某一年訓練不起來(某一類 0 個訓練點)就記下原因,那個門檻不算 3 年平均
        → results/amp_sweep_grid.json、results/amp_sweep_grid.png
--pool tw200:換股票池(預設 mainline.POOL),同樣剔除低波動股;輸出檔名一律加 --tag(預設 = 股票池名稱,例 amp_sweep_grid_tw200.json),
        不覆蓋 34 檔的 results/amp_sweep*.json / .png(34 檔重跑:--pool tw50 --tag tw50_34)
--grid 另外記錄(測試年用原本的標籤;大波段 = 兩邊幅度 label_amp ≥ 5%,所有門檻相同):
  判低點個數、判低點裡「真低點且大波段」的比例;判高點同理;每年 + 3 年(個數合計、比例取逐年平均)
  隨便猜的基準 = 該年全部股票 × 天裡,真低點(真高點)且大波段的比例(和門檻無關)→ 另畫 amp_sweep_grid_<tag>_lows.png
用法: python method_kline_peak/amp_sweep.py [--pool tw200] [--start 0] [--max 20] [--patience 2] [--grid]
輸出: results/amp_sweep_<股票池>.json / .png(--grid:amp_sweep_grid_<股票池>.json / .png)
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

BIG = 5.0          # 大波段:幅度 ≥ 5%
BIG_KEYS = ("n_pred_low", "n_big_low", "n_pred_high", "n_big_high")

COLORS = {"主軸": "#2a78d6", "Stacking 邏輯迴歸": "#eb6834"}
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
    for ax, key, title in ((axes[0], "method_mean_net", "扣成本報酬:3 年平均(各方法)與 6 個平均"),
                           (axes[1], None, "每年交易筆數(6 個平均)與最少的訓練點(每類)")):
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
    ax.plot(ths, m, color=INK, lw=2.4, marker="s", ms=6, mec=SURF, mew=1.5, label="6 個平均")
    b = res["best_amp"]
    ax.annotate(f"6 個平均最好:{b:g}%({max(m):+.1f}%)", (b, max(m)), xytext=(0, 14), textcoords="offset points", ha="center", fontsize=10, color=INK)
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
    fig.suptitle(f"訓練門檻每次 +1%({len(res['pool'])} 檔、只做多前 3 檔、2 個方法 × 2024–2026;直接看測試年,沒有驗證期)",
                 x=0.02, ha="left", fontsize=14, color=INK, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.95), w_pad=3)
    fig.savefig(out, facecolor=SURF)


def big_metrics(sig, look):
    """判低點 / 判高點的計數:判了幾個、其中「真低點(真高點)且兩邊幅度 ≥ BIG」幾個。"""
    m = sig[["date", "ticker", "pred", "y"]].merge(look[["date", "ticker", "amp"]], on=["date", "ticker"], how="left", validate="one_to_one")
    big = m.amp >= BIG
    lo, hi = m.pred == UP, m.pred == DOWN
    return {"n_pred_low": int(lo.sum()), "n_big_low": int((lo & (m.y == UP) & big).sum()),
            "n_pred_high": int(hi.sum()), "n_big_high": int((hi & (m.y == DOWN) & big).sum())}


def pct(n, d):
    return round(n / d * 100, 3) if d else None


def add_ratios(c):
    return {**c, "低點大波段比例": pct(c["n_big_low"], c["n_pred_low"]), "高點大波段比例": pct(c["n_big_high"], c["n_pred_high"])}


def base_rate(look):
    """隨便猜的基準:每個測試年全部股票 × 天裡,真低點(真高點)且兩邊幅度 ≥ BIG 的比例;和門檻無關。"""
    out = {}
    for y in T.YEARS:
        t = look[look.date.dt.year == y]
        big = t.amp >= BIG
        n_low, n_high = int(((t.y == UP) & big).sum()), int(((t.y == DOWN) & big).sum())
        out[str(y)] = {"n_days": int(len(t)), "n_big_low": n_low, "n_big_high": n_high,
                       "低點": pct(n_low, len(t)), "高點": pct(n_high, len(t))}
    out["3 年平均"] = {k: round(float(np.mean([out[str(y)][k] for y in T.YEARS])), 3) for k in ("低點", "高點")}
    return out


def grid(a, data, panel, fc, prices, t0):
    """每個門檻、每個方法、每一年都試著訓練;訓練不起來(某一類沒有訓練點)就記下原因,不影響其他組合。"""
    curves = {n: {} for n in T.SOURCES}
    look = panel[["date", "ticker", "y", "amp"]]
    on_signal = lambda sig: big_metrics(sig, look)  # noqa: E731
    for amp in range(a.start, a.max + 1):
        counts = train_counts(panel, amp)
        msg = []
        for n in T.SOURCES:
            row = {"net": [], "gross": [], "trades": [], "macro_f1": [], "failed": {}, "lows": {}}
            for y in T.YEARS:
                try:
                    r = T.run_all(panel, fc, prices, float(amp), log=lambda m: None, sources=[n], years=[y], on_signal=on_signal)[str(y)][n]
                except Exception as e:                      # 例如某一類 0 個訓練點
                    row["failed"][str(y)] = f"{type(e).__name__}: {str(e)[:120]}"
                    for k in ("net", "gross", "trades", "macro_f1"):
                        row[k].append(None)
                    continue
                row["net"].append(r["扣成本"]["total_return_pct"])
                row["gross"].append(r["沒扣成本"]["total_return_pct"])
                row["trades"].append(r["扣成本"]["n_trades"])
                row["macro_f1"].append(r["分類"]["macro_f1_pct"])
                row["lows"][str(y)] = add_ratios(r["訊號指標"])
            ok = not row["failed"]
            if ok:                                            # 3 年平均 = 逐年比例的平均;個數 = 3 年合計
                yrs = [row["lows"][str(y)] for y in T.YEARS]
                row["lows"]["3 年"] = {**{k: sum(v[k] for v in yrs) for k in BIG_KEYS},
                                      **{k: (round(float(np.mean([v[k] for v in yrs])), 3) if all(v[k] is not None for v in yrs) else None)
                                         for k in ("低點大波段比例", "高點大波段比例")}}
            row["mean_net"] = round(float(np.mean(row["net"])), 2) if ok else None
            row["mean_gross"] = round(float(np.mean(row["gross"])), 2) if ok else None
            curves[n][str(amp)] = row
            vals = "/".join("失敗" if v is None else f"{v:+.1f}" for v in row["net"])
            msg.append(f"{n} {row['mean_net']:+6.2f}({vals},{sum(t for t in row['trades'] if t)} 筆)" if ok else f"{n} --({vals})")
        curves.setdefault("_counts", {})[str(amp)] = counts
        main_min = min(min(c["主軸 4 年"]) for c in counts.values())
        b_min = min(min(c["Stacking B"]) for c in counts.values())
        print(f"{amp:>2}%  " + "  ".join(msg) + f"  主軸每類最少 {main_min}、Stacking B 每類最少 {b_min}  ({time.time() - t0:.0f}s)", flush=True)
    curves["_pool"] = {"name": a.pool, "tag": a.tag, "n_stocks": a.n_stocks, "big_pct": BIG}
    curves["_base_rate"] = base_rate(look)
    stem = os.path.join(ML.OUT, f"amp_sweep_grid_{a.tag}")
    with open(stem + ".json", "w", encoding="utf-8") as f:
        json.dump(curves, f, ensure_ascii=False, indent=1)
    grid_figure(curves, stem + ".png", a.n_stocks)
    lows_figure(curves, stem + "_lows.png", a.n_stocks)
    for n in T.SOURCES:
        c = {k: v for k, v in curves[n].items() if v["mean_net"] is not None}
        b = max(c, key=lambda k: c[k]["mean_net"])
        print(f"{n}:3 年都訓練得起來的門檻 {sorted(map(int, c))};最好 {b}%({c[b]['mean_net']:+.2f}%)")


def lows_figure(curves, out, n_stocks):
    """門檻 vs 判低點裡大波段的比例(3 年平均);虛線 = 隨便猜的基準。"""
    fig, ax = plt.subplots(figsize=(10, 6), dpi=160, facecolor=SURF)
    ax.set_facecolor(SURF)
    for k in ("top", "right"):
        ax.spines[k].set_visible(False)
    for k in ("left", "bottom"):
        ax.spines[k].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=10, length=0)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for n, col in COLORS.items():
        xs = [x for x in sorted(map(int, curves[n])) if curves[n][str(x)]["lows"].get("3 年", {}).get("低點大波段比例") is not None]
        v = [curves[n][str(x)]["lows"]["3 年"]["低點大波段比例"] for x in xs]
        ax.plot(xs, v, color=col, lw=2, marker="o", ms=6, mec=SURF, mew=1.5, label=n)
    br = curves["_base_rate"]["3 年平均"]["低點"]
    ax.axhline(br, color=MUTED, lw=1.2, ls="--", label=f"隨便猜的基準 {br:.2f}%")
    ax.set_ylim(bottom=0)
    ax.set_xticks(sorted(map(int, curves["主軸"])))
    ax.set_xlabel("訓練門檻:兩邊幅度至少(%)", color=MUTED, fontsize=10)
    ax.set_ylabel("比例(%,3 年平均)", color=MUTED, fontsize=10)
    ax.legend(frameon=False, fontsize=10, labelcolor=INK, loc="upper left")
    ax.set_title(f"判低點裡「真低點且兩邊幅度 ≥ {BIG:g}%」的比例({n_stocks} 檔、2024–2026 平均;對答案用原本的標籤;"
                 "有一年訓練不起來就不畫)", loc="left", fontsize=12, color=INK, pad=10)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURF)


def grid_figure(curves, out, n_stocks=34):
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
        xs = [x for x in sorted(map(int, curves[n])) if curves[n][str(x)]["mean_net"] is not None]
        v = [curves[n][str(x)]["mean_net"] for x in xs]
        ax.plot(xs, v, color=col, lw=2, marker="o", ms=6, mec=SURF, mew=1.5, label=n)
        b = xs[int(np.argmax(v))]
        ax.annotate(f"{max(v):+.1f}%", (b, max(v)), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9.5, color=INK)
    ax.axhline(0, color=MUTED, lw=0.8, ls=":")
    ax.set_ylabel("扣成本報酬,3 年平均(%)", color=MUTED, fontsize=10)
    ax.set_title("各方法的 3 年平均扣成本報酬(標出各自最高點;有一年訓練不起來就不畫)", loc="left", fontsize=12.5, color=INK, pad=10)
    ax.legend(frameon=False, fontsize=10, labelcolor=INK, loc="lower right")
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
    ax.set_yscale("symlog", linthresh=1)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("訓練點數(對數刻度)", color=MUTED, fontsize=10)
    ax.set_title("訓練點越來越少(0 個 = 那一類訓練不起來)", loc="left", fontsize=12.5, color=INK, pad=10)
    ax.legend(frameon=False, fontsize=10, labelcolor=INK, loc="upper right")
    ax.set_xticks(xs)
    xs_all = sorted(map(int, curves["主軸"]))
    fig.suptitle(f"訓練門檻每次 +1%({xs_all[0]}%–{xs_all[-1]}%;{n_stocks} 檔、只做多前 3 檔、2024–2026;直接看測試年,沒有驗證期)",
                 x=0.02, ha="left", fontsize=14, color=INK, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.95), w_pad=3)
    fig.savefig(out, facecolor=SURF)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--patience", type=int, default=2)
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--pool", default=ML.POOL, help="股票池(預設 mainline.POOL)")
    ap.add_argument("--tag", default=None, help="輸出檔名後綴(預設 = 股票池名稱)")
    a = ap.parse_args()
    t0 = time.time()
    data, panel, fc, prices = T.load(a.pool)
    a.n_stocks = len(data)
    a.tag = a.tag or a.pool
    if a.grid:
        return grid(a, data, panel, fc, prices, t0)
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
        print(f"{amp:>2}%  6 個平均 {sm['mean_net']:+6.2f}%(沒扣 {sm['mean_gross']:+6.2f}%,{sm['n_positive']} 個為正)  "
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
    with open(os.path.join(ML.OUT, f"amp_sweep_{a.tag}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    png = os.path.join(ML.OUT, f"amp_sweep_{a.tag}.png")
    figure(res, png)
    print(png)


if __name__ == "__main__":
    main()
