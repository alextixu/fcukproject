"""A 系統(permpos 欄 + Autoencoder 17 欄 → XGBoost)逐年 walk-forward:測試年 Y 用 x{YY}-tw50-h5-cs 的切分與該年自己篩出的特徵。
AE 輸入 = 該年 full 特徵(242 欄),全樣本訓練(≤ train_end 前一年)、train_end 那年早停;標準化用 ≤ train_end。
輸出:experiments/ae_years.json(逐年指標、AE 還原誤差)、results/fullpred_ae_years.parquet(各年打分列,欄 p_base / p_ae)"""
import os, sys, json, time, numpy as np, pandas as pd, torch
R=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0,R); sys.path.insert(0,os.path.join(R,'method_xgb','src')); sys.path.insert(0,os.path.join(R,'method_kline_v2'))
from common import paths as P
from split import time_split
from train_ae_ocsvm import train_ae
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier
def prf(y,pred):
    tp=((pred==1)&(y==1)).sum(); fp=((pred==1)&(y==0)).sum(); fn=((pred==0)&(y==1)).sum(); tn=((pred==0)&(y==0)).sum()
    Pq=tp/(tp+fp) if tp+fp else 0; Rq=tp/(tp+fn) if tp+fn else 0; f1=2*Pq*Rq/(Pq+Rq) if Pq+Rq else 0; P0=tn/(tn+fn) if tn+fn else 0; R0=tn/(tn+fp) if tn+fp else 0; f0=2*P0*R0/(P0+R0) if P0+R0 else 0
    return [(tp+tn)/len(y)*100,(f1+f0)/2*100,Pq*100,Rq*100]
panel_all=pd.read_parquet(os.path.join(P.FEATURES,'features_tw50_2016-01-01_2026-09-11.parquet'))
out={}; preds=[]
for Y in range(2021,2027):
    tag=f'x{str(Y)[2:]}-tw50-h5-cs'; x=json.load(open(os.path.join(P.XGB_EXP,f'{tag}.json'))); cfg=x['config']; feats=x['results']['full_permpos']['features']; full=x['results']['full']['features']; ycol='y_cs_h5'
    TE=pd.Timestamp(cfg['train_end']); AE_VA=TE-pd.DateOffset(years=1); t0=time.time()
    d=panel_all.index.get_level_values('date'); fit_m=np.asarray(d<=TE); dtr=np.asarray(d<=AE_VA); dva=np.asarray((d>AE_VA)&(d<=TE)); ym=np.asarray(d.year==Y)
    med=panel_all.loc[fit_m,full].median(); sc=StandardScaler().fit(panel_all.loc[fit_m,full].fillna(med).values)
    X=np.clip(sc.transform(panel_all[full].fillna(med).values),-5,5).astype(np.float32)
    m=train_ae(X[dtr],X[dva],16,seed=42,log=lambda s: None)[0]; m.eval()
    with torch.no_grad(): Xt=torch.FloatTensor(X); rec,z=m(Xt); err=((rec-Xt)**2).mean(1).numpy(); z=z.numpy()
    ae=pd.DataFrame(z,index=panel_all.index,columns=[f'ae_z{i}' for i in range(16)]); ae['ae_err']=err; aec=list(ae.columns)
    panel=panel_all[feats+[ycol,'r_h5']].join(ae); tr,va,te=time_split(panel,cfg['train_end'],cfg['val_end'],5,ycol)
    te=te[te.index.get_level_values('date').year==Y]; score=panel[ym]
    rec_={'tag':tag,'train_end':cfg['train_end'],'val_end':cfg['val_end'],'n_feat':len(feats),'n_test':len(te),'ae_err_train':float(err[dtr].mean()),'ae_err_early':float(err[dva].mean()),'ae_err_test':float(err[ym].mean())}
    yte=te[ycol].values.astype(int); dte=np.asarray(te.index.get_level_values('date')); sp=score[['r_h5']].copy()
    for name,fc in (('base',feats),('ae',feats+aec)):
        per=[]; probs=[]; aucs=[]; fp_=[]
        for seed in cfg['seeds']:
            p=dict(cfg['xgb']); p.update(tree_method='hist',eval_metric='logloss')
            mdl=XGBClassifier(random_state=seed,**p).fit(tr[fc],tr[ycol].values.astype(int),eval_set=[(va[fc],va[ycol].values.astype(int))],verbose=False)
            pr=mdl.predict_proba(te[fc])[:,1]; probs.append(pr); aucs.append(roc_auc_score(yte,pr)); fp_.append(mdl.predict_proba(score[fc])[:,1])
            per.append(prf(yte,(pr>pd.Series(pr).groupby(dte).transform('median').values).astype(int)))
        per=np.array(per); pe=np.mean(probs,axis=0); g=pd.DataFrame({'p':pe,'y':yte,'d':dte}); top3=g.sort_values(['d','p'],ascending=[True,False]).groupby('d').head(3)
        rec_[name]={'acc':round(per.mean(0)[0],2),'acc_std':round(per.std(0)[0],2),'f1m':round(per.mean(0)[1],2),'auc':round(float(np.mean(aucs)),4),'top3_hit':round(float(top3.y.mean()*100),1)}
        sp[f'p_{name}']=np.mean(fp_,axis=0).astype('float32')
    preds.append(sp); out[str(Y)]=rec_
    print(f"{Y} {tag} 訓練≤{cfg['train_end'][:4]} 早停{cfg['val_end'][:4]} 特徵{len(feats)} 測試{len(te)} | AE 誤差 訓練 {rec_['ae_err_train']:.3f} 早停 {rec_['ae_err_early']:.3f} 測試年 {rec_['ae_err_test']:.3f} | 95欄 Acc {rec_['base']['acc']:.2f} AUC {rec_['base']['auc']:.4f} 前3 {rec_['base']['top3_hit']:.1f}% | +AE Acc {rec_['ae']['acc']:.2f}±{rec_['ae']['acc_std']:.2f} AUC {rec_['ae']['auc']:.4f} 前3 {rec_['ae']['top3_hit']:.1f}% ({time.time()-t0:.0f}s)", flush=True)
    json.dump(out,open(os.path.join(P.XGB_EXP,'ae_years.json'),'w'),indent=1); pd.concat(preds).to_parquet(os.path.join(P.RESULTS,'fullpred_ae_years.parquet'))
print('[DONE]')
