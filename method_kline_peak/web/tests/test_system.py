"""系統層:正式模型(Stacking、TW200 訓練)和研究一致、不偷看未來、每日批次與回放結果相同、判斷存檔不重算、網頁資料的規則。"""
import json
import os

import numpy as np
import pandas as pd
import pytest

from system import config as C, model as MD, pipeline as PL, publish as PB, store as ST, universe as U
from system.features import live_frame, KIND2CODE

DATE = pd.Timestamp("2026-06-15")


def test_model_settings_match_research(prod_model):
    """Given 2026 年的正式模型 / When 檢查設定 / Then 只有 Stacking;股票池 = 研究的 TW200 剔除低波動股(同一份、同順序);
    訓練 2022–2025(前 3 年給兩組 AE + OC-SVM、最後 1 年給邏輯迴歸)、種子 42、29 個特徵、標籤門檻 0%"""
    m = prod_model
    import mainline as ML
    assert "main" not in m and "stack" in m
    assert m["pool"] == U.pool_for_year(2026) == list(ML.load_data(pool="tw200"))
    assert m["train"][0].startswith("2022-01") and m["train"][1] == "2025-12-23"
    assert m["train_a"][0].startswith("2022-01") and m["train_a"][1].startswith("2024-12") and m["train_b"][0].startswith("2025-01")
    assert len(m["fc"]) == 29 and C.SEED == 42 and m["train_min_amp"] == 0


