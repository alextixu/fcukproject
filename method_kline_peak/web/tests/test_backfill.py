"""計算範圍後來加了股票(上櫃、ETF):已經寫好的存檔不動,只把新加的股票補算到 days_extra;Yahoo 限流不當成沒資料。"""
import pandas as pd
import pytest

from kpweb_helpers import make_bars
from system import store as ST


def _day(date, rows, source="replay"):
    return {"date": date, "created": "x", "source": source, "model": {}, "rows": rows}


def test_extra_rows_are_frozen_and_merged(tmp_data):
    """Given 某天的存檔只有 2330,之後補算了 3374 / When 攤平成表 / Then 兩檔都在、答案也合併;
    補算檔一樣寫過就不再改,原本的存檔內容不變"""
    ST.write_day(_day("2026-03-02", [{"code": "2330", "status": "pool", "stack": {"pred": "low"}}]))
    before = open(ST.day_path("2026-03-02"), encoding="utf-8").read()
    ST.write_extra(_day("2026-03-02", [{"code": "3374", "status": "out", "stack": {"pred": "high", "score": 0.6}}], "backfill"))
    ST.write_extra_grade("2026-03-02", {"3374": {"truth": "high"}})
    with pytest.raises(ST.AlreadyFrozen):
        ST.write_extra(_day("2026-03-02", [{"code": "3374", "status": "out", "stack": {"pred": "low"}}], "backfill"))
    t = ST.table()
    assert set(t.code) == {"2330", "3374"}
    assert t.loc[t.code == "3374", "truth"].item() == "high" and t.loc[t.code == "3374", "stack_pred"].item() == "high"
    assert open(ST.day_path("2026-03-02"), encoding="utf-8").read() == before
    assert [r["code"] for r in ST.all_rows("2026-03-02")] == ["2330", "3374"]


def test_rate_limited_ticker_is_retried(monkeypatch):
    """Given Yahoo 第一次對 3374.TWO 回「Too Many Requests」/ When 下載 / Then 等一下重抓、拿到資料,不會被當成沒資料;
    Yahoo 明確說沒資料的代號(0080.TW)不重抓"""
    import yfinance
    import yfinance.shared as yfs
    from system import datasource as DS
    monkeypatch.setattr(DS.time, "sleep", lambda *_: None)
    calls = []

    def fake_download(tks, **kw):
        calls.append(list(tks))
        frames = {}
        for t in tks:
            if t == "3374.TWO" and len(calls) == 1:
                yfs._ERRORS[t] = "YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')"
                frames[t] = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"], dtype=float)
            elif t == "0080.TW":
                yfs._ERRORS[t] = "possibly delisted; no price data found"
                frames[t] = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"], dtype=float)
            else:
                frames[t] = make_bars([10, 11, 12]).rename(columns=str.capitalize)
        return pd.concat(frames, axis=1)
    monkeypatch.setattr(yfinance, "download", fake_download)
    got = DS.yf_download(["3374.TWO", "0080.TW", "2330.TW"], "2026-11-01", "2026-11-13")
    assert set(got) == {"3374.TWO", "2330.TW"}
    assert calls == [["3374.TWO", "0080.TW", "2330.TW"], ["3374.TWO"]]


def test_replay_backfills_new_codes_without_touching_frozen_day(tmp_data, prod_model, real_store, monkeypatch):
    """Given 2026-06-15 已經用 TW200 範圍存檔 / When 計算範圍改成全部(上市、上櫃、ETF)再回放 / Then 原本的存檔一個字都沒變;
    新加的股票補算到 days_extra(有 K 線的照樣判斷,沒有 K 線的上櫃股是資料不足);再跑一次不會重算"""
    from system import model as MD, pipeline as PL, universe as U
    monkeypatch.setattr(MD, "load", lambda year: prod_model if year == 2026 else None)
    quiet = lambda *_: None  # noqa: E731
    d = pd.Timestamp("2026-06-15")
    PL.run_daily(asof=d, online=False, kind="tw200", store=real_store, log=quiet, publish=False)
    before = open(ST.day_path(d), encoding="utf-8").read()
    have = {r["code"] for r in ST.read_day(d)["rows"]}
    PL.run_replay(d, d, kind="all", store=real_store, log=quiet, publish=False)
    assert open(ST.day_path(d), encoding="utf-8").read() == before
    ex = {r["code"]: r for r in ST.read_extra(d)["rows"]}
    assert set(ex) == {U.code_of(t) for t in U.universe("all")} - have
    assert ex["3374"]["status"] == U.NODATA
    judged = [r for r in ex.values() if r.get("stack")]
    assert len(judged) > 300 and all(r["status"] in (U.OUT, U.LOWVOL) for r in judged)
    extra_before = open(ST.extra_path(d), encoding="utf-8").read()
    PL.run_replay(d, d, kind="all", store=real_store, log=quiet, publish=False)
    assert open(ST.extra_path(d), encoding="utf-8").read() == extra_before
