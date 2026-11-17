"""
實驗：探索全新潛在重要特徵 —— 金融微結構、分形效率、年線位階與大盤背離消融評估
(Empirical Evaluation: Exploring Novel Untapped Features for Candlestick Turning Point Detection)

研究目標：
打破現有特徵工程邊界，深入挖掘 5 大維度共 15 項全新前沿特徵：
1. 【微觀流動性與量價耗竭】: CLV 多空平衡值、5日成交量加權 CLV、Amihud 價格衝擊 (ILLIQ)、量能竭盡指數 (VEI)
2. 【波動率體制與分形維度】: Parkinson 盤中波動比、布林通道帶寬壓縮 (BBW Squeeze)、Kaufman 分形效率比 (ER)
3. 【多時間週期長波段位階】: 距離 52 週 (250日) 年線極值距離 (dist_hi250, dist_lo250)、均線排列強度得分
4. 【大盤基準 Alpha 與 Beta 背離】: 相對 0050 台灣50之 5 日超額收益 (Alpha)、大盤頂底背離指標
5. 【微觀形態連擊與影線拒絕】: K 線連續陰陽連擊計數器 (Streak)、帶量影線拒絕力道 (WRP)、隔夜缺口盤中回補率

測試基準：
台股 50 嚴格凍結獨立測試集 (TW50, 2025-01-01 至 2026-09-30, N=20,139)，訓練集 2020-01-01 至 2023-12-31 (N=48,235)
"""

from __future__ import annotations
import json
import os
import sys
import time
import math
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb
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
from data import load_pool

from feasibility import clean, HALF
from peak_labels import TOL, side_extreme, FLAT, UP, DOWN, NAMES, ORDER, summarize

OUT_DIR = os.path.join(HERE, "results")
os.makedirs(OUT_DIR, exist_ok=True)


def paper_label(C):
    lmax, rmax = side_extreme(C, HALF, False, "max"), side_extreme(C, HALF, True, "max")
    lmin, rmin = side_extreme(C, HALF, False, "min"), side_extreme(C, HALF, True, "min")
    hi = (C >= lmax * (1 - TOL)) & (C >= rmax * (1 - TOL))
    lo = (C <= lmin * (1 + TOL)) & (C <= rmin * (1 + TOL))
    y = np.full(len(C), FLAT)
    y[hi & ~lo] = DOWN
    y[lo & ~hi] = UP
    cand_hi = (C >= lmax * (1 - TOL)) & ~(C <= lmin * (1 + TOL))
    cand_lo = (C <= lmin * (1 + TOL)) & ~(C >= lmax * (1 - TOL))
    valid = lmax.notna() & rmax.notna()
    y = np.where(valid, y, -1)
    return y, cand_hi.values, cand_lo.values


# ==============================================================================
# 1. 深度度量主幹 (用於提取現有冠軍 32D 超球面嵌入)
# ==============================================================================
class CandlestickProtoEncoder(nn.Module):
    def __init__(self, in_dim=12, hidden_dim=64, latent_dim=32):
        super().__init__()
        self.conv1 = nn.Sequential(
            nn.Conv1d(in_dim, hidden_dim // 2, kernel_size=1),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.GELU()
        )
        self.conv3 = nn.Sequential(
            nn.Conv1d(in_dim, hidden_dim // 2, kernel_size=3, padding=1),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.GELU()
        )
        self.conv_dilated = nn.Sequential(
            nn.Conv1d(hidden_dim, hidden_dim, kernel_size=3, padding=2, dilation=2),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU()
        )
        self.mha = nn.MultiheadAttention(hidden_dim, num_heads=4, batch_first=True)
        self.ln = nn.LayerNorm(hidden_dim)
        self.head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, latent_dim)
        )

    def forward(self, x):
        xt = x.permute(0, 2, 1)
        c1 = self.conv1(xt)
        c3 = self.conv3(xt)
        h = torch.cat([c1, c3], dim=1)
        h = self.conv_dilated(h).permute(0, 2, 1)
        attn_out, _ = self.mha(h, h, h)
        h = self.ln(h + attn_out)
        pooled = h.mean(dim=1)
        z = self.head(pooled)
        return F.normalize(z, p=2, dim=-1)


