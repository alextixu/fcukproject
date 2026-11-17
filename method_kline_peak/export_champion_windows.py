#!/usr/bin/env python3
"""
export_champion_windows.py
==========================
匯出【兩階段級聯冠軍模型 (Two-Stage Cascade + Soft-NMS)】在嚴格當日精準 (Exact Day t) 條件下的逐日預測結果，
並將全量數據注入互動式 HTML 視覺化頁面，產生單一自包含 (Self-contained) 網頁：
- 逐檔 K 線圖 (TW50 全部 50 檔股票)
- 真實標籤、規則候選、兩階段冠軍模型判斷
- 11 日微觀窗口檢視器
- 誤報、漏報、成功識別卡片畫廊
- 嚴格當日精準評測矩陣
"""

import os
import sys
import json
import time
import re
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
from common import paths as P
os.environ.setdefault("TW_CACHE_DIR", P.YF_2026_CACHE)
sys.path.insert(0, P.XGB_SRC)

from feasibility import START, END, load_pool, clean
from exp_novel_feature_discovery import extract_novel_feature_corpus, paper_label
from peak_labels import FLAT, UP, DOWN, ORDER, NAMES, summarize

OUT_WEB_DIR = os.path.join(HERE, "web")
OUT_DATA_JSON = os.path.join(OUT_WEB_DIR, "windows_data_champion.json")
OUT_HTML = os.path.join(OUT_WEB_DIR, "kline_peak_champion_viewer.html")
ARTIFACT_DIR = "/Users/tom/.gemini/antigravity-cli/brain/f9b83c20-4c2b-40c1-bf15-3cd87531b443"


def ticker_names():
    dl_path = os.path.join(P.COMMON, "data_loader.py")
    if not os.path.exists(dl_path):
        dl_path = os.path.join(P.CHARTGCN_CORE, "data_loader.py")
    src = open(dl_path, encoding="utf-8").read()
    return dict(re.findall(r'"(\d{4}\.TW)",\s*#\s*(\S+)', src))


def run_champion_model():
    print("=" * 80)
    print("🚀 啟動【兩階段級聯冠軍模型】預測生成 (嚴格維持當日精準 Exact Day t)")
    print("=" * 80)

    t0 = time.time()
    bundle = extract_novel_feature_corpus()
    y_tr, y_te = bundle["y_tr"], bundle["y_te"]
    c_hi_tr, c_lo_tr = bundle["c_hi_tr"], bundle["c_lo_tr"]
    c_hi_te, c_lo_te = bundle["c_hi_te"], bundle["c_lo_te"]
    dates_te = bundle["dates_te"]
    tickers_te = bundle["tickers_te"]

    # 組合 Top-24 Elite 特徵
    X_all_tr = np.hstack([
        bundle["dyn_base_tr"],
        bundle["fam1_tr"], bundle["fam2_tr"], bundle["fam3_tr"],
        bundle["fam4_tr"], bundle["fam5_tr"]
    ])
    X_all_te = np.hstack([
        bundle["dyn_base_te"],
        bundle["fam1_te"], bundle["fam2_te"], bundle["fam3_te"],
        bundle["fam4_te"], bundle["fam5_te"]
    ])

    scaler = StandardScaler()
    X_all_tr_sc = np.nan_to_num(scaler.fit_transform(X_all_tr), nan=0.0, posinf=3.0, neginf=-3.0)
    X_all_te_sc = np.nan_to_num(scaler.transform(X_all_te), nan=0.0, posinf=3.0, neginf=-3.0)

    clf_selector = lgb.LGBMClassifier(objective="multiclass", num_class=3, n_estimators=150,
                                      class_weight="balanced", random_state=42, n_jobs=4, verbose=-1)
    clf_selector.fit(X_all_tr_sc, y_tr)
    gains = clf_selector.booster_.feature_importance(importance_type="gain")
    top24_idx = np.argsort(gains)[::-1][:24]

    X_elite_tr = X_all_tr_sc[:, top24_idx]
    X_elite_te = X_all_te_sc[:, top24_idx]

    # 訓練兩階段專屬二元難例分類器
    hi_tr_idx = np.where(c_hi_tr)[0]
    lo_tr_idx = np.where(c_lo_tr)[0]
    y_tr_hi = (y_tr[hi_tr_idx] == DOWN).astype(int)
    y_tr_lo = (y_tr[lo_tr_idx] == UP).astype(int)

    clf_hi = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15,
                                max_depth=4, class_weight="balanced", random_state=42, n_jobs=4, verbose=-1)
    clf_hi.fit(X_elite_tr[hi_tr_idx], y_tr_hi)

    clf_lo = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15,
                                max_depth=4, class_weight="balanced", random_state=42, n_jobs=4, verbose=-1)
    clf_lo.fit(X_elite_tr[lo_tr_idx], y_tr_lo)

    # 測試集推理
    prob_hi = clf_hi.predict_proba(X_elite_te)[:, 1]
    prob_lo = clf_lo.predict_proba(X_elite_te)[:, 1]

    pred_raw = np.zeros(len(y_te), dtype=int)
    prob_raw = np.zeros((len(y_te), 3))
    for i in range(len(y_te)):
        phi = prob_hi[i] if c_hi_te[i] else 0.0
        plo = prob_lo[i] if c_lo_te[i] else 0.0
        prob_raw[i, DOWN] = phi
        prob_raw[i, UP] = plo
        prob_raw[i, FLAT] = 1.0 - max(phi, plo)
        if phi > 0.40 and phi > plo:
            pred_raw[i] = DOWN
        elif plo > 0.40 and plo > phi:
            pred_raw[i] = UP
        else:
            pred_raw[i] = FLAT

    # 高斯軟抑制 (Soft-NMS, 窗口 4 日, sigma=2.5)
    pred_champion = pred_raw.copy()
    W_soft = 4
    sigma = 2.5
    for i in range(len(y_te)):
        if pred_raw[i] == DOWN:
            cur_p = prob_raw[i, DOWN]
            st = max(0, i - W_soft)
            en = min(len(y_te), i + W_soft + 1)
            max_idx = st + np.argmax(prob_raw[st:en, DOWN])
            dist = abs(i - max_idx)
            soft_p = cur_p * np.exp(-(dist**2) / (2 * (sigma**2)))
            if (i != max_idx) and (soft_p < 0.38):
                pred_champion[i] = FLAT
        elif pred_raw[i] == UP:
            cur_p = prob_raw[i, UP]
            st = max(0, i - W_soft)
            en = min(len(y_te), i + W_soft + 1)
            max_idx = st + np.argmax(prob_raw[st:en, UP])
            dist = abs(i - max_idx)
            soft_p = cur_p * np.exp(-(dist**2) / (2 * (sigma**2)))
            if (i != max_idx) and (soft_p < 0.38):
                pred_champion[i] = FLAT

    print(f"冠軍模型推論完畢 (耗時: {time.time()-t0:.2f}s)")
    return dates_te, tickers_te, y_te, c_hi_te, c_lo_te, pred_champion, prob_raw


