#!/usr/bin/env bash
# v1.7: 股票池擴大。之後每個實驗都跑 tw50 和 tw300 兩個池 (使用者 09-21 指定)。
# tw300 = TW500 巢狀池的前 300 檔 (TW50 → TW100 → TW200 → 其餘按代碼; 已剔除下市與抓不到的)。
# 標準設定: 驗證集按時間切、關鍵點算法 minmax、N10/g4。
# 每個池五筆: 絕對漲跌 1 日 (w140) + 橫斷面標籤 {w140, w30} × {1 日, 5 日}。
# 用法: bash test/run_v17_pools_batch.sh "tw50 tw300" [seed]   已有結果 (同 tag 的 json) 會跳過
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
POOLS="${1:-tw50 tw300}"
SEED="${2:-42}"
PY=../.venv/bin/python
#      標籤 視窗 關鍵點 預測天數
RUNS=("abs 140 80 1" "cs 140 80 1" "cs 140 80 5" "cs 30 15 1" "cs 30 15 5")
for POOL in $POOLS; do
  for R in "${RUNS[@]}"; do
    set -- $R
    TAG="v17-$POOL-$1-w$2-m$3-h$4-s$SEED"
    if ls experiments_v1/EXP-*_"$TAG".json >/dev/null 2>&1; then echo "=== skip $TAG (已有結果)"; continue; fi
    echo "=== $TAG $(date '+%H:%M:%S')"
    $PY -u test/run_paper_repro.py --tickers $POOL --raw-features --batch-mode date \
        --val-split time --pip-mode minmax --label $1 --window $2 --m-pips $3 --horizon $4 \
        --N 10 --g 4 --seed $SEED --workers 8 \
        --out-dir experiments_v1 --md-file 實驗記錄_v1.md --tag "$TAG" > "logs/${TAG}.log" 2>&1
  done
done
echo "=== done $(date '+%H:%M:%S')"
