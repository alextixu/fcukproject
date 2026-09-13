#!/usr/bin/env bash
# 事件驅動實驗補跑 (§十三): D s43 + B/C/D s44 (2026-08-23 02:23 暫停後的剩餘 4 run)
cd "$(dirname "$0")/.."
LOG=experiments_paper/logs
echo "[BATCH2] start $(date)"
python -u test/run_event_experiment.py --label tb --dir-feat --seed 43 --tag evD-tbdir-s43 > $LOG/evD-s43.log 2>&1
echo "[BATCH2] D s43 done $(date)"
for s in 44; do
  python -u test/run_event_experiment.py --label nextday --seed $s --tag evB-nextday-s$s > $LOG/evB-s$s.log 2>&1
  echo "[BATCH2] B s$s done $(date)"
  python -u test/run_event_experiment.py --label tb --seed $s --tag evC-tb-s$s > $LOG/evC-s$s.log 2>&1
  echo "[BATCH2] C s$s done $(date)"
  python -u test/run_event_experiment.py --label tb --dir-feat --seed $s --tag evD-tbdir-s$s > $LOG/evD-s$s.log 2>&1
  echo "[BATCH2] D s$s done $(date)"
done
echo "[BATCH2] all done $(date)"
