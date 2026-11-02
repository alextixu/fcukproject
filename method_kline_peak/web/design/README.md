# 網頁設計稿(可行性評估 + UI/UX 示意,2026-11-02)

- `feasibility.md`:可行性評估(資料、模型、每日判斷、池外股票、建議寫法、法規、架構、工作量、結論)。
- `mockup.html`:可以點的靜態示意稿(假資料),直接用瀏覽器開。網址加 `#today`、`#stock/2330`、`#track`、`#about` 可跳到各頁。
- `screenshot.js`:截圖腳本,`node screenshot.js <本資料夾絕對路徑>`。手機版截圖把底部導覽列改成放在頁尾,實際畫面是固定在螢幕底部。

| 截圖 | 內容 |
|---|---|
| `shot_today_*.png` | ① 今日判斷:判低點 / 判高點前 3 檔、方法切換 |
| `shot_stock_2330_*.png` | ② 個股查詢(池內):判斷、各類分數、兩方法比較、K 線與過去訊號對錯、建議 |
| `shot_stock_outpool_2618_*.png` | ② 個股查詢(池外,黃色警示) |
| `shot_stock_lowvol_2412_*.png` | ② 個股查詢(低波動股,判斷不適用) |
| `shot_search_autocomplete_*.png` | ② 自動完成 |
| `shot_track_*.png` | ③ 成績追蹤:命中率、事後對答案明細 |
| `shot_about_*.png` | ④ 方法與說明:研究結果(實際數字)、回測摘要、免責 |

`*` = `desktop`(1280 寬)或 `mobile`(390 寬)。
