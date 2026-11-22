# 專題發表簡報與海報(final 分支的方法)

輸出(v2;final 分支原有的簡報為 v1):`../專題簡報_v2.pptx`(12 頁,備忘稿為逐字講稿)、`../專題海報_v2.pptx` / `.pdf` / `.png`(A1 直式)。
方法與數字只用 `final` 分支的結果檔,不訓練、不重跑模型。

```bash
git archive origin/final | tar -x -C /tmp/fin                     # 取 final 分支(不 merge)
python3 figs_final.py /tmp/fin ./fig /tmp/fin/method_kline_peak/results/baseline_rule_vs_mainline_2024_2026.json   # 圖 + fig/numbers.json
PPTX_SKILL=<pptx skill 目錄> node make_presentation_v2.js
node make_poster_v2.js
soffice --headless --convert-to pdf ../專題海報_v2.pptx            # 再用 pdftoppm 轉 PNG
```

數字來源(final 分支 `method_kline_peak/results/`):
- `confusion_2024_2026_tw200.json`:逐年 macro-F1、找到率、命中率、判反;三年合計由三個混淆矩陣相加算出。
- `per_stock_mainline_2024_2026.json`(`每檔/2025/2454.TW`)與 `outputs_2454_2025_tw200.csv`:聯發科 2025。
- `backtest_strategies_2024_2025.json`:30 種策略、0050、成本。
- `common/cache/yf_2026/2454.TW.parquet`:第 5 頁 / 成果 1 的 6 根 K 線(2025-02-26)。

- `baseline_rule_vs_mainline_2024_2026.json`:只用規則 vs 本系統(三年合計由逐年數字加總)。
- `timing_mainline.json`:實測時間與記憶體(第 3、10 頁;寫死在 make_presentation_v2.js 的 TM)。

網頁截圖:claude/kline-peak-web-app 4832aa2 的 today_desktop、stock_pool_2454_desktop、track_desktop(資料到 2026-11-20)。
裁切框(x0, y0, x1, y1,單位 px):簡報第 11 頁 web_today = today (0,0,1280,546)、web_2454_search = 2454 (60,240,1220,640)、web_2454_year = 2454 (60,648,1220,1126)、web_track = track (0,0,1280,590);海報成果二 web_p_today = today (0,0,1280,960)、web_p_2454 = 2454 (60,250,1220,1120)、web_p_track = track (0,0,1280,960)。
