"""網頁資料的成績欄位:主軸不分信心等級、Stacking 分;兩方法一致時的命中率。"""
import pandas as pd

from system import config as C, publish as PB


def _tab():
    """池內 6 個股票日(都已對答案)+ 1 個池外:
    A 兩方法都判低點、真的是低點;B 兩方法都判低點、其實是非極值;C 只有主軸判低點、真的是低點;
    D 兩方法都判高點、真的是高點;E 都判非極值;F 兩方法都判低點但還沒有答案;G 池外、兩方法都判低點、真的是低點。"""
    rows = [("A", "pool", "low", "low", "low"), ("B", "pool", "low", "low", "none"), ("C", "pool", "low", "none", "low"),
            ("D", "pool", "high", "high", "high"), ("E", "pool", "none", "none", "none"), ("F", "pool", "low", "low", None),
            ("G", "out", "low", "low", "low")]
    return pd.DataFrame([{"date": "2026-03-02", "source": "replay", "code": c, "status": st, "close": 10.0,
                          "main_pred": m, "main_score": 1.0 if m != "none" else None, "main_level": "高" if m != "none" else None,
                          "stack_pred": s, "stack_score": 0.6 if s != "none" else None, "stack_level": "中" if s != "none" else None,
                          "truth": t, "ret_pct": 1.0 if t else None} for c, st, m, s, t in rows])


def test_both_agree_hit_rate():
    """Given 池內兩方法都判低點且已對答案的有 A、B 兩筆(A 對、B 錯),F 還沒答案、G 是池外 /
    When 算兩方法一致時的命中率 / Then 判低點 1 / 2 = 50%(不含待驗證與池外);判高點 1 / 1 = 100%"""
    tr = PB.track(_tab())
    assert tr["both"]["low"] == {"hits": 1, "n": 2, "pct": 50.0}
    assert tr["both"]["high"] == {"hits": 1, "n": 1, "pct": 100.0}
    assert tr["methods"]["main"]["low"]["both"] == tr["methods"]["stack"]["low"]["both"] == tr["both"]["low"]


def test_main_has_no_levels_stack_does():
    """Given 存檔裡兩個方法都有信心等級欄位 / When 產生成績追蹤資料 / Then 主軸沒有分等級的命中率,Stacking 有;
    主軸仍有整體命中率(池內判低點 A、B、C 三筆對 2 筆)"""
    assert C.LEVEL_METHODS == ("stack",)
    tr = PB.track(_tab())
    assert tr["methods"]["main"]["low"]["levels"] == {}
    assert tr["methods"]["stack"]["low"]["levels"] == {"中": {"hits": 1, "n": 2, "pct": 50.0}}
    assert tr["methods"]["main"]["low"]["all"] == {"hits": 2, "n": 3, "pct": 66.7}


def test_public_row_drops_main_level_only():
    """Given 存檔的一檔判斷(兩個方法都有 level) / When 轉成網頁用的資料 / Then 主軸的 level 拿掉、Stacking 保留,存檔本身不被改動"""
    r = {"code": "2330", "status": "pool", "main": {"pred": "low", "score": 1.0, "level": "高"},
         "stack": {"pred": "low", "score": 0.6, "level": "中"}}
    out = PB._public_row(r)
    assert "level" not in out["main"] and out["stack"]["level"] == "中"
    assert r["main"]["level"] == "高"
