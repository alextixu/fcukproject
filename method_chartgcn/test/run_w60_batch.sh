#!/usr/bin/env bash
# window=60 實驗批次 (否證鏈第 9 維: 縮短窗格; 論文最短只搜到 100)
# 配置: w=60, m=30, N=10, g=4 (與 w140/m80/N10/g4 等比例), raw, date batch, 3 seeds
cd "$(dirname "$0")/.."
LOG=experiments_paper/logs
echo "[W60] start $(date)"
for s in 42 43 44; do
  python -u test/run_paper_repro.py --raw-features --batch-mode date --tickers tw50 \
    --window 60 --m-pips 30 --N 10 --g 4 --seed $s --tag w60-tw50-s$s > $LOG/w60-tw50-s$s.log 2>&1
  echo "[W60] tw50 s$s done $(date)"
done
for s in 42 43 44; do
  python -u test/run_paper_repro.py --raw-features --batch-mode date --tickers elec_all --workers 4 \
    --window 60 --m-pips 30 --N 10 --g 4 --seed $s --tag w60-elec_all-s$s > $LOG/w60-elec_all-s$s.log 2>&1
  echo "[W60] elec_all s$s done $(date)"
done
echo "[W60] all done $(date)"
