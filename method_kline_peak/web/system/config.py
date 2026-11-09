"""網頁系統的路徑與常數。研究程式碼(mainline / walkforward / stacking)直接 import,不複製。"""
import os
import sys

WEB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # method_kline_peak/web
KP = os.path.dirname(WEB)                                              # method_kline_peak
ROOT = os.path.dirname(KP)
for p in (ROOT, KP):
    if p not in sys.path:
        sys.path.insert(0, p)

from common import paths as P  # noqa: E402

os.environ.setdefault("TW_CACHE_DIR", P.YF_2026_CACHE)                # 研究程式碼的快取(只讀)

SITE = os.path.join(WEB, "site")                                       # 靜態前端
DATA = os.environ.get("KPWEB_DATA") or os.path.join(WEB, "data")       # 存檔(判斷、對答案、模型、K 線快取)
SITE_DATA = os.path.join(SITE, "data")                                 # 前端讀的 JSON(每次批次重寫)
RESULTS = os.path.join(KP, "results")
SYMBOLS = os.path.join(ROOT, "backtest", "ncku", "backtest", "stock_api", "stock_symbol_map.json")


def data_dir(*parts):
    return os.path.join(DATA, *parts)


# ── 股票池與訓練門檻:設定值(環境變數或 run.py 的 --pool / --train-min-amp),改了不用改程式 ──
# 每組設定的存檔(判斷、答案、模型)放在 data/<設定名稱>/ 底下,互不混用;K 線快取共用 data/prices/
# 2026-11-09 使用者決定:模型用研究版 TW200(剔除低波動股)訓練;推薦範圍是台灣 50(50 檔全部給判斷,低波動股也照樣出判斷)
POOL = os.environ.get("KPWEB_POOL", "tw200")                           # 訓練用股票池:data_loader.TICKER_SETS 的名稱,再剔除低波動股
TRAIN_MIN_AMP = float(os.environ.get("KPWEB_TRAIN_MIN_AMP", "0"))       # 訓練門檻(%):同 walkforward.relabel,對答案仍用原本的標籤
# 研究結果檔裡記錄的股票池清單:2026 年直接用這份,和研究完全相同
RESEARCH_POOL_FILES = {"tw100": "backtest_long_only_tw100.json", "tw200": "backtest_long_only_tw200.json",
                       "tw50": "backtest_long_only.json"}
POOL_LABELS = {"tw50": "台灣 50", "tw100": "TW100", "tw200": "TW200", "tw500": "TW500"}
RECOMMEND = os.environ.get("KPWEB_RECOMMEND", "tw50")                   # 推薦範圍:今日判斷、成績追蹤只看這些股票(不剔除低波動股)


def set_profile(pool=None, train_min_amp=None):
    global POOL, TRAIN_MIN_AMP
    if pool is not None:
        POOL = pool
    if train_min_amp is not None:
        TRAIN_MIN_AMP = float(train_min_amp)


def profile():
    """目前這組設定的名稱,例:tw100、tw200_amp3。"""
    return POOL + (f"_amp{TRAIN_MIN_AMP:g}" if TRAIN_MIN_AMP else "")


def profile_dir(*parts):
    return data_dir(profile(), *parts)


def profile_info(n_pool=None):
    return {"name": profile(), "pool": POOL, "pool_label": POOL_LABELS.get(POOL, POOL.upper()),
            "recommend": RECOMMEND, "recommend_label": POOL_LABELS.get(RECOMMEND, RECOMMEND.upper()),
            "n_pool": n_pool, "train_min_amp": TRAIN_MIN_AMP}


SEED = 42
TRAIN_YEARS = 4                       # 每年 1 月重訓:用前 4 年
HOLD = 5                              # 答案要 t+5 才知道;研究回測規則 t+1 開盤買、t+5 收盤賣
COST_PCT = 0.585                      # 買 0.1425% + 賣 0.1425% + 稅 0.3%
TOP_N = 3                             # 推薦清單每組先列前 N 檔
MIN_MOVE, MOVE_FROM = 0.725, "2020-01-01"   # 低波動門檻(同 mainline)
MIN_BARS = 16                         # 10 日均量 + 6 根 K
CHART_BARS = 60                       # 個股頁 K 線根數
HISTORY_START = "2016-01-01"
# 2026-11-09 使用者決定:Stacking 是最終版,主軸完全拿掉(模型、存檔、網頁都只有 Stacking)
METHODS = ("stack",)
METHOD_NAMES = {"stack": "Stacking"}
LEVEL_METHODS = ("stack",)                       # 顯示信心等級(高 / 中 / 低)的方法
DEFAULT_METHOD = "stack"
KIND = {"low": "低點", "high": "高點", "none": "非極值"}
