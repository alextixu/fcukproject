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


SEED = 42
TRAIN_YEARS = 4                       # 每年 1 月重訓:用前 4 年
HOLD = 5                              # 答案要 t+5 才知道;研究回測規則 t+1 開盤買、t+5 收盤賣
COST_PCT = 0.585                      # 買 0.1425% + 賣 0.1425% + 稅 0.3%
TOP_N = 3                             # 推薦清單前 N 檔(同回測)
MIN_MOVE, MOVE_FROM = 0.725, "2020-01-01"   # 低波動門檻(同 mainline)
MIN_BARS = 16                         # 10 日均量 + 6 根 K
CHART_BARS = 60                       # 個股頁 K 線根數
HISTORY_START = "2016-01-01"
METHODS = ("main", "stack")
METHOD_NAMES = {"main": "① 主軸", "stack": "② Stacking"}
KIND = {"low": "低點", "high": "高點", "none": "非極值"}
