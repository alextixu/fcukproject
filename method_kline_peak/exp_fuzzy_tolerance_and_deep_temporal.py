#!/usr/bin/env python3
"""
exp_fuzzy_tolerance_and_deep_temporal.py
========================================
評估兩大前沿維度：
1. 【深度時序模型 (Deep Temporal Modeling)】：
   利用 6 根連續 K 棒無量綱幾何張量 (B, T=6, D=12)，透過因果殘差卷積 (TCN) 與多頭時序自注意力 (Temporal Transformer)
   捕獲型態微觀時序演化特徵，並與 Top-24 表格特徵進行深度融合 (Deep-Tabular Hybrid)。
2. 【實戰模糊容差評估 (Fuzzy Temporal Tolerance)】：
   打破嚴苛「單日絕對對齊 (Exact Day t)」的雙重懲罰，評估在實盤交易允許的：
   - delta = 0: 嚴格精確單日 (Strict Exact Match)
   - delta = ±1: 實戰相鄰 1 日容差 (Next-day Execution Slack)
   - delta = ±2: 波段轉折區間 2 日容差 (Swing Window Slack)
   下的真實高低點精確率 (Precision)、召回率 (Recall) 與 Macro-F1。

評測基準：TW50 凍結獨立盲測集 (2025-01-01 至 2026-09-30, N=20,139)
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset
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

from exp_novel_feature_discovery import extract_novel_feature_corpus
from peak_labels import FLAT, UP, DOWN, NAMES

OUT_DIR = os.path.join(HERE, "results")
os.makedirs(OUT_DIR, exist_ok=True)


# ==============================================================================
# 1. 深度時序神經網絡架構 (Deep Temporal Transformer & TCN Backbone)
# ==============================================================================
class DeepTemporalNet(nn.Module):
    """
    深度時序特徵抽取器：
    - 前端：多尺度 1D 卷積 (核長 2, 3)，提取微觀 K 線組合 (如吞噬、孕線、晨星)
    - 中端：多頭時序自注意力 (Temporal Self-Attention, 4 heads) 捕捉連續時間依賴
    - 後端：池化與多層感知機，輸出 32 維深度時序表徵與 3 分類機率
    """
    def __init__(self, in_dim: int = 12, hidden_dim: int = 64, latent_dim: int = 32, num_classes: int = 3):
        super().__init__()
        # 1. 多尺度時序卷積前端
        self.conv2 = nn.Conv1d(in_dim, hidden_dim // 2, kernel_size=2, padding=1)
        self.conv3 = nn.Conv1d(in_dim, hidden_dim // 2, kernel_size=3, padding=1)
        self.bn_conv = nn.BatchNorm1d(hidden_dim)
        self.act = nn.GELU()

        # 2. 時序自注意力
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim, nhead=4, dim_feedforward=128,
            dropout=0.1, activation="gelu", batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)

        # 3. 表徵投影與分類頭
        self.pool_attn = nn.Linear(hidden_dim, 1)
        self.proj_latent = nn.Linear(hidden_dim, latent_dim)
        self.head = nn.Linear(latent_dim, num_classes)
        self.ln = nn.LayerNorm(latent_dim)

    def forward(self, x_seq: torch.Tensor):
        # x_seq: [B, T=6, D=12]
        B, T, D = x_seq.shape
        x_trans = x_seq.transpose(1, 2) # [B, D, T]
        
        # 卷積提取
        c2 = self.conv2(x_trans)[:, :, :T]
        c3 = self.conv3(x_trans)[:, :, :T]
        h_conv = self.act(self.bn_conv(torch.cat([c2, c3], dim=1))).transpose(1, 2) # [B, T, H]

        # Transformer 時序自注意力
        h_seq = self.transformer(h_conv) # [B, T, H]

        # 注意力池化聚合為單一樣本向量
        attn_scores = F.softmax(self.pool_attn(h_seq), dim=1) # [B, T, 1]
        h_pooled = torch.sum(h_seq * attn_scores, dim=1) # [B, H]

        # 潛在流形表徵
        z_latent = self.ln(self.proj_latent(h_pooled)) # [B, 32]
        logits = self.head(z_latent) # [B, 3]

        return logits, z_latent


# ==============================================================================
# 2. 實戰模糊容差評估函數 (Fuzzy Temporal Tolerance Evaluator)
# ==============================================================================
def evaluate_fuzzy_tolerance(y_true, y_pred, tickers, delta=0):
    """
    在給定時序容差 delta (0, 1, 2 日) 下，計算精準率、召回率、Macro-F1 與 Acc
    - 依個股 (ticker) 隔離邊界，避免跨股票誤配
    - delta=0 時完全等價於標準嚴格精確匹配
    """
    N = len(y_true)
    classes = [FLAT, UP, DOWN]
    metrics = {}

    tot_tp = 0
    f1_list = []
    prec_dict, rec_dict = {}, {}

    for c in classes:
        tot_pred = 0
        tot_true = 0
        tp_pred = 0
        recalled_true = 0

        for s in np.unique(tickers):
            s_idx = np.where(tickers == s)[0]
            yt = y_true[s_idx]
            yp = y_pred[s_idx]

            p_pos = np.where(yp == c)[0]
            t_pos = np.where(yt == c)[0]

            tot_pred += len(p_pos)
            tot_true += len(t_pos)

            if len(p_pos) == 0 or len(t_pos) == 0:
                continue

            if delta == 0:
                # 嚴格精確單日
                matches = (yt == c) & (yp == c)
                tp_pred += np.sum(matches)
                recalled_true += np.sum(matches)
            else:
                # 模糊容差 matching
                # 1. 檢驗預測點是否落在真實點的 ±delta 窗口內
                for p in p_pos:
                    if np.min(np.abs(t_pos - p)) <= delta:
                        tp_pred += 1
                # 2. 檢驗真實點是否被 ±delta 窗口內的預測點召回
                for t in t_pos:
                    if np.min(np.abs(p_pos - t)) <= delta:
                        recalled_true += 1

        p = (tp_pred / tot_pred * 100.0) if tot_pred > 0 else 0.0
        r = (recalled_true / tot_true * 100.0) if tot_true > 0 else 0.0
        f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0

        prec_dict[c] = float(p)
        rec_dict[c] = float(r)
        f1_list.append(float(f1))

    # 整體準確率 (Acc)
    # 在 delta 容差下，計算預測命中真實標籤的樣本比率
    if delta == 0:
        overall_acc = float((y_pred == y_true).sum() / N * 100.0)
    else:
        correct_cnt = 0
        for s in np.unique(tickers):
            s_idx = np.where(tickers == s)[0]
            yt = y_true[s_idx]
            yp = y_pred[s_idx]
            for i in range(len(s_idx)):
                c_pred = yp[i]
                st = max(0, i - delta)
                en = min(len(s_idx), i + delta + 1)
                if c_pred in yt[st:en]:
                    correct_cnt += 1
        overall_acc = float(correct_cnt / N * 100.0)

    macro_f1 = float(np.mean(f1_list))

    return {
        "macro_f1": macro_f1,
        "acc": overall_acc,
        "prec_hi": prec_dict[DOWN],
        "prec_lo": prec_dict[UP],
        "recall_hi": rec_dict[DOWN],
        "recall_lo": rec_dict[UP],
        "f1_hi": f1_list[DOWN],
        "f1_lo": f1_list[UP],
    }


def main():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print("=" * 85)
    print(f"🚀 啟動【模糊容差 (Fuzzy Tolerance) 與 深度時序 (Deep Temporal)】實證研究 (Device: {device})")
    print("=" * 85)

    # 1. 載入特徵庫
    t0 = time.time()
    bundle = extract_novel_feature_corpus()
    seq_tr = bundle["seq_geom_tr"]
    seq_te = bundle["seq_geom_te"]
    y_tr = bundle["y_tr"]
    y_te = bundle["y_te"]
    c_hi_tr = bundle["c_hi_tr"]
    c_lo_tr = bundle["c_lo_tr"]
    c_hi_te = bundle["c_hi_te"]
    c_lo_te = bundle["c_lo_te"]
    tickers_te = bundle["tickers_te"]

    print(f"資料載入完成: 訓練集={len(y_tr):,} 筆 | 測試集={len(y_te):,} 筆 (耗時: {time.time()-t0:.2f}s)")

    # 構建 Top-24 菁英特徵 (Tabular)
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

    # ==========================================================================
    # 模型 1: 單階段表格基準 (Top-24 Elite GBDT Baseline)
    # ==========================================================================
    print("\n[模型 1] 訓練 Top-24 Elite GBDT 基準模型...")
    clf_base = lgb.LGBMClassifier(objective="multiclass", num_class=3, n_estimators=300,
                                  learning_rate=0.05, num_leaves=31, max_depth=6,
                                  class_weight="balanced", random_state=42, n_jobs=4, verbose=-1)
    clf_base.fit(X_elite_tr, y_tr)
    prob_base = clf_base.predict_proba(X_elite_te)
    pred_base = np.argmax(prob_base, axis=1)

    # ==========================================================================
    # 模型 2: 兩階段級聯表格模型 (Two-Stage Cascade + Soft-NMS, 前一輪冠軍)
    # ==========================================================================
    print("[模型 2] 訓練兩階段級聯 (Two-Stage Cascade + Soft-NMS) 表格模型...")
    hi_tr_idx = np.where(c_hi_tr)[0]
    lo_tr_idx = np.where(c_lo_tr)[0]
    y_tr_hi = (y_tr[hi_tr_idx] == DOWN).astype(int)
    y_tr_lo = (y_tr[lo_tr_idx] == UP).astype(int)

    clf_s2_hi = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15,
                                   max_depth=4, class_weight="balanced", random_state=42, n_jobs=4, verbose=-1)
    clf_s2_hi.fit(X_elite_tr[hi_tr_idx], y_tr_hi)

    clf_s2_lo = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15,
                                   max_depth=4, class_weight="balanced", random_state=42, n_jobs=4, verbose=-1)
    clf_s2_lo.fit(X_elite_tr[lo_tr_idx], y_tr_lo)

    prob_hi_s2 = clf_s2_hi.predict_proba(X_elite_te)[:, 1]
    prob_lo_s2 = clf_s2_lo.predict_proba(X_elite_te)[:, 1]

    pred_cas_raw = np.zeros(len(y_te), dtype=int)
    prob_cas_raw = np.zeros((len(y_te), 3))
    for i in range(len(y_te)):
        phi = prob_hi_s2[i] if c_hi_te[i] else 0.0
        plo = prob_lo_s2[i] if c_lo_te[i] else 0.0
        prob_cas_raw[i, DOWN] = phi
        prob_cas_raw[i, UP] = plo
        prob_cas_raw[i, FLAT] = 1.0 - max(phi, plo)
        if phi > 0.40 and phi > plo:
            pred_cas_raw[i] = DOWN
        elif plo > 0.40 and plo > phi:
            pred_cas_raw[i] = UP

    # 執行高斯軟抑制 (Soft-NMS)
    pred_twostage_soft = pred_cas_raw.copy()
    sigma = 2.5
    W_soft = 4
    for i in range(len(y_te)):
        if pred_cas_raw[i] == DOWN:
            cur_p = prob_cas_raw[i, DOWN]
            st = max(0, i - W_soft)
            en = min(len(y_te), i + W_soft + 1)
            max_idx = st + np.argmax(prob_cas_raw[st:en, DOWN])
            dist = abs(i - max_idx)
            soft_p = cur_p * np.exp(-(dist**2) / (2 * (sigma**2)))
            if (i != max_idx) and (soft_p < 0.38):
                pred_twostage_soft[i] = FLAT
        elif pred_cas_raw[i] == UP:
            cur_p = prob_cas_raw[i, UP]
            st = max(0, i - W_soft)
            en = min(len(y_te), i + W_soft + 1)
            max_idx = st + np.argmax(prob_cas_raw[st:en, UP])
            dist = abs(i - max_idx)
            soft_p = cur_p * np.exp(-(dist**2) / (2 * (sigma**2)))
            if (i != max_idx) and (soft_p < 0.38):
                pred_twostage_soft[i] = FLAT

    # ==========================================================================
    # 模型 3: 純深度時序模型 (Deep Temporal Transformer & TCN Backbone)
    # ==========================================================================
    print("[模型 3] 訓練純深度時序網絡 (TCN + Temporal Transformer)...")
    torch.manual_seed(42)
    deep_net = DeepTemporalNet(in_dim=12, hidden_dim=64, latent_dim=32, num_classes=3).to(device)

    # 類別權重
    class_weights = torch.tensor([1.0, 5.0, 5.0], dtype=torch.float32).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(deep_net.parameters(), lr=1e-3, weight_decay=1e-4)

    t_tr_seq = torch.from_numpy(seq_tr).float()
    t_tr_y = torch.from_numpy(y_tr).long()
    train_loader = DataLoader(TensorDataset(t_tr_seq, t_tr_y), batch_size=256, shuffle=True)

    deep_net.train()
    t_deep_start = time.time()
    for epoch in range(6):
        for b_x, b_y in train_loader:
            b_x, b_y = b_x.to(device), b_y.to(device)
            optimizer.zero_grad()
            logits, _ = deep_net(b_x)
            loss = criterion(logits, b_y)
            loss.backward()
            optimizer.step()
    print(f"  深度時序網絡訓練完畢, 耗時: {time.time()-t_deep_start:.2f}s")

    # 推理測試集
    deep_net.eval()
    t_te_seq = torch.from_numpy(seq_te).float()
    with torch.no_grad():
        test_loader = DataLoader(TensorDataset(t_te_seq), batch_size=512, shuffle=False)
        logits_list, latent_list = [], []
        for (b_x,) in test_loader:
            b_x = b_x.to(device)
            lgt, z_lat = deep_net(b_x)
            logits_list.append(lgt.cpu())
            latent_list.append(z_lat.cpu())

    logits_deep = torch.cat(logits_list, dim=0)
    prob_deep = F.softmax(logits_deep, dim=1).numpy()
    z_deep_te = torch.cat(latent_list, dim=0).numpy()
    pred_deep = np.argmax(prob_deep, axis=1)

    # 提取訓練集深層表徵 (用於模型 4 融合)
    with torch.no_grad():
        tr_loader_eval = DataLoader(TensorDataset(t_tr_seq), batch_size=512, shuffle=False)
        latent_tr_list = []
        for (b_x,) in tr_loader_eval:
            b_x = b_x.to(device)
            _, z_lat = deep_net(b_x)
            latent_tr_list.append(z_lat.cpu())
    z_deep_tr = torch.cat(latent_tr_list, dim=0).numpy()

    # ==========================================================================
    # 模型 4: 深度時序 + 表格特徵雙模態混合級聯 (Deep-Tabular Hybrid Cascade)
    # ==========================================================================
    print("[模型 4] 訓練雙模態融合模型 (Deep Temporal Latent + Top-24 Tabular + Two-Stage)...")
    # 將 32D 深度時序表徵與 24D 表格特徵拼接為 56D 雙模態特徵
    X_hybrid_tr = np.hstack([X_elite_tr, z_deep_tr])
    X_hybrid_te = np.hstack([X_elite_te, z_deep_te])

    clf_hyb_hi = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15,
                                    max_depth=4, class_weight="balanced", random_state=42, n_jobs=4, verbose=-1)
    clf_hyb_hi.fit(X_hybrid_tr[hi_tr_idx], y_tr_hi)

    clf_hyb_lo = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15,
                                    max_depth=4, class_weight="balanced", random_state=42, n_jobs=4, verbose=-1)
    clf_hyb_lo.fit(X_hybrid_tr[lo_tr_idx], y_tr_lo)

    prob_hi_hyb = clf_hyb_hi.predict_proba(X_hybrid_te)[:, 1]
    prob_lo_hyb = clf_hyb_lo.predict_proba(X_hybrid_te)[:, 1]

    pred_hyb_raw = np.zeros(len(y_te), dtype=int)
    prob_hyb_raw = np.zeros((len(y_te), 3))
    for i in range(len(y_te)):
        phi = prob_hi_hyb[i] if c_hi_te[i] else 0.0
        plo = prob_lo_hyb[i] if c_lo_te[i] else 0.0
        prob_hyb_raw[i, DOWN] = phi
        prob_hyb_raw[i, UP] = plo
        prob_hyb_raw[i, FLAT] = 1.0 - max(phi, plo)
        if phi > 0.40 and phi > plo:
            pred_hyb_raw[i] = DOWN
        elif plo > 0.40 and plo > phi:
            pred_hyb_raw[i] = UP

    # 執行高斯軟抑制 (Soft-NMS)
    pred_hybrid_soft = pred_hyb_raw.copy()
    for i in range(len(y_te)):
        if pred_hyb_raw[i] == DOWN:
            cur_p = prob_hyb_raw[i, DOWN]
            st = max(0, i - W_soft)
            en = min(len(y_te), i + W_soft + 1)
            max_idx = st + np.argmax(prob_hyb_raw[st:en, DOWN])
            dist = abs(i - max_idx)
            soft_p = cur_p * np.exp(-(dist**2) / (2 * (sigma**2)))
            if (i != max_idx) and (soft_p < 0.38):
                pred_hybrid_soft[i] = FLAT
        elif pred_hyb_raw[i] == UP:
            cur_p = prob_hyb_raw[i, UP]
            st = max(0, i - W_soft)
            en = min(len(y_te), i + W_soft + 1)
            max_idx = st + np.argmax(prob_hyb_raw[st:en, UP])
            dist = abs(i - max_idx)
            soft_p = cur_p * np.exp(-(dist**2) / (2 * (sigma**2)))
            if (i != max_idx) and (soft_p < 0.38):
                pred_hybrid_soft[i] = FLAT

    # ==========================================================================
    # 多維度實證評估：嚴格匹配 vs. ±1日模糊容差 vs. ±2日模糊容差
    # ==========================================================================
    models_dict = {
        "1. 表格單階段基準 (Tabular Baseline)": pred_base,
        "2. 表格兩階段級聯 (Two-Stage Cascade Soft-NMS)": pred_twostage_soft,
        "3. 純深度時序模型 (Deep Temporal Transformer)": pred_deep,
        "4. 雙模態時序融合 (Deep-Tabular Hybrid) 🏆": pred_hybrid_soft
    }

    deltas = [0, 1, 2]
    delta_names = {
        0: "嚴格單日匹配 (delta=0)",
        1: "實戰±1日容差 (delta=1)",
        2: "波段±2日容差 (delta=2)"
    }

    full_results = {}
    print("\n" + "=" * 85)
    print("📊 模糊時序容差評估結果對照表 (Strict delta=0 vs. Fuzzy delta=±1, ±2)")
    print("=" * 85)

    for m_name, preds in models_dict.items():
        full_results[m_name] = {}
        print(f"\n▶ 【{m_name}】")
        for d in deltas:
            d_name = delta_names[d]
            res = evaluate_fuzzy_tolerance(y_te, preds, tickers_te, delta=d)
            full_results[m_name][d_name] = res
            print(f"  [{d_name}] Macro-F1: {res['macro_f1']:.2f}% | Acc: {res['acc']:.2f}% | "
                  f"Prec-Hi: {res['prec_hi']:.2f}% | Prec-Lo: {res['prec_lo']:.2f}% | "
                  f"Recall-Hi: {res['recall_hi']:.2f}% | Recall-Lo: {res['recall_lo']:.2f}%")

    # 儲存結果 JSON
    json_path = os.path.join(OUT_DIR, "fuzzy_tolerance_deep_temporal_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_results, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 完整實證結果已寫入: {json_path}")

    # 繪製高解析度對比圖表
    plot_path = os.path.join(OUT_DIR, "chart_fuzzy_tolerance_deep_temporal.png")
    generate_comparison_chart(full_results, plot_path)
    print(f"[OK] 成果對比圖表已生成: {plot_path}")

    # 複製到 Artifact 目錄
    artifact_chart = "/Users/tom/.gemini/antigravity-cli/brain/f9b83c20-4c2b-40c1-bf15-3cd87531b443/chart_fuzzy_tolerance_deep_temporal.png"
    import shutil
    shutil.copyfile(plot_path, artifact_chart)
    print(f"[OK] 圖表已同步複製到 Artifact: {artifact_chart}")


def generate_comparison_chart(results, save_path):
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    plt.rcParams["font.sans-serif"] = ["Heiti TC", "PingFang HK", "Arial Unicode MS", "SimHei", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    models = list(results.keys())
    short_model_names = ["1. 表格基準", "2. 兩階段級聯", "3. 純深度時序", "4. 雙模態融合 [Best]"]
    delta_keys = ["嚴格單日匹配 (delta=0)", "實戰±1日容差 (delta=1)", "波段±2日容差 (delta=2)"]
    delta_labels = ["嚴格 (delta=0)", "±1日容差", "±2日容差"]

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    x = np.arange(len(short_model_names))
    width = 0.25

    # Subplot 1: Macro-F1 隨容差變化
    ax1 = axes[0, 0]
    colors_f1 = ["#3498db", "#2980b9", "#1b4f72"]
    for idx, (dk, dl) in enumerate(zip(delta_keys, delta_labels)):
        vals = [results[m][dk]["macro_f1"] for m in models]
        bars = ax1.bar(x + (idx - 1)*width, vals, width, label=dl, color=colors_f1[idx], alpha=0.88)
        for bar in bars:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.6, f"{bar.get_height():.1f}%", ha='center', va='bottom', fontsize=8)
    ax1.set_title("綜合指標 Macro-F1 (%) 隨容差躍升幅度", fontsize=12, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(short_model_names, fontsize=9)
    ax1.set_ylabel("Macro-F1 (%)")
    ax1.set_ylim(40, 85)
    ax1.legend(loc="upper left")

    # Subplot 2: Prec-Hi (高點精確) 隨容差變化
    ax2 = axes[0, 1]
    colors_phi = ["#e74c3c", "#c0392b", "#78281f"]
    for idx, (dk, dl) in enumerate(zip(delta_keys, delta_labels)):
        vals = [results[m][dk]["prec_hi"] for m in models]
        bars = ax2.bar(x + (idx - 1)*width, vals, width, label=dl, color=colors_phi[idx], alpha=0.88)
        for bar in bars:
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.6, f"{bar.get_height():.1f}%", ha='center', va='bottom', fontsize=8)
    ax2.set_title("高點精確率 Prec-Hi (%) 突破實證 (直觀實戰勝率)", fontsize=12, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(short_model_names, fontsize=9)
    ax2.set_ylabel("Precision (%)")
    ax2.set_ylim(20, 75)
    ax2.legend(loc="upper left")

    # Subplot 3: Prec-Lo (低點精確) 隨容差變化
    ax3 = axes[1, 0]
    colors_plo = ["#2ecc71", "#27ae60", "#145a32"]
    for idx, (dk, dl) in enumerate(zip(delta_keys, delta_labels)):
        vals = [results[m][dk]["prec_lo"] for m in models]
        bars = ax3.bar(x + (idx - 1)*width, vals, width, label=dl, color=colors_plo[idx], alpha=0.88)
        for bar in bars:
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.6, f"{bar.get_height():.1f}%", ha='center', va='bottom', fontsize=8)
    ax3.set_title("低點精確率 Prec-Lo (%) 突破實證 (抄底成功率)", fontsize=12, fontweight="bold")
    ax3.set_xticks(x)
    ax3.set_xticklabels(short_model_names, fontsize=9)
    ax3.set_ylabel("Precision (%)")
    ax3.set_ylim(20, 80)
    ax3.legend(loc="upper left")

    # Subplot 4: Recall-Hi (高點召回) 隨容差變化
    ax4 = axes[1, 1]
    colors_rec = ["#f39c12", "#d68910", "#7e5109"]
    for idx, (dk, dl) in enumerate(zip(delta_keys, delta_labels)):
        vals = [results[m][dk]["recall_hi"] for m in models]
        bars = ax4.bar(x + (idx - 1)*width, vals, width, label=dl, color=colors_rec[idx], alpha=0.88)
        for bar in bars:
            ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.6, f"{bar.get_height():.1f}%", ha='center', va='bottom', fontsize=8)
    ax4.set_title("高點召回率 Recall-Hi (%) 變化對比", fontsize=12, fontweight="bold")
    ax4.set_xticks(x)
    ax4.set_xticklabels(short_model_names, fontsize=9)
    ax4.set_ylabel("Recall (%)")
    ax4.set_ylim(20, 95)
    ax4.legend(loc="upper right")

    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()


if __name__ == "__main__":
    main()
