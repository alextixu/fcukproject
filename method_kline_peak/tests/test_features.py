"""特徵組選項(--features)的行為契約(2026-11-19 新增)。

Component:2day10 / 2day9 的特徵值 = 原系統 method_kline 的 features_2day(轉接,不改公式)
Module   :預設 shape29 不變;三組特徵的樣本列相同;AE 潛在維度依特徵組
System   :feat2day_compare 的 shape29 結果 = 既有 confusion_2024_2026_tw200_amp0.json
"""
import json
import os

import numpy as np
import pandas as pd
import pytest

import mainline as ML
from feasibility import clean
from kline.features import features_2day

F2 = ["upper", "lower", "body", "p_upper", "p_lower", "p_body", "gap", "close_chg", "vol_ratio", "trend"]


@pytest.fixture(scope="module")
def small(data):
    return {tk: data[tk] for tk in list(data)[:3]}


def test_component_2day10_equals_features_2day(small):
    """Given 3 檔 TW50 的還原價
    When  用 --features 2day10 建 panel
    Then  特徵欄 = features_2day 的 10 欄,每個樣本列的值和直接呼叫 features_2day(欄位名 Open/High/Low/Close/Volume)逐欄相同"""
    panel, fc = ML.build_panel(small, 6, [], features="2day10")
    assert fc == F2
    for tk, df in small.items():
        d = clean(df)
        ref = features_2day(d.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}))
        p = panel[panel.ticker == tk].set_index("date")
        pd.testing.assert_frame_equal(p[fc], ref.loc[p.index, F2], check_names=False, check_freq=False)


def test_component_2day9_drops_only_trend(small):
    """Given 同上
    When  用 --features 2day9
    Then  特徵 = 2day10 拿掉 trend,其餘 9 欄的值完全相同"""
    p10, f10 = ML.build_panel(small, 6, [], features="2day10")
    p9, f9 = ML.build_panel(small, 6, [], features="2day9")
    assert f9 == [c for c in f10 if c != "trend"]
    pd.testing.assert_frame_equal(p9[f9], p10[f9])


def test_module_default_is_shape29_and_same_rows(small):
    """Given 同上
    When  不給 features、給 shape29、給 2day10 / 2day9
    Then  預設 = shape29(29 欄、panel 完全相同);三組的樣本列(日期 × 股票)相同,2day 的特徵不含 shape29 的欄"""
    p0, f0 = ML.build_panel(small, 6, [])
    p1, f1 = ML.build_panel(small, 6, [], features="shape29")
    assert len(f0) == 29 and f0 == f1
    pd.testing.assert_frame_equal(p0, p1)
    for f in ("2day10", "2day9"):
        p, fc = ML.build_panel(small, 6, [], features=f)
        assert (p[["date", "ticker"]].to_numpy() == p0[["date", "ticker"]].to_numpy()).all()
        assert not set(fc) & set(f0)


def test_module_latent_by_features():
    """Given 特徵組
    When  ML.setup_ae() 不給 latent
    Then  shape29 用 16(預設不變)、2day10 / 2day9 用 4(原系統 2 日 K 的設定)"""
    old = ML.FEATURES
    try:
        for f, k in (("shape29", 16), ("2day10", 4), ("2day9", 4)):
            ML.FEATURES = f
            ML.setup_ae()
            assert ML.KA.LATENT_DIM == k
    finally:
        ML.FEATURES = old
        ML.setup_ae()


def test_system_shape29_matches_existing_results():
    """Given feat2day_compare 的結果檔
    When  比對 shape29 與既有的 confusion_2024_2026_tw200_amp0.json
    Then  三年 × 兩方法的混淆矩陣與 macro-F1 完全相同(加 --features 選項沒有改變原本的結果)"""
    path = os.path.join(ML.OUT, "feat2day_compare_tw200.json")
    if not os.path.exists(path):
        pytest.skip("尚未執行 feat2day_compare.py")
    res = json.load(open(path, encoding="utf-8"))
    ref = json.load(open(os.path.join(ML.OUT, "confusion_2024_2026_tw200_amp0.json"), encoding="utf-8"))
    key = "confusion_rows_true_cols_pred(漲,不漲不跌,跌)"
    for y in ("2024", "2025", "2026"):
        for m, t in (("主軸", "① 主軸"), ("Stacking 邏輯迴歸", "② Stacking 邏輯迴歸")):
            assert res["results"]["shape29"][y][m][key] == ref[y][t][key]
            assert res["results"]["shape29"][y][m]["macro_f1"] == round(ref[y][t]["macro_f1"] * 100, 2)
