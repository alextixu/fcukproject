"""系統層:正式模型(規則候選 + AE + OC-SVM,同 final;TW200 訓練)和研究一致、不偷看未來、每日批次與回放結果相同、
判斷存檔不重算、網頁資料的規則(沒有機率、沒有回測)。"""
import json
import os

import numpy as np
import pandas as pd
import pytest

from system import config as C, model as MD, pipeline as PL, publish as PB, store as ST, universe as U
from system.features import live_frame, KIND2CODE

DATE = pd.Timestamp("2026-06-15")


def test_model_settings_match_research(prod_model):
    """Given 2026 年的正式模型 / When 檢查設定 / Then 是研究的 walkforward.MainlineSource(高點、低點各一組 AE + OC-SVM);
    股票池 = 研究的 TW200 剔除低波動股(168 檔、同一份、同順序);訓練 2022–2025(最後 5 個交易日剔除)、種子 42、29 個特徵、標籤門檻 0%"""
    m = prod_model
    import mainline as ML
    import walkforward as WF
    from learn5_trade6 import UP, DOWN
    assert isinstance(m["src"], WF.MainlineSource) and set(m["src"].models) == {UP, DOWN}
    assert not [k for k in m if "stack" in k]
    assert m["pool"] == U.pool_for_year(2026) == list(ML.load_data(pool="tw200")) and len(m["pool"]) == 168
    assert m["train"] == ["2022-01-03", "2025-12-23"]
    assert len(m["fc"]) == 29 and C.SEED == 42 and m["train_min_amp"] == 0


