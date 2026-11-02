"""訓練時的幅度門檻(2026-11-02 使用者要求:用 3% 訓練,對答案仍用原本的標籤)。

Module:幅度計算可手算、門檻只改訓練標籤、幅度不是特徵
System:2020–2023 達 3% 的點數、加門檻後測試期的答案與規則訊號不變
"""
import numpy as np
import pandas as pd
import pytest

import walkforward as WF
from paper_aeocsvm import paper_label, label_amp
from learn5_trade6 import FLAT, UP, DOWN


def _series(vals):
    return pd.Series(vals, index=pd.bdate_range("2024-01-01", periods=len(vals)), dtype=float)


def test_module_label_amp_high_hand_computed():
    """Given 收盤 100 → 104 慢慢漲、第 6 天 110,之後 5 天最低 104 / When 算標籤幅度 /
    Then 第 6 天是高點,左邊 110 / 100 − 1 = 10%、右邊 1 − 104 / 110 = 5.45%,幅度取較小的 5.45%;其他天沒有幅度"""
    C = _series([100, 101, 102, 103, 104, 110, 107, 106, 108, 105, 104])
    y, _, _ = paper_label(C)
    amp = label_amp(C, y)
    assert y.iloc[5] == DOWN and amp.iloc[5] == pytest.approx((1 - 104 / 110) * 100)
    assert amp.drop(C.index[5]).isna().all()


def test_module_label_amp_low_hand_computed():
    """Given 收盤從 110 跌到第 6 天 100,之後 5 天最高 106 / When 算標籤幅度 /
    Then 第 6 天是低點,左邊 1 − 100 / 110 = 9.09%、右邊 106 / 100 − 1 = 6%,幅度取較小的 6%"""
    C = _series([110, 108, 107, 106, 105, 100, 103, 104, 101, 102, 106])
    y, _, _ = paper_label(C)
    amp = label_amp(C, y)
    assert y.iloc[5] == UP and amp.iloc[5] == pytest.approx(6.0)


def test_module_relabel_only_small_points():
    """Given 高點幅度 2% 與 4%、低點幅度 3%、一個非極值 / When 用 3% 門檻改訓練標籤 /
    Then 2% 的高點變非極值,4% 的高點和剛好 3% 的低點保留,非極值不變;門檻 0 時完全不改"""
    tr = pd.DataFrame({"y": [DOWN, DOWN, UP, FLAT], "amp": [2.0, 4.0, 3.0, np.nan]})
    assert list(WF.relabel(tr, 3).y) == [FLAT, DOWN, UP, FLAT]
    assert WF.relabel(tr, 0) is tr


def test_module_amp_is_not_a_feature(panel):
    """Given 主軸的資料表 / When 取特徵欄 / Then 標籤幅度(會用到未來 5 天)不在特徵裡"""
    _, fc = panel
    assert "amp" not in fc and len(fc) == 29


def test_system_train_counts_2020_2023(panel):
    """Given 2024 的訓練期 2020–2023 / When 用 3% 門檻改訓練標籤 / Then 高點從 3,771 剩 1,254、低點從 3,652 剩 1,312,
    其餘都變成非極值,總天數不變"""
    df, _ = panel
    tr = WF.year_split(df, 2024)["train"]
    r = WF.relabel(tr, 3)
    assert ((tr.y == DOWN).sum(), (tr.y == UP).sum()) == (3771, 3652)
    assert ((r.y == DOWN).sum(), (r.y == UP).sum()) == (1254, 1312) and len(r) == len(tr)


def test_system_scoring_uses_original_labels(panel):
    """Given 用 3% 門檻訓練 / When 預測 2024 / Then 對答案的 y 仍是原本的標籤(和 0% 時完全相同);
    不看標籤的規則訊號也完全不變"""
    df, fc = panel
    a, _ = WF.run_year(df, fc, 2024, WF.RuleSource(), train_min_amp=3)
    b, _ = WF.run_year(df, fc, 2024, WF.RuleSource())
    te = WF.year_split(df, 2024)["test"]
    assert np.array_equal(a.y.to_numpy(), te.y.to_numpy()) and a.equals(b)
