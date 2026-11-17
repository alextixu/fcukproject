#!/usr/bin/env python3
"""
exp_two_stage_cascade.py
========================
驗證使用「兩階段級聯架構 (Two-Stage Cascade Architecture)」能否同時實現高 Precision 與高 Recall：
- 第一階段 (Stage 1: Coarse Screener / High Recall):
    高速過濾掉 70%+ 的「顯然平盤/非極值」，將候選池的轉折召回率保持在 85% ~ 99%。
- 第二階段 (Stage 2: Fine Refiner / High Precision):
    專門針對難例 (Hard Negatives: 假突破/假破底) 進行深度特徵辨識、次日價格確認 (Next-Bar Confirmation) 與軟抑制。

評測基準：TW50 凍結盲測集 (2025-01-01 至 2026-09-30, N=20,139)
"""

import os
import sys
import json
import time
import torch
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.preprocessing import StandardScaler
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
from common import paths as P
os.environ.setdefault("TW_CACHE_DIR", P.YF_2026_CACHE)
sys.path.insert(0, P.XGB_SRC)

from exp_novel_feature_discovery import extract_novel_feature_corpus, extract_champion_32d_embeddings
from peak_labels import FLAT, UP, DOWN, NAMES, ORDER, summarize

OUT_DIR = os.path.join(HERE, "results")
os.makedirs(OUT_DIR, exist_ok=True)


def evaluate_predictions(y_pred, prob_mat, y_true, cand_hi, cand_lo):
    """計算完整指標與 Delta Keep"""
    N = len(y_true)
    correct = (y_pred == y_true).sum()
    acc = correct / N * 100.0

    prec_list, rec_list, f1_list = [], [], []
    for c in [FLAT, UP, DOWN]:
        tp = np.sum((y_pred == c) & (y_true == c))
        fp = np.sum((y_pred == c) & (y_true != c))
        fn = np.sum((y_pred != c) & (y_true == c))
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        prec_list.append(p * 100.0)
        rec_list.append(r * 100.0)
        f1_list.append(f1 * 100.0)

    macro_f1 = np.mean(f1_list)
    bal_acc = np.mean(rec_list)
    prec_hi, recall_hi = prec_list[DOWN], rec_list[DOWN]
    prec_lo, recall_lo = prec_list[UP], rec_list[UP]

    # Delta Keep on Cand-Hi
    is_cand = (cand_hi == 1)
    true_peaks = is_cand & (y_true == DOWN)
    false_peaks = is_cand & (y_true != DOWN)

    keep_true = (y_pred[true_peaks] == DOWN).sum() / max(1, true_peaks.sum()) * 100.0
    keep_false = (y_pred[false_peaks] == DOWN).sum() / max(1, false_peaks.sum()) * 100.0
    delta_keep = keep_true - keep_false

    return {
        "macro_f1": float(macro_f1),
        "bal_acc": float(bal_acc),
        "acc": float(acc),
        "prec_hi": float(prec_hi),
        "prec_lo": float(prec_lo),
        "recall_hi": float(recall_hi),
        "recall_lo": float(recall_lo),
        "f1_hi": float(f1_list[DOWN]),
        "f1_lo": float(f1_list[UP]),
        "delta_keep": float(delta_keep),
        "keep_true": float(keep_true),
        "keep_false": float(keep_false),
    }


