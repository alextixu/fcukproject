"""論文的規則基準框架 + 我們的 AE + OC-SVM(TW50)。

論文(郭念慈、李俊宏)2.1 節指出:若 t 日收盤是 t±5 的最高,它必然也是 t−5 ~ t 的最高,而這在 t 日就知道。
所以「t 日為六日最高 → 高點候選、最低 → 低點候選」的規則已涵蓋所有真正的高低點(召回率 100%),
模型真正要做的只有一件事:排除其後五日內被超越的假候選。
本程式照這個框架:非候選一律判非極值;候選點交給 AE + OC-SVM,判在範圍內才保留,否則改判非極值。

與 paper_aeocsvm.py 的「規則候選 + AE + OC-SVM」不同:AE 與 OC-SVM 只用「訓練期的候選點」訓練,
  AE 學真高(低)點候選的形態;OC-SVM 權重 = 距離 ≤ 3 的相似候選點中,同為真高(低)點的比例(原系統重要性的替代)
標籤 / 輸入 / 切分:同 paper_aeocsvm.py(論文標籤、t−5 ~ t 六根 K、論文切分與我們的切分)
OC-SVM nu:原系統 0.1,另掃 0.2 / 0.3 / 0.5(nu 越大越嚴格、否決越多候選)
對照:隨機否決同樣數量的候選點(20 次平均)。模型若真能分辨真假候選,保留下來的命中率應高於隨機否決

用法: python method_kline_peak/paper_rule_aeocsvm.py
輸出: method_kline_peak/results/paper_rule_aeocsvm_tw50.json、.png
"""
import json
import os
import sys
import time

import numpy as np
import torch
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from feasibility import START, END, SHAPE, load_pool  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402
from confusion import SURFACE, INK, plt, draw, summarize  # noqa: E402
from paper_aeocsvm import NAMES, SEEDS, SPLITS, build_panel, split, rule_pred, mean_metrics  # noqa: E402
from ae_ocsvm import neighbor_purity, train_ae  # noqa: E402

OUT = os.path.join(HERE, "results")
POOL = "tw50"
NUS = (0.1, 0.2, 0.3, 0.5)
NU_MAIN = 0.1
N_RANDOM = 20
CAND = {DOWN: "cand_hi", UP: "cand_lo"}


def fit_candidates(Xc, yc, cls):
    seeds, w = neighbor_purity(Xc, yc, cls)                 # 只在候選點之間找相似樣本
    ae = train_ae(Xc[seeds], Xc.shape[1], lambda s: None)
    ae.eval()
    with torch.no_grad():
        z = ae.encode(torch.FloatTensor(Xc[seeds])).numpy()
    w = np.maximum(w, 1e-3)
    ocs = {nu: OneClassSVM(kernel="rbf", nu=nu, gamma="scale").fit(z, sample_weight=w / w.mean()) for nu in NUS}
    return ae, ocs, float(np.median(w))


