"""tw500 h20 系統(x25-tw500-h20-cs / full_permpos:訓練 ≤2023、2024 早停、seed 42/43/44)重訓,對 2025-01 起每個特徵日打分
(含尚無 20 日標籤的最後幾天),供 NCKU 框架每日排名用。輸出: results/fullpred_x25-tw500-h20-cs_full_permpos.parquet(欄 p)"""
import json, os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT); from common import paths as P
sys.path.insert(0, P.XGB_SRC)
from lowmem import load_lowmem; from split import time_split; from train_xgb import fit_xgb, predict_p
TAG, SET = "x25-tw500-h20-cs", "full_permpos"
meta = json.load(open(os.path.join(P.XGB_EXP, f"{TAG}.json"), encoding="utf-8")); cfg = meta["config"]; feats = meta["results"][SET]["features"]
ycol = f"y_{cfg['label']}_h{cfg['horizon']}"
panel, _ = load_lowmem(os.path.join(P.FEATURES, f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}_lowmem"), feats + [ycol], cfg["train_end"], cfg.get("stride", 1))
tr, va, _ = time_split(panel, cfg["train_end"], cfg["val_end"], cfg["horizon"], ycol)
dates = panel.index.get_level_values("date"); te = panel[dates > pd.Timestamp(cfg["val_end"])]
print(f"train {len(tr)} / val {len(va)} / 打分 {len(te)} 列,最後一天 {te.index.get_level_values('date').max().date()},特徵 {len(feats)}", flush=True)
ps = []
for seed in cfg["seeds"]:
    m = fit_xgb(tr[feats], tr[ycol].values.astype(int), va[feats], va[ycol].values.astype(int), seed, cfg["xgb"])
    ps.append(predict_p(m, te[feats])); print(f"  seed {seed} best_iter {m.best_iteration}", flush=True)
out = pd.DataFrame({"p": np.mean(ps, axis=0).astype("float32")}, index=te.index)
old = pd.read_parquet(os.path.join(P.XGB_EXP, f"{TAG}_testpred.parquet"))[f"p_{SET}"]
j = out.join(old.rename("p_old"), how="inner")
print(f"核對原 testpred:重疊 {len(j)} 列,相關 {j['p'].corr(j['p_old']):.6f},最大差 {float((j['p'] - j['p_old']).abs().max()):.2e}")
fp = os.path.join(P.RESULTS, f"fullpred_{TAG}_{SET}.parquet"); out.to_parquet(fp); print(f"[SAVED] {fp}")
