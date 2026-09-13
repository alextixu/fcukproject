# -*- coding: utf-8 -*-
"""
進度整理資料夾產生器。執行: python _build_progress.py
每個條目 = 一個 markdown 檔; 有日期者以 YYYY-MM-DD_ 開頭, 無日期者以「大綱_」開頭。
最後自動產生 00_總覽.md (索引)。
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

E = {}  # filename -> content

# ───────────────────────── 無明確日期(大綱標題) ─────────────────────────

E["大綱_00_專題整體架構(兩系統_同一repo兩分支).md"] = """# 大綱 00　專題整體架構:兩套系統、同一個 repo 的兩條分支

**主題**:台股走勢預測——用技術圖形 / 型態能不能預測?

| | 系統 A | 系統 B |
|---|---|---|
| 方法 | K 線型態挖掘 + Autoencoder + One-Class SVM | Chart GCN 論文復現(PIP → Visibility Graph → 子圖 → GCN) |
| 程式 | GitHub `lintaixu/fcukproject` **main** 分支(本機 `KLINE/`) | 同 repo **Chart-GCN** 分支(本機 `K/` 第一版 → `chartgcn/` 現行版) |
| 期間 | 2026-03-12 起(專題最早提交) | 2026-05-06 起 |
| 結局 | 07-04 修正回測灌水(非重疊持倉、OOS 切分);07-13 模組化為 `kline/` 套件後停更 | 07-21 起系統性否證論文 69.26%:台股與上證 50 皆 ~50% 天花板,九個維度逐一排除 |

**旁支 / 參考**
- `microsoft/`:微軟 Qlib 平台調研與課堂報告(2026-06-17,一晚完成)。
- `tomt/`:隊友 Tom 的 Qmodel(LightGBM 多層 + GA 選特徵),外來參考專案,績效為其自我宣稱。
- `101/`:空資料夾(2026-06-11 建立),用途無法從檔案還原。
- 根目錄 `系統流程架構報告_final.pptx`(2026-07-13):兩系統流程與輸入輸出整合簡報。

**整體敘事(到 2026-08-23)**
1. 03–05 月:系統 A 從 20 種 K 線型態、三套特徵集、AE + OCSVM 一路做到回測;05-21 一度擴充 FinMind / HMM / LightGBM,05-25 全部砍回 AE + OCSVM。
2. 05–06 月:系統 B 第一版(K/)對齊論文、網格搜尋,得到 51.5% 與負超額;期末簡報。
3. 07 月:兩系統流程審查 → 發現資料洩漏 → 融合實驗 15 版全數未達 60% → 重建實驗記錄、批次洩漏 P1 → 台股與上證 50 皆無法重現論文。
4. 07 月底–08 月:加資料量、分族群、分流動性、5 日標籤、事件取樣、k-NN 相似度 → 全部 = 隨機;表示法診斷與 block bootstrap 證明最佳實驗顯著低於全押跌地板;窗長 60 實驗進行中。
"""

E["大綱_01_空資料夾101(用途不明).md"] = """# 大綱 01　`101/` 空資料夾

- 完全空白(含隱藏檔遞迴確認),無 git、無 README。
- 資料夾建立時間 2026-06-11 02:25,介於 Chart-GCN 第一版收尾(06-01)與 Qlib 調研(06-16)之間。
- 可能是曾規劃的實驗(例如台指 / 0050 相關)但未動工,或內容已搬走。若報告需交代,需靠本人記憶補充。
"""

# ───────────────────────── 有日期(系統 A:KLINE main 分支) ─────────────────────────

E["2026-03-12_K線型態系統初始提交(AE+OC-SVM+GA)_main分支.md"] = """# 2026-03-12 ~ 03-19　K 線型態預測系統初始提交(系統 A,main 分支)

**做了什麼**
- 03-12 `Initial commit: K-line pattern prediction system (AE + OC-SVM + GA)`——**整個專題最早的程式提交**。
- 03-18 / 03-19:README、20 種 K 線型態辨識、Tkinter GUI 改進、多 K 型態與高級型態。

**方法(當時)**
- yfinance 下載台灣前 50 大 OHLCV → K 線型態 → Autoencoder 壓縮 → One-Class SVM 建看漲 / 看跌模型 → 回測。

**產出**
- `KLINE/fcukproject/`(GitHub `lintaixu/fcukproject` main 分支)。
"""

E["2026-04-02_三套K線特徵集比較_歐氏距離型態搜尋_重要性權重.md"] = """# 2026-04-02 ~ 04-23　三套 K 線特徵集比較系統 + 歐氏距離型態搜尋 + 重要性權重

**做了什麼**
- 04-02:新增三套 K 線特徵集(1 日 7 特徵:上/下影線、實體、開盤缺口、收盤漲跌、5 日均量比、前五日趨勢;2 日 10 特徵;3 日 12 特徵)的 AE + OC-SVM 比較系統。
- 04-23:型態搜尋改 **歐幾里得距離**(門檻 3.0)找相似 K 線群,過濾「出現頻率 ≥ 5 且每根皆符合報酬門檻」;**重要性權重 = 出現頻率 × |平均報酬|** 作為 OC-SVM 的 sample_weight;四大評估指標;新增進度報告 PPTX。

