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


def test_findings_read_from_result_files():
    """Given 研究結果檔 / When 產生研究發現頁的資料 / Then 兩個方法的數字都和結果檔一致(主軸原始判低點命中率 29.24%、等 3 天確認 81.01%;
    Stacking 機率 ≥ 0.8 命中率 32.81%;34 檔 2025 等權買進持有 +19.16%);用到未來資訊的列(真實標籤、事後最高分)都標成實際用不了"""
    F = PB.findings()
    assert F["cards"]["main"]["precision"]["low"] == 29.24 and F["cards"]["main"]["confirm"]["k3_hit"] == 81.01
    assert F["cards"]["stack"]["filters"]["p8_hit"] == 32.81 and F["cards"]["cross"] == 0
    assert F["cards"]["main"]["filters"]["p8_hit"] is None                      # 主軸沒有機率
    assert F["lohi_base"]["buy_hold"] == 19.16
    for m in ("main", "stack"):
        fut = {r["name"] for r in F["post"][m] if r["future"]}
        assert fut == {"合併連續・事後最高分"}
        names = {r["name"]: r["future"] for r in F["lohi"][m]}
        assert names["真實標籤"] and names["1a 合併連續・事後最高分"] and not names["A0 原始"]
    assert [r["key"] for r in F["post"]["main"]] == ["A0 原始", "1a", "1b", "top50", "k1", "k2", "k3"]
    assert F["confirm"]["main"]["low"] == {"k0": 29.24, "k1": 53.19, "k2": 67.74, "k3": 81.01, "base": 7.24}


def test_findings_stacking_numbers_match_json():
    """Given 研究結果檔的 Stacking 部分 / When 產生研究發現頁(網頁預設顯示 Stacking)/ Then 結論卡片、南電圖、分組命中率都用 Stacking 的數字:
    找到率 低 48.35% / 高 41.82%、命中率 27.68% / 26.02%、只做多前 3 檔回測 TW200 三年平均 −21.69%;等確認 k = 1–3 命中 49.67 / 63.0 / 75.93%;
    南電圖用 Stacking 版(compare_…_stack、prob_cut_…_stack、lohi_compare_…_stack)"""
    import json
    import os
    F = PB.findings()
    st = F["cards"]["stack"]
    with open(os.path.join(C.RESULTS, "confirm_signals_tw200.json"), encoding="utf-8") as f:
        cf = json.load(f)["classification_三年平均"]["Stacking 邏輯迴歸"]
    assert st["recall"]["low"] == cf["A0 原始"]["低點"]["找到率_精確"] == 48.35
    assert st["recall"]["high"] == cf["A0 原始"]["高點"]["找到率_精確"] == 41.82
    assert (st["precision"]["low"], st["precision"]["high"]) == (27.68, 26.02)
    assert st["confirm"]["bt0"] == -21.69
    assert st["confirm"]["k1_hit"] == cf["k=1"]["低點"]["命中率"] and st["confirm"]["k3_hit"] == cf["k=3"]["低點"]["命中率"]
    assert F["confirm"]["stack"]["low"]["k2"] == cf["k=2"]["低點"]["命中率"]
    files = [im["file"] for im in F["images"]["stack"]]
    assert files == ["img/compare_8046_2024_tw200_stack.png", "img/prob_cut_8046_2024_tw200_stack.png",
                     "img/lohi_compare_8046_2024_tw200_stack.png"]
    assert all("Stacking" in im["title"] for im in F["images"]["stack"])


def test_default_method_is_stacking():
    """Given 網站設定 / When 讀預設方法 / Then 是 Stacking(打開網站預設顯示 Stacking,主軸放第二個、可以切換);
    研究發現資料也帶著同一個預設"""
    assert C.DEFAULT_METHOD == "stack" and C.METHOD_ORDER == ("stack", "main")
    assert PB.findings()["default_method"] == "stack"
