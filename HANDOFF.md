# 接手說明：逢甲資工畢業專題「以深度學習為基礎之自動化K線辨識系統」

你要在我的本地電腦接手一個已經做到發表前收尾階段的專題。請照下面的順序做：

1. 讀完這份說明。
2. 照「一、建置環境」把環境建好，並跑完「驗收」的每一項。任何一步失敗就停下來告訴我錯誤訊息，不要跳過，也不要自己換套件版本。
3. 建好後用一張表回報：每個驗收項目通過或失敗、各分支的最新 commit、還缺什麼。
4. 之後等我指示，不要自己開始做「五、還沒完成的事」。

回覆一律用繁體中文，結論先講，多用表格，句子寫完整。

---

## 一、建置環境

### 1. 取得程式

```bash
git clone https://github.com/alextixu/fcukproject
cd fcukproject
git fetch --all
```

需要三個工作目錄，建議用 worktree 分開，互不干擾：

```bash
git checkout final                                              # 主目錄：最終版程式碼與成品
git worktree add ../fcuk-web    claude/kline-peak-web-app       # 網頁系統
git worktree add ../fcuk-report claude/kline-peak-report-pptx   # 簡報、海報、Word 的產生程式
```

| 分支 | 用途 | 我交接時的 commit |
|---|---|---|
| `final` | 最終版程式碼；簡報 v1 / v2 / v3、海報 v2、Word v2 | 07894bb |
| `claude/kline-peak-web-app` | 網頁系統 `method_kline_peak/web/` | 7ce69e3 |
| `claude/kline-peak-report-pptx` | 成品的產生程式 `method_kline_peak/report/final_build/`、`thesis_build_v2/` | 44e3974，之後可能多一筆架構圖的 commit |
| `claude/kline-peak-predict-tool` | 完整研究紀錄（含淘汰的方法與實驗），只供查閱 | a8a1332 |
| `kline-peak-new` | 組員的另一套方法，沒有採用 | d6c74ef |
| `main` | 舊版，**不要動** | 3120815 |

### 2. Python 環境

- 驗證過的版本是 **Python 3.13**。請用 3.13 建虛擬環境；沒有就先告訴我，不要用別的版本硬裝。
- 套件版本已釘死在 `final` 的 `requirements.txt`，照裝，不要升級：

```
numpy==2.5.3
pandas==3.0.5
pyarrow==23.0.1
scikit-learn==1.9.1
torch==2.14.1
lightgbm==4.7.0
matplotlib==3.10.8
pytest==9.2.0
yfinance==1.2.0
```

