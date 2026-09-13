# -*- coding: utf-8 -*-
"""
Legacy compatibility wrapper for the old single-file Stock_API class.

Place this file at:
    stock_api/legacy.py

Then expose it from stock_api/__init__.py, or use the top-level Stock_API.py shim.
"""

from typing import List, Any
import pandas as pd

from .core import (
    get_taiwan_stock_data,
    get_all_stock_list,
    Get_User_Stocks as _Get_User_Stocks,
    Buy_Stock as _Buy_Stock,
    Sell_Stock as _Sell_Stock,
)


class Stock_API:
    """Keep the old class interface while delegating to the new stock_api package."""

    def __init__(self, account: str, password: str):
        self.account = account
        self.password = password

    @staticmethod
    def _normalize_date(date_value: Any) -> str:
        """
        Old examples use YYYYMMDD, while the new package uses YYYY-MM-DD.
        This also accepts already-normalized YYYY-MM-DD strings.
        """
        s = str(date_value).strip()
        if len(s) == 8 and s.isdigit():
            return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
        return s

    @staticmethod
    def _dataframe_to_legacy_records(df: pd.DataFrame):
        """
        Convert the new pandas DataFrame output into a JSON-like list[dict],
        which is closest to the old API response['data'] behavior.
        """
        if df is None:
            return []

        out = df.copy()

        # Old API data was JSON-like; avoid returning pandas Timestamp / NaN objects.
        if "date" in out.columns:
            out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")

        out = out.where(pd.notnull(out), None)
        return out.to_dict("records")

    @staticmethod
    def Get_Stock_Informations(stock_code, start_date, stop_date):
        """
        Old-compatible stock information method.

        Input:
            stock_code: 股票代號
            start_date: 舊版常用 YYYYMMDD；也接受 YYYY-MM-DD
            stop_date:  舊版常用 YYYYMMDD；也接受 YYYY-MM-DD
        Output:
            list[dict]，欄位維持 date/capacity/turnover/high/low/close/change/
            transaction_volume/stock_code_id/open
        """
        stock_code = str(stock_code)
        start = Stock_API._normalize_date(start_date)
        stop = Stock_API._normalize_date(stop_date)

        try:
            df = get_taiwan_stock_data(stock_code, start, stop)
            return Stock_API._dataframe_to_legacy_records(df)
        except Exception as exc:
            # Match old style: fail quietly enough for old backtest scripts to continue.
            print(f"connect fail or data fetch fail: {exc}")
            return dict([])

    def Get_User_Stocks(self):
        """Old-compatible instance method for holdings."""
        return _Get_User_Stocks(self.account, self.password)

    def Buy_Stock(self, stock_code, stock_shares, stock_price):
        """Old-compatible instance method for buy order."""
        return _Buy_Stock(
            self.account,
            self.password,
            stock_code,
            stock_shares,
            stock_price,
        )

    def Sell_Stock(self, stock_code, stock_shares, stock_price):
        """Old-compatible instance method for sell order."""
        return _Sell_Stock(
            self.account,
            self.password,
            stock_code,
            stock_shares,
            stock_price,
        )

    @staticmethod
    def get_all_stock_information() -> List[str]:
        """
        Old-compatible all-stock-list method.
        The old implementation kept only 4-character stock codes; keep that behavior.
        """
        try:
            codes = get_all_stock_list()
            return [str(code) for code in codes if len(str(code)) == 4]
        except Exception as exc:
            print(f"get stock list fail: {exc}")
            return []
