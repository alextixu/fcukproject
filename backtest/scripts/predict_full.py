"""最終系統用的模型(XGB tw50 h=5 cs、permpos 特徵、seed 42/43/44)重訓,對 2026 所有特徵日產生預測(含尚無 5 日標籤的最後幾天)。

原本 run_pipeline 的 test 集只收「已知 5 日後報酬」的列,所以 _testpred 只到 2026-09-03。這裡用完全相同的資料、特徵、切分、
超參數與 seed 重訓,再對 2026-01-01 之後的每一個交易日打分,並核對與原 testpred 重疊部分一致。
輸出: results/tw50_h5_permpos_fullpred.parquet(index = date, ticker;欄 p)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
XGB = P.METHOD_XGB
sys.path.insert(0, os.path.join(XGB, "src"))
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
from split import time_split           # noqa: E402
from train_xgb import fit_xgb, predict_p  # noqa: E402

EXP = os.path.join(XGB, "experiments")
import argparse
_ap = argparse.ArgumentParser(); _ap.add_argument("--tag", default="x26-tw50-h5-cs"); _ap.add_argument("--set", default="full_permpos"); _a = _ap.parse_known_args()[0]
TAG, SET = _a.tag, _a.set


def main():
    meta = json.load(open(os.path.join(EXP, f"{TAG}.json"), encoding="utf-8"))
    cfg = meta["config"]
    feats = meta["results"][SET]["features"]
    panel = pd.read_parquet(os.path.join(P.FEATURES, f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}.parquet"))
    ycol = f"y_{cfg['label']}_h{cfg['horizon']}"
    tr, va, _ = time_split(panel, cfg["train_end"], cfg["val_end"], cfg["horizon"], ycol)
    dates = panel.index.get_level_values("date")
    te = panel[dates > pd.Timestamp(cfg["val_end"])]            # 不要求標籤:每個特徵日都打分
    print(f"train {len(tr)} / val {len(va)} / 打分 {len(te)} 列,{te.index.get_level_values('date').max().date()} 為最後一天,特徵 {len(feats)}")
    ps = []
    for seed in cfg["seeds"]:
        m = fit_xgb(tr[feats], tr[ycol].values.astype(int), va[feats], va[ycol].values.astype(int), seed, cfg["xgb"])
        ps.append(predict_p(m, te[feats]))
        print(f"  seed {seed} best_iter {m.best_iteration}")
    out = pd.DataFrame({"p": np.mean(ps, axis=0).astype("float32")}, index=te.index)
    old = pd.read_parquet(os.path.join(EXP, f"{TAG}_testpred.parquet"))[f"p_{SET}"]
    j = out.join(old.rename("p_old"), how="inner")
    print(f"核對原 testpred:重疊 {len(j)} 列,相關 {j['p'].corr(j['p_old']):.6f},最大差 {float((j['p'] - j['p_old']).abs().max()):.2e}")
    fp = os.path.join(P.RESULTS, "tw50_h5_permpos_fullpred.parquet" if TAG == "x26-tw50-h5-cs" and SET == "full_permpos" else f"fullpred_{TAG}_{SET}.parquet")
    out.to_parquet(fp)
    print(f"[SAVED] {fp}")


if __name__ == "__main__":
    main()
