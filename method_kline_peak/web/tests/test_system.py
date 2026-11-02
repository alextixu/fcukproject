"""系統層:正式模型和研究一致、不偷看未來、每日批次與回放結果相同、判斷存檔不重算、網頁資料的規則。"""
import json
import os

import numpy as np
import pandas as pd
import pytest

from system import config as C, model as MD, pipeline as PL, publish as PB, store as ST, universe as U
from system.features import live_frame, KIND2CODE

DATE = pd.Timestamp("2026-06-15")


def test_model_settings_match_research(prod_model):
    """Given 2026 年的正式模型 / When 檢查設定 / Then 股票池 73 檔、訓練 2022–2025(最後 5 個交易日剔除)、種子 42、29 個特徵"""
    m = prod_model
    import mainline as ML
    assert len(m["pool"]) == 73 and m["pool"] == U.pool_for_year(2026)
    assert m["pool"] == list(ML.load_data())                               # 和研究的股票池同一份、同順序
    assert m["train"][0].startswith("2022-01") and m["train"][1] == "2025-12-23"
    assert len(m["fc"]) == 29 and C.SEED == 42


def test_model_reproduces_research_2026(prod_model, real_store):
    """Given 正式模型與研究 walk-forward 的 2026 年模型同設定 / When 對 2026 年 1–9 月的股票池逐日判斷 /
    Then 測試筆數和研究相同(11,826),兩個方法的 macro-F1 與混淆矩陣和研究結果(results/confusion_2024_2026_tw100.json)完全相同"""
    import mainline as ML
    import walkforward as WF
    from confusion import summarize
    from paper_aeocsvm import NAMES
    data = real_store.load_many(prod_model["pool"], end=ML.END)
    panel, _ = ML.build_panel(data, 6, [])
    te = WF.year_split(panel, 2026)["test"]
    pr = MD.predict(prod_model, te)
    with open(os.path.join(C.RESULTS, "confusion_2024_2026_tw100.json"), encoding="utf-8") as f:
        ref = json.load(f)["2026"]
    assert len(te) == 11826
    for col, key in (("main_pred", "① 主軸"), ("stack_pred", "② Stacking 邏輯迴歸")):
        s = summarize(te.y.to_numpy(), pr[col].map(KIND2CODE).to_numpy(), NAMES)
        assert s["macro_f1"] == pytest.approx(ref[key]["macro_f1"], abs=1e-12)
        assert s["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"] == ref[key]["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"]
        cm = np.array(s["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"])
        assert cm[0, 2] == 0 and cm[2, 0] == 0                              # 高低點不會互相判反


@pytest.mark.parametrize("date", ["2026-02-10", "2026-06-15", "2026-09-10"])
def test_no_lookahead(real_store, date):
    """Given 台積電的 K 線 / When 只給到判斷日為止的資料算特徵,和給完整資料算特徵比較 / Then 判斷日那一列完全相同(特徵不偷看未來)"""
    df = real_store.load("2330.TW")
    d = pd.Timestamp(date)
    cut = live_frame("2330.TW", df.loc[:d].tail(PL.TAIL)).set_index("date").loc[d]
    full = live_frame("2330.TW", df).set_index("date").loc[d]
    pd.testing.assert_series_equal(cut, full, check_names=False)


def test_daily_equals_replay(prod_model, real_store):
    """Given 同一天、同一個模型 / When 用每日批次的算法(只有到那天的資料)和回放的算法(整段先算好特徵)各判斷一次 /
    Then 每一檔的分類、判斷、分數完全相同"""
    codes = ["2330", "2379", "8454", "2618", "2412", "2886", "0050"]
    data = real_store.load_many([U.ticker_of(c) for c in codes])
    daily = PL.judge_day(DATE, {tk: df.loc[:DATE] for tk, df in data.items()}, prod_model, codes)
    frames = {tk: live_frame(tk, df).set_index("date", drop=False).rename_axis(None) for tk, df in data.items()}
    moves = PL._moves_by_day(data, codes, [DATE])[DATE]
    replay = PL.judge_day(DATE, data, prod_model, codes, moves=moves, source="replay", frames=frames)
    assert daily["rows"] == replay["rows"]
    st = {r["code"]: r["status"] for r in daily["rows"]}
    assert st["2330"] == U.POOL and st["0050"] == U.NOSUP and st["2412"] == U.LOWVOL and st["2618"] == U.OUT


