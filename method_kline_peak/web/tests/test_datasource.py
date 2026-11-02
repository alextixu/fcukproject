"""資料更新:增量下載、還原價變動重抓、網路失敗、休市。下載函式用假的,不連網。"""
import pandas as pd

from kpweb_helpers import make_bars
from system.datasource import PriceStore


class FakeDL:
    def __init__(self, frames=None, fail=False):
        self.frames, self.fail, self.calls = frames or {}, fail, []

    def __call__(self, tickers, start, end):
        self.calls.append((tuple(tickers), start, end))
        if self.fail:
            raise ConnectionError("network down")
        out = {}
        for tk in tickers:
            df = self.frames.get(tk)
            if df is not None:
                out[tk] = df.loc[start:pd.Timestamp(end) - pd.Timedelta(days=1)]
        return out


def _store(tmp_path, dl):
    return PriceStore(root=str(tmp_path / "prices"), seed_dir="", downloader=dl)


def test_update_appends_new_days(tmp_path):
    """Given 快取有前 30 天、來源有 35 天 / When 更新到第 35 天 / Then 快取變成 35 天,舊資料不變,只下載最後一天之前約 20 天起的區間"""
    full = make_bars(range(100, 135))
    dl = FakeDL({"1111.TW": full})
    st = _store(tmp_path, dl)
    st.save("1111.TW", full.iloc[:30])
    rep = st.update(["1111.TW"], full.index[-1])
    got = st.load("1111.TW")
    assert rep.updated == ["1111.TW"] and len(got) == 35
    pd.testing.assert_frame_equal(got.iloc[:30], full.iloc[:30], check_names=False, check_freq=False)
    assert pd.Timestamp(dl.calls[0][1]) > full.index[0]


def test_update_refetches_when_adjusted_prices_change(tmp_path):
    """Given 快取的舊收盤和來源在重疊區間差 5%(除權息後還原價整段重算) / When 更新 / Then 重抓這檔的完整歷史,用新的還原價"""
    full = make_bars(range(100, 135))
    adj = full.copy()
    adj[["open", "high", "low", "close"]] *= 0.95
    dl = FakeDL({"1111.TW": adj})
    st = _store(tmp_path, dl)
    st.save("1111.TW", full.iloc[:30])
    rep = st.update(["1111.TW"], full.index[-1])
    assert rep.refreshed == ["1111.TW"]
    assert st.load("1111.TW")["close"].iloc[0] == adj["close"].iloc[0]


def test_update_network_failure_keeps_cache(tmp_path):
    """Given 下載時網路錯誤 / When 更新 / Then 不丟例外,報告記下失敗與錯誤訊息,快取維持原樣"""
    full = make_bars(range(100, 135))
    st = _store(tmp_path, FakeDL(fail=True))
    st.save("1111.TW", full.iloc[:30])
    rep = st.update(["1111.TW"], full.index[-1])
    assert rep.failed == ["1111.TW"] and "network down" in rep.error
    assert len(st.load("1111.TW")) == 30


def test_update_no_new_data_on_holiday(tmp_path):
    """Given 快取已經到最新交易日 / When 在休市日(週六)更新 / Then 來源沒有新資料,這檔記為沒變,快取不變"""
    full = make_bars(range(100, 135))
    st = _store(tmp_path, FakeDL({"1111.TW": full}))
    st.save("1111.TW", full)
    sat = full.index[-1] + pd.Timedelta(days=1)
    rep = st.update(["1111.TW"], sat)
    assert rep.unchanged == ["1111.TW"] and not rep.updated
    assert len(st.load("1111.TW")) == 35


def test_seed_from_research_cache_is_read_only(tmp_path):
    """Given 研究快取裡有一檔 / When 網頁系統第一次讀它 / Then 複製一份到網頁系統的快取,研究快取的檔案不被修改"""
    seed = tmp_path / "seed"
    seed.mkdir()
    full = make_bars(range(100, 135))
    full.to_parquet(seed / "1111.TW.parquet")
    before = (seed / "1111.TW.parquet").stat().st_mtime_ns
    st = PriceStore(root=str(tmp_path / "prices"), seed_dir=str(seed), downloader=FakeDL())
    assert len(st.load("1111.TW")) == 35
    assert (tmp_path / "prices" / "1111.TW.parquet").exists()
    assert (seed / "1111.TW.parquet").stat().st_mtime_ns == before
