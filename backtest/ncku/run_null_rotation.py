"""隨機排名零分佈:每天把 tw50 排名隨機打亂,套同一套輪動規則(抱 3 檔、連 2 天掉出前 8 名才賣)跑 N 次,看模型報酬落在哪個百分位。用法: NCKU_SRC=official python run_null_rotation.py 200"""
import os, sys, json, numpy as np, contextlib, io
HERE=os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, HERE)
import run_ncku as R
from run_ncku import assemble_csv, code
from run_logic import load_indicators
import run_logic2 as L2
from data_loader import TICKER_SETS
from run_tw50_aefeat_v3 import rankings
OUT=os.path.join(HERE,'out','null_rotation'); os.makedirs(OUT, exist_ok=True); END='20260911'; N=int(sys.argv[1]) if len(sys.argv)>1 else 200
codes=[code(t) for t in TICKER_SETS['tw50']]; avail=assemble_csv(codes+['0050'])
open(os.path.join(HERE,'tmp','save_data_info.yaml'),'w').write(f"end_date: '{END}'\nstart_date: '20251001'\n")
uni=[c for c in codes if c in avail]; ind,liq,mkt=load_indicators(uni),L2.load_liquidity(uni),L2.load_market()
start='20260102'; R.START,R.END,L2.START,L2.END=start,END,start,END; R.OUT=OUT
real=rankings('tw50_h5_permpos_fullpred.parquet','p',start); dates=sorted(real)
res={'無停損':[], '3ATR+30%':[]}
for i in range(N):
    rng=np.random.default_rng(1000+i); rk={d: list(rng.permutation(real[d])) for d in dates}
    for sname,(stop,take) in [('無停損',(None,None)),('3ATR+30%',(('atr',3.0),0.30))]:
        st=L2.Logic2(f'null{i}',uni,rk,ind,liq,mkt,L2.LIQ['vol2k'],L2.MKT['none'],8,stop,take,topk=3,maxrank=15,min_hold=0,out_days=2)
        with contextlib.redirect_stdout(io.StringIO()): rr=L2.run_one(f'null_{i}_{sname}'.replace('%','pct'),st,uni,OUT)
        res[sname].append(rr['net_return_pct'])
    if (i+1)%25==0:
        print(f'{i+1} 次: 無停損 中位 {np.median(res["無停損"]):+.1f}% | 3ATR 中位 {np.median(res["3ATR+30%"]):+.1f}%', flush=True)
json.dump(res, open(f'{OUT}/null.json','w'))
for sname,v in res.items():
    v=np.array(v); print(f'== {sname} 隨機排名 {len(v)} 次:平均 {v.mean():+.1f}% 中位 {np.median(v):+.1f}% 5% {np.percentile(v,5):+.1f}% 25% {np.percentile(v,25):+.1f}% 75% {np.percentile(v,75):+.1f}% 95% {np.percentile(v,95):+.1f}% 最大 {v.max():+.1f}% 最小 {v.min():+.1f}%')
    for lab,x in [('C 原最好那版',237.4 if sname=='無停損' else 266.4),('A 95+AE',170.8 if sname=='無停損' else 258.1),('B 95 重訓',205.7 if sname=='無停損' else 275.6)]:
        print(f'   {lab} {x:+.1f}% → 贏過隨機的比例 {(v<x).mean()*100:.1f}%(超過 {int((v>=x).sum())} 次)')
print('[DONE]')
