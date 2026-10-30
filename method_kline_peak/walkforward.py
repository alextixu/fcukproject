"""逐年 walk-forward:每個測試年 Y 用前 4 年重新訓練,預測 Y 年每一天的訊號。

訊號來源抽成 SignalSource 介面(Strategy):回測引擎只依賴這個介面,換訊號來源不用改引擎。
  RuleSource      規則:t 收盤為近 6 日最低 → 低點、最高 → 高點,其餘非極值(不用訓練)
  MainlineSource  主軸:規則候選 + 高點、低點各一組 AE + OC-SVM(設定同 mainline.py:29 個特徵、
                  量 ÷ 10 日均量、29 → 16、nu 0.1、相似度權重、種子 42)
新增訊號來源 = 新增一個 SignalSource 子類,並加進 SOURCES。

介面契約(tests/test_backtest.py 對每個實作跑同一組):
  fit(train, feat_cols)  只能看訓練期資料
  predict(test)          回傳 DataFrame[date, ticker, pred, score],一列對一個測試股票日,順序同 test;
                         pred ∈ {低點 UP, 非極值 FLAT, 高點 DOWN};score 越大越有把握(只在同類訊號間比大小);
                         不可讀 test 的標籤 y
切分:訓練 Y-4 ~ Y-1、測試 Y;測試年第一天前 5 個交易日剔除(它們的標籤會用到 Y 年的價格)。
"""
from abc import ABC, abstractmethod
from argparse import Namespace

import numpy as np
import pandas as pd
import torch

import mainline as ML
from learn5_trade6 import FLAT, UP, DOWN
from paper_aeocsvm import rule_pred

YEARS = tuple(range(2020, 2027))
TRAIN_YEARS = 4
SEED, NU = 42, 0.1
COLS = ["date", "ticker", "pred", "score"]


def year_split(panel, year, train_years=TRAIN_YEARS):
    sp = {"train": (f"{year - train_years}-01-01", f"{year - 1}-12-31"), "test": (f"{year}-01-01", f"{year}-12-31")}
    return ML.split(panel, sp)


class SignalSource(ABC):
    name = "abstract"

    @abstractmethod
    def fit(self, train, feat_cols):
        """只用訓練期資料。"""

    @abstractmethod
    def predict(self, test) -> pd.DataFrame:
        """回傳 COLS 欄位,一列對一個測試股票日。"""

    def _frame(self, test, pred, score):
        return pd.DataFrame({"date": test["date"].to_numpy(), "ticker": test["ticker"].to_numpy(),
                             "pred": np.asarray(pred, dtype=int), "score": np.asarray(score, dtype=float)})


class RuleSource(SignalSource):
    name = "規則"

    def fit(self, train, feat_cols):
        pass

    def predict(self, test):
        return self._frame(test, rule_pred(test), np.zeros(len(test)))


class MainlineSource(SignalSource):
    name = "主軸"

    def __init__(self, seed=SEED):
        self.seed = seed

    def fit(self, train, feat_cols):
        ML.setup_ae()
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        self.fc = feat_cols
        args = Namespace(weight="purity", gamma="scale", nu=[NU])
        self.models = {cls: ML.fit_class(train, cls, feat_cols, args) for cls in (DOWN, UP)}   # 先高後低,同主軸

    def predict(self, test):
        pred, score = np.full(len(test), FLAT), np.zeros(len(test))
        for cls, m in self.models.items():
            c = test[ML.CAND[cls]].to_numpy()
            if not c.any():
                continue
            X = np.clip(m["sc"].transform(test.loc[c, self.fc].fillna(m["med"])), -5, 5).astype(np.float32)
            with torch.no_grad():
                z = m["ae"].encode(torch.FloatTensor(X)).numpy()
            oc, idx = m["ocs"][NU], np.flatnonzero(c)
            keep = oc.predict(z) == 1
            pred[idx[keep]] = cls
            score[idx] = oc.decision_function(z)
        return self._frame(test, pred, score)


SOURCES = {"主軸": MainlineSource, "規則": RuleSource}


def run_year(panel, feat_cols, year, source):
    """訓練 Y-4 ~ Y-1 → 預測 Y;回傳 (訊號表含標籤 y, 訓練樣本數)。"""
    d = year_split(panel, year)
    tr, te = d["train"], d["test"]
    source.fit(tr, feat_cols)
    sig = source.predict(te.drop(columns="y"))
    sig["y"] = te["y"].to_numpy()
    return sig, len(tr)