**固定參數**
- HOLD_DAYS=5、RISE/FALL_THRESH ±5%、LATENT_DIM=4、EPOCHS=60、OCSVM RBF ν=0.1;回測扣 0.42%/筆(手續費 + 證交稅)。

**產出**
- `KLINE/fcukproject/kline_pattern_search.py`(單檔 GUI 主程式)、進度報告 PPTX。
"""

E["2026-05-21_擴充FinMind_HMM_LightGBM後於05-25清理回AE+OCSVM.md"] = """# 2026-05-21 ~ 05-25　系統 A 大擴充後全數清理

**做了什麼**
- 05-21(5 個 commit):加入 FinMind data provider、Regime HMM、LightGBM specialists、Meta-Model、投資組合優化與風險引擎。
- 05-25(5 個 commit):多分支合併後**全部砍掉**——「清理 main:僅保留 AE + OC-SVM 系統(系統B)」「僅保留主程式 kline_pattern_search.py」「移除參數搜尋功能」。

**為什麼**
- 野心過大、無法在專題時程內驗證;決定系統 A 只守 AE + OCSVM 一條線,把資源留給與論文系統(Chart-GCN)的對照。

**備註**
- 同期(05-28)Chart-GCN 分支做第一次網格搜尋。
"""

E["2026-06-17_Qlib平台研究與課堂報告(microsoft).md"] = """# 2026-06-16 ~ 06-17　微軟 Qlib 量化平台調研 + 課堂報告(一晚完成)

**做了什麼**(23:50 → 01:26)
- clone Qlib、建 venv、自寫 `run_demo.py` 跑官方流程:`Alpha158` 158 因子 → LightGBM → SignalRecord / SigAnaRecord(IC) → PortAnaRecord(TopkDropout,topk=50、n_drop=5,回測 2017-01-01 ~ 2020-08-01,CSI300 基準);`kernels=1` 避開 Windows 多進程 MemoryError。
- `build_slides.py`(python-pptx)自動產生兩份 13 頁簡報:`Qlib_專題報告.pptx`(CSI300 版)與 `Qlib_專題報告_台股.pptx`(台股版)。

**實測結果**(`demo_results.txt`)
- IC 0.0499、ICIR 0.401、Rank IC 0.0515;含成本超額年化 12.72%、資訊比率 1.446、最大回撤 −6.62%。台股版:IC 0.033、年化 +21.85%(與 0050 比較)。

**產出**
- `microsoft/run_demo.py`、`demo_results.txt`、`build_slides.py`、兩份 pptx / pdf、slide PNG。
"""

E["2026-07-07_隊友Tom的Qmodel參考專案(07-13研究簡報).md"] = """# 2026-07-07 ~ 07-13　隊友 Tom 的 Qmodel 台股量化模型(外來參考)

**這是什麼**
- 隊友專案(GitHub `TomweiLu/Qmodel`),07-07 收到 `Qmodel.zip`(499 MB),07-13 clone 最新版為 `tomt/Qmodel-latest/` 並做 `Qmodel_dev_src_研究報告.pptx`。
- 架構:yfinance 全市場 + FinMind 籌碼 → 特徵工程 → **GA 特徵選擇**(族群 20、15 代、交叉 0.8、突變 0.05、精英 2)→ 逐年 walk-forward 四層 LightGBM(States → Trend + Flow → Meta → Volatility)→ Portfolio Builder(週五收盤推論、週一開盤執行)→ 向量化回測 + Optuna。

**宣稱績效(未經獨立驗證)**
- 2021–2025 累積 653%(CAGR 50.5%)vs 0050 135%;Sharpe 4.74、最大回撤 −2.52%、Calmar 20.04。
- 注意:CAGR 50% 搭配 MaxDD −2.5% 極不尋常;文件自承曾有未還原除權息 Bug 造成虛假暴利。引用時標註「隊友專案自我宣稱」。

**對本專題的影響**
- 07-07 週進度計畫的主軸②「GA 搜特徵子集 × 超參數」即參考此設計(族群 / 代數 / 交叉 / 突變 / 精英參數一致)。

**產出**
- `tomt/Qmodel-latest/`(README、TECHNICAL_DOCUMENT.md、backtest_performance_charts.md、deploy/rolling_pipeline.py)、`Qmodel_dev_src_研究報告.pptx`。
"""

# ───────────────────────── 有日期(chartgcn 時期) ─────────────────────────

E["2026-05-06_Chart-GCN分支初始上傳.md"] = """# 2026-05-06　Chart-GCN 分支初始上傳

