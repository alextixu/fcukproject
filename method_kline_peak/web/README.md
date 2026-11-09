# K 線高低點判斷網頁(本機展示版)

每天收盤後判斷「台灣 50 哪些股票今天可能是 11 天高點 / 低點」,並提供個股查詢、成績追蹤、研究發現與方法說明。
定位是**參考方向的決策輔助**:判斷當提醒,不當買賣指令,網頁不放回測與報酬。
目前是展示版(畫面上有標示),只給自己或研究團隊用,不公開、不收費。設計稿與可行性評估在 `design/`。

2026-11-09 使用者決定:Stacking 是最終版,主軸完全拿掉;模型用研究版 TW200(剔除低波動股)訓練;推薦範圍改成台灣 50。

## 快速開始

```bash
pip install -r requirements.txt                      # 專題根目錄的套件清單(torch、scikit-learn、yfinance、pyarrow…)
python method_kline_peak/web/run.py replay --start 2026-01-01   # 第一次:回放上線前的日子,成績追蹤才有歷史(約 7 分鐘)
python method_kline_peak/web/run.py start            # 每日批次 + 開本機網頁 http://localhost:8000
```

之後每天 18:00 以後跑一次 `run.py daily` 就好,網頁用 `run.py serve` 開。

| 指令 | 做什麼 |
|---|---|
| `run.py daily` | 每日批次:更新 K 線 → 判斷並存檔 → 對答案 → 產生網頁資料 |
| `run.py daily --offline` | 不連網,只用已快取的 K 線(判斷基準日 = 快取的最後一天) |
| `run.py daily --date 2026-09-10` | 指定判斷基準日(補跑);那天已經有存檔就不重算 |
| `run.py replay --start 2026-01-01 [--end …]` | 上線前的日子逐日產生回放存檔(已存在的日子跳過) |
| `run.py train --year 2027` | 手動重訓某一年的模型(平常不用,批次會自動處理) |
| `run.py publish` | 只重新產生網頁資料 |
| `run.py serve [--port 8000]` | 開本機網頁(只聽 127.0.0.1) |
| `--universe tw200` | 只算研究用 TW200 清單裡的上市股(預設 `all` = 全部上市普通股,約 1,070 檔,供個股查詢) |
| `--pool tw100` | 換訓練用股票池(預設 `tw200`;可用 `data_loader.TICKER_SETS` 的名稱),一樣剔除低波動股 |
| `--train-min-amp 3` | 換訓練門檻(%,預設 0;同研究的 `--train-min-amp`,對答案仍用原本的標籤) |

### 換股票池、推薦範圍或訓練門檻

都是設定值,不用改程式:命令列參數,或環境變數 `KPWEB_POOL`(訓練用股票池)、`KPWEB_RECOMMEND`(推薦範圍,預設 `tw50`)、`KPWEB_TRAIN_MIN_AMP`。

- 每組設定的模型、判斷存檔、答案分開放在 `data/<設定>/`(例 `data/tw200/`、`data/tw200_amp3/`),互不覆蓋;K 線快取共用 `data/prices/`。
- 2026 年(含)以前的訓練股票池直接用研究結果檔記錄的清單(`results/backtest_long_only_<池>.json`),和研究完全相同、同順序;
  2027 年起照 `mainline.load_data` 的規則用前一年底的資料剔除低波動股。
- 換設定後網頁顯示的是最後一次執行的設定(`site/data/` 會整批重寫)。

### 每天自動跑

- macOS / Linux(crontab,週一到週五 18:10):
  `10 18 * * 1-5 cd /path/to/fcukproject && python method_kline_peak/web/run.py daily >> method_kline_peak/web/data/daily.log 2>&1`
  資料晚到時可以在 20:10、22:10 各加一行;已經存檔的日子不會重算。
- Windows(工作排程器):動作設為 `python method_kline_peak\web\run.py daily`,起始位置設為專題根目錄。

## 運作方式

