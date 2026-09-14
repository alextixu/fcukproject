"""元標籤法:第一層 = tw500 h20 full_permpos 3-seed 集成(當日中位數決定方向);第二層用 2024 驗證段訓練「第一層方向是否正確」。
對照組 = 信心過濾 |p - 當日中位數|。在固定出手比例下比第一層方向的 Accuracy。"""
import sys, os, json, numpy as np, pandas as pd
R=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0,R); sys.path.insert(0,R+'/method_xgb/src')
from common import paths as P
from lowmem import load_lowmem
from xgboost import XGBClassifier
S=os.path.join(R,'method_xgb','experiments')
base=json.load(open(f'{R}/method_xgb/experiments/x25-tw500-h20-cs.json')); feats=base['results']['full_permpos']['features']
va=pd.read_parquet(f'{S}/x25-tw500-h20-cs_exp_base_val.parquet'); te=pd.read_parquet(f'{S}/x25-tw500-h20-cs_exp_base_test.parquet')
panel,_=load_lowmem(os.path.join(P.FEATURES,'features_tw500_2016-01-01_2026-09-11_lowmem'), feats, None, 1)
def prep(df):
    d=df.index.get_level_values('date'); p=df[['s42','s43','s44']].mean(1).values
    med=pd.Series(p).groupby(np.asarray(d)).transform('median').values
    rank=pd.Series(p).groupby(np.asarray(d)).rank(pct=True).values
    side=(p>med).astype(int); correct=(side==df['y'].values).astype(int)
    X=panel.reindex(df.index)[feats].copy(); X['p1']=p; X['p1_dev']=p-med; X['p1_rank']=rank; X['side']=side
    return X, side, correct, np.abs(p-med), d
Xv,sv,cv,confv,dv=prep(va); Xt,st_,ct,conft,dt=prep(te)
print(f'val rows {len(Xv)} 第一層正確率 {cv.mean()*100:.2f}% | test rows {len(Xt)} 正確率 {ct.mean()*100:.2f}%', flush=True)
ud=np.array(sorted(set(dv))); cut=ud[int(len(ud)*0.8)]; mtr=np.asarray(dv<cut); mva=~mtr
res={}
for seed in (42,43,44):
    m=XGBClassifier(n_estimators=2000,learning_rate=0.03,max_depth=4,min_child_weight=100,subsample=0.8,colsample_bytree=0.5,reg_lambda=5.0,tree_method='hist',eval_metric='logloss',early_stopping_rounds=100,n_jobs=4,random_state=seed)
    m.fit(Xv[mtr],cv[mtr],eval_set=[(Xv[mva],cv[mva])],verbose=False)
    res[seed]=m.predict_proba(Xt)[:,1]; print(f'  meta s{seed} iters={m.best_iteration} val-auc-ish acc@0.5={((m.predict_proba(Xv[mva])[:,1]>=0.5)==cv[mva]).mean()*100:.2f}%', flush=True)
pm=np.mean([res[s] for s in res],axis=0)
yrs=np.asarray(dt.year); out={}
def cov_acc(score, m, cov):
    """每日各取 score 最高的 cov 比例出手,回傳這些列的第一層方向正確率、以及正例 P/R(把「出手且方向=漲」當訊號)。"""
    s=pd.Series(score[m]); r=s.groupby(np.asarray(dt[m])).rank(pct=True, ascending=False).values; act=r<=cov
    acc=ct[m][act].mean(); sig=act&(st_[m]==1); y=te['y'].values[m]
    P=y[sig].mean() if sig.sum() else 0; Rr=(y[sig]==1).sum()/(y==1).sum()
    return acc*100, P*100, Rr*100, act.mean()*100
for yr in (2025,2026):
    m=yrs==yr; out[yr]={}
    for cov in (1.0,0.5,0.3,0.2,0.1):
        a1=cov_acc(conft,m,cov); a2=cov_acc(pm,m,cov)
        out[yr][cov]={'conf':a1,'meta':a2}
        print(f'{yr} 出手 {int(cov*100):3d}% | 信心過濾 acc {a1[0]:.2f} P {a1[1]:.2f} R {a1[2]:.2f} | 元標籤 acc {a2[0]:.2f} P {a2[1]:.2f} R {a2[2]:.2f}', flush=True)
json.dump({str(k):{str(c):v for c,v in d.items()} for k,d in out.items()}, open(f'{S}/x25-tw500-h20-cs_meta_label.json','w'), indent=1); print('[DONE]')
