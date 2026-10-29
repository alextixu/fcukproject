"""主軸(論文標籤 + 規則候選 + AE + OC-SVM)的行為契約。

Component:標籤、規則候選、29 個特徵各自的 I/O
Module   :切分不洩漏、訓練只用訓練期的真高 / 真低點、預測結構
System   :整條流程可重現、指標算對、2024 測試數字與報告一致、資料品質

用法: python -m pytest method_kline_peak/tests -q   (約 1 分鐘;報告寫到 tests/REPORT.md)
"""
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import f1_score

import mainline as ML
from conftest import predict_split
from feasibility import clean
from learn5_trade6 import FLAT, UP, DOWN
from paper_aeocsvm import NAMES, paper_label, rule_pred
from confusion import ORDER, summarize

T = 5   # 合成序列中 t 的位置(第 6 天)


def label_at_t(closes):
    y, hi, lo = paper_label(pd.Series(closes, dtype=float))
    return y.iloc[T], bool(hi.iloc[T]), bool(lo.iloc[T])


# ─────────────────────────── Component:標籤與規則 ───────────────────────────
LABEL_CASES = {
    #  名稱                 11 天收盤(t 是第 6 個)                       標籤    高點候選 低點候選
    "嚴格最高":           ([10, 11, 12, 13, 14, 20, 15, 14, 13, 12, 11], DOWN, True, False),
    "與之後同價並列最高":  ([10, 11, 12, 13, 14, 20, 15, 20, 13, 12, 11], DOWN, True, False),
    "之後被超越=假候選":   ([10, 11, 12, 13, 14, 20, 21, 14, 13, 12, 11], FLAT, True, False),
    "嚴格最低":           ([20, 19, 18, 17, 16, 10, 15, 16, 17, 18, 19], UP, False, True),
    "之後更低=假低點候選":  ([20, 19, 18, 17, 16, 10, 15, 9, 17, 18, 19], FLAT, False, True),
    "盤整中間=一般日子":   ([10, 12, 11, 13, 12, 12, 13, 11, 12, 10, 13], FLAT, False, False),
    "11 天全部同價":       ([10] * 11, FLAT, False, False),
    "左邊 6 天同價後下跌":  ([10, 10, 10, 10, 10, 10, 9, 8, 7, 6, 5], DOWN, False, False),
}


@pytest.mark.parametrize("closes,y,cand_hi,cand_lo", LABEL_CASES.values(), ids=LABEL_CASES.keys())
def test_component_label_and_rule(closes, y, cand_hi, cand_lo):
    """Given t-5 ~ t+5 的 11 天收盤 / When 貼論文標籤並套規則 / Then 標籤(高點 / 低點 / 非極值)與高、低點候選符合定義:
    並列也算、之後被超越是假候選、全同價是非極值;左邊 6 天同價時規則不挑(t 同時是 6 日最高與最低),所以會漏掉這種真高點"""
    assert label_at_t(closes) == (y, cand_hi, cand_lo)


def test_component_incomplete_window_is_unlabeled():
    """Given 一串收盤 / When 貼標籤 / Then 前 5 天與最後 5 天(11 日窗口不完整)沒有標籤,不會進入訓練或測試"""
    y, _, _ = paper_label(pd.Series(np.arange(30, dtype=float)))
    assert y.iloc[:5].isna().all() and y.iloc[-5:].isna().all() and y.iloc[5:-5].notna().all()


def test_component_rule_never_misses_except_flat_left(panel):
    """Given TW50 2016~2026 全部股票日 / When 比對規則候選與真標籤 / Then 高、低點候選互斥;
    沒被規則挑到的真高(低)點,全部都是「t-5 ~ t 收盤同價」的特例"""
    df, _ = panel
    assert not (df.cand_hi & df.cand_lo).any()
    for cls, cand in ((DOWN, "cand_hi"), (UP, "cand_lo")):
        miss = df[(df.y == cls) & ~df[cand]]
        assert (miss[[f"c{k}" for k in range(1, 6)]].abs() < 1e-4).all(axis=None), f"{NAMES[cls]} 有非特例的漏網"


# ─────────────────────────── Component:29 個特徵 ───────────────────────────
@pytest.fixture(scope="module")
def stock(data):
    return clean(data["2382.TW"])


def test_component_feature_columns(panel):
    """Given 主軸的特徵設定(6 根 K、量 ÷ 10 日均量) / When 建立面板 / Then 剛好 29 個特徵:開高低收 × 6 天 − t 日收盤 + 量 × 6 天;
    標籤、候選、股票代號與交易報酬 r5 都不在特徵裡"""
    _, fc = panel
    expect = [f"{p}{k}" for k in range(6) for p in "ohlcv" if not (p == "c" and k == 0)]
    assert len(fc) == 29 and sorted(fc) == sorted(expect)
    assert not {"y", "cand_hi", "cand_lo", "ticker", "r5", "date", "c0"} & set(fc)


def test_component_features_do_not_peek_future(stock):
    """Given 廣達的日 K / When 把 2024-11-08 之後的開高低收量全部亂改 / Then 2024-11-08 以前每一天的 29 個特徵完全不變(不偷看未來)"""
    t = pd.Timestamp("2024-11-08")
    f0 = ML.shape_features(stock, 6)
    s2 = stock.copy()
    later = s2.index > t
    rng = np.random.default_rng(0)
    for col in ("open", "high", "low", "close", "volume"):
        s2.loc[later, col] *= rng.uniform(0.5, 2.0, later.sum())
    f1 = ML.shape_features(s2, 6)
    pd.testing.assert_frame_equal(f0.loc[:t], f1.loc[:t])