| 項目 | 做法 |
|---|---|
| 模型 | 只有 Stacking:`stacking.StackingSource("lr", "score")`,直接用研究的類別。Y 年用 Y−4 ~ Y−1 訓練:前 3 年給高點 / 低點兩組 AE + OC-SVM,最後 1 年給邏輯迴歸,中間剔除 5 個交易日;種子 42、標籤門檻 0% |
| 訓練股票池 | 研究版 TW200 剔除低波動股(和研究 `--pool tw200` 同一份) |
| 推薦範圍 | 台灣 50 全部 50 檔,每天都給判斷(低波動股也照樣判斷);今日判斷、成績追蹤只看這 50 檔 |
| 重訓 | 每年自動:1 月第 6 個交易日之後第一次跑批次時訓練新的一年(約 1 分鐘),在那之前沿用前一年的模型 |
| 資料 | yfinance 還原價,快取在 `data/prices/`;第一次從研究快取 `common/cache/yf_2026` 複製(研究快取不會被改)。只下載最後一天之後的資料,重疊區間收盤差 > 0.2%(除權息)就重抓整段 |
| 每日判斷 | 全部上市普通股都算(個股查詢用);推薦清單只列台灣 50,判低點 / 判高點依「沒破底 / 沒創高」天數分組、組內依機率排序 |
| 存檔 | `data/<設定>/days/<日期>.json` 當天判斷(只有 Stacking)、`data/<設定>/grades/<日期>.json` 5 天後的答案。兩種檔都是寫過就不再改。真實輸出的節錄在 `samples/` |
| 對答案 | t+5 收盤後,用研究的同一個標籤規則判斷是不是真高 / 低點 |
| 股票分類 | 台灣 50(推薦範圍)/ 池外(提示)/ 低波動(推薦範圍以外、每日漲跌幅中位數 < 0.725%,顯示不適用)/ 不支援(ETF、上櫃、興櫃、特別股)/ 資料不足 / 今日無交易 |
| 研究結果 | 網頁上的研究數字直接讀 `results/` 的結果檔(TW200 Stacking),不重算 |
| 前端 | `site/` 靜態網頁,讀 `site/data/*.json`(每次批次重寫) |

`data/` 與 `site/data/` 不進 git。每日存檔是唯一的紀錄,換電腦時要一起搬。

### 和研究模型一致

`python method_kline_peak/web/check_research_match.py` 比對網頁系統的 Stacking 和研究版 TW200 模型(結果存 `samples/research_match.json`):

- 2026:用研究程式(`mainline.load_data(pool="tw200")` → `walkforward.year_split` → `StackingSource`)另外訓練一份,
  台灣 50 全部 50 檔、2026-01-02 ~ 09-10 共 8,350 個股票日,三類機率最大差距 0、判斷 100% 相同。
- 2024:南電每日輸出 `results/outputs_8046_2024_tw200_amp0.csv` 242 天,判斷全部相同、最大機率差距 0(csv 4 位小數)。
- 2025:`results/lr_example_tw200_2025.json` 南電 4 個例子,三類機率完全相同。

## 頁面

| 頁面 | 網址 | 內容 |
|---|---|---|
| 今日判斷 | `#today` | 台灣 50 判低點 / 判高點,依「沒破底 / 沒創高」天數分三組(剛出現、已 1–2 天、已 3 天以上),每組附研究命中率;每檔標「連續第 N 天」 |
| 個股查詢 | `#stock`、`#stock-2330` | 今天的判斷與三類機率、最近 5 天內還沒破底 / 沒創高的訊號、K 線與過去訊號對錯;台灣 50 以外的股票加提示 |
| 成績追蹤 | `#track` | 台灣 50 每天的判斷 5 天後對答案:命中率、信心等級、每日明細 |
| 研究發現 | `#findings` | 方向性結論:找得到轉折區、高低點不判反、命中率約三成 → 定位為決策輔助;等確認天數的命中率;「網頁怎麼用」 |
| 方法與說明 | `#about` | 標籤定義、Stacking 怎麼判斷、研究命中率、免責聲明 |

- 「連續第 N 天」「已 M 天沒破底」只用當天以前的存檔與價格(`system/signals.py`,規則同研究 `confirm_signals.py`),產生網頁資料時才算。

## 發布成 claude.ai Artifact

```bash
python method_kline_peak/web/run.py publish          # 產生 site/data/
python method_kline_peak/web/build_artifact.py       # 打包成 dist/(index.html 只放頁面內容,其餘檔案原樣複製)
```

`dist/index.html` 加上 `dist/` 裡的其他檔案(約 72 個、4 MB)發布成一個 Artifact。個股資料依代號前兩碼分檔(`stocks/23.json`),
因為 Artifact 一次最多發布 255 個檔案。頁面支援淺色 / 深色主題與手機版面。

## 測試

```bash
python -m pytest method_kline_peak/web/tests        # 網頁系統 50 項
python -m pytest method_kline_peak/tests            # 研究程式碼原本的測試
```

網頁系統的測試涵蓋:資料更新(增量、還原價變動重抓、網路失敗、休市)、判斷存檔不覆蓋、5 天後才對答案、
台灣 50 / 池外 / 低波動 / 不支援判定、判斷檔格式(只有 Stacking)、股票池與訓練門檻設定、信心等級、連續天數與沒破底天數(不偷看未來)、
研究發現的數字和結果檔一致、網頁資料沒有回測與報酬欄位、特徵不偷看未來、每日批次與回放結果相同、正式模型重現研究 TW200 2026 年的成績。