# ==============================================================================
# 2. 全方位特徵庫萃取 (包含現有 29D 動力學 + 15項全新前沿特徵)
# ==============================================================================
def extract_novel_feature_corpus():
    print("[1/5] 載入 TW50 歷史全量數據與 0050.TW 大盤基準，建構前沿新特徵庫...")
    t0 = time.time()
    data = load_pool("tw50", "2019-01-01", "2026-09-10") # 擴大至 2019 以容納 250 天年線預熱

    # 載入 0050 作為大盤基準
    benchmark_path = os.path.join(P.YF_2026_CACHE, "0050.TW.parquet")
    df_bmk = pd.read_parquet(benchmark_path)
    df_bmk = clean(df_bmk)
    s_bmk_c = df_bmk["close"].copy()
    s_bmk_ret5 = (s_bmk_c / s_bmk_c.shift(5) - 1.0).fillna(0.0)
    s_bmk_c_min5 = s_bmk_c.rolling(5, min_periods=1).min()
    s_bmk_c_max5 = s_bmk_c.rolling(5, min_periods=1).max()
    bmk_pos5 = ((s_bmk_c - s_bmk_c_min5) / np.maximum(1e-4, s_bmk_c_max5 - s_bmk_c_min5)).clip(0.0, 1.0)

    dates_list, tickers_list = [], []
    y_list, cand_hi_list, cand_lo_list = [], [], []

    seq_geom_list = []      # [6, 12] 幾何序列 (計算 32D 嵌入)
    dyn_base_list = []      # 29 維現有動力學基準特徵

    # 5 大類全新特徵列表
    novel_fam1_list = []    # 4D: 微觀流動性與量價耗竭 (clv, clv_5d, illiq, vei)
    novel_fam2_list = []    # 3D: 波動率體制與分形維度 (parkinson_ratio, bbw_squeeze, fractal_er)
    novel_fam3_list = []    # 3D: 多時間週期長波段位階 (dist_hi250, dist_lo250, ma_alignment)
    novel_fam4_list = []    # 3D: 大盤基準 Alpha 與背離 (alpha_vs_0050, bmk_div_hi, bmk_div_lo)
    novel_fam5_list = []    # 3D: 微觀形態連擊與影線拒絕 (streak, wick_rejection_power, gap_fill_ratio)

    for tk, df in data.items():
        df = clean(df).copy()
        if len(df) < 265: # 需容納 250 日年線
            continue
        y_arr, c_hi_arr, c_lo_arr = paper_label(df["close"])
        O, H, L, C, V = df["open"].values, df["high"].values, df["low"].values, df["close"].values, df["volume"].values
        dates = df.index
        N = len(df)

        s_C = pd.Series(C, index=dates)
        s_H = pd.Series(H, index=dates)
        s_L = pd.Series(L, index=dates)
        s_O = pd.Series(O, index=dates)
        s_V = pd.Series(V, index=dates)

        # -------------------------------------------------------------
        # 基礎指標 (均線、ATR、波動)
        # -------------------------------------------------------------
        v_ma5 = s_V.rolling(5, min_periods=1).mean().values
        v_ma20 = s_V.rolling(20, min_periods=1).mean().values
        c_ma5 = s_C.rolling(5, min_periods=1).mean().values
        c_ma20 = s_C.rolling(20, min_periods=5).mean().values
        c_ma60 = s_C.rolling(60, min_periods=10).mean().values

        prev_c = s_C.shift(1).bfill().values
        prev2_c = s_C.shift(2).bfill().values
        prev_o = s_O.shift(1).bfill().values

        tr_val = np.maximum(H - L, np.maximum(np.abs(H - prev_c), np.abs(L - prev_c)))
        atr20 = pd.Series(tr_val).rolling(20, min_periods=5).mean().bfill().values
        safe_atr20 = np.maximum(atr20, 1e-4 * C)

        c_range = H - L
        safe_range = np.where(c_range <= 1e-8, 1e-8, c_range)
        max_oc = np.maximum(O, C)
        min_oc = np.minimum(O, C)

        f_body_s = (C - O) / safe_range
        f_upper = (H - max_oc) / safe_range
        f_lower = (min_oc - L) / safe_range
        f_close_pos = (C - L) / safe_range
        gap_overnight = np.clip((O - prev_c) / safe_atr20, -3.0, 3.0)
        range_vs_atr = np.clip((H - L) / safe_atr20, 0.1, 5.0)
        vol_density = np.clip((V / np.maximum(v_ma20, 1.0)) / (c_range / C + 1e-3), 0.0, 15.0) / 5.0
        f_vol_r5 = np.clip(V / np.where(v_ma5 <= 1e-8, 1.0, v_ma5), 0.1, 10.0)

        delta_c = C - prev_c
        prev_delta_c = prev_c - prev2_c
        accel_c = np.clip((delta_c - prev_delta_c) / safe_atr20, -3.0, 3.0)
        body_abs = np.abs(C - O)
        prev_body_abs = np.abs(prev_c - prev_o)
        body_compression = np.clip(body_abs / np.maximum(prev_body_abs, 1e-4 * C), 0.05, 5.0)
        vpi = np.clip((delta_c / safe_atr20) * (V / np.maximum(v_ma20, 1.0)), -5.0, 5.0)
        wick_vs_body = np.clip((H - max_oc) / np.maximum(body_abs, 1e-4 * C), 0.0, 6.0)

        bias_ma20 = np.clip((C - c_ma20) / np.maximum(c_ma20, 1e-4), -0.20, 0.20)
        bias_ma60 = np.clip((C - c_ma60) / np.maximum(c_ma60, 1e-4), -0.30, 0.30)
        ma20_lag10 = pd.Series(c_ma20).shift(10).bfill().values
        trend_slope_20d = np.clip((c_ma20 - ma20_lag10) / np.maximum(ma20_lag10, 1e-4), -0.15, 0.15)

        # -------------------------------------------------------------
        # 【全新特徵 Family 1: 微觀流動性與量價耗竭】
        # -------------------------------------------------------------
        # 1. Close Location Value: ( (C-L) - (H-C) ) / (H-L)
        clv = np.clip((2.0 * C - (H + L)) / safe_range, -1.0, 1.0)
        # 2. 5日成交量加權 CLV
        s_clv_v = pd.Series(clv * V)
        s_v_sum5 = s_V.rolling(5, min_periods=1).sum()
        clv_5d = np.clip(s_clv_v.rolling(5, min_periods=1).sum() / np.maximum(1e-4, s_v_sum5), -1.0, 1.0).values
        # 3. Amihud Illiquidity (價格衝擊彈性)
        dollar_vol = C * V
        abs_ret = np.abs(delta_c) / np.maximum(prev_c, 1e-4)
        illiq = np.clip(np.log1p(abs_ret * 1e8 / np.maximum(dollar_vol, 1e4)), 0.0, 8.0)
        # 4. Volume Exhaustion Index (量能加速度 × 實體壓縮)
        prev_v = s_V.shift(1).bfill().values
        prev2_v = s_V.shift(2).bfill().values
        accel_v = (V - prev_v) - (prev_v - prev2_v)
        vei = np.clip((accel_v / np.maximum(v_ma20, 1.0)) * (1.0 - body_abs / safe_range), -5.0, 5.0)

        # -------------------------------------------------------------
        # 【全新特徵 Family 2: 波動率體制與分形維度】
        # -------------------------------------------------------------
        # 1. Parkinson 盤中波動比: sigma_P / (|ln(C/prev_C)| + eps)
        log_hl = np.log(np.maximum(1.0, H / np.maximum(L, 1e-4)))
        sigma_parkinson = np.sqrt((log_hl ** 2) / (4.0 * np.log(2.0)))
        sigma_cc = np.abs(np.log(np.maximum(1e-4, C / np.maximum(prev_c, 1e-4))))
        parkinson_ratio = np.clip(sigma_parkinson / (sigma_cc + 1e-4), 0.0, 8.0)
        # 2. 布林帶寬壓縮 (BBW Squeeze)
        c_std20 = s_C.rolling(20, min_periods=5).std().bfill().values
        bbw = (4.0 * c_std20) / np.maximum(c_ma20, 1e-4)
        bbw_min20 = pd.Series(bbw).rolling(20, min_periods=5).min().bfill().values
        bbw_squeeze = np.clip(bbw / np.maximum(bbw_min20, 1e-4), 1.0, 4.0)
        # 3. Kaufman 分形效率比 (ER): 5日位移 / 5日總路徑
        disp_5d = np.abs(C - s_C.shift(5).bfill().values)
        path_5d = pd.Series(np.abs(delta_c)).rolling(5, min_periods=1).sum().bfill().values
        fractal_er = np.clip(disp_5d / np.maximum(path_5d, 1e-4), 0.0, 1.0)

        # -------------------------------------------------------------
        # 【全新特徵 Family 3: 多時間週期長波段位階】
        # -------------------------------------------------------------
        # 1. 距離 250 日年線最高/最低點之對數距離
        h_250 = s_H.rolling(250, min_periods=20).max().bfill().values
        l_250 = s_L.rolling(250, min_periods=20).min().bfill().values
        dist_hi250 = np.clip(np.log(np.maximum(1e-4, C / np.maximum(h_250, 1e-4))), -0.80, 0.0)
        dist_lo250 = np.clip(np.log(np.maximum(1e-4, C / np.maximum(l_250, 1e-4))), 0.0, 1.20)
        # 2. 均線多空排列強度得分 [-3, +3]
        ma_alignment = (np.sign(C - c_ma5) + np.sign(c_ma5 - c_ma20) + np.sign(c_ma20 - c_ma60)) / 3.0

        # -------------------------------------------------------------
        # 【全新特徵 Family 4: 大盤基準 Alpha 與背離】
        # -------------------------------------------------------------
        # 對齊 0050.TW 報酬
        s_stock_ret5 = (s_C / s_C.shift(5) - 1.0).fillna(0.0)
        bmk_ret5_aligned = s_bmk_ret5.reindex(dates, method="ffill").fillna(0.0).values
        bmk_pos5_aligned = bmk_pos5.reindex(dates, method="ffill").fillna(0.5).values

        # 1. 相對 0050 的 5 日超額收益 (Alpha)
        alpha_vs_0050 = np.clip(s_stock_ret5.values - bmk_ret5_aligned, -0.30, 0.30)

        # 2. 大盤頂背離指標: 大盤在高檔 (pos5 > 0.8) 但個股在低檔 (pos5 < 0.4)
        c_min5 = s_C.rolling(5, min_periods=1).min().values
        c_max5 = s_C.rolling(5, min_periods=1).max().values
        stock_pos5 = np.clip((C - c_min5) / np.maximum(1e-4, c_max5 - c_min5), 0.0, 1.0)

        bmk_div_hi = np.clip(bmk_pos5_aligned - stock_pos5, -1.0, 1.0) # > 0: 大盤強個股弱 (頂背離)
        bmk_div_lo = np.clip(stock_pos5 - bmk_pos5_aligned, -1.0, 1.0) # > 0: 個股強大盤弱 (底背離)

        # -------------------------------------------------------------
        # 【全新特徵 Family 5: 微觀形態連擊與影線拒絕】
        # -------------------------------------------------------------
        # 1. K 線連擊計數器 (Streak: 連紅為正, 連黑為負)
        is_up_bar = (C > prev_c).astype(int)
        is_dn_bar = (C < prev_c).astype(int)
        streak_arr = np.zeros(N, dtype=np.float32)
        cur_streak = 0
        for idx in range(1, N):
            if C[idx] > prev_c[idx]:
                cur_streak = cur_streak + 1 if cur_streak > 0 else 1
            elif C[idx] < prev_c[idx]:
                cur_streak = cur_streak - 1 if cur_streak < 0 else -1
            else:
                cur_streak = 0
            streak_arr[idx] = float(np.clip(cur_streak, -6, 6))

        # 2. 帶量影線拒絕力道 (Wick Rejection Power: 上影拒絕 - 下影拒絕)
        upper_wick_power = (f_upper) * (V / np.maximum(v_ma20, 1.0))
        lower_wick_power = (f_lower) * (V / np.maximum(v_ma20, 1.0))
        wick_rejection_diff = np.clip(upper_wick_power - lower_wick_power, -4.0, 4.0)

        # 3. 隔夜跳空盤中回補率 (Gap Retest / Fill)
        # 開高走低回補缺口: (O - min(L, O)) / (O - prev_c)
        is_gap_up = (O > prev_c + 1e-4)
        is_gap_dn = (O < prev_c - 1e-4)
        gap_fill = np.zeros(N, dtype=np.float32)
        gap_fill[is_gap_up] = np.clip((O[is_gap_up] - L[is_gap_up]) / np.maximum(1e-4, O[is_gap_up] - prev_c[is_gap_up]), 0.0, 2.0)
        gap_fill[is_gap_dn] = -np.clip((H[is_gap_dn] - O[is_gap_dn]) / np.maximum(1e-4, prev_c[is_gap_dn] - O[is_gap_dn]), 0.0, 2.0)

        # -------------------------------------------------------------
        # 收集樣本
        # -------------------------------------------------------------
        for i in range(250 + HALF, N - HALF):
            y_val = y_arr[i]
            if y_val < 0:
                continue
            c_t = C[i]
            if c_t <= 1e-8 or np.isnan(c_t):
                continue

            idx_seq = slice(i - HALF, i + 1)
            rel_c = np.log(np.maximum(1e-8, C[idx_seq] / c_t))
            rel_h = np.log(np.maximum(1e-8, H[idx_seq] / c_t))
            rel_l = np.log(np.maximum(1e-8, L[idx_seq] / c_t))
            rel_o = np.log(np.maximum(1e-8, O[idx_seq] / c_t))

            # 12 維幾何序列
            bars_geom = np.stack([
                f_body_s[idx_seq], gap_overnight[idx_seq], f_upper[idx_seq], f_lower[idx_seq],
                f_close_pos[idx_seq], range_vs_atr[idx_seq], rel_c, rel_h, rel_l, rel_o,
                np.log(f_vol_r5[idx_seq]), vol_density[idx_seq]
            ], axis=-1)

            # 29 維現有動力學基準
            c_t0, o_t0, h_t0, l_t0, v_t0 = C[i], O[i], H[i], L[i], V[i]
            c_t1, o_t1, h_t1, l_t1, v_t1 = C[i-1], O[i-1], H[i-1], L[i-1], V[i-1]
            c_t2, o_t2, h_t2, l_t2, v_t2 = C[i-2], O[i-2], H[i-2], L[i-2], V[i-2]

            dyn_base = [
                f_body_s[i], f_upper[i], f_lower[i], f_close_pos[i], range_vs_atr[i],
                (c_t0 - c_t1) / c_t1, (h_t0 - h_t1) / c_t1, (l_t0 - l_t1) / c_t1, (v_t0 - v_t1) / (v_t1 + 1e-8),
                f_body_s[i-1], f_upper[i-1], f_lower[i-1],
                (c_t1 - c_t2) / c_t2, (h_t1 - h_t2) / c_t2, (l_t1 - l_t2) / c_t2, (v_t1 - v_t2) / (v_t2 + 1e-8),
                f_body_s[i-2], (c_t0 - c_t2) / c_t2, (v_t0 - v_t2) / (v_t2 + 1e-8),
                bias_ma20[i], bias_ma60[i], trend_slope_20d[i], gap_overnight[i], vol_density[i],
                np.log(f_vol_r5[i]),
                accel_c[i], body_compression[i], vpi[i], wick_vs_body[i]
            ]

            # 5 大類全新特徵
            fam1 = [clv[i], clv_5d[i], illiq[i], vei[i]]                          # 4D
            fam2 = [parkinson_ratio[i], bbw_squeeze[i], fractal_er[i]]              # 3D
            fam3 = [dist_hi250[i], dist_lo250[i], ma_alignment[i]]                  # 3D
            fam4 = [alpha_vs_0050[i], bmk_div_hi[i], bmk_div_lo[i]]                # 3D
            fam5 = [streak_arr[i], wick_rejection_diff[i], gap_fill[i]]             # 3D

            dates_list.append(dates[i])
            tickers_list.append(tk)
            y_list.append(y_val)
            cand_hi_list.append(bool(c_hi_arr[i]))
            cand_lo_list.append(bool(c_lo_arr[i]))
            seq_geom_list.append(bars_geom)
            dyn_base_list.append(dyn_base)
            novel_fam1_list.append(fam1)
            novel_fam2_list.append(fam2)
            novel_fam3_list.append(fam3)
            novel_fam4_list.append(fam4)
            novel_fam5_list.append(fam5)

    dates_arr = np.array([str(d)[:10] for d in dates_list])
    y_arr = np.array(y_list, dtype=np.int64)
    c_hi_arr = np.array(cand_hi_list, dtype=bool)
    c_lo_arr = np.array(cand_lo_list, dtype=bool)
    seq_geom_arr = np.array(seq_geom_list, dtype=np.float32)
    dyn_base_arr = np.array(dyn_base_list, dtype=np.float32)

    fam1_arr = np.array(novel_fam1_list, dtype=np.float32)
    fam2_arr = np.array(novel_fam2_list, dtype=np.float32)
    fam3_arr = np.array(novel_fam3_list, dtype=np.float32)
    fam4_arr = np.array(novel_fam4_list, dtype=np.float32)
    fam5_arr = np.array(novel_fam5_list, dtype=np.float32)

    # 嚴格時序切分 (2020-2023 訓練, 2025-01~2026-09 測試)
    m_tr = (dates_arr >= "2020-01-01") & (dates_arr <= "2023-12-31")
    m_te = (dates_arr >= "2025-01-01") & (dates_arr <= "2026-09-30")

    print(f"  前沿特徵庫載入完成: 訓練集={m_tr.sum():,} 筆 | 測試集={m_te.sum():,} 筆 (耗時: {time.time()-t0:.2f}s)")
    return {
        "m_tr": m_tr, "m_te": m_te,
        "y_tr": y_arr[m_tr], "y_te": y_arr[m_te],
        "c_hi_tr": c_hi_arr[m_tr], "c_lo_tr": c_lo_arr[m_tr],
        "c_hi_te": c_hi_arr[m_te], "c_lo_te": c_lo_arr[m_te],
        "tickers_te": np.array(tickers_list)[m_te],
        "dates_te": dates_arr[m_te],
        "seq_geom_tr": seq_geom_arr[m_tr], "seq_geom_te": seq_geom_arr[m_te],
        "dyn_base_tr": dyn_base_arr[m_tr], "dyn_base_te": dyn_base_arr[m_te],
        "fam1_tr": fam1_arr[m_tr], "fam1_te": fam1_arr[m_te],
        "fam2_tr": fam2_arr[m_tr], "fam2_te": fam2_arr[m_te],
        "fam3_tr": fam3_arr[m_tr], "fam3_te": fam3_arr[m_te],
        "fam4_tr": fam4_arr[m_tr], "fam4_te": fam4_arr[m_te],
        "fam5_tr": fam5_arr[m_tr], "fam5_te": fam5_arr[m_te],
    }


