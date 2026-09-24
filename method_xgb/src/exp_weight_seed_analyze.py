import pandas as pd, numpy as np, json, os, itertools
S = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'experiments')
def prf(y, pred):
    tp=((pred==1)&(y==1)).sum(); fp=((pred==1)&(y==0)).sum(); fn=((pred==0)&(y==1)).sum(); tn=((pred==0)&(y==0)).sum()
    P=tp/(tp+fp) if tp+fp else 0; R=tp/(tp+fn) if tp+fn else 0; f1=2*P*R/(P+R) if P+R else 0
    P0=tn/(tn+fn) if tn+fn else 0; R0=tn/(tn+fp) if tn+fp else 0; f0=2*P0*R0/(P0+R0) if P0+R0 else 0
    return np.array([(tp+tn)/len(y), (f1+f0)/2, P, R])*100
def daily_pred(pr, dates):
    return (pr > pd.Series(pr).groupby(np.asarray(dates)).transform('median').values).astype(int)
rows = []
for name in ('base', 'hl2', 'hl3'):
    fp = f'{S}/x25-tw500-h20-cs_exp_{name}_test.parquet'
    if not os.path.exists(fp): continue
    te = pd.read_parquet(fp); d = te.index.get_level_values('date'); yrs = np.asarray(d.year); y = te['y'].values
    seeds = [c for c in te.columns if c.startswith('s')]
    for yr in (2025, 2026):
        m = yrs == yr
        for rule in ('thr0.5', 'daily-med'):
            per = []
            for s in seeds[:3]:
                pr = te[s].values[m]; pred = (pr >= 0.5).astype(int) if rule == 'thr0.5' else daily_pred(pr, d[m])
                per.append(prf(y[m], pred))
            per = np.array(per); mu, sd = per.mean(0), per.std(0)
            ens3 = te[seeds[:3]].values[m].mean(1); ens5 = te[seeds[:5]].values[m].mean(1) if len(seeds) >= 5 else None
            e3 = prf(y[m], (ens3 >= 0.5).astype(int) if rule == 'thr0.5' else daily_pred(ens3, d[m]))
            e5 = prf(y[m], (ens5 >= 0.5).astype(int) if rule == 'thr0.5' else daily_pred(ens5, d[m])) if ens5 is not None else None
            rows.append(dict(exp=name, year=yr, rule=rule, n=int(m.sum()),
                             acc=f'{mu[0]:.2f}±{sd[0]:.2f}', f1m=f'{mu[1]:.2f}±{sd[1]:.2f}', P=f'{mu[2]:.2f}±{sd[2]:.2f}', R=f'{mu[3]:.2f}±{sd[3]:.2f}',
                             ens3_acc=f'{e3[0]:.2f}', ens3_f1m=f'{e3[1]:.2f}', ens5_acc=f'{e5[0]:.2f}' if e5 is not None else '', ens5_f1m=f'{e5[1]:.2f}' if e5 is not None else ''))
    if len(seeds) >= 5:
        for yr in (2025, 2026):
            m = yrs == yr
            accs = [prf(y[m], daily_pred(te[s].values[m], d[m]))[0] for s in seeds]
            print(f'{name} {yr} daily-med 5-seed acc: ' + ' '.join(f'{a:.2f}' for a in accs) + f'  mean {np.mean(accs):.2f} std {np.std(accs):.2f}')
df = pd.DataFrame(rows); pd.set_option('display.width', 250); print(df.to_string(index=False)); df.to_csv(f'{S}/x25-tw500-h20-cs_exp_summary.csv', index=False)
