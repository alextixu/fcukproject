"""反手交易(判高點做多、判低點做空)的引擎行為(合成價格,數字可手算)。"""
import pandas as pd
import pytest

from backtest_years import TradeRule, NO_COST
from learn5_trade6 import UP, DOWN
from reversal import simulate_reversal

DAYS = pd.bdate_range("2025-01-02", periods=12)
RULE = TradeRule()
NET = (1 - RULE.sell_fee - RULE.tax) / (1 + RULE.buy_fee)


def px():
    """開盤 100、101、…,收盤 = 開盤 + 0.5。"""
    return pd.DataFrame({"open": [100.0 + k for k in range(12)], "close": [100.5 + k for k in range(12)]}, index=DAYS)


def pred(**days):
    return pd.Series({DAYS[int(k[1:])]: v for k, v in days.items()})


def test_module_reversal_long_short_long():
    """Given 第 0 天判高點、第 3 天判低點、第 6 天判高點 / When 反手交易 /
    Then 第 1 天開盤(101)做多 → 第 4 天開盤(104)賣出並反手放空 → 第 7 天開盤(107)回補並反手做多 → 最後一天收盤(111.5)平倉;
    每筆報酬照成本手算,期末資產 = 100 萬 + 損益加總"""
    out = simulate_reversal(px(), pred(d0=DOWN, d3=UP, d6=DOWN), DAYS[0], DAYS[11], RULE)
    tr, eq = out["trades"], out["equity"]
    assert list(tr.side) == ["做多", "做空", "做多"] and list(tr.how) == ["反手", "反手", "期末"]
    assert list(tr.entry) == [DAYS[1], DAYS[4], DAYS[7]] and list(tr.exit) == [DAYS[4], DAYS[7], DAYS[11]]
    assert tr.net_ret[0] == pytest.approx(104 / 101 * NET - 1)
    assert tr.net_ret[1] == pytest.approx((104 * (1 - RULE.sell_fee - RULE.tax) - 107 * (1 + RULE.buy_fee)) / 104)
    assert tr.net_ret[2] == pytest.approx(111.5 / 107 * NET - 1)
    assert eq.iloc[-1] == pytest.approx(RULE.init_cash + tr.pnl.sum())


def test_module_reversal_waits_for_first_high():
    """Given 第 0 天判低點、第 2 天判高點 / When 反手交易 / Then 第一個高點之前的低點不理會:第 3 天開盤才第一次做多,持有到期末"""
    out = simulate_reversal(px(), pred(d0=UP, d2=DOWN), DAYS[0], DAYS[11], RULE)
    tr = out["trades"]
    assert len(tr) == 1 and tr.side[0] == "做多" and tr.entry[0] == DAYS[3] and tr.how[0] == "期末"


def test_module_reversal_repeated_signals_ignored():
    """Given 第 0、2、4 天都判高點 / When 反手交易 / Then 做多中再判高點不加碼也不重買:只有一筆做多,第 1 天買、期末賣"""
    out = simulate_reversal(px(), pred(d0=DOWN, d2=DOWN, d4=DOWN), DAYS[0], DAYS[11], RULE)
    tr = out["trades"]
    assert len(tr) == 1 and tr.entry[0] == DAYS[1] and tr.exit[0] == DAYS[11]


def test_module_reversal_no_cost_compounds():
    """Given 同第一個情境、成本設 0 / When 反手交易 / Then 期末資產 ≈ 100 萬 × 104/101 × (1 − 3/104) × 111.5/107(只差整數股的零頭)"""
    out = simulate_reversal(px(), pred(d0=DOWN, d3=UP, d6=DOWN), DAYS[0], DAYS[11], TradeRule(**NO_COST))
    want = 1_000_000 * 104 / 101 * (1 - 3 / 104) * 111.5 / 107
    assert out["equity"].iloc[-1] == pytest.approx(want, rel=5e-4)


def test_module_long_only_sell_on_low_then_wait():
    """Given 第 0 天判高點、第 3 天判低點、第 6 天判高點 / When 只做多(不反手) /
    Then 第 1 天開盤(101)買 → 第 4 天開盤(104)賣出後空手 → 第 7 天開盤(107)再買 → 期末平倉;兩筆都是做多,中間沒有空單"""
    out = simulate_reversal(px(), pred(d0=DOWN, d3=UP, d6=DOWN), DAYS[0], DAYS[11], RULE, allow_short=False)
    tr, eq = out["trades"], out["equity"]
    assert list(tr.side) == ["做多", "做多"] and list(tr.how) == ["低點賣出", "期末"]
    assert list(tr.entry) == [DAYS[1], DAYS[7]] and list(tr.exit) == [DAYS[4], DAYS[11]]
    assert tr.net_ret[0] == pytest.approx(104 / 101 * NET - 1)
    assert eq.loc[DAYS[4]:DAYS[6]].nunique() == 1 and eq.iloc[-1] == pytest.approx(RULE.init_cash + tr.pnl.sum())
