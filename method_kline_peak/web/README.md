# K 線高低點判斷網頁(本機版)

每天收盤後產生「今天哪些股票可能是 11 天高點 / 低點」的判斷,並提供個股查詢、成績追蹤與方法說明。
只給自己或研究團隊用,不公開、不收費。設計稿與可行性評估在 `design/`。

## 快速開始

```bash
pip install -r requirements.txt                      # 專題根目錄的套件清單(torch、scikit-learn、yfinance、pyarrow…)
python method_kline_peak/web/run.py replay --start 2026-01-01   # 第一次:回放上線前的日子,成績追蹤才有歷史(約 2 分鐘)
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
| `--universe tw200` | 只算研究用 TW200 清單裡的上市股(預設 `all` = 全部上市普通股,約 1,070 檔) |

### 每天自動跑

- macOS / Linux(crontab,週一到週五 18:10):
  `10 18 * * 1-5 cd /path/to/fcukproject && python method_kline_peak/web/run.py daily >> method_kline_peak/web/data/daily.log 2>&1`
  資料晚到時可以在 20:10、22:10 各加一行;已經存檔的日子不會重算。
- Windows(工作排程器):動作設為 `python method_kline_peak\web\run.py daily`,起始位置設為專題根目錄。

## 運作方式

| 項目 | 做法 |
|---|---|
| 股票池 | TW100 剔除低波動股,2026 年 = 研究的 73 檔(`results/backtest_long_only_tw100.json`) |
| 模型 | 研究 walk-forward 的同一套:`walkforward.MainlineSource`(主軸)、`stacking.StackingSource("lr", "score")`;Y 年用 Y−4 ~ Y−1 訓練、種子 42 |
| 重訓 | 每年自動:1 月第 6 個交易日之後第一次跑批次時訓練新的一年(約 30 秒),在那之前沿用前一年的模型 |
| 資料 | yfinance 還原價,快取在 `data/prices/`;第一次從研究快取 `common/cache/yf_2026` 複製(研究快取不會被改)。只下載最後一天之後的資料,重疊區間收盤差 > 0.2%(除權息)就重抓整段 |
| 每日判斷 | 池內、池外、低波動股都算;推薦清單只列池內股票,判低點 / 判高點各依分數排序,前 3 檔放上面 |
| 存檔 | `data/days/<日期>.json` 當天判斷、`data/grades/<日期>.json` 5 天後的答案。兩種檔都是寫過就不再改 |
| 對答案 | t+5 收盤後,用研究的同一個標籤規則判斷是不是真高 / 低點;另記 t+1 開盤 → t+5 收盤報酬(扣成本 0.585%) |
| 股票分類 | 池內 / 池外(黃色警示)/ 低波動(每日漲跌幅中位數 < 0.725%,顯示不適用)/ 不支援(ETF、上櫃、興櫃、特別股)/ 資料不足 / 今日無交易 |
| 研究結果 | 方法說明頁的數字直接讀 `results/` 的結果檔,不重算 |
| 前端 | `site/` 靜態網頁,讀 `site/data/*.json`(每次批次重寫) |

`data/` 與 `site/data/` 不進 git。每日存檔是唯一的紀錄,換電腦時要一起搬。

## 測試

```bash
python -m pytest method_kline_peak/web/tests        # 網頁系統 31 項
python -m pytest method_kline_peak/tests            # 研究程式碼原本的測試
```

網頁系統的測試涵蓋:資料更新(增量、還原價變動重抓、網路失敗、休市)、判斷存檔不覆蓋、5 天後才對答案、
池內 / 池外 / 低波動 / 不支援判定、特徵不偷看未來、每日批次與回放結果相同、正式模型重現研究 2026 年的成績。
