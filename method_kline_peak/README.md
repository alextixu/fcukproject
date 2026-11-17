# method_kline_peak — 以深度學習為基礎之自動化 K 線高低點辨識系統

本專案為自動化 K 線形態轉折辨識系統，專注於二級市場波段轉折點（局部高點 Peak 與局部低點 Trough）之精準判定。系統採用**兩階段級聯深度度量架構**（Two-Stage Cascade Deep Metric Architecture），結合因果特徵工程、超球面角度邊界流形學習與時序軟抑制演算法，嚴格維持「當日精準（Exact Day $t$, $\delta=0$）」之即時決策約束，杜絕未來資訊洩漏。

---

## 核心技術架構

系統整體由以下四大核心模組構成：

```
[市場原始數據]
       │ (OHLCV 日線 + 0050.TW 大盤基準)
       ▼
[特徵工程與度量學習] ───► Top-24 菁英因果特徵庫 + 32D ArcFace 超球面幾何嵌入
       │
       ▼
[Stage 1 粗篩產生器] ───► 局部極值必要條件過濾 (過濾 85.5% 平盤，維持 100% 轉折召回)
       │
       ▼
[Stage 2 難例專屬判別器] ─► LightGBM 梯度提升決策樹 (專注於高難度假信號判別)
       │
       ▼
[時序後處理濾波] ─────► 一維高斯軟抑制 (Gaussian Soft-NMS) + 單邊市場恐慌熔斷
       │
       ▼
[正式交付輸出] ───────► 單一獨立、無相依、零 CORS 限制之視覺化系統 (kline_peak_system.html)
```

1. **嚴格因果極值標籤體系（Causal Peak Labels）**：
   - 採對稱 11 日收盤價視窗 $W_t = \{C_{t-5}, \dots, C_{t+5}\}$。
   - 決策時點嚴格限制於第 $t$ 日收盤，特徵計算僅能使用 $\le t$ 之市場可觀測資訊。
2. **深度度量特徵抽取（CandlestickProtoEncoder）**：
   - 多尺度 1D-CNN（卷積核 1 與 3）捕捉微觀跳動與跨日動量。
   - 多頭時序自注意力機制（Temporal Attention）自適應分配權重。
   - ArcFace 角度邊界損失函數最大化類內緊湊度，產出 32D 單位超球面嵌入表徵。
3. **兩階段級聯決策機制（Two-Stage Cascade Architecture）**：
   - **Stage 1 粗篩器**：藉由左側 5 日因果極值條件，快速排除 85.5% 的非極值平盤樣本。
   - **Stage 2 難例判別器**：融合 32D 深度度量嵌入、大盤頂背離特徵與非流動性指標，對難例負樣本進行精細化三分類。
4. **一維高斯軟抑制與環境防護（Gaussian Soft-NMS & Circuit Breaker）**：
   - 連續時間軸高斯衰減抑制連續日的群聚誤報，消除信號粘連。
   - 大盤恐慌熔斷機制於系統性單邊暴跌時強制凍結高點買入/做多信號。

---

## 模組檔案清單

| 模組檔案名稱 | 核心職責說明 |
| :--- | :--- |
| **`build_kline_peak_system.py`** | 一鍵建構自包含、無亂碼、零 CORS 限制之正式交付網頁（`kline_peak_system.html`） |
| **`export_champion_windows.py`** | 執行兩階段級聯冠軍模型推論，導出逐日預測與視窗序列庫（`windows_data_champion.json`） |
| **`exp_two_stage_cascade.py`** | 兩階段級聯模型實證評估腳本，執行盲測驗證並輸出評估指標與混淆矩陣圖表 |
| **`exp_novel_feature_discovery.py`** | 前沿因果特徵庫構建、32D 超球面流形度量抽取與大盤背離特徵工程模組 |
| **`exp_fuzzy_tolerance_and_deep_temporal.py`** | 實戰時序容差分析（$\delta=0$ 與 $\delta=\pm 1$ 日）與微觀誤差時間軸前導性統計模組 |
| **`peak_labels.py`** | 11 日對稱窗格極值標籤定義、因果特徵過濾、混淆矩陣指標統計計算工具庫 |
| **`deep_pattern_net.py`** | 多尺度卷積、時序注意力與超球面投影網絡之 PyTorch 定義 |
| **`feasibility.py`** | 基準可行性評估與因果特徵邊界檢驗模組 |
| **`web/`** | 視覺化系統資源、靜態前端首頁（`site/index.html`）與伺服器控制模組（`run.py`） |
| **`report/`** | 專題研究論文（`.docx` / `.md`）與全版本演進迭代報告（`evolution_history_and_design_iterations_report.md`） |
| **`results/`** | 冠軍模型與各消融實驗評估數據（`.json`）與高解析度圖表（`.png`） |

---

## 實證成果摘要

在台灣 50（TW50）指數成分股獨立凍結盲測集（2025-01-01 至 2026-09-30，共 $N=20,139$ 筆樣本）上，兩階段級聯系統之實證表現如下：

| 評測條件與指標 | 傳統技術分析規則 | 兩階段級聯深度度量系統 | 改善幅度 |
| :--- | :---: | :---: | :---: |
| **整體準確率（Accuracy）** | 68.20% | **77.33%** | **+9.13%** |
| **Macro-F1** | 50.00% | **56.51%** | **+6.51%** |
| **低點精確率（Prec-Lo）** | 32.00% | **36.70%** | **+4.70%** |
| **高點精確率（Prec-Hi）** | 25.35% | **31.20%** | **+5.85%** |
| **鑑別度增益（$\Delta\text{Keep}$）** | 0.00% | **+13.54%** | **+13.54%** |
| **高低點方向判反率** | 0.00% | **0.00%** | **維持 0 誤判** |
| **容差模式（$\delta=\pm 1$ 日）命中率** | — | **低點 56.02% / 高點 46.72%** | **大幅領先** |

---

## 系統執行與重現指南

### 1. 環境需求與依賴安裝
```bash
pip install -r requirements.txt
```

### 2. 執行兩階段級聯盲測驗證
```bash
python3 method_kline_peak/exp_two_stage_cascade.py
```

### 3. 執行實戰時序容差評估
```bash
python3 method_kline_peak/exp_fuzzy_tolerance_and_deep_temporal.py
```

### 4. 重新導出冠軍推論視窗序列
```bash
python3 method_kline_peak/export_champion_windows.py
```

### 5. 一鍵生成正式交付網頁系統
```bash
python3 method_kline_peak/build_kline_peak_system.py
```
執行後將於 `method_kline_peak/web/` 下產出自包含之 `kline_peak_system.html`，並同步覆蓋 `method_kline_peak/web/site/index.html`。

### 6. 本地啟動網頁伺服器預覽
```bash
python3 method_kline_peak/web/run.py serve --port 8080
```
或直接利用 Python 內建 HTTP 伺服器：
```bash
python3 -m http.server 8080 --directory scratch/kline-peak-web-app/method_kline_peak/web
```
開啟瀏覽器訪問 `http://localhost:8080/kline_peak_system.html` 即可瀏覽完整四大功能頁面（今日即時選股、個股互動查詢、盲測追蹤、方法說明）。