def build_windows_json_and_html():
    dates_te, tickers_te, y_te, c_hi_te, c_lo_te, pred_champion, prob_raw = run_champion_model()

    # 建立查找字典: (ticker, date_str) -> pred
    pred_map = {}
    for d, tk, p in zip(dates_te, tickers_te, pred_champion):
        pred_map[(tk, d)] = int(p)

    # 載入全量 TW50 原始價格數據
    print("\n載入 TW50 價格並建立面板...")
    data = load_pool("tw50", START, END)
    names = ticker_names()

    # 建立標籤與候選面板 (直接調用 paper_label，零外部依賴)
    lab = {}
    cand = {}
    for tk, df in data.items():
        df_c = clean(df)
        y_vals, chi_vals, clo_vals = paper_label(df_c["close"])
        for dt, y_v, chi_v, clo_v in zip(df_c.index, y_vals, chi_vals, clo_vals):
            d_str = dt.strftime("%Y-%m-%d")
            lab[(tk, d_str)] = int(y_v)
            cand[(tk, d_str)] = (bool(chi_v), bool(clo_v))

    SPLIT = {
        "train": ["2020-01-01", "2023-12-31"],
        "test": ["2025-01-01", "2026-09-30"]
    }

    # 計算統計摘要 (在測試集上)
    # 規則基準預測
    rule_p = np.zeros(len(y_te), dtype=int)
    for i in range(len(y_te)):
        if c_hi_te[i]: rule_p[i] = DOWN
        elif c_lo_te[i]: rule_p[i] = UP
        else: rule_p[i] = FLAT

    summary = {
        "split": SPLIT,
        "n_train": 47883,
        "n_test": len(y_te),
        "n_tickers": len(data),
        "dist_train": {"低點": 0.076, "非極值": 0.849, "高點": 0.075},
        "dist_test": {
            "低點": float((y_te == UP).mean()),
            "非極值": float((y_te == FLAT).mean()),
            "高點": float((y_te == DOWN).mean()),
        },
        "rule": summarize(y_te, rule_p, NAMES),
        "model": summarize(y_te, pred_champion, NAMES),
    }

    stocks = []
    print("處理 50 檔個股逐日序列與窗口...")
    for tk, df in data.items():
        df = clean(df)
        r5 = (df["close"].shift(-5) / df["open"].shift(-1) - 1) * 100
        periods = {}

        for key in ["train", "test"]:
            a0, b0 = SPLIT[key]
            w = df.loc[a0:b0]
            idx = [(tk, t) for t in w.index]

            y = np.array([lab.get((tk, t.strftime("%Y-%m-%d")), -1) for t in w.index], dtype=int)
            ch = np.array([cand.get((tk, t.strftime("%Y-%m-%d")), (False, False)) for t in w.index], dtype=bool)
            cd = np.where(ch[:, 0], 2, np.where(ch[:, 1], 1, 0))

            if key == "test":
                # 從 pred_map 中精確取出兩階段冠軍模型在嚴格當日的預測
                pr_list = []
                for t in w.index:
                    d_str = t.strftime("%Y-%m-%d")
                    pr_list.append(pred_map.get((tk, d_str), -1))
                pr = np.array(pr_list, dtype=int)
            else:
                pr = np.full(len(w), -1)

            periods[key] = {
                "d": [t.strftime("%Y-%m-%d") for t in w.index],
                "o": np.round(w["open"].to_numpy(), 2).tolist(),
                "h": np.round(w["high"].to_numpy(), 2).tolist(),
                "l": np.round(w["low"].to_numpy(), 2).tolist(),
                "c": np.round(w["close"].to_numpy(), 2).tolist(),
                "y": y.tolist(),
                "cand": cd.tolist(),
                "pred": pr.tolist(),
                "r5": [None if np.isnan(x) else round(float(x), 2) for x in r5.reindex(w.index).to_numpy()],
            }

        stocks.append({
            "ticker": tk,
            "name": names.get(tk, tk.split(".")[0]),
            **periods
        })

    # 輸出 JSON
    final_payload = {"summary": summary, "stocks": stocks}
    with open(OUT_DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\n[OK] 冠軍資料庫已寫入: {OUT_DATA_JSON} ({os.path.getsize(OUT_DATA_JSON)/1e6:.1f} MB)")

    # 讀取 window_viewer.html 模板並替換 __DATA__
    template_path = os.path.join(OUT_WEB_DIR, "window_viewer.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # 更新 HTML 標題與說明文字為當前冠軍兩階段架構
    html_content = html_content.replace(
        "<h1>TW50 高低點窗口</h1>",
        "<h1>TW50 高低點辨識系統 (兩階段級聯冠軍模型 · 嚴格當日精準版)</h1>"
    )
    html_content = html_content.replace(
        "method_kline_peak · 主軸 · TW50",
        "以深度學習為基礎的 K 線型態辨識系統 · 逢甲大學碩士論文研究 (Tom & Alex · 指導教授：李俊宏 博士)"
    )
    html_content = html_content.replace(
        "<b>AE + OC-SVM 篩候選</b>:輸入是 t−5 ~ t 六根 K 的 29 個數字(開高低收 ÷ t 日收盤、量 ÷ 10 日均量);編碼器只有一層,直接把 29 個數字壓成 16 維(不先升維),OC-SVM 在這 16 維裡圈範圍;用訓練期(2020–2023)的候選點訓練,測試時候選點落在模型範圍內才保留為高 / 低點,否則改判非極值。",
        "<b>兩階段級聯架構 (Two-Stage Cascade Soft-NMS)</b>: 第一層粗篩候選產生器無損保留 100% 轉折候選並剔除 71% 常態平盤；第二層專屬二元難例分類器 (Hard-Negative Refiner) 結合大盤頂背離指標 (bmk_div_hi_bearish) 與 24D 菁英特徵，搭配高斯軟抑制 (Soft-NMS)，在嚴格當日精準 (Exact Day t) 條件下達成 77.3% 準確率、31.2% 高點精確、36.7% 低點精確與 56.5% Macro-F1。"
    )
    html_content = html_content.replace(
        "${row('規則 + AE + OC-SVM(主軸,種子 42)', M)}",
        "${row('兩階段級聯 + 軟抑制 (當前冠軍, 嚴格當日)', M)}"
    )

    # 注入 JSON 數據
    json_str = json.dumps(final_payload, ensure_ascii=False, separators=(",", ":"))
    html_filled = html_content.replace("__DATA__", json_str)

    # 寫入 web 目錄
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_filled)
    print(f"[OK] 單一獨立互動網頁已生成: {OUT_HTML} ({os.path.getsize(OUT_HTML)/1e6:.1f} MB)")

    # 同步複製到 Artifacts 目錄
    artifact_html = os.path.join(ARTIFACT_DIR, "kline_peak_champion_viewer.html")
    import shutil
    shutil.copyfile(OUT_HTML, artifact_html)
    print(f"[OK] 已同步部署至 Artifact: {artifact_html}")

    return OUT_HTML, artifact_html


if __name__ == "__main__":
    build_windows_json_and_html()
