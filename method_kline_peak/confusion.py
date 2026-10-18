"""learn5_trade6 的 LightGBM 三分類:accuracy 與混淆矩陣(漲 / 不漲不跌 / 跌)。

兩種判法
  argmax  三類機率取最大(一般三分類的 accuracy)
  前1%    預設判不漲不跌;P(漲) 排前 1% 判漲、P(跌) 排前 1% 判跌(兩者都中取機率大者),
          對應「只要最有把握的挑得出漲跌,其餘不漲不跌也沒關係」
每格:筆數與列百分比(真實為該類中被判成各類的比例,顏色深淺依列百分比);
橫軸標籤下方:該欄被判的筆數與命中率(precision)。

用法: python method_kline_peak/confusion.py --pool tw50
輸出: method_kline_peak/results/confusion_<pool>.json、confusion_<pool>.png
"""
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from sklearn.metrics import confusion_matrix, f1_score  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from feasibility import START, END, load_pool  # noqa: E402
from tail_precision import FOLDS, lgb_proba  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN, NAMES, LABELS, RAW5, build_panel, split  # noqa: E402

OUT = os.path.join(HERE, "results")
ORDER = [UP, FLAT, DOWN]                         # 顯示順序:漲 / 不漲不跌 / 跌
LABEL_TEXT = {"pct3": "±3%", "sig1": "±1σ"}
TOP_Q = 0.01
# 依序列(sequential)單一藍色色階,淺 → 深(dataviz 參考色票 100 → 650)
CMAP = LinearSegmentedColormap.from_list("blue", ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#104281"])
INK, INK_MUTED, SURFACE = "#1f1f1d", "#5f5e5a", "#ffffff"


def selective_pred(proba):
    pred = np.full(len(proba), FLAT)
    up = proba[:, UP] >= np.quantile(proba[:, UP], 1 - TOP_Q)
    dn = proba[:, DOWN] >= np.quantile(proba[:, DOWN], 1 - TOP_Q)
    pred[up] = UP
    pred[dn & (~up | (proba[:, DOWN] > proba[:, UP]))] = DOWN
    return pred


def summarize(y, pred):
    cm = confusion_matrix(y, pred, labels=ORDER)
    col = cm.sum(axis=0)
    row = cm.sum(axis=1)
    return {
        "acc": float((y == pred).mean()),
        "majority_acc": float(max((y == c).mean() for c in ORDER)),
        "macro_f1": float(f1_score(y, pred, labels=ORDER, average="macro", zero_division=0)),
        "confusion_rows_true_cols_pred(漲,不漲不跌,跌)": cm.tolist(),
        "precision": {NAMES[c]: float(cm[i, i] / col[i]) if col[i] else None for i, c in enumerate(ORDER)},
        "recall": {NAMES[c]: float(cm[i, i] / row[i]) if row[i] else None for i, c in enumerate(ORDER)},
    }


def draw(ax, s, title):
    cm = np.array(s["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"])
    pct = cm / cm.sum(axis=1, keepdims=True)
    ax.imshow(pct, cmap=CMAP, vmin=0, vmax=1)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{cm[i, j]:,}\n{pct[i, j]:.0%}", ha="center", va="center", fontsize=10,
                    color=SURFACE if pct[i, j] > 0.55 else INK)
    names = [NAMES[c] for c in ORDER]
    col = cm.sum(axis=0)
    xt = [f"{n}\n判 {col[j]:,} 筆" + (f"\n命中 {cm[j, j] / col[j]:.0%}" if col[j] else "\n命中 —")
          for j, n in enumerate(names)]
    ax.set_xticks(range(3), xt, fontsize=9, color=INK)
    ax.set_yticks(range(3), names, fontsize=10, color=INK)
    ax.set_xlabel("模型判斷", fontsize=9, color=INK_MUTED)
    ax.set_ylabel("實際", fontsize=9, color=INK_MUTED, labelpad=8)
    ax.set_title(f"{title}\nacc {s['acc']:.1%}(全猜不漲不跌 {s['majority_acc']:.1%})  macro-F1 {s['macro_f1']:.2f}",
                 fontsize=10, color=INK, loc="left")
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    ax.set_xticks(np.arange(-.5, 3), minor=True)
    ax.set_yticks(np.arange(-.5, 3), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2)     # 格與格之間 2px 留白
    ax.tick_params(which="minor", length=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="tw50")
    args = ap.parse_args()
    plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
    panel = build_panel(load_pool(args.pool, START, END))

    out, cells = {}, []
    for fold_name, fold in FOLDS.items():
        for label in LABELS:
            ycol = f"y_{label}"
            sp = {k: d.assign(y=d[ycol]) for k, d in split(panel, fold).items()}
            proba = lgb_proba(sp["train"], sp["val"], sp["test"], RAW5)
            y = sp["test"]["y"].to_numpy()
            key = f"{fold_name}|{label}"
            out[key] = {"argmax": summarize(y, proba.argmax(axis=1)),
                        "top1pct": summarize(y, selective_pred(proba))}
            cells.append((fold_name, label, out[key]))
            print(f"{key:<15} argmax acc {out[key]['argmax']['acc']:.1%}  前1% acc {out[key]['top1pct']['acc']:.1%}  "
                  f"全猜不漲不跌 {out[key]['argmax']['majority_acc']:.1%}", flush=True)

    fig, axes = plt.subplots(2, len(cells), figsize=(5.4 * len(cells), 13.5), facecolor=SURFACE)
    for j, (fold_name, label, r) in enumerate(cells):
        head = f"測試 {fold_name} · 不漲不跌帶寬 {LABEL_TEXT[label]}"
        draw(axes[0, j], r["argmax"], f"{head}\n判法:三類取機率最大")
        draw(axes[1, j], r["top1pct"], f"{head}\n判法:只有前 1% 判漲 / 跌")
    fig.suptitle(f"{args.pool.upper()}:學第 1–5 天 → 第 11 天收盤 vs 第 6 天開盤(LightGBM)",
                 fontsize=14, color=INK, x=0.01, ha="left")
    fig.subplots_adjust(left=0.05, right=0.99, top=0.9, bottom=0.09, wspace=0.4, hspace=0.62)
    png = os.path.join(OUT, f"confusion_{args.pool}.png")
    fig.savefig(png, dpi=110, facecolor=SURFACE)
    with open(os.path.join(OUT, f"confusion_{args.pool}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"輸出 {png}")


if __name__ == "__main__":
    main()
