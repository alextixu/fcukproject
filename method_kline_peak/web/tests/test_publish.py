"""網頁資料的成績欄位(只有 Stacking)、研究發現的方向性結論。"""
import json
import os

import pandas as pd

from system import config as C, publish as PB


def _tab():
    """推薦範圍內 5 個股票日(都已對答案)+ 1 個待驗證 + 1 個池外:
    A 判低點(信心中)、真的是低點;B 判低點(信心中)、其實是非極值;C 判低點(信心高)、真的是低點;
    D 判高點、真的是高點;E 判非極值;F 判低點、還沒有答案;G 池外、判低點、真的是低點。"""
    rows = [("A", "pool", "low", "中", "low"), ("B", "pool", "low", "中", "none"), ("C", "pool", "low", "高", "low"),
            ("D", "pool", "high", "高", "high"), ("E", "pool", "none", None, "none"), ("F", "pool", "low", "低", None),
            ("G", "out", "low", "高", "low")]
    return pd.DataFrame([{"date": "2026-03-02", "source": "replay", "code": c, "status": st, "close": 10.0,
                          "stack_pred": p, "stack_score": 0.6 if p != "none" else None, "stack_level": lv,
                          "truth": t, "ret_pct": 1.0 if t else None} for c, st, p, lv, t in rows])


def test_track_hit_rates_and_levels():
    """Given 推薦範圍內判低點且已對答案的 A、B、C(A、C 對)/ When 產生成績追蹤 / Then 判低點命中 2 / 3;信心中 1 / 2、高 1 / 1;
    待驗證(F)和池外(G)不算進推薦範圍的命中率,池外另外算 1 / 1"""
    tr = PB.track(_tab())
    low = tr["kinds"]["low"]
    assert low["all"] == {"hits": 2, "n": 3, "pct": 66.7}
    assert low["levels"] == {"中": {"hits": 1, "n": 2, "pct": 50.0}, "高": {"hits": 1, "n": 1, "pct": 100.0}}
    assert low["out_pool"] == {"hits": 1, "n": 1, "pct": 100.0}
    assert tr["kinds"]["high"]["all"] == {"hits": 1, "n": 1, "pct": 100.0}
    assert "methods" not in tr and "both" not in tr


def test_track_has_no_returns():
    """Given 存檔的答案裡有 t+1 → t+5 報酬 / When 產生成績追蹤 / Then 輸出裡沒有任何報酬欄位(網頁不放回測與報酬)"""
    text = json.dumps(PB.track(_tab()), ensure_ascii=False, default=str)
    assert "ret" not in text and "win" not in text


def test_public_row_has_only_stacking():
    """Given 舊存檔的一檔判斷(同時有主軸與 Stacking)/ When 轉成網頁用的資料 / Then 只留 Stacking,存檔本身不被改動"""
    r = {"code": "2330", "status": "pool", "main": {"pred": "low", "score": 1.0}, "stack": {"pred": "low", "score": 0.6, "level": "中"}}
    out = PB._public_row(r)
    assert "main" not in out and out["stack"]["level"] == "中" and "main" in r


def test_findings_directional_only():
    """Given 研究結果檔 / When 產生研究發現頁的資料 / Then 只有方向性結論(找到率、高低點判反次數、命中率、等確認的命中率),
    數字和結果檔的 Stacking 部分一致:找到率 48.35 / 41.82%、±2 天 56.79 / 51.18%、命中率 27.68 / 26.02%、判反 0 次;
    沒有回測、後處理、機率門檻、主軸"""
    F = PB.findings()
    with open(os.path.join(C.RESULTS, "postproc_signals_tw200.json"), encoding="utf-8") as f:
        a0 = json.load(f)["三年平均"]["Stacking 邏輯迴歸"]["A0 原始"]
    assert F["recall"] == {"low": a0["低點"]["找到率_精確"], "high": a0["高點"]["找到率_精確"],
                           "low2": a0["低點"]["找到率_±2天"], "high2": a0["高點"]["找到率_±2天"]}
    assert (F["recall"]["low"], F["recall"]["high"], F["recall"]["low2"]) == (48.35, 41.82, 56.79)
    assert (F["precision"]["low"], F["precision"]["high"]) == (27.68, 26.02)
    assert F["cross"] == 0 and F["years"] == ["2024", "2025", "2026"]
    assert F["confirm"]["low"] == {"k0": 27.68, "k1": 49.67, "k2": 62.99, "k3": 75.93, "base": 7.24}
    assert set(F) == {"recall", "precision", "cross", "years", "confirm", "sources"}
    text = json.dumps({k: v for k, v in F.items() if k != "sources"}, ensure_ascii=False)
    assert not [b for b in ("backtest", "扣成本", "主軸") if b in text]


def test_only_stacking_configured():
    """Given 網站設定 / When 讀方法、股票池、推薦範圍 / Then 只有 Stacking;訓練股票池預設 TW200;推薦範圍預設台灣 50"""
    assert C.METHODS == ("stack",) and C.DEFAULT_METHOD == "stack"
    assert C.POOL == "tw200" and C.RECOMMEND == "tw50"
