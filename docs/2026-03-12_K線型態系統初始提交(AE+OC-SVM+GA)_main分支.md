# 2026-03-12 ~ 03-19　K 線型態預測系統初始提交(系統 A,main 分支)

**做了什麼**
- 03-12 `Initial commit: K-line pattern prediction system (AE + OC-SVM + GA)`——**整個專題最早的程式提交**。
- 03-18 / 03-19:README、20 種 K 線型態辨識、Tkinter GUI 改進、多 K 型態與高級型態。

**方法(當時)**
- yfinance 下載台灣前 50 大 OHLCV → K 線型態 → Autoencoder 壓縮 → One-Class SVM 建看漲 / 看跌模型 → 回測。

**產出**
- `KLINE/fcukproject/`(GitHub `lintaixu/fcukproject` main 分支)。