**做了什麼**
- 在 GitHub repo `lintaixu/fcukproject` 開 `Chart-GCN` 分支,上傳論文復現的第一版程式(commit `d071480` Initial upload on feature branch)。
- 放入原論文 PDF:Li, Wu, Jiang & Xu (2022), *Chart GCN: Learning chart information with a graph convolutional network for stock movement prediction*, Knowledge-Based Systems 248, 108842。

**為什麼**
- 專題原本只有 main 分支的「K 線型態 + AE + OC-SVM」系統;老師建議以論文方法(PIP → Visibility Graph → GCN)做第二套系統互相對照。

**產出**
- `chartgcn/`(當時為 fcukproject 的分支工作目錄)、論文 PDF。

**後續**
- 隔日(05-07)開始逐條對齊論文。
"""

E["2026-05-07_對齊論文實作_回測_DateBatch_差異文件.md"] = """# 2026-05-07　對齊論文實作 + 回測 + DateGroupedBatchSampler + 差異文件

**做了什麼**(同日 5 個 commit)
1. `9265b59` 依論文 Section 3 重寫管線:PIP(Eq.1)、VG(Eq.3)、BFS 子圖 + 正規化、Conv1(g×F)→Conv2(5×1)→Conv3→FC 84→32→Self-Attention(Eq.7-9)→2 類;加入 2024 回測。
2. `7d02948` 寫 `needchange.md`:列出實作與論文不同之處。
3. `8f054fb` 實作 **DateGroupedBatchSampler**(同一交易日的股票同一批,讓 self-attention 跨股票),並移除殘差連接。
4. `4de05da` 以真實台灣 50 資料更新回測圖。
5. `86731a8` 寫 `paper_analysis.md`:論文技術逐條清單(PIP / 9 指標 / VG / 子圖 / 模型 / 訓練 / 實驗設定)。

**為什麼**
- 先把「論文寫了什麼」和「我們做了什麼」白紙黑字對齊,之後所有差距才有辦法歸因。

**產出**
- `core/`(當時在根目錄)的 pip_algorithm / vg_graph / subgraph / indicators / model / train / dataset、`backtest.py`、`paper_analysis.md`、`needchange.md`。

**備註**
- DateGroupedBatchSampler 這天就寫了,但直到 07-24 才發現它是解決「批次 attention 洩漏未來」的關鍵,並成為標準協定。
"""

E["2026-05-13_資料品質改善與PIP視覺化.md"] = """# 2026-05-13 ~ 05-14　資料品質改善 + PIP 視覺化工具

**做了什麼**
- 05-13 `6d4ac46`:yfinance 改用除權息還原價(auto_adjust)、移除先前測試用的合成資料、PIP 初始化改為 5 點。
- 05-14 `9f25c75`:新增 `plot_pip.py`——上排畫原始收盤價 / PIP 關鍵點 / Visibility Graph,下排畫 N 個子圖各自一格;用法 `python plot_pip.py --ticker 2330.TW --m-pips 40 --window 100`。

**為什麼**
- 早期結果不穩定,先確認資料沒問題、並能「看見」管線每一步長什麼樣子。

**產出**
- `plot_pip.py`、資料載入修正。
"""

E["2026-05-28_GridSearch與模型改進(BatchNorm_ResidualAttention).md"] = """# 2026-05-28　Grid Search 最佳參數搜尋 + 模型改進

**做了什麼**(commit `dbe276e`)
- 第一次網格搜尋 window / m_pips / N / g,存成 `best_params.json`。
- 模型加 BatchNorm、Residual Attention、以 macro-F1 作為選模指標(這些是論文沒有的「改進版」,現為 `paper_exact=False` 模式)。

**結果**
- 當時最佳約 **51.5%**(隔日標籤,TW50):`best_params.json` 記 window=130 / m=80 / N=15 / g=5,test acc 0.5149、F1 macro 0.4887;回測策略 −5.82% vs 大盤 −3.87%(超額 −1.94%)。受記憶體限制只能 stride=3。
- 這一版的完整程式保留在本機 `K/fcukproject/`(`needchange.md` 列 14 項與論文差異:已修 3 項、待做 5 項——消融、baseline 對照、stride=1 等即後來 07 月補齊的工作)。05-28 凌晨 00:23 → 06:46 一次通宵衝刺完成;06-01 改進度簡報後此資料夾停更,工作轉入 `chartgcn/`。

**事後註記(07-04 / 07-24 審查)**
- 這個 51.5% 含資料洩漏:測試集被用來選參(C-2)、z-score 用到全期統計(C-3)、測試樣本窗不回溯歷史(C-4)、標籤時點錯位(C-5);07-05 融合實驗以修正後協定重跑,列為「V0* 不可信」。

**產出**
- `best_params.json`(後已清理)、model.py 改進版分支。
"""

E["2026-06-01_特徵對比實驗簡報(9維vs14維vs23維)與期末簡報.md"] = """# 2026-06-01 ~ 06-04　特徵對比實驗簡報(9 維 vs 14 維 vs 23 維)+ 期末作業簡報

