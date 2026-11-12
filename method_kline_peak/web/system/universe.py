"""股票分類:池內 / 池外 / 低波動 / 資料不足 / 不支援。

- 計算範圍:上市(TWSE)、上櫃(OTC)普通股(代號 4 位數字、不是 0 開頭)與 ETF,全部用同一個 Stacking 模型判斷。
  Yahoo 代號:上市 .TW、上櫃 .TWO;ETF 有上市也有上櫃,第一次下載時兩種都試,結果記在 data/tickers.json。
- 興櫃不計算,顯示「資料不足」;特別股、存託憑證等非普通股不支援。
  名稱與市場別來自 backtest/ncku/backtest/stock_api/stock_symbol_map.json。
- 推薦範圍(status = pool):config.RECOMMEND,預設台灣 50。50 檔全部給判斷,低波動股也照樣出判斷。
  訓練用的股票池是另一份(config.POOL,預設 TW200 剔除低波動股,存在模型檔裡)。
- 低波動:推薦範圍以外、2020-01 起每日收盤漲跌幅(絕對值)中位數 < 0.725%(同 mainline.low_vol),判斷不適用。
- 池外:推薦範圍以外的其餘上市普通股,判斷照算,畫面加提示。
"""
import json
import os
import re
from functools import lru_cache

import pandas as pd

from . import config as C

POOL, OUT, LOWVOL, NOSUP, NODATA = "pool", "out", "lowvol", "nosup", "nodata"
STATUS_NAMES = {POOL: "台灣 50", OUT: "池外", LOWVOL: "低波動", NOSUP: "不支援", NODATA: "資料不足"}
MARKET_NAMES = {"TWSE": "上市", "OTC": "上櫃", "ESB": "興櫃", "ETF": "ETF"}
_CODE = re.compile(r"[1-9]\d{3}")


@lru_cache(maxsize=1)
def symbols():
    with open(C.SYMBOLS, encoding="utf-8") as f:
        return json.load(f)


def code_of(ticker):
    return ticker.split(".")[0]


def ticker_map_path():
    return C.data_dir("tickers.json")


@lru_cache(maxsize=1)
def ticker_map():
    """ETF 的 Yahoo 代號(.TW 或 .TWO;None = Yahoo 兩種都沒有資料)。由 datasource.resolve_etf_tickers 寫入。"""
    p = ticker_map_path()
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def ticker_of(code):
    """Yahoo 代號:上市 .TW、上櫃 .TWO;ETF 照 data/tickers.json(還沒查過的先當 .TW)。"""
    info = symbols().get(code, {})
    if info.get("type") == "OTC":
        return f"{code}.TWO"
    if info.get("type") == "ETF":
        return ticker_map().get(code) or f"{code}.TW"
    return f"{code}.TW"


def market_of(code):
    return symbols().get(code, {}).get("type")


def name_of(code):
    return symbols().get(code, {}).get("name", code)


def supported(code):
    """會計算判斷的股票:上市、上櫃普通股與 ETF(ETF 若 Yahoo 兩種代號都沒有資料就不算)。"""
    info = symbols().get(code)
    if not info:
        return False
    if info["type"] == "ETF":
        return ticker_map().get(code, "") is not None
    return info["type"] in ("TWSE", "OTC") and bool(_CODE.fullmatch(code))


def unsupported_reason(code):
    info = symbols().get(code)
    if not info:
        return "查無此代號"
    if not _CODE.fullmatch(code) and info["type"] != "ETF":
        return "特別股、存託憑證等非普通股不支援"
    return ""


def nodata_reason(code):
    """不計算、但顯示「資料不足」的原因(興櫃、Yahoo 沒有資料的 ETF)。"""
    info = symbols().get(code) or {}
    if info.get("type") == "ESB":
        return "興櫃股票不在計算範圍"
    if info.get("type") == "ETF" and ticker_map().get(code, "") is None:
        return "Yahoo 沒有這檔的日 K 資料"
    return ""


def all_supported():
    return sorted(c for c in symbols() if supported(c))


def recommend_list():
    """推薦範圍的股票代號(.TW),順序照 TICKER_SETS。"""
    from data_loader import TICKER_SETS  # noqa: E402
    return [t for t in TICKER_SETS[C.RECOMMEND] if supported(code_of(t))]


def universe(kind="all"):
    """每日要計算的股票代號。all = 全部上市、上櫃普通股與 ETF;tw200 = 研究用 TW200 清單裡的上市普通股。"""
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
    """回傳 (分類, 每日漲跌幅中位數)。pool 為推薦範圍代號(.TW)的集合;推薦範圍內的低波動股仍算 pool。"""
    if not supported(code):
        return (NODATA if nodata_reason(code) else NOSUP), None
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
    2026 年(含)以前且研究結果檔有這個股票池:直接用結果檔記錄的清單(TW100、TW200、台灣50 剔除低波動股),和研究完全相同
    (研究 2024–2026 的 walk-forward 每年都用同一份清單);
    2027 年起:TICKER_SETS[pool] 有資料的股票,用到前一年底的資料剔除低波動股(同 mainline.load_data 的規則)。
    順序照 TICKER_SETS[pool](同 mainline.load_data):訓練資料的列順序會影響 AE / OC-SVM 的結果,順序不同就無法和研究完全一致。"""
    import mainline as ML
    from data_loader import TICKER_SETS  # noqa: E402
    pool = pool or C.POOL
    if year <= 2026 and pool in C.RESEARCH_POOL_FILES:
        with open(os.path.join(C.RESULTS, C.RESEARCH_POOL_FILES[pool]), encoding="utf-8") as f:
            keep = set(json.load(f)["pool"])
        return [tk for tk in TICKER_SETS[pool] if tk in keep]
    from .datasource import PriceStore
    store = store or PriceStore()
    data = store.load_many(TICKER_SETS[pool], end=f"{year - 1}-12-31")
    data = {tk: df for tk, df in data.items() if len(df) >= 250}
    drop = set(ML.low_vol(data))
    return [tk for tk in data if tk not in drop]
