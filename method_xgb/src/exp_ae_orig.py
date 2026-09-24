"""最一開始的 AE 規則 → XGB:AE 用全部訓練樣本(≤2023)訓練、原始架構(kline.autoencoder,潛在 4 維、60 epoch、MSE),
輸入 = 1 日 7 特徵 + 四大指標(11 欄,K 線 v1 最佳特徵集);另跑 346 欄 K 線輸入(潛在 16 維)當對照。
AE 的 4/16 維向量 + 還原誤差 → XGB tw50 h5 cs(x25 協定:訓練 ≤2023、2024 早停、2025/2026 分年),三組:原 90 欄 / +AE / 只用 AE。
用法: python ae_orig_xgb_tw50.py kline | c346"""
import sys, os, json, time, numpy as np, pandas as pd, torch
R=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0,R); sys.path.insert(0,R+'/method_xgb/src'); sys.path.insert(0,R+'/backtest/scripts'); sys.path.insert(0,R+'/method_kline')
from common import paths as P
from split import time_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
MODE=sys.argv[1]
if MODE=='kline':
    from run_kline_plus_ta import load_raw, build_dataset, FEATURE_SETS, plus_ta
    from kline.autoencoder import Autoencoder
    import kline.config as KC
    raw=load_raw(); df=build_dataset(raw, plus_ta(FEATURE_SETS[0][1]))
    cols=[c for c in df.columns if c not in ('future_ret','ticker')]
    df.index.name='date'; bm=df.set_index('ticker',append=True)[cols]; Z=KC.LATENT_DIM
else:
    meta=json.load(open(f'{R}/common/cache/bigmove/samples_tw50_meta.json')); cols=meta['cols']['C']
    bm=pd.read_parquet(f'{R}/common/cache/bigmove/samples_tw50.parquet', columns=cols); Z=16
d=bm.index.get_level_values('date'); fit_m=np.asarray(d<='2023-12-31')
med=bm.loc[fit_m,cols].median(); sc=StandardScaler().fit(bm.loc[fit_m,cols].fillna(med).values)
X=np.clip(sc.transform(bm[cols].fillna(med).values),-5,5).astype(np.float32)
print(f'[{MODE}] AE 輸入 {len(cols)} 欄,訓練列(全部樣本 ≤2023){int(fit_m.sum())},潛在 {Z} 維', flush=True)
torch.manual_seed(42)
if MODE=='kline':
    from kline.autoencoder import train_ae
    m=train_ae(X[fit_m], len(cols), lambda s: None)
else:
    sys.path.insert(0,R+'/method_kline_v2'); from train_ae_ocsvm import train_ae as train_ae2
    dtr=np.asarray(d<='2022-12-31'); dva=np.asarray((d>'2022-12-31')&(d<='2023-12-31'))
    m=train_ae2(X[dtr], X[dva], Z, seed=42, log=lambda s: None)[0]
m.eval()
with torch.no_grad():
    rec,z=m(torch.FloatTensor(X)); err=((rec-torch.FloatTensor(X))**2).mean(1).numpy(); z=z.numpy()
ae=pd.DataFrame(z, index=bm.index, columns=[f'ae_z{i}' for i in range(Z)]); ae['ae_err']=err
x25=json.load(open(f'{R}/method_xgb/experiments/x25-tw50-h5-cs.json')); cfg=x25['config']; feats=x25['results']['full_permpos']['features']; ycol='y_cs_h5'
panel=pd.read_parquet(os.path.join(P.FEATURES,'features_tw50_2016-01-01_2026-09-11.parquet'), columns=feats+[ycol,'r_h5']).join(ae, how='left')
tr,va,te=time_split(panel,cfg['train_end'],cfg['val_end'],5,ycol)
score=panel[panel.index.get_level_values('date')>pd.Timestamp(cfg['val_end'])]; full={}
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
        if len(fc)<=5: p['colsample_bytree']=1.0
        mdl=XGBClassifier(random_state=seed,**p).fit(tr[fc],tr[ycol].values.astype(int),eval_set=[(va[fc],va[ycol].values.astype(int))],verbose=False)
        probs.append(mdl.predict_proba(te[fc])[:,1]); full.setdefault(name,[]).append(mdl.predict_proba(score[fc])[:,1])
    out[name]={}
    for yr in (2025,2026):
        mm=yrs==yr; res={}
        for rule in ('thr0.5','daily-med'):
            per=[]
            for pr in probs:
                pred=(pr[mm]>=0.5).astype(int) if rule=='thr0.5' else (pr[mm]>pd.Series(pr[mm]).groupby(np.asarray(dte[mm])).transform('median').values).astype(int)
                per.append(prf(yte[mm],pred))
            per=np.array(per); res[rule]={'mean':per.mean(0).round(2).tolist(),'std':per.std(0).round(2).tolist()}
        out[name][yr]=res; dm=res['daily-med']
        print(f"  {name:8s} {yr} 當日中位數: Acc {dm['mean'][0]:.2f}±{dm['std'][0]:.2f} F1m {dm['mean'][1]:.2f} P {dm['mean'][2]:.2f} R {dm['mean'][3]:.2f}", flush=True)
    print(f'  ({name}: {len(fc)} 欄, {time.time()-t0:.0f}s)', flush=True)
pd.DataFrame({('p_'+n.replace('+','')): np.mean(v,axis=0).astype('float32') for n,v in full.items()}, index=score.index).to_parquet(f'{R}/backtest/results/fullpred_x25-tw50-h5-cs_aeorig_{MODE}.parquet')
json.dump({'mode':MODE,'ae_input_cols':len(cols),'z':Z,'ae_train_rows':int(fit_m.sum()),'results':out}, open(f'{R}/method_xgb/experiments/x25-tw50-h5-cs_aeorig_{MODE}.json','w'), indent=1); print('[DONE]')