```bash
python3.13 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

注意：

- `torch` 從 PyPI 裝會帶 CUDA，佔約 5–6 GB。本專題只用 CPU。要省空間可以改裝 CPU 版：`pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu`，再裝其餘套件。兩種都可以，結果相同。
- scikit-learn 的版本一定要是 1.9.1，換版本會讓已存的模型和核對結果對不上。
- 三個工作目錄共用同一個虛擬環境即可。

### 3. 只有重做簡報、海報、Word 才需要的工具

只跑程式和網頁的話可以跳過這一節。先檢查有沒有，沒有再裝。

| 工具 | 用途 | 檢查指令 |
|---|---|---|
| Node.js 18 以上 | 產生 pptx、docx | `node -v` |
| npm 套件 `pptxgenjs`、`docx` | 同上 | 在 `method_kline_peak/report/final_build/` 和 `thesis_build_v2/` 各自 `npm install pptxgenjs docx` |
| LibreOffice | pptx / docx 轉 PDF、更新 Word 目錄 | `soffice --version` |
| poppler（`pdftoppm`、`pdftotext`） | PDF 轉圖、搜尋文字 | `pdftoppm -v` |
| Pillow | 裁切截圖、畫圖 | `pip install pillow` |
| 中文字型 | 簡報用微軟正黑體；Word 用標楷體 + Times New Roman | Windows、macOS 通常已有；Linux 要自己裝 |

簡報和海報的產生程式會讀環境變數 `PPTX_SKILL`，指向一個放 pptx 輔助腳本的資料夾（裡面有 `scripts/apply_theme.js`、`scripts/office/validate.py`）。這個資料夾**不在 repo 裡**，是雲端環境內建的。本地如果沒有：

- 只要改字、換圖，直接用 PowerPoint 編輯現成的 pptx 就好，不需要它。
- 要用程式重新產生，先打開 `make_presentation_v3.js` 看它用到 `PPTX_SKILL` 的哪幾個函式，告訴我缺什麼，再決定怎麼補。不要自己刪掉相關程式碼。

### 4. 網頁系統的資料要在本地重新產生

**網頁的資料不在 git 裡**（`method_kline_peak/web/data/`、`site/data/`、`dist/` 都被 `.gitignore` 排除）。本地第一次要自己產生，需要連得到 Yahoo Finance：

```bash
cd ../fcuk-web
python method_kline_peak/web/run.py replay --start 2026-01-01   # 第一次：下載股價、訓練模型、逐日產生今年的判斷
python method_kline_peak/web/run.py serve                        # 開 http://localhost:8000
```

- 第一次會下載約 2,200 檔股票（上市、上櫃、ETF）的日 K，Yahoo 偶爾會限流（429），程式會自動等候重試，整個過程可能要幾十分鐘。
- 之後每天收盤後（18:00 以後）跑一次 `python method_kline_peak/web/run.py daily`。
- 其他指令見 `method_kline_peak/web/README.md`：`update`（只下載）、`publish`（只重產網頁資料）、`train --year`、`daily --offline`。

### 5. 驗收

每一項都要實際執行，回報結果：

| # | 在哪個目錄 | 指令 | 預期 |
|---|---|---|---|
| 1 | `final` | `python -m pytest method_kline_peak/tests -q` | 71 passed |
| 2 | `final` | `python method_kline_peak/report/confusion_2024_2026.py --pool tw200` | 三年 macro-F1 = 54.31 / 53.42 / 54.51，和 `results/confusion_2024_2026_tw200.json` 一致 |
| 3 | `final` | `python method_kline_peak/report/baseline_rule.py` | 只用規則三年合計 macro-F1 54.15；本系統 54.07 |
| 4 | `fcuk-web` | `python -m pytest method_kline_peak/web/tests -q` | 63 passed |
| 5 | `fcuk-web` | `python method_kline_peak/web/check_research_match.py` | 網頁模型和 final 的結果完全一致 |
| 6 | `fcuk-web` | `run.py replay` 後 `run.py serve`，打開首頁、個股查詢輸入 2454 | 頁面正常；畫面沒有「機率」「Stacking」「台灣 50」 |
| 7 | `final` | `git status` | 乾淨；跑測試會重寫 `tests/REPORT.md`，內容應該不變 |

第 2、3、5 項會重新訓練模型，各需要幾分鐘。結果檔如果有任何數字和 git 裡的不同，停下來告訴我，不要 commit。

---

## 二、專題內容

- 題目：以深度學習為基礎之自動化K線辨識系統
- 指導老師：李俊宏 老師
- 學生：郭家齊 D1245765、呂偉湘 D1286314（呂偉湘的 GitHub 帳號是 TomweiLu）

### 最終方法（`final`）

規則篩候選 → 29 維型態特徵 → AE（29→16）→ OC-SVM（nu 0.1、相似樣本權重）。內部曾稱「主軸」，對外文件一律寫「本系統」。

| 項目 | 設定 |
|---|---|
| 標籤 | t 的收盤是前後各 5 天、共 11 天裡最高 = 高點，最低 = 低點，其餘非極值 |
| 規則候選 | t 收盤是最近 6 天最高 / 最低才進模型，其餘直接判非極值 |
| 特徵 | t−5 到 t 六根 K 線的開高低收 ÷ t 收盤取 log（t 那天的收盤恆為 0，拿掉），加六天的量 ÷ 10 日均量取 log，共 29 維 |
| 資料 | TW200 剔除低波動股後 168 檔，還原價，2016 到 2026-09，快取在 `common/cache/yf_2026/` |
| 驗證 | 逐年 walk-forward，測哪一年就用前 4 年訓練，種子 42 |
| 主要程式 | `method_kline_peak/mainline.py`、`walkforward.py`、`ae_ocsvm.py`、`peak_labels.py` |

### 成績（168 檔；數字都在 `final` 的 `method_kline_peak/results/`）

| 年 | macro-F1 | 低點找到率 / 命中率 | 高點找到率 / 命中率 | 判反 |
|---|---|---|---|---|
| 2024 | 54.31% | 87.6% / 27.7% | 86.8% / 29.8% | 0 |
| 2025 | 53.42% | 83.3% / 28.2% | 82.2% / 27.8% | 0 |
| 2026（1–9 月） | 54.51% | 71.5% / 31.9% | 66.5% / 26.7% | 0 |
| 三年合計 | 54.07% | 81.9% / 28.7% | 80.1% / 28.3% | 0 |

必須照實說的事：

1. **成績主要來自規則。** 只用規則：macro-F1 54.15%、找到率 100%、命中率 28.6%。加上 AE + OC-SVM 後訊號少 18.6%，命中率持平（28.5%），找到率降到 81.0%。不能說 AE + OC-SVM 提高了準確度。來源：`results/baseline_rule_vs_mainline_2024_2026.json`。
2. **判反 0 是規則設計保證的**，不是模型學出來的。
3. **回測全部虧損。** 2024–2025 試了 30 種只做多策略，扣成本（一趟 0.585%）後全賠，最好 −6.56%，同期 0050 +102.02%。定位是看盤輔助，不是交易訊號。來源：`results/backtest_strategies_2024_2025.json`。
4. 隨機基準約 7.2%。「命中率約為隨機的 4 倍」是真的，但這 4 倍來自規則。
5. 實測時間：168 檔判斷一天 2.48 秒、訓練一個年份 19.0 秒，只用 CPU（Intel Xeon 2.10GHz、4 核）。來源：`results/timing_mainline.json`。本地重測的數字會不同，文件上要嘛沿用這組並註明環境，要嘛全部改成本地實測。
6. 範例股：聯發科 2454 的 2025 年。真高 26 / 真低 22，高點找到 24（92.3%）、低點找到 20（90.9%），命中率 41.4% / 37.0%。它高於整體平均。來源：`results/per_stock_mainline_2024_2026.json`。
7. 曾把特徵換成舊系統的 2 日 K（10 維），成績差不到 0.3 分，沒有採用。

---

## 三、成品與狀態

都在 `final` 的 `method_kline_peak/report/`：

| 成品 | 檔案 | 狀態 |
|---|---|---|
| 簡報 v1 | `專題簡報_v1.pptx` | 組員做的，有沒根據的數字（2 毫秒、年收入 6 億等），不用 |
| 簡報 v2 | `專題簡報_v2.pptx` | 舊大綱，保留 |
| **簡報 v3** | `專題簡報_v3.pptx` | **目前版本**。12 頁，備忘稿有逐字講稿，約 11–12 分鐘 |
| 海報 v2 | `專題海報_v2.pptx / .pdf / .png` | A1 直式，定稿 |
| Word v2 | `專題研究報告_v2.docx` | 32 頁，照逢甲專題研究報告格式規範。轉 PDF 前要在 Word 對目錄、圖目錄、表目錄各按一次「更新功能變數」 |
| 網頁 | 雲端版：https://claude.ai/artifact/BdK1rkGGJNDKEWbdbfdsDZ | 資料到 2026-11-20；推薦範圍 168 檔；全部上市 / 上櫃 / ETF 可查。本地版要照「一之 4」重新產生 |

產生程式在 `claude/kline-peak-report-pptx`：

| 成品 | 程式 | 說明文件 |
|---|---|---|
| 簡報 v3 | `report/final_build/make_presentation_v3.js`、`figs_v3.py`、`figs_final.py` | `report/final_build/README.md`（有指令、數字來源、截圖裁切框） |
| 海報 v2 | `report/final_build/make_poster_v2.js` | 同上 |
| Word v2 | `report/thesis_build_v2/build_report_v2.js`、`figs_v2.py`、`lo_update.py`、`fix_fonts.py` | `report/thesis_build_v2/README.md` |

產生程式改好成品後，要把成品複製一份到 `final` 的 `method_kline_peak/report/`。

### 簡報 v3 的大綱

| 頁 | 段落 | 標題 |
|---|---|---|
| 1 | 封面 | 以深度學習為基礎之自動化K線辨識系統 |
| 2 | 問題動機 | 給使用者判斷高低點 |
| 3 | 問題動機 | 現有做法的限制，與我們的一句話 |
| 4 | 系統架構 | 整體流程 |
| 5 | 方法技術 | 做了什麼：三個模組 |
| 6 | 方法技術 | 為什麼這樣選、亮點在哪 |
| 7 | 成果數據 | 168 檔 × 三年實測 |
| 8 | 成果數據 | 跟 Baseline 比 |
| 9 | 應用價值 | 效益與限制 |
| 10 | 應用價值 | 導入場域、誰會買、競爭對手 |
| 11 | Demo | 系統實機展示 |
| 12 | 結論 | 結論 |

一句話：「我們開發一套 K 線高低點辨識系統，在收盤當天就指出股價是否處在極值環境：找到約 8 成的高低點，命中率從隨機的 7.2% 提高到 28.5%」。

---

## 四、我的固定要求

- 沒有叫你跑的實驗不要跑。新實驗先給設計，我說好才跑。
- 破壞性或改寫歷史的 git 操作先問我。不要動 `main`。`final` 只放一個方法。沒有我的指示不要 push。
- 新版成品另存新檔名（v4、v5…），舊版保留。
- 每個數字都要對得上 `final` 的結果檔；沒有實測或出處的數字不寫。
- 對外文件（簡報、海報、Word、網頁）不能出現：Stacking、邏輯迴歸、機率、主軸、信心等級、台灣 50、34 檔、73 檔、2 日 K、「提高準確度」「更準」。
- 簡報另外不能出現：「股票看不完」、人工看盤時間的估算、「剔除低波動股」或 168 檔怎麼來的、市場規模。
- 簡報的動機：有波動才有利潤，要幫使用者判斷高低點、找出極值環境。系統回答的是「現在是不是極值環境」，不是「該不該買賣」。
- 簡報規範：封面 / 問題動機 / 系統架構 / 方法技術 / 成果數據 / 應用價值 / Demo / 結論；每頁約 1 分鐘，總長 10–12 分鐘；每頁一個重點、圖和大數字為主、少標籤，說明放講稿。
- 改完成品要轉成圖逐頁檢查：文字不能溢出、不能有單字落單、區塊要對齊。

---

## 五、還沒完成的事（等我指示再做）

1. **簡報 v3 第 4 頁的系統架構圖重畫。** 我嫌原圖太差，給過一份參考圖集（LLM Engineer's Handbook 風格）。要求：
   - 分成四個管線大框：資料（Yahoo 股價 → 每日更新 → K 線資料庫）、特徵（6 根 K 線 → 29 維型態 → 規則候選的菱形判斷）、訓練（前 4 年資料 → 標籤 → AE → OC-SVM，高點低點各一組 → 模型庫）、判斷與服務（今日特徵 → 載入模型 → 分數 → 高點 / 低點 / 非極值 → 判斷存檔 → 5 天後對答案 → 網頁 ↔ 使用者）。
   - 風格：細線圓角大框、框內上方粗體名稱；淡色圓角模組（淡橘 = 處理步驟、淡黃 = 輸入輸出、淡綠 = 服務或決策）；黑白線條的圓柱資料庫圖示；細的圓角折線箭頭，端點有小圓點，旁邊小字標出流過去的資料；人形使用者圖示；次要流向用虛線；白底、留白多、線不交叉、字少。
   - 雲端的報告 session 正在畫。請先 `git fetch`，看 `claude/kline-peak-report-pptx` 在 44e3974 之後有沒有新 commit。有的話新圖在 `method_kline_peak/report/final_build/fig/f_arch_v2.png`，簡報 v3 也會更新，要把新的 v3 複製到 `final`。沒有的話等我指示再重畫。
2. **專題介紹影片（約 3 分鐘）。** 系上規定發表前要交。可行做法：用瀏覽器自動操作錄下網頁 Demo、投影片轉圖、ffmpeg 合成、燒字幕；旁白我自己錄。參考影片是系上頻道的「110-A10.肢體辨識健身系統」（https://youtu.be/uttg6YnH28k）。雲端看不到它的內容，本地可以看；需要時先看過，把它的架構整理給我。
3. 海報的「系統流程」和 Word 的架構圖要不要換成新架構圖，還沒決定。
4. 海報摘要和 Word v2 的動機仍寫「人工每天看盤費時」，簡報 v3 已改成「找出極值環境」。要不要統一，還沒決定。
5. 網頁上推薦範圍寫的是「台灣 200（剔除低波動股）」，簡報不提剔除這件事。要不要改網頁上的字，還沒決定。
6. 還沒做：抄襲比對（系上要求單一來源相似度低於 5%）、把網頁部署到我自己的主機並設定每日自動更新。

## 六、還沒告知的人

- 「AE + OC-SVM 沒有比只用規則更準」這個發現，建議發表前先讓李老師知道，我還沒決定要不要講。
- 組員的 v1 簡報和現在的 v3 說法不同，上台前要對齊。
