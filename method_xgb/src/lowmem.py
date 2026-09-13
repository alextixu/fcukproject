"""低記憶體 panel 建構(tw500 用):特徵逐檔寫進磁碟 memmap,訓練時只讀需要的欄位。

快取檔:<prefix>.dat(float32 memmap, N×C)、<prefix>_index.parquet(date, ticker)、<prefix>_cols.json。
Windows 的 memmap 以檔案為後備儲存,不吃 commit 額度(本機分頁檔僅 512 MB)。
"""
import json
import os

import numpy as np
import pandas as pd

from features import single_stock_features, CHIP_COLUMNS, chip_features
from features.cross_section import cross_section_features, RANK_COLS
from features.chip import CHIP_RANK_COLS
from features._util import W
from data import paper9_indicators, PAPER9_NAMES
from labels import HORIZONS

OHLCV = ["open", "high", "low", "close", "volume"]
LABEL_COLS = [f"{p}_h{h}" for h in HORIZONS for p in ("r", "y_bin", "y_cs")]


def cs_column_names(has_chip):
    cols = [f"cs_rank_{c}" for c in RANK_COLS] + [f"cs_excess_roc_{w}" for w in W]
    cols += ["mkt_roc_5", "mkt_roc_20", "mkt_roc_60", "cs_beta_60", "cs_idio_std_60",
             "cs_rank_excess_roc_20"]
    if has_chip:
        cols += [f"cs_rank_{c}" for c in CHIP_RANK_COLS]
    return cols


def build_lowmem(stock_data: dict, prefix: str, chip_data: dict = None, verbose=True):
    has_chip = chip_data is not None
    # 先探一檔決定欄位
    tk0, df0 = next(iter(stock_data.items()))
    f0, fam = single_stock_features(df0)
    feat_cols = list(f0.columns)
    base_cols = OHLCV + feat_cols + PAPER9_NAMES + (list(CHIP_COLUMNS) if has_chip else [])
    cs_cols = cs_column_names(has_chip)
    cols = base_cols + cs_cols + LABEL_COLS
    for k in PAPER9_NAMES:
        fam[k] = "paper9"
    if has_chip:
        for k in CHIP_COLUMNS:
            fam[k] = "chip"
    for k in cs_cols:
        fam[k] = "cross_section"

    n_total = sum(len(df) for df in stock_data.values())
    mm = np.memmap(prefix + ".dat", dtype=np.float32, mode="w+", shape=(n_total, len(cols)))
    dates, tickers = [], []
    pos = 0
    nb = len(base_cols)
    for i, (tk, df) in enumerate(stock_data.items()):
        feats, _ = single_stock_features(df)
        p9 = paper9_indicators(df, n=140, stats=(0.0, 1.0)).astype(np.float32)
        arrs = [df[OHLCV].values.astype(np.float32), feats.values.astype(np.float32), p9]
        if has_chip:
            arrs.append(chip_features(df, chip_data.get(tk, {})).shift(1).values.astype(np.float32))
        block = np.hstack(arrs)
        block[~np.isfinite(block)] = np.nan
        mm[pos:pos + len(df), :nb] = block
        dates.append(df.index.values)
        tickers.append(np.repeat(tk, len(df)))
        pos += len(df)
        del feats, p9, block
        if verbose and (i + 1) % 50 == 0:
            print(f"  特徵 {i + 1}/{len(stock_data)}", flush=True)
    mm.flush()
    index = pd.MultiIndex.from_arrays([np.concatenate(dates), np.concatenate(tickers)],
                                      names=["date", "ticker"])
    pd.DataFrame({"date": index.get_level_values(0), "ticker": index.get_level_values(1)}
                 ).to_parquet(prefix + "_index.parquet")

    # 橫斷面:只讀需要的欄位
    need = list(dict.fromkeys(RANK_COLS + [f"roc_{w}" for w in W] + ["ret_lag_1"]
                              + (CHIP_RANK_COLS if has_chip else [])))
    small = pd.DataFrame({c: np.array(mm[:, cols.index(c)]) for c in need}, index=index)
    cs = cross_section_features(small)
    del small
    assert list(cs.columns) == cs_cols, (list(cs.columns), cs_cols)
    for c in cs_cols:
        mm[:, cols.index(c)] = cs[c].values.astype(np.float32)
    del cs

    # 標籤
    close = pd.Series(np.array(mm[:, cols.index("close")]), index=index).unstack("ticker")
    for h in HORIZONS:
        r = (close.shift(-h) / close - 1).stack(future_stack=True).reindex(index)
        med = r.groupby(level="date").transform("median")
        mm[:, cols.index(f"r_h{h}")] = r.values.astype(np.float32)
        mm[:, cols.index(f"y_bin_h{h}")] = (r > 0).astype(float).where(r.notna()).values.astype(np.float32)
        mm[:, cols.index(f"y_cs_h{h}")] = (r > med).astype(float).where(r.notna()).values.astype(np.float32)
    mm.flush()
    del mm
    json.dump({"cols": cols, "shape": [n_total, len(cols)], "family": fam},
              open(prefix + "_cols.json", "w", encoding="utf-8"), ensure_ascii=False)
    return fam


def load_lowmem(prefix: str, columns: list, train_end=None, stride: int = 1):
    """只載入 columns;stride>1 時訓練期(date ≤ train_end)只保留每 stride 個交易日的列。"""
    meta = json.load(open(prefix + "_cols.json", encoding="utf-8"))
    cols, shape = meta["cols"], tuple(meta["shape"])
    mm = np.memmap(prefix + ".dat", dtype=np.float32, mode="r", shape=shape)
    idx = pd.read_parquet(prefix + "_index.parquet")
    dates = pd.to_datetime(idx["date"]).values
    keep = np.ones(len(idx), dtype=bool)
    if stride > 1 and train_end is not None:
        te = np.datetime64(pd.Timestamp(train_end))
        ud = np.sort(np.unique(dates[dates <= te]))[::stride]
        keep = (dates > te) | np.isin(dates, ud)
    index = pd.MultiIndex.from_arrays([dates[keep], idx["ticker"].values[keep]],
                                      names=["date", "ticker"])
    columns = list(dict.fromkeys(columns))
    data = {}
    for c in columns:
        if c in cols:
            col = np.array(mm[:, cols.index(c)])
            data[c] = col[keep] if stride > 1 else col
            del col
    del mm
    return pd.DataFrame(data, index=index), meta["family"]