**做了什麼**
- 06-01 `add_motivation_slide.py`:為期末作業簡報《利用K線型態進行預測_最終作業.pptx》加動機頁。
- 06-04 `make_comparison_ppt.py` → `特徵對比實驗.pptx`(v1 / v2 / v3):比較 PIP 節點特徵用 9 個技術指標、14 維(+K 棒)、23 維(+更多)的結果,附 Grid Search 結果。

**為什麼**
- 課程期末需要呈現;同時測試「特徵越多越好嗎」——結果沒有明顯改善,為後來「問題不在特徵數」埋下伏筆。

**產出**
- `特徵對比實驗_v3.pptx`(最終)、`make_comparison_ppt.py`、`add_motivation_slide.py`。
"""

E["2026-06-11_大盤趨勢訊號模組(trend_signal).md"] = """# 2026-06-11　大盤趨勢訊號模組

**做了什麼**
- `trend_signal.py`:以加權指數(TAIEX)判斷多頭 / 盤整 / 空頭(收盤 vs MA5 / MA10;另提供多種判斷法),輸出 +1 / 0 / −1。

**為什麼**
- 構想是把大盤狀態當成濾網或額外特徵接進兩套系統(main 與 Chart-GCN)。

**後續**
- 07-07 週計畫改以「三大法人籌碼」與「GA 搜參」為主軸,此模組未再接入主線實驗。
"""

E["2026-07-01_程式重整(core模組化).md"] = """# 2026-07-01　程式重整:核心模組移入 core/

**做了什麼**(commit `17091ab`)
- 把 pip_algorithm / vg_graph / subgraph / indicators / dataset / model / train / data_loader 移入 `core/`;執行腳本加 `sys.path` shim,統一從 repo 根目錄執行。

**為什麼**
- 準備做兩分支(main 與 Chart-GCN)的流程對照與融合,需要清楚的模組邊界。
"""

E["2026-07-04_分支流程檢查報表(main_vs_Chart-GCN).md"] = """# 2026-07-04　分支流程與輸入/輸出檢查報表

**做了什麼**
- 逐檔審查 fcukproject 的 `main` 分支(K 線型態分析系統,`kline_pattern_search.py` 892 行 Tkinter GUI:yfinance 下載 50 檔 → 型態挖掘 → AE → OC-SVM)與 `Chart-GCN` 分支的資料流與張量銜接。
- 產出 `分支流程檢查報表.md`,以 ✅ / 🟡 / 🔴 標記。

**發現**
- main 分支 4 個問題(M-1 ~ M-4)已修正並推上 GitHub(commit「修正回測與驗證方法學問題」):回測改**非重疊持倉**(進場後 5 日內忽略新訊號,避免同段行情重複計算灌水)、驗證改 out-of-sample 80/20 按日期切、`vol_ratio` 分母改均量、補 Adj Close 檢查。
- Chart-GCN 分支方法學疑慮 **C-2 ~ C-5**:測試集被用於選參、z-score 用全期統計(前視)、測試樣本窗不回溯歷史、標籤時點錯位。→ 成為 07-05 融合實驗前必須修正的清單。

**產出**
- `分支流程檢查報表.md`(07-25 加註:Chart-GCN 部分已被 07-24 全流程審查取代,保留作為 C 系列問題原始定義出處)。
"""

E["2026-07-05_融合實驗V1-V7c(main×Chart-GCN_全部未達60%).md"] = """# 2026-07-05 ~ 07-06　兩方法融合實驗 V1 ~ V7c

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
"""

E["2026-07-07_週進度計畫(7月-8月路線圖_籌碼×GA雙主軸).md"] = """# 2026-07-07　每週進度計畫(7/7 ~ 8/31,週二會議)

**做了什麼**
- 寫 `週進度計畫.md`:目標「模型出訊號的子集準確率 60%」;**雙主軸 × 雙系統**任務矩陣——主軸① 三大法人籌碼特徵、主軸② GA 搜特徵子集 × 超參數,分別在系統 A(main:K 棒 + AE + OCSVM)與系統 B(Chart-GCN)上測試。
- 排程 W1(7/7 流程檢查報告)→ W2(修方法學 + 籌碼管線)→ W3(籌碼 × Chart-GCN)→ W4(籌碼 × main)→ W5/W6(GA)→ W7(60% 攻堅、雙系統對決)→ W8(8/25 結案)。
- 附未達標備案(門檻換覆蓋、雙系統訊號交集)。

**實際走向(事後)**
- W2 起的方法學修正揭露 Chart-GCN 在乾淨協定下只有 ~50%,主線轉為「系統性否證論文宣稱」(07-21 起),籌碼與 GA 主軸未執行;同學(郭念慈)的論文走了籌碼雙分支路線,可作對照。

**產出**
- `週進度計畫.md`。
"""

E["2026-07-12_進度報告簡報_流程檢查筆記_系統流程架構報告.md"] = """# 2026-07-12 ~ 07-13　進度報告簡報 / 兩專案流程檢查筆記 / 系統流程架構報告

