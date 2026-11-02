"""股票分類:池內 / 池外 / 低波動 / 不支援 / 資料不足。"""
import numpy as np

from kpweb_helpers import make_bars
from system import universe as U

POOL = {"2330.TW"}


def _walk(daily_pct, n=400, seed=0):
    r = np.random.default_rng(seed).choice([-1, 1], n) * daily_pct / 100
    return make_bars(100 * np.cumprod(1 + r), start="2020-01-02")


def test_pool_stock():
    """Given 台積電在股票池裡 / When 分類 / Then 池內"""
    assert U.classify("2330", _walk(2.0), POOL)[0] == U.POOL


def test_out_of_pool_stock():
    """Given 一檔上市普通股不在股票池、每天漲跌約 2% / When 分類 / Then 池外(照算但要警示)"""
    st, move = U.classify("2618", _walk(2.0), POOL)
    assert st == U.OUT and move > 0.725


def test_low_volatility_stock():
    """Given 一檔上市普通股每天漲跌約 0.3%(低於門檻 0.725%) / When 分類 / Then 低波動(判斷不適用)"""
    st, move = U.classify("2412", _walk(0.3), POOL)
    assert st == U.LOWVOL and move < 0.725


def test_threshold_same_as_research():
    """Given 研究的低波動門檻 / When 比對網頁系統的門檻 / Then 相同(0.725%,2020-01 起)"""
    import mainline as ML
    from system import config as C
    assert (C.MIN_MOVE, C.MOVE_FROM) == (ML.MIN_MOVE, ML.MOVE_FROM)


def test_unsupported_etf_otc_esb():
    """Given ETF 0050、上櫃 6488、興櫃股票 / When 分類 / Then 都是不支援,並說明原因"""
    df = _walk(2.0)
    for code in ("0050", "6488"):
        assert U.classify(code, df, POOL)[0] == U.NOSUP
        assert U.unsupported_reason(code)
    esb = next(c for c, v in U.symbols().items() if v["type"] == "ESB")
    assert U.classify(esb, df, POOL)[0] == U.NOSUP


def test_too_little_data():
    """Given 新上市只有 10 天 K 線 / When 分類 / Then 資料不足(要 16 天:10 日均量 + 6 根 K)"""
    assert U.classify("2618", _walk(2.0, n=10), POOL)[0] == U.NODATA


def test_pool_2026_is_research_pool():
    """Given 2026 年的股票池 / When 讀取 / Then 就是研究的 TW100 剔除低波動股 73 檔"""
    p = U.pool_for_year(2026)
    assert len(p) == 73 and "2330.TW" in p and "2412.TW" not in p


def test_universe_all_is_listed_common_stocks():
    """Given 全部支援的股票 / When 列出 / Then 都是 4 位數代號的上市股票,不含 ETF(00 開頭)"""
    u = U.universe("all")
    assert len(u) > 900
    assert all(U.symbols()[U.code_of(t)]["type"] == "TWSE" and not t.startswith("0") for t in u)
