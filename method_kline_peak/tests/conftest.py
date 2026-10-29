"""主軸測試的共用資料與自動測試報告。

報告列出每個測試 docstring 裡的 Given / When / Then,人審的是「這些行為是不是我們對主軸正確性的定義」,
不是測試碼本身。執行後寫到 tests/REPORT.md。
"""
import os
import pathlib
import sys
from argparse import Namespace

import numpy as np
import pytest
import torch

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import mainline as ML  # noqa: E402
from feasibility import START, END, load_pool  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402

SEED, NU = 42, 0.1
ARGS = Namespace(weight="purity", gamma="scale", nu=[NU])


@pytest.fixture(scope="session")
def data():
    return load_pool(ML.POOL, START, END)


@pytest.fixture(scope="session")
def panel(data):
    return ML.build_panel(data, 6, [])          # (panel, feat_cols)


def predict_split(panel, sp_name, seed=SEED, classes=(DOWN, UP)):
    """照主軸(export_windows 同一流程)訓練並預測;回傳 (train, test, pred, models)。"""
    df, fc = panel
    d = ML.split(df, ML.SPLITS[sp_name])
    tr, te = d["train"], d["test"]
    ML.setup_ae()
    torch.manual_seed(seed)
    np.random.seed(seed)
    pred, models = np.full(len(te), FLAT), {}
    for cls in classes:
        m = ML.fit_class(tr, cls, fc, ARGS)
        c = te[ML.CAND[cls]].to_numpy()
        Xt = np.clip(m["sc"].transform(te.loc[c, fc].fillna(m["med"])), -5, 5).astype(np.float32)
        with torch.no_grad():
            zt = m["ae"].encode(torch.FloatTensor(Xt)).numpy()
        pred[np.flatnonzero(c)[m["ocs"][NU].predict(zt) == 1]] = cls
        models[cls] = m
    return tr, te, pred, models


@pytest.fixture(scope="session")
def run2024(panel):
    return predict_split(panel, "測試 2024")


# ───────────── 自動測試報告 ─────────────
_rows = []
LEVEL = {"component": "Component", "module": "Module", "system": "System"}


def pytest_runtest_makereport(item, call):
    if call.when == "call":
        doc = (item.function.__doc__ or "").strip()
        doc = " ".join(line.strip() for line in doc.splitlines() if line.strip())
        param = ""
        if hasattr(item, "callspec"):
            name = item.callspec.id.encode().decode("unicode_escape")          # pytest 會把中文 id 轉成 \u 編碼
            p = item.callspec.params
            if "closes" in p:                                                   # 標籤案例:直接列出這個案例的輸入與預期
                lab = {DOWN: "高點", UP: "低點", FLAT: "非極值"}[p["y"]]
                cand = "高點候選" if p["cand_hi"] else "低點候選" if p["cand_lo"] else "不是候選"
                doc = f"Given 收盤 {p['closes']}(t 是第 6 個) / When 貼標籤、套規則 / Then 標籤 = {lab},規則 = {cand}"
            param = f"[{name}] "
        level = next((v for k, v in LEVEL.items() if item.name.startswith(f"test_{k}")), "-")
        _rows.append((level, item.name.split("[")[0], param + doc, "通過" if call.excinfo is None else "失敗"))


def pytest_sessionfinish(session, exitstatus):
    if not _rows:
        return
    passed = sum(r[3] == "通過" for r in _rows)
    lines = ["# 主軸測試報告(自動產生)", "", f"結果:{passed} / {len(_rows)} 通過", "",
             "| # | 層級 | 測試 | 情境(Given / When / Then) | 結果 |", "|---|---|---|---|---|"]
    for i, (lv, name, doc, res) in enumerate(_rows, 1):
        lines.append(f"| {i} | {lv} | `{name}` | {doc} | {res} |")
    out = pathlib.Path(__file__).with_name("REPORT.md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
