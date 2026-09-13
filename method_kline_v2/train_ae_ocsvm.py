"""階段二 + 三:只用「大漲」樣本訓練 AE → 驗收可還原 → 潛在向量訓練 OC-SVM → 四大指標(計畫 §3、§4)。

流程(每個池、輸入 C):
  切分 train ≤ 2022 / val 2023–2024 / test 2025–2026-09(purge 5 天),標準化(train 全體)、截 ±5、缺值補 train 中位數。
  AE:輸入 → 128 → z → 128 → 輸入,MSE;只用 train 正例訓練,val 正例重建誤差 10 輪不降就停(最多 200 輪)。
     對照:同結構用 train 全部樣本訓練。
  驗收(§3.2):train / val 正例重建誤差(相對「輸出全猜平均」的 MSE = 1)、逐欄重建相關(最低 / 中位)、
     非正例重建誤差是否 > 正例(AUC,誤差當分數)、潛在向量 logistic AUC vs 原始輸入 logistic AUC。
  OC-SVM(§4):train 正例的潛在向量,nu ∈ {0.05, 0.1, 0.2, 0.5};val / test 出訊號比例、Precision / Recall / Accuracy / F1。
  對照組(§4.2):(1) AE 重建誤差當分數取最像的前 10%;(2) 潛在向量 + logistic 前 10%;(3) 原始 C + XGB 前 10%。
  每種判法另報前 1%、以及測試段每年訊號數(2025 全年、2026 至 09-11,並換算成 245 個交易日的年率)。
--k-sigma:重新標籤 y = r_h5 > k × σ20 × √5(samples 的 y 欄是 k = 2;門檻曲線顯示 4σ 以上正例才開始成群)。
用法:python train_ae_ocsvm.py --pool all --k-sigma 4 [--z 16]  → results/bigmove_stage2_<pool>_<set>_z<z>_k<k>.json
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
sys.path.insert(0, HERE)
from check_separability import split, H  # noqa: E402
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

DATA = os.path.join(P.CACHE, "bigmove")
RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)
SIG_FRAC = 0.10


class AE(nn.Module):
    def __init__(self, d, z, h=128):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(d, h), nn.ReLU(), nn.Linear(h, h // 2), nn.ReLU(), nn.Linear(h // 2, z))
        self.dec = nn.Sequential(nn.Linear(z, h // 2), nn.ReLU(), nn.Linear(h // 2, h), nn.ReLU(), nn.Linear(h, d))

    def forward(self, x):
        z = self.enc(x)
        return self.dec(z), z


def train_ae(Xtr, Xva, z, seed=42, max_epochs=200, patience=10, log=print):
    torch.manual_seed(seed)
    m = AE(Xtr.shape[1], z)
    opt = torch.optim.Adam(m.parameters(), 1e-3, weight_decay=1e-5)
    Xt, Xv = torch.FloatTensor(Xtr), torch.FloatTensor(Xva)
    best, best_state, bad = np.inf, None, 0
    for ep in range(1, max_epochs + 1):
        m.train()
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 256):
            xb = Xt[perm[i:i + 256]]
            opt.zero_grad()
            r, _ = m(xb)
            loss = ((r - xb) ** 2).mean()
            loss.backward()
            opt.step()
        m.eval()
        with torch.no_grad():
            v = float(((m(Xv)[0] - Xv) ** 2).mean())
        if v < best - 1e-4:
            best, bad, best_state = v, 0, {k: t.clone() for k, t in m.state_dict().items()}
        else:
            bad += 1
        if ep % 20 == 0:
            log(f"      epoch {ep:3d} val 正例 MSE {v:.4f}(最佳 {best:.4f})")
        if bad >= patience:
            break
    m.load_state_dict(best_state)
    m.eval()
    return m, ep, best


def recon(m, X):
    with torch.no_grad():
        Xt = torch.FloatTensor(X)
        r, z = m(Xt)
        return r.numpy(), ((r - Xt) ** 2).mean(1).numpy(), z.numpy()


def prf(y, pred):
    y, pred = np.asarray(y).astype(bool), np.asarray(pred).astype(bool)
    TP = int((pred & y).sum()); FP = int((pred & ~y).sum()); FN = int((~pred & y).sum()); TN = int((~pred & ~y).sum())
    Pp = TP / (TP + FP) if TP + FP else 0.0; R = TP / (TP + FN) if TP + FN else 0.0
    return {"P": Pp * 100, "R": R * 100, "Acc": (TP + TN) / len(y) * 100, "F1": (2 * Pp * R / (Pp + R) * 100) if Pp + R else 0.0,
            "sig": pred.mean() * 100, "base": y.mean() * 100}


def top_frac(score, frac=SIG_FRAC):
    """分數越大越像;取前 frac 為訊號。"""
    thr = np.quantile(score, 1 - frac)
    return score >= thr


def fmt(r):
    return f"出訊號 {r['sig']:5.1f}%  P {r['P']:5.2f}%(隨機 {r['base']:.2f}%)  R {r['R']:5.2f}%  Acc {r['Acc']:5.2f}%  F1 {r['F1']:5.2f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    ap.add_argument("--set", default="C")
    ap.add_argument("--z", type=int, default=16)
    ap.add_argument("--k-sigma", type=float, default=2.0, help="大漲門檻 k:r_h5 > k*sigma20*sqrt(5);2 = samples 內建的 y 欄")
    ap.add_argument("--nus", default="0.05,0.1,0.2,0.5")
    ap.add_argument("--seed", type=int, default=42, help="AE 初始化與批次順序的種子(檢查結果穩不穩定用)")
    a = ap.parse_args()
    t0 = time.time()
    meta = json.load(open(os.path.join(DATA, f"samples_{a.pool}_meta.json"), encoding="utf-8"))
    cols = meta["cols"][a.set]
    df = pd.read_parquet(os.path.join(DATA, f"samples_{a.pool}.parquet"), columns=cols + ["r_h5", "sigma20", "y"])
    df["y"] = (df["r_h5"] > a.k_sigma * df["sigma20"] * np.sqrt(H)).astype(float)   # k=2 時與原 y 欄相同
    tr, va, te = split(df)
    te_year = te.index.get_level_values("date").year.values
    te_days = {int(yr): int(te.index.get_level_values("date")[te_year == yr].nunique()) for yr in np.unique(te_year)}
    med = tr[cols].median()
    sc = StandardScaler().fit(tr[cols].fillna(med).values)
    X = {k: np.clip(sc.transform(v[cols].fillna(med).values), -5, 5).astype(np.float32) for k, v in (("tr", tr), ("va", va), ("te", te))}
    y = {k: v["y"].values.astype(int) for k, v in (("tr", tr), ("va", va), ("te", te))}
    pos = {k: y[k] == 1 for k in y}
    print(f"===== {a.pool} 輸入 {a.set}({len(cols)} 欄) z={a.z} 門檻 {a.k_sigma:g}σ√5:train {len(tr):,}(正例 {pos['tr'].sum():,})/ val {len(va):,}(正例 {pos['va'].sum():,})/ test {len(te):,}(正例 {pos['te'].sum():,});"
          f"test 交易日 {te_days} =====", flush=True)
    out = {"pool": a.pool, "set": a.set, "n_cols": len(cols), "z": a.z, "k_sigma": a.k_sigma, "seed": a.seed, "label": f"r_h5 > {a.k_sigma:g}*sigma20*sqrt(5)",
           "n": {k: int(len(v)) for k, v in y.items()}, "n_pos": {k: int(pos[k].sum()) for k in pos}, "base": {k: float(v.mean()) for k, v in y.items()},
           "test_days": te_days}

    def per_year(pred):
        """測試段每年訊號數、其中真大漲數,與 245 個交易日年率。"""
        pred = np.asarray(pred).astype(bool)
        r = {}
        for yr, nd in te_days.items():
            m = te_year == yr
            n_sig, n_hit = int(pred[m].sum()), int((pred[m] & pos["te"][m]).sum())
            r[str(yr)] = {"signals": n_sig, "hits": n_hit, "days": nd, "signals_per_245d": round(n_sig / nd * 245), "signals_per_day": round(n_sig / nd, 2)}
        return r

    # ── 階段二:AE ─────────────────────────────────────────────
    for tag, Xtrain in (("AE_大漲樣本", X["tr"][pos["tr"]]), ("AE_全部樣本(對照)", X["tr"])):
        print(f"  [{tag}] 訓練 {len(Xtrain):,} 列", flush=True)
        m, ep, best = train_ae(Xtrain, X["va"][pos["va"]], a.z, seed=a.seed, log=lambda s: print(s, flush=True))
        rec = {"epochs": ep, "val_pos_mse": best}
        R, E, Z = {}, {}, {}
        for k in ("tr", "va", "te"):
            R[k], E[k], Z[k] = recon(m, X[k])
        rec["train_pos_mse"] = float(E["tr"][pos["tr"]].mean())
        rec["mse_pos"] = {k: float(E[k][pos[k]].mean()) for k in E}
        rec["mse_neg"] = {k: float(E[k][~pos[k]].mean()) for k in E}
        corr = np.array([np.corrcoef(R["va"][:, j], X["va"][:, j])[0, 1] for j in range(len(cols))])
        corr = np.nan_to_num(corr)
        rec["col_corr_min"], rec["col_corr_median"], rec["cols_corr_below_0.5"] = float(corr.min()), float(np.median(corr)), int((corr < 0.5).sum())
        rec["recon_err_auc"] = {k: float(roc_auc_score(y[k], -E[k])) for k in ("va", "te")}     # 誤差小 = 像正例 → 應 > 0.5
        lr_z = LogisticRegression(max_iter=500, C=0.1).fit(Z["tr"], y["tr"])
        lr_x = LogisticRegression(max_iter=500, C=0.1).fit(X["tr"], y["tr"])
        rec["latent_lr_auc"] = {k: float(roc_auc_score(y[k], lr_z.predict_proba(Z[k])[:, 1])) for k in ("va", "te")}
        rec["raw_lr_auc"] = {k: float(roc_auc_score(y[k], lr_x.predict_proba(X[k])[:, 1])) for k in ("va", "te")}
        print(f"    驗收:{ep} 輪;正例 MSE train {rec['train_pos_mse']:.3f} / val {rec['mse_pos']['va']:.3f} / test {rec['mse_pos']['te']:.3f}(全猜平均 ≈ 1.0);"
              f"非正例 MSE val {rec['mse_neg']['va']:.3f} / test {rec['mse_neg']['te']:.3f}", flush=True)
        print(f"          逐欄重建相關 最低 {rec['col_corr_min']:.2f} 中位 {rec['col_corr_median']:.2f},相關 < 0.5 的欄 {rec['cols_corr_below_0.5']} / {len(cols)}", flush=True)
        print(f"          「誤差小 = 像大漲」AUC val {rec['recon_err_auc']['va']:.3f} test {rec['recon_err_auc']['te']:.3f}(要 ≥ 0.60 才算正例有獨特結構)", flush=True)
        print(f"          潛在向量 logistic AUC val {rec['latent_lr_auc']['va']:.3f} test {rec['latent_lr_auc']['te']:.3f} | 原始輸入 logistic AUC val {rec['raw_lr_auc']['va']:.3f} test {rec['raw_lr_auc']['te']:.3f}", flush=True)

        # ── 階段三:OC-SVM 與對照 ─────────────────────────────
        rec["ocsvm"] = {}
        Ztr_pos = Z["tr"][pos["tr"]]
        for nu in [float(v) for v in a.nus.split(",")]:
            oc = OneClassSVM(kernel="rbf", nu=nu, gamma="scale").fit(Ztr_pos)
            D = {k: oc.decision_function(Z[k]) for k in ("va", "te")}
            raw = {k: D[k] >= 0 for k in D}                                    # 原判法:predict == 1
            r = {k: prf(y[k], raw[k]) for k in ("va", "te")}
            r10 = {k: prf(y[k], top_frac(D[k])) for k in ("va", "te")}        # 決策函數前 10%(控制出訊號比例)
            r1 = {k: prf(y[k], top_frac(D[k], 0.01)) for k in ("va", "te")}
            rec["ocsvm"][str(nu)] = {"raw": r, "top10": r10, "top1": r1,
                                     "per_year_test": {"raw": per_year(raw["te"]), "top10": per_year(top_frac(D["te"])), "top1": per_year(top_frac(D["te"], 0.01))}}
            print(f"    OC-SVM nu={nu:<4}: val {fmt(r['va'])} | test {fmt(r['te'])}", flush=True)
            print(f"           前10%  : val {fmt(r10['va'])} | test {fmt(r10['te'])}", flush=True)
            print(f"           前1%   : val {fmt(r1['va'])} | test {fmt(r1['te'])}", flush=True)
        S_con = {"重建誤差": {k: -E[k] for k in ("va", "te")}, "潛在+logistic": {k: lr_z.predict_proba(Z[k])[:, 1] for k in ("va", "te")}}
        rec["contrast"] = {}
        for nm, sc_ in S_con.items():
            for frac, lab in ((0.10, "前10%"), (0.01, "前1%")):
                r = {k: prf(y[k], top_frac(sc_[k], frac)) for k in ("va", "te")}
                r["per_year_test"] = per_year(top_frac(sc_["te"], frac))
                rec["contrast"][nm + lab] = r
                print(f"    對照 {nm + lab:14s}: val {fmt(r['va'])} | test {fmt(r['te'])}", flush=True)
        out[tag] = rec

    from xgboost import XGBClassifier
    xgb = XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=4, min_child_weight=50, subsample=0.8, colsample_bytree=0.6,
                        reg_lambda=5.0, n_jobs=4, random_state=42, eval_metric="logloss", early_stopping_rounds=50)
    xgb.fit(X["tr"], y["tr"], eval_set=[(X["va"], y["va"])], verbose=False)
    px = {k: xgb.predict_proba(X[k])[:, 1] for k in ("va", "te")}
    out["對照_原始C+XGB_auc"] = {k: float(roc_auc_score(y[k], px[k])) for k in px}
    for frac, lab in ((0.10, "前10%"), (0.01, "前1%")):
        r = {k: prf(y[k], top_frac(px[k], frac)) for k in ("va", "te")}
        r["per_year_test"] = per_year(top_frac(px["te"], frac))
        out["對照_原始C+XGB" + lab] = r
        print(f"    對照 原始 C + XGB {lab}: val {fmt(r['va'])} | test {fmt(r['te'])}", flush=True)
    fp = os.path.join(RES, f"bigmove_stage2_{a.pool}_{a.set}_z{a.z}_k{a.k_sigma:g}" + (f"_seed{a.seed}" if a.seed != 42 else "") + ".json")
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[SAVED] {fp} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
