#!/usr/bin/env bash
# v1.6: 標籤改成「未來報酬是否高於當天所有股票的中位數」(疑慮 S2)。
# 類別天生約 50/50, 基準就是 50%; 也能和 XGB 系統 (同標籤、5 日, 52~54%) 直接比。
# 其餘用目前的標準: 驗證集按時間切、關鍵點算法 minmax (預設)。
# 兩種結構 × 兩種預測天數: (視窗 140/關鍵點 80) 與 v1.4 較平衡的 (視窗 30/關鍵點 15); 1 日與 5 日。
# 用法: bash test/run_v16_cslabel_batch.sh [seed]
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
SEED="${1:-42}"
PY=../.venv/bin/python
COMMON="--tickers tw50 --raw-features --batch-mode date --val-split time --pip-mode minmax \
  --label cs --N 10 --g 4 --seed $SEED --workers 8 \
  --out-dir experiments_v1 --md-file 實驗記錄_v1.md"
RUNS=("140 80 1" "140 80 5" "30 15 1" "30 15 5")
for R in "${RUNS[@]}"; do
  set -- $R
  TAG="v16-cs-w$1-m$2-h$3-s$SEED"
  echo "=== $TAG $(date '+%H:%M:%S')"
  $PY -u test/run_paper_repro.py $COMMON --window $1 --m-pips $2 --horizon $3 \
      --tag "$TAG" > "logs/${TAG}.log" 2>&1
done
echo "=== done $(date '+%H:%M:%S')"
