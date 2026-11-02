# 主軸測試報告(自動產生)

結果:86 / 87 通過,1 項刻意跳過(條件不適用)

| # | 層級 | 測試 | 情境(Given / When / Then) | 結果 |
|---|---|---|---|---|
| 1 | Module | `test_module_source_contract_schema` | [主軸] Given 任一訊號來源(主軸 / 規則 / Stacking)用 2020–2023 訓練好 / When 預測 2024 / Then 回傳 date、ticker、pred、score 四欄, 一列對一個測試股票日、順序和輸入相同,pred 只會是低點 / 非極值 / 高點,score 是有限數字 | 通過 |
| 2 | Module | `test_module_source_contract_structure` | [主軸] Given 任一訊號來源 / When 預測 2024 / Then 有規則把關的來源(gated:主軸、規則),判低點的一定是低點候選、 判高點的一定是高點候選;拿掉規則的 Stacking 不保證這點,跳過 | 通過 |
| 3 | Module | `test_module_source_contract_ignores_labels` | [主軸] Given 任一訊號來源 / When 測試資料的標籤被打亂 / Then 預測完全不變(預測不會偷看答案) | 通過 |
| 4 | Module | `test_module_source_contract_schema` | [規則] Given 任一訊號來源(主軸 / 規則 / Stacking)用 2020–2023 訓練好 / When 預測 2024 / Then 回傳 date、ticker、pred、score 四欄, 一列對一個測試股票日、順序和輸入相同,pred 只會是低點 / 非極值 / 高點,score 是有限數字 | 通過 |
| 5 | Module | `test_module_source_contract_structure` | [規則] Given 任一訊號來源 / When 預測 2024 / Then 有規則把關的來源(gated:主軸、規則),判低點的一定是低點候選、 判高點的一定是高點候選;拿掉規則的 Stacking 不保證這點,跳過 | 通過 |
| 6 | Module | `test_module_source_contract_ignores_labels` | [規則] Given 任一訊號來源 / When 測試資料的標籤被打亂 / Then 預測完全不變(預測不會偷看答案) | 通過 |
| 7 | Module | `test_module_source_contract_schema` | [Stacking] Given 任一訊號來源(主軸 / 規則 / Stacking)用 2020–2023 訓練好 / When 預測 2024 / Then 回傳 date、ticker、pred、score 四欄, 一列對一個測試股票日、順序和輸入相同,pred 只會是低點 / 非極值 / 高點,score 是有限數字 | 通過 |
| 8 | Module | `test_module_source_contract_structure` | [Stacking] Given 任一訊號來源 / When 預測 2024 / Then 有規則把關的來源(gated:主軸、規則),判低點的一定是低點候選、 判高點的一定是高點候選;拿掉規則的 Stacking 不保證這點,跳過 | 跳過 |
| 9 | Module | `test_module_source_contract_ignores_labels` | [Stacking] Given 任一訊號來源 / When 測試資料的標籤被打亂 / Then 預測完全不變(預測不會偷看答案) | 通過 |
| 10 | Module | `test_module_year_split_no_leak` | [2020] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 11 | Module | `test_module_year_split_no_leak` | [2021] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 12 | Module | `test_module_year_split_no_leak` | [2022] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 13 | Module | `test_module_year_split_no_leak` | [2023] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 14 | Module | `test_module_year_split_no_leak` | [2024] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 15 | Module | `test_module_year_split_no_leak` | [2025] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 16 | Module | `test_module_year_split_no_leak` | [2026] Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y; 每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天 | 通過 |
| 17 | Module | `test_module_engine_buy_t1_open_sell_t5_close` | Given 100 萬、A 股第 0 天收盤出現低點訊號,第 1 天開盤 100、第 5 天收盤 110 / When 回測 / Then 第 1 天開盤用總資產 1/10 買進,第 5 天收盤賣出;報酬 = 110 / 100 × 扣成本(0.585%)− 1,現金帳一致 | 通過 |
| 18 | Module | `test_module_engine_limit_up_still_buys` | Given 第 0 天收盤 100 出現訊號,第 1 天開盤 110(漲停價) / When 回測 / Then 照樣在第 1 天開盤用 110 買進(已取消「漲停買不到」),第 5 天收盤賣出 | 通過 |
| 19 | Module | `test_module_engine_no_add_when_held` | Given A 股第 0 天與第 1 天都出現訊號 / When 回測 / Then 只買一次(持有中不加碼) | 通過 |
| 20 | Module | `test_module_engine_slots_take_highest_score` | Given 只有 2 個空位、同一天 3 檔出現訊號,分數 0.1 / 0.9 / 0.5 / When 回測 / Then 買分數最高的 2 檔(B、C) | 通過 |
| 21 | Module | `test_module_engine_year_end_force_close` | Given 回測期間只到第 3 天,第 0 天出現訊號 / When 回測 / Then 第 1 天買進,第 3 天(期末)收盤強制結清,期末沒有持股 | 通過 |
| 22 | Module | `test_module_engine_signal_on_last_day_not_traded` | Given 期末最後一天出現訊號(t+1 已在期間之外) / When 回測 / Then 不交易 | 通過 |
| 23 | Module | `test_module_engine_too_expensive_skip` | Given 每格只有 10 萬,股價 20 萬 / When 出現訊號 / Then 錢不夠買一股,放棄 | 通過 |
| 24 | Module | `test_module_engine_exit_on_high_next_open` | Given A 股第 0 天判低點、第 3 天判高點,開盤價每天 100、101、…  / When 用「判高點才賣、沒有最長持有」回測 / Then 第 1 天開盤(101)買,第 4 天開盤(104)賣,出場方式是高點出場,報酬 = 104 / 101 × 扣成本 − 1 | 通過 |
| 25 | Module | `test_module_engine_no_high_holds_to_year_end` | Given 買進後一直沒有判高點 / When 用「判高點才賣、沒有最長持有」回測 / Then 持有到期末最後一天收盤才賣(出場方式 = 期末), 不會在第 5 天賣 | 通過 |
| 26 | Module | `test_module_engine_high_before_entry_ignored` | Given A 股第 0 天判高點、第 1 天判低點(第 2 天開盤才買進) / When 回測 / Then 買進前的高點訊號不會讓它賣掉,持有到期末 | 通過 |
| 27 | Module | `test_module_engine_sells_ignored_by_default` | Given 預設規則(持有 5 天、不看高點)但傳入高點訊號 / When 回測 / Then 結果和沒傳高點訊號完全相同 | 通過 |
| 28 | Module | `test_module_engine_short_t1_open_cover_t5_close` | Given 做多 3 格 + 做空 3 格、A 股第 0 天收盤出現高點訊號,第 1 天開盤 100、第 5 天收盤 90 / When 回測 / Then 第 1 天開盤用總資產 1/6 放空,第 5 天收盤回補;放空付賣出手續費 + 稅、回補付買進手續費,跌 10% 賺錢,現金帳一致 | 通過 |
| 29 | Module | `test_module_engine_short_loses_when_price_rises` | Given 放空後股價從 100 漲到 110 / When 回測 / Then 這筆做空虧錢(net_ret < 0),期末資產 = 100 萬 + 損益 | 通過 |
| 30 | Module | `test_module_engine_long_short_slots_separate` | Given 同一天 4 檔低點訊號(分數 4 / 3 / 2 / 1)與 4 檔高點訊號 / When 用做多 3 格 + 做空 3 格回測 / Then 做多買分數最高的 3 檔、做空放空分數最高的 3 檔,總共持有 6 檔,另外 2 檔沒有空位;每檔資金約 1/6 | 通過 |
| 31 | Module | `test_module_engine_one_position_per_stock` | Given A 股第 0 天出現低點訊號(做多中),第 1 天又出現高點訊號 / When 回測 / Then 不會同時放空 A(已持有),只有一筆做多 | 通過 |
| 32 | Module | `test_module_engine_no_short_by_default` | Given 預設規則(做空 0 格)但傳入高點訊號 / When 回測 / Then 不做空,結果和沒傳高點訊號完全相同 | 通過 |
| 33 | System | `test_system_interface_reproduces_mainline` | Given 介面版的主軸(MainlineSource,種子 42) / When 用 2020–2023 訓練、預測 2024 / Then 每一天的判斷都和原本測過的主軸相同 | 通過 |
| 34 | System | `test_system_backtest_2024_bookkeeping` | Given 2024 主軸的低點訊號與 50 檔價格 / When 跑全年回測 / Then 每筆都是 t+1 開盤買、最多持有到 t+5、 同時持有不超過 10 檔、年底沒有持股、期末資產 = 100 萬 + 每筆損益加總、資產從不為負 | 通過 |
| 35 | System | `test_system_long_short_2024_bookkeeping` | Given 2024 主軸的低點與高點訊號 / When 做多前 3 檔 + 做空前 3 檔跑全年 / Then 每筆都是 t+1 開盤進場、最多持有到 t+5, 任何一天做多 ≤ 3 檔、做空 ≤ 3 檔(總共 ≤ 6 檔),同一檔不會同時多空,期末資產 = 100 萬 + 每筆損益加總、資產從不為負 | 通過 |
| 36 | Module | `test_module_label_amp_high_hand_computed` | Given 收盤 100 → 104 慢慢漲、第 6 天 110,之後 5 天最低 104 / When 算標籤幅度 / Then 第 6 天是高點,左邊 110 / 100 − 1 = 10%、右邊 1 − 104 / 110 = 5.45%,幅度取較小的 5.45%;其他天沒有幅度 | 通過 |
| 37 | Module | `test_module_label_amp_low_hand_computed` | Given 收盤從 110 跌到第 6 天 100,之後 5 天最高 106 / When 算標籤幅度 / Then 第 6 天是低點,左邊 1 − 100 / 110 = 9.09%、右邊 106 / 100 − 1 = 6%,幅度取較小的 6% | 通過 |
| 38 | Module | `test_module_relabel_only_small_points` | Given 高點幅度 2% 與 4%、低點幅度 3%、一個非極值 / When 用 3% 門檻改訓練標籤 / Then 2% 的高點變非極值,4% 的高點和剛好 3% 的低點保留,非極值不變;門檻 0 時完全不改 | 通過 |
| 39 | Module | `test_module_amp_is_not_a_feature` | Given 主軸的資料表 / When 取特徵欄 / Then 標籤幅度、每邊對方向天數(都會用到未來 5 天)不在特徵裡,特徵仍是 29 個 | 通過 |
| 40 | Module | `test_module_label_side_high_hand_computed` | Given 收盤 100、101、100.5、101.5、102、105(第 6 天,最高)、104、104.5、103、102、101 / When 算每邊對方向的天數 / Then 前 5 天漲了 4 天(只有 101 → 100.5 是跌)、後 5 天跌了 4 天(只有 104 → 104.5 是漲);其他天沒有計數 | 通過 |
| 41 | Module | `test_module_label_side_low_flat_not_counted` | Given 收盤 110、109、109、108、107、100(第 6 天,最低)、101、101、102、103、104 / When 算每邊對方向的天數 / Then 前 5 天跌了 4 天、後 5 天漲了 4 天:平盤(109 → 109、101 → 101)不算對方向 | 通過 |
| 42 | Module | `test_module_relabel_side_filter` | Given 高點每邊對方向 3+3、2+5、5+2 天,低點 4+3 天,一個非極值 / When 用每邊至少 3 天改訓練標籤 / Then 3+3 與 4+3 保留,2+5、5+2 變非極值(任一邊不夠就刪),非極值不變 | 通過 |
| 43 | System | `test_system_train_counts_2020_2023` | Given 2024 的訓練期 2020–2023 / When 用 3% 門檻改訓練標籤 / Then 高點從 3,771 剩 1,254、低點從 3,652 剩 1,312, 其餘都變成非極值,總天數不變 | 通過 |
| 44 | System | `test_system_side_filter_counts_2020_2023` | Given 2024 的訓練期 2020–2023(完整 TW50) / When 用每邊至少 3 天改訓練標籤 / Then 高點從 3,771 剩 2,309、低點從 3,652 剩 2,264 | 通過 |
| 45 | System | `test_system_scoring_uses_original_labels` | Given 用 3% 門檻訓練 / When 預測 2024 / Then 對答案的 y 仍是原本的標籤(和 0% 時完全相同); 不看標籤的規則訊號也完全不變 | 通過 |
| 46 | Component | `test_component_label_and_rule` | [嚴格最高] Given 收盤 [10, 11, 12, 13, 14, 20, 15, 14, 13, 12, 11](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 高點,規則 = 高點候選 | 通過 |
| 47 | Component | `test_component_label_and_rule` | [與之後同價並列最高] Given 收盤 [10, 11, 12, 13, 14, 20, 15, 20, 13, 12, 11](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 高點,規則 = 高點候選 | 通過 |
| 48 | Component | `test_component_label_and_rule` | [之後被超越=假候選] Given 收盤 [10, 11, 12, 13, 14, 20, 21, 14, 13, 12, 11](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 非極值,規則 = 高點候選 | 通過 |
| 49 | Component | `test_component_label_and_rule` | [嚴格最低] Given 收盤 [20, 19, 18, 17, 16, 10, 15, 16, 17, 18, 19](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 低點,規則 = 低點候選 | 通過 |
| 50 | Component | `test_component_label_and_rule` | [之後更低=假低點候選] Given 收盤 [20, 19, 18, 17, 16, 10, 15, 9, 17, 18, 19](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 非極值,規則 = 低點候選 | 通過 |
| 51 | Component | `test_component_label_and_rule` | [盤整中間=一般日子] Given 收盤 [10, 12, 11, 13, 12, 12, 13, 11, 12, 10, 13](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 非極值,規則 = 不是候選 | 通過 |
| 52 | Component | `test_component_label_and_rule` | [11 天全部同價] Given 收盤 [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 非極值,規則 = 不是候選 | 通過 |
| 53 | Component | `test_component_label_and_rule` | [左邊 6 天同價後下跌] Given 收盤 [10, 10, 10, 10, 10, 10, 9, 8, 7, 6, 5](t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = 高點,規則 = 不是候選 | 通過 |
| 54 | Component | `test_component_incomplete_window_is_unlabeled` | Given 一串收盤 / When 貼標籤 / Then 前 5 天與最後 5 天(11 日窗口不完整)沒有標籤,不會進入訓練或測試 | 通過 |
| 55 | Component | `test_component_rule_never_misses_except_flat_left` | Given TW50 2016~2026 全部股票日 / When 比對規則候選與真標籤 / Then 高、低點候選互斥; 沒被規則挑到的真高(低)點,全部都是「t-5 ~ t 收盤同價」的特例 | 通過 |
| 56 | Component | `test_component_feature_columns` | Given 主軸的特徵設定(6 根 K、量 ÷ 10 日均量) / When 建立面板 / Then 剛好 29 個特徵:開高低收 × 6 天 − t 日收盤 + 量 × 6 天; 標籤、候選、股票代號與交易報酬 r5 都不在特徵裡 | 通過 |
| 57 | Component | `test_component_features_do_not_peek_future` | Given 廣達的日 K / When 把 2024-11-08 之後的開高低收量全部亂改 / Then 2024-11-08 以前每一天的 29 個特徵完全不變(不偷看未來) | 通過 |
| 58 | Component | `test_component_features_scale_invariant` | Given 廣達的日 K / When 價格全部 × 3、成交量全部 × 7 / Then 29 個特徵不變(只看形狀,不看股價高低與成交量大小) | 通過 |
| 59 | Module | `test_module_split_no_label_leak` | [測試 2024] Given 主軸切分(訓練 2020–2023;測試 2024 或 2025–26) / When 切出訓練與測試 / Then 每一檔股票、每一個訓練樣本, 它的 t+5(該股票自己的第 5 個交易日)都早於測試期第一天,而且訓練與測試的日期沒有重疊 | 通過 |
| 60 | Module | `test_module_split_no_label_leak` | [我們的切分] Given 主軸切分(訓練 2020–2023;測試 2024 或 2025–26) / When 切出訓練與測試 / Then 每一檔股票、每一個訓練樣本, 它的 t+5(該股票自己的第 5 個交易日)都早於測試期第一天,而且訓練與測試的日期沒有重疊 | 通過 |
| 61 | Module | `test_module_fit_uses_only_train_true_class` | Given 2024 切分的訓練期 / When 訓練高點、低點各一組 AE + OC-SVM / Then 標準化只用訓練期的該類候選; OC-SVM 只用訓練期候選中的真高(低)點,一筆測試資料都沒用 | 通過 |
| 62 | Module | `test_module_prediction_structure` | Given 2024 測試期的判斷 / When 對照規則候選 / Then 判高點的一定是高點候選、判低點的一定是低點候選、 不是候選的一律判非極值;所以真高點不會被判成低點,真低點也不會被判成高點 | 通過 |
| 63 | System | `test_system_reproducible` | Given 同一份資料與種子 42 / When 把高點模型從頭再訓練一次 / Then 2024 每一天的高點判斷完全一樣(結果可重現) | 通過 |
| 64 | System | `test_system_metrics_match_report` | Given 2024 測試期的判斷 / When 計算混淆矩陣與 macro-F1 / Then 混淆矩陣加總 = 12,098 天、macro-F1 與 sklearn 一致; 規則 54.20%、模型(種子 42)53.96%,與簡報和 README 的數字相同 | 通過 |
| 65 | System | `test_system_data_quality` | Given TW50 50 檔還原日 K / When 清理後檢查 / Then 沒有零量日、最高 ≥ 開收、最低 ≤ 開收; 每年「開盤 ÷ 前日收盤」中位數在 0.98 ~ 1.02(開盤和收盤用同一套還原,沒有錯位) | 通過 |
| 66 | Module | `test_module_pool_excludes_low_vol` | Given 完整 TW50 50 檔與使用者剔除的 16 檔 / When 讀主軸的股票池 / Then 剩 34 檔,剔除的一檔都不在,其餘都是 TW50 成分股 | 通過 |
| 67 | Module | `test_module_excluded_are_lowest_volatility` | Given 2020-01 以後每檔的每日漲跌幅(絕對值)中位數 / When 由低到高排序 / Then 剔除的 16 檔正好是最低的 16 檔(中華電 ~ 中信金) | 通過 |
| 68 | Module | `test_module_reversal_long_short_long` | Given 第 0 天判高點、第 3 天判低點、第 6 天判高點 / When 反手交易 / Then 第 1 天開盤(101)做多 → 第 4 天開盤(104)賣出並反手放空 → 第 7 天開盤(107)回補並反手做多 → 最後一天收盤(111.5)平倉; 每筆報酬照成本手算,期末資產 = 100 萬 + 損益加總 | 通過 |
| 69 | Module | `test_module_reversal_waits_for_first_high` | Given 第 0 天判低點、第 2 天判高點 / When 反手交易 / Then 第一個高點之前的低點不理會:第 3 天開盤才第一次做多,持有到期末 | 通過 |
| 70 | Module | `test_module_reversal_repeated_signals_ignored` | Given 第 0、2、4 天都判高點 / When 反手交易 / Then 做多中再判高點不加碼也不重買:只有一筆做多,第 1 天買、期末賣 | 通過 |
| 71 | Module | `test_module_reversal_no_cost_compounds` | Given 同第一個情境、成本設 0 / When 反手交易 / Then 期末資產 ≈ 100 萬 × 104/101 × (1 − 3/104) × 111.5/107(只差整數股的零頭) | 通過 |
| 72 | Component | `test_component_split_base_meta` | Given 2024 的訓練期(2020–2023) / When 切成基底層 A 與元學習器 B / Then A 只有 2020–2022、B 只有 2023; A 的每一筆標籤(該股自己的 t+5)都早於 2023 年第一天,所以元學習器看到的分數來自基底層沒看過的資料 | 通過 |
| 73 | Component | `test_component_meta_learner_three_classes` | [lr] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現;把握程度是有限數字,有機率的分類器落在 0 ~ 1 (SVM 為 0) | 通過 |
| 74 | Component | `test_component_meta_learner_three_classes` | [lr-l1] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現;把握程度是有限數字,有機率的分類器落在 0 ~ 1 (SVM 為 0) | 通過 |
| 75 | Component | `test_component_meta_learner_three_classes` | [lr-enet] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現;把握程度是有限數字,有機率的分類器落在 0 ~ 1 (SVM 為 0) | 通過 |
| 76 | Component | `test_component_meta_learner_three_classes` | [lr-poly2] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現;把握程度是有限數字,有機率的分類器落在 0 ~ 1 (SVM 為 0) | 通過 |
| 77 | Component | `test_component_meta_learner_three_classes` | [lr-poly3] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現;把握程度是有限數字,有機率的分類器落在 0 ~ 1 (SVM 為 0) | 通過 |
| 78 | Component | `test_component_meta_learner_three_classes` | [tree] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現;把握程度是有限數字,有機率的分類器落在 0 ~ 1 (SVM 為 0) | 通過 |
| 79 | Component | `test_component_meta_learner_three_classes` | [hgb] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現;把握程度是有限數字,有機率的分類器落在 0 ~ 1 (SVM 為 0) | 通過 |
| 80 | Component | `test_component_meta_learner_three_classes` | [svm] Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 / Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現;把握程度是有限數字,有機率的分類器落在 0 ~ 1 (SVM 為 0) | 通過 |
| 81 | System | `test_system_refactor_matches_before` | [score|lr] Given 重構後的基底層與元學習器(種子 42) / When 重跑舊的輸入 × 元學習器組合 / Then 測試 2024 的 macro-F1 和重構前完全相同 | 通過 |
| 82 | System | `test_system_refactor_matches_before` | [score+recon|lr] Given 重構後的基底層與元學習器(種子 42) / When 重跑舊的輸入 × 元學習器組合 / Then 測試 2024 的 macro-F1 和重構前完全相同 | 通過 |
| 83 | System | `test_system_refactor_matches_before` | [score+pos|lr] Given 重構後的基底層與元學習器(種子 42) / When 重跑舊的輸入 × 元學習器組合 / Then 測試 2024 的 macro-F1 和重構前完全相同 | 通過 |
| 84 | System | `test_system_refactor_matches_before` | [score|hgb] Given 重構後的基底層與元學習器(種子 42) / When 重跑舊的輸入 × 元學習器組合 / Then 測試 2024 的 macro-F1 和重構前完全相同 | 通過 |
| 85 | System | `test_system_refactor_matches_before` | [score|svm] Given 重構後的基底層與元學習器(種子 42) / When 重跑舊的輸入 × 元學習器組合 / Then 測試 2024 的 macro-F1 和重構前完全相同 | 通過 |
| 86 | System | `test_system_refactor_matches_before` | [score|tree] Given 重構後的基底層與元學習器(種子 42) / When 重跑舊的輸入 × 元學習器組合 / Then 測試 2024 的 macro-F1 和重構前完全相同 | 通過 |
| 87 | System | `test_system_source_equals_experiment` | Given StackingSource(邏輯迴歸、只用分數) / When 走 SignalSource 介面訓練 2020–2023、預測 2024 / Then 每一天的判斷和實驗流程(基底層 + 元學習器)完全相同,所以逐年回測可以直接用它 | 通過 |