**做了什麼**
- 07-12:`make_ppt.py` → `progress_report.pptx`(Chart-GCN 進度報告);`兩專案流程檢查筆記.docx`;`debug_pipeline.py`(診斷「模型為何學不到」:特徵統計、特徵-標籤相關、Logistic 基線、無 attention、類別加權)。
- 07-13 凌晨:系統 A 重構——`kline_pattern_search.py` 模組化為 `kline/` 套件(config / features / data_loader / autoencoder / pattern_model / backtest / validate / gui),README 補方法學修正說明(main 分支最後一筆 commit)。
- 07-13 白天:`系統流程架構報告.pptx`(10:50 初版 → 11:51 v3 與初版內容相同 → **12:55 final 為真正改版**),放在 專題進度/ 根目錄:「股票走勢預測——兩系統流程與輸入輸出」7 頁,數值取自當日本機實跑(kline 49 檔 × 2675 天;Chart-GCN 維度銜接 (15,5,9);介面契約 18/18 通過)。同日 clone 隊友 Qmodel 並做研究簡報。
- **07-13 是一次總整理日**(專題進度/ 根目錄 mtime 即為此日)。

**為什麼**
- 週二會議(W2)呈報用;debug_pipeline 是第一次系統性懷疑「不是參數問題,是訊號問題」。

**產出**
- `progress_report.pptx`、`兩專案流程檢查筆記.docx`、`系統流程架構報告_final.pptx`(引用此版;另兩份為過程稿)、`debug_pipeline.py`、`KLINE/fcukproject/kline/`。
"""

E["2026-07-21_論文復現實驗(台股TW50)與上證50否證(chinatest).md"] = """# 2026-07-21　論文復現實驗:台股 TW50 全套 + 論文自身資料(上證 50)否證

