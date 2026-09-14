"""XGB tw500 h20 cs full_permpos:基準多 seed / 時間權重。用法: python xgb_tw500_exp.py <name> <half_life_years|0> <seeds,csv>"""
import sys, os, json, time, numpy as np, pandas as pd
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, R); sys.path.insert(0, R + '/method_xgb/src')
from common import paths as P
from lowmem import load_lowmem
from split import time_split
from train_xgb import fit_xgb, predict_p
name, hl, seeds = sys.argv[1], float(sys.argv[2]), [int(s) for s in sys.argv[3].split(',')]
S = os.path.join(R, 'method_xgb', 'experiments')
base = json.load(open(f'{R}/method_xgb/experiments/x25-tw500-h20-cs.json'))
feats = base['results']['full_permpos']['features']; xgb_cfg = base['config']['xgb']; ycol = 'y_cs_h20'
prefix = os.path.join(P.FEATURES, 'features_tw500_2016-01-01_2026-09-11_lowmem')
t0 = time.time()
panel, fam = load_lowmem(prefix, feats + [ycol, 'r_h20'], '2023-12-31', 3)
tr, va, te = time_split(panel, '2023-12-31', '2024-12-31', 20, ycol); del panel
print(f'[DATA] train {len(tr)} val {len(va)} test {len(te)} ({time.time()-t0:.0f}s)', flush=True)
w = None
if hl > 0:
    age = (pd.Timestamp('2023-12-31') - tr.index.get_level_values('date')).days / 365.25
    w = np.power(0.5, np.asarray(age, dtype=np.float64) / hl).astype(np.float32)
    print(f'[WEIGHT] half-life {hl}y: min {w.min():.3f} mean {w.mean():.3f}', flush=True)
Xtr, ytr = tr[feats], tr[ycol].values.astype(int); Xva, yva = va[feats], va[ycol].values.astype(int); Xte, yte = te[feats], te[ycol].values.astype(int)
out = te[['r_h20']].copy(); out['y'] = yte; vout = va[['r_h20']].copy(); vout['y'] = yva; info = {}
from xgboost import XGBClassifier
for seed in seeds:
    t1 = time.time()
    p = dict(n_estimators=3000, learning_rate=0.03, max_depth=5, min_child_weight=50, subsample=0.8, colsample_bytree=0.5,
             reg_lambda=5.0, tree_method='hist', eval_metric='logloss', early_stopping_rounds=100, n_jobs=4); p.update(xgb_cfg)
    m = XGBClassifier(random_state=seed, **p)
    m.fit(Xtr, ytr, sample_weight=w, eval_set=[(Xva, yva)], verbose=False)
    out[f's{seed}'] = predict_p(m, Xte).astype('float32'); vout[f's{seed}'] = predict_p(m, Xva).astype('float32')
    acc = ((out[f's{seed}'] >= 0.5).astype(int) == yte).mean()
    info[str(seed)] = {'best_iter': int(m.best_iteration), 'test_acc_thr05': float(acc), 'sec': round(time.time() - t1)}
    print(f'  [{name} s{seed}] iters={m.best_iteration} test acc@0.5={acc*100:.2f}% ({time.time()-t1:.0f}s)', flush=True)
out.to_parquet(f'{S}/x25-tw500-h20-cs_exp_{name}_test.parquet'); vout.to_parquet(f'{S}/x25-tw500-h20-cs_exp_{name}_val.parquet')
json.dump({'name': name, 'half_life': hl, 'seeds': seeds, 'n_feat': len(feats), 'info': info}, open(f'{S}/x25-tw500-h20-cs_exp_{name}.json', 'w'), indent=1)
print('[DONE]', name, flush=True)
