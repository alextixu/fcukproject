"""重建 method_xgb 的特徵面板 common/cache/features/features_<pool>_2016-01-01_2026-09-11.parquet
(不進 git;build_dataset.py 的輸入 C 靠它接 240 個技術指標 + 橫斷面 cs_/mkt_ 欄)。
只適合 tw50 / tw200 這種 60 萬列以下的池(大池 method_xgb 走 lowmem memmap,這裡不處理;
大池請改用 add_ta.py 逐檔補單股指標)。
用法:python build_feature_panel.py --pool tw50   (tw50 約 1 分鐘、tw200 約 5 分鐘)
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from common import paths as P  # noqa: E402
os.environ.setdefault("TW_CACHE_DIR", P.YF_2026_CACHE)
sys.path.insert(0, P.XGB_SRC)
from run_pipeline import get_panel  # noqa: E402

START, END = "2016-01-01", "2026-09-11"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()
    os.makedirs(P.FEATURES, exist_ok=True)
    t0 = time.time()
    cfg = {"pool": a.pool, "start": START, "end": END, "train_end": "2022-12-31"}
    panel, fam = get_panel(cfg, rebuild=a.rebuild)
    if cfg.get("_strided"):
        sys.exit(f"[ERR] {a.pool} 走了 lowmem 路徑,沒有寫 parquet 面板;大池請用 add_ta.py --pool {a.pool}")
    print(f"[OK] {a.pool} 面板 {panel.shape},特徵 {len(fam)} 欄 ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
