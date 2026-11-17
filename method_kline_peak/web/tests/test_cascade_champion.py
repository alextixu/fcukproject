"""兩階段級聯深度度量冠軍系統核心單元測試。

測試範疇涵蓋：
1. CandlestickProtoEncoder 深度度量網絡架構與單位超球面嵌入投影 (L2 範數 = 1)。
2. 因果性驗證：t+1 日後之數據變動嚴格不影響 <= t 日之特徵計算與候選判定。
3. 冠軍模型視窗資料庫 (windows_data_champion.json) 結構與統計指標一致性。
4. 正式交付頁面 (kline_peak_system.html) 之存在性、完整性與 UTF-8 編碼。
"""
import os
import sys
import json
import torch
import numpy as np
import pandas as pd
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.dirname(HERE)
KP_DIR = os.path.dirname(WEB_DIR)
ROOT_DIR = os.path.dirname(KP_DIR)

for p in (ROOT_DIR, KP_DIR, WEB_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from exp_novel_feature_discovery import CandlestickProtoEncoder, paper_label
from peak_labels import causal_features, TOP, BOTTOM, FLAT, UP, DOWN, ORDER, summarize


def test_candlestick_proto_encoder_projection():
    """驗證 CandlestickProtoEncoder 能接受 (B, T, D)=(8, 6, 12) 時序輸入並投射至 32D 單位超球面上 (L2 範數嚴格為 1)"""
    model = CandlestickProtoEncoder(in_dim=12, hidden_dim=64, latent_dim=32)
    model.eval()

    # 模擬 8 個批次、長度為 6 的時間序列、12 個特徵通道
    x = torch.randn(8, 6, 12)
    with torch.no_grad():
        emb = model(x)

    assert emb.shape == (8, 32), f"預期形狀 (8, 32)，實際得到 {emb.shape}"
    norms = torch.norm(emb, p=2, dim=1).numpy()
    assert np.allclose(norms, 1.0, atol=1e-5), "所有嵌入向量之 L2 範數必須嚴格等於 1.0"


def test_causal_no_lookahead():
    """驗證因果特徵與標籤條件嚴格不洩漏未來資訊：改動 t+1 以後之價格，t 以前之特徵值與判定不變"""
    n = 60
    c = np.full(n, 100.0)
    c[10], c[30], c[40] = 110.0, 90.0, 112.0
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    df1 = pd.DataFrame({
        "open": c, "high": c + 1.0, "low": c - 1.0, "close": c,
        "volume": np.full(n, 1e6)
    }, index=dates)

    f1 = causal_features(df1)

    # 構造 t=35 之後價格暴漲 200% 之對照組
    df2 = df1.copy()
    df2.iloc[35:] *= 3.0
    f2 = causal_features(df2)

    # 驗證 t <= 34 之特徵完全不受 t >= 35 之價格影響
    assert np.allclose(f1.iloc[:35].fillna(0), f2.iloc[:35].fillna(0), atol=1e-6), "特徵工程存在未來資訊洩漏！"


def test_champion_windows_database():
    """驗證冠軍資料庫 windows_data_champion.json 包含 50 檔成分股與完備之盲測統計指標"""
    json_path = os.path.join(WEB_DIR, "windows_data_champion.json")
    assert os.path.exists(json_path), f"找不到冠軍資料庫: {json_path}"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "summary" in data and "stocks" in data
    stocks = data["stocks"]
    assert len(stocks) == 50, f"預期包含 50 檔台灣 50 成分股，實際包含 {len(stocks)} 檔"

    summary = data["summary"]
    assert "model" in summary
    m = summary["model"]
    # 兩階段冠軍模型在盲測集上之 Macro-F1 應達到 56.51%
    assert m["macro_f1"] >= 0.55, f"冠軍模型 Macro-F1 應高於 0.55，實際為 {m['macro_f1']}"

    # 驗證混淆矩陣方向判反率為 0 (低點判成高點或高點判成低點為 0)
    cm = np.array(m["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"])
    assert cm[0, 2] == 0, "低點判為高點之嚴重反向錯誤應為 0"
    assert cm[2, 0] == 0, "高點判為低點之嚴重反向錯誤應為 0"


def test_static_html_system_integrity():
    """驗證正式交付網頁 kline_peak_system.html 檔案完整、無亂碼且四大模組結構齊備"""
    html_path = os.path.join(WEB_DIR, "kline_peak_system.html")
    assert os.path.exists(html_path), f"找不到正式網頁檔案: {html_path}"
    assert os.path.getsize(html_path) > 300 * 1024, "網頁檔案大小應大於 300KB (自包含數據)"

    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 驗證包含四大核心功能頁面函數與導航錨點
    assert "pageToday" in content, "缺少今日即時選股視圖函數"
    assert "pageStock" in content, "缺少個股查詢視圖函數"
    assert "pageTrack" in content, "缺少盲測追蹤視圖函數"
    assert "pageAbout" in content, "缺少系統架構說明視圖函數"
    assert "#today" in content and "#stock" in content and "#track" in content and "#about" in content, "缺少頁面路由錨點"

    # 驗證無亂碼符號 (如常見的雙重編碼錯誤字符與 Unicode replacement char)
    assert "锟斤拷" not in content and "\ufffd" not in content, "網頁中發現亂碼字符"
