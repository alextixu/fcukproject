"""網頁系統測試的共用設定。

- 每個測試的存檔都寫到暫存資料夾(tmp_data),不會碰到 web/data 的正式存檔。
- 需要正式模型的系統測試:有 web/data/models/model_2026.joblib 就直接讀,沒有就訓練一次(約 30 秒)。
"""
import os
import pathlib
import sys
import warnings

import numpy as np
import pandas as pd
import pytest

WEB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB))
warnings.filterwarnings("ignore")

from system import config as C  # noqa: E402

C.set_profile("tw100", 0.0)                    # 測試固定用預設設定(不受環境變數影響)
REAL_DATA = C.DATA


@pytest.fixture
def tmp_data(tmp_path, monkeypatch):
    """把存檔位置換成暫存資料夾。"""
    monkeypatch.setattr(C, "DATA", str(tmp_path / "data"))
    monkeypatch.setattr(C, "SITE_DATA", str(tmp_path / "site_data"))
    return tmp_path


@pytest.fixture(scope="session")
def real_store():
    """讀研究快取的真實 K 線(只讀,寫到暫存資料夾)。"""
    import tempfile
    from system.datasource import PriceStore
    d = tempfile.mkdtemp()
    return PriceStore(root=d, downloader=None)


@pytest.fixture(scope="session")
def prod_model(real_store):
    import joblib
    from system import model as MD
    path = os.path.join(REAL_DATA, "tw100", "models", "model_2026.joblib")
    m = joblib.load(path) if os.path.exists(path) else None
    if m is None:
        old = C.DATA
        C.DATA = REAL_DATA
        try:
            m = MD.train(2026, real_store, log=lambda *_: None)
        finally:
            C.DATA = old
    return m