def main():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print("=" * 80)
    print(f"🚀 啟動「兩階段級聯 (Two-Stage Cascade)」實證研究 (Device: {device})")
    print("=" * 80)

    # 1. 載入特徵與凍結資料集
    bundle = extract_novel_feature_corpus()
    z_tr, z_te = extract_champion_32d_embeddings(bundle, device)

    # 組合 77 維全模態特徵
    X_base_tr = np.hstack([bundle["dyn_base_tr"], z_tr])
    X_base_te = np.hstack([bundle["dyn_base_te"], z_te])
    X_all_tr = np.hstack([
        X_base_tr,
        bundle["fam1_tr"], bundle["fam2_tr"], bundle["fam3_tr"],
        bundle["fam4_tr"], bundle["fam5_tr"]
    ])
    X_all_te = np.hstack([
        X_base_te,
        bundle["fam1_te"], bundle["fam2_te"], bundle["fam3_te"],
        bundle["fam4_te"], bundle["fam5_te"]
    ])

    scaler = StandardScaler()
    X_all_tr_sc = np.nan_to_num(scaler.fit_transform(X_all_tr), nan=0.0, posinf=3.0, neginf=-3.0)
    X_all_te_sc = np.nan_to_num(scaler.transform(X_all_te), nan=0.0, posinf=3.0, neginf=-3.0)

    # 取出 Top-24 Elite 特徵
    clf_selector = lgb.LGBMClassifier(objective="multiclass", num_class=3, n_estimators=150,
                                      class_weight="balanced", random_state=42, n_jobs=4, verbose=-1)
    clf_selector.fit(X_all_tr_sc, bundle["y_tr"])
    gains = clf_selector.booster_.feature_importance(importance_type="gain")
    top24_idx = np.argsort(gains)[::-1][:24]

    X_elite_tr = X_all_tr_sc[:, top24_idx]
    X_elite_te = X_all_te_sc[:, top24_idx]

    y_tr = bundle["y_tr"]
    y_te = bundle["y_te"]
    c_hi_tr = bundle["c_hi_tr"]
    c_lo_tr = bundle["c_lo_tr"]
    c_hi_te = bundle["c_hi_te"]
    c_lo_te = bundle["c_lo_te"]

    # 提取序列中的價格特徵 (用於次日價格驗證)
    # dyn_base_te 的特徵包含:
    # 0: c_t, 1: h_t, 2: l_t, 3: o_t, 4: v_t, 10: ret2d, 16: ret1d
    ret1d_te = bundle["dyn_base_te"][:, 16] # 當日相較昨日報酬
    ret2d_te = bundle["dyn_base_te"][:, 17] # 2日報酬
    
    print(f"訓練集: {X_elite_tr.shape[0]} 筆 | 測試集: {X_elite_te.shape[0]} 筆 (真實高點: {(y_te==DOWN).sum()}, 真實低點: {(y_te==UP).sum()})")

    results = {}

    # --------------------------------------------------------------------------
    # 對照組 1: 單階段基準模型 (Single-Stage Baseline: Top-24 Elite GBDT)
    # --------------------------------------------------------------------------
    print("\n--- 對照組 1: 單階段基準模型 (Single-Stage Baseline) ---")
    clf_base = lgb.LGBMClassifier(objective="multiclass", num_class=3, n_estimators=300,
                                  learning_rate=0.05, num_leaves=31, max_depth=6,
                                  class_weight="balanced", random_state=42, n_jobs=4, verbose=-1)
    clf_base.fit(X_elite_tr, y_tr)
    prob_base = clf_base.predict_proba(X_elite_te)
    pred_base = np.argmax(prob_base, axis=1)

    m_base = evaluate_predictions(pred_base, prob_base, y_te, c_hi_te, c_lo_te)
    results["1. 單階段基準 (Single-Stage Baseline)"] = m_base
    print(f"  Macro-F1: {m_base['macro_f1']:.2f}% | Acc: {m_base['acc']:.2f}% | Prec-Hi: {m_base['prec_hi']:.2f}% | Recall-Hi: {m_base['recall_hi']:.2f}%")

    # --------------------------------------------------------------------------
    # 對照組 2: 單階段硬過濾模型 (Single-Stage + Hard 1D-NMS + 恐慌熔斷)
    # --------------------------------------------------------------------------
    print("\n--- 對照組 2: 單階段硬過濾模型 (Single-Stage + Hard 1D-NMS) ---")
    pred_s4 = np.zeros_like(pred_base)
    for i in range(len(y_te)):
        p_hi = prob_base[i, DOWN]
        p_lo = prob_base[i, UP]
        if p_hi > 0.45 and p_hi > p_lo:
            pred_s4[i] = DOWN
        elif p_lo > 0.45 and p_lo > p_hi:
            pred_s4[i] = UP
        else:
            pred_s4[i] = FLAT

    # 1D-NMS 硬抑制 (窗口 5 日)
    pred_s4_nms = pred_s4.copy()
    W = 5
    for i in range(len(pred_s4)):
        if pred_s4[i] == DOWN:
            cur_p = prob_base[i, DOWN]
            st = max(0, i - W)
            en = min(len(pred_s4), i + W + 1)
            neighbor_p = prob_base[st:en, DOWN]
            if cur_p < np.max(neighbor_p):
                pred_s4_nms[i] = FLAT
        elif pred_s4[i] == UP:
            cur_p = prob_base[i, UP]
            st = max(0, i - W)
            en = min(len(pred_s4), i + W + 1)
            neighbor_p = prob_base[st:en, UP]
            if cur_p < np.max(neighbor_p):
                pred_s4_nms[i] = FLAT

    m_s4 = evaluate_predictions(pred_s4_nms, prob_base, y_te, c_hi_te, c_lo_te)
    results["2. 單階段硬過濾 (Single-Stage + Hard 1D-NMS)"] = m_s4
    print(f"  Macro-F1: {m_s4['macro_f1']:.2f}% | Acc: {m_s4['acc']:.2f}% | Prec-Hi: {m_s4['prec_hi']:.2f}% | Recall-Hi: {m_s4['recall_hi']:.2f}%")

    # --------------------------------------------------------------------------
    # 方案 A: 兩階段級聯 (Stage 1: 候選產生器 -> Stage 2: 難例專屬判別器)
    # --------------------------------------------------------------------------
    print("\n--- 方案 A: 兩階段級聯 (Coarse Screen -> Hard-Negative Specialized Classifier) ---")
    # Stage 1: 候選產生 (Cand-Hi / Cand-Lo). 訓練階段只在對應候選子集訓練!
    # 在訓練集中，Cand-Hi 包含 True Peak (1) 與 False Breakout (0)
    hi_tr_idx = np.where(c_hi_tr)[0]
    lo_tr_idx = np.where(c_lo_tr)[0]

    y_tr_hi = (y_tr[hi_tr_idx] == DOWN).astype(int)
    y_tr_lo = (y_tr[lo_tr_idx] == UP).astype(int)

    # Stage 2 專屬二元模型 (專門區分真假突破，擺脫 85% FLAT 的主導偏置)
    clf_stage2_hi = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15,
                                       max_depth=4, class_weight="balanced", random_state=42, n_jobs=4, verbose=-1)
    clf_stage2_hi.fit(X_elite_tr[hi_tr_idx], y_tr_hi)

    clf_stage2_lo = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15,
                                       max_depth=4, class_weight="balanced", random_state=42, n_jobs=4, verbose=-1)
    clf_stage2_lo.fit(X_elite_tr[lo_tr_idx], y_tr_lo)

    # 測試集推論
    prob_hi_s2 = clf_stage2_hi.predict_proba(X_elite_te)[:, 1]
    prob_lo_s2 = clf_stage2_lo.predict_proba(X_elite_te)[:, 1]

    pred_cas_a = np.zeros(len(y_te), dtype=int)
    prob_cas_a = np.zeros((len(y_te), 3))
    
    # 門檻設置: 0.40 (維持高召回)
    for i in range(len(y_te)):
        is_hi = c_hi_te[i]
        is_lo = c_lo_te[i]
        phi = prob_hi_s2[i] if is_hi else 0.0
        plo = prob_lo_s2[i] if is_lo else 0.0

        prob_cas_a[i, DOWN] = phi
        prob_cas_a[i, UP] = plo
        prob_cas_a[i, FLAT] = 1.0 - max(phi, plo)

        if phi > 0.40 and phi > plo:
            pred_cas_a[i] = DOWN
        elif plo > 0.40 and plo > phi:
            pred_cas_a[i] = UP
        else:
            pred_cas_a[i] = FLAT

    m_cas_a = evaluate_predictions(pred_cas_a, prob_cas_a, y_te, c_hi_te, c_lo_te)
    results["3. 方案 A: 兩階段級聯 (Cascade Coarse-to-Fine)"] = m_cas_a
    print(f"  Macro-F1: {m_cas_a['macro_f1']:.2f}% | Acc: {m_cas_a['acc']:.2f}% | Prec-Hi: {m_cas_a['prec_hi']:.2f}% | Recall-Hi: {m_cas_a['recall_hi']:.2f}%")

    # --------------------------------------------------------------------------
    # 方案 B: 兩階段級聯 + 高斯軟抑制 (Cascade + Gaussian Soft-NMS)
    # --------------------------------------------------------------------------
    print("\n--- 方案 B: 兩階段級聯 + 高斯軟抑制 (Cascade + Soft-NMS) ---")
    # 高斯軟衰減: 連續群聚轉折點只衰減其分數，若次高點分數仍然顯著 (如複合雙重頂)，則予以保留！
    pred_cas_b = pred_cas_a.copy()
    prob_cas_b = prob_cas_a.copy()
    sigma = 2.5
    W_soft = 4

    for i in range(len(y_te)):
        if pred_cas_a[i] == DOWN:
            cur_p = prob_cas_a[i, DOWN]
            st = max(0, i - W_soft)
            en = min(len(y_te), i + W_soft + 1)
            max_idx = st + np.argmax(prob_cas_a[st:en, DOWN])
            dist = abs(i - max_idx)
            decay = np.exp(-(dist**2) / (2 * (sigma**2)))
            soft_p = cur_p * decay
            prob_cas_b[i, DOWN] = soft_p
            # 只有當軟衰減後的分數太低時才歸零
            if (i != max_idx) and (soft_p < 0.38):
                pred_cas_b[i] = FLAT

        elif pred_cas_a[i] == UP:
            cur_p = prob_cas_a[i, UP]
            st = max(0, i - W_soft)
            en = min(len(y_te), i + W_soft + 1)
            max_idx = st + np.argmax(prob_cas_a[st:en, UP])
            dist = abs(i - max_idx)
            decay = np.exp(-(dist**2) / (2 * (sigma**2)))
            soft_p = cur_p * decay
            prob_cas_b[i, UP] = soft_p
            if (i != max_idx) and (soft_p < 0.38):
                pred_cas_b[i] = FLAT

    m_cas_b = evaluate_predictions(pred_cas_b, prob_cas_b, y_te, c_hi_te, c_lo_te)
    results["4. 方案 B: 兩階段 + 高斯軟抑制 (Cascade + Soft-NMS) 🏆"] = m_cas_b
    print(f"  Macro-F1: {m_cas_b['macro_f1']:.2f}% | Acc: {m_cas_b['acc']:.2f}% | Prec-Hi: {m_cas_b['prec_hi']:.2f}% | Recall-Hi: {m_cas_b['recall_hi']:.2f}%")

    # --------------------------------------------------------------------------
    # 方案 C: 兩階段級聯 + 價格行為確認 (Cascade + Price Action Confirmation)
    # --------------------------------------------------------------------------
    print("\n--- 方案 C: 兩階段級聯 + 次日價格行為確認 (Cascade + Next-Bar Action) ---")
    # 次日驗證：
    # 如果宣告高點，但次日收盤報酬大漲超過 1.2% (表示為順勢突破，非頂部)，自動撤銷！
    # 如果宣告低點，但次日收盤報酬重挫超過 -1.2% (表示單邊破底，非底部)，自動撤銷！
    pred_cas_c = pred_cas_a.copy()
    
    # 利用序列中的下日報酬進行確認
    # 在 seq_geom_te 或是 dyn_base_te 中: 索引 i 的次日報酬即為 i+1 的當日報酬
    for i in range(len(y_te) - 1):
        next_ret = ret1d_te[i + 1] # 次日單日報酬
        if pred_cas_a[i] == DOWN:
            if next_ret > 0.015: # 次日大漲繼續推升 -> 假頂撤銷
                pred_cas_c[i] = FLAT
        elif pred_cas_a[i] == UP:
            if next_ret < -0.015: # 次日大跌單邊破底 -> 假底撤銷
                pred_cas_c[i] = FLAT

    m_cas_c = evaluate_predictions(pred_cas_c, prob_cas_a, y_te, c_hi_te, c_lo_te)
    results["5. 方案 C: 兩階段 + 次日確認 (Cascade + Next-Bar Action) 🏆"] = m_cas_c
    print(f"  Macro-F1: {m_cas_c['macro_f1']:.2f}% | Acc: {m_cas_c['acc']:.2f}% | Prec-Hi: {m_cas_c['prec_hi']:.2f}% | Recall-Hi: {m_cas_c['recall_hi']:.2f}%")

    # --------------------------------------------------------------------------
    # 方案 D: 終極兩階段複合級聯 (Two-Stage Cascade Ultimate: Soft-NMS + Next-Bar)
    # --------------------------------------------------------------------------
    print("\n--- 方案 D: 終極兩階段複合級聯 (Two-Stage Ultimate: Soft-NMS + Next-Bar) ---")
    pred_cas_d = pred_cas_b.copy() # 先經過 Soft-NMS 保住波段複合點
    for i in range(len(y_te) - 1):
        next_ret = ret1d_te[i + 1]
        if pred_cas_b[i] == DOWN:
            if next_ret > 0.012: # 次日強勢大漲突破
                pred_cas_d[i] = FLAT
        elif pred_cas_b[i] == UP:
            if next_ret < -0.012: # 次日急挫下殺
                pred_cas_d[i] = FLAT

    m_cas_d = evaluate_predictions(pred_cas_d, prob_cas_b, y_te, c_hi_te, c_lo_te)
    results["6. 方案 D: 終極兩階段複合級聯 (Two-Stage Ultimate) 🏆"] = m_cas_d
    print(f"  Macro-F1: {m_cas_d['macro_f1']:.2f}% | Acc: {m_cas_d['acc']:.2f}% | Prec-Hi: {m_cas_d['prec_hi']:.2f}% | Recall-Hi: {m_cas_d['recall_hi']:.2f}%")

    # 儲存結果 JSON
    json_path = os.path.join(OUT_DIR, "two_stage_cascade_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 實驗結果已成功寫入: {json_path}")

    # 繪製圖表
    plot_path = os.path.join(OUT_DIR, "chart_two_stage_cascade.png")
    generate_comparison_chart(results, plot_path)
    print(f"[OK] 成果對比圖表已生成: {plot_path}")

    # 複製到 Artifact 目錄
    artifact_chart = "/Users/tom/.gemini/antigravity-cli/brain/f9b83c20-4c2b-40c1-bf15-3cd87531b443/chart_two_stage_cascade.png"
    import shutil
    shutil.copyfile(plot_path, artifact_chart)
    print(f"[OK] 圖表已同步複製到 Artifact: {artifact_chart}")


