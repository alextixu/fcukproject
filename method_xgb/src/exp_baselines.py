"""基線對照(tw50、x26 切分:訓練 ≤2024、早停/驗證 2025、測試 2026):邏輯迴歸、隨機森林、單純動量排名,對照 XGBoost 95 欄。
指標:當日中位數判方向的 Acc / F1m、AUC、每日前 3 名命中率。輸出 experiments/baselines_2026.json、results/fullpred_baselines_2026.parquet"""
import os, sys, json, numpy as np, pandas as pd
R=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0,R); sys.path.insert(0,os.path.join(R,'method_xgb','src'))
from common import paths as P
from split import time_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
x=json.load(open(os.path.join(P.XGB_EXP,'x26-tw50-h5-cs.json'))); cfg=x['config']; feats=x['results']['full_permpos']['features']; ycol='y_cs_h5'
mom=['cs_excess_roc_20','roc_20','cs_excess_roc_5','rsi_14','cs_excess_roc_60']
panel=pd.read_parquet(os.path.join(P.FEATURES,'features_tw50_2016-01-01_2026-09-11.parquet'),columns=sorted(set(feats+mom))+[ycol,'r_h5'])
tr,va,te=time_split(panel,cfg['train_end'],cfg['val_end'],5,ycol); score=panel[panel.index.get_level_values('date')>pd.Timestamp(cfg['val_end'])]
med=tr[feats].median(); sc=StandardScaler().fit(tr[feats].fillna(med).values)
Xs=lambda df: np.clip(sc.transform(df[feats].fillna(med).values),-5,5)
yte=te[ycol].values.astype(int); dte=np.asarray(te.index.get_level_values('date'))
def prf(y,pred):
    tp=((pred==1)&(y==1)).sum(); fp=((pred==1)&(y==0)).sum(); fn=((pred==0)&(y==1)).sum(); tn=((pred==0)&(y==0)).sum()
    Pq=tp/(tp+fp) if tp+fp else 0; Rq=tp/(tp+fn) if tp+fn else 0; f1=2*Pq*Rq/(Pq+Rq) if Pq+Rq else 0; P0=tn/(tn+fn) if tn+fn else 0; R0=tn/(tn+fp) if tn+fp else 0; f0=2*P0*R0/(P0+R0) if P0+R0 else 0
    return (tp+tn)/len(y)*100,(f1+f0)/2*100
def report(name,pr,pr_score):
    pred=(pr>pd.Series(pr).groupby(dte).transform('median').values).astype(int); acc,f1=prf(yte,pred)
    g=pd.DataFrame({'p':pr,'y':yte,'d':dte}); top3=g.sort_values(['d','p'],ascending=[True,False]).groupby('d').head(3)
    daily=pd.Series((pred==yte).astype(float)).groupby(dte).mean(); t=(daily.mean()-0.5)/(daily.std(ddof=1)/np.sqrt(len(daily)))
    res[name]={'acc':round(acc,2),'f1m':round(f1,2),'auc':round(float(roc_auc_score(yte,pr)),4),'top3_hit':round(float(top3.y.mean()*100),1),'daily_t':round(float(t),2)}
    sp['p_'+name]=np.asarray(pr_score,dtype='float32'); print(f"  {name:12s} Acc {acc:.2f} F1m {f1:.2f} AUC {res[name]['auc']:.4f} 前3命中 {res[name]['top3_hit']:.1f}% 每日t {t:.2f}", flush=True)
res={}; sp=score[['r_h5']].copy()
lr=LogisticRegression(C=0.1,max_iter=2000).fit(Xs(tr),tr[ycol].values.astype(int)); report('logistic',lr.predict_proba(Xs(te))[:,1],lr.predict_proba(Xs(score))[:,1])
rf=RandomForestClassifier(n_estimators=300,max_depth=8,min_samples_leaf=200,max_features=0.3,n_jobs=6,random_state=42).fit(tr[feats].fillna(med),tr[ycol].values.astype(int))
report('rf',rf.predict_proba(te[feats].fillna(med))[:,1],rf.predict_proba(score[feats].fillna(med))[:,1])
for c in mom:
    s_te=te[c].fillna(te[c].median()).values; s_sc=score[c].fillna(score[c].median()).values
    r_te=pd.Series(s_te).groupby(dte).rank(pct=True).values; r_sc=pd.Series(s_sc).groupby(np.asarray(score.index.get_level_values('date'))).rank(pct=True).values
    report('mom_'+c,r_te,r_sc)
    if c in ('cs_excess_roc_20','roc_20'): report('rev_'+c,1-r_te,1-r_sc)
json.dump(res,open(os.path.join(P.XGB_EXP,'baselines_2026.json'),'w'),indent=1); sp.to_parquet(os.path.join(P.RESULTS,'fullpred_baselines_2026.parquet')); print('[DONE]')
