"""把「大漲」正例畫成 K 線圖看長相:訊號日前 20 天(AE 看到的視窗)+ 後 5 天(標籤區間),以及全部正例的中位路徑。
用法:python plot_bigmove_samples.py --pool all --k-sigma 6 [--n 16] [--seed 0]  → figs/bigmove_samples_<pool>_k<k>.png、bigmove_median_<pool>_k<k>.png
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402

DATA = os.path.join(P.CACHE, "bigmove")
FIGS = os.path.join(HERE, "figs")
os.makedirs(FIGS, exist_ok=True)
plt.rcParams["font.family"] = ["Noto Sans CJK TC", "Noto Sans CJK JP", "WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def candles(ax, df, t_idx):
    x = np.arange(len(df))
    up = df["close"] >= df["open"]
    ax.bar(x, df["high"] - df["low"], bottom=df["low"], width=0.25, color=np.where(up, "#d62728", "#2ca02c"))
    ax.bar(x, (df["close"] - df["open"]).abs(), bottom=np.minimum(df["open"], df["close"]), width=0.8, color=np.where(up, "#d62728", "#2ca02c"))
    ax.axvline(t_idx + 0.5, color="k", ls="--", lw=0.8)
    ax2 = ax.twinx()
    ax2.bar(x, df["volume"] / 1000, width=0.8, color="#1f77b4", alpha=0.25)
    ax2.set_ylim(0, df["volume"].max() / 1000 * 3)
    ax2.set_yticks([])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="all")
    ap.add_argument("--k-sigma", type=float, default=6)
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--before", type=int, default=20)
    ap.add_argument("--after", type=int, default=5)
    a = ap.parse_args()
    s = pd.read_parquet(os.path.join(DATA, f"samples_{a.pool}.parquet"), columns=["r_h5", "sigma20", "roc_20", "a_vol_ratio"])
    thr = a.k_sigma * s["sigma20"] * np.sqrt(5)
    pos = s[s["r_h5"] > thr]
    print(f"{a.pool} {a.k_sigma:g}σ 正例 {len(pos):,} / {len(s):,}")
    rng = np.random.default_rng(a.seed)
    pick = pos.iloc[rng.choice(len(pos), a.n, replace=False)].sort_index()
    # ── 圖 1:抽樣 K 線 ──
    ncol = 4
    nrow = int(np.ceil(a.n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 2.9 * nrow))
    for ax, ((d, tk), r) in zip(axes.ravel(), pick.iterrows()):
        px = pd.read_parquet(os.path.join(P.YF_2026_CACHE, f"{tk}.parquet"))
        i = px.index.get_loc(d)
        w = px.iloc[max(0, i - a.before + 1): i + a.after + 1]
        candles(ax, w, a.before - 1)
        ax.set_title(f"{tk} {d.date()}  後5日 {r['r_h5']*100:+.1f}%(門檻 {thr.loc[(d, tk)]*100:.0f}%)\n前20日 {r['roc_20']*100:+.1f}%  當日量比 {r['a_vol_ratio']+1:.1f}x", fontsize=8)
        ax.set_xticks([0, a.before - 1, len(w) - 1]); ax.set_xticklabels(["-20", "t", "+5"], fontsize=7)
        ax.tick_params(axis="y", labelsize=7)
    for ax in axes.ravel()[len(pick):]:
        ax.axis("off")
    fig.suptitle(f"{a.pool} 池 {a.k_sigma:g}σ√5 正例隨機 {a.n} 個:虛線左邊 20 天是 AE 的輸入視窗,右邊 5 天是標籤區間(紅漲綠跌,藍為成交量)", fontsize=10)
    fig.tight_layout()
    f1 = os.path.join(FIGS, f"bigmove_samples_{a.pool}_k{a.k_sigma:g}.png")
    fig.savefig(f1, dpi=110); plt.close(fig)
    # ── 圖 2:全部正例 vs 非正例 的中位路徑(收盤、量)──
    cols = [f"b_c{k}" for k in range(a.before)] + [f"b_v{k}" for k in range(a.before)]
    b = pd.read_parquet(os.path.join(DATA, f"samples_{a.pool}.parquet"), columns=cols + ["r_h5", "sigma20"])
    y = b["r_h5"] > a.k_sigma * b["sigma20"] * np.sqrt(5)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 3.8))
    x = np.arange(-a.before + 1, 1)
    for m, lab, c in ((y, f"正例({y.sum():,})", "#d62728"), (~y, f"非正例({(~y).sum():,})", "#7f7f7f")):
        cc = [b.loc[m, f"b_c{k}"].quantile(q) * 100 for k in range(a.before - 1, -1, -1) for q in (0.5,)]
        q25 = [b.loc[m, f"b_c{k}"].quantile(0.25) * 100 for k in range(a.before - 1, -1, -1)]
        q75 = [b.loc[m, f"b_c{k}"].quantile(0.75) * 100 for k in range(a.before - 1, -1, -1)]
        ax1.plot(x, cc, color=c, label=lab + " 中位"); ax1.fill_between(x, q25, q75, color=c, alpha=0.12)
        vv = [b.loc[m, f"b_v{k}"].median() for k in range(a.before - 1, -1, -1)]
        ax2.plot(x, vv, color=c, label=lab)
    ax1.set_title("收盤相對訊號日收盤(%),帶 = 四分位"); ax1.axhline(0, color="k", lw=0.5); ax1.legend(fontsize=8); ax1.set_xlabel("距訊號日天數")
    ax2.set_title("成交量 log(當日量 / 60 日均量)中位"); ax2.axhline(0, color="k", lw=0.5); ax2.legend(fontsize=8); ax2.set_xlabel("距訊號日天數")
    fig.suptitle(f"{a.pool} 池 {a.k_sigma:g}σ√5:AE 輸入視窗的中位路徑,正例 vs 非正例", fontsize=10)
    fig.tight_layout()
    f2 = os.path.join(FIGS, f"bigmove_median_{a.pool}_k{a.k_sigma:g}.png")
    fig.savefig(f2, dpi=110); plt.close(fig)
    print("[SAVED]", f1, f2)


if __name__ == "__main__":
    main()
