"""股票分類:池內 / 池外 / 低波動 / 不支援。

- 支援範圍:上市(TWSE)普通股,代號 4 位數字、不是 0 開頭。ETF、上櫃、興櫃、特別股、存託憑證都不支援。
  名稱與市場別來自 backtest/ncku/backtest/stock_api/stock_symbol_map.json。
- 池內:訓練用的股票池(設定值 config.POOL,預設 TW100;剔除低波動股後 2026 年為 73 檔,存在模型檔裡)。
- 低波動:2020-01 起每日收盤漲跌幅(絕對值)中位數 < 0.725%(同 mainline.low_vol),判斷不適用。
- 池外:其餘支援的股票,判斷照算,但沒有驗證過。
"""
import json
import os
import re
from functools import lru_cache

import pandas as pd

from . import config as C

POOL, OUT, LOWVOL, NOSUP, NODATA = "pool", "out", "lowvol", "nosup", "nodata"
STATUS_NAMES = {POOL: "池內", OUT: "池外", LOWVOL: "低波動", NOSUP: "不支援", NODATA: "資料不足"}
MARKET_NAMES = {"TWSE": "上市", "OTC": "上櫃", "ESB": "興櫃", "ETF": "ETF"}
_CODE = re.compile(r"[1-9]\d{3}")


@lru_cache(maxsize=1)
def symbols():
    with open(C.SYMBOLS, encoding="utf-8") as f:
        return json.load(f)


def code_of(ticker):
    return ticker.split(".")[0]


def ticker_of(code):
    return f"{code}.TW"


def name_of(code):
    return symbols().get(code, {}).get("name", code)


def supported(code):
    """上市普通股才支援。"""
    info = symbols().get(code)
    return bool(info) and info["type"] == "TWSE" and bool(_CODE.fullmatch(code))


def unsupported_reason(code):
    info = symbols().get(code)
    if not info:
        return "查無此代號"
    if info["type"] == "ETF":
        return "ETF 不支援:成分與走勢特性和個股不同,模型沒有在 ETF 上測試過"
    if info["type"] in ("OTC", "ESB"):
        return f"{MARKET_NAMES[info['type']]}股票目前不支援,第一版只支援上市普通股"
    if not _CODE.fullmatch(code):
        return "特別股、存託憑證等非普通股不支援"
    return ""


def all_supported():
    return sorted(c for c in symbols() if supported(c))


def universe(kind="all"):
    """每日要計算的股票代號(.TW)。all = 全部上市普通股;tw200 = 研究用 TW200 清單裡的上市普通股。"""
    if kind == "tw200":
        from data_loader import TICKER_SETS  # noqa: E402  (feasibility 已把 chartgcn/core 加進 sys.path)
        return [t for t in TICKER_SETS["tw200"] if supported(code_of(t))]
    return [ticker_of(c) for c in all_supported()]


def daily_move(df, upto=None):
    """2020-01 起(到 upto 為止)每日收盤漲跌幅絕對值的中位數(%);同 mainline.daily_move。"""
    import mainline as ML
    if upto is not None:
        df = df.loc[:pd.Timestamp(upto)]
    return ML.daily_move(df)


def classify(code, df, pool, upto=None):
    """回傳 (分類, 每日漲跌幅中位數)。pool 為池內代號(.TW)的集合。"""
    if not supported(code):
        return NOSUP, None
    if df is None or len(df) < C.MIN_BARS:
        return NODATA, None
    move = daily_move(df, upto)
    if ticker_of(code) in pool:
        return POOL, move
    if not move == move or move < C.MIN_MOVE:                                # NaN(2020 年後資料太少)也當低波動
        return LOWVOL, move
    return OUT, move


def pool_for_year(year, store=None, pool=None):
    """year 年使用的股票池(.TW 代號)。pool 預設為設定值 config.POOL。
    2026 年且研究結果檔有這個股票池:直接用結果檔記錄的清單(TW100 73 檔、TW200 168 檔、台灣50 34 檔),和研究完全相同;
    其他情況:TICKER_SETS[pool] 有資料的股票,用到前一年底的資料剔除低波動股(同 mainline.load_data 的規則)。"""
    pool = pool or C.POOL
    if year == 2026 and pool in C.RESEARCH_POOL_FILES:
        with open(os.path.join(C.RESULTS, C.RESEARCH_POOL_FILES[pool]), encoding="utf-8") as f:
            return sorted(json.load(f)["pool"])
    import mainline as ML
    from data_loader import TICKER_SETS  # noqa: E402
    from .datasource import PriceStore
    store = store or PriceStore()
    data = store.load_many(TICKER_SETS[pool], end=f"{year - 1}-12-31")
    data = {tk: df for tk, df in data.items() if len(df) >= 250}
    drop = set(ML.low_vol(data))
    return sorted(tk for tk in data if tk not in drop)