@pytest.fixture
def ran_daily(tmp_data, prod_model, real_store, monkeypatch):
    """在暫存資料夾跑兩次每日批次(離線、TW200 範圍、2026-06-15)。"""
    monkeypatch.setattr(MD, "load", lambda year: prod_model if year == 2026 else None)
    quiet = lambda *_: None  # noqa: E731
    PL.run_daily(asof=DATE, online=False, kind="tw200", store=real_store, log=quiet)
    first = open(ST.day_path(DATE), encoding="utf-8").read()
    PL.run_daily(asof=DATE, online=False, kind="tw200", store=real_store, log=quiet)
    return first


def test_daily_run_freezes_and_does_not_recompute(ran_daily):
    """Given 每日批次已經存了 2026-06-15 的判斷 / When 同一天再跑一次 / Then 存檔內容一字不差(不重算、不覆蓋)"""
    assert open(ST.day_path(DATE), encoding="utf-8").read() == ran_daily
    assert ST.list_days() == [str(DATE.date())]


def test_today_lists_only_pool_sorted(ran_daily):
    """Given 每日批次產生的今日判斷 / When 檢查推薦清單 / Then 只列池內股票、依分數由高到低、判低點清單裡每檔都是判低點"""
    with open(os.path.join(C.SITE_DATA, "today.json"), encoding="utf-8") as f:
        t = json.load(f)
    day = {r["code"]: r for r in ST.read_day(DATE)["rows"]}
    for method in C.METHODS:
        for kind in ("low", "high"):
            items = t["methods"][method][kind]
            assert all(day[i["code"]]["status"] == U.POOL and day[i["code"]][method]["pred"] == kind for i in items)
            scores = [i["score"] for i in items]
            assert scores == sorted(scores, reverse=True)


def test_stock_files_and_index(ran_daily):
    """Given 每日批次產生的網頁資料 / When 檢查個股檔與自動完成清單 / Then 池內、池外、低波動股都有個股檔並標好分類;
    ETF 0050 沒有個股檔,清單裡標不支援並附原因"""
    out = C.SITE_DATA
    for code, st in (("2330", U.POOL), ("2618", U.OUT), ("2412", U.LOWVOL)):
        with open(os.path.join(out, "stocks", f"{code}.json"), encoding="utf-8") as f:
            s = json.load(f)
        assert s["status"] == st and len(s["bars"]) == C.CHART_BARS and s["bars"][-1][0] == str(DATE.date())
    assert not os.path.exists(os.path.join(out, "stocks", "0050.json"))
    with open(os.path.join(out, "index.json"), encoding="utf-8") as f:
        idx = {r[0]: r for r in json.load(f)}
    assert idx["0050"][2] == U.NOSUP and "ETF" in idx["0050"][4]
    assert idx["2330"][2] == U.POOL


def test_research_numbers_are_read_not_recomputed():
    """Given 研究結果檔 / When 產生方法說明頁的數字 / Then 和結果檔一致(例:TW100 主軸 2025 扣成本 −42.17%、判低點命中 29.0%)"""
    r = PB.research()
    bt = {(b["pool"], b["year"], b["method"]): b["ret_pct"] for b in r["backtest"]}
    assert bt[("TW100 73 檔", "2025", "main")] == -42.17
    cl = {(c["year"], c["method"]): c for c in r["classification"]}
    assert cl[("2025", "main")]["prec_low"] == 29.0 and cl[("2025", "stack")]["macro_f1"] == 49.87


def test_day_file_format(ran_daily):
    """Given 每日批次存的判斷檔 / When 檢查格式 / Then 每檔都有代號與分類;有判斷的股票兩個方法都有 pred(低點 / 高點 / 非極值),
    判非極值時分數與信心是空的、其餘有分數與信心(高 / 中 / 低);Stacking 三類機率加起來是 1;只有池內 / 池外 / 低波動股有判斷"""
    day = ST.read_day(DATE)
    assert day["date"] == str(DATE.date()) and day["source"] == "daily" and day["model"]["year"] == 2026
    statuses = {U.POOL, U.OUT, U.LOWVOL, U.NOSUP, U.NODATA, "halted"}
    n_judged = 0
    for r in day["rows"]:
        assert set(r) >= {"code", "status"} and r["status"] in statuses
        if "main" not in r:
            assert r["status"] in {U.NOSUP, U.NODATA, "halted"}
            continue
        n_judged += 1
        assert r["status"] in {U.POOL, U.OUT, U.LOWVOL} and isinstance(r["close"], float)
        for method in C.METHODS:
            m = r[method]
            assert m["pred"] in {"low", "high", "none"}
            if m["pred"] == "none":
                assert m["score"] is None and m["level"] is None
            else:
                assert isinstance(m["score"], float) and m["level"] in MD.LEVELS
        s = r["stack"]
        assert s["p_low"] + s["p_none"] + s["p_high"] == pytest.approx(1, abs=1e-3)
    assert n_judged > 100
