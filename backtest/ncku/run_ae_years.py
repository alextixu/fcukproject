"""A 系統逐年輪動回測(2021~2026,walk-forward 模型,還原價 yf_hist):對 results/fullpred_ae_years.parquet 的 p_base / p_ae 兩欄,
各跑「抱 3 檔、連 2 天掉出前 8 名才賣」的無停損版與 3×ATR+30% 版;附 0050 與 tw50 等權。用法: NCKU_SRC=yf_hist python run_ae_years.py"""
import json, os, sys
import pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0,HERE)
import run_ncku as R
from run_ncku import BuyHoldStrategy, assemble_csv, code
from run_logic import load_indicators
import run_logic2 as L2
from data_loader import TICKER_SETS
RES=os.path.join(HERE,'..','results'); OUT=os.path.join(HERE,'out','ae_years'); os.makedirs(OUT,exist_ok=True); SUMM=os.path.join(HERE,'out','summary_ae_years.json')
def main():
    fp=pd.read_parquet(os.path.join(RES,'fullpred_ae_years.parquet')); summ={}
    tw50=[code(t) for t in TICKER_SETS['tw50']]; avail=assemble_csv(tw50+['0050'])
    open(os.path.join(HERE,'tmp','save_data_info.yaml'),'w').write("end_date: '20261231'\nstart_date: '20200101'\n")
    uni=[c for c in tw50 if c in avail]; ind,liq,mkt=load_indicators(uni),L2.load_liquidity(uni),L2.load_market()
    for year in sorted(set(fp.index.get_level_values('date').year)):
        p=fp[fp.index.get_level_values('date').year==year]; rec={'year':year}
        w0=p['p_base'].unstack('ticker').sort_index(); dates=list(w0.index); start,end=dates[0].strftime('%Y%m%d'),dates[-1].strftime('%Y%m%d')
        R.START,R.END,L2.START,L2.END=start,end,start,end; R.OUT=OUT
        for bname,st,u in [('0050',BuyHoldStrategy(f'b0050_{year}',uni+['0050'],['0050']),uni+['0050']),('ew',BuyHoldStrategy(f'ew_{year}',uni,uni),uni)]:
            r=R.run(st,u); rec[bname]={'ret':r['total_return_pct'],'mdd':r['max_dd_pct']}
        for col in ('p_base','p_ae'):
            w=p[col].unstack('ticker').sort_index(); rk={d.strftime('%Y%m%d'):[code(t) for t in row.dropna().sort_values(ascending=False).index] for d,row in w.iterrows()}
            for sname,(stop,take) in (('v3',(None,None)),('v3+3ATR30',(('atr',3.0),0.30))):
                st=L2.Logic2(f'{col}_{sname}_{year}',uni,rk,ind,liq,mkt,L2.LIQ['vol2k'],L2.MKT['none'],8,stop,take,topk=3,maxrank=15,min_hold=0,out_days=2)
                r=L2.run_one(f'{col}_{sname}_{year}',st,uni,OUT); rec[f'{col}|{sname}']={'ret':r['net_return_pct'],'mdd':r['net_max_dd_pct'],'trips':r['n_round_trips'],'sharpe':r['net_sharpe']}
        summ[str(year)]=rec; json.dump(summ,open(SUMM,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
        print(f"{year} {start}~{end}: 等權 {rec['ew']['ret']:+6.1f}% 0050 {rec['0050']['ret']:+6.1f}% | 95欄 v3 {rec['p_base|v3']['ret']:+7.1f}% (+停損 {rec['p_base|v3+3ATR30']['ret']:+7.1f}%) | +AE v3 {rec['p_ae|v3']['ret']:+7.1f}% (+停損 {rec['p_ae|v3+3ATR30']['ret']:+7.1f}%, MDD {rec['p_ae|v3+3ATR30']['mdd']})", flush=True)
    print(f'[SAVED] {os.path.relpath(SUMM,HERE)}')
if __name__=='__main__': main()
