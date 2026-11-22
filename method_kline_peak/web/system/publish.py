"""產生前端讀的 JSON(site/data/,每次批次整批重寫;真正的紀錄在 data/<設定>/days、grades)。
判斷方法和 final 分支相同(規則候選 → AE + OC-SVM);網頁定位為「看盤輔助」,不放回測與報酬。
輸出沒有機率:每檔只有判斷(高點 / 低點 / 非極值)、是否為規則候選、OC-SVM 分數(不是機率;排序用)。

  meta.json        基準日、資料檢查、模型資訊
  today.json       今日判斷:推薦範圍(預設 = 訓練股票池,TW200 剔除低波動股)內判低點 / 判高點,依「沒破底 / 沒創高」天數分組、
                   組內依分數排序;同一檔同時有兩個方向的訊號時只列比較新的那個
  track.json       成績追蹤:每日前 3 檔(分數最高)對答案、命中率、池外命中率
  index.json       自動完成用的股票清單(代號、名稱、分類、市場別)
  research.json    研究結果:TW200 168 檔 2024–2026 的分類成績(直接讀 results/confusion_2024_2026_tw200.json,不重算)
  stocks/<代號前兩碼>.json  個股(每檔一筆):今天的判斷、還沒破底 / 沒創高的訊號、今年整年的 K 線、今年的判斷與答案、今年的對答案統計

畫面上的收盤、K 線、量用 Yahoo 未還原的實際成交價(data/prices_raw);抓不到的股票才用還原價並標示。
漲跌幅用還原價算(除權息當天和看盤軟體一樣是對參考價的漲跌)。
模型、判斷、對答案一律用 yfinance 還原價(和研究相同),顯示用的價格不影響任何判斷。
  findings.json    研究發現頁:找到率、高低點不判反、命中率約三成、多判的訊號很多、扣成本後不能直接當交易訊號
"""
import json
import os
import shutil
import time

import numpy as np
import pandas as pd

from . import config as C, signals as SG, store as ST, universe as U
from feasibility import clean  # noqa: E402

KINDS = ("low", "high")
MK = "主軸"                                   # 研究結果檔(final)裡的方法名稱
CM = "confusion_rows_true_cols_pred(漲,不漲不跌,跌)"
K_ZH = {"low": "低點", "high": "高點"}


def _w(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), default=_default)
    os.replace(tmp, path)


def _default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    raise TypeError(type(o))


