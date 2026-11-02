"""股票池與訓練門檻是設定值:換設定不用改程式,存檔分開放。"""
import os

import numpy as np
import pytest

from system import config as C, model as MD, store as ST, universe as U
from learn5_trade6 import FLAT  # noqa: E402


def test_default_profile():
    """Given 沒有另外設定 / When 讀目前設定 / Then 股票池 tw100、訓練門檻 0%,設定名稱 tw100"""
    assert (C.POOL, C.TRAIN_MIN_AMP, C.profile()) == ("tw100", 0.0, "tw100")


def test_profile_separates_storage(tmp_data, monkeypatch):
    """Given 設定換成 TW200、訓練門檻 3% / When 取存檔與模型的位置 / Then 都在 data/tw200_amp3/ 底下,和預設設定分開;
    K 線快取不分設定,共用 data/prices/"""
    monkeypatch.setattr(C, "POOL", "tw200")
    monkeypatch.setattr(C, "TRAIN_MIN_AMP", 3.0)
    assert C.profile() == "tw200_amp3"
    root = os.path.join(C.DATA, "tw200_amp3")
    assert ST.day_path("2026-03-02").startswith(root) and ST.grade_path("2026-03-02").startswith(root)
    assert MD.model_path(2026).startswith(root)
    from system.datasource import PriceStore
    assert PriceStore(seed_dir="").root == os.path.join(C.DATA, "prices")


@pytest.mark.parametrize("pool,n", [("tw100", 73), ("tw200", 168), ("tw50", 34)])
def test_pool_setting_uses_research_lists(pool, n):
    """Given 股票池設定為 tw100 / tw200 / tw50 / When 取 2026 年的股票池 / Then 和研究結果檔記錄的清單相同(73 / 168 / 34 檔)"""
    p = U.pool_for_year(2026, pool=pool)
    assert len(p) == n and "2412.TW" not in p


def test_train_min_amp_setting(real_store, monkeypatch):
    """Given 訓練門檻 0% 與 3% / When 取 2026 年模型的訓練資料 / Then 筆數相同;3% 時幅度不到 3% 的高低點改成非極值,
    高低點變少,其餘不變(同研究 walkforward.relabel);0% 時標籤完全不動"""
    import mainline as ML
    import walkforward as WF
    monkeypatch.setattr(C, "TRAIN_MIN_AMP", 0.0)
    tr0, fc, pool = MD.training_set(2026, real_store)
    monkeypatch.setattr(C, "TRAIN_MIN_AMP", 3.0)
    tr3, _, _ = MD.training_set(2026, real_store)
    assert len(tr0) == len(tr3) and len(pool) == 73
    n0, n3 = (tr0.y != FLAT).sum(), (tr3.y != FLAT).sum()
    assert n3 < n0
    changed = tr0.y.to_numpy() != tr3.y.to_numpy()
    assert (tr3.y.to_numpy()[changed] == FLAT).all() and (tr0.amp.to_numpy()[changed] < 3).all()
    data = real_store.load_many(pool, end="2026-01-31")
    panel, _ = ML.build_panel({tk: df.loc[ML.START:] for tk, df in data.items()}, 6, [])
    raw = WF.year_split(panel, 2026)["train"]
    assert np.array_equal(raw.y.to_numpy(), tr0.y.to_numpy())
