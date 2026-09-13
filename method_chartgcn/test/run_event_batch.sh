#!/usr/bin/env bash
# 事件驅動實驗批次 (實驗記錄 §十三): k-NN 相似度檢驗 + B/C/D x 3 seeds
cd "$(dirname "$0")/.."
LOG=experiments_paper/logs
echo "[BATCH] start $(date)"
python analysis/knn_similarity.py --calendar-contrast > $LOG/knn_similarity.log 2>&1
echo "[BATCH] knn done $(date)"
for s in 42 43 44; do
  python test/run_event_experiment.py --label nextday --seed $s --tag evB-nextday-s$s > $LOG/evB-s$s.log 2>&1
  echo "[BATCH] B s$s done $(date)"
  python test/run_event_experiment.py --label tb --seed $s --tag evC-tb-s$s > $LOG/evC-s$s.log 2>&1
  echo "[BATCH] C s$s done $(date)"
  python test/run_event_experiment.py --label tb --dir-feat --seed $s --tag evD-tbdir-s$s > $LOG/evD-s$s.log 2>&1
  echo "[BATCH] D s$s done $(date)"
done
echo "[BATCH] all done $(date)"