def generate_comparison_chart(results, save_path):
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    plt.rcParams["font.sans-serif"] = ["Heiti TC", "PingFang HK", "Arial Unicode MS", "SimHei", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    labels = [
        "1. 單階段基準\n(Single Base)",
        "2. 單階段硬過濾\n(Hard NMS)",
        "3. 兩階段候選難例\n(Cascade Coarse)",
        "4. 兩階段+軟抑制\n(Cascade+SoftNMS)",
        "5. 兩階段+次日確認\n(Cascade+NextBar)",
        "6. 兩階段終極集成\n(Cascade Ultimate)"
    ]
    keys = list(results.keys())

    macro_f1 = [results[k]["macro_f1"] for k in keys]
    acc = [results[k]["acc"] for k in keys]
    prec_hi = [results[k]["prec_hi"] for k in keys]
    prec_lo = [results[k]["prec_lo"] for k in keys]
    rec_hi = [results[k]["recall_hi"] for k in keys]
    rec_lo = [results[k]["recall_lo"] for k in keys]
    delta_k = [results[k]["delta_keep"] for k in keys]

    fig, axes = plt.subplots(2, 2, figsize=(15, 11))
    x = np.arange(len(keys))
    width = 0.35

    # Subplot 1: Macro-F1 vs Overall Accuracy
    ax1 = axes[0, 0]
    b1 = ax1.bar(x - width/2, macro_f1, width, label="Macro-F1 (%)", color="#3498db", alpha=0.9)
    b2 = ax1.bar(x + width/2, acc, width, label="Overall Acc (%)", color="#2ecc71", alpha=0.9)
    ax1.set_title("綜合指標: Macro-F1 vs Overall Accuracy", fontsize=12, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=8)
    ax1.set_ylabel("Percentage (%)")
    ax1.set_ylim(40, 90)
    ax1.legend(loc="upper left")
    for bar in b1:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f"{bar.get_height():.1f}%", ha='center', va='bottom', fontsize=8)
    for bar in b2:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f"{bar.get_height():.1f}%", ha='center', va='bottom', fontsize=8)

    # Subplot 2: Precision (High & Low)
    ax2 = axes[0, 1]
    b3 = ax2.bar(x - width/2, prec_hi, width, label="Prec-Hi (高點精確)", color="#e74c3c", alpha=0.9)
    b4 = ax2.bar(x + width/2, prec_lo, width, label="Prec-Lo (低點精確)", color="#9b59b6", alpha=0.9)
    ax2.set_title("精確率: 高點 (Prec-Hi) 與 低點 (Prec-Lo)", fontsize=12, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=8)
    ax2.set_ylabel("Percentage (%)")
    ax2.set_ylim(15, 45)
    ax2.legend(loc="upper left")
    for bar in b3:
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f"{bar.get_height():.1f}%", ha='center', va='bottom', fontsize=8)
    for bar in b4:
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f"{bar.get_height():.1f}%", ha='center', va='bottom', fontsize=8)

    # Subplot 3: Recall (High & Low) - 檢驗是否有折損
    ax3 = axes[1, 0]
    b5 = ax3.bar(x - width/2, rec_hi, width, label="Recall-Hi (高點召回)", color="#f39c12", alpha=0.9)
    b6 = ax3.bar(x + width/2, rec_lo, width, label="Recall-Lo (低點召回)", color="#1abc9c", alpha=0.9)
    ax3.set_title("召回率: 高點 (Recall-Hi) 與 低點 (Recall-Lo) [檢視是否兼顧]", fontsize=12, fontweight="bold")
    ax3.set_xticks(x)
    ax3.set_xticklabels(labels, fontsize=8)
    ax3.set_ylabel("Percentage (%)")
    ax3.set_ylim(15, 95)
    ax3.legend(loc="upper right")
    for bar in b5:
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8, f"{bar.get_height():.1f}%", ha='center', va='bottom', fontsize=8)
    for bar in b6:
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8, f"{bar.get_height():.1f}%", ha='center', va='bottom', fontsize=8)

    # Subplot 4: Delta Keep
    ax4 = axes[1, 1]
    colors = ["#95a5a6", "#34495e", "#2980b9", "#27ae60", "#d35400", "#c0392b"]
    bars_dk = ax4.bar(x, delta_k, 0.5, color=colors, alpha=0.9)
    ax4.set_title("候選點真偽辨識優勢 Delta Keep (%) [越大越佳]", fontsize=12, fontweight="bold")
    ax4.set_xticks(x)
    ax4.set_xticklabels(labels, fontsize=8)
    ax4.set_ylabel("Delta Keep (%)")
    ax4.set_ylim(0, max(delta_k) * 1.25)
    for bar in bars_dk:
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.15, f"{bar.get_height():+.2f}%", ha='center', va='bottom', fontsize=9, fontweight="bold")

    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()


if __name__ == "__main__":
    main()
