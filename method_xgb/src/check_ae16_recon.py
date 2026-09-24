"""2026-09-22:檢查 AE 38→16 壓縮再還原的失真(測試年 2025 這一組;訓練 2016~2023、早停看 2024)。
每欄在測試段的還原 R²(= 1 − 還原誤差 ÷ 該欄變異),3 個 seed 平均。訓練設定與 exp_ae_shortlist_r3.train_ae 相同。"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exp_ae_shortlist_r3 as M
import torch, torch.nn as nn

Y, K = 2025, 16
tr, va, te = M.FOLDS[Y]; Z = M.Z; F = M.F38
REC = []
for seed in M.SEEDS:
    torch.manual_seed(seed); np.random.seed(seed)
    E_ = nn.Sequential(nn.Linear(38, K), nn.Tanh()); D_ = nn.Sequential(nn.Linear(K, 38))
    opt = torch.optim.Adam(list(E_.parameters()) + list(D_.parameters()), 1e-3, weight_decay=1e-5)
    Xt, Xv = torch.from_numpy(Z[tr]), torch.from_numpy(Z[va]); best, bad, state = np.inf, 0, None
    for ep in range(1, 201):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 512):
            xb = Xt[perm[i:i + 512]]; opt.zero_grad(); loss = ((D_(E_(xb)) - xb) ** 2).mean(); loss.backward(); opt.step()
        with torch.no_grad(): v = float(((D_(E_(Xv)) - Xv) ** 2).mean())
        if v < best - 1e-5: best, bad, state = v, 0, ({k: t.clone() for k, t in E_.state_dict().items()}, {k: t.clone() for k, t in D_.state_dict().items()})
        else:
            bad += 1
            if bad >= 10: break
    E_.load_state_dict(state[0]); D_.load_state_dict(state[1])
    with torch.no_grad(): REC.append(D_(E_(torch.from_numpy(Z[te]))).numpy())
    print("seed", seed, "epochs", ep, flush=True)
X = Z[te]; out = []
for j, f in enumerate(F):
    r2 = [1 - ((R[:, j] - X[:, j]) ** 2).mean() / X[:, j].var() for R in REC]
    corr = [np.corrcoef(R[:, j], X[:, j])[0, 1] for R in REC]
    out.append({"feature": f, "r2": float(np.mean(r2)), "corr": float(np.mean(corr))})
df = pd.DataFrame(out).sort_values("r2")
tot = float(np.mean([1 - ((R - X) ** 2).sum() / ((X - X.mean(0)) ** 2).sum() for R in REC]))
mse = float(np.mean([((R - X) ** 2).mean() for R in REC]))
df.to_csv(os.path.join(M.P.XGB_EXP, "ae16_recon_2025.csv"), index=False)
print("整體 R2", round(tot, 4), "MSE", round(mse, 4)); print(df.round(3).to_string(index=False))
