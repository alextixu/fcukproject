"""股票池(2026-11-02 使用者剔除 16 檔低波動股)。"""
import pandas as pd

import mainline as ML
from feasibility import clean


def test_module_pool_excludes_low_vol(data):
    """Given 完整 TW50 50 檔與使用者剔除的 16 檔 / When 讀主軸的股票池 / Then 剩 34 檔,剔除的一檔都不在,其餘都是 TW50 成分股"""
    pool = ML.load_data()
    assert len(ML.EXCLUDE) == 16 and set(ML.EXCLUDE) <= set(data)
    assert set(pool) == set(data) - set(ML.EXCLUDE) and len(pool) == 34


def test_module_excluded_are_lowest_volatility(data):
    """Given 2020-01 以後每檔的每日漲跌幅(絕對值)中位數 / When 由低到高排序 / Then 剔除的 16 檔正好是最低的 16 檔(中華電 ~ 中信金)"""
    med = pd.Series({tk: clean(df)["close"].loc["2020-01-01":].pct_change().abs().median() for tk, df in data.items()})
    assert set(med.nsmallest(16).index) == set(ML.EXCLUDE)
