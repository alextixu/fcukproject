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


def test_otc_and_etf_are_computed(tmp_data):
    """Given 上櫃的精材(3374)、上櫃 6488、ETF 0050 / When 分類 / Then 都會計算(Yahoo 代號:上櫃 .TWO、ETF 還沒查過先當 .TW);
    不在台灣 50 → 池外(照算、標推薦範圍外);ETF 每天漲跌小 → 低波動(不適用)"""
    U.ticker_map.cache_clear()
    assert U.supported("3374") and U.ticker_of("3374") == "3374.TWO" and U.ticker_of("6488") == "6488.TWO"
    assert U.supported("0050") and U.ticker_of("0050") == "0050.TW"
    assert U.classify("3374", _walk(2.0), POOL)[0] == U.OUT
    assert U.classify("0050", _walk(0.3), POOL)[0] == U.LOWVOL


def test_esb_is_nodata_and_special_shares_unsupported(tmp_data):
    """Given 興櫃股票、存託憑證(910322)/ When 分類 / Then 興櫃顯示「資料不足」並說明不在計算範圍(不計算);存託憑證不支援"""
    U.ticker_map.cache_clear()
    df = _walk(2.0)
    esb = next(c for c, v in U.symbols().items() if v["type"] == "ESB")
    assert not U.supported(esb) and U.classify(esb, df, POOL)[0] == U.NODATA and "興櫃" in U.nodata_reason(esb)
    assert U.classify("910322", df, POOL)[0] == U.NOSUP and U.unsupported_reason("910322")


def test_etf_ticker_resolution(tmp_data):
    """Given(假的下載)0050 在 Yahoo 是 .TW、0051 只有 .TWO、0052 兩種都沒有 / When 查 ETF 代號 / Then 記下 .TW、.TWO、None;
    沒有資料的 ETF 不計算、顯示「資料不足」;查過的不再查"""
    from system import datasource as DS
    have = {"0050.TW", "0051.TWO"}
    calls = []

    def fake(tks, start, end):
        calls.append(list(tks))
        return {t: make_bars([10, 11, 12]) for t in tks if t in have}
    assert DS.resolve_etf_tickers(["0050", "0051", "0052"], "2026-11-12", fake) == 3
    assert U.ticker_of("0050") == "0050.TW" and U.ticker_of("0051") == "0051.TWO"
    assert not U.supported("0052") and U.classify("0052", _walk(2.0), POOL)[0] == U.NODATA and U.nodata_reason("0052")
    n = len(calls)
    assert DS.resolve_etf_tickers(["0050", "0051", "0052"], "2026-11-12", fake) == 0 and len(calls) == n


def test_too_little_data():
    """Given 新上市只有 10 天 K 線 / When 分類 / Then 資料不足(要 16 天:10 日均量 + 6 根 K)"""
    assert U.classify("2618", _walk(2.0, n=10), POOL)[0] == U.NODATA


def test_pool_2026_is_research_pool():
    """Given 2026 年的訓練股票池(預設 TW200)/ When 讀取 / Then 就是研究的 TW200 剔除低波動股 168 檔;2024、2025 也用同一份(同研究)"""
    p = U.pool_for_year(2026)
    assert len(p) == 168 and "2330.TW" in p and "2412.TW" not in p
    assert U.pool_for_year(2024) == U.pool_for_year(2025) == p


def test_recommend_pool_is_tw50_with_low_vol():
    """Given 推薦範圍台灣 50 / When 列出並分類 / Then 50 檔都是上市普通股;低波動的中華電(2412)在推薦範圍內仍算 pool(照樣給判斷)"""
    rec = U.recommend_list()
    assert len(rec) == 50 and "2412.TW" in rec and "8046.TW" in rec
    assert U.classify("2412", _walk(0.3), set(rec))[0] == U.POOL


def test_universe_all_is_listed_otc_and_etf(tmp_data):
    """Given 全部要計算的股票 / When 列出 / Then 包含上市、上櫃普通股與 ETF(約 2,200 檔),不含興櫃與存託憑證"""
    U.ticker_map.cache_clear()
    u = U.universe("all")
    kinds = {U.symbols()[U.code_of(t)]["type"] for t in u}
    assert kinds == {"TWSE", "OTC", "ETF"} and len(u) > 2000
    assert "3374.TWO" in u and "0050.TW" in u and "910322.TW" not in u
