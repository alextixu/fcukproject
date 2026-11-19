"""特徵組比較:shape29(目前)vs 原系統 2 日 K 的 features_2day(2day10)與拿掉 trend 的 2day9(2026-11-19 使用者要求)。

其餘全部不變:標籤 11 天收盤最高 / 最低(t = 第 6 天)、訓練門檻 0%;TW200 剔除低波動股 168 檔;walk-forward 測 2024–2026
(Stacking 第一層前 3 年、第二層第 4 年,邊界留 5 天);前處理 缺值補中位數 → StandardScaler → 截 ±5;種子 42;
neighbor_purity 距離門檻 3.0、OC-SVM nu 0.1。AE 潛在維度依特徵組:shape29 16、2day 4(原系統 2 日 K 的設定;shallow 一層線性)。
另記錄 neighbor_purity 每個樣本的相似樣本數(距離 ≤ 3.0 的其他候選數)中位數。
shape29 的結果應和 results/confusion_2024_2026_tw200_amp0.json 完全相同(腳本內核對)。
用法: python method_kline_peak/feat2day_compare.py
輸出: results/feat2day_compare_tw200.json
      results/confusion_2024_2026_tw200_<2day10|2day9>_<main|stack>.png(混淆矩陣)
      results/feat2day_8046_2024_tw200_stack.png(南電 2024:真實標籤 / 29 維 / 2day10 / 2day9 的 Stacking)
"""
import json
import os
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "report"))
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import backtest_years as BY  # noqa: E402
import ae_ocsvm  # noqa: E402
import confusion_compare as CC  # noqa: E402
import compare_postproc as CP  # noqa: E402
from confusion import summarize  # noqa: E402
from export_windows import ticker_names  # noqa: E402
from feasibility import clean  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402
from paper_aeocsvm import NAMES  # noqa: E402

POOL, YEARS, FEATS = "tw200", (2024, 2025, 2026), ("shape29", "2day10", "2day9")
METHODS = {"主軸": "main", "Stacking 邏輯迴歸": "stack"}
TK = "8046.TW"
KEY = "confusion_rows_true_cols_pred(漲,不漲不跌,跌)"


def metrics(y, pred):
    s = summarize(y, pred, NAMES)
    cm = np.array(s[KEY])
    n = len(y)
    return {"macro_f1": round(s["macro_f1"] * 100, 2),
            "recall": {k: round(s["recall"][k] * 100, 1) for k in ("低點", "高點")},
            "precision": {k: round((s["precision"][k] or 0) * 100, 1) for k in ("低點", "高點")},
            "random_baseline": {"低點": round(float((y == UP).mean()) * 100, 2), "高點": round(float((y == DOWN).mean()) * 100, 2)},
            "high_low_swapped": int(cm[0, 2] + cm[2, 0]), "n_days": n, KEY: cm.tolist()}


