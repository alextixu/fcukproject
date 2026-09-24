# 2026-09-21 AE + XGBoost 流程圖頁;Chart-GCN v1.7 重新啟動

## AE + XGBoost 流程圖頁
- 網址:https://claude.ai/artifact/6j4hxsYTtskPswrUbt33qW
- 做法和 Chart-GCN 架構圖頁相同(資料驅動):`docs/_aexgb_state.json`(groups / versions / roadmap / stages / concerns)+ `docs/_aexgb_page_template.html` → `python3 docs/_build_aexgb_page.py` → `docs/aexgb_architecture.html` → 重新發佈(同路徑 = 同網址)。
- 內容:目前版本、分岔總覽圖(242 指標 → 支線甲特徵篩選 95 欄 / 支線乙自編碼器 17 欄 → 合併 112 欄 → XGBoost → 名次 → 三檔輪動 → 回測 → 每日頁)、11 站流程圖與 25 項問題(右欄)、逐年走動表、判斷、版本記錄、候選待辦。
- 版本編號(本頁新訂):v1.0 = 95 欄 → XGBoost → 三檔輪動(09-14);v1.1 = 加自編碼器 17 欄(09-15);v1.2 = 加 3×ATR 停損 + 30% 停利(09-15,目前採用)。只做檢驗、沒改系統的(09-15 深夜四項檢驗、09-18~20 特徵篩選與超參數網格、09-20 每日頁)記為「檢驗 / 頁面」,不升版本。
- 問題狀態:open 未處理 / measured 已量化 / nogain 已驗證沒有改善 / fixed 已修 / none 純說明。
- 數字全部取自既有 docs(09-14、09-15、09-20),沒有重跑任何實驗。

## Chart-GCN v1.7(tw300 五筆)
- 09-21 03:16 啟動的批次在第一筆建資料集 34% 時中斷(03:18),五筆皆無結果;journal 無 OOM,研判是前一個對話結束時背景程序被一併收掉。
- 09-21 12:48 以 `setsid nohup` 重新啟動(`bash test/run_v17_pools_batch.sh "tw300" 42`,`TW_CACHE_DIR=common/cache/yf_2026`),已有結果的 tag 會自動跳過。批次記錄 `method_chartgcn/logs/v17_batch_tw300.log`。

## 兩個頁面加「歷史疑慮」區(使用者要求)
- 規則:status 為 fixed / done / nogain 的疑慮視為結案,不再放在流程圖右欄,該站只留一行連結;全部收進「歷史疑慮」區,點開可看「原本的疑慮 → 改了什麼(取自版本記錄的 changes)→ 結果」。open / testing / measured 仍留在圖上。
- Chart-GCN 頁:7 項進歷史(已修 D3、S1、P1;試過沒有改善 I1、S2、G2;先前已處理 M1),圖上剩 6 項;「我的判斷」裡過時的「四項都沒跑過實驗」改成 v1.1 ~ v1.6 的實際結果。
- AE + XGBoost 頁:2 項進歷史(P1 特徵篩選、X1 超參數,皆為試過沒有改善);A1(自編碼器無增益)改標「已量化」、留在圖上,因為它是現存事實不是結案的疑慮。
