# 主軸測試報告(自動產生)

結果:20 / 20 通過

| # | 層級 | 測試 | 情境(Given / When / Then) | 結果 |
|---|---|---|---|---|
| 1 | Component | `test_component_label_and_rule` | [\u56b4\u683c\u6700\u9ad8] Given t-5 ~ t+5 的 11 天收盤 / When 貼論文標籤並套規則 / Then 標籤(高點 / 低點 / 非極值)與高、低點候選符合定義: 並列也算、之後被超越是假候選、全同價是非極值;左邊 6 天同價時規則不挑(t 同時是 6 日最高與最低),所以會漏掉這種真高點 | 通過 |
| 2 | Component | `test_component_label_and_rule` | [\u8207\u4e4b\u5f8c\u540c\u50f9\u4e26\u5217\u6700\u9ad8] Given t-5 ~ t+5 的 11 天收盤 / When 貼論文標籤並套規則 / Then 標籤(高點 / 低點 / 非極值)與高、低點候選符合定義: 並列也算、之後被超越是假候選、全同價是非極值;左邊 6 天同價時規則不挑(t 同時是 6 日最高與最低),所以會漏掉這種真高點 | 通過 |
| 3 | Component | `test_component_label_and_rule` | [\u4e4b\u5f8c\u88ab\u8d85\u8d8a=\u5047\u5019\u9078] Given t-5 ~ t+5 的 11 天收盤 / When 貼論文標籤並套規則 / Then 標籤(高點 / 低點 / 非極值)與高、低點候選符合定義: 並列也算、之後被超越是假候選、全同價是非極值;左邊 6 天同價時規則不挑(t 同時是 6 日最高與最低),所以會漏掉這種真高點 | 通過 |
| 4 | Component | `test_component_label_and_rule` | [\u56b4\u683c\u6700\u4f4e] Given t-5 ~ t+5 的 11 天收盤 / When 貼論文標籤並套規則 / Then 標籤(高點 / 低點 / 非極值)與高、低點候選符合定義: 並列也算、之後被超越是假候選、全同價是非極值;左邊 6 天同價時規則不挑(t 同時是 6 日最高與最低),所以會漏掉這種真高點 | 通過 |
| 5 | Component | `test_component_label_and_rule` | [\u4e4b\u5f8c\u66f4\u4f4e=\u5047\u4f4e\u9ede\u5019\u9078] Given t-5 ~ t+5 的 11 天收盤 / When 貼論文標籤並套規則 / Then 標籤(高點 / 低點 / 非極值)與高、低點候選符合定義: 並列也算、之後被超越是假候選、全同價是非極值;左邊 6 天同價時規則不挑(t 同時是 6 日最高與最低),所以會漏掉這種真高點 | 通過 |
| 6 | Component | `test_component_label_and_rule` | [\u76e4\u6574\u4e2d\u9593=\u4e00\u822c\u65e5\u5b50] Given t-5 ~ t+5 的 11 天收盤 / When 貼論文標籤並套規則 / Then 標籤(高點 / 低點 / 非極值)與高、低點候選符合定義: 並列也算、之後被超越是假候選、全同價是非極值;左邊 6 天同價時規則不挑(t 同時是 6 日最高與最低),所以會漏掉這種真高點 | 通過 |
| 7 | Component | `test_component_label_and_rule` | [11 \u5929\u5168\u90e8\u540c\u50f9] Given t-5 ~ t+5 的 11 天收盤 / When 貼論文標籤並套規則 / Then 標籤(高點 / 低點 / 非極值)與高、低點候選符合定義: 並列也算、之後被超越是假候選、全同價是非極值;左邊 6 天同價時規則不挑(t 同時是 6 日最高與最低),所以會漏掉這種真高點 | 通過 |
| 8 | Component | `test_component_label_and_rule` | [\u5de6\u908a 6 \u5929\u540c\u50f9\u5f8c\u4e0b\u8dcc] Given t-5 ~ t+5 的 11 天收盤 / When 貼論文標籤並套規則 / Then 標籤(高點 / 低點 / 非極值)與高、低點候選符合定義: 並列也算、之後被超越是假候選、全同價是非極值;左邊 6 天同價時規則不挑(t 同時是 6 日最高與最低),所以會漏掉這種真高點 | 通過 |
| 9 | Component | `test_component_incomplete_window_is_unlabeled` | Given 一串收盤 / When 貼標籤 / Then 前 5 天與最後 5 天(11 日窗口不完整)沒有標籤,不會進入訓練或測試 | 通過 |
| 10 | Component | `test_component_rule_never_misses_except_flat_left` | Given TW50 2016~2026 全部股票日 / When 比對規則候選與真標籤 / Then 高、低點候選互斥; 沒被規則挑到的真高(低)點,全部都是「t-5 ~ t 收盤同價」的特例 | 通過 |
| 11 | Component | `test_component_feature_columns` | Given 主軸的特徵設定(6 根 K、量 ÷ 10 日均量) / When 建立面板 / Then 剛好 29 個特徵:開高低收 × 6 天 − t 日收盤 + 量 × 6 天; 標籤、候選、股票代號與交易報酬 r5 都不在特徵裡 | 通過 |
| 12 | Component | `test_component_features_do_not_peek_future` | Given 廣達的日 K / When 把 2024-11-08 之後的開高低收量全部亂改 / Then 2024-11-08 以前每一天的 29 個特徵完全不變(不偷看未來) | 通過 |
| 13 | Component | `test_component_features_scale_invariant` | Given 廣達的日 K / When 價格全部 × 3、成交量全部 × 7 / Then 29 個特徵不變(只看形狀,不看股價高低與成交量大小) | 通過 |
| 14 | Module | `test_module_split_no_label_leak` | [\u6e2c\u8a66 2024] Given 主軸切分(訓練 2020–2023;測試 2024 或 2025–26) / When 切出訓練與測試 / Then 每一檔股票、每一個訓練樣本, 它的 t+5(該股票自己的第 5 個交易日)都早於測試期第一天,而且訓練與測試的日期沒有重疊 | 通過 |
| 15 | Module | `test_module_split_no_label_leak` | [\u6211\u5011\u7684\u5207\u5206] Given 主軸切分(訓練 2020–2023;測試 2024 或 2025–26) / When 切出訓練與測試 / Then 每一檔股票、每一個訓練樣本, 它的 t+5(該股票自己的第 5 個交易日)都早於測試期第一天,而且訓練與測試的日期沒有重疊 | 通過 |
| 16 | Module | `test_module_fit_uses_only_train_true_class` | Given 2024 切分的訓練期 / When 訓練高點、低點各一組 AE + OC-SVM / Then 標準化只用訓練期的該類候選; OC-SVM 只用訓練期候選中的真高(低)點,一筆測試資料都沒用 | 通過 |
| 17 | Module | `test_module_prediction_structure` | Given 2024 測試期的判斷 / When 對照規則候選 / Then 判高點的一定是高點候選、判低點的一定是低點候選、 不是候選的一律判非極值;所以真高點不會被判成低點,真低點也不會被判成高點 | 通過 |
| 18 | System | `test_system_reproducible` | Given 同一份資料與種子 42 / When 把高點模型從頭再訓練一次 / Then 2024 每一天的高點判斷完全一樣(結果可重現) | 通過 |
| 19 | System | `test_system_metrics_match_report` | Given 2024 測試期的判斷 / When 計算混淆矩陣與 macro-F1 / Then 混淆矩陣加總 = 12,098 天、macro-F1 與 sklearn 一致; 規則 54.20%、模型(種子 42)53.96%,與簡報和 README 的數字相同 | 通過 |
| 20 | System | `test_system_data_quality` | Given TW50 50 檔還原日 K / When 清理後檢查 / Then 沒有零量日、最高 ≥ 開收、最低 ≤ 開收; 每年「開盤 ÷ 前日收盤」中位數在 0.98 ~ 1.02(開盤和收盤用同一套還原,沒有錯位) | 通過 |
