"""Stacking(Blending):拿掉規則,兩組 AE + OC-SVM 的輸出 → 在新資料上訓練第三個模型(元學習器)做三分類。

老師的建議:不用規則挑候選;高點、低點各一組 AE + OC-SVM 先訓練好,再用「兩模型都沒看過的新資料」訓練第三個模型。

結構(新增元學習器 = LEARNERS 多一行;新增輸入組合 = INPUTS 多一行)
  BaseScorers     基底層:高點、低點兩組 AE + OC-SVM(設定同主軸:29 個特徵、量 ÷ 10 日均量、29 → 16、
                  OC-SVM rbf nu 0.1、相似度權重)。沒有規則,所以標準化與相似度權重用 A 期的全部日子,
                  OC-SVM 只用真高(低)點訓練,對每一天都給分數
  MetaLearner     元學習器:一種輸入組合 + 一種分類器;類別權重 = 訓練頻率倒數的平方根(同論文)
  StackingSource  walkforward.SignalSource 的實作:訓練期最後 1 年給元學習器(B),其餘給基底層(A),
                  中間剔除 5 個交易日。可以直接放進逐年回測

測試 2024 的切分(= year_split(2024) 的訓練期再切一次)
  A 基底層     2020-01 ~ 2022-12(最後 5 個交易日剔除)
  B 元學習器   2023-01 ~ 2023-12(最後 5 個交易日剔除)
  C 測試       2024-01 ~ 2024-12

元學習器的輸入(INPUTS)
  score        兩個 OC-SVM 的 decision_function(> 0 = 範圍內)
  score+recon  再加兩個 AE 的重建誤差
  score+pos    再加位置特徵(t 收盤距近 6 日最高 / 最低),等於把規則的資訊當特徵放回去
元學習器(LEARNERS)
  lr        多類別邏輯迴歸,L2(sklearn 預設;主方法)
  lr-l1     多類別邏輯迴歸,L1(Lasso 式懲罰)
  lr-enet   多類別邏輯迴歸,Elastic Net(L1 : L2 = 1 : 1)
  lr-poly2  2 次多項式特徵(平方、交乘)+ 邏輯迴歸 L2
  lr-poly3  3 次多項式特徵 + 邏輯迴歸 L2
  tree      決策樹(深度 3)
  hgb       梯度提升樹
  svm       多類別 SVM(rbf)
線性回歸、Ridge / Lasso / Elastic Net 回歸、多項式回歸輸出連續數字,不是三分類,所以只取它們的正則化與多項式特徵,
放進多類別邏輯迴歸。

對照:規則基準、主軸(同一段訓練期,規則 + 兩個 OC-SVM)、先驗隨機。
用法: python method_kline_peak/stacking.py [--seeds 42 43 44] [--test-year 2024] [--train-years 4] [--meta-years 1]
      例:測試 2025、訓練 2020–2024、B = 2023–2024 → --test-year 2025 --train-years 5 --meta-years 2
輸出: results/stacking_2024.json(預設設定)或 results/stacking_<測試年>_A<起>-<迄>_B<起>-<迄>.json,
      並在 results/experiments.csv 追加 mode = stack 的列
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.svm import OneClassSVM, SVC
from sklearn.tree import DecisionTreeClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mainline as ML  # noqa: E402
import ae_ocsvm  # noqa: E402
import walkforward as WF  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402
from paper_aeocsvm import NAMES, rule_pred  # noqa: E402
from confusion import summarize  # noqa: E402

OUT = os.path.join(ML.OUT, "stacking_2024.json")
TEST_YEAR, HALF, NU, SEED = 2024, 5, 0.1, 42
DEFAULT = (TEST_YEAR, WF.TRAIN_YEARS, 1)          # 預設:測試 2024、訓練 4 年、B 1 年 → 寫回 stacking_2024.json
INPUTS = {
    "score": ["s_high", "s_low"],
    "score+recon": ["s_high", "s_low", "e_high", "e_low"],
    "score+pos": ["s_high", "s_low", "pos_hi", "pos_lo"],
}


def _lr(cw, **kw):
    return LogisticRegression(class_weight=cw, **kw)


def _poly(degree):
    return lambda cw: make_pipeline(PolynomialFeatures(degree, include_bias=False), StandardScaler(), _lr(cw, max_iter=5000))


LEARNERS = {
    "lr": lambda cw: _lr(cw, max_iter=2000),
    "lr-l1": lambda cw: _lr(cw, l1_ratio=1.0, solver="saga", max_iter=5000),
    "lr-enet": lambda cw: _lr(cw, l1_ratio=0.5, solver="saga", max_iter=5000),
    "lr-poly2": _poly(2),
    "lr-poly3": _poly(3),
    "tree": lambda cw: DecisionTreeClassifier(max_depth=3, class_weight=cw, random_state=0),
    "hgb": lambda cw: HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05, class_weight=cw, random_state=0),
    "svm": lambda cw: SVC(kernel="rbf", C=1.0, gamma="scale", class_weight=cw),
}


# ─────────────────────────── 切分 ───────────────────────────
def split_base_meta(train, meta_years=1, half=HALF):
    """訓練期最後 meta_years 年 → B(元學習器);之前 → A(基底層),A 最後 half 個交易日剔除(標籤會用到 B 的價格)。"""
    first_meta = train["date"].dt.year.max() - meta_years + 1
    start = pd.Timestamp(f"{first_meta}-01-01")
    cal = np.sort(train["date"].unique())
    i = np.searchsorted(cal, np.datetime64(start))
    A = train[(train["date"] < start) & ~train["date"].isin(cal[max(0, i - half):i])]
    B = train[train["date"] >= start]
    return A.reset_index(drop=True), B.reset_index(drop=True)


# ─────────────────────────── 基底層 ───────────────────────────
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


def position(df):
    """t 收盤距近 6 日最高(≤ 0)與最低(≥ 0);等於 0 就是規則的高點 / 低點候選。"""
    cm = df[[f"c{k}" for k in range(1, 6)]].to_numpy()
    return np.column_stack([-np.maximum(0, cm.max(1)), -np.minimum(0, cm.min(1))])


class BaseScorers:
    """高點、低點兩組 AE + OC-SVM;transform 對任何日子輸出分數、重建誤差與位置特徵。"""

    def __init__(self, seed=SEED):
        self.seed = seed

    def _prep(self, df):
        return np.clip(self.sc.transform(df[self.fc].fillna(self.med)), -5, 5).astype(np.float32)

    def fit(self, A, feat_cols):
        ML.setup_ae()
        self.fc, self.med = feat_cols, A[feat_cols].median()
        self.sc = StandardScaler().fit(A[feat_cols].fillna(self.med))
        Xa, ya = self._prep(A), A["y"].to_numpy()
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        self.models = {cls: fit_base(Xa, ya, cls) for cls in (DOWN, UP)}      # 先高後低
        return self

    def transform(self, df):
        X, out = torch.FloatTensor(self._prep(df)), {}
        for cls, tag in ((DOWN, "high"), (UP, "low")):
            ae, oc = self.models[cls]
            with torch.no_grad():
                recon, z = ae(X)
                out[f"e_{tag}"] = ((recon - X) ** 2).mean(dim=1).numpy()
            out[f"s_{tag}"] = oc.decision_function(z.numpy())
        out["pos_hi"], out["pos_lo"] = position(df).T
        return pd.DataFrame(out, index=df.index)


# ─────────────────────────── 元學習器 ───────────────────────────
def class_weight(y):
    freq = {c: (y == c).mean() for c in (UP, FLAT, DOWN)}
    w = {c: 1 / np.sqrt(f) for c, f in freq.items()}
    m = np.mean(list(w.values()))
    return {c: v / m for c, v in w.items()}


class MetaLearner:
    """一種輸入組合 + 一種分類器;predict 回傳 (三分類判斷, 把握程度:有機率的分類器為最大類的機率、其他為 0)。"""

    def __init__(self, learner="lr", inputs="score"):
        self.learner, self.inputs = learner, inputs

    def fit(self, F, y):
        X = F[INPUTS[self.inputs]].to_numpy()
        self.fsc = StandardScaler().fit(X)
        self.model = LEARNERS[self.learner](class_weight(y)).fit(self.fsc.transform(X), y)
        return self

    def predict(self, F):
        X = self.fsc.transform(F[INPUTS[self.inputs]].to_numpy())
        pred = self.model.predict(X)
        if hasattr(self.model, "predict_proba"):
            score = self.model.predict_proba(X).max(axis=1)
        else:
            score = np.zeros(len(X))
        return pred, score

    def coef(self):
        lr = self.model[-1] if hasattr(self.model, "steps") else self.model
        if not isinstance(lr, LogisticRegression) or hasattr(self.model, "steps"):
            return None
        return {NAMES[c]: dict(zip(INPUTS[self.inputs], np.round(w, 3).tolist())) for c, w in zip(lr.classes_, lr.coef_)}


# ─────────────────────────── 訊號來源 ───────────────────────────
class StackingSource(WF.SignalSource):
    """拿掉規則:基底層 + 元學習器。判斷不保證落在規則候選內(gated = False)。"""
    name = "Stacking"
    gated = False

    def __init__(self, learner="lr", inputs="score", seed=SEED, meta_years=1):
        self.learner, self.inputs, self.seed, self.meta_years = learner, inputs, seed, meta_years

    def fit(self, train, feat_cols):
        A, B = split_base_meta(train, self.meta_years)
        self.base = BaseScorers(self.seed).fit(A, feat_cols)
        self.meta = MetaLearner(self.learner, self.inputs).fit(self.base.transform(B), B["y"].to_numpy())

    def predict(self, test):
        pred, score = self.meta.predict(self.base.transform(test))
        return self._frame(test, pred, score)


# ─────────────────────────── 實驗:測試 2024,全部輸入 × 全部元學習器 ───────────────────────────
def extra(y, pred, te):
    cm = np.array(summarize(y, pred, NAMES)["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"])
    hi, lo = pred == DOWN, pred == UP
    return {"cross_errors": int(cm[0, 2] + cm[2, 0]),
            "pred_high_in_rule_cand": float(te["cand_hi"].to_numpy()[hi].mean()) if hi.any() else None,
            "pred_low_in_rule_cand": float(te["cand_lo"].to_numpy()[lo].mean()) if lo.any() else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--test-year", type=int, default=TEST_YEAR)
    ap.add_argument("--train-years", type=int, default=WF.TRAIN_YEARS)
    ap.add_argument("--meta-years", type=int, default=1)
    args = ap.parse_args()
    t0 = time.time()
    panel, fc = ML.build_panel(ML.load_data(), 6, [])
    d = WF.year_split(panel, args.test_year, args.train_years)
    A, B = split_base_meta(d["train"], args.meta_years)
    C = d["test"]
    yA, yB = (A.date.dt.year.min(), A.date.dt.year.max()), (B.date.dt.year.min(), B.date.dt.year.max())
    split_tag = f"測試 {args.test_year}(A {yA[0]}–{yA[1]} / B {yB[0]}–{yB[1]})"
    out_path = OUT if (args.test_year, args.train_years, args.meta_years) == DEFAULT else \
        os.path.join(ML.OUT, f"stacking_{args.test_year}_A{yA[0]}-{yA[1]}_B{yB[0]}-{yB[1]}.json")
    yb, yc = B["y"].to_numpy(), C["y"].to_numpy()
    print(f"A {len(A):,}(真高 {(A.y == DOWN).sum():,}、真低 {(A.y == UP).sum():,})/ B {len(B):,} / C {len(C):,}  ({time.time() - t0:.0f}s)", flush=True)

    res = {"periods": {"A": [str(A.date.min().date()), str(A.date.max().date())], "B": [str(B.date.min().date()), str(B.date.max().date())],
                       "C": [str(C.date.min().date()), str(C.date.max().date())]},
           "n": {"A": len(A), "B": len(B), "C": len(C)},
           "rule": {**summarize(yc, rule_pred(C), NAMES), **extra(yc, rule_pred(C), C)}, "runs": {}}
    rng = np.random.default_rng(0)
    rand = rng.choice([UP, FLAT, DOWN], size=len(yc), p=[(yb == c).mean() for c in (UP, FLAT, DOWN)])
    res["prior_random"] = summarize(yc, rand, NAMES)
    res["mainline"] = {}                                                # 對照:主軸用整段訓練期(A + B)
    for seed in args.seeds:
        src = WF.MainlineSource(seed)
        src.fit(d["train"], fc)
        res["mainline"][seed] = summarize(yc, src.predict(C.drop(columns="y")).pred.to_numpy(), NAMES)
    print(f"主軸(訓練 {d['train'].date.dt.year.min()}–{d['train'].date.dt.year.max()},{len(d['train']):,} 筆)完成  ({time.time() - t0:.0f}s)", flush=True)
    for seed in args.seeds:
        base = BaseScorers(seed).fit(A, fc)
        FB, FC = base.transform(B), base.transform(C)
        for cls, tag in ((DOWN, "high"), (UP, "low")):                  # 測試期分數的分辨力
            s, cand = FC[f"s_{tag}"].to_numpy(), C[ML.CAND[cls]].to_numpy()
            res.setdefault("score_auc", {}).setdefault(tag, {})[seed] = {
                "true_vs_rest": float(roc_auc_score(yc == cls, s)),
                "cand_vs_ordinary": float(roc_auc_score(cand, s)),
                "true_vs_false_within_cand": float(roc_auc_score(yc[cand] == cls, s[cand])),
                "inside_rate_cand": float((s[cand] > 0).mean()), "inside_rate_ordinary": float((s[~cand] > 0).mean())}
        for inp in INPUTS:
            for ln in LEARNERS:
                meta = MetaLearner(ln, inp).fit(FB, yb)
                pred, _ = meta.predict(FC)
                r = {**summarize(yc, pred, NAMES), **extra(yc, pred, C)}
                if meta.coef():
                    r["coef"] = meta.coef()
                res["runs"].setdefault(f"{inp}|{ln}", {})[seed] = r
        print(f"  種子 {seed} 完成  ({time.time() - t0:.0f}s)", flush=True)

    rule = res["rule"]
    mm = [r["macro_f1"] for r in res["mainline"].values()]
    m0 = res["mainline"][args.seeds[0]]
    print(f"\n{split_tag},{len(C):,} 天:規則 macro-F1 {rule['macro_f1']:.2%};先驗隨機 {res['prior_random']['macro_f1']:.2%};"
          f"主軸 {np.mean(mm):.2%} ± {np.std(mm):.2%}(種子 {args.seeds[0]}:找到 高 {m0['recall']['高點']:.1%} / 低 {m0['recall']['低點']:.1%},"
          f"命中 高 {m0['precision']['高點']:.1%} / 低 {m0['precision']['低點']:.1%})")
    print(f"{'輸入|元學習器':<22}{'macro-F1(3 種子)':>18}{'找到 高/低':>14}{'命中 高/低':>14}{'判非極值正確':>10}{'判反':>6}{'判高在規則候選內':>14}")
    summary = {}
    for key, runs in res["runs"].items():
        mf = [r["macro_f1"] for r in runs.values()]
        r0 = runs[args.seeds[0]]
        summary[key] = {"macro_f1_mean": float(np.mean(mf)), "macro_f1_sd": float(np.std(mf))}
        print(f"{key:<22}{np.mean(mf) * 100:>11.2f} ± {np.std(mf) * 100:.2f}"
              f"{r0['recall']['高點'] * 100:>8.1f}/{r0['recall']['低點'] * 100:.1f}%"
              f"{(r0['precision']['高點'] or 0) * 100:>8.1f}/{(r0['precision']['低點'] or 0) * 100:.1f}%"
              f"{(r0['precision']['非極值'] or 0) * 100:>9.1f}%{r0['cross_errors']:>6}"
              f"{(r0['pred_high_in_rule_cand'] or 0) * 100:>12.1f}%")
        ML.write_log({"time": time.strftime("%Y-%m-%d %H:%M"), "tag": f"stack-{key}", "split": split_tag,
                      "mode": "stack", "window": 6, "vol_ma": ML.VOL_MA, "arch": ML.ARCH, "latent": ML.LATENT, "nu": NU,
                      "seeds": len(args.seeds), "rule_macro_f1": round(rule["macro_f1"] * 100, 2),
                      "model_macro_f1": round(np.mean(mf) * 100, 2), "model_sd": round(np.std(mf) * 100, 2),
                      "delta_vs_rule": round((np.mean(mf) - rule["macro_f1"]) * 100, 2),
                      "acc": round(r0["acc"] * 100, 2), "bal_acc": round(r0["bal_acc"] * 100, 2),
                      "prec_high": round((r0["precision"]["高點"] or 0) * 100, 2), "prec_low": round((r0["precision"]["低點"] or 0) * 100, 2)})
    res["summary"] = summary
    res["mainline_summary"] = {"macro_f1_mean": float(np.mean(mm)), "macro_f1_sd": float(np.std(mm)),
                               "train": [str(d["train"].date.min().date()), str(d["train"].date.max().date())], "n_train": len(d["train"])}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n記錄於 {out_path}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
