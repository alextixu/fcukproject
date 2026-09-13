"""專題共用路徑(2026-09-12 重整後)。所有方法與回測腳本從這裡取資料位置,不再各自寫死。

用法: sys.path.insert(0, <專題根目錄>); from common.paths import CACHE, ROOT, ...
環境變數可覆蓋:TW_CACHE_DIR(還原價)、FINMIND_DIR(籌碼)、NCKU_SRC(official | yf_fw | yf_hist)
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMON = os.path.join(ROOT, "common")
CACHE = os.path.join(COMMON, "cache")

YF_CACHE = os.path.join(CACHE, "yf")            # yfinance 還原價 2016 ~ 2024(原 chartgcn/cache)
YF_2026_CACHE = os.path.join(CACHE, "yf_2026")  # yfinance 還原價到 2026-09(原 chartgcn/cache_2026)
OFFICIAL = os.path.join(CACHE, "official")      # 證交所官方日資料 2025-10 起(原 ncku/tmp/official)
YF_HIST = os.path.join(CACHE, "yf_hist")        # 還原價轉框架格式 2020-09 起(原 ncku/tmp/yf_hist)
YF_FW = os.path.join(CACHE, "yf_fw")            # 還原價轉框架格式 2025-10 起(原 ncku/tmp/yf)
KLINE_RAW = os.path.join(CACHE, "kline_raw")    # KLINE 用 yfinance 未還原 + 還原(原 backtest_2026/data/kline_raw)
FINMIND = os.path.join(CACHE, "finmind")        # FinMind 籌碼 tw500(原 xgb_ta_pipeline/data/finmind)
FINMIND_2026 = os.path.join(CACHE, "finmind_2026")
FEATURES = os.path.join(CACHE, "features")      # XGB 特徵面板 features_<pool>_<start>_<end>.parquet

METHOD_XGB = os.path.join(ROOT, "method_xgb")
METHOD_KLINE = os.path.join(ROOT, "method_kline")
METHOD_CHARTGCN = os.path.join(ROOT, "method_chartgcn")
METHOD_TOMT = os.path.join(ROOT, "method_tomt")
XGB_SRC = os.path.join(METHOD_XGB, "src")
XGB_EXP = os.path.join(METHOD_XGB, "experiments")
CHARTGCN_CORE = os.path.join(METHOD_CHARTGCN, "core")   # TICKER_SETS 目前仍在這裡的 data_loader.py

BACKTEST = os.path.join(ROOT, "backtest")
NCKU = os.path.join(BACKTEST, "ncku")
RESULTS = os.path.join(BACKTEST, "results")

NCKU_SRC_MAP = {"official": OFFICIAL, "yf": YF_FW, "yf_fw": YF_FW, "yf_hist": YF_HIST}


def ncku_src():
    """NCKU_SRC 環境變數 → 框架格式資料夾。"""
    return NCKU_SRC_MAP[os.environ.get("NCKU_SRC", "official")]