def test_model_reproduces_research_2026(prod_model, real_store):
    """Given 正式模型與研究 walk-forward 的 TW200 2026 年模型同設定 / When 對 2026 年 1–9 月的研究股票池逐日判斷 /
    Then 測試筆數、macro-F1、混淆矩陣都和研究結果(results/confusion_2024_2026_tw200_amp0.json 的 Stacking)完全相同,高低點不判反"""
    import mainline as ML
    import walkforward as WF
    from confusion import summarize
    from paper_aeocsvm import NAMES
    data = real_store.load_many(prod_model["pool"], end=ML.END)
    panel, _ = ML.build_panel(data, 6, [])
    te = WF.year_split(panel, 2026)["test"]
    pr = MD.predict(prod_model, te)
    with open(os.path.join(C.RESULTS, "confusion_2024_2026_tw200_amp0.json"), encoding="utf-8") as f:
        ref = next(v for k, v in json.load(f)["2026"].items() if "Stacking" in k)
    s = summarize(te.y.to_numpy(), pr["stack_pred"].map(KIND2CODE).to_numpy(), NAMES)
    cm = s["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"]
    assert len(te) == int(np.array(ref["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"]).sum())
    assert s["macro_f1"] == pytest.approx(ref["macro_f1"], abs=1e-12)
    assert cm == ref["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"]
    assert cm[0][2] == 0 and cm[2][0] == 0


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
    Then 每一檔的分類、判斷、機率完全相同;台灣 50 的低波動股(2412 中華電)也算推薦範圍、照樣判斷,範圍以外的低波動股(2801)與 ETF 0050 不適用"""
    codes = ["2330", "2379", "8454", "2618", "2412", "2801", "0050"]
    data = real_store.load_many([U.ticker_of(c) for c in codes])
    daily = PL.judge_day(DATE, {tk: df.loc[:DATE] for tk, df in data.items()}, prod_model, codes)
    frames = {tk: live_frame(tk, df).set_index("date", drop=False).rename_axis(None) for tk, df in data.items()}
    moves = PL._moves_by_day(data, codes, [DATE])[DATE]
    replay = PL.judge_day(DATE, data, prod_model, codes, moves=moves, source="replay", frames=frames)
    assert daily["rows"] == replay["rows"]
    rows = {r["code"]: r for r in daily["rows"]}
    st = {c: r["status"] for c, r in rows.items()}
    assert st["2330"] == U.POOL and st["2412"] == U.POOL and st["0050"] == U.LOWVOL and st["2801"] == U.LOWVOL and st["2618"] == U.OUT
    assert "stack" in rows["2412"] and "main" not in rows["2330"]


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


def test_today_lists_only_recommend_pool_sorted(ran_daily):
    """Given 每日批次產生的今日判斷 / When 檢查推薦清單 / Then 只列台灣 50 的股票、清單裡每檔都是那一類的判斷、
    依「沒破底天數」分組、組內依機率由高到低;台灣 50 的 50 檔都有判斷"""
    with open(os.path.join(C.SITE_DATA, "today.json"), encoding="utf-8") as f:
        t = json.load(f)
    day = {r["code"]: r for r in ST.read_day(DATE)["rows"]}
    rec = {U.code_of(tk) for tk in U.recommend_list()}
    assert len(rec) == 50 and t["n_pool"] == 50
    assert all(day[c]["status"] == U.POOL and "stack" in day[c] for c in rec)
    for kind in ("low", "high"):
        items = t["lists"][kind]
        assert all(i["code"] in rec and day[i["code"]]["stack"]["pred"] == kind for i in items)
        for g in ("new", "d12", "d3"):
            scores = [i["score"] for i in items if i["group"] == g]
            assert scores == sorted(scores, reverse=True)
        assert all(i["days"] == 0 and i["run"] == 1 for i in items)         # 只有一天存檔:都是剛出現、連續第 1 天
    assert "methods" not in t and "both" not in t


def test_stock_files_and_index(ran_daily):
    """Given 每日批次產生的網頁資料 / When 檢查個股檔(依代號前兩碼分檔)與自動完成清單 / Then 台灣 50、池外、低波動股都有資料並標好分類;
    K 線是今年整年(第一個交易日到判斷基準日),附今年的對答案統計;個股資料只有 Stacking(沒有主軸欄位);興櫃標資料不足、存託憑證標不支援並附原因,這次沒算到的 ETF 標資料不足;分檔數量不超過 Artifact 一次發布的上限"""
    out = C.SITE_DATA

    def shard(code):
        with open(os.path.join(out, "stocks", f"{PB.shard_of(code)}.json"), encoding="utf-8") as f:
            return json.load(f)
    for code, st in (("2330", U.POOL), ("2412", U.POOL), ("2618", U.OUT), ("2801", U.LOWVOL)):
        s = shard(code)[code]
        assert s["status"] == st and s["bars"][0][0] == "2026-01-02" and s["bars"][-1][0] == str(DATE.date())   # 今年整年
        assert set(s["year"]) == {"year", "low", "high"} and s["year"]["year"] == "2026"
        assert "main" not in s["today"] and all("main" not in x for x in s["signals"])
    assert len(os.listdir(os.path.join(out, "stocks"))) <= 100
    with open(os.path.join(out, "index.json"), encoding="utf-8") as f:
        idx = {r[0]: r for r in json.load(f)}
    esb = next(c for c, v in U.symbols().items() if v["type"] == "ESB")
    assert idx[esb][2] == U.NODATA and "興櫃" in idx[esb][4]
    assert idx["910322"][2] == U.NOSUP and idx["910322"][4]
    assert idx["0050"][2] == U.NODATA and idx["0050"][4]                 # 這次只算 TW200:ETF 沒算到 → 資料不足並說明
    assert idx["2330"][2] == U.POOL


def test_no_backtest_or_return_in_site_data(ran_daily):
    """Given 每日批次產生的網頁資料 / When 檢查所有 JSON / Then 沒有回測、報酬、主軸相關的欄位(網頁定位為參考方向,不放回測)"""
    banned = ("backtest", "ret_pct", "avg_ret", "win_pct", "扣成本", "\"main\"", "主軸")
    for name in ("today.json", "track.json", "research.json", "findings.json", "meta.json"):
        text = open(os.path.join(C.SITE_DATA, name), encoding="utf-8").read()
        assert not [b for b in banned if b in text], name
    for f in os.listdir(os.path.join(C.SITE_DATA, "stocks")):
        text = open(os.path.join(C.SITE_DATA, "stocks", f), encoding="utf-8").read()
        assert "ret_pct" not in text and "\"main\"" not in text


def test_research_numbers_are_read_not_recomputed():
    """Given 研究結果檔 / When 產生方法說明頁的數字 / Then 和 TW200 Stacking 的結果檔一致,而且只有分類成績、沒有回測"""
    r = PB.research()
    with open(os.path.join(C.RESULTS, "confusion_2024_2026_tw200_amp0.json"), encoding="utf-8") as f:
        ref = json.load(f)
    assert set(r) == {"classification", "sources"}
    for c in r["classification"]:
        x = next(v for k, v in ref[c["year"]].items() if "Stacking" in k)
        assert c["macro_f1"] == round(x["macro_f1"] * 100, 2) and c["prec_low"] == round(x["precision"]["低點"] * 100, 1)
        assert c["cross"] == 0


def test_day_file_format(ran_daily):
    """Given 每日批次存的判斷檔 / When 檢查格式 / Then 每檔都有代號與分類;有判斷的股票只有 Stacking(沒有主軸欄位):
    pred 是低點 / 高點 / 非極值,判非極值時機率與信心是空的、其餘有機率與信心(高 / 中 / 低);三類機率加起來是 1"""
    day = ST.read_day(DATE)
    assert day["date"] == str(DATE.date()) and day["source"] == "daily" and day["model"]["year"] == 2026
    statuses = {U.POOL, U.OUT, U.LOWVOL, U.NOSUP, U.NODATA, "halted"}
    n_judged = 0
    for r in day["rows"]:
        assert set(r) >= {"code", "status"} and r["status"] in statuses and "main" not in r
        if "stack" not in r:
            assert r["status"] in {U.NOSUP, U.NODATA, "halted"}
            continue
        n_judged += 1
        assert r["status"] in {U.POOL, U.OUT, U.LOWVOL} and isinstance(r["close"], float)
        s = r["stack"]
        assert s["pred"] in {"low", "high", "none"}
        if s["pred"] == "none":
            assert s["score"] is None and s["level"] is None
        else:
            assert isinstance(s["score"], float) and s["level"] in MD.LEVELS
        assert s["p_low"] + s["p_none"] + s["p_high"] == pytest.approx(1, abs=1e-3)
    assert n_judged > 100
