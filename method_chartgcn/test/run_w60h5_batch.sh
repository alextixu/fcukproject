#!/usr/bin/env bash
# §十五: w60 + 週視野 (h=5) — tw50 與 elec_all 各 3 seeds
cd "$(dirname "$0")/.."
LOG=experiments_paper/logs
export OMP_NUM_THREADS=12
echo "[W60H5] start $(date)"
for s in 42 43 44; do
  python -u test/run_paper_repro.py --raw-features --batch-mode date --tickers tw50 \
    --window 60 --m-pips 30 --N 10 --g 4 --horizon 5 --val-split time --no-backtest \
    --seed $s --tag w60h5-tw50-s$s > $LOG/w60h5-tw50-s$s.log 2>&1
  echo "[W60H5] tw50 s$s done $(date)"
done
for s in 42 43 44; do
  python -u test/run_paper_repro.py --raw-features --batch-mode date --tickers elec_all --workers 4 \
    --window 60 --m-pips 30 --N 10 --g 4 --horizon 5 --val-split time --no-backtest \
    --seed $s --tag w60h5-elec_all-s$s > $LOG/w60h5-elec_all-s$s.log 2>&1
  echo "[W60H5] elec_all s$s done $(date)"
done
echo "[W60H5] all done $(date)"
