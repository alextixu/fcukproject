"""全樣本 AE(大漲資料集 C 集 K 線欄位 → 16 維 + 還原誤差)→ XGB。三組:原 permpos 欄 / +AE / 只用 AE。
用法: python exp_ae_full.py --pool tw50 --split x25|x26   (tw50 h5)
      python exp_ae_full.py --pool tw500 --split x25     (tw500 h20,lowmem)
AE:全部樣本訓練(train_end 前一年為早停),StandardScaler 用 ≤train_end 列。輸出:experiments/<tag>_aefull.json、results/fullpred_<tag>_aefull.parquet"""
import sys, os, json, time, argparse, numpy as np, pandas as pd, torch
R=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0,R); sys.path.insert(0,os.path.join(R,'method_xgb','src')); sys.path.insert(0,os.path.join(R,'method_kline_v2'))
from common import paths as P
from split import time_split
from lowmem import load_lowmem
from train_ae_ocsvm import train_ae
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
ap=argparse.ArgumentParser(); ap.add_argument('--pool',default='tw50'); ap.add_argument('--split',default='x25'); ap.add_argument('--z',type=int,default=16); ap.add_argument('--ae-input',default='c',choices=['c','xgbfull'],help='c = 大漲資料集 C 集 K 線欄位;xgbfull = XGB 自己的 full 特徵(覆蓋率 100%%)'); a=ap.parse_args()
H=5 if a.pool=='tw50' else 20; TAG=f"{a.split}-{a.pool}-h{H}-cs"; Z=a.z
x=json.load(open(os.path.join(P.XGB_EXP,f'{TAG}.json'))); TAG0=TAG; cfg=x['config']; feats=x['results']['full_permpos']['features']; ycol=f'y_cs_h{H}'
TE=pd.Timestamp(cfg['train_end']); AE_VA=(TE-pd.DateOffset(years=1))
if a.ae_input=='c':
    meta=json.load(open(os.path.join(P.CACHE,'bigmove',f'samples_{a.pool}_meta.json'))); cols=meta['cols']['C']
    bm=pd.read_parquet(os.path.join(P.CACHE,'bigmove',f'samples_{a.pool}.parquet'), columns=cols)
else:
    cols=x['results']['full']['features']
    if a.pool=='tw500': bm,_=load_lowmem(os.path.join(P.FEATURES,f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}_lowmem"), cols, cfg['train_end'], cfg.get('stride',1))
    else: bm=pd.read_parquet(os.path.join(P.FEATURES,f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}.parquet"), columns=cols)
    TAG=TAG+'-xf'
d=bm.index.get_level_values('date'); fit_m=np.asarray(d<=TE); dtr=np.asarray(d<=AE_VA); dva=np.asarray((d>AE_VA)&(d<=TE))
med=bm.loc[fit_m,cols].median(); sc=StandardScaler().fit(bm.loc[fit_m,cols].fillna(med).values)
X=np.clip(sc.transform(bm[cols].fillna(med).values),-5,5).astype(np.float32); bm_index=bm.index; del bm
t0=time.time(); m=train_ae(X[dtr],X[dva],Z,seed=42,log=lambda s: None)[0]; m.eval()
with torch.no_grad():
    Xt=torch.FloatTensor(X); rec,z=m(Xt); err=((rec-Xt)**2).mean(1).numpy(); z=z.numpy()
print(f'[{TAG}] AE {len(cols)} 欄→{Z} 維,訓練 {int(dtr.sum())} / 早停 {int(dva.sum())} 列,{time.time()-t0:.0f}s', flush=True)
ae=pd.DataFrame(z, index=bm_index, columns=[f'ae_z{i}' for i in range(Z)]); ae['ae_err']=err; del X
if a.pool=='tw500':
    panel,_=load_lowmem(os.path.join(P.FEATURES,f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}_lowmem"), feats+[ycol,f'r_h{H}'], cfg['train_end'], cfg.get('stride',1))
else:
    panel=pd.read_parquet(os.path.join(P.FEATURES,f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}.parquet"), columns=feats+[ycol,f'r_h{H}'])
panel=panel.join(ae, how='left'); tr,va,te=time_split(panel,cfg['train_end'],cfg['val_end'],H,ycol)
score=panel[panel.index.get_level_values('date')>pd.Timestamp(cfg['val_end'])]; full={}; del panel
print(f'XGB train {len(tr)} val {len(va)} test {len(te)};AE 覆蓋率 train {tr.ae_err.notna().mean():.3f} test {te.ae_err.notna().mean():.3f}', flush=True)
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
        probs.append(mdl.predict_proba(te[fc])[:,1]); full.setdefault(name,[]).append(mdl.predict_proba(score[fc])[:,1])
    out[name]={}
    for yr in sorted(set(yrs.tolist())):
        mm=yrs==yr; res={}
        for rule in ('thr0.5','daily-med'):
            per=[]
            for pr in probs:
                pred=(pr[mm]>=0.5).astype(int) if rule=='thr0.5' else (pr[mm]>pd.Series(pr[mm]).groupby(np.asarray(dte[mm])).transform('median').values).astype(int)
                per.append(prf(yte[mm],pred))
            per=np.array(per); res[rule]={'mean':per.mean(0).round(2).tolist(),'std':per.std(0).round(2).tolist()}
        out[name][int(yr)]=res; dm=res['daily-med']
        print(f"  {name:8s} {yr} 當日中位數: Acc {dm['mean'][0]:.2f}±{dm['std'][0]:.2f} F1m {dm['mean'][1]:.2f} P {dm['mean'][2]:.2f} R {dm['mean'][3]:.2f}", flush=True)
    print(f'  ({name}: {len(fc)} 欄, {time.time()-t0:.0f}s)', flush=True)
pd.DataFrame({('p_'+n.replace('+','')): np.mean(v,axis=0).astype('float32') for n,v in full.items()}, index=score.index).to_parquet(os.path.join(P.RESULTS,f'fullpred_{TAG}_aefull.parquet'))
json.dump({'tag':TAG,'ae_input_cols':len(cols),'z':Z,'ae_train_rows':int(dtr.sum()),'results':out}, open(os.path.join(P.XGB_EXP,f'{TAG}_aefull.json'),'w'), indent=1); print('[DONE]')
