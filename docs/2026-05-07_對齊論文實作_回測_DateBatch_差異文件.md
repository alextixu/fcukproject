# 2026-05-07　對齊論文實作 + 回測 + DateGroupedBatchSampler + 差異文件

> **【2026-09-21 警告】這份文件裡的「台灣 50 / tw50」股票池不是臺灣 50 指數的成分股**,而是一份 2026-05-28 手動補齊、沒有日期與出處的 50 檔大型股名單(和任何一天的官方成分股差 7 ~ 18 檔)。**相關數字暫不可引用**;「tw50 等權」對照組用的也是同一份名單,所以「2021 ~ 2025 連續五年輸等權」等結論一併暫停使用。詳見 [2026-09-21_repo的TW50名單不是官方成分股_出處與受影響的結果](2026-09-21_repo的TW50名單不是官方成分股_出處與受影響的結果.md)。

**做了什麼**(同日 5 個 commit)
1. `9265b59` 依論文 Section 3 重寫管線:PIP(Eq.1)、VG(Eq.3)、BFS 子圖 + 正規化、Conv1(g×F)→Conv2(5×1)→Conv3→FC 84→32→Self-Attention(Eq.7-9)→2 類;加入 2024 回測。
2. `7d02948` 寫 `needchange.md`:列出實作與論文不同之處。
3. `8f054fb` 實作 **DateGroupedBatchSampler**(同一交易日的股票同一批,讓 self-attention 跨股票),並移除殘差連接。
4. `4de05da` 以真實台灣 50 資料更新回測圖。
5. `86731a8` 寫 `paper_analysis.md`:論文技術逐條清單(PIP / 9 指標 / VG / 子圖 / 模型 / 訓練 / 實驗設定)。

**為什麼**
- 先把「論文寫了什麼」和「我們做了什麼」白紙黑字對齊,之後所有差距才有辦法歸因。

**產出**
- `core/`(當時在根目錄)的 pip_algorithm / vg_graph / subgraph / indicators / model / train / dataset、`backtest.py`、`paper_analysis.md`、`needchange.md`。

**備註**
- DateGroupedBatchSampler 這天就寫了,但直到 07-24 才發現它是解決「批次 attention 洩漏未來」的關鍵,並成為標準協定。