**做了什麼**
- 新執行器 `test/run_paper_repro.py`(訓練 → 測試 → 回測 → JSON → 自動 append md)。台股 2016–2023 訓練 / 2024 測試,w140/m60/N15/g5。
- 台股 23 個 run:baseline、rawfeat、zscore、datebatch、noattn(raw / zscore)、long120、lr3e-4、gridbest s42/43/44、scale125/150/175/200、tw100、elec、fin 等(檔名 `EXP-20260721-*`)。
- **chinatest/**:用論文自己的市場(上證 50,2010–2017 訓練 / 2018 測試)跑同一管線——raw / zscore / 論文網格 32 組 / 最佳參數 3 seeds。

**結果**
- 台股 TW50 最佳 rawfeat **Acc 52.70% / F1m 50.33%**(後於 07-24 證實含批次洩漏)。
- **上證 50:50.1% ± 0.4%,論文宣稱的 69.26% 無法重現**——差距來自方法 / 論文本身,不是市場差異。

**結論**
- 否證鏈第 1 維「換市場 ✗」。

**產出**
- `experiments_paper/EXP-20260721-*.json`(18 個舊協定 run 列於實驗記錄附錄 A)、`chinatest/實驗記錄_china.md`、`chinatest/*.json`、`grid_search_paper.py`。
"""

E["2026-07-22_XGBoost同條件對照.md"] = """# 2026-07-22　XGBoost 同條件對照

**做了什麼**
- `test/run_xgb_baseline.py`:同樣本同標籤,A = 子圖張量攤平、B = 裸 9 指標,XGBoost 二分類。

**結果**
- A:Acc 54.15% / F1m 35.70%;B:53.87% / 39.44%——都塌縮成全押跌。
- 當時看似「Chart-GCN F1m 贏 XGB 10pp」,07-24 審查後加註:Chart-GCN 的數字含批次 attention 效應,公平對照須用 date 批次重測 → 重測後兩者同水準(F1m 38 vs 39)。

**結論**
- 否證鏈「模型對照 ✗」:換成樹模型也挖不出訊號。

**產出**
- `experiments_paper/XGB-20260722-031504_tw.json`。
"""

E["2026-07-24_全流程審查_批次洩漏發現_論文逐條核對_網格重掃.md"] = """# 2026-07-24　全流程審查(8 段 pipeline 獨立審查 + 對抗驗證)/ 批次洩漏 / 論文逐條核對 / 網格重掃

**做了什麼**
- 舊實驗記錄刪除重建為 `實驗記錄_論文對齊.md`(審查報告 + 全部實驗記錄)。
- 8 個審查員各審一段 pipeline,每個發現交 3 個對抗驗證者投票。

**確認的問題**
- **P1【high】測試/回測時 batch 維 self-attention 跨樣本洩漏未來**:序向切 128 筆會把「同股票的今天與明天」放同一批,明天的輸入窗含今天標籤答案。實測同一顆模型只換評估批次:序向 **52.70% → 同日一批 51.30% → 單筆 46.82%**。
- P2 預測隨 batch 組成改變;P3 PIP 距離把「天數」與「元」混進同一歐氏距離;P4 train/val 隨機切重疊滑窗樣本。
- §六 論文對齊清單(依 PDF 逐條核對):標準協定 = **date 批次 + raw 特徵**;「論文明定 vs 自行拼湊」誠實清單(批次定義、正規化、卷積通道數論文皆未明定)。

**網格重掃(GRID-20260724-2351)**
- 乾淨協定下論文 4.3 兩階段 31 組:val F1m 全在 0.47–0.53 噪音帶;名義最佳 **w140 / m80 / N10 / g4**(val 0.5345)。raw-datebatch s43 / s44 補跑。

**結論**
- 台股 ~50% 天花板結論不變、甚至更穩固;否證鏈第 2 維「掃參數 ✗」。

**產出**
- `實驗記錄_論文對齊.md` §一~§六、`EXP-20260724-*`。
"""

E["2026-07-25_第二輪偵查_文件整理_清理7.7GB.md"] = """# 2026-07-25　第二輪偵查 + 文件整理

**做了什麼**
- 審 `backtest.py`(超額報酬可信度:無交易成本、批次協定傳遞修復)、`experiments_fusion`、舊執行器(test/main.py、run_50/100stocks、run_final、grid_search_run → 移除)、工具與說明檔(實測修復)。
- 文件整理:重寫 `README.md`(專案現狀 + 權威文件指引)、`台積電_資料流程.md` 加註、`分支流程檢查報表.md` 加歷史註記;清理 7.7GB 冗餘檔(使用者核准)。
- 補跑 gridbest-date s43 / s44、scale-date-n50(規模實驗起點)。

**產出**
- `實驗記錄_論文對齊.md` §七、`README.md`、`requirements.txt`。
"""

E["2026-07-26_規模實驗50→500檔(10輪).md"] = """# 2026-07-26　規模實驗 50 → 500 檔

**做了什麼**
- 從證交所 ISIN 抓全部上市普通股建 **TW500 巢狀股票池**(554 檔,前 50 = TW50,每次 +50),每輪獨立訓練(date + raw + w140/m80/N10/g4,seed 42)。
- 同日深夜啟動全電子 450 檔實驗(EXP-20260726-232550)。

**結果**
| 檔數 | 50 | 100 | 150 | 200 | 250 | 300 | 350 | 400 | 450 | 500 |
|---|---|---|---|---|---|---|---|---|---|---|
| Acc | 54.3 | 54.8 | 55.1 | 52.2 | 55.1 | 52.0 | 55.9 | 46.2 | 56.2 | 56.1 |
| F1m | 38.4 | 47.4 | 39.9 | 43.3 | 38.0 | 43.6 | 36.1 | 45.7 | 36.0 | 35.9 |
- 訓練樣本 9 萬 → 88.5 萬(10 倍)**完全沒有改善趨勢**;F1m 在「全押跌 ~36%」與「均衡亂猜 ~47%」間震盪;回測 10 輪 9 輪輸給等權買入持有。

**結論**
- 否證鏈第 3 維「加資料量 ✗」。

**產出**
- `EXP-20260726-scale-date-n100~n500`、`725/scale_tw500_curve.png`、`實驗記錄_論文對齊.md` §八。
"""

E["2026-07-27_族群實驗_725週報與簡報_git提交.md"] = """# 2026-07-27　分族群實驗 + 7/25 週報與簡報 + git 提交

**做了什麼**
- 證交所產業別盤點電子族群 455 檔;四組實驗(date + raw + w140/m80/N10/g4):全電子 450、半導體 92、電子零組件 104、金融保險 32(對照)。
- 寫 `725/報告_本週工作.md`、`725/操作文檔.md`(任何人可重現的指令手冊)、`725/進度報告.pptx`(make_ppt_725.py;之後兩次改版只呈現檔數與族群結果)。
- git 提交本週成果(`fa32dcd`、`77f26f4`、`1469ae6`)。

**結果**
| 族群 | 檔數 | Acc | F1m | 回測超額 | 形態 |
|---|---|---|---|---|---|
| 全電子 | 450 | **51.29%** | **51.22%** | +0.4% | 均衡 ≈ 亂猜(歷來最高 F1m) |
| 半導體 | 92 | 44.85% | 38.24% | −11.6% | 反向塌縮 |
| 電子零組件 | 104 | 49.33% | 48.91% | −3.8% | 均衡亂猜 |
| 金融保險 | 32 | 54.16% | 39.09% | −18.4% | 塌縮全押跌 |
- 沒有任何一組同時「Acc 高於先驗 + 預測均衡」;同質性最高的半導體反而最差。

**結論**
- 否證鏈第 4 維「分族群 ✗」。**EXP-20260726-232550_sector-date-elec455 成為日後所有診斷的「最佳實驗」基準**(Acc 51.29%,仍低於全押跌地板 55.08%)。

**產出**
- `EXP-20260727-sector-date-*`、`725/`、`實驗記錄_論文對齊.md` §九。
"""

E["2026-08-02_流動性分層實驗.md"] = """# 2026-08-02　流動性分層實驗

**做了什麼**
- 假說:低流動性股票噪音大,拖累模型。電子股 439 檔依 **2016–2023 訓練期**日均成交金額排序(不碰測試期),取前 100 / 後 100(對照)/ 前 200;協定同前,seed 42。

**結果**
| 組 | Acc | F1m | 回測超額 | 形態 |
|---|---|---|---|---|
| 前 100(高流動) | 53.42% | 45.17% | −4.4% | 半塌縮 |
| 後 100(低流動) | 49.81% | 49.43% | −16.9% | 均衡亂猜 |
| 前 200 | 52.55% | 49.59% | −2.1% | 半均衡 |
- 分類指標無流動性效應;唯一單調的是回測「爛的程度」隨流動性遞減,但全部 ≤ 大盤。

**結論**
- 否證鏈第 5 維「分流動性 ✗」。1 日標籤路線至此窮盡 → 建議轉 5 日標籤 / 橫斷面標籤 / 非價格資訊源。

**產出**
- `EXP-20260802-liq-date-*`、`實驗記錄_論文對齊.md` §十。
"""

E["2026-08-10_資料永久快取_5日標籤實驗.md"] = """# 2026-08-10　資料層改為下載一次永久快取 + 5 日標籤實驗

**做了什麼**
1. **資料快取重寫**(`core/data_loader.py`):每檔一個 `cache/<ticker>.parquet` 主檔 + `cache/_manifest.json`(涵蓋區間、查無資料旗標),以專案根目錄定位;`test/download_data.py` 預下載全部股票池(832 檔;11 檔標記無資料,部分為 .TWO 後綴 / 下市合併 → 存活者偏誤註記)。之後所有實驗完全離線。
2. **5 日標籤**:`--horizon h`(Eq.(11) 推廣 close[t+h] > close[t]);`derive_horizon_ds` 直接從 h=1 dscache 衍生(X 逐位元相同,`analysis/verify_horizon.py` 驗證);val 改時間切分 + 5 日 embargo;tw50 與 elec_all 各 3 seeds。

**結果**
| 池 | s42 | s43 | s44 | 地板 |
|---|---|---|---|---|
| tw50 | 49.82%(近全押漲) | 49.37% | 50.83%(全押漲) | 全押漲 50.8% |
| elec_all | 50.73%(均衡) | 51.01% | 51.61%(全塌縮) | 全押跌 51.6% |
- 六輪無一同時「Acc 高於先驗 + 預測均衡」;**同組態三個 seed 分落三種形態**,單 seed 的「形態」標註只是抽樣結果。

**結論**
- 否證鏈第 7 維「拉長視野 ✗」(第 6 維為 XGB 模型對照)。

**產出**
- `cache/`、`test/download_data.py`、`EXP-20260810-h5-*`、`實驗記錄_論文對齊.md` §十一。
"""

E["2026-08-11_表示法診斷_子圖解剖_跨度統計_block_bootstrap.md"] = """# 2026-08-10 ~ 08-11　表示法診斷與統計分析(對最佳實驗 elec455 的無訓練診斷)

**做了什麼**(`analysis/`,皆可重跑)
1. **子圖解剖**(`viz_subgraphs_multi.py` → `figs/subgraph_viz.html`):2330.TW @ 2024-08-05 ±3 交易日,實算 PIP / 錨點 / 10 個子圖。
2. **跨度統計**(`span_stats.py`):200 個真實子圖的時間跨度。
3. **跨度 × 表現**(`span_vs_perf.py`):105,215 測試樣本推論 + 每筆平均跨度。
4. **Block bootstrap**(`block_bootstrap.py`):以交易日為區塊、10,000 次。

**發現**
- 解剖:Eq.(1) 端點規則使窗首日 + 決策日恆為錨點;40 個槽位只觸及 ~26 個唯一日期;**相鄰決策日錨點重疊 7–8/10,標籤卻天天翻面**(+2.78 → −5.94 → −9.75 → +7.98 …)。表示法方向盲(V 型 = 倒 V)、跨度盲。
- 跨度雙峰:52% ≤20 天、29% >60 天,最大 139 天 = 整窗;論文同機制亦未限制。
- 跨度 vs 對錯 **r = −0.0002**,四分位 Acc 全距 0.65pp——模型表現與子圖時間結構完全獨立。
- Acc 51.29%,CI [48.81, 53.71];**Acc − 全押跌地板 = −3.79pp,CI [−7.27, −0.36],P(高於地板) = 1.5%**;SE 膨脹 8.1×,**有效樣本數 ≈ 1,599**(名目 105,215)。

**結論**
- 「精緻但讀不出東西的取景器」:表示法框到什麼不影響輸出;樣本重疊讓統計效力縮水 66 倍。

**產出**
- `analysis/*.py`、`figs/subgraph_viz.html`、`實驗記錄_論文對齊.md` §十二(12.1–12.4)。
"""

E["2026-08-20_流程圖海報_最佳實驗卡_講稿_CNN對照(中止)_記錄補齊.md"] = """# 2026-08-11 ~ 08-20　流程圖海報 / 最佳實驗卡 / 講稿 / CNN 對照(中止)/ 記錄補齊(檔案日期 08-20)

**做了什麼**
- 解讀同學(郭念慈)論文:雙分支 PIP-VG-GCN + 三大法人籌碼、±1% 死區三分類;整理其可借用工具(標籤隨機化對照、交易日 block bootstrap、非重疊子集、增量價值實驗設計)。
- **三張簡報級流程圖**(仿參考框架圖風格):總覽管線海報 `figs/chartgcn_pipeline.html`(含 7 維否證鏈、Row 4 表示法診斷)、子圖解剖 `figs/subgraph_viz.html`、最佳實驗卡 `figs/best_run_flow.html`;線上 artifact 三份(ID 記於實驗記錄附錄 A)。依指示多次修版(刪 Eq.(11) 推廣框 → 放回純 h=1 框 → 刪 dscache 框)。
- 海報步驟 1–6 講稿;說明 GCN vs CNN、importance 排序、子圖方向與標籤無關、老師「相似度比對 100 天內」建議的意思、grid search 參數清單。
- `test/run_cnn_baseline.py`:1D-CNN 對照(同樣本同標籤,輸入改 140×9 序列),tw50 煙霧測試通過;六輪批次依指示中止,無結果。
- 發現 scratchpad 被系統清空 → 全部分析腳本 / 海報原始檔**復原進 repo**(`analysis/`、`figs/`),重跑驗證一致;實驗記錄補 §十二與附錄 A(18 個 07-21 舊協定 JSON 索引)。教訓:持久工作一律放 repo。

**產出**
- `figs/`、`test/run_cnn_baseline.py`、`實驗記錄_論文對齊.md` §12.5 + 附錄 A。
"""

E["2026-08-23_事件驅動取樣_TripleBarrier_kNN相似度_相鄰日距離_w60_sysmon.md"] = """# 2026-08-23　事件驅動取樣 + Triple-barrier / k-NN 相似度 / 相鄰日距離 / window=60 / sysmon 監控工具

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
"""


def build():
    for name, body in E.items():
        with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
            f.write(body.lstrip("\n"))
    dated = sorted(n for n in E if n[:4] == "2026")
    undated = sorted(n for n in E if not n[:4] == "2026")
    lines = ["# 專題進度總覽(依日期)", "",
             "> 每個檔案 = 一個工作階段:做了什麼 / 為什麼 / 結果 / 產出。",
             "> 有日期者以 `YYYY-MM-DD_` 開頭;早期無可靠日期者以 `大綱_` + 簡略標題命名。",
             "> 產生器:`_build_progress.py`(修改內容後重新執行即可重建全部檔案)。", ""]
    if undated:
        lines += ["## 早期(無明確日期,依大綱排序)", ""]
        for n in undated:
            title = n[:-3].split("_", 2)[-1]
            lines.append(f"- [{title}]({n})")
        lines.append("")
    lines += ["## 有日期(依時間排序;系統 A = KLINE main 分支,系統 B = Chart-GCN)", ""]
    for n in dated:
        d, title = n[:10], n[11:-3]
        lines.append(f"- **{d}**　[{title}]({n})")
    lines += ["", "## 否證鏈總表(截至 2026-08-23)", "",
              "| # | 維度 | 日期 | 結果 |", "|---|---|---|---|",
              "| 1 | 換市場(上證 50,論文自身資料) | 07-21 | 50.1 ± 0.4%,69.26% 無法重現 ✗ |",
              "| 2 | 掃參數(論文 4.3 網格 31 組) | 07-24 | val F1m 0.47–0.53 噪音帶 ✗ |",
              "| 3 | 加資料量(50 → 500 檔) | 07-26 | 無改善趨勢 ✗ |",
              "| 4 | 分族群(電子 / 半導體 / 零組件 / 金融) | 07-27 | 最佳 51.29%,低於地板 ✗ |",
              "| 5 | 分流動性(前 100 / 後 100 / 前 200) | 08-02 | 無效應 ✗ |",
              "| 6 | 模型對照(XGBoost) | 07-22 / 07-24 | 同水準 ✗ |",
              "| 7 | 拉長視野(1 → 5 日) | 08-10 | 無訊號、seed 敏感 ✗ |",
              "| 8 | 事件取樣 + triple-barrier + 方向特徵;k-NN 相似度 | 08-23 | 9/9 run ≈ floor、k-NN = 隨機 ✗ |",
              "| 9 | 縮短窗格(w=60,論文範圍外) | 08-23 | 53.7% ≈ floor,塌向全跌 ✗ |",
              "| 10 | w60 + 週視野(h=5) | 08-23 | 平均 49.2 / 49.0%,低於 floor ✗ |", ""]
    with open(os.path.join(HERE, "00_總覽.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"built {len(E)} entries + 00_總覽.md")


if __name__ == "__main__":
    build()
