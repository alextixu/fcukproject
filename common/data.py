"""讀取已快取的台股日 OHLCV。"""
import os
import sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from common import paths as P
from data_loader import fetch_yfinance, TICKER_SETS
from indicators import compute_indicators as paper9_indicators

CACHE_DIR = os.environ.get("TW_CACHE_DIR") or P.YF_CACHE

PAPER9_NAMES = ["p9_sma", "p9_wma", "p9_mom", "p9_macd", "p9_willr",
                "p9_cci", "p9_stoch_k", "p9_stoch_d", "p9_rsi"]


def load_pool(pool: str, start: str, end: str, min_len: int = 250) -> dict:
    """回傳 {ticker: DataFrame[open,high,low,close,volume]},長度不足者剔除。"""
    tickers = TICKER_SETS[pool]
    data = fetch_yfinance(tickers, start, end, cache_dir=CACHE_DIR)
    out = {}
    for tk, df in data.items():
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        df = df[~df.index.duplicated()].sort_index()
        if len(df) >= min_len and (df["close"] > 0).all():
            out[tk] = df
    return out

