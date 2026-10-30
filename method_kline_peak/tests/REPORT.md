# 主軸測試報告(自動產生)

結果:42 / 42 通過

| # | 層級 | 測試 | 情境(Given / When / Then) | 結果 |
|---|---|---|---|---|
| 1 | Module | `test_module_source_contract_schema` | [主軸] Given 任一訊號來源(主軸 / 規則)用 2020–2023 訓練好 / When 預測 2024 / Then 回傳 date、ticker、pred、score 四欄, 一列對一個測試股票日、順序和輸入相同,pred 只會是低點 / 非極值 / 高點,score 是有限數字 | 通過 |
| 2 | Module | `test_module_source_contract_structure` | [主軸] Given 任一訊號來源 / When 預測 2024 / Then 判低點的一定是低點候選、判高點的一定是高點候選(高低點不會判反) | 通過 |
| 3 | Module | `test_module_source_contract_ignores_labels` | [主軸] Given 任一訊號來源 / When 測試資料的標籤被打亂 / Then 預測完全不變(預測不會偷看答案) | 通過 |
| 4 | Module | `test_module_source_contract_schema` | [規則] Given 任一訊號來源(主軸 / 規則)用 2020–2023 訓練好 / When 預測 2024 / Then 回傳 date、ticker、pred、score 四欄, 一列對一個測試股票日、順序和輸入相同,pred 只會是低點 / 非極值 / 高點,score 是有限數字 | 通過 |
| 5 | Module | `test_module_source_contract_structure` | [規則] Given 任一訊號來源 / When 預測 2024 / Then 判低點的一定是低點候選、判高點的一定是高點候選(高低點不會判反) | 通過 |
| 6 | Module | `test_module_source_contract_ignores_labels` | [規則] Given 任一訊號來源 / When 測試資料的標籤被打亂 / Then 預測完全不變(預測不會偷看答案) | 通過 |
| 7 | Module | `test_module_year_split_no_leak` | [2020] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 8 | Module | `test_module_year_split_no_leak` | [2021] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 9 | Module | `test_module_year_split_no_leak` | [2022] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 10 | Module | `test_module_year_split_no_leak` | [2023] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 11 | Module | `test_module_year_split_no_leak` | [2024] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 12 | Module | `test_module_year_split_no_leak` | [2025] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 13 | Module | `test_module_year_split_no_leak` | [2026] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 14 | Module | `test_module_engine_buy_t1_open_sell_t5_close` | Given 100 萬、A 股第 0 天收盤出現低點訊號,第 1 天開盤 100、第 5 天收盤 110 / When 回測 / Then 第 1 天開盤用總資產 1/10 買進,第 5 天收盤賣出;報酬 = 110 / 100 × 扣成本(0.585%)− 1,現金帳一致 | 通過 |
| 15 | Module | `test_module_engine_limit_up_skip` | Given 第 0 天收盤 100 出現訊號,第 1 天開盤 110(≥ 漲停 109.5) / When 回測 / Then 買不到,放棄,沒有交易 | 通過 |
| 16 | Module | `test_module_engine_no_add_when_held` | Given A 股第 0 天與第 1 天都出現訊號 / When 回測 / Then 只買一次(持有中不加碼) | 通過 |
| 17 | Module | `test_module_engine_slots_take_highest_score` | Given 只有 2 個空位、同一天 3 檔出現訊號,分數 0.1 / 0.9 / 0.5 / When 回測 / Then 買分數最高的 2 檔(B、C) | 通過 |
| 18 | Module | `test_module_engine_year_end_force_close` | Given 回測期間只到第 3 天,第 0 天出現訊號 / When 回測 / Then 第 1 天買進,第 3 天(期末)收盤強制結清,期末沒有持股 | 通過 |
| 19 | Module | `test_module_engine_signal_on_last_day_not_traded` | Given 期末最後一天出現訊號(t+1 已在期間之外) / When 回測 / Then 不交易 | 通過 |
| 20 | Module | `test_module_engine_too_expensive_skip` | Given 每格只有 10 萬,股價 20 萬 / When 出現訊號 / Then 錢不夠買一股,放棄 | 通過 |
| 21 | System | `test_system_interface_reproduces_mainline` | Given 介面版的主軸(MainlineSource,種子 42) / When 用 2020–2023 訓練、預測 2024 / Then 每一天的判斷都和原本測過的主軸相同 | 通過 |
| 22 | System | `test_system_backtest_2024_bookkeeping` | Given 2024 主軸的低點訊號與 50 檔價格 / When 跑全年回測 / Then 每筆都是 t+1 開盤買、最多持有到 t+5、 同時持有不超過 10 檔、年底沒有持股、期末資產 = 100 萬 + 每筆損益加總、資產從不為負 | 通過 |
| 23 | Component | `test_component_label_and_rule` | [嚴格最高] Given 收盤 [10, 11, 12, 13, 14, 20, 15, 14, 13, 12, 11](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 高點,規則 = 高點候選 | 通過 |
| 24 | Component | `test_component_label_and_rule` | [與之後同價並列最高] Given 收盤 [10, 11, 12, 13, 14, 20, 15, 20, 13, 12, 11](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 高點,規則 = 高點候選 | 通過 |
| 25 | Component | `test_component_label_and_rule` | [之後被超越=假候選] Given 收盤 [10, 11, 12, 13, 14, 20, 21, 14, 13, 12, 11](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 非極值,規則 = 高點候選 | 通過 |
| 26 | Component | `test_component_label_and_rule` | [嚴格最低] Given 收盤 [20, 19, 18, 17, 16, 10, 15, 16, 17, 18, 19](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 低點,規則 = 低點候選 | 通過 |
| 27 | Component | `test_component_label_and_rule` | [之後更低=假低點候選] Given 收盤 [20, 19, 18, 17, 16, 10, 15, 9, 17, 18, 19](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 非極值,規則 = 低點候選 | 通過 |
| 28 | Component | `test_component_label_and_rule` | [盤整中間=一般日子] Given 收盤 [10, 12, 11, 13, 12, 12, 13, 11, 12, 10, 13](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 非極值,規則 = 不是候選 | 通過 |
| 29 | Component | `test_component_label_and_rule` | [11 天全部同價] Given 收盤 [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 非極值,規則 = 不是候選 | 通過 |
| 30 | Component | `test_component_label_and_rule` | [左邊 6 天同價後下跌] Given 收盤 [10, 10, 10, 10, 10, 10, 9, 8, 7, 6, 5](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 高點,規則 = 不是候選 | 通過 |
| 31 | Component | `test_component_incomplete_window_is_unlabeled` | Given 一串收盤 / When 貼標籤 / Then 前 5 天與最後 5 天(11 日窗口不完整)沒有標籤,不會進入訓練或測試 | 通過 |
| 32 | Component | `test_component_rule_never_misses_except_flat_left` | Given TW50 2016~2026 全部股票日 / When 比對規則候選與真標籤 / Then 高、低點候選互斥; 沒被規則挑到的真高(低)點,全部都是「t-5 ~ t 收盤同價」的特例 | 通過 |
| 33 | Component | `test_component_feature_columns` | Given 主軸的特徵設定(6 根 K、量 ÷ 10 日均量) / When 建立面板 / Then 剛好 29 個特徵:開高低收 × 6 天 − t 日收盤 + 量 × 6 天; 標籤、候選、股票代號與交易報酬 r5 都不在特徵裡 | 通過 |
| 34 | Component | `test_component_features_do_not_peek_future` | Given 廣達的日 K / When 把 2024-11-08 之後的開高低收量全部亂改 / Then 2024-11-08 以前每一天的 29 個特徵完全不變(不偷看未來) | 通過 |
| 35 | Component | `test_component_features_scale_invariant` | Given 廣達的日 K / When 價格全部 × 3、成交量全部 × 7 / Then 29 個特徵不變(只看形狀,不看股價高低與成交量大小) | 通過 |
| 36 | Module | `test_module_split_no_label_leak` | [測試 2024] Given 主軸切分(訓練 2020–2023;測試 2024 或 2025–26) / When 切出訓練與測試 / Then 每一檔股票、每一個訓練樣本, 它的 t+5(該股票自己的第 5 個交易日)都早於測試期第一天,而且訓練與測試的日期沒有重疊 | 通過 |
| 37 | Module | `test_module_split_no_label_leak` | [我們的切分] Given 主軸切分(訓練 2020–2023;測試 2024 或 2025–26) / When 切出訓練與測試 / Then 每一檔股票、每一個訓練樣本, 它的 t+5(該股票自己的第 5 個交易日)都早於測試期第一天,而且訓練與測試的日期沒有重疊 | 通過 |
| 38 | Module | `test_module_fit_uses_only_train_true_class` | Given 2024 切分的訓練期 / When 訓練高點、低點各一組 AE + OC-SVM / Then 標準化只用訓練期的該類候選; OC-SVM 只用訓練期候選中的真高(低)點,一筆測試資料都沒用 | 通過 |
| 39 | Module | `test_module_prediction_structure` | Given 2024 測試期的判斷 / When 對照規則候選 / Then 判高點的一定是高點候選、判低點的一定是低點候選、 不是候選的一律判非極值;所以真高點不會被判成低點,真低點也不會被判成高點 | 通過 |
| 40 | System | `test_system_reproducible` | Given 同一份資料與種子 42 / When 把高點模型從頭再訓練一次 / Then 2024 每一天的高點判斷完全一樣(結果可重現) | 通過 |
| 41 | System | `test_system_metrics_match_report` | Given 2024 測試期的判斷 / When 計算混淆矩陣與 macro-F1 / Then 混淆矩陣加總 = 12,098 天、macro-F1 與 sklearn 一致; 規則 54.20%、模型(種子 42)53.96%,與簡報和 README 的數字相同 | 通過 |
| 42 | System | `test_system_data_quality` | Given TW50 50 檔還原日 K / When 清理後檢查 / Then 沒有零量日、最高 ≥ 開收、最低 ≤ 開收; 每年「開盤 ÷ 前日收盤」中位數在 0.98 ~ 1.02(開盤和收盤用同一套還原,沒有錯位) | 通過 |
