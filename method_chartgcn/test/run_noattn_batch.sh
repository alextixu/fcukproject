#!/usr/bin/env bash
# =============================================================================
# §19.3 實驗 A:乾淨協定(date 批次)下的 no-attention 對照
#
# 目的:§18 的十分位檢定所用的機率全部經過「跨股票 self-attention」(model.py:164-165,
#       softmax(QK^T)V,無殘差),實測 attention 近 one-hot → 同日多檔共用同一個 winner 的 V,
#       機率被抹平。因此「輸出機率不含橫斷面排序資訊」這個 null 無法歸因:
#       是子圖表示法沒訊號,還是 attention 抹平了橫斷面?
#       本批次把 use_attention 關掉、其餘設定與既有 run 完全相同,做成配對對照。
#
# 配對:
#   h=1 : sector-date-elec455 (attention, seed 42) ←→ noattn-date-elec-h1-s42/43/44
#         另補 attention seed 43/44,讓兩側都是 3 seed(回應稽核第 6 項「挑選規則未寫」)
#   h=5 : h5-elec_all-s42/43/44 (attention) ←→ noattn-date-elec-h5-s42/43/44
#
# dscache 已存在(elec_all w140m80N10g4 raw 的 h1 與 h5),不需重建。
# 用法:bash test/run_noattn_batch.sh
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
COMMON="--tickers elec_all --window 140 --m-pips 80 --N 10 --g 4 \
        --epochs 30 --lr 1e-3 --stride 1 --batch-mode date --raw-features --no-backtest"

run() {  # run <tag> <extra args...>
  local tag="$1"; shift
  if ls experiments_paper/*_"$tag".json >/dev/null 2>&1; then
    echo "[$(date +%H:%M:%S)] $tag 已存在,略過"; return
  fi
  echo "[$(date +%H:%M:%S)] === $tag ==="
  python test/run_paper_repro.py $COMMON --tag "$tag" "$@" \
      > "logs/${tag}.log" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then
    echo "[$(date +%H:%M:%S)] $tag 失敗 (rc=$rc)"; tail -n 5 "logs/${tag}.log"
  else
    grep -E "acc|f1_macro|Test" "logs/${tag}.log" | tail -3
  fi
}

# ---- h=1(val 隨機切分,與 sector-date-elec455 相同)----
for s in 42 43 44; do
  run "noattn-date-elec-h1-s$s" --seed $s --no-attention
done
# 補齊 attention 側的 seed(sector-date-elec455 只有 seed 42)
for s in 43 44; do
  run "attn-date-elec-h1-s$s" --seed $s
done

# ---- h=5(val 時間切分,與 h5-elec_all-* 相同)----
for s in 42 43 44; do
  run "noattn-date-elec-h5-s$s" --seed $s --horizon 5 --val-split time --no-attention
done

echo "[$(date +%H:%M:%S)] 全部完成"
