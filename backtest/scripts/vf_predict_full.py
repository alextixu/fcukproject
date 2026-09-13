"""量增篩選訓練的 v3 型模型(vf{YY}-tw50-h5-cs-spike12 / full_permpos)重訓後,對測試年「全部」tw50 股票日打分
(訓練/驗證只用量增樣本,打分不篩,這樣排名才完整;同 predict_full.py 的做法,多了 sample filter)。
輸出: results/fullpred_<tag>_<set>.parquet(index = date, ticker;欄 p),並核對與 _testpred 重疊列一致。
用法: python vf_predict_full.py --tag vf26-tw50-h5-cs-spike12 [--set full_permpos] [--year 2026]
"""
import argparse
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
from split import time_split                # noqa: E402
from train_xgb import fit_xgb, predict_p    # noqa: E402

EXP = os.path.join(XGB, "experiments")


def apply_filter(panel, rule_str, ycol):
    """同 run_pipeline.py --sample-filter:不符合的列標籤設 NaN(不進 train / val)。"""
    keep = pd.Series(True, index=panel.index)
    for rule in rule_str.split("+"):
        if rule.startswith("liq"):
            q = int(rule[3:]) / 100
            amt = (panel["close"] * panel["volume"]).groupby(level="ticker").transform(lambda x: x.rolling(20, min_periods=10).mean())
            keep &= (amt.groupby(level="date").rank(pct=True) >= 1 - q).fillna(False)
        elif rule.startswith("spike"):
            keep &= (panel["vol_sma_ratio_20"] >= int(rule[5:]) / 10 - 1).fillna(False)
    panel.loc[~keep.values, ycol] = np.nan
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--set", default="full_permpos")
    ap.add_argument("--year", type=int)
    a = ap.parse_args()
    meta = json.load(open(os.path.join(EXP, f"{a.tag}.json"), encoding="utf-8"))
    cfg = meta["config"]
    feats = meta["results"][a.set]["features"]
    panel = pd.read_parquet(os.path.join(P.FEATURES, f"features_{cfg['pool']}_{cfg['start']}_{cfg['end']}.parquet"))
    ycol = f"y_{cfg['label']}_h{cfg['horizon']}"
    dates = panel.index.get_level_values("date")
    te = panel[dates > pd.Timestamp(cfg["val_end"])]
    if a.year:
        te = te[te.index.get_level_values("date").year == a.year]
    keep = apply_filter(panel, cfg["sample_filter"], ycol)
    tr, va, _ = time_split(panel, cfg["train_end"], cfg["val_end"], cfg["horizon"], ycol)
    print(f"[{a.tag}] filter {cfg['sample_filter']} 保留 {keep.mean() * 100:.1f}%;train {len(tr)} val {len(va)};"
          f"打分 {len(te)} 列({te.index.get_level_values('date').min().date()} ~ {te.index.get_level_values('date').max().date()}),特徵 {len(feats)}")
    ps = []
    for seed in cfg["seeds"]:
        m = fit_xgb(tr[feats], tr[ycol].values.astype(int), va[feats], va[ycol].values.astype(int), seed, cfg["xgb"])
        ps.append(predict_p(m, te[feats]))
        print(f"  seed {seed} best_iter {m.best_iteration}")
    out = pd.DataFrame({"p": np.mean(ps, axis=0).astype("float32")}, index=te.index)
    old = pd.read_parquet(os.path.join(EXP, f"{a.tag}_testpred.parquet"))[f"p_{a.set}"]
    j = out.join(old.rename("p_old"), how="inner")
    print(f"核對 testpred:重疊 {len(j)} 列,相關 {j['p'].corr(j['p_old']):.6f},最大差 {float((j['p'] - j['p_old']).abs().max()):.2e}")
    fp = os.path.join(P.RESULTS, f"fullpred_{a.tag}_{a.set}.parquet")
    out.to_parquet(fp)
    print("[SAVED]", fp)


if __name__ == "__main__":
    main()
