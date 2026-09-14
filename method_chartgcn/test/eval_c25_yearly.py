"""Chart-GCN:載入 c25 模型與 test 快取,分 2025 / 2026 評估四大指標(同日批次)。"""
import sys, os, glob, json, numpy as np, torch
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R); sys.path.insert(0, R+'/core'); sys.path.insert(0, R+'/test')
from torch.utils.data import DataLoader, Subset
from run_paper_repro import load_ds_cache
from train import DateGroupedBatchSampler, evaluate
from model import ChartGCN
out = {}
for h in (1, 5):
    js = sorted(glob.glob(f'{R}/experiments_2026/EXP-*c25-gridbest-date-h{h}-s42.json'))
    if not js: print('missing h', h); continue
    d = json.load(open(js[-1])); p = d['params']
    key = f"tw500_2016-01-01_2024-12-31_2026-09-11_w140m80N10g4s1_raw".replace('tw500', p['tickers'] + str(p['n_stocks']))
    key += f"_h{h}" if h != 1 else ""
    te = load_ds_cache(f"{R}/experiments_2026/dscache/{key}_test.npz")
    model = ChartGCN(N=p['N'], g=p['g'], F_dim=9, paper_exact=True, use_attention=not p['no_attention'])
    model.load_state_dict(torch.load(js[-1].replace('.json', '_model.pt'), map_location='cpu')); model.eval()
    yrs = np.array([m[1].year for m in te.meta])
    out[f'h{h}'] = {'exp': d['exp_id'], 'all': d['metrics'], 'f1_macro_all': d['f1_macro'], 'test_pos_pct': d['test_pos_pct']}
    for yr in (2025, 2026):
        idx = np.where(yrs == yr)[0].tolist(); sub = Subset(te, idx)
        m = evaluate(model, DataLoader(sub, batch_sampler=DateGroupedBatchSampler(sub, shuffle=False)), 'cpu')
        m['f1_macro'] = (m['f1_1'] + m['f1_0']) / 2; m['n'] = len(idx); m['pos_pct'] = float(te.y[idx].mean() * 100)
        out[f'h{h}'][str(yr)] = {k: round(float(v), 4) for k, v in m.items()}
        print(f"h{h} {yr} n={len(idx)} pos={m['pos_pct']:.2f}% acc={m['acc']:.4f} f1m={m['f1_macro']:.4f} pre1={m['pre_1']:.4f} rec1={m['rec_1']:.4f} pre0={m['pre_0']:.4f} rec0={m['rec_0']:.4f}")
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'experiments_2026', 'c25_yearly_2025_2026.json'), 'w'), ensure_ascii=False, indent=1)
