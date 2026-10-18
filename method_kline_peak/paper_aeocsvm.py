"""論文標籤(郭念慈、李俊宏,逢甲資工)+ 原系統 AE + OC-SVM,TW50。

標籤(論文 2.1 節,照抄):
  C_t 為第 t 日收盤價,W_t = {C_t-5, …, C_t+5}
  C_t = max W_t → 高點;C_t = min W_t → 低點;其餘 → 非極值
  與他日並列最高(最低)者亦標為高點(低點);視窗內收盤價全部相同 → 非極值
  頭尾不足 11 天不納入;輸入只用到 t 日收盤,預測於 t 日盤後產生
  (還原價比大小加相對容差 1e-5,避免還原因子的浮點誤差把同價拆開)
輸入:t-5 ~ t 共六根 K 的形態(feasibility.SHAPE:O/H/L/C 相對 t 日收盤的 log 價 + 量相對 20 日均量,29 維)
模型:ae_ocsvm.fit_direction(method_kline 的 AE 潛在 4 維、60 輪 + OC-SVM nu 0.1),高點、低點各一組;
      AE 亂數種子 42 / 43 / 44,指標取三種子平均(同論文)
判法
  規則基準  論文的規則:t 日收盤為 t-5 ~ t 最高 → 高點、最低 → 低點,其餘(含兩者同時)→ 非極值
  AE+OC-SVM 原生:低點的 OC-SVM 判在範圍內 → 低點;否則高點的判在範圍內 → 高點;其餘非極值(低點 = 看漲方向優先)
  規則候選 + AE+OC-SVM:只有規則認定的候選點才交給 OC-SVM;判在範圍內才保留,其餘改判非極值
切分
  論文  訓練 2024-05-14 ~ 2025-08-18 / 驗證 2025-08-26 ~ 2025-10-21 / 測試 2025-10-30 ~ 2026-03-25
  我們  訓練 2020–2023 / 驗證 2024 / 測試 2025-01 ~ 2026-09
  (AE + OC-SVM 不需要驗證段;交界前 5 個交易日的樣本剔除,因為標籤看到 t+5)

用法: python method_kline_peak/paper_aeocsvm.py
輸出: method_kline_peak/results/paper_aeocsvm_tw50.json、.png
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from feasibility import START, END, SHAPE, load_pool, clean  # noqa: E402
from peak_labels import HALF, TOL, causal_features, side_extreme  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402
from confusion import ORDER, SURFACE, INK, plt, draw, summarize  # noqa: E402
from ae_ocsvm import fit_direction, predict  # noqa: E402

OUT = os.path.join(HERE, "results")
POOL = "tw50"
SEEDS = (42, 43, 44)
NAMES = {UP: "低點", FLAT: "非極值", DOWN: "高點"}        # 低點 = 漲、高點 = 跌
SPLITS = {
    "論文切分": {"train": ("2024-05-14", "2025-08-18"), "test": ("2025-10-30", "2026-03-25")},
    "我們的切分": {"train": ("2020-01-01", "2023-12-31"), "test": ("2025-01-01", END)},
}
METHODS = {"rule": "規則基準(論文)", "native": "AE + OC-SVM(原系統判法)", "rule_oc": "規則候選 + AE + OC-SVM"}


def paper_label(C):
    lmax, rmax = side_extreme(C, HALF, False, "max"), side_extreme(C, HALF, True, "max")
    lmin, rmin = side_extreme(C, HALF, False, "min"), side_extreme(C, HALF, True, "min")
    hi = (C >= lmax * (1 - TOL)) & (C >= rmax * (1 - TOL))          # 並列最高也算
    lo = (C <= lmin * (1 + TOL)) & (C <= rmin * (1 + TOL))
    y = pd.Series(FLAT, index=C.index)
    y[hi & ~lo] = DOWN
    y[lo & ~hi] = UP                                                  # hi & lo = 視窗全部同價 → 非極值
    cand_hi = (C >= lmax * (1 - TOL)) & ~(C <= lmin * (1 + TOL))      # 規則:t 日為 t-5 ~ t 最高(且非同時最低)
    cand_lo = (C <= lmin * (1 + TOL)) & ~(C >= lmax * (1 - TOL))
    return y.where(lmax.notna() & rmax.notna()), cand_hi, cand_lo


def build_panel(data):
    parts = []
    for tk, df in data.items():
        df = clean(df)
        y, cand_hi, cand_lo = paper_label(df["close"])
        part = causal_features(df)[SHAPE].copy()
        part["y"], part["cand_hi"], part["cand_lo"] = y, cand_hi, cand_lo
        part["ticker"] = tk
        part.index.name = "date"
        parts.append(part.reset_index())
    panel = pd.concat(parts, ignore_index=True)
    panel = panel[panel["y"].notna() & panel[SHAPE].notna().all(axis=1) & (panel["date"] >= START)]
    panel["y"] = panel["y"].astype(int)
    return panel.reset_index(drop=True)


def split(panel, sp):
    cal = np.sort(panel["date"].unique())
    i = np.searchsorted(cal, np.datetime64(sp["test"][0]))
    purge = cal[max(0, i - HALF):i]                                   # t+5 會跨進測試段的樣本
    keep = ~panel["date"].isin(purge)
    return {k: panel[keep & panel["date"].between(a, b)].reset_index(drop=True) for k, (a, b) in sp.items()}


def rule_pred(te):
    pred = np.full(len(te), FLAT)
    pred[te["cand_hi"].to_numpy()] = DOWN
    pred[te["cand_lo"].to_numpy()] = UP
    return pred


def mean_metrics(runs):
    keys = ("acc", "macro_f1", "bal_acc")
    out = {k: float(np.mean([r[k] for r in runs])) for k in keys}
    out |= {f"sd_{k}": float(np.std([r[k] for r in runs])) for k in keys}
    for part in ("precision", "f1"):
        out[part] = {n: float(np.mean([r[part][n] or 0 for r in runs])) for n in NAMES.values()}
    return out


def main():
    t0 = time.time()
    plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
    panel = build_panel(load_pool(POOL, START, END))
    out, cells = {}, []
    for sp_name, sp in SPLITS.items():
        d = split(panel, sp)
        tr, te = d["train"], d["test"]
        dist = {k: {NAMES[c]: float((v["y"] == c).mean()) for c in ORDER} | {"n": len(v)} for k, v in d.items()}
        print(f"\n== {sp_name}:訓練 {sp['train'][0]} ~ {sp['train'][1]}({len(tr):,})/ 測試 {sp['test'][0]} ~ "
              f"{sp['test'][1]}({len(te):,})", flush=True)
        for k, v in dist.items():
            print(f"   {k:<5} 低點 / 非極值 / 高點 = {v['低點']:.1%} / {v['非極值']:.1%} / {v['高點']:.1%}")
        sc = StandardScaler().fit(tr[SHAPE])
        Xtr = np.clip(sc.transform(tr[SHAPE]), -5, 5).astype(np.float32)
        Xte = np.clip(sc.transform(te[SHAPE]), -5, 5).astype(np.float32)
        ytr, yte = tr["y"].to_numpy(), te["y"].to_numpy()

        res = {"label_dist": dist, "rule": summarize(yte, rule_pred(te), NAMES), "native": [], "rule_oc": []}
        cand = {UP: te["cand_lo"].to_numpy(), DOWN: te["cand_hi"].to_numpy()}
        for seed in SEEDS:
            torch.manual_seed(seed)
            np.random.seed(seed)
            models = {cls: fit_direction(Xtr, ytr, cls, lambda s: None) for cls in (UP, DOWN)}
            native, _, inside = predict(models, Xte)
            hyb = np.full(len(te), FLAT)
            hyb[cand[DOWN] & inside[DOWN]] = DOWN
            hyb[cand[UP] & inside[UP]] = UP
            res["native"].append(summarize(yte, native, NAMES))
            res["rule_oc"].append(summarize(yte, hyb, NAMES))
        res["native_mean"], res["rule_oc_mean"] = mean_metrics(res["native"]), mean_metrics(res["rule_oc"])
        out[sp_name] = res
        cells.append((sp_name, sp, res))
        for m, label in METHODS.items():
            r = res[m] if m == "rule" else res[f"{m}_mean"]
            print(f"   {label:<22} acc {r['acc']:.1%}  macro-F1 {r['macro_f1']:.2%}  BalAcc {r['bal_acc']:.2%}  "
                  f"精確率 高 {r['precision']['高點'] or 0:.1%} / 低 {r['precision']['低點'] or 0:.1%}  "
                  f"F1 高 {r['f1']['高點']:.1%} / 低 {r['f1']['低點']:.1%}", flush=True)
        print(f"   ({time.time() - t0:.0f}s)", flush=True)

    fig, axes = plt.subplots(len(cells), len(METHODS), figsize=(5.6 * len(METHODS), 6.3 * len(cells)),
                             facecolor=SURFACE)
    for i, (sp_name, sp, res) in enumerate(cells):
        head = f"{sp_name}:訓練 {sp['train'][0][:7]} ~ {sp['train'][1][:7]} · 測試 {sp['test'][0][:7]} ~ {sp['test'][1][:7]}"
        for j, (m, label) in enumerate(METHODS.items()):
            s = res[m] if m == "rule" else res[m][0]
            draw(axes[i, j], s, f"{head}\n{label}" + ("" if m == "rule" else "(種子 42)"), NAMES)
    fig.suptitle("TW50:論文標籤(t 日收盤是否為 t±5 日最高 / 最低)· 輸入 t-5 ~ t 六根 K",
                 fontsize=14, color=INK, x=0.01, ha="left")
    fig.subplots_adjust(left=0.07, right=0.99, top=0.9, bottom=0.08, wspace=0.42, hspace=0.62)
    png = os.path.join(OUT, f"paper_aeocsvm_{POOL}.png")
    fig.savefig(png, dpi=110, facecolor=SURFACE)
    with open(os.path.join(OUT, f"paper_aeocsvm_{POOL}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n輸出 {png}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