def test_component_features_scale_invariant(stock):
    """Given 廣達的日 K / When 價格全部 × 3、成交量全部 × 7 / Then 29 個特徵不變(只看形狀,不看股價高低與成交量大小)"""
    s2 = stock.copy()
    s2[["open", "high", "low", "close"]] *= 3
    s2["volume"] *= 7
    a, b = ML.shape_features(stock, 6).dropna(), ML.shape_features(s2, 6).dropna()
    np.testing.assert_allclose(a.to_numpy(), b.to_numpy(), atol=1e-12)


# ─────────────────────────── Module:切分與訓練 ───────────────────────────
@pytest.mark.parametrize("sp_name", ["測試 2024", "我們的切分"])
def test_module_split_no_label_leak(data, panel, sp_name):
    """Given 主軸切分(訓練 2020–2023;測試 2024 或 2025–26) / When 切出訓練與測試 / Then 每一檔股票、每一個訓練樣本,
    它的 t+5(該股票自己的第 5 個交易日)都早於測試期第一天,而且訓練與測試的日期沒有重疊"""
    df, _ = panel
    d = ML.split(df, ML.SPLITS[sp_name])
    tr, te = d["train"], d["test"]
    start = pd.Timestamp(ML.SPLITS[sp_name]["test"][0])
    plus5 = pd.concat([pd.DataFrame({"ticker": tk, "date": c.index, "t5": pd.Series(c.index).shift(-5).to_numpy()})
                       for tk, c in ((tk, clean(x)) for tk, x in data.items())])
    m = tr[["ticker", "date"]].merge(plus5, on=["ticker", "date"], how="left")
    assert m.t5.notna().all() and (m.t5 < start).all(), f"{(m.t5 >= start).sum()} 筆訓練標籤跨進測試期"
    assert tr.date.max() < te.date.min()


def test_module_fit_uses_only_train_true_class(run2024):
    """Given 2024 切分的訓練期 / When 訓練高點、低點各一組 AE + OC-SVM / Then 標準化只用訓練期的該類候選;
    OC-SVM 只用訓練期候選中的真高(低)點,一筆測試資料都沒用"""
    tr, _, _, models = run2024
    for cls in (DOWN, UP):
        m, cand = models[cls], tr[ML.CAND[cls]]
        assert m["sc"].n_samples_seen_ == cand.sum()
        assert m["ocs"][0.1].shape_fit_[0] == (cand & (tr.y == cls)).sum()


def test_module_prediction_structure(run2024):
    """Given 2024 測試期的判斷 / When 對照規則候選 / Then 判高點的一定是高點候選、判低點的一定是低點候選、
    不是候選的一律判非極值;所以真高點不會被判成低點,真低點也不會被判成高點"""
    _, te, pred, _ = run2024
    assert te.cand_hi.to_numpy()[pred == DOWN].all()
    assert te.cand_lo.to_numpy()[pred == UP].all()
    assert (pred[~(te.cand_hi | te.cand_lo).to_numpy()] == FLAT).all()
    y = te.y.to_numpy()
    assert ((y == DOWN) & (pred == UP)).sum() == 0 and ((y == UP) & (pred == DOWN)).sum() == 0


# ─────────────────────────── System:整條流程 ───────────────────────────
def test_system_reproducible(panel, run2024):
    """Given 同一份資料與種子 42 / When 把高點模型從頭再訓練一次 / Then 2024 每一天的高點判斷完全一樣(結果可重現)"""
    _, te, pred, _ = run2024
    _, _, pred2, _ = predict_split(panel, "測試 2024", classes=(DOWN,))
    hi = te.cand_hi.to_numpy()
    assert np.array_equal(pred[hi] == DOWN, pred2[hi] == DOWN)


def test_system_metrics_match_report(run2024):
    """Given 2024 測試期的判斷 / When 計算混淆矩陣與 macro-F1 / Then 混淆矩陣加總 = 12,098 天、macro-F1 與 sklearn 一致;
    規則 54.20%、模型(種子 42)53.96%,與簡報和 README 的數字相同"""
    _, te, pred, _ = run2024
    y = te.y.to_numpy()
    s, r = summarize(y, pred, NAMES), summarize(y, rule_pred(te), NAMES)
    assert np.array(s["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"]).sum() == len(te) == 12098
    assert s["macro_f1"] == pytest.approx(f1_score(y, pred, labels=ORDER, average="macro"))
    assert r["macro_f1"] == pytest.approx(0.5420, abs=5e-5)
    assert s["macro_f1"] == pytest.approx(0.5396, abs=5e-5)


def test_system_data_quality(data):
    """Given TW50 50 檔還原日 K / When 清理後檢查 / Then 沒有零量日、最高 ≥ 開收、最低 ≤ 開收;
    每年「開盤 ÷ 前日收盤」中位數在 0.98 ~ 1.02(開盤和收盤用同一套還原,沒有錯位)"""
    assert len(data) == 50
    for tk, raw in data.items():
        df = clean(raw)
        assert (df.volume > 0).all()
        assert (df.high >= df[["open", "close"]].max(axis=1)).all() and (df.low <= df[["open", "close"]].min(axis=1)).all()
        med = (df.open / df.close.shift(1)).groupby(df.index.year).median()
        assert med.between(0.98, 1.02).all(), tk
