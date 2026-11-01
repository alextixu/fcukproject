# 主軸測試報告(自動產生)

結果:16 / 16 通過

| # | 層級 | 測試 | 情境(Given / When / Then) | 結果 |
|---|---|---|---|---|
| 1 | Component | `test_component_split_base_meta` | Given 2024 的訓練期(2020–2023) / When 切成基底層 A 與元學習器 B / Then A 只有 2020–2022、B 只有 2023; A 的每一筆標籤(該股自己的 t+5)都早於 2023 年第一天,所以元學習器看到的分數來自基底層沒看過的資料 | 通過 |
| 2 | Component | `test_component_meta_learner_three_classes` | [lr] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現,分數是 0 ~ 1 的機率(沒有機率的 SVM 為 0) | 通過 |
| 3 | Component | `test_component_meta_learner_three_classes` | [lr-l1] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現,分數是 0 ~ 1 的機率(沒有機率的 SVM 為 0) | 通過 |
| 4 | Component | `test_component_meta_learner_three_classes` | [lr-enet] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現,分數是 0 ~ 1 的機率(沒有機率的 SVM 為 0) | 通過 |
| 5 | Component | `test_component_meta_learner_three_classes` | [lr-poly2] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現,分數是 0 ~ 1 的機率(沒有機率的 SVM 為 0) | 通過 |
| 6 | Component | `test_component_meta_learner_three_classes` | [lr-poly3] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現,分數是 0 ~ 1 的機率(沒有機率的 SVM 為 0) | 通過 |
| 7 | Component | `test_component_meta_learner_three_classes` | [tree] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現,分數是 0 ~ 1 的機率(沒有機率的 SVM 為 0) | 通過 |
| 8 | Component | `test_component_meta_learner_three_classes` | [hgb] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現,分數是 0 ~ 1 的機率(沒有機率的 SVM 為 0) | 通過 |
| 9 | Component | `test_component_meta_learner_three_classes` | [svm] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現,分數是 0 ~ 1 的機率(沒有機率的 SVM 為 0) | 通過 |
| 10 | System | `test_system_refactor_matches_before` | [score|lr] Given 重構後的基底層與元學習器(種子 42) / When 重跑舊的輸入 × 元學習器組合 / Then 測試 2024 的 macro-F1 和重構前完全相同 | 通過 |
| 11 | System | `test_system_refactor_matches_before` | [score+recon|lr] Given 重構後的基底層與元學習器(種子 42) / When 重跑舊的輸入 × 元學習器組合 / Then 測試 2024 的 macro-F1 和重構前完全相同 | 通過 |
| 12 | System | `test_system_refactor_matches_before` | [score+pos|lr] Given 重構後的基底層與元學習器(種子 42) / When 重跑舊的輸入 × 元學習器組合 / Then 測試 2024 的 macro-F1 和重構前完全相同 | 通過 |
| 13 | System | `test_system_refactor_matches_before` | [score|hgb] Given 重構後的基底層與元學習器(種子 42) / When 重跑舊的輸入 × 元學習器組合 / Then 測試 2024 的 macro-F1 和重構前完全相同 | 通過 |
| 14 | System | `test_system_refactor_matches_before` | [score|svm] Given 重構後的基底層與元學習器(種子 42) / When 重跑舊的輸入 × 元學習器組合 / Then 測試 2024 的 macro-F1 和重構前完全相同 | 通過 |
| 15 | System | `test_system_refactor_matches_before` | [score|tree] Given 重構後的基底層與元學習器(種子 42) / When 重跑舊的輸入 × 元學習器組合 / Then 測試 2024 的 macro-F1 和重構前完全相同 | 通過 |
| 16 | System | `test_system_source_equals_experiment` | Given StackingSource(邏輯迴歸、只用分數) / When 走 SignalSource 介面訓練 2020–2023、預測 2024 / Then 每一天的判斷和實驗流程(基底層 + 元學習器)完全相同,所以逐年回測可以直接用它 | 通過 |
