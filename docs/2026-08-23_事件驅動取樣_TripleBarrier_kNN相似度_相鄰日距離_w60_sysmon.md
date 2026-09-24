# 2026-08-23　事件驅動取樣 + Triple-barrier / k-NN 相似度 / 相鄰日距離 / window=60 / sysmon 監控工具

> **【2026-09-21 警告】這份文件裡的「台灣 50 / tw50」股票池不是臺灣 50 指數的成分股**,而是一份 2026-05-28 手動補齊、沒有日期與出處的 50 檔大型股名單(和任何一天的官方成分股差 7 ~ 18 檔)。**相關數字暫不可引用**;「tw50 等權」對照組用的也是同一份名單,所以「2021 ~ 2025 連續五年輸等權」等結論一併暫停使用。詳見 [2026-09-21_repo的TW50名單不是官方成分股_出處與受影響的結果](2026-09-21_repo的TW50名單不是官方成分股_出處與受影響的結果.md)。

**先回答的問題**
- 原論文輸出定義:§4.3 Eq.(11) `y = 1 if c[t+1] > c[t] else 0`,Table 3「all models predict price trend labels at the **next time step**」;§6.3 以分鐘線期貨再驗(t+1 = 下一分鐘)。論文**未對隔日視野作任何論證**;窗長只搜過 {100,120,130,140},最短 100;Fig. 1 自用 60 日序列、§2 引述型態「幾天到一兩個月」。

**做了什麼**
1. `core/events.py`:因果 ZigZag 確認(x=5%,確認日 = 決策日,無前視)+ triple-barrier(+5% / −5% / 20 日,到期以報酬正負定;不足 20 日丟棄)。
2. `core/model.py` / `core/train.py` 加 `extra_dim`(方向特徵,預設 0 行為不變)。
3. `test/event_data.py`:從 elec_all h=1 dscache 以 (ticker, 確認日) 篩事件樣本,X 逐位元不變。事件 63,431 個、間隔中位 9 日;train 736,530 → 50,395(漲 51.5%)、test 105,215 → 8,017(漲 50.53%,**floor 50.53%**,221 事件日、每日 36 檔)。
4. `test/run_event_experiment.py`:B(事件日 + 隔日)/ C(事件日 + triple-barrier)/ D(C + 方向特徵),3 seeds,內建事件日 block bootstrap。
5. `analysis/knn_similarity.py`(老師建議的相似度比對)、`analysis/adjacent_distance.py`。

**結果(02:23 暫停於 5/9,03:34–03:49 補跑完成 9/9)**
| 組 | seed 42 | seed 43 | seed 44 | 平均 ± sd | floor |
|---|---|---|---|---|---|
| B 事件日 + 隔日 | 50.35%(猜 57% 漲) | 56.74%(猜 7%) | 53.88%(猜 21%) | 53.66 ± 2.61% | 57.66% |
| C 事件日 + TB | 50.77%(猜 95%) | 50.52%(猜 13%) | 49.87%(猜 88%) | 50.39 ± 0.38% | 50.53% |
| D C + 方向特徵 | 51.27%(猜 65%) | 48.98%(猜 53%) | 50.47%(猜 76%) | 50.24 ± 0.95% | 50.53% |
- 九個 run 無一同時「高於 floor + 預測平衡」;C/D 訓練 loss 全程卡在 ln2、訓練集 Acc 50–51%,換 seed 即從全押漲翻成全押跌——沒有可學訊號。
- **k-NN**(事件樣本、k=20):鄰居標籤一致率 50.16% vs 隨機 50.02%、標籤置換 49.97 ± 0.11%;多數決 50.52% vs floor 50.53%(CI [−4.2, +1.0])。日曆樣本對照同樣 = 隨機。**「最像的歷史事件,未來與你一致的機率 = 丟銅板」**。
- 副發現:確認底部後的隔天只有 39.75% 漲(短期均值回歸,存在於標籤先驗、不在圖形)。
- 相鄰日距離:同檔隔 1 日的槽位不變距離 9.9(隨機配對 20.0),但在模型槽位排列空間裡只有 28% 機率是最近鄰——影本效應在「內容」上真實,在模型輸入空間被 importance 重排稀釋;取樣重疊造成的是有效樣本數膨脹(§12.4 的 8.1×),不是字面複本。

**結論**
- 否證鏈第 8 維「事件取樣 + 換標籤形式 + 方向特徵 ✗」(9/9 run);k-NN 相似度 = 隨機。

**window=60 實驗(否證鏈第 9 維,03:19 完成)**
- 依指示暫停事件批次,改跑 w=60 / m=30 / N=10 / g=4(等比例縮),tw50 → elec_all 各 3 seeds(`test/run_w60_batch.sh`);論文從未測過 100 以下的窗。
- tw50:53.32 / 53.85 / 54.08%(floor 54.19),猜漲 6.5 / 11.3 / 1.9%——三個全塌向全跌;elec_all:52.97 / 53.03 / 55.08%(floor 55.08),F1m 42 / 50 / 36%。平均 53.75 ± 0.32% 與 53.69 ± 0.98%,無一同時「高於 floor + 平衡」。
- 結論:窗長 60–140 天全域無訊號,**縮短窗格 ✗**;w60 elec_all 用 4 workers 建構只要 5 分鐘(w140 單 worker 41 分鐘)。記於實驗記錄 §十四。

**w60 + 週視野(§十五,同日深夜,否證鏈第 10 維)**
- 使用者假說「會漲就是會漲,週視野濾掉日內雜訊」:輸入不變(60 根日 K、每日取樣),標籤改 close[t+5](自 w60 快取衍生,X 逐位元相同);時間切分 val + 5 日 embargo;本批起訓練限 12 執行緒。
- tw50:49.27(全跌)/ 47.33(平衡)/ 50.84%(全漲 = floor),平均 49.15 ± 1.44(floor 50.84);elec_all:49.01 / 50.60 / 47.40%,平均 49.00 ± 1.31(floor 51.62)。elec_all s44 首跑因系統 RAM 吃滿而 MemoryError,重跑成功。
- 六 run 無一過 floor;窗長 {60,140} × 視野 {1,5} 四格全 ✗。

**系統監控工具(同日,`專題進度/sysmon/`)**
- 因實驗把 CPU 推到 95–97°C,建立 sysmon:命令列版 `sysmon.py`(status / watch / temps / fans / set / auto / mode / curve)與深色儀表板 GUI `sysmon_gui.py`(背景執行緒收集、溫度色條、風扇滑桿、功耗與電費估算、執行中程式);以 LibreHardwareMonitor 函式庫(nuget 自動下載相依)+ PawnIO 驅動讀 CPU / 主機板,nvidia-smi 讀 GPU。
- 發現:ASUS Z790-I 的 Q-Fan 會蓋回軟體寫入的風扇設定(Fan #3/#6 設 100% 後 RPM 與讀回值不變),主機板風扇需在 BIOS 調;CPU 散熱風扇已 100%,降溫要靠限制訓練執行緒數或 BIOS 功耗上限。

**產出**
- `core/events.py`、`test/event_data.py`、`test/run_event_experiment.py`、`test/run_event_batch.sh`、`test/run_w60_batch.sh`、`analysis/knn_similarity.py`、`analysis/adjacent_distance.py`、`analysis/summarize_events.py`、`analysis/output/knn_similarity.json`、`analysis/output/adjacent_distance.json`、`EXP-20260823-ev*`、`實驗記錄_論文對齊.md` §十三。
