"""Stacking(拿掉規則,兩組 AE + OC-SVM → 元學習器)的行為。

Component:A / B 切分、每一種元學習器的輸入輸出
System   :重構後與重構前(2026-10-29 的 stacking_2024.json)逐一相同;StackingSource 與實驗流程結果相同
"""
import numpy as np
import pandas as pd
import pytest

import walkforward as WF
import stacking as S
from confusion import summarize
from feasibility import clean
from learn5_trade6 import FLAT, UP, DOWN
from paper_aeocsvm import NAMES

# 重構前 stacking.py 的結果(種子 42,測試 2024 的 macro-F1)
BEFORE = {"score|lr": 0.487763, "score+recon|lr": 0.492482, "score+pos|lr": 0.537158,
          "score|hgb": 0.481372, "score|svm": 0.480427, "score|tree": 0.475358}


@pytest.fixture(scope="module")
def abc(panel):
    df, fc = panel
    d = WF.year_split(df, 2024)
    A, B = S.split_base_meta(d["train"])
    return A, B, d["test"], fc, d["train"]


@pytest.fixture(scope="module")
def scored(abc):
    A, B, C, fc, _ = abc
    base = S.BaseScorers(42).fit(A, fc)
    return base.transform(B), base.transform(C)


def test_component_split_base_meta(data, abc):
    """Given 2024 的訓練期(2020–2023) / When 切成基底層 A 與元學習器 B / Then A 只有 2020–2022、B 只有 2023;
    A 的每一筆標籤(該股自己的 t+5)都早於 2023 年第一天,所以元學習器看到的分數來自基底層沒看過的資料"""
    A, B, _, _, _ = abc
    assert A.date.dt.year.between(2020, 2022).all() and (B.date.dt.year == 2023).all()
    assert (len(A), len(B)) == (36385, 11700)
    plus5 = pd.concat([pd.DataFrame({"ticker": tk, "date": c.index, "t5": pd.Series(c.index).shift(-5).to_numpy()})
                       for tk, c in ((tk, clean(x)) for tk, x in data.items())])
    m = A[["ticker", "date"]].merge(plus5, on=["ticker", "date"], how="left")
    assert (m.t5 < pd.Timestamp("2023-01-01")).all()


@pytest.mark.parametrize("learner", list(S.LEARNERS))
def test_component_meta_learner_three_classes(learner):
    """Given 一份三類都有的合成分數(高點分數大 → 高點、低點分數大 → 低點) / When 用這種元學習器訓練並預測 /
    Then 輸出只有低點 / 非極值 / 高點三類、每一類都會出現,分數是 0 ~ 1 的機率(沒有機率的 SVM 為 0)"""
    rng = np.random.default_rng(0)
    n = 900
    y = rng.choice([UP, FLAT, DOWN], size=n, p=[0.2, 0.6, 0.2])
    F = pd.DataFrame({"s_high": rng.normal(0, 1, n) + 3 * (y == DOWN), "s_low": rng.normal(0, 1, n) + 3 * (y == UP)})
    pred, score = S.MetaLearner(learner, "score").fit(F, y).predict(F)
    assert set(np.unique(pred)) == {UP, FLAT, DOWN}
    assert np.isfinite(score).all() and ((score >= 0) & (score <= 1)).all()


@pytest.mark.parametrize("key", list(BEFORE))
def test_system_refactor_matches_before(abc, scored, key):
    """Given 重構後的基底層與元學習器(種子 42) / When 重跑舊的輸入 × 元學習器組合 / Then 測試 2024 的 macro-F1 和重構前完全相同"""
    _, B, C, _, _ = abc
    FB, FC = scored
    inp, ln = key.split("|")
    pred, _ = S.MetaLearner(ln, inp).fit(FB, B.y.to_numpy()).predict(FC)
    assert summarize(C.y.to_numpy(), pred, NAMES)["macro_f1"] == pytest.approx(BEFORE[key], abs=1e-6)


def test_system_source_equals_experiment(abc, scored):
    """Given StackingSource(邏輯迴歸、只用分數) / When 走 SignalSource 介面訓練 2020–2023、預測 2024 /
    Then 每一天的判斷和實驗流程(基底層 + 元學習器)完全相同,所以逐年回測可以直接用它"""
    _, B, C, fc, train = abc
    FB, FC = scored
    pred, _ = S.MetaLearner("lr", "score").fit(FB, B.y.to_numpy()).predict(FC)
    src = S.StackingSource("lr", "score")
    src.fit(train, fc)
    out = src.predict(C.drop(columns="y"))
    assert np.array_equal(out.pred.to_numpy(), pred)