def _clean_nan(x):
    if isinstance(x, dict):
        return {k: _clean_nan(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_clean_nan(v) for v in x]
    if isinstance(x, float) and not np.isfinite(x):
        return None
    return x


def _rate(hits, n):
    return {"hits": int(hits), "n": int(n), "pct": round(hits / n * 100, 1) if n else None}


def _public_row(r):
    """網頁用的單檔判斷(代號、分類、判斷、規則候選、分數)。回傳複本,存檔本身不被改動。"""
    return {k: (dict(v) if isinstance(v, dict) else v) for k, v in r.items()}


def _rj(name):
    with open(os.path.join(C.RESULTS, name), encoding="utf-8") as f:
        return json.load(f)


# ───────────────────────── 成績 ─────────────────────────
def top_picks(tab, kind, n=C.TOP_N):
    """每天推薦範圍內判 kind 的股票依分數取前 n 檔。"""
    t = tab[(tab.status == U.POOL) & (tab.pred == kind)]
    t = t.sort_values(["date", "score"], ascending=[True, False])
    return t.groupby("date", sort=True).head(n)


def track(tab):
    out = {"kinds": {}, "dates": {}}
    if not len(tab):
        return out
    graded_dates = sorted(tab.loc[tab.truth.notna(), "date"].unique())
    src = tab.groupby("date")["source"].first()
    live = src[src == "daily"]
    out["dates"] = {"first": tab.date.min(), "last": tab.date.max(), "n": int(tab.date.nunique()),
                    "graded_last": graded_dates[-1] if graded_dates else None, "n_graded": len(graded_dates),
                    "live_start": live.index.min() if len(live) else None}
    pool_g = tab[(tab.status == U.POOL) & tab.truth.notna()]
    year = str(tab.date.max())[:4]
    for kind in KINDS:
        picks = top_picks(tab, kind)
        gp = picks[picks.truth.notna()]
        gdates = sorted(gp.date.unique())

        def window(k):
            w = gp[gp.date.isin(gdates[-k:])]
            return _rate((w.truth == kind).sum(), len(w)) | {"days": len(gdates[-k:])}
        allsig = pool_g[pool_g.pred == kind]
        ytd = allsig[allsig.date.str.startswith(year)]
        series = []
        by_day = allsig.groupby("date").agg(h=("truth", lambda s: int((s == kind).sum())), n=("truth", "size"))
        by_day = by_day.reindex(graded_dates, fill_value=0)
        roll = by_day.rolling(60, min_periods=20).sum()
        for d, r in roll.iterrows():
            if r.n > 0 and np.isfinite(r.n):
                series.append([d, round(r.h / r.n * 100, 2), src.get(d, "daily")])
        daily = []
        for d in sorted(picks.date.unique())[-30:][::-1]:
            p = picks[picks.date == d]
            graded = p.truth.notna().all()
            daily.append({"date": d, "source": src.get(d), "picks": [
                {"code": r.code, "name": U.name_of(r.code), "score": r.score, "truth": r.truth} for _, r in p.iterrows()],
                "hits": int((p.truth == kind).sum()) if graded else None})
        outs = tab[(tab.status == U.OUT) & (tab.pred == kind) & tab.truth.notna()]
        out["kinds"][kind] = {
            "top_20": window(20), "top_60": window(60), "top_all": window(10 ** 6),
            "all_ytd": _rate((ytd.truth == kind).sum(), len(ytd)) | {"year": year},
            "all": _rate((allsig.truth == kind).sum(), len(allsig)),
            "base_rate": _rate((pool_g.truth == kind).sum(), len(pool_g)),
            "out_pool": _rate((outs.truth == kind).sum(), len(outs)),
            "series": series, "daily": daily}
    return out


# ───────────────────────── 研究結果(只讀既有結果檔,數字不手抄) ─────────────────────────
def _conf():
    """results/confusion_2024_2026_tw200.json:{年: 混淆矩陣 dict}(列 = 真實、欄 = 判斷,順序 低點、非極值、高點)。"""
    return {y: v[MK] for y, v in _rj("confusion_2024_2026_tw200.json").items()}


def research():
    """TW200 168 檔 2024–2026 的分類成績(final 的 results/confusion_2024_2026_tw200.json)。"""
    cls = []
    for y, x in _conf().items():
        cm = np.array(x[CM])
        cls.append({"year": y, "macro_f1": round(x["macro_f1"] * 100, 2),
                    "prec_low": round(x["precision"]["低點"] * 100, 1), "prec_high": round(x["precision"]["高點"] * 100, 1),
                    "rec_low": round(x["recall"]["低點"] * 100, 1), "rec_high": round(x["recall"]["高點"] * 100, 1),
                    "base_low": round(cm[0].sum() / cm.sum() * 100, 1), "base_high": round(cm[2].sum() / cm.sum() * 100, 1),
                    "n_days": int(cm.sum()), "cross": int(cm[0, 2] + cm[2, 0])})
    return {"classification": cls, "sources": ["method_kline_peak/results/confusion_2024_2026_tw200.json"]}


def findings():
    """研究發現頁(final 的結果檔):三年合計的找到率、±2 天找到率、命中率、判反次數、判的天數是真高低點的幾倍,
    以及只做多的交易組合扣成本後是否全部虧損(只取結論,不放報酬表)。"""
    conf = _conf()
    cm = sum(np.array(x[CM]) for x in conf.values())
    tot = {"low": (0, 0), "high": (0, 0)}
    for r in _rj("per_stock_mainline_2024_2026.json")["每檔"]["合計"].values():   # ±2 天找到率:逐檔加總(和 168 檔混淆矩陣一致)
        for kind in KINDS:
            x = r[K_ZH[kind]]
            n, f = tot[kind]
            tot[kind] = (n + x["真"], f + round(x["真"] * x["找到率_±2天"] / 100))
    ps = _rj("per_stock_mainline_2024_2026.json")
    st = _rj("backtest_strategies_2024_2025.json")
    nets = [v["扣成本"]["合計"]["total_return_pct"] for v in st["results"].values()]
    holds = [v["扣成本"]["合計"]["total_return_pct"] for v in st["baselines"].values()]
    i = {"low": 0, "high": 2}

    def pct(a, b):
        return round(a / b * 100, 1) if b else None
    return {"years": sorted(conf),
            "recall": {k: pct(cm[i[k], i[k]], cm[i[k]].sum()) for k in KINDS}
            | {f"{k}2": pct(tot[k][1], tot[k][0]) for k in KINDS},
            "precision": {k: pct(cm[i[k], i[k]], cm[:, i[k]].sum()) for k in KINDS}
            | {f"base_{k}": pct(cm[i[k]].sum(), cm.sum()) for k in KINDS},
            "by_year": {y: {"rec_low": round(x["recall"]["低點"] * 100, 1), "rec_high": round(x["recall"]["高點"] * 100, 1),
                            "prec_low": round(x["precision"]["低點"] * 100, 1), "prec_high": round(x["precision"]["高點"] * 100, 1)}
                        for y, x in conf.items()},
            "over": {k: round(cm[:, i[k]].sum() / cm[i[k]].sum(), 1) for k in KINDS},      # 判的天數 ÷ 真的天數
            "cross": int(cm[0, 2] + cm[2, 0]), "n_days": int(cm.sum()),
            "n_stocks": ps["n_stocks"],
            "trade": {"n": len(nets), "all_loss": all(x < 0 for x in nets), "below_hold": max(nets) < min(holds),
                      "period": st["period"], "cost_pct": st["cost_round_trip_pct"]},
            "sources": ["confusion_2024_2026_tw200.json", "per_stock_mainline_2024_2026.json", "backtest_strategies_2024_2025.json"]}


# ───────────────────────── 個股的訊號狀態 ─────────────────────────
def stock_active(g, df, asof):
    """一檔股票在 asof 那天「還沒破底 / 沒創高」的訊號。g = 這檔的存檔判斷(依日期索引),df = K 線。
    兩者都只用到 asof(含)為止,之後的資料不影響結果。回傳 (最近 60 天收盤, {low/high: 訊號})。"""
    cl = clean(df.loc[:asof])["close"].tail(60)
    g = g.loc[:asof]
    out = {}
    for kind in KINDS:
        a = SG.active_signal(g["pred"], cl, kind)
        if a is None:
            continue
        t = pd.Timestamp(a["date"])
        a.update(score=g.loc[t, "score"], group=SG.group_of(a["days"]))
        out[kind] = a
    return cl, out


def shard_of(code):
    """個股資料分檔:代號前兩碼(例 2330 → 23);ETF(00 開頭)用前四碼(例 00878 → 0087),免得 ETF 全擠在同一檔。
    前端照同一規則讀 stocks/<分檔>.json。"""
    return code[:4] if code.startswith("00") else code[:2]


# ───────────────────────── 顯示用的價格 ─────────────────────────
def chart_start(index, asof):
    """K 線圖的起點:判斷基準日那年的第一個交易日;那年還不到 CHART_BARS 根時,往前補到 CHART_BARS 根。"""
    idx = index[index <= asof]
    ystart = pd.Timestamp(f"{asof.year}-01-01")
    if not len(idx):
        return ystart
    return min(ystart, idx[-min(C.CHART_BARS, len(idx))])


def display_bars(code, df, asof, raw=None):
    """畫面用的 K 線,從 chart_start 到判斷基準日。df = 還原價(模型用),raw = Yahoo 未還原價(沒有就 None)。
    回傳 dict:bars、price('actual' 實際成交價 / 'adj' 還原價)、close、chg_pct、close_date。
    日期照還原價的日子(和模型同一份交易日);未還原價涵蓋整段才用實際成交價,否則整段用還原價。
    漲跌幅一律用還原價算:除權息當天和看盤軟體一樣,是對參考價(前一天收盤扣掉股利)的漲跌。"""
    empty = {"bars": [], "price": "adj", "close": None, "chg_pct": None, "close_date": None}
    if df is None:
        return empty
    adj = clean(df.loc[:asof])
    if not len(adj):
        return empty
    start = chart_start(adj.index, asof)
    a = adj.loc[start:]
    prev = adj["close"].shift(1).iloc[-1]
    chg = round((adj["close"].iloc[-1] / prev - 1) * 100, 3) if prev == prev and prev else None
    src, price = a, "adj"
    if raw is not None and len(raw):
        r = raw.reindex(a.index)
        if r["close"].notna().all():
            src, price = r, "actual"
    bars = [[str(d.date()), round(float(o), 2), round(float(h), 2), round(float(lo), 2), round(float(c), 2), int(v)]
            for d, o, h, lo, c, v in zip(src.index, src["open"], src["high"], src["low"], src["close"], src["volume"])]
    return {"bars": bars, "price": price, "close": bars[-1][4], "chg_pct": chg, "close_date": bars[-1][0]}


def year_stats(g, year):
    """一檔股票 year 年的判低點 / 判高點:判斷天數、已對答案天數、對幾天、命中率。"""
    out = {"year": year}
    y = g[g.date.str.startswith(year)] if g is not None else None
    for kind in KINDS:
        s = y[y.pred == kind] if y is not None else []
        gr = s[s.truth.notna()] if len(s) else []
        hits = int((gr.truth == kind).sum()) if len(gr) else 0
        out[kind] = {"n": int(len(s)), "graded": int(len(gr)), "hits": hits,
                     "pct": round(hits / len(gr) * 100, 1) if len(gr) else None}
    return out


# ───────────────────────── 主程式 ─────────────────────────
def publish(data, cal, check, log=print):
    t0 = time.time()
    days = ST.list_days()
    if not days:
        log("沒有任何存檔,略過產生網頁資料")
        return
    tab = ST.table()
    latest = ST.read_day(days[-1])
    latest = dict(latest, rows=ST.all_rows(days[-1]))                  # 含補算的股票
    asof = pd.Timestamp(latest["date"])
    out = C.SITE_DATA
    for sub in ("stocks", "img"):
        if os.path.exists(os.path.join(out, sub)):
            shutil.rmtree(os.path.join(out, sub))
    tr = track(tab)
    _w(os.path.join(out, "track.json"), _clean_nan(tr))
    rows = {r["code"]: r for r in latest["rows"]}

    # 每檔最近一次的高 / 低點訊號是否還沒破底 / 沒創高(只用今天以前的存檔與價格)
    recent = sorted(tab.date.unique())[-40:]
    rt = tab[tab.date.isin(recent)]
    preds_by = {c: g.assign(date=pd.to_datetime(g.date)).set_index("date") for c, g in rt.groupby("code")}
    from .datasource import raw_store
    rs = raw_store()
    disp = {code: display_bars(code, data.get(U.ticker_of(code)), asof, rs.load(U.ticker_of(code)))
            for code, r in rows.items() if r["status"] != U.NOSUP}
    closes_by, active = {}, {}
    for code, r in rows.items():
        df = data.get(U.ticker_of(code))
        if r["status"] not in (U.POOL, U.OUT, U.LOWVOL) or df is None or code not in preds_by:
            continue
        closes_by[code], act = stock_active(preds_by[code], df, asof)
        if act:
            active[code] = act

    today = {"date": latest["date"], "source": latest.get("source"), "lists": {},
             "hit": {k: tr["kinds"].get(k, {}).get("all") for k in KINDS}}
    for kind in KINDS:
        items = []
        for code, a in active.items():
            x = SG.newest_only(a).get(kind)                                  # 新訊號蓋掉舊訊號:同一檔不會同時出現在兩邊
            if x is None or rows[code]["status"] != U.POOL:
                continue
            r = rows[code]
            dp = disp.get(code) or {}
            items.append({"code": code, "name": U.name_of(code), "close": dp.get("close", r.get("close")),
                          "chg_pct": dp.get("chg_pct", r.get("chg_pct")), "score": x["score"],
                          "date": x["date"], "days": x["days"], "run": x["run"], "group": x["group"]})
        items.sort(key=lambda x: (x["days"], -(x["score"] if x["score"] is not None else -1e9)))
        for it in items:
            bars = (disp.get(it["code"]) or {}).get("bars") or []
            if bars:
                it["spark"] = [b[4] for b in bars[-20:]]                      # 走勢小圖:實際成交價(沒有官方資料才用還原價)
        today["lists"][kind] = items
    today["n_pool"] = sum(1 for r in latest["rows"] if r["status"] == U.POOL)
    _w(os.path.join(out, "today.json"), _clean_nan(today))

    # 個股:依代號前兩碼分成幾十個檔(Artifact 一次最多發布 255 個檔案)
    hist = tab[tab.pred.isin(KINDS)]
    hist_by = {c: g for c, g in hist.groupby("code")}
    year = str(asof.year)
    excluded = {U.code_of(t) for t in U.lowvol_excluded(asof.year)}         # 訓練股票池剔除的低波動股(TW200 48 檔)
    shards = {}
    for code, r in rows.items():
        if r["status"] in (U.NOSUP,) or (r["status"] == U.NODATA and U.nodata_reason(code)):
            continue
        dp = disp[code]
        g = hist_by.get(code)
        sig = []
        if g is not None:
            first = dp["bars"][0][0] if dp["bars"] else latest["date"]
            for _, s in g[g.date >= first].iterrows():
                sig.append({"date": s.date, "pred": s.pred, "score": s.score, "truth": s.truth, "source": s.source})
        shards.setdefault(shard_of(code), {})[code] = _clean_nan({
            "code": code, "name": U.name_of(code), "market": U.market_of(code), "status": r["status"], "move": r.get("move"), "date": latest["date"],
            "excluded": code in excluded,
            "today": _public_row(r), "active": active.get(code, {}), "price": dp["price"], "close": dp["close"],
            "chg_pct": dp["chg_pct"], "close_date": dp["close_date"], "bars": dp["bars"], "signals": sig,
            "year": year_stats(g, year)})
    for k, v in shards.items():
        _w(os.path.join(out, "stocks", f"{k}.json"), v)

    _w(os.path.join(out, "findings.json"), _clean_nan(findings()))

    # 自動完成清單
    idx = []
    for code, info in U.symbols().items():
        why = U.nodata_reason(code) or ("這次批次沒有計算這檔" if code not in rows and U.supported(code) else "")
        st = rows[code]["status"] if code in rows else (U.NODATA if why else U.NOSUP)
        reason = U.unsupported_reason(code) if st == U.NOSUP else why if st == U.NODATA else ""
        idx.append([code, info["name"], st, info["type"], reason])
    idx.sort(key=lambda x: (x[2] == U.NOSUP, x[0]))
    _w(os.path.join(out, "index.json"), idx)
    _w(os.path.join(out, "research.json"), research())
    _w(os.path.join(out, "meta.json"), _clean_nan({
        "asof": latest["date"], "source": latest.get("source"), "created": latest.get("created"),
        "published": time.strftime("%Y-%m-%d %H:%M"), "check": check, "model": latest.get("model"),
        "profile": C.profile_info(),
        "counts": {s: sum(1 for r in latest["rows"] if r["status"] == s) for s in (U.POOL, U.OUT, U.LOWVOL, U.NODATA, "halted")},
        "rules": {"hold": C.HOLD, "top_n": C.TOP_N, "min_move": C.MIN_MOVE},
        "method": C.METHOD_NAME}))
    log(f"網頁資料完成:{len(rows)} 檔  ({time.time() - t0:.0f}s)")
