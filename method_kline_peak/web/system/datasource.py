"""K 線快取與每日更新。

- 快取放在 data/prices/<代號>.parquet(還原價,欄位 open/high/low/close/volume)。
  第一次用到某檔時,從研究用的快取(common/cache/yf_2026,只讀)複製過來,研究快取不會被改動。
- update():只下載最後一天之後的資料(往前多抓 OVERLAP 天核對)。
  重疊區間的收盤價差超過 ADJ_TOL,代表除權息後還原價整段重算了,就重抓這檔的完整歷史。
- 下載函式可以替換(測試用假的下載函式;沒有網路時 update 回報失敗,系統照樣用快取跑)。
- 畫面用的實際成交價(Yahoo 未還原價)另外放在 data/prices_raw/,用同一個類別、換成 yf_download_raw;只用來顯示,模型不讀。
- ETF 有上市(.TW)也有上櫃(.TWO):resolve_etf_tickers 第一次兩種都試,結果寫在 data/tickers.json。
"""
import json
import time
import os
from dataclasses import dataclass, field

import pandas as pd

from . import config as C

COLS = ["open", "high", "low", "close", "volume"]
OVERLAP = 10          # 往前多抓幾天核對
ADJ_TOL = 0.002       # 重疊區間收盤價相對差 > 0.2% → 還原價變了,重抓完整歷史
BATCH = 40            # yfinance 一次下載幾檔(太多容易被 Yahoo 限流)


def _norm(df):
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=COLS)
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [str(c).lower() for c in df.columns]
    df = df[COLS].dropna()
    df = df[df["close"] > 0]
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df.index.name = "Date"
    return df[~df.index.duplicated(keep="last")].sort_index().astype(float)


THROTTLE = ("ratelimit", "too many requests", "invalid crumb", "unauthorized", "timed out", "timeout", "connection")


def _throttled(msg):
    m = str(msg).lower()
    return any(k in m for k in THROTTLE)


def yf_download(tickers, start, end, adjust=True, rounds=5):
    """預設下載函式:yfinance 還原價(adjust=False 為未還原的實際成交價)。回傳 {代號: DataFrame}(抓不到的不放)。end 不含。
    Yahoo 限流(Too Many Requests、Invalid Crumb、逾時)的代號會等一下再重抓,最多 rounds 輪;
    只有 Yahoo 明確回「沒有資料」的代號才當作沒資料,不會因為限流被當成沒資料。"""
    import yfinance as yf
    import yfinance.shared as yfs
    out, todo = {}, list(tickers)
    for k in range(rounds):
        if k:
            time.sleep(min(90, 10 * 2 ** (k - 1)))
        yfs._ERRORS.clear()
        try:
            raw = yf.download(todo, start=start, end=end, auto_adjust=adjust, progress=False,
                              group_by="ticker", threads=8)
        except Exception as e:                                            # noqa: BLE001
            if k == rounds - 1:
                raise
            if not _throttled(e):
                time.sleep(5)
            continue
        errs = dict(yfs._ERRORS)
        retry = []
        for tk in todo:
            try:
                df = raw[tk] if isinstance(raw.columns, pd.MultiIndex) else raw
            except KeyError:
                df = None
            df = _norm(df)
            if len(df):
                out[tk] = df
            elif _throttled(errs.get(tk, "")):
                retry.append(tk)
        if not retry:
            break
        todo = retry
    return out


def yf_download_raw(tickers, start, end):
    """實際成交價(未還原):畫面上的收盤、K 線用。"""
    return yf_download(tickers, start, end, adjust=False)


def resolve_etf_tickers(codes, today, downloader=yf_download, path=None):
    """ETF 的 Yahoo 代號:先試 .TW,沒資料再試 .TWO,兩種都沒有記 None。已經查過的不再查。回傳新查到幾檔。"""
    from . import universe as U
    path = path or U.ticker_map_path()
    known = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            known = json.load(f)
    todo = [c for c in codes if c not in known]
    if not todo:
        return 0
    start = str((pd.Timestamp(today) - pd.Timedelta(days=40)).date())
    end = str((pd.Timestamp(today) + pd.Timedelta(days=1)).date())
    left = list(todo)
    for suffix in (".TW", ".TWO"):
        for i in range(0, len(left), BATCH):
            part = left[i:i + BATCH]
            got = downloader([c + suffix for c in part], start, end)
            for c in part:
                if c + suffix in got and len(got[c + suffix]):
                    known[c] = c + suffix
        left = [c for c in left if c not in known]
    for c in left:
        known[c] = None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(known.items())), f, ensure_ascii=False, indent=0)
    U.ticker_map.cache_clear()
    return len(todo)