def main():
    t0 = time.time()
    plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
    panel = build_panel(load_pool(POOL, START, END))
    rng = np.random.default_rng(0)
    out, cells = {}, []
    for sp_name, sp in SPLITS.items():
        d = split(panel, sp)
        tr, te = d["train"], d["test"]
        yte = te["y"].to_numpy()
        rule = summarize(yte, rule_pred(te), NAMES)
        print(f"\n== {sp_name}:訓練 {sp['train'][0]} ~ {sp['train'][1]} / 測試 {sp['test'][0]} ~ {sp['test'][1]}", flush=True)
        for cls in (DOWN, UP):
            c_tr, c_te = tr[CAND[cls]].to_numpy(), te[CAND[cls]].to_numpy()
            print(f"   {NAMES[cls]}候選:訓練 {c_tr.sum():,} 個(真 {(tr['y'].to_numpy()[c_tr] == cls).mean():.1%})/"
                  f" 測試 {c_te.sum():,} 個(真 {(yte[c_te] == cls).mean():.1%})")

        runs = {nu: [] for nu in NUS}
        rand = {nu: [] for nu in NUS}
        keep = {nu: {cls: {"真": [], "假": []} for cls in (DOWN, UP)} for nu in NUS}
        for seed in SEEDS:
            torch.manual_seed(seed)
            np.random.seed(seed)
            preds = {nu: np.full(len(te), FLAT) for nu in NUS}
            for cls in (DOWN, UP):
                c_tr, c_te = tr[CAND[cls]].to_numpy(), te[CAND[cls]].to_numpy()
                sc = StandardScaler().fit(tr.loc[c_tr, SHAPE])
                Xc = np.clip(sc.transform(tr.loc[c_tr, SHAPE]), -5, 5).astype(np.float32)
                Xt = np.clip(sc.transform(te.loc[c_te, SHAPE]), -5, 5).astype(np.float32)
                ae, ocs, med_w = fit_candidates(Xc, tr["y"].to_numpy()[c_tr], cls)
                with torch.no_grad():
                    zt = ae.encode(torch.FloatTensor(Xt)).numpy()
                true_c = yte[c_te] == cls
                for nu, oc in ocs.items():
                    inside = oc.predict(zt) == 1
                    idx = np.flatnonzero(c_te)
                    preds[nu][idx[inside]] = cls
                    keep[nu][cls]["真"].append(float(inside[true_c].mean()))
                    keep[nu][cls]["假"].append(float(inside[~true_c].mean()))
            for nu in NUS:
                runs[nu].append(summarize(yte, preds[nu], NAMES))
                # 隨機否決:每類保留與模型相同數量的候選點
                f1s = []
                for _ in range(N_RANDOM):
                    rp = np.full(len(te), FLAT)
                    for cls in (DOWN, UP):
                        idx = np.flatnonzero(te[CAND[cls]].to_numpy())
                        k = int((preds[nu][idx] == cls).sum())
                        rp[rng.choice(idx, size=k, replace=False)] = cls
                    f1s.append(summarize(yte, rp, NAMES))
                rand[nu].append(mean_metrics(f1s))

        res = {"rule": rule, "by_nu": {}}
        for nu in NUS:
            res["by_nu"][str(nu)] = {
                "model": mean_metrics(runs[nu]), "random_veto": mean_metrics(rand[nu]),
                "keep_rate": {NAMES[cls]: {k: float(np.mean(v)) for k, v in keep[nu][cls].items()} for cls in (DOWN, UP)},
            }
        res["seed42_nu0.1"] = runs[NU_MAIN][0]
        out[sp_name] = res
        cells.append((sp_name, sp, res))

        r = rule
        print(f"   規則基準                      acc {r['acc']:.1%}  macro-F1 {r['macro_f1']:.2%}  BalAcc {r['bal_acc']:.2%}  "
              f"精確率 高 {r['precision']['高點']:.1%} / 低 {r['precision']['低點']:.1%}")
        for nu in NUS:
            b = res["by_nu"][str(nu)]
            m, rv, kp = b["model"], b["random_veto"], b["keep_rate"]
            print(f"   規則 + AE + OC-SVM nu={nu:<4}  acc {m['acc']:.1%}  macro-F1 {m['macro_f1']:.2%}"
                  f"(隨機否決 {rv['macro_f1']:.2%})  BalAcc {m['bal_acc']:.2%}  "
                  f"精確率 高 {m['precision']['高點']:.1%}(隨機 {rv['precision']['高點']:.1%})/ "
                  f"低 {m['precision']['低點']:.1%}(隨機 {rv['precision']['低點']:.1%})  "
                  f"保留率 高 真 {kp['高點']['真']:.0%} 假 {kp['高點']['假']:.0%} / 低 真 {kp['低點']['真']:.0%} 假 {kp['低點']['假']:.0%}",
                  flush=True)
        print(f"   ({time.time() - t0:.0f}s)", flush=True)

    fig, axes = plt.subplots(len(cells), 2, figsize=(11.6, 6.3 * len(cells)), facecolor=SURFACE)
    for i, (sp_name, sp, res) in enumerate(cells):
        head = f"{sp_name}:訓練 {sp['train'][0][:7]} ~ {sp['train'][1][:7]} · 測試 {sp['test'][0][:7]} ~ {sp['test'][1][:7]}"
        draw(axes[i, 0], res["rule"], f"{head}\n規則基準(論文)", NAMES)
        draw(axes[i, 1], res["seed42_nu0.1"], f"{head}\n規則 + AE + OC-SVM(只用候選點訓練,nu 0.1,種子 42)", NAMES)
    fig.suptitle("TW50:論文規則基準框架 + AE + OC-SVM 否決假候選", fontsize=14, color=INK, x=0.01, ha="left")
    fig.subplots_adjust(left=0.1, right=0.99, top=0.9, bottom=0.08, wspace=0.45, hspace=0.62)
    png = os.path.join(OUT, f"paper_rule_aeocsvm_{POOL}.png")
    fig.savefig(png, dpi=110, facecolor=SURFACE)
    with open(os.path.join(OUT, f"paper_rule_aeocsvm_{POOL}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n輸出 {png}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