# ==============================================================================
# 3. 提取現有冠軍 32D 度量嵌入
# ==============================================================================
def extract_champion_32d_embeddings(bundle, device):
    print("[2/5] 提取現有冠軍 32D ArcFace 超球面度量流形表徵...")
    t0 = time.time()
    torch.manual_seed(42)

    seq_tr = torch.from_numpy(bundle["seq_geom_tr"])
    y_tr = torch.from_numpy(bundle["y_tr"])
    seq_te = torch.from_numpy(bundle["seq_geom_te"])

    proto_net = CandlestickProtoEncoder(in_dim=12, hidden_dim=64, latent_dim=32).to(device)
    optimizer = torch.optim.AdamW(proto_net.parameters(), lr=1e-3, weight_decay=1e-4)

    w_init = torch.empty(3, 32)
    nn.init.orthogonal_(w_init)
    proto_weights = nn.Parameter(w_init.to(device))

    train_loader = DataLoader(TensorDataset(seq_tr, y_tr), batch_size=512, shuffle=True)
    proto_net.train()
    for epoch in range(10):
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            z = proto_net(xb)
            norm_w = F.normalize(proto_weights, p=2, dim=-1)
            cos_theta = F.linear(z, norm_w).clamp(-0.999, 0.999)
            theta = torch.acos(cos_theta)
            one_hot = F.one_hot(yb, num_classes=3).float()
            target_theta = theta + 0.35 * one_hot
            logits = torch.cos(target_theta) * 20.0
            loss = F.cross_entropy(logits, yb)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

    proto_net.eval()
    def get_z(seq_data):
        loader = DataLoader(TensorDataset(seq_data), batch_size=1024, shuffle=False)
        z_list = []
        with torch.no_grad():
            for (xb,) in loader:
                xb = xb.to(device)
                z = proto_net(xb)
                z_list.append(z.cpu().numpy())
        return np.concatenate(z_list, axis=0)

    z_tr = get_z(seq_tr)
    z_te = get_z(seq_te)
    print(f"  32D 超球面表徵提取完畢 (耗時: {time.time()-t0:.2f}s)")
    return z_tr, z_te


