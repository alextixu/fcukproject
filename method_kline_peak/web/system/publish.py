"""產生前端讀的 JSON(site/data/,每次批次整批重寫;真正的紀錄在 data/<設定>/days、grades)。
2026-11-09 起只有 Stacking(主軸拿掉),網頁定位為「參考方向的決策輔助」,不放回測與報酬。

  meta.json        基準日、資料檢查、模型資訊
  today.json       今日判斷:推薦範圍(台灣 50)內判低點 / 判高點,依「沒破底 / 沒創高」天數分組、組內依機率排序
  track.json       成績追蹤:每日前 3 檔對答案、命中率、各信心等級命中率、池外命中率
  index.json       自動完成用的股票清單(代號、名稱、分類、市場別)
  research.json    研究結果:TW200 Stacking 2024–2026 的分類成績(直接讀 results/,不重算)
  stocks/<代號前兩碼>.json  個股(每檔一筆):今天的判斷、還沒破底 / 沒創高的訊號、最近 60 根 K 線、過去的判斷與答案
  findings.json    研究發現頁:方向性結論(找得到轉折區、高低點不判反、命中率約三成)
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
M = "stack"                                   # 唯一的方法
MK = "Stacking 邏輯迴歸"                      # 研究結果檔裡 Stacking 的名稱
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
    """網頁用的單檔判斷:只留 Stacking(舊存檔裡的主軸欄位不輸出)。"""
    return {k: (dict(v) if isinstance(v, dict) else v) for k, v in r.items() if k != "main"}


def _rj(name):
    with open(os.path.join(C.RESULTS, name), encoding="utf-8") as f:
        return json.load(f)


# ───────────────────────── 成績 ─────────────────────────
def top_picks(tab, kind, n=C.TOP_N):
    """每天推薦範圍內判 kind 的股票依機率取前 n 檔。"""
    t = tab[(tab.status == U.POOL) & (tab.stack_pred == kind)]
    t = t.sort_values(["date", "stack_score"], ascending=[True, False])
    return t.groupby("date", sort=True).head(n)


def level_hits(tab, kind):
    """各信心等級的命中率(推薦範圍內)。"""
    t = tab[(tab.status == U.POOL) & (tab.stack_pred == kind) & tab.truth.notna()]
    return {lv: _rate((g.truth == kind).sum(), len(g)) for lv, g in t.groupby("stack_level")}


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
        allsig = pool_g[pool_g.stack_pred == kind]
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
                {"code": r.code, "name": U.name_of(r.code), "score": r.stack_score, "truth": r.truth} for _, r in p.iterrows()],
                "hits": int((p.truth == kind).sum()) if graded else None})
        outs = tab[(tab.status == U.OUT) & (tab.stack_pred == kind) & tab.truth.notna()]
        out["kinds"][kind] = {
            "top_20": window(20), "top_60": window(60), "top_all": window(10 ** 6),
            "all_ytd": _rate((ytd.truth == kind).sum(), len(ytd)) | {"year": year},
            "all": _rate((allsig.truth == kind).sum(), len(allsig)),
            "base_rate": _rate((pool_g.truth == kind).sum(), len(pool_g)),
            "levels": level_hits(tab, kind),
            "out_pool": _rate((outs.truth == kind).sum(), len(outs)),
            "series": series, "daily": daily}
    return out


# ───────────────────────── 研究結果(只讀既有結果檔,數字不手抄) ─────────────────────────
def research():
    """TW200 Stacking 2024–2026 的分類成績(results/confusion_2024_2026_tw200_amp0.json)。"""
    conf = _rj("confusion_2024_2026_tw200_amp0.json")
    cls = []
    for y, v in conf.items():
        for m, x in v.items():
            if not isinstance(x, dict) or "precision" not in x or "Stacking" not in m:
                continue
            cm = np.array(x["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"])
            cls.append({"year": y, "macro_f1": round(x["macro_f1"] * 100, 2),
                        "prec_low": round(x["precision"]["低點"] * 100, 1), "prec_high": round(x["precision"]["高點"] * 100, 1),
                        "rec_low": round(x["recall"]["低點"] * 100, 1), "rec_high": round(x["recall"]["高點"] * 100, 1),
                        "base_low": round(cm[0].sum() / cm.sum() * 100, 1), "n_days": int(cm.sum()),
                        "cross": int(cm[0, 2] + cm[2, 0])})
    return {"classification": cls, "sources": ["method_kline_peak/results/confusion_2024_2026_tw200_amp0.json"]}


def confirm_hits():
    """推薦頁分組用的研究命中率:剛出現 = 原始,已 k 天沒破底 = 等 k 天確認(Stacking、TW200 168 檔、2024–2026 三年平均)。"""
    c = _rj("confirm_signals_tw200.json")["classification_三年平均"][MK]
    out = {"source": "研究結果:Stacking、TW200 168 檔、訓練門檻 0%、2024–2026 三年平均(results/confirm_signals_tw200.json)"}
    for kind in KINDS:
        z = K_ZH[kind]
        out[kind] = {"k0": c["A0 原始"][z]["命中率"], "k1": c["k=1"][z]["命中率"],
                     "k2": c["k=2"][z]["命中率"], "k3": c["k=3"][z]["命中率"], "base": c["A0 原始"][z]["隨機基準"]}
    return out


def findings():
    """研究發現頁:只放方向性結論(找得到轉折區、高低點不判反、命中率約三成 → 定位為決策輔助)。"""
    a0 = _rj("postproc_signals_tw200.json")["三年平均"][MK]["A0 原始"]
    conf = _rj("confusion_2024_2026_tw200_amp0.json")
    cross = 0
    for v in conf.values():
        for m, x in v.items():
            if "Stacking" in m and isinstance(x, dict) and "confusion_rows_true_cols_pred(漲,不漲不跌,跌)" in x:
                cm = x["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"]
                cross += cm[0][2] + cm[2][0]
    return {"recall": {"low": a0["低點"]["找到率_精確"], "high": a0["高點"]["找到率_精確"],
                       "low2": a0["低點"]["找到率_±2天"], "high2": a0["高點"]["找到率_±2天"]},
            "precision": {"low": a0["低點"]["命中率"], "high": a0["高點"]["命中率"],
                          "base_low": a0["低點"]["隨機基準"], "base_high": a0["高點"]["隨機基準"]},
            "cross": int(cross), "years": sorted(conf), "confirm": confirm_hits(),
            "sources": ["postproc_signals_tw200.json", "confusion_2024_2026_tw200_amp0.json", "confirm_signals_tw200.json"]}


# ───────────────────────── 個股的訊號狀態 ─────────────────────────
def stock_active(g, df, asof):
    """一檔股票在 asof 那天「還沒破底 / 沒創高」的 Stacking 訊號。g = 這檔的存檔判斷(依日期索引),df = K 線。
    兩者都只用到 asof(含)為止,之後的資料不影響結果。回傳 (最近 60 天收盤, {low/high: 訊號})。"""
    cl = clean(df.loc[:asof])["close"].tail(60)
    g = g.loc[:asof]
    out = {}
    for kind in KINDS:
        a = SG.active_signal(g["stack_pred"], cl, kind)
        if a is None:
            continue
        t = pd.Timestamp(a["date"])
        a.update(score=g.loc[t, "stack_score"], level=g.loc[t, "stack_level"], group=SG.group_of(a["days"]))
        out[kind] = a
    return cl, out


def shard_of(code):
    """個股資料分檔:代號前兩碼(例 2330 → 23)。前端照同一規則讀 stocks/<前兩碼>.json。"""
    return code[:2]


# ───────────────────────── 主程式 ─────────────────────────
def publish(data, cal, check, log=print):
    t0 = time.time()
    days = ST.list_days()
    if not days:
        log("沒有任何存檔,略過產生網頁資料")
        return
    tab = ST.table()
    latest = ST.read_day(days[-1])
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
    closes_by, active = {}, {}
    for code, r in rows.items():
        df = data.get(U.ticker_of(code))
        if r["status"] not in (U.POOL, U.OUT, U.LOWVOL) or df is None or code not in preds_by:
            continue
        closes_by[code], act = stock_active(preds_by[code], df, asof)
        if act:
            active[code] = act

    today = {"date": latest["date"], "source": latest.get("source"), "lists": {},
             "hit": {k: tr["kinds"].get(k, {}).get("all") for k in KINDS}, "confirm_hit": confirm_hits()}
    for kind in KINDS:
        items = []
        for code, a in active.items():
            x = a.get(kind)
            if x is None or rows[code]["status"] != U.POOL:
                continue
            r = rows[code]
            items.append({"code": code, "name": U.name_of(code), "close": r.get("close"), "chg_pct": r.get("chg_pct"),
                          "score": x["score"], "level": x["level"],
                          "level_hit": tr["kinds"].get(kind, {}).get("levels", {}).get(x["level"]),
                          "date": x["date"], "days": x["days"], "run": x["run"], "group": x["group"]})
        items.sort(key=lambda x: (x["days"], -(x["score"] if x["score"] is not None else -1e9)))
        for it in items:
            if it["code"] in closes_by:
                it["spark"] = [round(float(v), 2) for v in closes_by[it["code"]].tail(20)]
        today["lists"][kind] = items
    today["n_pool"] = sum(1 for r in latest["rows"] if r["status"] == U.POOL)
    _w(os.path.join(out, "today.json"), _clean_nan(today))

    # 個股:依代號前兩碼分成幾十個檔(Artifact 一次最多發布 255 個檔案)
    hist = tab[tab.stack_pred.isin(KINDS)]
    hist_by = {c: g for c, g in hist.groupby("code")}
    shards = {}
    for code, r in rows.items():
        if r["status"] in (U.NOSUP,):
            continue
        df = data.get(U.ticker_of(code))
        bars = []
        if df is not None:
            cdf = clean(df.loc[:asof]).tail(C.CHART_BARS)
            bars = [[str(d.date()), round(o, 2), round(h, 2), round(lo, 2), round(c, 2), int(v)]
                    for d, o, h, lo, c, v in zip(cdf.index, cdf.open, cdf.high, cdf.low, cdf.close, cdf.volume)]
        g = hist_by.get(code)
        sig, stats = [], None
        if g is not None:
            first = bars[0][0] if bars else latest["date"]
            for _, s in g[g.date >= first].iterrows():
                sig.append({"date": s.date, "pred": s.stack_pred, "score": s.stack_score, "level": s.stack_level,
                            "truth": s.truth, "source": s.source})
            gm = g[(g.stack_pred == "low") & g.truth.notna()]
            stats = _rate((gm.truth == "low").sum(), len(gm))
        shards.setdefault(shard_of(code), {})[code] = _clean_nan({
            "code": code, "name": U.name_of(code), "status": r["status"], "move": r.get("move"), "date": latest["date"],
            "today": _public_row(r), "active": active.get(code, {}), "bars": bars, "signals": sig[-40:], "low_stats": stats})
    for k, v in shards.items():
        _w(os.path.join(out, "stocks", f"{k}.json"), v)

    _w(os.path.join(out, "findings.json"), _clean_nan(findings()))

    # 自動完成清單
    idx = []
    for code, info in U.symbols().items():
        st = rows[code]["status"] if code in rows else U.NOSUP
        reason = U.unsupported_reason(code) if st == U.NOSUP else ""
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
        "method": C.METHOD_NAMES[M]}))
    log(f"網頁資料完成:{len(rows)} 檔  ({time.time() - t0:.0f}s)")
