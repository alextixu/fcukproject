# K 線高低點判斷網頁(本機展示版)

每天收盤後產生「今天哪些股票可能是 11 天高點 / 低點」的判斷,並提供個股查詢、成績追蹤與方法說明。
目前是展示版(畫面上有標示),只給自己或研究團隊用,不公開、不收費。設計稿與可行性評估在 `design/`。

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
| `--pool tw200` | 換訓練用股票池(預設 `tw100`;可用 `data_loader.TICKER_SETS` 的名稱),一樣剔除低波動股 |
| `--train-min-amp 3` | 換訓練門檻(%,預設 0;同研究的 `--train-min-amp`,對答案仍用原本的標籤) |

### 換股票池或訓練門檻

股票池和訓練門檻是設定值,不用改程式。可以用命令列參數,也可以用環境變數 `KPWEB_POOL`、`KPWEB_TRAIN_MIN_AMP`:

```bash
python method_kline_peak/web/run.py replay --start 2026-01-01 --pool tw200      # TW200 剔除低波動股(2026 年 168 檔)
python method_kline_peak/web/run.py start --pool tw200
KPWEB_POOL=tw100 KPWEB_TRAIN_MIN_AMP=3 python method_kline_peak/web/run.py start
```

- 每組設定的模型、判斷存檔、答案分開放在 `data/<設定>/`(例 `data/tw100/`、`data/tw200_amp3/`),互不覆蓋;K 線快取共用 `data/prices/`。
- 2026 年的股票池直接用研究結果檔記錄的清單:`tw100` 73 檔、`tw200` 168 檔、`tw50` 34 檔;其他股票池或年份照 `mainline.load_data` 的規則剔除低波動股。
- 換設定後網頁顯示的是最後一次執行的設定(`site/data/` 會整批重寫)。

### 每天自動跑

- macOS / Linux(crontab,週一到週五 18:10):
  `10 18 * * 1-5 cd /path/to/fcukproject && python method_kline_peak/web/run.py daily >> method_kline_peak/web/data/daily.log 2>&1`
  資料晚到時可以在 20:10、22:10 各加一行;已經存檔的日子不會重算。
- Windows(工作排程器):動作設為 `python method_kline_peak\web\run.py daily`,起始位置設為專題根目錄。

## 運作方式

| 項目 | 做法 |
|---|---|
| 股票池 | 設定值,預設 TW100 剔除低波動股,2026 年 = 研究的 73 檔(`results/backtest_long_only_tw100.json`) |
| 模型 | 研究 walk-forward 的同一套:`walkforward.MainlineSource`(主軸)、`stacking.StackingSource("lr", "score")`;Y 年用 Y−4 ~ Y−1 訓練、種子 42、訓練門檻預設 0%(`walkforward.relabel`) |
| 重訓 | 每年自動:1 月第 6 個交易日之後第一次跑批次時訓練新的一年(約 30 秒),在那之前沿用前一年的模型 |
| 資料 | yfinance 還原價,快取在 `data/prices/`;第一次從研究快取 `common/cache/yf_2026` 複製(研究快取不會被改)。只下載最後一天之後的資料,重疊區間收盤差 > 0.2%(除權息)就重抓整段 |
| 每日判斷 | 池內、池外、低波動股都算;推薦清單只列池內股票,判低點 / 判高點各依分數排序,前 3 檔放上面 |
| 存檔 | `data/<設定>/days/<日期>.json` 當天判斷、`data/<設定>/grades/<日期>.json` 5 天後的答案。兩種檔都是寫過就不再改。真實輸出的節錄在 `samples/` |
| 對答案 | t+5 收盤後,用研究的同一個標籤規則判斷是不是真高 / 低點;另記 t+1 開盤 → t+5 收盤報酬(扣成本 0.585%) |
| 股票分類 | 池內 / 池外(黃色警示)/ 低波動(每日漲跌幅中位數 < 0.725%,顯示不適用)/ 不支援(ETF、上櫃、興櫃、特別股)/ 資料不足 / 今日無交易 |
| 研究結果 | 方法說明頁的數字直接讀 `results/` 的結果檔,不重算 |
| 前端 | `site/` 靜態網頁,讀 `site/data/*.json`(每次批次重寫) |

`data/` 與 `site/data/` 不進 git。每日存檔是唯一的紀錄,換電腦時要一起搬。

## 測試

```bash
python -m pytest method_kline_peak/web/tests        # 網頁系統 38 項
python -m pytest method_kline_peak/tests            # 研究程式碼原本的測試
```

網頁系統的測試涵蓋:資料更新(增量、還原價變動重抓、網路失敗、休市)、判斷存檔不覆蓋、5 天後才對答案、
池內 / 池外 / 低波動 / 不支援判定、判斷檔格式、股票池與訓練門檻設定、特徵不偷看未來、每日批次與回放結果相同、正式模型重現研究 2026 年的成績。