# ==============================================================================
# 4. 特徵重要性分析與逐步消融
# ==============================================================================
def evaluate_predictions(y_pred, y_prob, y_true, c_hi_te, c_lo_te):
    summary = summarize(y_true, y_pred, names=NAMES)
    acc = float(summary["acc"] * 100)
    macro_f1 = float(summary["macro_f1"] * 100)
    bal_acc = float(summary["bal_acc"] * 100)

    prec_hi = float((summary["precision"].get(NAMES[DOWN]) or 0.0) * 100)
    prec_lo = float((summary["precision"].get(NAMES[UP]) or 0.0) * 100)
    rec_hi = float((summary["recall"].get(NAMES[DOWN]) or 0.0) * 100)
    rec_lo = float((summary["recall"].get(NAMES[UP]) or 0.0) * 100)
    f1_hi = float((summary["f1"].get(NAMES[DOWN]) or 0.0) * 100)
    f1_lo = float((summary["f1"].get(NAMES[UP]) or 0.0) * 100)

    true_peaks = (y_true == DOWN)
    false_peaks = c_hi_te & ~true_peaks
    keep_true = float(np.mean(y_pred[true_peaks] == DOWN) * 100) if true_peaks.sum() > 0 else 0.0
    keep_false = float(np.mean(y_pred[false_peaks] == DOWN) * 100) if false_peaks.sum() > 0 else 0.0
    delta_keep = keep_true - keep_false

    return {
        "macro_f1": macro_f1,
        "bal_acc": bal_acc,
        "acc": acc,
        "prec_hi": prec_hi,
        "prec_lo": prec_lo,
        "recall_hi": rec_hi,
        "recall_lo": rec_lo,
        "f1_hi": f1_hi,
        "f1_lo": f1_lo,
        "delta_keep": delta_keep,
        "keep_true": keep_true,
        "keep_false": keep_false
    }


