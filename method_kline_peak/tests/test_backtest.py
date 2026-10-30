"""逐年回測的契約與邊界行為。

Module :SignalSource 契約(所有訊號來源跑同一組)、逐年切分不洩漏、回測引擎的交易規則(合成價格,數字可手算)
System :介面版主軸 = 原本測過的主軸、2024 全年回測的帳目一致
"""
import math

import numpy as np
import pandas as pd
import pytest

import mainline as ML
import walkforward as WF
from backtest_years import TradeRule, simulate
from feasibility import clean
from learn5_trade6 import FLAT, UP, DOWN

RULE = TradeRule()
NET = (1 - RULE.sell_fee - RULE.tax) / (1 + RULE.buy_fee)       # 買賣一輪扣完成本後的倍數


# ─────────────────────────── Module:SignalSource 契約 ───────────────────────────
@pytest.fixture(scope="module", params=list(WF.SOURCES), ids=list(WF.SOURCES))
def fitted(request, panel):
    df, fc = panel
    d = WF.year_split(df, 2024)
    src = WF.SOURCES[request.param]()
    src.fit(d["train"], fc)
    return src, d["test"]


def test_module_source_contract_schema(fitted):
    """Given 任一訊號來源(主軸 / 規則)用 2020–2023 訓練好 / When 預測 2024 / Then 回傳 date、ticker、pred、score 四欄,
    一列對一個測試股票日、順序和輸入相同,pred 只會是低點 / 非極值 / 高點,score 是有限數字"""
    src, te = fitted
    out = src.predict(te.drop(columns="y"))
    assert list(out.columns) == WF.COLS and len(out) == len(te)
    assert (out.date.to_numpy() == te.date.to_numpy()).all() and (out.ticker.to_numpy() == te.ticker.to_numpy()).all()
    assert set(out.pred.unique()) <= {UP, FLAT, DOWN} and np.isfinite(out.score).all()


def test_module_source_contract_structure(fitted):
    """Given 任一訊號來源 / When 預測 2024 / Then 判低點的一定是低點候選、判高點的一定是高點候選(高低點不會判反)"""
    src, te = fitted
    out = src.predict(te.drop(columns="y"))
    assert te.cand_lo.to_numpy()[out.pred == UP].all() and te.cand_hi.to_numpy()[out.pred == DOWN].all()


def test_module_source_contract_ignores_labels(fitted):
    """Given 任一訊號來源 / When 測試資料的標籤被打亂 / Then 預測完全不變(預測不會偷看答案)"""
    src, te = fitted
    shuffled = te.assign(y=np.random.default_rng(0).permutation(te.y.to_numpy()))
    pd.testing.assert_frame_equal(src.predict(te.drop(columns="y")), src.predict(shuffled))


@pytest.mark.parametrize("year", WF.YEARS)
def test_module_year_split_no_leak(data, panel, year):
    """Given 測試年 Y / When 逐年切分 / Then 訓練只含 Y-4 ~ Y-1,測試只含 Y;
    每個訓練樣本的 t+5(該股自己的交易日)都早於 Y 年第一天"""
    df, _ = panel
    d = WF.year_split(df, year)
    tr, te = d["train"], d["test"]
    assert tr.date.dt.year.between(year - 4, year - 1).all() and (te.date.dt.year == year).all()
    plus5 = pd.concat([pd.DataFrame({"ticker": tk, "date": c.index, "t5": pd.Series(c.index).shift(-5).to_numpy()})
                       for tk, c in ((tk, clean(x)) for tk, x in data.items())])
    m = tr[["ticker", "date"]].merge(plus5, on=["ticker", "date"], how="left")
    assert (m.t5 < pd.Timestamp(f"{year}-01-01")).all()


# ─────────────────────────── Module:回測引擎的交易規則(合成價格) ───────────────────────────
DAYS = pd.bdate_range("2024-01-02", periods=12)


def px(opens, closes=None):
    closes = opens if closes is None else closes
    return pd.DataFrame({"open": opens, "close": closes}, index=DAYS[:len(opens)], dtype=float)


def buys(*rows):
    return pd.DataFrame([(DAYS[i], tk, s) for i, tk, s in rows], columns=["date", "ticker", "score"])


def run(prices, b, end=None):
    return simulate(prices, b, DAYS[0], end or DAYS[len(next(iter(prices.values()))) - 1], RULE)


def test_module_engine_buy_t1_open_sell_t5_close():
    """Given 100 萬、A 股第 0 天收盤出現低點訊號,第 1 天開盤 100、第 5 天收盤 110 / When 回測 /
    Then 第 1 天開盤用總資產 1/10 買進,第 5 天收盤賣出;報酬 = 110 / 100 × 扣成本(0.585%)− 1,現金帳一致"""
    p = {"A": px([100] * 5 + [110] * 7, [100] * 5 + [110] * 7)}
    out = run(p, buys((0, "A", 1.0)))
    tr = out["trades"]
    assert len(tr) == 1 and tr.entry[0] == DAYS[1] and tr.exit[0] == DAYS[5]
    sh = math.floor(100_000 / (100 * (1 + RULE.buy_fee)))
    assert tr.shares[0] == sh and tr.net_ret[0] == pytest.approx(1.1 * NET - 1)
    assert out["equity"].iloc[-1] == pytest.approx(RULE.init_cash + tr.pnl.sum())


