"""每日批次與回放。

每日批次(run_daily)
  1. 更新 K 線(online=False 時只用快取)
  2. 判斷基準日 = 股票池最後一個有資料的交易日;檢查池內股票是否都有這天的資料
  3. 這天還沒有存檔 → 兩個方法對所有計算的股票做判斷,存檔(之後不重算);已有存檔 → 不動
  4. 已滿 5 個交易日、還沒對答案的存檔 → 對答案並存檔
  5. 產生前端的 JSON
回放(run_replay)
  上線前的日子用同一個正式模型逐日產生存檔(source = replay),讓成績追蹤有歷史可看。
  每一天只用到那天為止的 K 線(特徵本來就只用 t−5 ~ t),和每天收盤後跑批次的結果相同。
"""
import time

import numpy as np
import pandas as pd

from . import config as C, model as MD, store as ST, universe as U
from .datasource import PriceStore
from .features import live_frame, labels, grade_from

TAIL = 80                      # 每日判斷只需要最後幾十根 K 線(10 日均量 + 6 根 K + 規則看前 5 天)


def _calendar(data, pool):
    idx = [data[tk].index for tk in pool if tk in data]
    return pd.DatetimeIndex(sorted(set().union(*idx))) if idx else pd.DatetimeIndex([])


def _row(code, status, move, df, date, pred=None, m=None):
    r = {"code": code, "status": status}
    if move is not None and move == move:
        r["move"] = round(move, 3)
    if df is not None and date in df.index:
        i = df.index.get_loc(date)
        r["close"] = round(float(df["close"].iloc[i]), 4)
        if i > 0:
            r["chg_pct"] = round(float(df["close"].iloc[i] / df["close"].iloc[i - 1] - 1) * 100, 3)
    if pred is not None:
        def f(x, n=4):
            return None if x is None or not np.isfinite(x) else round(float(x), n)
        r["main"] = {"pred": pred.main_pred, "score": f(pred.main_score), "s_high": f(pred.main_s_high), "s_low": f(pred.main_s_low),
                     "level": MD.level(pred.main_score, m["cuts"]["main"][pred.main_pred]) if pred.main_pred != "none" else None}
        r["stack"] = {"pred": pred.stack_pred, "score": f(pred.stack_score),
                      "p_low": f(pred.stack_p_low), "p_none": f(pred.stack_p_none), "p_high": f(pred.stack_p_high),
                      "level": MD.level(pred.stack_score, m["cuts"]["stack"][pred.stack_pred]) if pred.stack_pred != "none" else None}
    return r


def judge_day(date, data, m, codes, moves=None, source="daily", check=None, frames=None):
    """對 date 這天做判斷,回傳存檔用的 dict(不寫檔)。data 只能含 date(含)以前的資料。
    frames(回放用):{代號: live_frame 依日期索引},事先對整段資料算好;特徵只用 t−5 ~ t,結果和逐日計算相同。"""
    date = pd.Timestamp(date)
    pool = set(m["pool"])
    rows, feats, keys = [], [], []
    for code in codes:
        tk = U.ticker_of(code)
        df = data.get(tk)
        if df is not None:
            df = df.loc[:date]
        move = moves.get(code) if moves is not None else None
        status, mv = U.classify(code, df, pool, upto=date) if moves is None else _status(code, df, pool, move)
        if status in (U.NOSUP, U.NODATA):
            rows.append(_row(code, status, mv, None, date))
            continue
        if date not in df.index or df["volume"].loc[date] <= 0:
            rows.append(_row(code, "halted", mv, df, date))
            continue
        if frames is not None:
            fa = frames.get(tk)
            fr = fa.loc[[date]].reset_index() if fa is not None and date in fa.index else pd.DataFrame()
        else:
            fr = live_frame(tk, df.tail(TAIL))
        if not len(fr) or fr["date"].iloc[-1] != date:
            rows.append(_row(code, U.NODATA, mv, df, date))
            continue
        feats.append(fr.iloc[[-1]])
        keys.append((len(rows), code, status, mv, df))
        rows.append(None)
    if feats:
        pr = MD.predict(m, pd.concat(feats, ignore_index=True))
        for (i, code, status, mv, df), p in zip(keys, pr.itertuples(index=False)):
            rows[i] = _row(code, status, mv, df, date, p, m)
    return {"date": str(date.date()), "created": time.strftime("%Y-%m-%d %H:%M:%S"), "source": source,
            "model": MD.info(m), "check": check or {}, "rows": rows}


def _status(code, df, pool, move):
    if not U.supported(code):
        return U.NOSUP, None
    if df is None or len(df) < C.MIN_BARS:
        return U.NODATA, None
    if U.ticker_of(code) in pool:
        return U.POOL, move
    if move is None or move != move or move < C.MIN_MOVE:
        return U.LOWVOL, move
    return U.OUT, move


def grade_pending(data, cal, log=print):
    """已滿 5 個交易日、還沒對答案的存檔 → 對答案並存檔。回傳對了幾天。
    每檔的答案表只算一次(t 的標籤只看 t−5 ~ t+5,用較長的資料算結果相同)。"""
    todo = []
    for d in ST.list_days():
        if ST.has_grade(d):
            continue
        ts = pd.Timestamp(d)
        if (cal > ts).sum() >= C.HOLD:
            todo.append(ts)
    if not todo:
        return 0
    cache = {}

    def answers(code):
        if code not in cache:
            df = data.get(U.ticker_of(code))
            cache[code] = None if df is None else labels(df)
        return cache[code]
    for ts in todo:
        day = ST.read_day(ts)
        out = {}
        for r in day["rows"]:
            if r.get("main"):
                out[r["code"]] = grade_from(answers(r["code"]), ts)
        ST.write_grade(ts, out)
    log(f"對答案:{len(todo)} 天")
    return len(todo)


