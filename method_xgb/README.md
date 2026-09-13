# xgb_ta_pipeline — 技術指標 × XGBoost 特徵篩選

老師 2026-08-25 建議的方法：生成 ~200 個技術指標 → XGBoost → feature importance 剔除弱指標 → 重訓 → 與 Chart-GCN 同協定比較。

完整設計見 **`計畫書.md`**。

## 資料夾

```
計畫書.md        設計文件（背景、指標清單、切分協定、剔除規則、評估、時程）
實驗記錄.md      每次執行自動 append
config/          default.json（參數）、feature_catalog.csv（指標目錄，程式產生）
src/             管線程式:data / features(七族 + 籌碼) / labels / split / train_xgb / importance / prune / evaluate / plots / run_pipeline
                 chip_data.py:FinMind 籌碼下載(三大法人、融資券、外資持股)→ data/finmind/
data/finmind/    籌碼原始資料(每檔每 dataset 一個 parquet,可續跑;未版控)
tests/           test_features.py(無 inf、無未來洩漏)
experiments/     JSON / 模型 / importance csv / 特徵 parquet 快取
figs/            重要性圖、十分位圖
```

## 資料來源

不重新下載。直接讀 `../chartgcn/cache/*.parquet`（822 檔台股 2016–2024，yfinance auto_adjust）。
程式透過 `sys.path` 掛上 `../chartgcn/core` 使用 `data_loader.fetch_yfinance()` 與 `TICKER_SETS`。

## 環境

Python 3.12，本機已有 xgboost 3.3 / pandas 2.3 / numpy 2.2 / sklearn 1.8 / scipy / matplotlib / pyarrow。
可選：`pip install shap`。

執行前（Windows 分頁檔限制）：

```
set LOKY_MAX_CPU_COUNT=4
```

## 快速開始

```
cd xgb_ta_pipeline
python tests/test_features.py                       # 特徵庫自測
python src/run_pipeline.py --tag e1-tw50-h1         # 預設:tw50, h=1, 7 個特徵集, 3 seeds, 5 種剔除規則
python src/run_pipeline.py --horizon 5 --tag e3-tw50-h5
python src/run_pipeline.py --pool tw200 --horizon 5 --label cs --tag e5-tw200-h5-cs
python src/run_pipeline.py --lag 1 --feature-sets full --prune none --seeds 42 --tag diag-lag1   # 洩漏診斷
python src/chip_data.py --pool tw200                                   # 下載籌碼(免 token,約 1.5s/次;可設 FINMIND_TOKEN)
python src/run_pipeline.py --chip --pool tw200 --horizon 5 --label cs --tag e6-tw200-h5-cs-chip   # 加籌碼族群
```

特徵集名稱:`ma` `macd` `kd` `rsi`(四種經典)、`classic4`(四種合併)、`paper9`(論文 9 指標 n=140)、`full`(約 200 欄)、
`family:<族群>` / `nofamily:<族群>`(消融;族群名 trend/momentum/volatility/volume/candle/stats/cross_section/chip)。
`--chip` 時 full 會包含 35 欄籌碼 + 6 欄籌碼橫斷面排名;籌碼整族 shift(1)(收盤後才公布,決策日只用前一日籌碼)。
`top:<tag>:<K>`:沿用某次實驗 `experiments/<tag>_importance.csv` 的合成排名前 K 欄(跨股票池沿用篩選結果)。

大股票池(tw500,>60 萬列)自動走 `src/lowmem.py`:特徵逐檔寫進 memmap(`experiments/features_*_lowmem.dat`),
訓練時只載入本次用到的欄位;`--stride 3` 讓訓練列每 3 個交易日取一(val/test 不變)以省記憶體。

分類指標另含 `acc_cov5/10/20/50`:只對機率最極端的前 5/10/20/50% 樣本計算的準確率(覆蓋率 vs 準確率)。剔除規則:`cum90` `top20` `top40` `top80` `permpos`,或 `all` / `none`。

結果表的「週轉 / 成本年化% / 淨 H-L / 淨 t」:多空兩腿各自計算每次換倉的成員變動比例,
乘上一趟成本 0.585%(手續費 0.1425%×2 + 證交稅 0.3%,`src/evaluate.py` 的 `COST_RT`),從 H-L 扣除。

每次執行:`experiments/<tag>.json`(全部數字)、`experiments/<tag>_importance.csv`、`figs/<tag>_*.png`,並 append 到 `實驗記錄.md`。
特徵 panel 快取在 `experiments/features_<pool>_<start>_<end>.parquet`(第一次約 15 秒)。

## 狀態

- 2026-09-07:資料夾建立、計畫書、程式完成;tw50 特徵 201 欄 + paper9 9 欄;煙霧測試通過。
- 2026-09-07:e1(h=1)、e3(h=5)、洩漏診斷完成,結果與判讀見 `實驗記錄.md`。摘要:全指標 XGB AUC 0.574 / H-L +86%(h=1),
  訊號集中在當日 K 棒(close_pos、影線)的隔日反轉;四種經典指標與論文 9 指標皆在 floor;篩到 20 欄訊號不變。
- 2026-09-07:加交易成本(週轉 × 0.585%);e4(tw50 h5 cs)、e5a–d(tw200 h1/h5/h20、bin/cs)完成。
  h=1 效應在 tw200 重現(AUC 0.561、t 4.9)但淨值大幅為負;h=5 用橫斷面標籤最佳(tw200 top20 H-L +37%、t 2.6),
  淨值接近打平(損益兩平一趟成本 0.48%);h=20 無訊號。判讀見 `實驗記錄.md` 結論五~八。
- 2026-09-07:FinMind 籌碼(三大法人 / 融資券 / 外資持股,tw200 全部下載到 data/finmind/)接入為 chip 族群,e6a–e6d 完成。
  籌碼單獨無訊號;h=1/h=5 無增值;tw200 h=20 橫斷面標籤 + 篩 20 欄(含 6 欄籌碼)AUC 0.551、淨 H-L +30%、淨 t 2.9,
  是目前唯一扣成本後顯著的設定,但只有 12 個月期,待 rolling-origin 驗證。判讀見結論九~十一。
- 2026-09-07:tw500(552 檔)via lowmem memmap + stride 3;籌碼補齊 560 檔。AUC 全面上升(h=20 0.567、h=5 0.558)但 H-L 與淨值
  反而下降、t < 2;籌碼在 tw500 亦無增值。acc@cov20 約 60%。判讀見結論十二~十三。
