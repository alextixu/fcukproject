"""產生前端讀的 JSON(site/data/,每次批次整批重寫;真正的紀錄在 data/days、data/grades)。

  meta.json        基準日、資料檢查、模型資訊
  today.json       今日判斷:兩個方法 × 判低點 / 判高點,池內股票依分數排序
  track.json       成績追蹤:每日前 3 檔對答案、命中率、各信心等級命中率、池外命中率
  index.json       自動完成用的股票清單(代號、名稱、分類、市場別)
  research.json    研究結果(直接讀 results/ 的既有結果檔,不重算)
  stocks/<代號前兩碼>.json  個股(每檔一筆):今天兩個方法的判斷、還沒破底 / 沒創高的訊號、最近 60 根 K 線、過去的判斷與答案
  findings.json    研究發現頁:直接讀 results/ 的後處理、等確認、機率門檻、低點進高點出結果檔
  img/             研究發現頁的圖(results/ 的 png 縮小後複製)
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
    """網頁用的單檔判斷:不顯示等級的方法拿掉 level 欄位(存檔本身不改)。"""
    r = {k: (dict(v) if isinstance(v, dict) else v) for k, v in r.items()}
    for m in C.METHODS:
        if m not in C.LEVEL_METHODS and isinstance(r.get(m), dict):
            r[m].pop("level", None)
    return r


# ───────────────────────── 成績 ─────────────────────────
def top_picks(tab, method, kind, n=C.TOP_N):
    """每天池內判 kind 的股票依分數取前 n 檔。"""
    t = tab[(tab.status == U.POOL) & (tab[f"{method}_pred"] == kind)]
    t = t.sort_values(["date", f"{method}_score"], ascending=[True, False])
    return t.groupby("date", sort=True).head(n)


def level_hits(tab, method, kind):
    """各信心等級的命中率(池內);不顯示等級的方法(config.LEVEL_METHODS 以外)回傳空的。"""
    if method not in C.LEVEL_METHODS:
        return {}
    t = tab[(tab.status == U.POOL) & (tab[f"{method}_pred"] == kind) & tab.truth.notna()]
    return {lv: _rate((g.truth == kind).sum(), len(g)) for lv, g in t.groupby(f"{method}_level")}


def both_hits(tab, kind):
    """兩個方法都判 kind 的池內股票日,事後真的是 kind 的比例。"""
    t = tab[(tab.status == U.POOL) & (tab.main_pred == kind) & (tab.stack_pred == kind) & tab.truth.notna()]
    return _rate((t.truth == kind).sum(), len(t))


def track(tab):
    out = {"methods": {}, "dates": {}, "both": {}}
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
    out["both"] = {kind: both_hits(tab, kind) for kind in KINDS}
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
                "levels": level_hits(tab, method, kind), "both": out["both"][kind],
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


def stock_active(g, df, asof):
    """一檔股票在 asof 那天「還沒破底 / 沒創高」的訊號。g = 這檔的存檔判斷(依日期索引),df = K 線。
    兩者都只用到 asof(含)為止,之後的資料不影響結果。回傳 (最近 60 天收盤, {方法: {low/high: 訊號}})。"""
    cl = clean(df.loc[:asof])["close"].tail(60)
    g = g.loc[:asof]
    out = {}
    for method in C.METHODS:
        for kind in KINDS:
            a = SG.active_signal(g[f"{method}_pred"], cl, kind)
            if a is None:
                continue
            t = pd.Timestamp(a["date"])
            other = "stack" if method == "main" else "main"
            a.update(score=g.loc[t, f"{method}_score"], level=g.loc[t, f"{method}_level"] if method in C.LEVEL_METHODS else None,
                     both=bool(g.loc[t, f"{other}_pred"] == kind), group=SG.group_of(a["days"]))
            out.setdefault(method, {})[kind] = a
    return cl, out


def shard_of(code):
    """個股資料分檔:代號前兩碼(例 2330 → 23)。前端照同一規則讀 stocks/<前兩碼>.json。"""
    return code[:2]


# ───────────────────────── 研究發現(只讀 results/ 的既有結果檔,數字不手抄) ─────────────────────────
M_KEYS = {"main": "主軸", "stack": "Stacking 邏輯迴歸"}
K_ZH = {"low": "低點", "high": "高點"}
FUTURE = "用到未來資訊,實際用不了"


def _rj(name):
    with open(os.path.join(C.RESULTS, name), encoding="utf-8") as f:
        return json.load(f)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(float(np.mean(xs)), 2) if xs else None


def confirm_hits():
    """推薦頁分組用的研究命中率:剛出現 = 原始(A0),已 k 天沒破底 = 等 k 天確認(TW200 168 檔、2024–2026 三年平均)。"""
    c = _rj("confirm_signals_tw200.json")["classification_三年平均"]
    out = {"source": "研究結果:TW200 168 檔、訓練門檻 0%、2024–2026 三年平均(results/confirm_signals_tw200.json)"}
    for m, mk in M_KEYS.items():
        out[m] = {}
        for kind in KINDS:
            z = K_ZH[kind]
            out[m][kind] = {"k0": c[mk]["A0 原始"][z]["命中率"], "k1": c[mk]["k=1"][z]["命中率"],
                            "k2": c[mk]["k=2"][z]["命中率"], "k3": c[mk]["k=3"][z]["命中率"],
                            "base": c[mk]["A0 原始"][z]["隨機基準"]}
    return out


def findings(out=None):
    pp = _rj("postproc_signals_tw200.json")
    cf = _rj("confirm_signals_tw200.json")
    pc = _rj("prob_cut_tw200.json")
    lo = _rj("lohi_compare_34_2025.json")
    cmp8 = _rj("compare_8046_2024_tw200.json")
    lo8 = _rj("lohi_compare_8046_2024_tw200.json")
    conf = _rj("confusion_2024_2026_tw200_amp0.json")
    avg = pp["三年平均"]
    years = sorted(cf["backtest"]["k=0"])

    def bt(k, mk):
        return _mean([cf["backtest"][f"k={k}"][y][mk]["扣成本"]["total_return_pct"] for y in years])

    def late(k, mk):
        return _mean([cf["late_entry"][f"k={k}"][y][mk]["差距(晚 − 早)"] for y in years])

    cross = 0
    for y, v in conf.items():
        for x in v.values():
            if isinstance(x, dict) and "confusion_rows_true_cols_pred(漲,不漲不跌,跌)" in x:
                cm = x["confusion_rows_true_cols_pred(漲,不漲不跌,跌)"]
                cross += cm[0][2] + cm[2][0]
    pa = pc["全部_三年平均"]
    p0, p7, p8 = pa["不設門檻(原始)"], pa["最大機率 ≥ 0.7"], pa["最大機率 ≥ 0.8"]
    cards = {"cross": int(cross), "years": sorted(conf)}
    for m, mk in M_KEYS.items():                                  # 兩個方法各一組結論數字(網頁預設顯示 Stacking)
        a0 = avg[mk]["A0 原始"]
        top50, top10 = avg[mk]["2 每天前 50%"], avg[mk]["2 每天前 10%"]
        ca = cf["classification_三年平均"][mk]
        cards[m] = {
            "recall": {"low": a0["低點"]["找到率_精確"], "high": a0["高點"]["找到率_精確"],
                       "low2": a0["低點"]["找到率_±2天"], "high2": a0["高點"]["找到率_±2天"]},
            "precision": {"low": a0["低點"]["命中率"], "high": a0["高點"]["命中率"],
                          "base_low": a0["低點"]["隨機基準"], "base_high": a0["高點"]["隨機基準"]},
            "filters": {"orig_hit": a0["低點"]["命中率"], "orig_rec": a0["低點"]["找到率_精確"],
                        "top50_hit": top50["低點"]["命中率"], "top50_rec": top50["低點"]["找到率_精確"],
                        "top10_hit": top10["低點"]["命中率"], "top10_rec": top10["低點"]["找到率_精確"],
                        # 機率門檻只有 Stacking 有(主軸沒有機率)
                        "p7_hit": p7["低點"]["命中率"] if m == "stack" else None, "p7_rec": p7["低點"]["找到率_精確"] if m == "stack" else None,
                        "p8_hit": p8["低點"]["命中率"] if m == "stack" else None, "p8_rec": p8["低點"]["找到率_精確"] if m == "stack" else None},
            "confirm": {"k0_hit": ca["A0 原始"]["低點"]["命中率"], "k1_hit": ca["k=1"]["低點"]["命中率"],
                        "k3_hit": ca["k=3"]["低點"]["命中率"], "bt0": bt(0, mk), "bt1": bt(1, mk), "bt2": bt(2, mk),
                        "bt3": bt(3, mk), "late1": late(1, mk), "late3": late(3, mk)},
        }

    # 後處理比較(TW200 三年平均)
    post = {}
    for m, mk in M_KEYS.items():
        rows = []
        src = [("A0 原始", "原始(不處理)", avg[mk]["A0 原始"], bt(0, mk), ""),
               ("1a", "合併連續・事後最高分", avg[mk]["1a 合併連續・事後最高分(上限參考)"], None, FUTURE),
               ("1b", "合併連續・即時版", avg[mk]["1b 合併連續・即時版"], None, ""),
               ("top50", "每天只留前 50%", avg[mk]["2 每天前 50%"], None, "")]
        src += [(f"k{k}", f"等 {k} 天確認", cf["classification_三年平均"][mk][f"k={k}"], bt(k, mk),
                 f"命中率要等 {k} 天才知道;晚 {k} 天進場") for k in (1, 2, 3)]
        for key, name, x, b, note in src:
            rows.append({"key": key, "name": name, "macro_f1": x["macro_f1"], "n_low": round(x["低點"]["訊號數"]),
                         "hit_low": x["低點"]["命中率"], "rec_low": x["低點"]["找到率_精確"],
                         "hit_high": x["高點"]["命中率"], "rec_high": x["高點"]["找到率_精確"],
                         "bt": b, "future": key == "1a", "note": note})
        post[m] = rows

    # Stacking 機率門檻(TW200 三年平均)
    prob = [{"name": k, "n_low": round(v["低點"]["訊號數"]), "n_high": round(v["高點"]["訊號數"]),
             "hit_low": v["低點"]["命中率"], "hit_high": v["高點"]["命中率"],
             "rec_low": v["低點"]["找到率_精確"], "rec_high": v["高點"]["找到率_精確"], "macro_f1": v["macro_f1"]}
            for k, v in pa.items()]

    # 34 檔 2025 低點進、高點出
    lohi = {}
    for m, mk in M_KEYS.items():
        rows = []
        for k, v in lo["methods"][mk].items():
            if k.startswith("_"):
                continue
            rows.append({"name": k.split("(")[0].replace("2-50 ", ""), "future": "未來" in k or k.startswith("1a"),
                         "ret": v["扣成本_pct"], "gross": v["沒扣成本_pct"], "n": v["n_trades"], "win": v["win_rate_pct"],
                         "hold": v["avg_hold_days"], "dd": v["max_dd_pct"], "vs": v["vs_等權買進持有"]})
        lohi[m] = rows
    lohi_base = {"buy_hold": lo["等權買進持有_pct"], "top3": lo["前3檔持有5天_引用"], "n_stocks": lo["n_stocks"], "year": lo["year"]}

    # 南電 2024 圖的說明(數字從 json 讀)
    def c8(mk, key, kind="low"):
        return next(v[K_ZH[kind]] for k, v in cmp8["methods"][mk].items() if k.startswith(key))

    def l8(mk, prefix):
        return next(v for k, v in lo8["methods"][mk].items() if k.startswith(prefix))
    pn = pc["南電 2024"]
    q0, q7, q8 = pn["不設門檻(原始)"]["低點"], pn["最大機率 ≥ 0.7"]["低點"], pn["最大機率 ≥ 0.8"]["低點"]
    imgs = {}
    for m, mk in M_KEYS.items():
        name = "Stacking" if m == "stack" else "主軸"
        x0, x1a, x3 = c8(mk, "A0"), c8(mk, "1a"), c8(mk, "確認 k=3")
        h0 = c8(mk, "A0", "high")
        items = [(f"compare_8046_2024_tw200_{m}.png", f"{name} · 各種後處理留下的訊號", [
            f"最上面是南電 2024 的真實高低點。{name} 原始判斷把 {x0['判']} 天判成低點,其中 {x0['對']} 天對、{x0['錯']} 天錯;"
            f"{x0['真']} 個真低點有 {x0['當天抓到']} 個當天就被提醒到(判高點 {h0['判']} 天,{h0['真']} 個真高點抓到 {h0['當天抓到']} 個)。",
            f"「事後最高分」那列命中 {x1a['命中率']}%,但要等整段訊號結束才知道哪天最高,實際用不了。"
            f"等 3 天確認剩 {x3['判']} 天({x3['對']} 對 / {x3['錯']} 錯),真低點一個都沒少;代價是確認的那天(小點)已經晚了 3 天。"])]
        if m == "stack":
            items.append(("prob_cut_8046_2024_tw200_stack.png", "Stacking · 只留最大機率夠高的訊號", [
                f"不設門檻時判低點 {q0['判']} 天,命中 {q0['命中率']}%。機率 ≥ 0.7 剩 {q7['判']} 天、命中 {q7['命中率']}%;"
                f"≥ 0.8 剩 {q8['判']} 天、命中 {q8['命中率']}%。",
                f"門檻拉高,錯的訊號少了,對的也一起少了:命中率 {q0['命中率']}% → {q8['命中率']}%,"
                f"真低點當天抓到 {q0['當天抓到']} → {q8['當天抓到']} 個。"]))
        items.append((f"lohi_compare_8046_2024_tw200_{m}.png", f"{name} · 南電 2024 低點進場、高點出場", [
            f"南電 2024 全年下跌,買進持有 {lo8['buy_hold_pct']}%。照 {name} 原始判斷低點買、高點賣是 {l8(mk, 'A0')['扣成本_pct']}%,"
            f"等 3 天確認是 {l8(mk, '確認 k=3')['扣成本_pct']}%。",
            f"實際做得到的規則都沒有賺錢,只是虧得比買進持有少。最上面「真實標籤」的 +{l8(mk, '真實標籤')['扣成本_pct']}% "
            f"是事先知道答案的上限,實際做不到。"]))
        imgs[m] = []
        for fname, title, text in items:
            imgs[m].append({"file": f"img/{fname}", "title": title, "text": text})
            if out is not None:
                _copy_img(fname, os.path.join(out, "img", fname))
    return {"cards": cards, "post": post, "prob": prob, "prob_median": pc["機率中位數_三年平均"], "lohi": lohi,
            "lohi_base": lohi_base, "images": imgs, "confirm": confirm_hits(), "default_method": C.DEFAULT_METHOD,
            "sources": ["postproc_signals_tw200.json", "confirm_signals_tw200.json", "prob_cut_tw200.json",
                        "lohi_compare_34_2025.json", "compare_8046_2024_tw200.json", "lohi_compare_8046_2024_tw200.json",
                        "confusion_2024_2026_tw200_amp0.json"]}


def _copy_img(name, dst, width=1400):
    """results/ 的圖縮小後複製到網頁資料夾(原圖 2676 px 寬,約 0.7 MB)。"""
    from PIL import Image
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im = Image.open(os.path.join(C.RESULTS, name))
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.convert("RGB").save(dst, optimize=True)


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

    # 每檔每個方法最近一次的高 / 低點訊號是否還沒破底 / 沒創高(只用今天以前的存檔與價格)
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

    def lv_hit(method, kind, lv):
        return tr["methods"].get(method, {}).get(kind, {}).get("levels", {}).get(lv)

    today = {"date": latest["date"], "source": latest.get("source"), "methods": {}, "both_hit": tr.get("both", {}),
             "hit": {m: {k: tr["methods"].get(m, {}).get(k, {}).get("all") for k in KINDS} for m in C.METHODS},
             "confirm_hit": confirm_hits()}
    for method in C.METHODS:
        today["methods"][method] = {}
        for kind in KINDS:
            items = []
            for code, a in active.items():
                x = a.get(method, {}).get(kind)
                if x is None or rows[code]["status"] != U.POOL:
                    continue
                r = rows[code]
                items.append({"code": code, "name": U.name_of(code), "close": r.get("close"), "chg_pct": r.get("chg_pct"),
                              "score": x["score"], "level": x["level"],
                              "level_hit": lv_hit(method, kind, x["level"]) if method in C.LEVEL_METHODS else None,
                              "both": bool(x["both"]), "date": x["date"], "days": x["days"], "run": x["run"], "group": x["group"]})
            items.sort(key=lambda x: (x["days"], -(x["score"] if x["score"] is not None else -1e9)))
            for it in items:
                if it["code"] in closes_by:
                    it["spark"] = [round(float(v), 2) for v in closes_by[it["code"]].tail(20)]
            today["methods"][method][kind] = items
    today["both"] = {k: sum(1 for r in latest["rows"] if r["status"] == U.POOL and r.get("main") and r["main"]["pred"] == k
                            and r["stack"]["pred"] == k) for k in KINDS}
    today["n_pool"] = sum(1 for r in latest["rows"] if r["status"] == U.POOL)
    _w(os.path.join(out, "today.json"), _clean_nan(today))

    # 個股:依代號前兩碼分成幾十個檔(Artifact 一次最多發布 255 個檔案)
    hist = tab[(tab.main_pred.isin(KINDS)) | (tab.stack_pred.isin(KINDS))]
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
        sig, stats = [], {}
        if g is not None:
            first = bars[0][0] if bars else latest["date"]
            for _, s in g[g.date >= first].iterrows():
                sig.append({"date": s.date, "main": s.main_pred, "main_score": s.main_score,
                            "stack": s.stack_pred, "truth": s.truth, "ret_pct": s.ret_pct, "source": s.source})
            for method in C.METHODS:
                gm = g[(g[f"{method}_pred"] == "low") & g.truth.notna()]
                stats[method] = _rate((gm.truth == "low").sum(), len(gm))
        shards.setdefault(shard_of(code), {})[code] = _clean_nan({
            "code": code, "name": U.name_of(code), "status": r["status"], "move": r.get("move"), "date": latest["date"],
            "today": _public_row(r), "active": active.get(code, {}), "bars": bars, "signals": sig[-40:], "low_stats": stats})
    for k, v in shards.items():
        _w(os.path.join(out, "stocks", f"{k}.json"), v)

    _w(os.path.join(out, "findings.json"), _clean_nan(findings(out)))

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
        "rules": {"hold": C.HOLD, "cost_pct": C.COST_PCT, "top_n": C.TOP_N, "min_move": C.MIN_MOVE},
        "default_method": C.DEFAULT_METHOD}))
    log(f"網頁資料完成:{len(rows)} 檔  ({time.time() - t0:.0f}s)")
