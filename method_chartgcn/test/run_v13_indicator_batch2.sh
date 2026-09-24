#!/usr/bin/env bash
# v1.3 第二批: 指標週期 30、60 天 (第一批是 140 / 5 / 10 / 20)。其餘設定同第一批。
# 用法: bash test/run_v13_indicator_batch2.sh [seed]
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
SEED="${1:-42}"
PY=../.venv/bin/python
COMMON="--tickers tw50 --raw-features --batch-mode date --val-split time \
  --window 140 --m-pips 80 --N 10 --g 4 --seed $SEED --workers 8 \
  --out-dir experiments_v1 --md-file 實驗記錄_v1.md"
for N in 30 60; do
  echo "=== indicator_n=$N seed=$SEED $(date '+%H:%M:%S')"
  $PY -u test/run_paper_repro.py $COMMON --indicator-n $N --tag "v13-in$N-s$SEED" \
      > "logs/v13_in${N}_s${SEED}.log" 2>&1
done
echo "=== done $(date '+%H:%M:%S')"