def check_data(data, pool, cal, today=None, online=True):
    """資料檢查:池內股票最後一天是否都是基準日;今天收盤後(18:00)資料還沒到 → stale。"""
    asof = cal[-1] if len(cal) else None
    missing = sorted(tk for tk in pool if tk not in data or data[tk].index[-1] < asof)
    now = pd.Timestamp(today) if today is not None else pd.Timestamp.now(tz="Asia/Taipei").tz_localize(None)
    stale = bool(online and asof is not None and now.weekday() < 5 and now.hour >= 18 and asof.normalize() < now.normalize())
    return {"asof": str(asof.date()) if asof is not None else None, "missing_pool": [U.code_of(t) for t in missing],
            "stale": stale, "online": online, "checked": str(now)[:16]}


def run_daily(asof=None, online=True, kind="all", store=None, log=print, publish=True):
    from . import publish as PB
    t0 = time.time()
    store = store or PriceStore()
    today = pd.Timestamp(asof) if asof else pd.Timestamp.now(tz="Asia/Taipei").tz_localize(None).normalize()
    m = MD.ensure(today.year, store, log)
    codes = [U.code_of(t) for t in U.universe(kind)]
    tickers = sorted(set(U.ticker_of(c) for c in codes) | set(m["pool"]))
    rep = {"online": online}
    if online:
        r = store.update(tickers, today)
        rep = {"online": True, **r.as_dict()}
        log(f"更新 K 線:{len(r.updated)} 檔有新資料、{len(r.refreshed)} 檔重抓、{len(r.failed)} 檔失敗"
            + (f"({r.error})" if r.error else ""))
    data = store.load_many(tickers, end=today)
    cal = _calendar(data, m["pool"])
    check = check_data(data, m["pool"], cal, None if asof is None else today, online) | {"update": rep}
    date = cal[-1]
    if date.year != m["year"]:
        m = MD.ensure(date.year, store, log)
    if ST.has_day(date):
        log(f"{date.date()} 已有存檔,不重算")
    else:
        ST.write_day(judge_day(date, data, m, codes, check=check))
        log(f"{date.date()} 判斷完成並存檔({len(codes)} 檔)")
    grade_pending(data, cal, log)
    if publish:
        PB.publish(data, cal, check, log=log)
    log(f"每日批次完成  ({time.time() - t0:.0f}s)")
    return date


def _moves_by_day(data, codes, dates):
    """每檔在每一天的「2020-01 起每日漲跌幅中位數」(只用到那天)。回傳 {日期: {代號: 中位數}}。"""
    from feasibility import clean  # noqa: E402
    out = {d: {} for d in dates}
    for code in codes:
        df = data.get(U.ticker_of(code))
        if df is None:
            continue
        r = clean(df)["close"].loc[C.MOVE_FROM:].pct_change().abs() * 100
        r = r.dropna()
        if not len(r):
            continue
        vals, idx = r.to_numpy(), r.index
        for d in dates:
            k = idx.searchsorted(d, side="right")
            if k:
                out[d][code] = float(np.median(vals[:k]))
    return out


def run_replay(start, end=None, kind="all", store=None, log=print, publish=True):
    """start ~ end 每個交易日產生回放存檔(已存在的日子跳過)。"""
    from . import publish as PB
    t0 = time.time()
    store = store or PriceStore()
    end = pd.Timestamp(end) if end else None
    codes = [U.code_of(t) for t in U.universe(kind)]
    m0 = MD.ensure(pd.Timestamp(start).year, store, log)
    tickers = sorted(set(U.ticker_of(c) for c in codes) | set(m0["pool"]))
    data = store.load_many(tickers, end=end)
    cal = _calendar(data, m0["pool"])
    days = [d for d in cal if d >= pd.Timestamp(start) and not ST.has_day(d)]
    log(f"回放 {len(days)} 天({days[0].date() if days else '-'} ~ {days[-1].date() if days else '-'}),{len(codes)} 檔")
    moves = _moves_by_day(data, codes, days)
    frames = {}
    for tk, df in data.items():
        fr = live_frame(tk, df)
        if len(fr):
            frames[tk] = fr.set_index("date", drop=False).rename_axis(None)
    log(f"  特徵完成  ({time.time() - t0:.0f}s)")
    pool_cache = {}
    for i, d in enumerate(days):
        m = pool_cache.get(d.year) or pool_cache.setdefault(d.year, MD.ensure(d.year, store, log))
        ST.write_day(judge_day(d, data, m, codes, moves=moves[d], source="replay",
                               check={"asof": str(d.date()), "replay": True}, frames=frames))
        if (i + 1) % 20 == 0:
            log(f"  {i + 1}/{len(days)}  ({time.time() - t0:.0f}s)")
    grade_pending(data, cal, log)
    if publish:
        PB.publish(data, cal, check_data(data, m0["pool"], cal, cal[-1], online=False) | {"update": {"online": False}}, log=log)
    log(f"回放完成  ({time.time() - t0:.0f}s)")
