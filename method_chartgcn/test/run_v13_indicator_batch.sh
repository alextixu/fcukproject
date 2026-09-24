#!/usr/bin/env bash
# v1.3: 技術指標週期和視窗脫鉤, 從一週 (5 天) 開始試。
# 其餘參數固定為 v1.0 的 140/80/10/4、驗證集按時間切 (v1.1)、本地股價資料夾 (v1.2)。
# 第一筆 in140 = 論文設定 (指標週期跟著視窗), 當同條件基準。
# 用法: bash test/run_v13_indicator_batch.sh [seed]
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
SEED="${1:-42}"
PY=../.venv/bin/python
COMMON="--tickers tw50 --raw-features --batch-mode date --val-split time \
  --window 140 --m-pips 80 --N 10 --g 4 --seed $SEED --workers 8 \
  --out-dir experiments_v1 --md-file 實驗記錄_v1.md"
for N in 140 5 10 20; do
  if [ "$N" = "140" ]; then EXTRA=""; else EXTRA="--indicator-n $N"; fi
  echo "=== indicator_n=$N seed=$SEED $(date '+%H:%M:%S')"
  $PY -u test/run_paper_repro.py $COMMON $EXTRA --tag "v13-in$N-s$SEED" \
      > "logs/v13_in${N}_s${SEED}.log" 2>&1
  grep -E "Accuracy|F1 macro|acc=|\[TEST\]|test" "logs/v13_in${N}_s${SEED}.log" | tail -3
done
echo "=== done $(date '+%H:%M:%S')"
