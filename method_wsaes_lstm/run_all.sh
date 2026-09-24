#!/usr/bin/env bash
# 步驟 8:六個指數 × 24 季 × 三種去噪。已有結果的組合會跳過。
set -uo pipefail
cd "$(dirname "$0")"
PY=../.venv/bin/python
for IDX in csi300 nifty50 hangseng nikkei225 sp500 djia; do
  for W in full causal none; do
    OUT="results/${IDX}_${W}_metrics.csv"
    if [ -f "$OUT" ] && [ "$(grep -c '' "$OUT")" -gt 100 ]; then echo "=== skip $IDX $W"; continue; fi
    echo "=== $IDX $W  $(date '+%H:%M:%S')"
    $PY src/run.py --index "$IDX" --wavelet "$W" > "results/${IDX}_${W}.log" 2>&1
  done
done
echo "=== done $(date '+%H:%M:%S')"