def test_model_reproduces_research_2026(prod_model, real_store):
    """Given 正式模型與 final 的 walk-forward 2026 年模型同設定 / When 對 2026 年 1–9 月的研究股票池 168 檔逐日判斷 /
    Then 測試筆數、macro-F1(54.51%)、混淆矩陣都和 final 的結果檔(results/confusion_2024_2026_tw200.json)完全相同,高低點不判反;
    判高點 / 低點一定是規則候選、分數 > 0"""
    import mainline as ML
    import walkforward as WF
    from confusion import summarize
    from paper_aeocsvm import NAMES
    data = real_store.load_many(prod_model["pool"], end=ML.END)
    panel, _ = ML.build_panel(data, 6, [])
    te = WF.year_split(panel, 2026)["test"]
    pr = MD.predict(prod_model, te)
    with open(os.path.join(C.RESULTS, "confusion_2024_2026_tw200.json"), encoding="utf-8") as f:
        ref = json.load(f)["2026"]["主軸"]
    s = summarize(te.y.to_numpy(), pr["pred"].map(KIND2CODE).to_numpy(), NAMES)
    cm = s["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"]
    assert len(te) == int(np.array(ref["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"]).sum()) == 27208
    assert s["macro_f1"] == pytest.approx(ref["macro_f1"], abs=1e-12) and round(s["macro_f1"] * 100, 2) == 54.51
    assert cm == ref["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"]
    assert cm[0][2] == 0 and cm[2][0] == 0
    hi, lo = pr.pred == "high", pr.pred == "low"
    assert te.cand_hi[hi].all() and te.cand_lo[lo].all() and (pr.score[hi | lo] > 0).all()


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
    Then 每一檔的分類、判斷、分數完全相同;推薦範圍 = 訓練股票池(2330、2454、2618);TW200 剔除的低波動股(2412、2801)與 ETF 0050 不適用"""
    codes = ["2330", "2454", "8454", "2618", "2412", "2801", "0050"]
    data = real_store.load_many([U.ticker_of(c) for c in codes])
    daily = PL.judge_day(DATE, {tk: df.loc[:DATE] for tk, df in data.items()}, prod_model, codes)
    frames = {tk: live_frame(tk, df).set_index("date", drop=False).rename_axis(None) for tk, df in data.items()}
    moves = PL._moves_by_day(data, codes, [DATE])[DATE]
    replay = PL.judge_day(DATE, data, prod_model, codes, moves=moves, source="replay", frames=frames)
    assert daily["rows"] == replay["rows"]
    rows = {r["code"]: r for r in daily["rows"]}
    st = {c: r["status"] for c, r in rows.items()}
    assert st["2330"] == st["2454"] == st["2618"] == U.POOL
    assert st["2412"] == U.LOWVOL and st["2801"] == U.LOWVOL and st["0050"] == U.LOWVOL
    assert "judge" in rows["2412"] and "stack" not in rows["2330"]


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
    """Given 每日批次產生的今日判斷 / When 檢查推薦清單 / Then 只列推薦範圍(訓練股票池 168 檔)的股票、清單裡每檔都是那一類的判斷、
    依「沒破底天數」分組、組內依分數由高到低;168 檔都有判斷;同一檔不會同時出現在判低點和判高點"""
    with open(os.path.join(C.SITE_DATA, "today.json"), encoding="utf-8") as f:
        t = json.load(f)
    day = {r["code"]: r for r in ST.read_day(DATE)["rows"]}
    rec = {U.code_of(tk) for tk in U.recommend_list(2026)}
    assert len(rec) == 168 and t["n_pool"] == 168
    assert not {i["code"] for i in t["lists"]["low"]} & {i["code"] for i in t["lists"]["high"]}
    assert all(day[c]["status"] == U.POOL and "judge" in day[c] for c in rec)
    for kind in ("low", "high"):
        items = t["lists"][kind]
        assert all(i["code"] in rec and day[i["code"]]["judge"]["pred"] == kind for i in items)
        for g in ("new", "d12", "d3"):
            scores = [i["score"] for i in items if i["group"] == g]
            assert scores == sorted(scores, reverse=True)
        assert all(i["days"] == 0 and i["run"] == 1 for i in items)         # 只有一天存檔:都是剛出現、連續第 1 天
    assert "methods" not in t and "both" not in t


def test_stock_files_and_index(ran_daily):
    """Given 每日批次產生的網頁資料 / When 檢查個股檔(依代號前兩碼分檔)與自動完成清單 / Then 台灣 50、池外、低波動股都有資料並標好分類;
    K 線是今年整年(第一個交易日到判斷基準日),附今年的對答案統計;個股資料是判斷、規則候選、分數(沒有機率);TW200 剔除的低波動股標低波動;興櫃標資料不足、存託憑證標不支援並附原因,這次沒算到的 ETF 標資料不足;分檔數量不超過 Artifact 一次發布的上限"""
    out = C.SITE_DATA

    def shard(code):
        with open(os.path.join(out, "stocks", f"{PB.shard_of(code)}.json"), encoding="utf-8") as f:
            return json.load(f)
    for code, st in (("2330", U.POOL), ("2454", U.POOL), ("2412", U.LOWVOL), ("2801", U.LOWVOL)):
        s = shard(code)[code]
        assert s["status"] == st and s["bars"][0][0] == "2026-01-02" and s["bars"][-1][0] == str(DATE.date())   # 今年整年
        assert set(s["year"]) == {"year", "low", "high"} and s["year"]["year"] == "2026"
        assert set(s["today"]["judge"]) == {"pred", "cand", "score"} and all("level" not in x for x in s["signals"])
    assert len(os.listdir(os.path.join(out, "stocks"))) <= 100
    with open(os.path.join(out, "index.json"), encoding="utf-8") as f:
        idx = {r[0]: r for r in json.load(f)}
    esb = next(c for c, v in U.symbols().items() if v["type"] == "ESB")
    assert idx[esb][2] == U.NODATA and "興櫃" in idx[esb][4]
    assert idx["910322"][2] == U.NOSUP and idx["910322"][4]
    assert idx["0050"][2] == U.NODATA and idx["0050"][4]                 # 這次只算 TW200:ETF 沒算到 → 資料不足並說明
    assert idx["2330"][2] == U.POOL


def test_no_backtest_or_return_in_site_data(ran_daily):
    """Given 每日批次產生的網頁資料 / When 檢查所有 JSON / Then 沒有回測、報酬、機率、Stacking 相關的欄位或文字
    (研究發現只引用結果檔的檔名當資料來源)"""
    banned = ("backtest", "ret_pct", "avg_ret", "win_pct", "扣成本", "total_return", "\"stack", "Stacking", "stacking",
              "邏輯迴歸", "機率", "p_low", "p_none", "p_high", "\"level", "信心")
    for name in ("today.json", "track.json", "research.json", "findings.json", "meta.json"):
        obj = json.load(open(os.path.join(C.SITE_DATA, name), encoding="utf-8"))
        obj.pop("sources", None) if isinstance(obj, dict) else None
        text = json.dumps(obj, ensure_ascii=False)
        assert not [b for b in banned if b in text], name
    for f in os.listdir(os.path.join(C.SITE_DATA, "stocks")):
        text = open(os.path.join(C.SITE_DATA, "stocks", f), encoding="utf-8").read()
        assert not [b for b in banned if b in text], f


def test_site_text_has_no_banned_words():
    """Given 前端檔案與網頁系統程式 / When 檢查文字 / Then 畫面沒有「機率」「Stacking」「邏輯迴歸」、沒有信心等級、沒有「台灣 50」
    (ETF 0050 的名稱「元大台灣50」除外);程式與說明也沒有 Stacking"""
    site = "".join(open(os.path.join(C.SITE, f), encoding="utf-8").read() for f in ("app.js", "index.html", "style.css"))
    assert not [b for b in ("機率", "Stacking", "stacking", "邏輯迴歸", "主軸", "回測", "73 檔", "信心", "台灣 50") if b in site]
    import glob
    files = glob.glob(os.path.join(C.WEB, "system", "*.py")) + [os.path.join(C.WEB, f) for f in ("run.py", "build_artifact.py",
                                                                                                   "check_research_match.py", "README.md")]
    for p in files:
        text = open(p, encoding="utf-8").read()
        assert not [b for b in ("Stacking", "stacking", "邏輯迴歸", "StackingSource") if b in text], p


def test_research_numbers_are_read_not_recomputed():
    """Given final 的結果檔 / When 產生方法說明頁的數字 / Then 和 results/confusion_2024_2026_tw200.json 一致,只有分類成績、沒有回測"""
    r = PB.research()
    with open(os.path.join(C.RESULTS, "confusion_2024_2026_tw200.json"), encoding="utf-8") as f:
        ref = json.load(f)
    assert set(r) == {"classification", "sources"} and [c["year"] for c in r["classification"]] == ["2024", "2025", "2026"]
    for c in r["classification"]:
        x = ref[c["year"]]["主軸"]
        assert c["macro_f1"] == round(x["macro_f1"] * 100, 2) and c["prec_low"] == round(x["precision"]["低點"] * 100, 1)
        assert c["rec_high"] == round(x["recall"]["高點"] * 100, 1) and c["cross"] == 0
    assert [c["macro_f1"] for c in r["classification"]] == [54.31, 53.42, 54.51]


def test_day_file_format(ran_daily):
    """Given 每日批次存的判斷檔 / When 檢查格式 / Then 每檔都有代號與分類;有判斷的股票有判斷(低點 / 高點 / 非極值)、
    規則候選、分數(沒有機率、沒有信心等級):判高點 / 低點一定是同類候選且分數 > 0;候選但判非極值的分數 ≤ 0;不是候選的沒有分數"""
    day = ST.read_day(DATE)
    assert day["date"] == str(DATE.date()) and day["source"] == "daily" and day["model"]["year"] == 2026
    statuses = {U.POOL, U.OUT, U.LOWVOL, U.NOSUP, U.NODATA, "halted"}
    n_judged, seen = 0, set()
    for r in day["rows"]:
        assert set(r) >= {"code", "status"} and r["status"] in statuses and "stack" not in r
        if "judge" not in r:
            assert r["status"] in {U.NOSUP, U.NODATA, "halted"}
            continue
        n_judged += 1
        assert r["status"] in {U.POOL, U.OUT, U.LOWVOL} and isinstance(r["close"], float)
        s = r["judge"]
        assert set(s) == {"pred", "cand", "score"} and s["pred"] in {"low", "high", "none"} and s["cand"] in {"low", "high", None}
        if s["pred"] != "none":
            assert s["cand"] == s["pred"] and s["score"] > 0
        elif s["cand"]:
            assert s["score"] <= 0
        else:
            assert s["score"] is None
        seen.add((s["pred"], s["cand"]))
    assert n_judged > 100 and {("none", None), ("low", "low"), ("high", "high")} <= seen
