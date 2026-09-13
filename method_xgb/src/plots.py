import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["font.family"] = ["Microsoft JhengHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def decile_bars(results: dict, h: int, path: str, title: str):
    """results: {name: decile dict}。多組並排。"""
    names = [n for n, r in results.items() if r]
    if not names:
        return
    n_dec = 10
    fig, ax = plt.subplots(figsize=(11, 4.5))
    width = 0.8 / len(names)
    x = np.arange(n_dec)
    for i, n in enumerate(names):
        r = results[n]
        ax.bar(x + i * width, r["decile_ann_ret_pct"], width,
               label=f"{n}  H-L {r['hl_ann_ret_pct']:+.1f}%  ρ={r['monotonic_spearman']:+.2f}")
        ax.axhline(r["bench_ann_ret_pct"], color="gray", lw=0.6, ls="--")
    ax.set_xticks(x + width * (len(names) - 1) / 2)
    ax.set_xticklabels([str(i + 1) for i in range(n_dec)])
    ax.set_xlabel("分位(1=最看壞, 10=最看好)")
    ax.set_ylabel(f"年化報酬 % (h={h})")
    ax.set_title(title)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def importance_bars(imp: pd.DataFrame, path: str, top: int = 40):
    d = imp.sort_values("rank_mean").head(top)
    fig, ax = plt.subplots(figsize=(8, 0.25 * top + 1))
    ax.barh(d.index[::-1], d["gain_mean"][::-1] * 100, xerr=None)
    ax.set_xlabel("total gain share %(3 seeds 平均)")
    ax.set_title(f"重要性前 {top} 名(依合成排名)")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def family_bars(imp: pd.DataFrame, path: str):
    g = imp.groupby("family").agg(gain=("gain_mean", "sum"), perm=("perm_mean", "sum"),
                                  n=("gain_mean", "size"))
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
    ax[0].bar(g.index, g["gain"] * 100)
    ax[0].set_title("各族群 gain share 總和 %")
    ax[1].bar(g.index, g["perm"] * 100)
    ax[1].set_title("各族群 permutation AUC 下降總和 (×100)")
    for a in ax:
        a.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def rfe_curve(rows: list, path: str):
    d = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(6, 3.8))
    ax.plot(d["n_feat"], d["val_auc"], marker="o")
    ax.set_xlabel("特徵數")
    ax.set_ylabel("val AUC")
    ax.set_xscale("log")
    ax.set_title("特徵數 vs val AUC")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
