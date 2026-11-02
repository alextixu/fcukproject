"""產生前端讀的 JSON(site/data/,每次批次整批重寫;真正的紀錄在 data/days、data/grades)。

  meta.json        基準日、資料檢查、模型資訊
  today.json       今日判斷:兩個方法 × 判低點 / 判高點,池內股票依分數排序
  track.json       成績追蹤:每日前 3 檔對答案、命中率、各信心等級命中率、池外命中率
  index.json       自動完成用的股票清單(代號、名稱、分類、市場別)
  research.json    研究結果(直接讀 results/ 的既有結果檔,不重算)
  stocks/<代號>.json  個股:今天兩個方法的判斷、最近 60 根 K 線、過去的判斷與答案
"""
import json
import os
import shutil
import time

import numpy as np
import pandas as pd

from . import config as C, store as ST, universe as U
from feasibility import clean  # noqa: E402

KINDS = ("low", "high")


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


# ───────────────────────── 成績 ─────────────────────────
def top_picks(tab, method, kind, n=C.TOP_N):
    """每天池內判 kind 的股票依分數取前 n 檔。"""
    t = tab[(tab.status == U.POOL) & (tab[f"{method}_pred"] == kind)]
    t = t.sort_values(["date", f"{method}_score"], ascending=[True, False])
    return t.groupby("date", sort=True).head(n)


def level_hits(tab, method, kind):
    t = tab[(tab.status == U.POOL) & (tab[f"{method}_pred"] == kind) & tab.truth.notna()]
    return {lv: _rate((g.truth == kind).sum(), len(g)) for lv, g in t.groupby(f"{method}_level")}


def track(tab):
    out = {"methods": {}, "dates": {}}
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
    for method in C.METHODS:
        out["methods"][method] = {}
        for kind in KINDS:
            picks = top_picks(tab, method, kind)
            gp = picks[picks.truth.notna()]
            gdates = sorted(gp.date.unique())

            def window(k):
                w = gp[gp.date.isin(gdates[-k:])]
                return _rate((w.truth == kind).sum(), len(w)) | {"days": len(gdates[-k:]),
                                                                 "avg_ret_pct": round(float(w.ret_pct.mean()), 2) if len(w) else None,
                                                                 "win_pct": round(float((w.ret_pct > 0).mean() * 100), 1) if len(w) else None}
            allsig = pool_g[pool_g[f"{method}_pred"] == kind]
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
                    {"code": r.code, "name": U.name_of(r.code), "score": r[f"{method}_score"], "truth": r.truth,
                     "ret_pct": r.ret_pct} for _, r in p.iterrows()],
                    "hits": int((p.truth == kind).sum()) if graded else None,
                    "avg_ret_pct": round(float(p.ret_pct.mean()), 2) if graded else None})
            outs = tab[(tab.status == U.OUT) & (tab[f"{method}_pred"] == kind) & tab.truth.notna()]
            low_v = tab[(tab.status == U.LOWVOL) & (tab[f"{method}_pred"] == kind) & tab.truth.notna()]
            out["methods"][method][kind] = {
                "top_20": window(20), "top_60": window(60), "top_all": window(10 ** 6),
                "all_ytd": _rate((ytd.truth == kind).sum(), len(ytd)) | {"year": year},
                "all": _rate((allsig.truth == kind).sum(), len(allsig)),
                "base_rate": _rate((pool_g.truth == kind).sum(), len(pool_g)),
                "levels": level_hits(tab, method, kind),
                "out_pool": _rate((outs.truth == kind).sum(), len(outs)),
                "low_vol": _rate((low_v.truth == kind).sum(), len(low_v)),
                "series": series, "daily": daily}
    return out