def main():
    t0 = time.time()
    data = ML.load_data(pool=POOL)
    orig_np = ae_ocsvm.neighbor_purity
    nb_log = []

    def logged(X, y, cls):                                         # 只記錄相似樣本數,不改結果
        out = orig_np(X, y, cls)
        nb_log.append({"dim": int(X.shape[1]), "n_samples": len(out[0]), "median": float(np.median(ae_ocsvm.LAST_COUNTS)),
                       "class": NAMES[cls]})
        return out
    ae_ocsvm.neighbor_purity = logged

    res = {"pool": POOL, "n_stocks": len(data), "train_min_amp": 0, "seed": 42, "dist": ae_ocsvm.DIST_THRESH,
           "latent": dict(ML.LATENT_BY_FEATURES), "results": {}, "neighbor_count_median": {}}
    stock = {}
    for f in FEATS:
        ML.FEATURES = f
        panel, fc = ML.build_panel(data, 6, [], features=f)
        res["results"][f] = {"n_features": len(fc), "features": fc}
        for y in YEARS:
            for name in METHODS:
                nb_log.clear()
                sig, _ = WF.run_year(panel, fc, y, BY.SOURCE_FACTORIES[name]())
                res["results"][f].setdefault(str(y), {})[name] = metrics(sig["y"].to_numpy(), sig["pred"].to_numpy())
                res["neighbor_count_median"].setdefault(f, {}).setdefault(str(y), {})[name] = [dict(e) for e in nb_log]
                if y == 2024 and name == "Stacking 邏輯迴歸":
                    stock[f] = sig[sig.ticker == TK].sort_values("date").reset_index(drop=True)
                r = res["results"][f][str(y)][name]
                print(f"{f} {y} {name:<10} macro-F1 {r['macro_f1']:.2f}  找到 低/高 {r['recall']['低點']}/{r['recall']['高點']}"
                      f"  命中 低/高 {r['precision']['低點']}/{r['precision']['高點']}  判反 {r['high_low_swapped']}"
                      f"  相似樣本數中位 {[e['median'] for e in nb_log]}  ({time.time() - t0:.0f}s)", flush=True)
    ML.FEATURES = "shape29"
    ae_ocsvm.neighbor_purity = orig_np

    # 核對:shape29 = 既有 confusion_2024_2026_tw200_amp0.json
    ref = json.load(open(os.path.join(ML.OUT, "confusion_2024_2026_tw200_amp0.json"), encoding="utf-8"))
    tmap = {"主軸": "① 主軸", "Stacking 邏輯迴歸": "② Stacking 邏輯迴歸"}
    res["check_shape29_vs_amp0"] = all(
        res["results"]["shape29"][str(y)][m][KEY] == ref[str(y)][tmap[m]][KEY]
        and res["results"]["shape29"][str(y)][m]["macro_f1"] == round(ref[str(y)][tmap[m]]["macro_f1"] * 100, 2)
        for y in YEARS for m in METHODS)
    print("shape29 和 confusion_2024_2026_tw200_amp0.json 相同:", res["check_shape29_vs_amp0"])

    # 南電 2024 判低 / 判高對錯
    res["8046_2024_stack"] = {f: CP.counts(s["y"].to_numpy(), s["pred"].to_numpy()) for f, s in stock.items()}
    with open(os.path.join(ML.OUT, f"feat2day_compare_{POOL}.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, default=float)

    # 混淆矩陣圖(2day10、2day9 × 主軸、Stacking;列 = 年)
    for f in FEATS[1:]:
        for name, tag in METHODS.items():
            fig, axes = plt.subplots(len(YEARS), 1, figsize=(6.4, 16), dpi=150, squeeze=False)
            for r, y in enumerate(YEARS):
                a0, a1 = y - 4, y - 1
                sub = f"(訓練 {a0}–{a1})" if name == "主軸" else f"(A {a0}–{a1 - 1}、B {a1})"
                CC.panel(axes[r, 0], f"測試 {y}" + ("(1–9 月)" if y == 2026 else "") + f" · {name}{sub}",
                         res["results"][f][str(y)][name][KEY])
            fig.suptitle(f"2024–2026 混淆矩陣({POOL.upper()} 剔除低波動股後 {len(data)} 檔,種子 42)\n"
                         f"特徵 {f}({res['results'][f]['n_features']} 維,AE 潛在 {ML.LATENT_BY_FEATURES[f]} 維);"
                         f"訓練門檻 0%;對答案用原本的標籤;顏色 = 每列比例", fontsize=12, color=CC.INK, x=0.02, ha="left", y=0.997,
                         linespacing=1.4)
            fig.text(0.02, 0.003, "列 = 真實標籤、欄 = 判斷;橘框 = 高低點判反。", fontsize=10, color=CC.MUTED)
            fig.tight_layout(rect=(0, 0.012, 1, 0.95), h_pad=3.0)
            fig.savefig(os.path.join(ML.OUT, f"confusion_2024_2026_{POOL}_{f}_{tag}.png"), facecolor="white")
            plt.close(fig)

    # 南電 2024 對照圖(Stacking;不畫回測持有期間)
    s0 = stock["shape29"]
    dates, yv = s0["date"].to_numpy(), s0["y"].to_numpy()
    cl = clean(data[TK])["close"].loc[s0["date"]].to_numpy()
    pad = (cl.max() - cl.min()) * 0.04
    nm = ticker_names().get(TK, TK)
    fig, axes = plt.subplots(4, 1, figsize=(18, 13.5), dpi=150, sharex=True, facecolor="white", gridspec_kw={"hspace": 0.4})
    fig.subplots_adjust(left=0.05, right=0.99, top=0.92, bottom=0.06)
    for ax in axes:
        ax.plot(dates, cl, color="#9a9994", lw=1.1, zorder=1)
        CP.style(ax)
        ax.set_ylim(cl.min() - pad * 3, cl.max() + pad * 3)
    for cls, mk, col, off, lab in ((DOWN, "v", CP.HI, pad, "真高點"), (UP, "^", CP.LO, -pad, "真低點")):
        m = yv == cls
        axes[0].scatter(dates[m], cl[m] + off, marker=mk, s=40, color=col, zorder=3, label=f"{lab} {int(m.sum())} 個")
    axes[0].set_title(f"{TK[:4]} {nm} 2024:收盤與真實標籤(11 天收盤最高 / 最低)", loc="left", fontsize=12, color=CP.INK, fontweight="bold")
    axes[0].legend(frameon=True, facecolor="white", edgecolor=CP.GRID, fontsize=9.5, labelcolor=CP.INK, loc="lower left", ncol=2)
    for ax, f in zip(axes[1:], FEATS):
        s = stock[f]
        assert (s["date"].to_numpy() == dates).all()
        p = s["pred"].to_numpy()
        for cls, mk, col, off in ((DOWN, "v", CP.HI, pad), (UP, "^", CP.LO, -pad)):
            on = p == cls
            hit, miss = on & (yv == cls), on & (yv != cls)
            ax.scatter(dates[hit], cl[hit] + off, marker=mk, s=44, color=col, zorder=3)
            ax.scatter(dates[miss], cl[miss] + off, marker=mk, s=44, facecolors="white", edgecolors=col, lw=1.2, zorder=3)
        c = res["8046_2024_stack"][f]
        L, H = c["低點"], c["高點"]
        ax.set_title(f"Stacking 邏輯迴歸 · {f}({res['results'][f]['n_features']} 維):判低點 {L['判']} 天(對 {L['對']} / 錯 {L['錯']})、"
                     f"判高點 {H['判']} 天(對 {H['對']} / 錯 {H['錯']})", loc="left", fontsize=11, color=CP.INK, fontweight="bold")
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m 月"))
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator())
    fig.suptitle(f"{TK[:4]} {nm} 2024:特徵組比較 — Stacking 邏輯迴歸(168 檔、訓練門檻 0%、種子 42)",
                 x=0.01, ha="left", fontsize=15, color=CP.INK, y=0.985)
    fig.text(0.01, 0.012, "▼ 判高點、▲ 判低點,標在判斷日 t:實心 = 和真實標籤相同、空心 = 判錯。", fontsize=10, color=CP.MUTED)
    fig.savefig(os.path.join(ML.OUT, f"feat2day_8046_2024_{POOL}_stack.png"), facecolor="white", bbox_inches="tight")
    print(f"完成 ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
