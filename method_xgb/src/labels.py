"""標籤:r_h、y_bin_h(漲跌)、y_cs_h(橫斷面高於中位數)。"""
import pandas as pd

HORIZONS = [1, 5, 20]


def add_labels(panel: pd.DataFrame, horizons=HORIZONS) -> pd.DataFrame:
    close = panel["close"].unstack("ticker")
    for h in horizons:
        r = (close.shift(-h) / close - 1).stack(future_stack=True).reindex(panel.index)
        panel[f"r_h{h}"] = r
        panel[f"y_bin_h{h}"] = (r > 0).astype(float).where(r.notna())
        med = r.groupby(level="date").transform("median")
        panel[f"y_cs_h{h}"] = (r > med).astype(float).where(r.notna())
    return panel


def label_col(kind: str, h: int) -> str:
    return f"y_{kind}_h{h}"
