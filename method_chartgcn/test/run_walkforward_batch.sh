#!/usr/bin/env bash
# =============================================================================
# §19.3 實驗 B:walk-forward 4 折(測試年 2021 / 2022 / 2023 / 2024)
#
# 目的:73 筆 EXP 全部是 train_end 2023-12-31 / end 2024-12-31,只有一個測試年,
#       而 2024 是台股大多頭年。原論文自己是在 2018(A 股空頭年)報告最佳結果,
#       口試委員最可能問的就是「技術型態訊號常在空頭/震盪年才顯現」。
#       本批次每折都是「訓練到該年前一年底、測試該年整年」,再把四折 pooled 起來,
#       有效樣本數約為單年的 4 倍。
#
# 折數:
#   fold2021: --train-end 2020-12-31 --end 2021-12-31
#   fold2022: --train-end 2021-12-31 --end 2022-12-31   ← 空頭年,最關鍵
#   fold2023: --train-end 2022-12-31 --end 2023-12-31
#   fold2024: --train-end 2023-12-31 --end 2024-12-31   ← 與既有 run 同期(對照)
#
# 股票池用 tw50(小、建 dscache 快);每折 3 個 seed。
# 注意:每折的 dscache key 含日期,會各自重建(第一次跑該折會比較久)。
# 用法:bash test/run_walkforward_batch.sh [tickers]      預設 tw50
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
TICKERS="${1:-tw50}"
COMMON="--tickers $TICKERS --window 140 --m-pips 80 --N 10 --g 4 \
        --epochs 30 --lr 1e-3 --stride 1 --batch-mode date --raw-features \
        --val-split time --no-backtest"

run() {
  local tag="$1"; shift
  if ls experiments_paper/*_"$tag".json >/dev/null 2>&1; then
    echo "[$(date +%H:%M:%S)] $tag 已存在,略過"; return
  fi
  echo "[$(date +%H:%M:%S)] === $tag ==="
  python -u test/run_paper_repro.py $COMMON --tag "$tag" "$@" > "logs/${tag}.log" 2>&1
  local rc=$?
  [ $rc -ne 0 ] && { echo "  失敗 rc=$rc"; tail -n 5 "logs/${tag}.log"; } \
                || grep -E "Test|acc|f1_macro" "logs/${tag}.log" | tail -3
}

for y in 2021 2022 2023 2024; do
  te=$((y - 1))
  for s in 42 43 44; do
    run "wf${y}-${TICKERS}-s${s}" --train-end "${te}-12-31" --end "${y}-12-31" --seed $s
  done
done
echo "[$(date +%H:%M:%S)] 全部完成 —— 接著跑:"
echo "  python analysis/bootstrap_any.py --exps \$(ls experiments_paper/*wf*.json | sed 's/.*_//;s/.json//' | paste -sd,) --out bootstrap_walkforward.json"
