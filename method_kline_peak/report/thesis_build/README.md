# 專題研究報告的產生方式

不跑實驗、不訓練:數字讀 `results/` 的 json(分支 claude/kline-peak-predict-tool)與 README 表格,截圖讀分支 claude/kline-peak-web-app。

```bash
# 1. 取兩個分支的檔案(不 merge)
git archive origin/claude/kline-peak-predict-tool method_kline_peak | tar -x -C /tmp/pt
git archive origin/claude/kline-peak-web-app method_kline_peak/web | tar -x -C /tmp/web
# 2. 資料與圖(需要 matplotlib、Pillow)
python3 figs.py /tmp/pt/method_kline_peak /tmp/web/method_kline_peak/web/screenshots ../ ./out
# 3. Word(需要 npm 的 docx)
node build_report.js ./out ./out/report.docx
# 4. LibreOffice 更新目錄 / 圖目錄 / 表目錄頁碼,另存 docx;再統一字型、修正頁首頁尾距離與分節設定
python3 lo_update.py ./out/report.docx ./out/tmp.pdf ./out/report_lo.docx
python3 fix_fonts.py ./out/report_lo.docx ../專題研究報告.docx   # 也會加上「開啟時更新欄位」
# (檢查用)python3 lo_update.py ../專題研究報告.docx /tmp/check.pdf ""   PDF 由使用者在 Word 轉出,不交付
```

本機檢查用的 PDF 在沒有標楷體的環境轉出時,以 fontconfig 把「標楷體」對應到 AR PL UKai TW(fonts-arphic-ukai);Times New Roman 由 Liberation Serif 代替。
