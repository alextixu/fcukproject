"""網頁系統測試的輔助函式(獨立模組名稱,避免和研究測試的 conftest 衝突)。"""
import numpy as np
import pandas as pd


def make_bars(closes, start="2026-01-05", volume=1000.0):
    """由收盤價做出 K 線:開盤 = 前一天收盤,高 / 低 = 開收的最大 / 最小 ± 0.2%。"""
    c = np.asarray(closes, dtype=float)
    o = np.r_[c[0], c[:-1]]
    idx = pd.bdate_range(start, periods=len(c))
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.002, "low": np.minimum(o, c) * 0.998,
                         "close": c, "volume": volume}, index=idx)
