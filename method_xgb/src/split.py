"""時間序切分 + purge。特徵已在整段序列上以回看視窗計算,暖機自動成立。"""
import numpy as np
import pandas as pd


def time_split(panel: pd.DataFrame, train_end: str, val_end: str, h: int, ycol: str):
    dates = panel.index.get_level_values("date")
    udates = np.array(sorted(dates.unique()))
    train_end, val_end = pd.Timestamp(train_end), pd.Timestamp(val_end)

    tr_dates = udates[udates <= train_end][:-h] if h > 0 else udates[udates <= train_end]
    va_dates = udates[(udates > train_end) & (udates <= val_end)]
    va_dates = va_dates[:-h] if h > 0 else va_dates
    te_dates = udates[udates > val_end]

    def pick(ds):
        m = dates.isin(ds) & panel[ycol].notna().values
        return panel[m]

    return pick(tr_dates), pick(va_dates), pick(te_dates)


def apply_deadzone(parts, h: int, dz: float):
    """漲跌標籤的死區:|r_h| < dz 的樣本(train/val/test)全部拿掉,只分「明顯漲 / 明顯跌」。"""
    out = []
    for p in parts:
        m = p[f"r_h{h}"].abs() >= dz
        out.append(p[m.values])
    return tuple(out)


def filter_features(train: pd.DataFrame, feats: list, max_nan: float = 0.3):
    """只用訓練集統計:剔除 NaN 比例過高或常數欄。回傳 (kept, stats_df)。"""
    X = train[feats]
    nan_ratio = X.isna().mean()
    std = X.std()
    stats = pd.DataFrame({"nan_ratio": nan_ratio, "mean": X.mean(), "std": std})
    kept = [f for f in feats if nan_ratio[f] <= max_nan and std[f] > 0 and np.isfinite(std[f])]
    stats["kept"] = stats.index.isin(kept)
    return kept, stats
