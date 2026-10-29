"""Stacking(Blending):拿掉規則,兩組 AE + OC-SVM 的輸出分數 → 在新資料上訓練第三個模型(元學習器)做三分類。

老師的建議:不用規則挑候選;高點、低點各一組 AE + OC-SVM 先訓練好,再用「兩模型都沒看過的新資料」訓練第三個模型。

切分(TW50,全域日曆,每段之間剔除 5 個交易日,因為標籤用到 t+5)
  A 基底模型   2020-01 ~ 2022-12:真高點 → 高點 AE + OC-SVM;真低點 → 低點 AE + OC-SVM
  B 元學習器   2023-01 ~ 2023-12:每天的兩個分數 + 11 日標籤 → 訓練第三個模型
  C 測試       2024-01 ~ 2024-12

基底模型與主軸相同(29 個特徵、量 ÷ 10 日均量、編碼器一層 29 → 16、OC-SVM rbf nu 0.1、相似度權重),
差別只在:沒有規則,所以標準化與相似度權重用 A 的「全部日子」,OC-SVM 對每一天都給分數。

元學習器的輸入
  score:兩個 OC-SVM 的 decision_function(連續分數,> 0 = 範圍內)
  score+recon:再加兩個 AE 的重建誤差
  score+pos:分數 + 論文式位置特徵(t 收盤距近 6 日最高 / 最低,由 c1..c5 算出)。
            這等於把規則的資訊當特徵放回去,用來看「拿掉規則」少了什麼
元學習器(類別權重 = 訓練頻率倒數的平方根,同論文)
  lr   多類別邏輯迴歸(主方法)
  tree 決策樹(深度 3)
  hgb  梯度提升樹
  svm  多類別 SVM(rbf)

對照:規則基準、主軸(規則 + AE + OC-SVM,訓練 2020–2023)、隨機。
用法: python method_kline_peak/stacking.py [--seeds 42 43 44]
輸出: results/stacking_2024.json,並在 results/experiments.csv 追加 mode = stack 的列
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import torch
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM, SVC
from sklearn.tree import DecisionTreeClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mainline as ML  # noqa: E402
import ae_ocsvm  # noqa: E402
from feasibility import START, END, load_pool  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402
from paper_aeocsvm import NAMES, rule_pred  # noqa: E402
from confusion import summarize  # noqa: E402

OUT = os.path.join(ML.OUT, "stacking_2024.json")
PERIODS = {"A": ("2020-01-01", "2022-12-31"), "B": ("2023-01-01", "2023-12-31"), "C": ("2024-01-01", "2024-12-31")}
HALF, NU = 5, 0.1
INPUTS = ("score", "score+recon", "score+pos")
LEARNERS = ("lr", "tree", "hgb", "svm")


def split3(panel):
    """A / B / C 三段;每段最後 5 個交易日剔除(它們的標籤會用到下一段的價格)。"""
    cal = np.sort(panel["date"].unique())
    out = {}
    for k, (a, b) in PERIODS.items():
        d = panel[panel["date"].between(a, b)]
        nxt = {"A": "B", "B": "C"}.get(k)
        if nxt:
            i = np.searchsorted(cal, np.datetime64(PERIODS[nxt][0]))
            d = d[~d["date"].isin(cal[i - HALF:i])]
        out[k] = d.reset_index(drop=True)
    return out


def fit_base(Xa, ya, cls):
    """一組 AE + OC-SVM:只用 A 期的真高(低)點訓練,權重 = 相似日子中同為真高(低)點的比例。"""
    seeds, w = ae_ocsvm.neighbor_purity(Xa, ya, cls)
    ae = ML.KA.train_ae(Xa[seeds], Xa.shape[1], lambda s: None)
    ae.eval()
    with torch.no_grad():
        z = ae.encode(torch.FloatTensor(Xa[seeds])).numpy()
    w = np.maximum(w, 1e-3)
    oc = OneClassSVM(kernel="rbf", nu=NU, gamma="scale").fit(z, sample_weight=w / w.mean())
    return ae, oc


def base_outputs(ae, oc, X):
    with torch.no_grad():
        t = torch.FloatTensor(X)
        recon, z = ae(t)
        err = ((recon - t) ** 2).mean(dim=1).numpy()
    return oc.decision_function(z.numpy()), err


def position(df):
    """t 收盤距近 6 日最高(≤ 0)與最低(≥ 0);等於 0 就是規則的高點 / 低點候選。"""
    cm = df[[f"c{k}" for k in range(1, 6)]].to_numpy()
    return np.column_stack([-np.maximum(0, cm.max(1)), -np.minimum(0, cm.min(1))])


def class_weight(y):
    freq = {c: (y == c).mean() for c in (UP, FLAT, DOWN)}
    w = {c: 1 / np.sqrt(f) for c, f in freq.items()}
    m = np.mean(list(w.values()))
    return {c: v / m for c, v in w.items()}


def make_learner(name, cw):
    if name == "lr":
        return LogisticRegression(class_weight=cw, max_iter=2000)
    if name == "tree":
        return DecisionTreeClassifier(max_depth=3, class_weight=cw, random_state=0)
    if name == "hgb":
        return HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05, class_weight=cw, random_state=0)
    return SVC(kernel="rbf", C=1.0, gamma="scale", class_weight=cw)


def extra(y, pred, te):
    cm = np.array(summarize(y, pred, NAMES)["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"])
    hi, lo = pred == DOWN, pred == UP
    return {"cross_errors": int(cm[0, 2] + cm[2, 0]),
            "pred_high_in_rule_cand": float(te["cand_hi"].to_numpy()[hi].mean()) if hi.any() else None,
            "pred_low_in_rule_cand": float(te["cand_lo"].to_numpy()[lo].mean()) if lo.any() else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    args = ap.parse_args()
    t0 = time.time()
    ML.setup_ae()
    panel, fc = ML.build_panel(load_pool(ML.POOL, START, END), 6, [])
    d = split3(panel)
    A, B, C = d["A"], d["B"], d["C"]
    print(f"A {len(A):,}(真高 {(A.y == DOWN).sum():,}、真低 {(A.y == UP).sum():,})/ B {len(B):,} / C {len(C):,}  ({time.time() - t0:.0f}s)", flush=True)

    med = A[fc].median()
    sc = StandardScaler().fit(A[fc].fillna(med))
    prep = lambda df: np.clip(sc.transform(df[fc].fillna(med)), -5, 5).astype(np.float32)
    Xa, Xb, Xc = prep(A), prep(B), prep(C)
    ya, yb, yc = A.y.to_numpy(), B.y.to_numpy(), C.y.to_numpy()
    cw = class_weight(yb)

    res = {"periods": PERIODS, "n": {"A": len(A), "B": len(B), "C": len(C)},
           "rule": {**summarize(yc, rule_pred(C), NAMES), **extra(yc, rule_pred(C), C)}, "runs": {}}
    rng = np.random.default_rng(0)
    rand = rng.choice([UP, FLAT, DOWN], size=len(yc), p=[(yb == c).mean() for c in (UP, FLAT, DOWN)])
    res["prior_random"] = summarize(yc, rand, NAMES)
    for seed in args.seeds:
        torch.manual_seed(seed)
        np.random.seed(seed)
        feats = {}
        for cls, tag in ((DOWN, "high"), (UP, "low")):
            ae, oc = fit_base(Xa, ya, cls)
            for part, X in (("B", Xb), ("C", Xc)):
                s, e = base_outputs(ae, oc, X)
                feats[(part, f"s_{tag}")], feats[(part, f"e_{tag}")] = s, e
            s, cand = feats[("C", f"s_{tag}")], C[ML.CAND[cls]].to_numpy()
            res.setdefault("score_auc", {}).setdefault(tag, {})[seed] = {      # 測試期分數的分辨力
                "true_vs_rest": float(roc_auc_score(yc == cls, s)),
                "cand_vs_ordinary": float(roc_auc_score(cand, s)),
                "true_vs_false_within_cand": float(roc_auc_score(yc[cand] == cls, s[cand])),
                "inside_rate_cand": float((s[cand] > 0).mean()), "inside_rate_ordinary": float((s[~cand] > 0).mean())}
        for part, df in (("B", B), ("C", C)):
            feats[(part, "pos_hi")], feats[(part, "pos_lo")] = position(df).T
        for inp in INPUTS:
            cols = ["s_high", "s_low"] + {"score+recon": ["e_high", "e_low"], "score+pos": ["pos_hi", "pos_lo"]}.get(inp, [])
            Fb = np.column_stack([feats[("B", c)] for c in cols])
            Fc = np.column_stack([feats[("C", c)] for c in cols])
            fsc = StandardScaler().fit(Fb)
            for ln in LEARNERS:
                m = make_learner(ln, cw).fit(fsc.transform(Fb), yb)
                pred = m.predict(fsc.transform(Fc))
                r = {**summarize(yc, pred, NAMES), **extra(yc, pred, C)}
                if ln == "lr":
                    r["coef"] = {NAMES[c]: dict(zip(cols, np.round(w, 3).tolist())) for c, w in zip(m.classes_, m.coef_)}
                res["runs"].setdefault(f"{inp}|{ln}", {})[seed] = r
        print(f"  種子 {seed} 完成  ({time.time() - t0:.0f}s)", flush=True)

    rule = res["rule"]
    print(f"\n測試 2024({len(C):,} 天):規則 macro-F1 {rule['macro_f1']:.2%};先驗隨機 {res['prior_random']['macro_f1']:.2%}")
    print(f"{'輸入|元學習器':<20}{'macro-F1(3 種子)':>18}{'找到 高/低':>14}{'命中 高/低':>14}{'判非極值正確':>10}{'判反':>6}{'判高在規則候選內':>14}")
    summary = {}
    for key, runs in res["runs"].items():
        mf = [r["macro_f1"] for r in runs.values()]
        r0 = runs[args.seeds[0]]
        summary[key] = {"macro_f1_mean": float(np.mean(mf)), "macro_f1_sd": float(np.std(mf))}
        print(f"{key:<20}{np.mean(mf) * 100:>11.2f} ± {np.std(mf) * 100:.2f}"
              f"{r0['recall']['高點'] * 100:>8.1f}/{r0['recall']['低點'] * 100:.1f}%"
              f"{r0['precision']['高點'] * 100:>8.1f}/{(r0['precision']['低點'] or 0) * 100:.1f}%"
              f"{(r0['precision']['非極值'] or 0) * 100:>9.1f}%{r0['cross_errors']:>6}"
              f"{(r0['pred_high_in_rule_cand'] or 0) * 100:>12.1f}%")
        ML.write_log({"time": time.strftime("%Y-%m-%d %H:%M"), "tag": f"stack-{key}", "split": "測試 2024(A 2020–22 / B 2023)",
                      "mode": "stack", "window": 6, "vol_ma": ML.VOL_MA, "arch": ML.ARCH, "latent": ML.LATENT, "nu": NU,
                      "seeds": len(args.seeds), "rule_macro_f1": round(rule["macro_f1"] * 100, 2),
                      "model_macro_f1": round(np.mean(mf) * 100, 2), "model_sd": round(np.std(mf) * 100, 2),
                      "delta_vs_rule": round((np.mean(mf) - rule["macro_f1"]) * 100, 2),
                      "acc": round(r0["acc"] * 100, 2), "bal_acc": round(r0["bal_acc"] * 100, 2),
                      "prec_high": round((r0["precision"]["高點"] or 0) * 100, 2), "prec_low": round((r0["precision"]["低點"] or 0) * 100, 2)})
    res["summary"] = summary
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n記錄於 {OUT}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
