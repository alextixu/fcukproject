#!/usr/bin/env bash
# v1.5: 關鍵點 (PIP) 距離算法改成和股價高低無關。
# raw = 論文原式; minmax = 視窗內價格先縮放到和時間軸同長度; vd = 垂直距離。
# 關鍵點 80 個時 140 天裡過半都入選, 算法差異會被稀釋, 所以另外用 30 個再比一次。
# 基準: m80/raw = v1.3 的 in140 那一筆 (同參數); m30/raw 在這裡補跑。
# 用法: bash test/run_v15_pipmode_batch.sh [seed]
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
SEED="${1:-42}"
PY=../.venv/bin/python
COMMON="--tickers tw50 --raw-features --batch-mode date --val-split time \
  --window 140 --N 10 --g 4 --seed $SEED --workers 8 \
  --out-dir experiments_v1 --md-file 實驗記錄_v1.md"
RUNS=("80 minmax" "80 vd" "30 raw" "30 minmax" "30 vd")
for R in "${RUNS[@]}"; do
  set -- $R
  TAG="v15-m$1-pip$2-s$SEED"
  echo "=== $TAG $(date '+%H:%M:%S')"
  $PY -u test/run_paper_repro.py $COMMON --m-pips $1 --pip-mode $2 \
      --tag "$TAG" > "logs/${TAG}.log" 2>&1
done
echo "=== done $(date '+%H:%M:%S')"