@dataclass
class UpdateReport:
    asked: int = 0
    updated: list = field(default_factory=list)       # 有新資料
    refreshed: list = field(default_factory=list)     # 還原價變了,重抓完整歷史
    unchanged: list = field(default_factory=list)     # 沒有新資料(休市或還沒更新)
    failed: list = field(default_factory=list)        # 下載失敗
    error: str = ""

    def as_dict(self):
        return {k: (len(v) if isinstance(v, list) else v) for k, v in self.__dict__.items()} | {
            "failed_tickers": self.failed[:50], "refreshed_tickers": self.refreshed[:50]}


class PriceStore:
    def __init__(self, root=None, seed_dir=None, downloader=yf_download, history_start=None):
        self.root = root or C.data_dir("prices")
        self.seed_dir = seed_dir if seed_dir is not None else C.P.YF_2026_CACHE
        self.download = downloader
        self.history_start = history_start or C.HISTORY_START
        self.pause = 1.0 if downloader in (yf_download, yf_download_raw) else 0.0   # 真的連 Yahoo 時每批之間停一下
        os.makedirs(self.root, exist_ok=True)

    def path(self, tk):
        return os.path.join(self.root, f"{tk}.parquet")

    def load(self, tk):
        """回傳這檔的完整 K 線;本地沒有就從研究快取複製;都沒有回傳 None。"""
        p = self.path(tk)
        if not os.path.exists(p) and self.seed_dir:
            src = os.path.join(self.seed_dir, f"{tk}.parquet")
            if os.path.exists(src):
                df = _norm(pd.read_parquet(src))
                if len(df):
                    df.to_parquet(p)
        if not os.path.exists(p):
            return None
        return _norm(pd.read_parquet(p))

    def load_many(self, tickers, end=None):
        """{代號: DataFrame},end(含)之後的資料切掉;沒有資料的不放。"""
        out = {}
        for tk in tickers:
            df = self.load(tk)
            if df is None or not len(df):
                continue
            if end is not None:
                df = df.loc[:pd.Timestamp(end)]
            if len(df):
                out[tk] = df
        return out

    def save(self, tk, df):
        tmp = self.path(tk) + ".tmp"                                        # 先寫暫存檔再換掉,讀的人不會讀到寫一半的檔
        _norm(df).to_parquet(tmp)
        os.replace(tmp, self.path(tk))

    def update(self, tickers, today):
        """把每檔更新到 today(含)。網路失敗不丟例外,記在報告裡。"""
        today = pd.Timestamp(today).normalize()
        rep = UpdateReport(asked=len(tickers))
        have = {tk: self.load(tk) for tk in tickers}
        need = [tk for tk, df in have.items() if df is None or not len(df) or df.index[-1] < today]
        rep.unchanged += [tk for tk in tickers if tk not in need]
        groups = {}
        for tk in need:                                                     # 依起始日分組下載
            df = have[tk]
            start = self.history_start if df is None or not len(df) else str((df.index[-1] - pd.Timedelta(days=OVERLAP * 2)).date())
            groups.setdefault(start, []).append(tk)
        end = str((today + pd.Timedelta(days=1)).date())
        full = []
        for start, tks in groups.items():
            for i in range(0, len(tks), BATCH):
                part = tks[i:i + BATCH]
                time.sleep(self.pause)
                try:
                    got = self.download(part, start, end)
                except Exception as e:                                      # noqa: BLE001  網路或 API 錯誤
                    rep.failed += part
                    rep.error = f"{type(e).__name__}: {e}"[:300]
                    continue
                for tk in part:
                    new = _norm(got.get(tk))
                    old = have[tk]
                    if not len(new):
                        (rep.failed if old is None else rep.unchanged).append(tk)
                        continue
                    if old is None or not len(old):
                        self.save(tk, new)
                        rep.updated.append(tk)
                        continue
                    common = old.index.intersection(new.index)
                    if len(common):
                        diff = (new.loc[common, "close"] / old.loc[common, "close"] - 1).abs().max()
                        if diff > ADJ_TOL:
                            full.append(tk)
                            continue
                    merged = pd.concat([old[old.index < new.index[0]], new])
                    if merged.index[-1] > old.index[-1]:
                        self.save(tk, merged)
                        rep.updated.append(tk)
                    else:
                        rep.unchanged.append(tk)
        for i in range(0, len(full), BATCH):                                # 還原價變了:重抓完整歷史
            part = full[i:i + BATCH]
            try:
                got = self.download(part, self.history_start, end)
            except Exception as e:                                          # noqa: BLE001
                rep.failed += part
                rep.error = f"{type(e).__name__}: {e}"[:300]
                continue
            for tk in part:
                new = _norm(got.get(tk))
                if len(new):
                    self.save(tk, new)
                    rep.refreshed.append(tk)
                else:
                    rep.failed.append(tk)
        return rep


def raw_store(root=None, downloader=yf_download_raw):
    """畫面用的實際成交價(Yahoo 未還原價)快取:data/prices_raw/,從 RAW_START 起。"""
    return PriceStore(root=root or C.data_dir("prices_raw"), seed_dir="", downloader=downloader, history_start=C.RAW_START)
