# 專題研究報告 v2 的產生方式

輸出:`../專題研究報告_v2.docx`(舊版 `../專題研究報告.docx` 保留不動)。
方法與數字和 `final` 分支、簡報 v2、海報 v2 相同;不跑實驗、不訓練,數字全部讀 `final` 的 `method_kline_peak/results/`。

```bash
# 1. 取 final 分支與網頁截圖(不 merge)
git archive origin/final method_kline_peak common | tar -x -C /tmp/fin
git archive 7ce69e3 method_kline_peak/web | tar -x -C /tmp/web          # 分支 claude/kline-peak-web-app
# 2. 資料(data.json)與圖(需要 matplotlib、Pillow);第 3、4 章的部分圖直接取 ../final_build/fig(簡報 v2 的圖)
python3 figs_v2.py /tmp/fin /tmp/web/method_kline_peak/web/screenshots ../final_build/fig ./out
# 3. Word(需要 npm 的 docx)
node build_report_v2.js ./out ./out/report.docx
# 4. LibreOffice 更新目錄 / 圖目錄 / 表目錄頁碼,另存 docx;再統一字型、頁首頁尾距離與分節設定
python3 lo_update.py ./out/report.docx ./out/tmp.pdf ./out/report_lo.docx
python3 fix_fonts.py ./out/report_lo.docx ../專題研究報告_v2.docx
# (檢查用)python3 lo_update.py ../專題研究報告_v2.docx /tmp/check.pdf ""   PDF 由使用者在 Word 轉出,不交付
```

## 數字來源(final 分支 `method_kline_peak/results/`)

| 報告中的數字 | 檔案 |
|---|---|
| 逐年混淆矩陣、macro-F1、找到率、命中率、判反(表 4.2、4.3,圖 4.1、4.2);三年合計由三個矩陣相加 | `confusion_2024_2026_tw200.json` |
| 只用規則 vs 本系統、隨機基準、訊號少 18.6%、規則外 49.6%(表 4.4,圖 4.3,4.1.3 節) | `baseline_rule_vs_mainline_2024_2026.json`(三年合計由逐年個數相加) |
| 聯發科 2025(表 4.5,圖 4.4) | `per_stock_mainline_2024_2026.json` 的 `每檔/2025/2454.TW`;圖取自 `outputs_2454_2025_tw200.csv`(簡報 v2 同一張) |
| 30 種策略、最好 / 第 2 / 最差、0050、168 檔等權、成本 0.585%(表 4.6,圖 4.5) | `backtest_strategies_2024_2025.json` |
| 每天前 3 檔、持有 5 天的逐年報酬與勝率;剔除低波動 48 檔 | `backtest_long_only_tw200.json` |
| 實測時間、記憶體、測試環境(表 4.7) | `timing_mainline.json` |
| 29 維特徵示意(圖 3.2、3.3,聯發科 2025-02-26) | `common/cache/yf_2026/2454.TW.parquet` |
| 網頁判斷與研究一致(4.5.3 節) | 網頁分支 `method_kline_peak/web/samples/research_match.json` |

網頁截圖:claude/kline-peak-web-app 7ce69e3 的 `screenshots/`,只裁切不塗改;個股頁從股票列開始裁(不含快捷鈕列)。

| 圖 | 來源與裁切框(x0, y0, x1, y1,px) |
|---|---|
| 圖 4.6 今日判斷 | today_desktop (0, 0, 1280, 926) |
| 圖 4.7 個股查詢 2454 | stock_pool_2454_desktop (60, 240, 1220, 1126) |
| 圖 4.8 成績追蹤 | track_desktop (0, 0, 1280, 1328) |
| 圖 A.1 今日判斷(手機) | today_mobile (0, 0, 780, 1460),縮為 50% |
| 圖 A.2 3374 精材 | stock_otc_3374_desktop (60, 240, 1220, 700) |
| 圖 A.3 研究發現 | findings_desktop (0, 0, 1280, 860) |
| 圖 A.4 方法與說明 | about_desktop (0, 0, 1280, 820) |

本機檢查用的 PDF 在沒有標楷體的環境轉出時,以 fontconfig 把「標楷體」對應到 AR PL UKai TW;Times New Roman 由 Liberation Serif 代替。
