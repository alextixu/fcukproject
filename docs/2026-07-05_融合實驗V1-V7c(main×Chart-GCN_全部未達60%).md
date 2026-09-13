# 2026-07-05 ~ 07-06　兩方法融合實驗 V1 ~ V7c

**做了什麼**
- 目標:融合 main 分支(K 線型態 + AE + OC-SVM)與 Chart-GCN,把樣本外準確率推到 60%。
- 統一設計:TW50 前 30 大、2018–2024、**訓練 ≤2022 / 驗證 2023 / 測試 2024(只碰一次)**、w100/m40/N15/g5、DateGroupedBatchSampler、驗證集 macro-F1 選模;修正 C-2 ~ C-5。
- 15 個版本:V1 修正版 Chart-GCN、V2 5 日標籤、V3 特徵融合(9 指標 + 7 K 棒 = 16 維)、V4 OC-SVM 閘門、V5a 信心門檻、V5b GBDT 平面特徵、V6a 死區標籤、V6b 逐季 walk-forward、V6c GBDT+死區、V7a 逐月擴張、V7b 樣本衰減、V7c 逐月滾動 2 年。

**結果**
- **全部未達 60%;修正洩漏後沒有任何版本穩定超越多數類基準**(隔日全猜跌 54.10%、5 日全猜漲 51.75%)。
- V1 53.88% 但 macro-F1 0.368(塌縮成全猜跌);最佳 V7c 51.74% / F1 0.517,恰追平基準。
- 原版 51.49%(best_params.json)判定為「含洩漏、不可信」。

**結論**
- 準確率必須同時看 macro-F1,否則塌縮模型會被誤判有效——這條規則從此成為所有實驗的判讀基準。

**產出**
- `融合實驗報告.md`、`experiments_fusion/`(fusion_dataset / fusion_train / run_v6 / run_v7 / results*.json,不入版控)。
