"""標籤的幅度:高點 / 低點兩邊差多少,是不是真的倒 V / V,幅度門檻要定多少。

幅度 = 兩邊較小那邊
  高點:min(從前 5 天最低收盤漲到 t,從 t 跌到後 5 天最低收盤)
  低點:min(從前 5 天最高收盤跌到 t,從 t 漲到後 5 天最高收盤)
也算以該股到 t 為止 20 天日報酬標準差(σ)為單位的幅度。
「抓到後交易」= 假設完全抓對這個點:t+1 開盤進場、t+5 收盤出場(低點做多;高點看放空),扣成本 0.585%。
這是事後看答案的上限,只用來比較不同門檻留下的點值不值得交易,不是模型的成績。
用法: python method_kline_peak/label_amplitude.py
輸出: results/label_amplitude.json、results/label_amplitude.png
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import mainline as ML  # noqa: E402
from feasibility import START, END, load_pool, clean  # noqa: E402
from paper_aeocsvm import paper_label  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402

COST = 1 - (1 - 0.001425 - 0.003) / (1 + 0.001425)
PCT_TH, SIG_TH = (1, 1.5, 2, 3, 5), (0.5, 1, 1.5, 2, 3)
BINS = [0, 1, 1.5, 2, 3, 5, np.inf]
BIN_NAMES = ["< 1%", "1–1.5%", "1.5–2%", "2–3%", "3–5%", "≥ 5%"]
SHAPE_GROUPS = [("< 1%", 0, 1), ("1–2%", 1, 2), ("≥ 2%", 2, np.inf)]
INK, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"
RAMP = {UP: ["#86b6ef", "#2a78d6", "#104281"], DOWN: ["#f0956b", "#eb6834", "#a8441c"]}
NAME = {UP: "低點", DOWN: "高點"}
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False


def collect():
    data = load_pool(ML.POOL, START, END)
    rows, paths = [], []
    for tk, df in data.items():
        df = clean(df)
        c, o = df["close"], df["open"]
        y, _, _ = paper_label(c)
        v, ov = c.to_numpy(), o.to_numpy()
        sig = np.log(c).diff().rolling(20).std().to_numpy() * 100
        for i in range(20, len(v) - 5):
            if c.index[i] < pd.Timestamp(START) or pd.isna(y.iloc[i]) or int(y.iloc[i]) not in (UP, DOWN):
                continue
            L, R, t, cls = v[i - 5:i], v[i + 1:i + 6], v[i], int(y.iloc[i])
            if cls == DOWN:
                amp = min(t / L.min() - 1, 1 - R.min() / t) * 100
            else:
                amp = min(1 - t / L.max(), R.max() / t - 1) * 100
            move = (v[i + 5] / ov[i + 1] - 1) * 100
            rows.append((tk, c.index[i], cls, amp, sig[i], (move if cls == UP else -move) - COST * 100))
            paths.append((v[i - 5:i + 6] / t - 1) * 100)
    d = pd.DataFrame(rows, columns=["ticker", "date", "y", "amp", "sigma", "net"])
    d["amp_sig"] = d.amp / d.sigma
    return d, np.array(paths)


def summarize(d):
    out = {"period": [str(d.date.min().date()), str(d.date.max().date())], "cost_pct": round(COST * 100, 3),
           "sigma_median_pct": round(float(d.sigma.median()), 2)}
    for cls in (UP, DOWN):
        s = d[d.y == cls]
        r = {"n": len(s), "all": {"net_mean_pct": round(float(s.net.mean()), 2), "win_pct": round(float((s.net > 0).mean()) * 100, 1)}}
        for col, ths, unit in (("amp", PCT_TH, "%"), ("amp_sig", SIG_TH, "σ")):
            for th in ths:
                k = s[col] >= th
                r[f"≥ {th}{unit}"] = {"kept_pct": round(float(k.mean()) * 100, 1), "kept_n": int(k.sum()),
                                      "kept_net_mean_pct": round(float(s.net[k].mean()), 2), "kept_win_pct": round(float((s.net[k] > 0).mean()) * 100, 1),
                                      "dropped_net_mean_pct": round(float(s.net[~k].mean()), 2), "dropped_win_pct": round(float((s.net[~k] > 0).mean()) * 100, 1)}
        g = s.groupby(pd.cut(s.amp, BINS, right=False), observed=True).net
        r["by_amp_bin"] = {n: {"n": int(c), "net_mean_pct": round(float(m), 2), "win_pct": round(float(w) * 100, 1)}
                           for n, c, m, w in zip(BIN_NAMES, g.size(), g.mean(), g.apply(lambda x: (x > 0).mean()))}
        out[NAME[cls]] = r
    return out


def style(ax):
    ax.set_facecolor(SURF)
    for k in ("top", "right"):
        ax.spines[k].set_visible(False)
    for k in ("left", "bottom"):
        ax.spines[k].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=10, length=0)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def figure(d, P, out):
    fig, axes = plt.subplots(2, 2, figsize=(15, 10.5), dpi=160, facecolor=SURF)
    x = np.arange(-5, 6)
    for ax, cls in zip(axes[0], (UP, DOWN)):                 # 上排:平均形狀
        style(ax)
        m = (d.y == cls).to_numpy()
        for (lab, lo, hi), col in zip(SHAPE_GROUPS, RAMP[cls]):
            k = m & (d.amp >= lo).to_numpy() & (d.amp < hi).to_numpy()
            med = np.median(P[k], axis=0)
            ax.plot(x, med, color=col, lw=2, marker="o", ms=5, label=f"幅度 {lab}({k.sum() / m.sum():.0%})")
            ax.annotate(lab, (5, med[-1]), xytext=(6, 0), textcoords="offset points", va="center", fontsize=10, color=INK)
        ax.axvline(0, color=GRID, lw=1)
        ax.axhline(0, color=MUTED, lw=0.8, ls=":")
        ax.set_xticks(x)
        ax.set_xticklabels([f"t{i:+d}" if i else "t" for i in x])
        ax.set_xlim(-5.4, 6.2)
        ax.set_ylabel("收盤相對 t 日收盤(%)", color=MUTED, fontsize=10)
        ax.set_title(f"{NAME[cls]}的平均形狀(中位數),依兩邊較小的幅度分三組", loc="left", fontsize=12.5, color=INK, pad=10)
        ax.legend(frameon=False, fontsize=10, loc="upper center" if cls == UP else "lower center", labelcolor=INK)

    ax = axes[1, 0]                                           # 左下:門檻留下多少標籤
    style(ax)
    ths = np.linspace(0, 6, 121)
    for cls, col in ((UP, BLUE), (DOWN, ORANGE)):
        a = d.amp[d.y == cls].to_numpy()
        kept = [(a >= t).mean() * 100 for t in ths]
        ax.plot(ths, kept, color=col, lw=2, label=NAME[cls])
        for t in (1, 2, 3):
            ax.plot(t, (a >= t).mean() * 100, "o", color=col, ms=8, mec=SURF, mew=2)
    for t in (1, 2, 3):
        ku, kd = ((d.amp[d.y == c] >= t).mean() * 100 for c in (UP, DOWN))
        ax.annotate(f"≥ {t}%:低 {ku:.0f}% / 高 {kd:.0f}%", (t, max(ku, kd)), xytext=(8, 8), textcoords="offset points", fontsize=10, color=INK)
    ax.axvline(2, color=MUTED, lw=1, ls="--")
    ax.set_xlabel("門檻:兩邊都至少差多少(%)", color=MUTED, fontsize=10)
    ax.set_ylabel("留下的標籤比例(%)", color=MUTED, fontsize=10)
    ax.set_ylim(0, 105)
    ax.set_title("門檻越高,留下的高點 / 低點越少", loc="left", fontsize=12.5, color=INK, pad=10)
    ax.legend(frameon=False, fontsize=10, labelcolor=INK)

    ax = axes[1, 1]                                           # 右下:依幅度分組,完全抓對後交易的扣成本報酬
    style(ax)
    w, xb = 0.38, np.arange(len(BIN_NAMES))
    for j, (cls, col, lab) in enumerate(((UP, BLUE, "低點(做多)"), (DOWN, ORANGE, "高點(放空)"))):
        s = d[d.y == cls]
        g = s.groupby(pd.cut(s.amp, BINS, right=False), observed=True).net.mean().to_numpy()
        bars = ax.bar(xb + (j - 0.5) * (w + 0.02), g, w, color=col, label=lab)
        for b, v in zip(bars, g):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.12, f"{v:+.1f}", ha="center", fontsize=9, color=INK)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xticks(xb)
    ax.set_xticklabels(BIN_NAMES)
    ax.set_xlabel("兩邊較小的幅度", color=MUTED, fontsize=10)
    ax.set_ylabel("t+1 開盤 → t+5 收盤,扣成本 0.585%(%)", color=MUTED, fontsize=10)
    ax.set_title("假設完全抓對:小幅度的點扣完成本幾乎不賺", loc="left", fontsize=12.5, color=INK, pad=10)
    ax.legend(frameon=False, fontsize=10, labelcolor=INK, loc="upper left")

    fig.suptitle(f"TW50 標籤幅度({d.date.min():%Y-%m}–{d.date.max():%Y-%m},低點 {(d.y == UP).sum():,} 個、高點 {(d.y == DOWN).sum():,} 個)",
                 x=0.02, ha="left", fontsize=15, color=INK, y=0.995)
    fig.text(0.02, 0.005, "幅度 = 兩邊較小那邊:高點 = min(前 5 天最低漲到 t, t 跌到後 5 天最低);低點反之。"
             "右下是事後看答案的上限,不是模型的成績。", fontsize=10, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97), h_pad=3, w_pad=3)
    fig.savefig(out, facecolor=SURF)


def main():
    d, P = collect()
    res = summarize(d)
    with open(os.path.join(ML.OUT, "label_amplitude.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    png = os.path.join(ML.OUT, "label_amplitude.png")
    figure(d, P, png)
    print(json.dumps({k: res[k] for k in ("period", "cost_pct", "sigma_median_pct")}, ensure_ascii=False))
    for n in ("低點", "高點"):
        print(n, res[n]["n"], {k: (v["kept_pct"], v["kept_net_mean_pct"], v["kept_win_pct"], v["dropped_net_mean_pct"], v["dropped_win_pct"])
                               for k, v in res[n].items() if k.startswith("≥")})
        print("  分組", {k: (v["n"], v["net_mean_pct"], v["win_pct"]) for k, v in res[n]["by_amp_bin"].items()})
    print(png)


if __name__ == "__main__":
    main()
