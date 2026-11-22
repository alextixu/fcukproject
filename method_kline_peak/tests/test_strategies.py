"""策略回測引擎(backtest_strategies.run)的行為契約(2026-11-22 新增)。

用合成價格,不需要模型:和既有引擎 backtest_years.simulate 一致、不用到未來資料、成本、滿倉規則、停損。
"""
import numpy as np
import pandas as pd
import pytest

import backtest_years as BY
import backtest_strategies as BS


def make_px(n=40, tickers=("AAA", "BBB", "CCC", "DDD"), seed=1):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2024-01-01", periods=n)
    out = {}
    for tk in tickers:
        c = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
        o = c * np.exp(rng.normal(0, 0.01, n))
        out[tk] = pd.DataFrame({"open": o, "close": c}, index=days)
    return out


def random_orders(px, n=25, seed=2):
    rng = np.random.default_rng(seed)
    days = px["AAA"].index[:-3]
    rows = [(days[rng.integers(len(days))], list(px)[rng.integers(len(px))], float(rng.normal())) for _ in range(n)]
    return pd.DataFrame(rows, columns=["date", "ticker", "score"]).drop_duplicates(["date", "ticker"])


@pytest.mark.parametrize("hold,exit_on_high", [(5, False), (3, False), (20, True)])
def test_component_matches_existing_simulate(hold, exit_on_high):
    """Given 合成價格與隨機訊號(含判高點出場)
    When  用新引擎 run 與既有的 backtest_years.simulate 跑同一組設定(K = 2,沒有停損)
    Then  每日資產與每筆交易完全相同(新引擎沿用同一套慣例)"""
    px = make_px()
    lo = random_orders(px)
    sells = random_orders(px, n=15, seed=3)[["date", "ticker"]] if exit_on_high else None
    start, end = px["AAA"].index[0], px["AAA"].index[-1]
    rule = BY.TradeRule(slots=2, hold=hold, exit_on_high=exit_on_high)
    ref = BY.simulate(px, lo, start, end, rule, sells=sells)
    got = BS.run(BS.Market(px, start, end), lo.assign(hold=hold), 2, BS.COST, sells=sells)
    pd.testing.assert_series_equal(got["equity"], ref["equity"], check_names=False)
    cols = ["ticker", "entry", "exit", "shares", "buy_px", "sell_px", "net_ret"]
    pd.testing.assert_frame_equal(got["trades"][cols].reset_index(drop=True), ref["trades"][cols].reset_index(drop=True))


def test_component_no_future_data():
    """Given 訊號日 t
    When  把 t+1 之後(不含 t+1 開盤)的價格全部改掉
    Then  t+1 開盤買進的價格不變,且 t 以前的資產不受影響;進場日 = t 的下一個交易日"""
    px = make_px()
    days = px["AAA"].index
    t = days[10]
    orders = pd.DataFrame({"date": [t], "ticker": ["BBB"], "score": [1.0], "hold": [5]})
    a = BS.run(BS.Market(px, days[0], days[-1]), orders, 1)
    px2 = {k: v.copy() for k, v in px.items()}
    px2["BBB"].loc[days[12]:, ["open", "close"]] *= 3
    px2["BBB"].loc[days[11], "close"] *= 3
    b = BS.run(BS.Market(px2, days[0], days[-1]), orders, 1)
    assert a["trades"].entry.iloc[0] == days[11] == b["trades"].entry.iloc[0]
    assert a["trades"].buy_px.iloc[0] == px["BBB"]["open"].iloc[11] == b["trades"].buy_px.iloc[0]
    pd.testing.assert_series_equal(a["equity"].loc[:t], b["equity"].loc[:t])


def test_component_cost_round_trip():
    """Given 一筆交易(開盤 100 買、收盤賣)
    When  扣成本 / 沒扣成本
    Then  扣成本報酬 = 賣價 × (1 − 0.1425% − 0.3%) ÷ (買價 × (1 + 0.1425%)) − 1;一趟來回成本 0.585%;沒扣成本 = 賣價 ÷ 買價 − 1"""
    px = make_px()
    days = px["AAA"].index
    orders = pd.DataFrame({"date": [days[5]], "ticker": ["AAA"], "score": [1.0], "hold": [4]})
    net = BS.run(BS.Market(px, days[0], days[-1]), orders, 1, BS.COST)["trades"].iloc[0]
    gross = BS.run(BS.Market(px, days[0], days[-1]), orders, 1, BS.NO_COST)["trades"].iloc[0]
    assert net.exit == days[9] and net.buy_px == px["AAA"]["open"].iloc[6] and net.sell_px == px["AAA"]["close"].iloc[9]
    assert net.net_ret == pytest.approx(net.sell_px * (1 - 0.001425 - 0.003) / (net.buy_px * 1.001425) - 1)
    assert gross.net_ret == pytest.approx(gross.sell_px / gross.buy_px - 1)
    assert round((0.001425 * 2 + 0.003) * 100, 3) == 0.585


def test_component_full_slots_skip():
    """Given K = 1,同一天兩個訊號(分數不同),隔天再一個訊號
    When  回測
    Then  只買分數高的那檔;持有期間的新訊號因滿倉跳過;已持有的同一檔不加碼"""
    px = make_px()
    days = px["AAA"].index
    orders = pd.DataFrame({"date": [days[5], days[5], days[6], days[7]], "ticker": ["AAA", "BBB", "CCC", "BBB"],
                           "score": [0.1, 0.9, 5.0, 1.0], "hold": [5, 5, 5, 5]})
    r = BS.run(BS.Market(px, days[0], days[-1]), orders, 1)
    assert list(r["trades"].ticker) == ["BBB"]
    assert r["skipped"]["沒有空位"] == 2 and r["skipped"]["已持有"] == 1


def test_component_stop_loss():
    """Given 進場後某天收盤比進場價低超過 8%
    When  開啟停損(8%)
    Then  隔天開盤賣出(標記停損);只跌 7.9% 不觸發;不開停損時照原本持有到期"""
    days = pd.bdate_range("2024-01-01", periods=15)
    c = np.full(15, 100.0)
    px = {"AAA": pd.DataFrame({"open": c.copy(), "close": c.copy()}, index=days)}
    px["AAA"].loc[days[4], "close"] = 100 * 0.921            # 跌 7.9%:不觸發
    px["AAA"].loc[days[6], "close"] = 100 * 0.91             # 跌 9%:觸發
    orders = pd.DataFrame({"date": [days[2]], "ticker": ["AAA"], "score": [1.0], "hold": [10]})
    mk = BS.Market(px, days[0], days[-1])
    t = BS.run(mk, orders, 1, stop=0.08)["trades"].iloc[0]
    assert t.how == "停損" and t.exit == days[7] and t.sell_px == px["AAA"]["open"].iloc[7]
    t2 = BS.run(mk, orders, 1)["trades"].iloc[0]
    assert t2.how == "到期" and t2.exit == days[12]
