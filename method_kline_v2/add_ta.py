"""把 method_xgb 的單股技術指標(約 220 欄)逐檔算好接到 samples_<pool>.parquet 當 C 欄(沒有現成特徵面板的池用)。
橫斷面 cs_* / mkt_* 欄不算(需要整池同日資料),所以這種 C 比 tw50 / tw200 現成面板的 C 少 20 欄。
用法:python add_ta.py --pool tw100 | tw500 | all
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
os.environ.setdefault("TW_CACHE_DIR", P.YF_2026_CACHE)
sys.path.insert(0, P.XGB_SRC)
import data as _d                              # noqa: E402
from data import load_pool                     # noqa: E402
from features import single_stock_features     # noqa: E402

DATA = os.path.join(P.CACHE, "bigmove")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    a = ap.parse_args()
    t0 = time.time()
    if a.pool == "all":
        _d.TICKER_SETS["all"] = list(dict.fromkeys(_d.TICKER_SETS["tw500"] + _d.TICKER_SETS["elec_all"]))
    fp = os.path.join(DATA, f"samples_{a.pool}.parquet")
    panel = pd.read_parquet(fp)
    panel = panel[[c for c in panel.columns if not c.startswith("c_")]]
    keep = panel.index
    data = load_pool(a.pool, "2016-01-01", "2026-09-11")
    parts = []
    for i, (tk, df) in enumerate(data.items()):
        idx = keep[keep.get_level_values("ticker") == tk]
        if len(idx) == 0:
            continue
        f, _ = single_stock_features(df)
        f = f.reindex(idx.get_level_values("date")).astype(np.float32)
        f.index = idx
        parts.append(f)
        if i % 100 == 0:
            print(f"  {i}/{len(data)} {tk} ({time.time() - t0:.0f}s)", flush=True)
    feat = pd.concat(parts).add_prefix("c_")
    panel = panel.join(feat, how="left")
    c_cols = list(feat.columns)
    panel = panel[panel[c_cols].isna().mean(axis=1) < 0.3]
    panel.to_parquet(fp)
    mp = os.path.join(DATA, f"samples_{a.pool}_meta.json")
    meta = json.load(open(mp, encoding="utf-8"))
    meta["rows"] = len(panel); meta["pos_rate"] = float(panel["y"].mean()); meta["n_pos"] = int(panel["y"].sum())
    meta["cols"]["C"] = [c for c in panel.columns if c.startswith(("b_", "m_", "c_"))]
    meta["note_C"] = "單股指標,無橫斷面 cs_/mkt_ 欄"
    json.dump(meta, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[SAVED] {fp}  列 {len(panel):,}  正例 {meta['pos_rate']*100:.2f}%  C 欄 {len(meta['cols']['C'])}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