def test_module_engine_limit_up_skip():
    """Given 第 0 天收盤 100 出現訊號,第 1 天開盤 110(≥ 漲停 109.5) / When 回測 / Then 買不到,放棄,沒有交易"""
    p = {"A": px([100, 110] + [110] * 10)}
    out = run(p, buys((0, "A", 1.0)))
    assert out["trades"].empty and out["skipped"]["漲停買不到"] == 1


def test_module_engine_no_add_when_held():
    """Given A 股第 0 天與第 1 天都出現訊號 / When 回測 / Then 只買一次(持有中不加碼)"""
    p = {"A": px([100] * 12)}
    out = run(p, buys((0, "A", 1.0), (1, "A", 1.0)))
    assert len(out["trades"]) == 1 and out["skipped"]["已持有"] == 1


def test_module_engine_slots_take_highest_score():
    """Given 只有 2 個空位、同一天 3 檔出現訊號,分數 0.1 / 0.9 / 0.5 / When 回測 / Then 買分數最高的 2 檔(B、C)"""
    p = {tk: px([100] * 12) for tk in "ABC"}
    out = simulate(p, buys((0, "A", 0.1), (0, "B", 0.9), (0, "C", 0.5)), DAYS[0], DAYS[11], TradeRule(slots=2))
    assert sorted(out["trades"].ticker) == ["B", "C"] and out["skipped"]["沒有空位"] == 1


def test_module_engine_year_end_force_close():
    """Given 回測期間只到第 3 天,第 0 天出現訊號 / When 回測 / Then 第 1 天買進,第 3 天(期末)收盤強制結清,期末沒有持股"""
    p = {"A": px([100, 100, 100, 105] + [120] * 8)}
    out = run(p, buys((0, "A", 1.0)), end=DAYS[3])
    tr = out["trades"]
    assert len(tr) == 1 and tr.exit[0] == DAYS[3] and tr.net_ret[0] == pytest.approx(1.05 * NET - 1)
    assert out["equity"].iloc[-1] == pytest.approx(RULE.init_cash + tr.pnl.sum())


def test_module_engine_signal_on_last_day_not_traded():
    """Given 期末最後一天出現訊號(t+1 已在期間之外) / When 回測 / Then 不交易"""
    p = {"A": px([100] * 12)}
    out = run(p, buys((5, "A", 1.0)), end=DAYS[5])
    assert out["trades"].empty and out["skipped"]["跨到下一年"] == 1


def test_module_engine_too_expensive_skip():
    """Given 每格只有 10 萬,股價 20 萬 / When 出現訊號 / Then 錢不夠買一股,放棄"""
    p = {"A": px([200_000] * 12)}
    out = run(p, buys((0, "A", 1.0)))
    assert out["trades"].empty and out["skipped"]["錢不夠一股"] == 1


# ─────────────────────────── System ───────────────────────────
def test_system_interface_reproduces_mainline(panel, run2024):
    """Given 介面版的主軸(MainlineSource,種子 42) / When 用 2020–2023 訓練、預測 2024 / Then 每一天的判斷都和原本測過的主軸相同"""
    df, fc = panel
    sig, n_train = WF.run_year(df, fc, 2024, WF.MainlineSource())
    tr, _, pred, _ = run2024
    assert n_train == len(tr) and np.array_equal(sig.pred.to_numpy(), pred)


def test_system_backtest_2024_bookkeeping(data, panel):
    """Given 2024 主軸的低點訊號與 50 檔價格 / When 跑全年回測 / Then 每筆都是 t+1 開盤買、最多持有到 t+5、
    同時持有不超過 10 檔、年底沒有持股、期末資產 = 100 萬 + 每筆損益加總、資產從不為負"""
    df, fc = panel
    sig, _ = WF.run_year(df, fc, 2024, WF.MainlineSource())
    prices = {tk: clean(x)[["open", "close"]] for tk, x in data.items()}
    out = simulate(prices, sig[sig.pred == UP][["date", "ticker", "score"]], "2024-01-01", "2024-12-31", RULE)
    tr, eq = out["trades"], out["equity"]
    for t in tr.itertuples():
        idx = prices[t.ticker].index
        i = idx.get_loc(t.signal)
        assert idx[i + 1] == t.entry and t.exit <= idx[min(i + 5, len(idx) - 1)]
    held = [((tr.entry <= d) & (tr.exit >= d)).sum() for d in eq.index]
    assert max(held) <= RULE.slots and tr.exit.max() <= eq.index[-1]
    assert eq.iloc[-1] == pytest.approx(RULE.init_cash + tr.pnl.sum()) and (eq > 0).all()
