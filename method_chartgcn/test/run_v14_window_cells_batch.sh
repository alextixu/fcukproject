#!/usr/bin/env bash
# v1.4: 視窗縮到 30 天 + 減少格子數 (核心節點 N × 子圖節點 g)。
# 模型的卷積核是 (5,1) 和 (N-4,1), 所以 N 最小是 5。
# 視窗 30 天時關鍵點取 15 個 (一半), 指標週期跟著視窗 = 30 天;
# 對照組: v1.3 的 w140 / 指標 30 天 / N10 g4 (只差視窗)。
# 用法: bash test/run_v14_window_cells_batch.sh [seed]
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
SEED="${1:-42}"
PY=../.venv/bin/python
# --pip-mode raw 寫死: 這批的對照組 (v1.3 的 in30) 是用論文原式跑的, 預設值之後會改成 minmax
COMMON="--tickers tw50 --raw-features --batch-mode date --val-split time --pip-mode raw \
  --seed $SEED --workers 8 --out-dir experiments_v1 --md-file 實驗記錄_v1.md"
#      視窗 關鍵點 N  g   (格子數 = N×g)
RUNS=("140 80 5 4"    # 只減格子: 40 → 20
      "30 15 10 4"    # 只縮視窗: 格子維持 40
      "30 15 5 4"     # 縮視窗 + 格子 20
      "30 15 5 3")    # 縮視窗 + 格子 15
for R in "${RUNS[@]}"; do
  set -- $R
  TAG="v14-w$1-m$2-N$3-g$4-s$SEED"
  echo "=== $TAG $(date '+%H:%M:%S')"
  $PY -u test/run_paper_repro.py $COMMON --window $1 --m-pips $2 --N $3 --g $4 \
      --tag "$TAG" > "logs/${TAG}.log" 2>&1
done
echo "=== done $(date '+%H:%M:%S')"
