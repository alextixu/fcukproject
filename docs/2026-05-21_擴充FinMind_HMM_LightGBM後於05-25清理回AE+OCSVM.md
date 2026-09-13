# 2026-05-21 ~ 05-25　系統 A 大擴充後全數清理

**做了什麼**
- 05-21(5 個 commit):加入 FinMind data provider、Regime HMM、LightGBM specialists、Meta-Model、投資組合優化與風險引擎。
- 05-25(5 個 commit):多分支合併後**全部砍掉**——「清理 main:僅保留 AE + OC-SVM 系統(系統B)」「僅保留主程式 kline_pattern_search.py」「移除參數搜尋功能」。

**為什麼**
- 野心過大、無法在專題時程內驗證;決定系統 A 只守 AE + OCSVM 一條線,把資源留給與論文系統(Chart-GCN)的對照。

**備註**
- 同期(05-28)Chart-GCN 分支做第一次網格搜尋。
