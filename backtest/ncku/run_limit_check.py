"""漲停買不到 / 跌停賣不掉(開盤鎖死且全天未打開)開關對照:三模型 × 原規則 × 有無停損停利 × 全年 / 7 月後。用法: NCKU_SRC=official python run_limit_check.py"""
import os, sys, json
HERE=os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, HERE)
import run_ncku as R
from run_ncku import BuyHoldStrategy, assemble_csv, code
from run_logic import load_indicators
import run_logic2 as L2
from data_loader import TICKER_SETS
from run_tw50_aefeat_v3 import rankings
OUT=os.path.join(HERE,'out','limit_check'); os.makedirs(OUT, exist_ok=True); END='20260911'
codes=[code(t) for t in TICKER_SETS['tw50']]; avail=assemble_csv(codes+['0050'])
open(os.path.join(HERE,'tmp','save_data_info.yaml'),'w').write(f"end_date: '{END}'\nstart_date: '20251001'\n")
uni=[c for c in codes if c in avail]; ind,liq,mkt=load_indicators(uni),L2.load_liquidity(uni),L2.load_market()
models=[('A 95+AE','fullpred_x26-tw50-h5-cs-xf_aefull.parquet','p_ae'),('B 95 重訓','fullpred_x26-tw50-h5-cs-xf_aefull.parquet','p_base'),('C 原最好那版','tw50_h5_permpos_fullpred.parquet','p')]
for win,start in [('全年','20260102'),('7月後','20260630')]:
    R.START,R.END,L2.START,L2.END=start,END,start,END; R.OUT=OUT
    for mname,fp,pcol in models:
        rk=rankings(fp,pcol,start)
        for sname,(stop,take) in [('無停損',(None,None)),('3ATR+30%',(('atr',3.0),0.30))]:
            res={}
            for la in (False,True):
                st=L2.Logic2(f'{mname}|{win}|{sname}|{la}',uni,rk,ind,liq,mkt,L2.LIQ['vol2k'],L2.MKT['none'],8,stop,take,topk=3,maxrank=15,min_hold=0,out_days=2,limit_aware=la)
                rr=L2.run_one(f'{mname}_{win}_{sname}_{la}'.replace('%','pct').replace(' ','_'),st,uni,OUT)
                res[la]=(rr['net_return_pct'],rr['net_max_dd_pct'],rr.get('n_round_trips'),st.n_limit_skip_buy,st.n_limit_skip_sell)
            a,b=res[False],res[True]
            print(f"{win} {mname:10s} {sname:9s} | 不考慮 {a[0]:+7.1f}% (MDD {a[1]}) | 考慮鎖死 {b[0]:+7.1f}% (MDD {b[1]}) 差 {b[0]-a[0]:+6.1f} | 買不到 {b[3]} 次 賣不掉 {b[4]} 次 | 交易 {a[2]}→{b[2]}", flush=True)
