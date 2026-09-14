"""提案 2:大漲 AE 當特徵。AE 只用 tw50「大漲前夕」樣本(≤2022 訓練、2023 早停)訓練,對每列算重建誤差與 16 維潛在向量,
加進 XGB tw50 h5 cs full_permpos 的 90 欄;協定同 x25:訓練 ≤2023、2024 早停、2025/2026 分年,四大指標(固定 0.5 與當日中位數)。"""
import sys, os, json, time, numpy as np, pandas as pd, torch
R=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0,R); sys.path.insert(0,R+'/method_xgb/src'); sys.path.insert(0,R+'/method_kline_v2')
from common import paths as P
from split import time_split
from train_ae_ocsvm import AE, train_ae
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier
S=os.path.join(R,'method_xgb','experiments'); K=float(sys.argv[1]) if len(sys.argv)>1 else 2.0; Z=16
meta=json.load(open(f'{R}/common/cache/bigmove/samples_tw50_meta.json')); cols=meta['cols']['C']
bad=[c for c in cols if c.startswith(('a_','f_','fut','r_h','y'))]; assert not bad, bad
bm=pd.read_parquet(f'{R}/common/cache/bigmove/samples_tw50.parquet', columns=cols+['r_h5','sigma20'])
d=bm.index.get_level_values('date'); pos=(bm['r_h5']>K*bm['sigma20']*np.sqrt(5)).values
tr_m=np.asarray(d<='2022-12-31'); va_m=np.asarray((d>'2022-12-31')&(d<='2023-12-31')); fit_m=np.asarray(d<='2023-12-31')
med=bm.loc[fit_m,cols].median(); sc=StandardScaler().fit(bm.loc[fit_m,cols].fillna(med).values)
X=np.clip(sc.transform(bm[cols].fillna(med).values),-5,5).astype(np.float32)
print(f'AE 訓練正例 {int((pos&tr_m).sum())} / 早停正例 {int((pos&va_m).sum())} (k={K:g}σ√5), 輸入 {len(cols)} 欄', flush=True)
m=train_ae(X[pos&tr_m], X[pos&va_m], Z, seed=42, log=lambda s: None)
m=m[0] if isinstance(m,tuple) else m; m.eval()
with torch.no_grad():
    rec,z=m(torch.FloatTensor(X)); err=((rec-torch.FloatTensor(X))**2).mean(1).numpy(); z=z.numpy()
ae=pd.DataFrame(z, index=bm.index, columns=[f'ae_z{i}' for i in range(Z)]); ae['ae_err']=err
# 診斷:重建誤差對「大漲」的 AUC(誤差越小越像大漲前夕 → 用 −err)
for nm,mm in (('2024',np.asarray((d>'2023-12-31')&(d<='2024-12-31'))),('2025-26',np.asarray(d>'2024-12-31'))):
    print(f'  AE 誤差 AUC(−err vs 大漲 {K:g}σ){nm}: {roc_auc_score(pos[mm], -err[mm]):.4f}', flush=True)
# XGB
x25=json.load(open(f'{R}/method_xgb/experiments/x25-tw50-h5-cs.json')); cfg=x25['config']; feats=x25['results']['full_permpos']['features']; ycol='y_cs_h5'
panel=pd.read_parquet(os.path.join(P.FEATURES,'features_tw50_2016-01-01_2026-09-11.parquet'), columns=feats+[ycol,'r_h5'])
panel=panel.join(ae, how='left')
tr,va,te=time_split(panel,cfg['train_end'],cfg['val_end'],5,ycol)
print(f'XGB train {len(tr)} val {len(va)} test {len(te)};AE 特徵覆蓋率 train {tr.ae_err.notna().mean():.3f} test {te.ae_err.notna().mean():.3f}', flush=True)
aecols=list(ae.columns); variants={'base':feats,'+ae':feats+aecols,'ae_only':aecols}
def prf(y,pred):
    tp=((pred==1)&(y==1)).sum(); fp=((pred==1)&(y==0)).sum(); fn=((pred==0)&(y==1)).sum(); tn=((pred==0)&(y==0)).sum()
    Pq=tp/(tp+fp) if tp+fp else 0; Rq=tp/(tp+fn) if tp+fn else 0; f1=2*Pq*Rq/(Pq+Rq) if Pq+Rq else 0
    P0=tn/(tn+fn) if tn+fn else 0; R0=tn/(tn+fp) if tn+fp else 0; f0=2*P0*R0/(P0+R0) if P0+R0 else 0
    return np.array([(tp+tn)/len(y),(f1+f0)/2,Pq,Rq])*100
yte=te[ycol].values.astype(int); dte=te.index.get_level_values('date'); yrs=np.asarray(dte.year); out={}
for name,fc in variants.items():
    probs=[]; t0=time.time()
    for seed in cfg['seeds']:
        p=dict(cfg['xgb']); p.update(tree_method='hist',eval_metric='logloss')
        mdl=XGBClassifier(random_state=seed,**p).fit(tr[fc],tr[ycol].values.astype(int),eval_set=[(va[fc],va[ycol].values.astype(int))],verbose=False)
        probs.append(mdl.predict_proba(te[fc])[:,1])
    out[name]={}
    for yr in (2025,2026):
        mm=yrs==yr; res={}
        for rule in ('thr0.5','daily-med'):
            per=[]
            for pr in probs:
                if rule=='thr0.5': pred=(pr[mm]>=0.5).astype(int)
                else: pred=(pr[mm]>pd.Series(pr[mm]).groupby(np.asarray(dte[mm])).transform('median').values).astype(int)
                per.append(prf(yte[mm],pred))
            per=np.array(per); res[rule]={'mean':per.mean(0).round(2).tolist(),'std':per.std(0).round(2).tolist()}
        out[name][yr]=res
        dm=res['daily-med']; print(f"  {name:8s} {yr} 當日中位數: Acc {dm['mean'][0]:.2f}±{dm['std'][0]:.2f} F1m {dm['mean'][1]:.2f} P {dm['mean'][2]:.2f} R {dm['mean'][3]:.2f} | thr0.5 Acc {res['thr0.5']['mean'][0]:.2f} F1m {res['thr0.5']['mean'][1]:.2f}", flush=True)
    print(f'  ({name}: {len(fc)} 欄, {time.time()-t0:.0f}s)', flush=True)
json.dump({'k_sigma':K,'z':Z,'n_ae_pos_train':int((pos&tr_m).sum()),'results':out}, open(f'{S}/x25-tw50-h5-cs_aefeat_k{K:g}.json','w'), indent=1); print('[DONE]')
