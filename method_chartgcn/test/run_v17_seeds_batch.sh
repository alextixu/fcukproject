#!/usr/bin/env bash
# v1.7 補 seed: tw300 橫斷面標籤 w140-m80-h5 單一 seed 得 52.57%, 補 seed 確認不是運氣 (兩個池都跑)。
# 用法: bash test/run_v17_seeds_batch.sh "tw50 tw300" "43 44"   已有結果 (同 tag 的 json) 會跳過
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
POOLS="${1:-tw50 tw300}"
SEEDS="${2:-43 44}"
PY=../.venv/bin/python
for POOL in $POOLS; do
  for SEED in $SEEDS; do
    TAG="v17-$POOL-cs-w140-m80-h5-s$SEED"
    if ls experiments_v1/EXP-*_"$TAG".json >/dev/null 2>&1; then echo "=== skip $TAG (已有結果)"; continue; fi
    echo "=== $TAG $(date '+%H:%M:%S')"
    $PY -u test/run_paper_repro.py --tickers $POOL --raw-features --batch-mode date \
        --val-split time --pip-mode minmax --label cs --window 140 --m-pips 80 --horizon 5 \
        --N 10 --g 4 --seed $SEED --workers 8 \
        --out-dir experiments_v1 --md-file 實驗記錄_v1.md --tag "$TAG" > "logs/${TAG}.log" 2>&1
  done
done
echo "=== done $(date '+%H:%M:%S')"
