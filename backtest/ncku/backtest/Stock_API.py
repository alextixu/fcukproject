# -*- coding: utf-8 -*-
"""
Top-level shim for old scripts.

Old code can keep:
    from Stock_API import Stock_API

This file delegates to the new package wrapper:
    stock_api.legacy.Stock_API
"""

from backtest.stock_api.legacy import Stock_API

__all__ = ["Stock_API"]
