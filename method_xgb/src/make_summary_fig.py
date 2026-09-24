"""從 experiments/<tag>.json 重畫較乾淨的十分位對比圖(挑選特徵集、圖例放外面)。

用法: python src/make_summary_fig.py --tag e1-tw50-h1 --sets classic4,paper9,full,full_top20
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = ["Microsoft JhengHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--sets", default="ma,macd,kd,rsi,classic4,paper9,full,full_top20")
    ap.add_argument("--h", type=int)
    a = ap.parse_args()
    d = json.load(open(os.path.join(ROOT, "experiments", f"{a.tag}.json"), encoding="utf-8"))
    h = a.h or d["config"]["horizon"]
    sets = [s for s in a.sets.split(",") if s in d["results"]]
    x = np.arange(10)
    width = 0.8 / len(sets)
    fig, ax = plt.subplots(figsize=(12, 5))
    for i, s in enumerate(sets):
        r = d["results"][s]["ensemble"]["decile"][f"h{h}"]
        sm = d["results"][s]["summary"]
        ax.bar(x + i * width, r["decile_ann_ret_pct"], width,
               label=f"{s} ({d['results'][s]['n_feat']} 欄)  H-L {r['hl_ann_ret_pct']:+.0f}%  "
                     f"t={r['hl_t_stat']:.1f}  ρ={r['monotonic_spearman']:+.2f}  "
                     f"AUC {sm['auc']['mean']:.3f}")
    ax.axhline(d["results"][sets[0]]["ensemble"]["decile"][f"h{h}"]["bench_ann_ret_pct"],
               color="gray", lw=0.8, ls="--", label="等權基準")
    ax.axhline(0, color="black", lw=0.5)
    ax.set_xticks(x + width * (len(sets) - 1) / 2)
    ax.set_xticklabels([str(i + 1) for i in range(10)])
    ax.set_xlabel("分位(1 = 模型最看壞 … 10 = 最看好)")
    ax.set_ylabel(f"年化報酬 %(h={h},零成本)")
    ax.set_title(f"{a.tag}:十分位多空,test 2024,3-seed 平均機率")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=8, frameon=False)
    fig.tight_layout()
    out = os.path.join(ROOT, "figs", f"{a.tag}_decile_h{h}_clean.png")
    fig.savefig(out, dpi=140, bbox_inches="tight")
    print("[SAVED]", out)


if __name__ == "__main__":
    main()
