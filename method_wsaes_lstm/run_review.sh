#!/usr/bin/env bash
# 2026-09-22 審查後的兩組補跑。C:WLSTM 整段 / 因果去噪各補 seed 1、2(seed 0 在 run_all.sh 已跑)。D:照原文設定(SGD 學習率 0.05、5,000 回合、5 層、不早停),滬深 300、整段去噪。
set -uo pipefail
cd "$(dirname "$0")"
PY=../.venv/bin/python
echo "=== C start $(date '+%H:%M:%S')"
for IDX in csi300 nifty50 hangseng; do
  ( for S in 1 2; do for W in full causal; do
      $PY src/run.py --index "$IDX" --wavelet "$W" --models WLSTM --seed "$S" --tag "_s$S" --no-preds > "results/_C_${IDX}_${W}_s$S.log" 2>&1
    done; done; echo "=== C done $IDX $(date '+%H:%M:%S')" ) &
done
echo "=== D start $(date '+%H:%M:%S')"
$PY src/run.py --index csi300 --wavelet full --models WSAEs-LSTM,WLSTM,LSTM,RNN --optim sgd --lr 0.05 --epochs 5000 --layers 5 --no-early-stop --jobs 5 --tag _paper > results/_D_csi300_full_paper.log 2>&1
echo "=== D done $(date '+%H:%M:%S')"
wait
echo "=== review done $(date '+%H:%M:%S')"
