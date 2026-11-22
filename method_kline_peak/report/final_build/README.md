# 專題發表簡報與海報(final 分支的方法)

輸出:`../final_presentation.pptx`(12 頁,備忘稿為逐字講稿)、`../final_poster.pptx` / `.pdf` / `.png`(A1 直式)。
方法與數字只用 `final` 分支的結果檔,不訓練、不重跑模型。

```bash
git archive origin/final | tar -x -C /tmp/fin                     # 取 final 分支(不 merge)
python3 figs_final.py /tmp/fin ./fig [只用規則的結果 json]          # 圖 + fig/numbers.json(三年合計等數字)
PPTX_SKILL=<pptx skill 目錄> node build_presentation.js ../final_presentation.pptx
node build_poster.js ../final_poster.pptx
soffice --headless --convert-to pdf ../final_poster.pptx            # 再用 pdftoppm 轉 PNG
```

數字來源(final 分支 `method_kline_peak/results/`):
- `confusion_2024_2026_tw200.json`:逐年 macro-F1、找到率、命中率、判反;三年合計由三個混淆矩陣相加算出。
- `per_stock_mainline_2024_2026.json`(`每檔/2025/2454.TW`)與 `outputs_2454_2025_tw200.csv`:聯發科 2025。
- `backtest_strategies_2024_2025.json`:30 種策略、0050、成本。
- `common/cache/yf_2026/2454.TW.parquet`:第 5 頁 / 成果 1 的 6 根 K 線(2025-02-26)。

待補:只用規則的數字(`baseline_rule_vs_mainline_2024_2026.json`)、實測時間(`timing_mainline.json`)、網頁截圖。