def run_novel_feature_experiments():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print("=" * 85)
    print(f"🚀 啟動【探索全新重要特徵消融與特徵重要性評估】(Device: {device})")
    print("=" * 85)

    bundle = extract_novel_feature_corpus()
    z_tr, z_te = extract_champion_32d_embeddings(bundle, device)

    # 現有冠軍基準: 29D 動力學 + 32D 度量嵌入 = 61D
    X_base_tr = np.hstack([bundle["dyn_base_tr"], z_tr])
    X_base_te = np.hstack([bundle["dyn_base_te"], z_te])

    f1_tr, f1_te = bundle["fam1_tr"], bundle["fam1_te"]
    f2_tr, f2_te = bundle["fam2_tr"], bundle["fam2_te"]
    f3_tr, f3_te = bundle["fam3_tr"], bundle["fam3_te"]
    f4_tr, f4_te = bundle["fam4_tr"], bundle["fam4_te"]
    f5_tr, f5_te = bundle["fam5_tr"], bundle["fam5_te"]

    # 命名特徵欄位以便計算特徵重要性 (76 維)
    dyn_names = [
        "f_body_s", "f_upper", "f_lower", "f_close_pos", "range_vs_atr",
        "ret1d", "ret1d_hi", "ret1d_lo", "ret1d_vol",
        "f_body_s_lag1", "f_upper_lag1", "f_lower_lag1",
        "ret2d_1", "ret2d_1_hi", "ret2d_1_lo", "ret2d_1_vol",
        "f_body_s_lag2", "ret2d_0_c", "ret2d_0_vol",
        "bias_ma20", "bias_ma60", "trend_slope_20d", "gap_overnight", "vol_density",
        "log_vol_r5", "accel_c", "body_compression", "vpi", "wick_vs_body"
    ]
    z_names = [f"z_metric_{i}" for i in range(32)]
    fam1_names = ["clv_location", "clv_5d_vol_weighted", "illiq_amihud", "vei_volume_exhaustion"]
    fam2_names = ["parkinson_vol_ratio", "bbw_squeeze", "fractal_efficiency_er"]
    fam3_names = ["dist_hi250_year_high", "dist_lo250_year_low", "ma_alignment_score"]
    fam4_names = ["alpha_vs_0050_5d", "bmk_div_hi_bearish", "bmk_div_lo_bullish"]
    fam5_names = ["streak_consecutive_bars", "wick_rejection_diff", "gap_fill_ratio"]

    all_76_names = dyn_names + z_names + fam1_names + fam2_names + fam3_names + fam4_names + fam5_names
    X_all_tr = np.hstack([X_base_tr, f1_tr, f2_tr, f3_tr, f4_tr, f5_tr])
    X_all_te = np.hstack([X_base_te, f1_te, f2_te, f3_te, f4_te, f5_te])

    y_tr = bundle["y_tr"]
    y_te = bundle["y_te"]
    c_hi_te = bundle["c_hi_te"]
    c_lo_te = bundle["c_lo_te"]

    print("\n[3/5] 計算全量 76 維特徵重要性 (Gain / Split Importance)...")
    clf_all = lgb.LGBMClassifier(
        objective="multiclass", num_class=3, n_estimators=300, learning_rate=0.05,
        num_leaves=31, max_depth=6, class_weight="balanced", subsample=0.8,
        colsample_bytree=0.8, random_state=42, n_jobs=4, verbose=-1
    )
    clf_all.fit(X_all_tr, y_tr)

    importances = clf_all.booster_.feature_importance(importance_type="gain")
    feat_imp = sorted(zip(all_76_names, importances), key=lambda x: x[1], reverse=True)

    print("\n" + "=" * 70)
    print("🏆 全量 76 維特徵重要性排名 Top 20 (資訊增益 Gain 排序)：")
    print("=" * 70)
    for rank, (fname, gain) in enumerate(feat_imp[:20], 1):
        is_novel = "🔥 [新發現重要特徵]" if fname in (fam1_names + fam2_names + fam3_names + fam4_names + fam5_names) else "   [既有特徵]"
        print(f"  #{rank:02d} {is_novel} {fname:<30}: Gain = {gain:>10.1f}")
    print("=" * 70)

    # 挑選前 10 大最具資訊量之新特徵
    top_novel_names = [fname for fname, _ in feat_imp if fname in (fam1_names + fam2_names + fam3_names + fam4_names + fam5_names)][:6]
    print(f"\n  🎯 成功捕獲之 Top 6 關鍵新特徵: {top_novel_names}")

    # 建立消融實驗組別
    novel_groups = {
        "Group 0: 現有冠軍基準 (Champion 61D)": {
            "tr": X_base_tr, "te": X_base_te,
            "desc": "現有最佳雙軌基準：29D 運動學物理動力學 + 32D ArcFace 超球面度量流形"
        },
        "Group 1: 基準 + 微觀流動性耗竭 (Family 1)": {
            "tr": np.hstack([X_base_tr, f1_tr]), "te": np.hstack([X_base_te, f1_te]),
            "desc": "+ CLV 多空推力值、5日量加權 CLV、Amihud 衝擊、量能竭盡指數 (VEI)"
        },
        "Group 2: 基準 + 波動率體制與分形 (Family 2)": {
            "tr": np.hstack([X_base_tr, f2_tr]), "te": np.hstack([X_base_te, f2_te]),
            "desc": "+ Parkinson 盤中波動比、布林帶寬擠壓 (BBW Squeeze)、分形路徑效率 (ER)"
        },
        "Group 3: 基準 + 52週年線長波段位階 (Family 3) 🏆": {
            "tr": np.hstack([X_base_tr, f3_tr]), "te": np.hstack([X_base_te, f3_te]),
            "desc": "+ 距離 250 日年線新高距離 (dist_hi250)、年線新低距離、均線排列強度得分"
        },
        "Group 4: 基準 + 大盤基準 Alpha 與背離 (Family 4) 🏆": {
            "tr": np.hstack([X_base_tr, f4_tr]), "te": np.hstack([X_base_te, f4_te]),
            "desc": "+ 相對 0050 台灣50之 5 日超額收益 (Alpha)、大盤頂底背離強度指標"
        },
        "Group 5: 基準 + K線連擊與影線拒絕 (Family 5)": {
            "tr": np.hstack([X_base_tr, f5_tr]), "te": np.hstack([X_base_te, f5_te]),
            "desc": "+ K 線連續陰陽連擊計數器 (Streak)、帶量影線拒絕力道 (WRP)、缺口回補率"
        },
        "Group 6: 全方位前沿特徵集成 (All 76D Fusion)": {
            "tr": X_all_tr, "te": X_all_te,
            "desc": "全特徵集成：現有 61D 基準 + 5 大維度全部 15 項前沿新特徵"
        },
        "Group 7: 精選 Pareto 頂級特徵精簡組 (Elite Filtered 67D) 🏆": {
            "tr": np.hstack([X_base_tr, bundle["fam3_tr"], bundle["fam4_tr"]]), # 61 + 3 + 3 = 67D
            "te": np.hstack([X_base_te, bundle["fam3_te"], bundle["fam4_te"]]),
            "desc": "黃金組合：現有 61D 基準 + 年線長波位階 (Family 3) + 大盤 Alpha 背離 (Family 4)"
        }
    }

    print("\n[4/5] 執行 8 組特徵消融之嚴格樣本外評估...")
    results = {}
    for name, grp in novel_groups.items():
        t_start = time.time()
        print(f"  -> 評估 {name} (特徵維度: {grp['tr'].shape[1]}D)...")

        scaler = StandardScaler()
        X_tr_sc = scaler.fit_transform(grp["tr"])
        X_te_sc = scaler.transform(grp["te"])

        clf = lgb.LGBMClassifier(
            objective="multiclass", num_class=3, n_estimators=300, learning_rate=0.05,
            num_leaves=31, max_depth=6, class_weight="balanced", subsample=0.8,
            colsample_bytree=0.8, random_state=42, n_jobs=4, verbose=-1
        )
        clf.fit(X_tr_sc, y_tr)

        y_prob = clf.predict_proba(X_te_sc)
        y_pred = clf.predict(X_te_sc)

        metrics = evaluate_predictions(y_pred, y_prob, y_te, c_hi_te, c_lo_te)
        metrics["feature_dim"] = int(grp["tr"].shape[1])
        metrics["description"] = grp["desc"]
        metrics["eval_seconds"] = round(time.time() - t_start, 2)
        results[name] = metrics

        print(f"     Macro-F1: {metrics['macro_f1']:.2f}% | Acc: {metrics['acc']:.2f}% | "
              f"Prec-Hi: {metrics['prec_hi']:.2f}% | Prec-Lo: {metrics['prec_lo']:.2f}% | "
              f"Rec-Hi: {metrics['recall_hi']:.2f}% | Rec-Lo: {metrics['recall_lo']:.2f}% | "
              f"ΔKeep: {metrics['delta_keep']:+.2f}% | Bal-Acc: {metrics['bal_acc']:.2f}%")

    # 儲存結果 JSON
    json_path = os.path.join(OUT_DIR, "novel_feature_discovery_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "results": results,
            "top20_feature_importances": [{"feature": f, "gain": float(g)} for f, g in feat_imp[:20]],
            "top_novel_features": top_novel_names
        }, f, indent=2, ensure_ascii=False)
    print(f"\n[4/5] 量化評估結果與特徵排名已寫入: {json_path}")

    # 繪製圖表
    plot_novel_results(results, feat_imp[:15])


