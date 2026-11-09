"""判斷存檔(寫過不覆蓋)與對答案(t+5 才有答案)。"""
import json

import pandas as pd
import pytest

from kpweb_helpers import make_bars
from system import config as C, store as ST
from system.features import grade, labels
from system.pipeline import grade_pending

V = [10, 9, 8, 7, 6, 5, 6, 7, 8, 9, 10, 11]           # 第 6 天(索引 5)收盤 5 是前後 11 天最低


def _day(date, rows, source="daily"):
    return {"date": str(pd.Timestamp(date).date()), "created": "x", "source": source, "model": {}, "rows": rows}


def test_day_file_written_once(tmp_data):
    """Given 某天的判斷已經存檔 / When 同一天再存一次(例如批次重跑、資料事後修正) / Then 拒絕寫入,檔案內容維持第一次的判斷"""
    ST.write_day(_day("2026-03-02", [{"code": "2330", "status": "pool", "stack": {"pred": "low"}}]))
    with pytest.raises(ST.AlreadyFrozen):
        ST.write_day(_day("2026-03-02", [{"code": "2330", "status": "pool", "stack": {"pred": "high"}}]))
    assert ST.read_day("2026-03-02")["rows"][0]["stack"]["pred"] == "low"


def test_grade_file_written_once(tmp_data):
    """Given 某天已經對過答案 / When 再寫一次答案 / Then 拒絕寫入,答案不會被改"""
    ST.write_grade("2026-03-02", {"2330": {"truth": "low"}})
    with pytest.raises(ST.AlreadyFrozen):
        ST.write_grade("2026-03-02", {"2330": {"truth": "high"}})
    assert ST.read_grade("2026-03-02")["2330"]["truth"] == "low"


def test_grade_true_low_and_return():
    """Given 收盤 10,9,8,7,6,5,6,7,8,9,10,11(第 6 天最低) / When 對第 6 天的答案 / Then 真實類別是低點;
    報酬 = 第 11 天收盤 10 ÷ 第 7 天開盤 5 − 1 − 成本 0.585% = 99.415%;對答案日是第 11 天"""
    df = make_bars(V)
    g = grade(df, df.index[5])
    assert g["truth"] == "low"
    assert g["ret_pct"] == pytest.approx(100 - C.COST_PCT, abs=1e-3)
    assert g["graded_on"] == str(df.index[10].date())


def test_grade_waits_five_days():
    """Given 判斷日之後只有 4 個交易日 / When 對答案 / Then 還沒有答案(待驗證);第 5 天收盤後才有"""
    df = make_bars(V)
    assert grade(df.iloc[:10], df.index[5]) == {"truth": None, "ret_pct": None}
    assert grade(df.iloc[:11], df.index[5])["truth"] == "low"


def test_grade_ordinary_day_is_none_class():
    """Given 一路上漲的股票 / When 對中間一天的答案 / Then 真實類別是非極值(不是最高也不是最低)"""
    df = make_bars(range(100, 130))
    assert grade(df, df.index[12])["truth"] == "none"


def test_grade_pending_only_after_five_days(tmp_data):
    """Given 兩天的存檔:一天之後已有 5 個交易日、一天只有 2 個 / When 對答案 / Then 只對前一天,後一天仍是待驗證;
    再跑一次不會重對(答案檔不變)"""
    df = make_bars(V)
    cal = df.index
    rows = [{"code": "1111", "status": "pool", "stack": {"pred": "low"}}]
    ST.write_day(_day(cal[5], rows))
    ST.write_day(_day(cal[9], rows))
    data = {"1111.TW": df}
    assert grade_pending(data, cal, log=lambda *_: None) == 1
    assert ST.has_grade(cal[5]) and not ST.has_grade(cal[9])
    assert ST.read_grade(cal[5])["1111"]["truth"] == "low"
    before = open(ST.grade_path(cal[5])).read()
    assert grade_pending(data, cal, log=lambda *_: None) == 0
    assert open(ST.grade_path(cal[5])).read() == before


def test_labels_match_research_label():
    """Given 一檔真實股票 / When 用網頁系統的答案表 / Then 標籤和研究的 build_panel 完全相同(對答案的規則和研究一致)"""
    import mainline as ML
    from system.datasource import PriceStore
    st = PriceStore(root=str(tmp_path_factory_dir()), downloader=None)
    df = st.load("2330.TW").loc[:"2025-12-31"]
    panel, _ = ML.build_panel({"2330.TW": df}, 6, [])
    lab = labels(df)
    y = lab.loc[panel["date"], "y"].to_numpy()
    assert (y == panel["y"].to_numpy()).all()


def tmp_path_factory_dir():
    import tempfile
    return tempfile.mkdtemp()


def test_table_joins_days_and_grades(tmp_data):
    """Given 一天的判斷與答案 / When 攤平成表 / Then 每檔一列,判斷和答案對在一起;沒答案的天數答案是空的"""
    ST.write_day(_day("2026-03-02", [{"code": "2330", "status": "pool", "stack": {"pred": "low", "score": 0.7, "level": "高"}}]))
    ST.write_day(_day("2026-03-03", [{"code": "2330", "status": "pool", "stack": {"pred": "none"}}]))
    ST.write_grade("2026-03-02", {"2330": {"truth": "low", "ret_pct": 1.2}})
    t = ST.table()
    assert len(t) == 2
    assert t.loc[t.date == "2026-03-02", "truth"].item() == "low"
    assert pd.isna(t.loc[t.date == "2026-03-03", "truth"].item())
    json.dumps(t.to_dict("records"), default=str)
