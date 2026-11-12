"""畫面用的價格:實際成交價(Yahoo 未還原價)只用來顯示,模型與判斷一律用還原價;個股 K 線是今年整年;今年的對答案統計。"""
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


def test_display_uses_actual_price_not_adjusted():
    """Given 還原價(模型用)和 Yahoo 未還原價(除息前的價格比較高)/ When 產生個股頁的 K 線 / Then K 線與收盤用未還原價;
    漲跌幅用還原價算(和看盤軟體一樣對參考價);日期和還原價相同"""
    from kpweb_helpers import make_bars
    adj = make_bars([95, 96, 97, 100, 99], start="2026-03-02")
    raw = make_bars([100, 101, 102, 100, 99], start="2026-03-02")             # 03-05 除息:之前的未還原價比較高
    d = PB.display_bars("9999", adj, pd.Timestamp("2026-03-06"), raw)
    assert d["price"] == "actual" and [b[4] for b in d["bars"]] == [100, 101, 102, 100, 99]
    assert d["close"] == 99 and d["chg_pct"] == pytest.approx(-1.0, abs=1e-3) and d["close_date"] == "2026-03-06"


def test_display_falls_back_when_raw_is_incomplete():
    """Given 未還原價缺了其中一天(或根本沒有)/ When 產生 K 線 / Then 整段用還原價並標 price = adj(畫面標「還原價」),不混用"""
    from kpweb_helpers import make_bars
    adj = make_bars([95, 96, 97, 100, 99], start="2026-03-02")
    raw = make_bars([100, 101, 102, 100, 99], start="2026-03-02").drop(pd.Timestamp("2026-03-04"))
    for r in (raw, None):
        d = PB.display_bars("9999", adj, pd.Timestamp("2026-03-06"), r)
        assert d["price"] == "adj" and [b[4] for b in d["bars"]] == [95, 96, 97, 100, 99]


RAW = os.path.join(C.DATA, "prices_raw", "2412.TW.parquet")


@pytest.mark.skipif(not os.path.exists(RAW), reason="還沒下載 Yahoo 未還原價")
def test_yahoo_raw_matches_official_close():
    """Given 已下載的 Yahoo 未還原價與 repo 裡的證交所官方日資料 / When 比對中華電 2026 年每天收盤 / Then 全部相同
    (2026-01-02 是 132.00,還原價是 127.08)"""
    raw = pd.read_parquet(RAW)
    off = _official("2412")
    common = raw.index.intersection(off.index)
    common = common[(common >= "2026-01-01") & (common <= "2026-09-10")]
    assert len(common) > 150
    assert (raw.loc[common, "close"].round(2) == off.loc[common, "close"]).all()
    assert raw.loc["2026-01-02", "close"] == 132.0


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
    """Given 每日批次產生的存檔與網頁資料 / When 檢查判斷存檔 / Then 判斷存檔(模型用的)收盤是還原價,顯示用的價格不會寫進存檔;
    個股頁標明價格種類(這個測試沒有下載未還原價 → 標還原價)"""
    from system import store as ST
    row = next(r for r in ST.read_day(DATE)["rows"] if r["code"] == "2412")
    with open(os.path.join(C.SITE_DATA, "stocks", "24.json"), encoding="utf-8") as f:
        s = json.load(f)["2412"]
    assert row["close"] == pytest.approx(real_store.load("2412.TW").loc[DATE, "close"], abs=0.01)
    assert s["price"] == "adj" and s["bars"][-1][4] == pytest.approx(row["close"], abs=0.01)