# ───────────────────────── 研究結果(只讀既有結果檔) ─────────────────────────
def research():
    def rd(name):
        with open(os.path.join(C.RESULTS, name), encoding="utf-8") as f:
            return json.load(f)
    conf = rd("confusion_2024_2026_tw100.json")
    cls = []
    for y, v in conf.items():
        for m, x in v.items():
            if not isinstance(x, dict) or "precision" not in x:
                continue
            cm = np.array(x["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"])
            cls.append({"year": y, "method": "main" if "主軸" in m else "stack", "macro_f1": round(x["macro_f1"] * 100, 2),
                        "prec_low": round(x["precision"]["低點"] * 100, 1), "prec_high": round(x["precision"]["高點"] * 100, 1),
                        "rec_low": round(x["recall"]["低點"] * 100, 1), "rec_high": round(x["recall"]["高點"] * 100, 1),
                        "base_low": round(cm[0].sum() / cm.sum() * 100, 1), "n_days": int(cm.sum()),
                        "signals_per_day_low": None})
    bt = []
    for pool, name in (("tw100", "TW100 73 檔"), ("tw200", "TW200 168 檔")):
        d = rd(f"backtest_long_only_{pool}.json")
        for y, v in d["years"].items():
            for m in ("主軸", "Stacking 邏輯迴歸"):
                x = v[m]["扣成本"]
                bt.append({"pool": name, "year": y, "method": "main" if m == "主軸" else "stack",
                           "ret_pct": x["total_return_pct"], "max_dd_pct": x["max_dd_pct"], "win_pct": x["win_rate_pct"],
                           "n_trades": x["n_trades"], "period": v["period"]})
    return {"classification": cls, "backtest": bt,
            "sources": ["method_kline_peak/results/confusion_2024_2026_tw100.json",
                        "method_kline_peak/results/backtest_long_only_tw100.json",
                        "method_kline_peak/results/backtest_long_only_tw200.json"]}


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
    if os.path.exists(os.path.join(out, "stocks")):
        shutil.rmtree(os.path.join(out, "stocks"))
    tr = track(tab)
    _w(os.path.join(out, "track.json"), _clean_nan(tr))
    rows = {r["code"]: r for r in latest["rows"]}

    def lv_hit(method, kind, lv):
        return tr["methods"].get(method, {}).get(kind, {}).get("levels", {}).get(lv)

    today = {"date": latest["date"], "source": latest.get("source"), "methods": {}}
    for method in C.METHODS:
        today["methods"][method] = {}
        for kind in KINDS:
            items = []
            for r in latest["rows"]:
                mm = r.get(method)
                if r["status"] != U.POOL or not mm or mm["pred"] != kind:
                    continue
                other = r.get("stack" if method == "main" else "main") or {}
                items.append({"code": r["code"], "name": U.name_of(r["code"]), "close": r.get("close"), "chg_pct": r.get("chg_pct"),
                              "score": mm["score"], "level": mm["level"], "level_hit": lv_hit(method, kind, mm["level"]),
                              "both": other.get("pred") == kind})
            items.sort(key=lambda x: -(x["score"] if x["score"] is not None else -1e9))
            for it in items[:C.TOP_N * 2]:
                df = data.get(U.ticker_of(it["code"]))
                if df is not None:
                    it["spark"] = [round(float(v), 2) for v in clean(df.loc[:asof])["close"].tail(20)]
            today["methods"][method][kind] = items
    today["both"] = {k: sum(1 for r in latest["rows"] if r["status"] == U.POOL and r.get("main") and r["main"]["pred"] == k
                            and r["stack"]["pred"] == k) for k in KINDS}
    today["n_pool"] = sum(1 for r in latest["rows"] if r["status"] == U.POOL)
    _w(os.path.join(out, "today.json"), _clean_nan(today))

    # 個股
    hist = tab[(tab.main_pred.isin(KINDS)) | (tab.stack_pred.isin(KINDS))]
    hist_by = {c: g for c, g in hist.groupby("code")}
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
        sig, stats = [], {}
        if g is not None:
            first = bars[0][0] if bars else latest["date"]
            for _, s in g[g.date >= first].iterrows():
                sig.append({"date": s.date, "main": s.main_pred, "main_score": s.main_score, "main_level": s.main_level,
                            "stack": s.stack_pred, "truth": s.truth, "ret_pct": s.ret_pct, "source": s.source})
            for method in C.METHODS:
                gm = g[(g[f"{method}_pred"] == "low") & g.truth.notna()]
                stats[method] = _rate((gm.truth == "low").sum(), len(gm))
        _w(os.path.join(out, "stocks", f"{code}.json"), _clean_nan({
            "code": code, "name": U.name_of(code), "status": r["status"], "move": r.get("move"), "date": latest["date"],
            "today": r, "bars": bars, "signals": sig[-40:], "low_stats": stats}))

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
        "profile": C.profile_info(sum(1 for r in latest["rows"] if r["status"] == U.POOL)),
        "counts": {s: sum(1 for r in latest["rows"] if r["status"] == s) for s in (U.POOL, U.OUT, U.LOWVOL, U.NODATA, "halted")},
        "rules": {"hold": C.HOLD, "cost_pct": C.COST_PCT, "top_n": C.TOP_N, "min_move": C.MIN_MOVE}}))
    log(f"網頁資料完成:{len(rows)} 檔  ({time.time() - t0:.0f}s)")
