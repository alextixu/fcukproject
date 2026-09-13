# common/ — 共用資料與路徑(2026-09-12 重整)

`paths.py` 是唯一的路徑來源;各方法與回測腳本用
`sys.path.insert(0, <專題根目錄>); from common import paths as P` 取得。

## cache/ 內容

| 資料夾 | 內容 | 區間 | 來源 / 產生方式 | 誰在用 |
|---|---|---|---|---|
| `yf/` | yfinance 還原價,每檔多個區間版本 | 2016 ~ 2024 | `method_chartgcn/core/data_loader.py` 下載 | 2024 實驗(XGB、Chart-GCN) |
| `yf_2026/` | yfinance 還原價 | 2016 ~ 2026-09 | 同上,`TW_CACHE_DIR` 指到這裡 | 2026 全部實驗、逐年回測 |
| `official/` | 證交所 / 櫃買官方日資料(未還原) | 2025-10-01 ~ 2026-09-11 | `backtest/ncku/fetch_official.py`、`update_official.py` | 成大框架正式口徑(`NCKU_SRC=official`) |
| `yf_hist/` | 還原價轉成框架格式 | 2020-09 ~ 2026-09-10 | `backtest/ncku/make_yf_src.py --out yf_hist` | 逐年回測(`NCKU_SRC=yf_hist`) |
| `yf_fw/` | 還原價轉成框架格式 | 2025-10 ~ 2026-09-10 | `make_yf_src.py --out yf` | 大池篩選(`NCKU_SRC=yf`) |
| `kline_raw/` | yfinance 未還原 + Adj Close,TW50 | 2015 ~ 2026-09 | `backtest/scripts/run_kline_2026.py` | KLINE |
| `finmind/`、`finmind_2026/` | FinMind 籌碼(法人、融資券、外資持股) | tw500 / 2026 | `method_xgb/src/chip_data.py`(FINMIND_TOKEN 環境變數,token 不存檔) | XGB `--chip`(結論:沒幫助) |
| `features/` | XGB 特徵面板 `features_<pool>_<start>_<end>.parquet` | | `method_xgb/src/run_pipeline.py` 自動產生 | run_pipeline、predict_full* |

## 股票池清單

`TICKER_SETS`(tw50 / tw100 / tw200 / tw500 / electronics / semi / elec_liq100 / elec_liq200 / elec_all / tw50_elec)
目前仍定義在 `method_chartgcn/core/data_loader.py`,路徑由 `paths.CHARTGCN_CORE` 提供。重構時可搬到 `common/tickers.py`。

## 環境變數

- `TW_CACHE_DIR`:覆蓋還原價快取(預設 `cache/yf`;2026 實驗設成 `cache/yf_2026`)
- `FINMIND_DIR`:覆蓋籌碼快取
- `NCKU_SRC`:框架資料來源 `official` | `yf` | `yf_hist`
- `LOKY_MAX_CPU_COUNT=4`:joblib 重的工作先設,避免 pagefile MemoryError