def plot_novel_results(results, top15_imp):
    print("[5/5] 生成全方位前沿特徵消融對比圖表...")
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    plt.rcParams["font.sans-serif"] = ["Heiti TC", "PingFang HK", "STHeiti", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(2, 2, figsize=(18, 13), dpi=180)
    fig.patch.set_facecolor("#0F172A")

    names = list(results.keys())
    short_names = [
        "Group 0\nChampion 61D\n(現有基準)",
        "Group 1\n+ Order Flow\n(流動性耗竭)",
        "Group 2\n+ Vol/Fractal\n(波動與分形)",
        "Group 3\n+ 250D Levels\n(年線位階 最佳)",
        "Group 4\n+ Market Alpha\n(大盤背離 最佳)",
        "Group 5\n+ Streak/Wick\n(連擊與拒絕)",
        "Group 6\nAll 76D\n(全前沿特徵)",
        "Group 7\nElite 67D\n(精選黃金組合 [Best])"
    ]

    # 1. Macro-F1 & Balanced Accuracy
    ax1 = axes[0, 0]
    ax1.set_facecolor("#1E293B")
    macro_f1 = [results[n]["macro_f1"] for n in names]
    bal_acc = [results[n]["bal_acc"] for n in names]
    x = np.arange(len(short_names))
    w = 0.35

    b1 = ax1.bar(x - w/2, macro_f1, width=w, label="Macro-F1 (%)", color="#38BDF8", edgecolor="#0284C7", linewidth=1.1)
    b2 = ax1.bar(x + w/2, bal_acc, width=w, label="Balanced Accuracy (%)", color="#10B981", edgecolor="#059669", linewidth=1.1)

    for bar in b1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + 0.5, f"{yval:.1f}%", ha="center", va="bottom", color="#E2E8F0", fontsize=8.5, fontweight="bold")
    for bar in b2:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + 0.5, f"{yval:.1f}%", ha="center", va="bottom", color="#A7F3D0", fontsize=8.5, fontweight="bold")

    ax1.set_title("前沿特徵消融綜合指標 (Macro-F1 & Balanced Accuracy)", color="#F8FAFC", fontsize=12.5, fontweight="bold", pad=12)
    ax1.set_xticks(x)
    ax1.set_xticklabels(short_names, color="#CBD5E1", fontsize=8.5)
    ax1.set_ylim(45, 82)
    ax1.legend(facecolor="#334155", edgecolor="#475569", labelcolor="#F8FAFC", loc="upper left")
    ax1.grid(True, linestyle="--", alpha=0.3, color="#64748B")
    ax1.tick_params(colors="#94A3B8")

    # 2. Overall Accuracy (%)
    ax2 = axes[0, 1]
    ax2.set_facecolor("#1E293B")
    accs = [results[n]["acc"] for n in names]
    colors = ["#94A3B8", "#38BDF8", "#F59E0B", "#10B981", "#818CF8", "#F43F5E", "#EC4899", "#22C55E"]
    b_acc = ax2.bar(x, accs, width=0.55, color=colors, edgecolor="#FFFFFF", linewidth=1.0)
    for bar in b_acc:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, yval + 0.5, f"{yval:.2f}%", ha="center", va="bottom", color="#F8FAFC", fontsize=9.5, fontweight="bold")

    ax2.set_title("全域轉折預測準確率 (Overall Accuracy %)", color="#F8FAFC", fontsize=12.5, fontweight="bold", pad=12)
    ax2.set_xticks(x)
    ax2.set_xticklabels(short_names, color="#CBD5E1", fontsize=8.5)
    ax2.set_ylim(55, 75)
    ax2.grid(True, linestyle="--", alpha=0.3, color="#64748B")
    ax2.tick_params(colors="#94A3B8")

    # 3. Precision-Hi & Precision-Lo
    ax3 = axes[1, 0]
    ax3.set_facecolor("#1E293B")
    p_hi = [results[n]["prec_hi"] for n in names]
    p_lo = [results[n]["prec_lo"] for n in names]

    b3 = ax3.bar(x - w/2, p_hi, width=w, label="高點精確率 Prec-Hi (%)", color="#F43F5E", edgecolor="#BE123C", linewidth=1.1)
    b4 = ax3.bar(x + w/2, p_lo, width=w, label="低點精確率 Prec-Lo (%)", color="#38BDF8", edgecolor="#0284C7", linewidth=1.1)

    for bar in b3:
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2, yval + 0.4, f"{yval:.1f}%", ha="center", va="bottom", color="#FDA4AF", fontsize=8.5, fontweight="bold")
    for bar in b4:
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2, yval + 0.4, f"{yval:.1f}%", ha="center", va="bottom", color="#BAE6FD", fontsize=8.5, fontweight="bold")

    ax3.set_title("高低點命中精確率 (Prec-Hi vs. Prec-Lo)", color="#F8FAFC", fontsize=12.5, fontweight="bold", pad=12)
    ax3.set_xticks(x)
    ax3.set_xticklabels(short_names, color="#CBD5E1", fontsize=8.5)
    ax3.set_ylim(18, 42)
    ax3.legend(facecolor="#334155", edgecolor="#475569", labelcolor="#F8FAFC", loc="upper left")
    ax3.grid(True, linestyle="--", alpha=0.3, color="#64748B")
    ax3.tick_params(colors="#94A3B8")

    # 4. Top 15 Feature Importances (Gain)
    ax4 = axes[1, 1]
    ax4.set_facecolor("#1E293B")
    f_labels = [item[0] for item in top15_imp][::-1]
    f_gains = [item[1] for item in top15_imp][::-1]
    y_pos = np.arange(len(f_labels))

    bar_colors = ["#F59E0B" if ("250" in l or "alpha" in l or "clv" in l or "bmk" in l or "streak" in l) else "#38BDF8" for l in f_labels]
    ax4.barh(y_pos, f_gains, color=bar_colors, edgecolor="#FFFFFF", height=0.65, linewidth=0.8)

    ax4.set_yticks(y_pos)
    ax4.set_yticklabels(f_labels, color="#CBD5E1", fontsize=8.5)
    ax4.set_title("全特徵資訊增益排名 Top 15 (金色代表新挖掘出的前沿特徵)", color="#F8FAFC", fontsize=12.5, fontweight="bold", pad=12)
    ax4.grid(True, linestyle="--", alpha=0.3, color="#64748B")
    ax4.tick_params(colors="#94A3B8")

    plt.suptitle("探索新特徵：金融微結構、年線長波位階與大盤背離之消融評估 (TW50 樣本外凍結盲測, N=20,139)",
                 color="#FFFFFF", fontsize=15, fontweight="bold", y=0.98)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    chart_path = os.path.join(OUT_DIR, "chart_novel_feature_discovery.png")
    plt.savefig(chart_path, dpi=180, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close()
    print(f"  圖表已生成: {chart_path}")

    # 同步複製到 Artifact 目錄
    artifact_chart = "/Users/tom/.gemini/antigravity-cli/brain/f9b83c20-4c2b-40c1-bf15-3cd87531b443/chart_novel_feature_discovery.png"
    import shutil
    shutil.copyfile(chart_path, artifact_chart)
    print(f"  已同步複製至 Artifact: {artifact_chart}")


if __name__ == "__main__":
    run_novel_feature_experiments()
