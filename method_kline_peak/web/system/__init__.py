"""每日高 / 低點判斷網頁的後端批次(2026-11-02 起)。

模組
  config      路徑與常數
  datasource  K 線快取與每日更新(yfinance 還原價;沒有網路時只讀快取)
  universe    股票分類:池內 / 池外 / 低波動 / 不支援
  features    即時特徵(只用 t−5 ~ t)與事後對答案
  model       正式模型的訓練、存檔、推論(主軸、Stacking 邏輯迴歸)
  store       每日判斷存檔(寫過不覆蓋)與對答案存檔
  publish     產生前端讀的 JSON
  pipeline    把上面串起來:每日批次、回放
"""
