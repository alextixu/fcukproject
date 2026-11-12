"""畫面用的價格:實際成交價(證交所官方資料)只用來顯示,模型與判斷一律用還原價;個股 K 線是今年整年;今年的對答案統計。"""
import json
import os

import pandas as pd
import pytest

from system import config as C, publish as PB
from test_system import DATE, ran_daily  # noqa: F401  (共用每日批次的 fixture)

ASOF = pd.Timestamp("2026-09-10")


def _official(code):
    o = pd.read_parquet(os.path.join(C.OFFICIAL, f"{code}.parquet"))
    o["date"] = pd.to_datetime(o["date"])
    return o.set_index("date").sort_index()


def test_display_uses_actual_price_not_adjusted(real_store):
    """Given 中華電(2412)2026-07-09 除息,還原價把之前的價格往下調 / When 產生個股頁的 K 線 / Then 用證交所的實際成交價:
    2026-01-02 收盤 132.00(還原價是 127.08);最後一天兩者相同 139.5;漲跌幅用證交所的漲跌價差"""
    df = real_store.load("2412.TW")
    d = PB.display_bars("2412", df, ASOF)
    bars = {b[0]: b for b in d["bars"]}
    assert d["price"] == "actual" and d["close_date"] == "2026-09-10"
    assert bars["2026-01-02"][4] == 132.0 and round(df.loc["2026-01-02", "close"], 2) == pytest.approx(127.08, abs=0.01)
    assert d["close"] == 139.5 == round(df.loc[ASOF, "close"], 2)
    off = _official("2412").loc[ASOF]
    assert d["chg_pct"] == pytest.approx(off["change"] / (off["close"] - off["change"]) * 100, abs=1e-3)


def test_display_drops_days_without_trading(real_store):
    """Given 2026-07-10 休市,Yahoo 補了一根量 0 的 K 棒 / When 產生台積電的實際成交價 K 線 / Then 07-10 不出現、07-09 和 07-13 都在;
    K 線的日期全部是證交所有交易的日子"""
    df = real_store.load("2330.TW")
    assert df.loc["2026-07-10", "volume"] == 0
    dates = [b[0] for b in PB.display_bars("2330", df, ASOF)["bars"]]
    assert "2026-07-10" not in dates and {"2026-07-09", "2026-07-13"} <= set(dates)
    assert set(dates) <= set(str(d.date()) for d in _official("2330").index)


def test_display_falls_back_to_adjusted_without_official(real_store, monkeypatch, tmp_path):
    """Given 一檔沒有證交所官方資料的股票 / When 產生 K 線 / Then 用還原價並標 price = adj(畫面會標「還原價」)"""
    monkeypatch.setattr(C, "OFFICIAL", str(tmp_path))
    df = real_store.load("2330.TW")
    d = PB.display_bars("2330", df, ASOF)
    assert d["price"] == "adj" and d["bars"][0][0] == "2026-01-02" and d["bars"][-1][4] == round(df.loc[ASOF, "close"], 2)


def test_chart_is_whole_year_with_minimum_bars():
    """Given 交易日曆 / When 決定 K 線起點 / Then 6 月看的是 1 月第一個交易日起整年;1 月初今年還不到 60 根,往前補到 60 根"""
    idx = pd.bdate_range("2025-06-02", "2026-09-10")
    assert PB.chart_start(idx, pd.Timestamp("2026-06-15")) == pd.Timestamp("2026-01-01")
    start = PB.chart_start(idx, pd.Timestamp("2026-01-09"))
    assert len(idx[(idx >= start) & (idx <= pd.Timestamp("2026-01-09"))]) == C.CHART_BARS


def test_year_stats_counts_days_hits_and_pending():
    """Given 一檔今年判低點 4 天(3 天已對答案、其中 2 天對、1 天待驗證)、判高點 1 天(錯)、去年判低點 1 天 /
    When 算今年的對答案統計 / Then 判低點 4 天、已對 3 天、對 2 天、命中 66.7%;判高點 1 天、對 0 天;去年的不算"""
    g = pd.DataFrame([("2026-02-02", "low", "low"), ("2026-02-03", "low", "none"), ("2026-03-02", "low", "low"),
                      ("2026-09-10", "low", None), ("2026-04-01", "high", "none"), ("2025-12-30", "low", "low")],
                     columns=["date", "stack_pred", "truth"])
    y = PB.year_stats(g, "2026")
    assert y["low"] == {"n": 4, "graded": 3, "hits": 2, "pct": 66.7}
    assert y["high"] == {"n": 1, "graded": 1, "hits": 0, "pct": 0.0}


def test_model_inputs_stay_adjusted(ran_daily, real_store):
    """Given 每日批次產生的存檔與網頁資料 / When 比對同一天的判斷存檔和個股頁 / Then 判斷存檔(模型用的)收盤是還原價、沒有被改;
    個股頁另外附實際成交價。中華電 2026-06-15(除息前):存檔收盤 = 還原價,個股頁收盤 = 證交所收盤,兩者不同"""
    from system import store as ST
    row = next(r for r in ST.read_day(DATE)["rows"] if r["code"] == "2412")
    with open(os.path.join(C.SITE_DATA, "stocks", "24.json"), encoding="utf-8") as f:
        s = json.load(f)["2412"]
    assert s["price"] == "actual" and s["close"] == _official("2412").loc[DATE, "close"]
    assert row["close"] == pytest.approx(real_store.load("2412.TW").loc[DATE, "close"], abs=0.01)
    assert row["close"] < s["close"]
