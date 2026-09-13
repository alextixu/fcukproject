#!/usr/bin/env bash
# =============================================================================
# §19.3 後續分析:等 no-attention 對照訓練完成後執行
#   1. 十分位重跑(含平手修正 + 退化日統計 + 零假設分佈 = 實驗 A 併 C)
#   2. 區塊 bootstrap(GCN 各 run 的 Acc / gap / F1 之 95% CI = 實驗 D 的 GCN 半邊)
# 用法:bash analysis/run_phase19.sh
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs analysis/output

# 既有(attention)+ 新增(no-attention)配對,h=1 與 h=5 兩組
# 只列出「已經訓練成功」的 tag。2026-09-05 夜 h=1 有 3 個 run 因 commit 耗盡失敗
# (noattn-h1-s43/s44、attn-h1-s43),補跑成功後再把它們加回這一行。
EXPS="sector-date-elec455,attn-date-elec-h1-s44,noattn-date-elec-h1-s42,\
h5-elec_all-s42,h5-elec_all-s43,h5-elec_all-s44,\
noattn-date-elec-h5-s42,noattn-date-elec-h5-s43,noattn-date-elec-h5-s44"

echo "[$(date +%H:%M:%S)] 1/2 十分位(平手修正 + 零假設分佈 200 次)"
python -u analysis/decile_ls.py --exps "$EXPS" --horizons 1,5,20 \
    --null-reps 200 --out decile_attn_ablation.json \
    > logs/decile_attn_ablation.log 2>&1
echo "  rc=$? → analysis/output/decile_attn_ablation.json"
tail -n 20 logs/decile_attn_ablation.log

echo "[$(date +%H:%M:%S)] 2/2 區塊 bootstrap(2000 次)"
python -u analysis/bootstrap_any.py --exps "$EXPS" --reps 2000 \
    --out bootstrap_attn_ablation.json > logs/bootstrap_attn_ablation.log 2>&1
echo "  rc=$? → analysis/output/bootstrap_attn_ablation.json"
tail -n 20 logs/bootstrap_attn_ablation.log

echo "[$(date +%H:%M:%S)] 完成"
