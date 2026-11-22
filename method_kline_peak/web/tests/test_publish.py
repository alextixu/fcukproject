"""網頁資料的成績欄位(判斷、規則候選、分數;沒有機率)、研究發現的數字(final 的結果檔)。"""
import json
import os

import numpy as np
import pandas as pd

from system import config as C, publish as PB


def _tab():
    """推薦範圍內 5 個股票日(都已對答案)+ 1 個待驗證 + 1 個池外:
    A 判低點(分數 30)、真的是低點;B 判低點(分數 10)、其實是非極值;C 判低點(分數 20)、真的是低點;
    D 判高點、真的是高點;E 判非極值;F 判低點、還沒有答案;G 池外、判低點、真的是低點。"""
    rows = [("A", "pool", "low", 30.0, "low"), ("B", "pool", "low", 10.0, "none"), ("C", "pool", "low", 20.0, "low"),
            ("D", "pool", "high", 15.0, "high"), ("E", "pool", "none", None, "none"), ("F", "pool", "low", 5.0, None),
            ("G", "out", "low", 40.0, "low")]
    return pd.DataFrame([{"date": "2026-03-02", "source": "replay", "code": c, "status": st, "close": 10.0,
                          "pred": p, "cand": p if p != "none" else None, "score": sc,
                          "truth": t, "ret_pct": 1.0 if t else None} for c, st, p, sc, t in rows])


def test_track_hit_rates():
    """Given 推薦範圍內判低點且已對答案的 A、B、C(A、C 對)/ When 產生成績追蹤 / Then 判低點命中 2 / 3;
    待驗證(F)和池外(G)不算進推薦範圍的命中率,池外另外算 1 / 1;沒有信心等級(回放驗證後拿掉)"""
    tr = PB.track(_tab())
    low = tr["kinds"]["low"]
    assert low["all"] == {"hits": 2, "n": 3, "pct": 66.7}
    assert low["out_pool"] == {"hits": 1, "n": 1, "pct": 100.0}
    assert tr["kinds"]["high"]["all"] == {"hits": 1, "n": 1, "pct": 100.0}
    assert "levels" not in low and not hasattr(C, "SHOW_LEVELS")


def test_top_picks_sorted_by_score():
    """Given 同一天推薦範圍內判低點的 A(30)、B(10)、C(20)、F(5)與池外 G(40)/ When 取前 3 檔 / Then 依分數 A、C、B,池外不算"""
    picks = PB.top_picks(_tab(), "low")
    assert list(picks.code) == ["A", "C", "B"]


def test_track_has_no_returns():
    """Given 存檔的答案裡有 t+1 → t+5 報酬 / When 產生成績追蹤 / Then 輸出裡沒有任何報酬欄位(網頁不放回測與報酬)"""
    text = json.dumps(PB.track(_tab()), ensure_ascii=False, default=str)
    assert "ret" not in text and "win" not in text


def test_public_row_keeps_judgement_candidate_score():
    """Given 存檔的一檔判斷 / When 轉成網頁用的資料 / Then 有判斷、規則候選、分數,沒有三類機率;存檔本身不被改動"""
    r = {"code": "2330", "status": "pool", "judge": {"pred": "low", "cand": "low", "score": 12.3}}
    out = PB._public_row(r)
    assert out["judge"] == {"pred": "low", "cand": "low", "score": 12.3} and out is not r


def test_findings_match_final_results():
    """Given final 的結果檔 / When 產生研究發現頁的資料 / Then 數字和結果檔一致:2024–2026 三年合計找到率 81.9 / 80.1%、
    ±2 天 85.8 / 85.4%、命中率 28.7 / 28.3%、判反 0 次;每年找到率 7–9 成、命中率約三成;判的天數是真高低點的 2.9 / 2.8 倍;
    30 種只做多的進出方式扣成本後全部虧損、都輸給買進持有(只取結論,沒有報酬數字)"""
    F = PB.findings()
    with open(os.path.join(C.RESULTS, "confusion_2024_2026_tw200.json"), encoding="utf-8") as f:
        ref = json.load(f)
    cm = sum(np.array(v["主軸"]["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"]) for v in ref.values())
    assert F["recall"]["low"] == round(cm[0, 0] / cm[0].sum() * 100, 1) == 81.9
    assert F["recall"]["high"] == round(cm[2, 2] / cm[2].sum() * 100, 1) == 80.1
    assert (F["recall"]["low2"], F["recall"]["high2"]) == (85.8, 85.4)
    assert (F["precision"]["low"], F["precision"]["high"]) == (28.7, 28.3)
    assert F["cross"] == 0 and F["years"] == ["2024", "2025", "2026"] and F["n_stocks"] == 168
    for y, v in ref.items():
        x = v["主軸"]
        assert F["by_year"][y]["rec_low"] == round(x["recall"]["低點"] * 100, 1)
        assert 66 <= F["by_year"][y]["rec_high"] <= 90 and 26 <= F["by_year"][y]["prec_low"] <= 32
    assert F["over"] == {"low": 2.9, "high": 2.8}
    assert F["trade"]["n"] == 30 and F["trade"]["all_loss"] and F["trade"]["below_hold"]
    text = json.dumps({k: v for k, v in F.items() if k != "sources"}, ensure_ascii=False)
    assert not [b for b in ("backtest", "扣成本", "total_return", "Stacking", "機率") if b in text]


def test_method_configured():
    """Given 網站設定 / When 讀方法、股票池、推薦範圍 / Then 方法同 final(規則候選 + AE + OC-SVM),沒有其他方法的設定;
    訓練股票池預設 TW200;推薦範圍預設和訓練股票池相同"""
    assert C.METHOD_NAME == "規則候選 + AE + OC-SVM"
    assert not hasattr(C, "METHODS") and not hasattr(C, "DEFAULT_METHOD")
    assert C.POOL == "tw200" and C.RECOMMEND == "pool"
