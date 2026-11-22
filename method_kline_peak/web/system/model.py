"""正式模型:訓練、存檔、推論。判斷方法和 final 分支相同:規則候選 → 高點、低點各一組 AE(29 → 16)+ OC-SVM。

- 用在 Y 年的模型 = 研究 walk-forward 的 Y 年模型:股票池 pool_for_year(Y)(設定值 config.POOL),訓練 Y−4 ~ Y−1,
  訓練期最後 5 個交易日剔除(標籤會看到 Y 年),種子 42,訓練門檻 config.TRAIN_MIN_AMP(預設 0%)。
  2026 年(含)以前的模型用研究快取的 K 線訓練(和 final 同一份資料,模型完全相同);2027 年起用網頁系統自己的 K 線快取。
  程式碼直接引用研究的類別 walkforward.MainlineSource(fit / predict),不複製。
- 每組設定(股票池 + 門檻)的模型分開存在 data/<設定>/models/。
- 訓練要用到 Y 年至少 5 個交易日的資料(剔除規則要知道 Y 年第一天在哪),所以 1 月第 6 個交易日之後才能重訓;
  在那之前沿用 Y−1 年的模型。
- 輸出:判斷(高點 / 低點 / 非極值)、規則候選(t 收盤是最近 6 天最高 → 高點候選、最低 → 低點候選)、
  分數 = OC-SVM 的 decision 值(只有候選才有;> 0 = 落在學過的高點 / 低點範圍內 → 判高點 / 低點)。分數不是機率。
- 信心等級(高 / 中 / 低):分數在訓練期同類判斷裡的三分位。要不要顯示由 config.SHOW_LEVELS 決定
  (2026-11-22 用回放資料檢查各等級的命中率,見 README)。
"""
import json
import os
import time

import joblib
import numpy as np
import pandas as pd

from . import config as C
from .features import CODE2KIND
from .universe import pool_for_year
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402

LEVELS = ("高", "中", "低")


def model_path(year):
    return C.profile_dir("models", f"model_{year}.joblib")


class NotEnoughData(Exception):
    pass


def _cuts(scores):
    s = np.asarray(scores, dtype=float)
    s = s[np.isfinite(s)]
    if len(s) < 3:
        return [float("inf"), float("inf")]
    return [float(np.quantile(s, 2 / 3)), float(np.quantile(s, 1 / 3))]


def level(score, cuts):
    if score is None or not np.isfinite(score):
        return None
    return "高" if score >= cuts[0] else "中" if score >= cuts[1] else "低"


def training_store(year, store):
    """year 年模型的訓練資料來源:研究涵蓋的年份(≤ config.RESEARCH_LAST_YEAR)用研究快取(和 final 同一份資料),
    之後用網頁系統自己的 K 線快取。"""
    from .datasource import research_store
    return research_store() if year <= C.RESEARCH_LAST_YEAR else store


def training_set(year, store):
    """year 年模型的訓練資料:(訓練期 panel, 特徵欄, 股票池)。訓練門檻 config.TRAIN_MIN_AMP > 0 時,
    兩邊幅度未達門檻的高點 / 低點在訓練時改成非極值(walkforward.relabel,同研究的 --train-min-amp)。"""
    pool = pool_for_year(year, store)
    data = training_store(year, store).load_many(pool, end=f"{year}-01-31")
    data = {tk: df.loc[ML.START:] for tk, df in data.items() if len(df) >= 250}
    first = [df.index[df.index.year == year] for df in data.values()]
    if sum(len(f) >= C.HOLD for f in first) < len(data) * 0.8:
        raise NotEnoughData(f"{year} 年的交易日還不到 {C.HOLD} 天,先沿用 {year - 1} 年的模型")
    panel, fc = ML.build_panel(data, 6, [])
    tr = WF.relabel(WF.year_split(panel, year, C.TRAIN_YEARS)["train"], C.TRAIN_MIN_AMP)
    return tr, fc, list(data)                                                 # 保持 TICKER_SETS 順序(同研究)


def train(year, store, log=print):
    """訓練 year 年要用的模型並存檔;回傳模型 dict。walkforward.MainlineSource:訓練期的候選點裡,
    高點、低點各一組 AE + OC-SVM 只學真的高點 / 低點,同研究的 walk-forward(run_year)。"""
    t0 = time.time()
    tr, fc, pool = training_set(year, store)
    log(f"訓練 {year} 年模型({C.profile()}):{len(pool)} 檔,{tr.date.min().date()} ~ {tr.date.max().date()},{len(tr):,} 筆,"
        f"訓練門檻 {C.TRAIN_MIN_AMP:g}%")
    src = WF.MainlineSource(seed=C.SEED)
    src.fit(tr, fc)
    m = {"src": src, "fc": fc, "pool": pool, "year": year, "profile": C.profile(),
         "pool_name": C.POOL, "train_min_amp": C.TRAIN_MIN_AMP,
         "train": [str(tr.date.min().date()), str(tr.date.max().date())], "n_train": len(tr),
         "created": time.strftime("%Y-%m-%d %H:%M")}
    ins = predict(m, tr)                                                      # 訓練期內的判斷 → 信心等級切點
    m["cuts"] = {k: _cuts(ins.loc[ins.pred == k, "score"]) for k in ("low", "high")}
    os.makedirs(os.path.dirname(model_path(year)), exist_ok=True)
    joblib.dump(m, model_path(year))
    log(f"  完成,存於 {model_path(year)}  ({time.time() - t0:.0f}s)")
    return m


def load(year):
    p = model_path(year)
    return joblib.load(p) if os.path.exists(p) else None


def ensure(year, store, log=print):
    """year 年的模型;沒有就訓練;資料還不夠就用前一年的。"""
    m = load(year)
    if m is not None and "src" in m:
        return m
    try:
        return train(year, store, log)
    except NotEnoughData as e:
        log(str(e))
        prev = load(year - 1)
        return prev if prev is not None and "src" in prev else train(year - 1, store, log)


def info(m):
    return {"year": m["year"], "train": m["train"], "n_train": m["n_train"], "n_pool": len(m["pool"]),
            "created": m["created"], "seed": C.SEED,
            "pool_name": m.get("pool_name", C.POOL), "train_min_amp": m.get("train_min_amp", 0.0)}


def predict(m, frame):
    """frame:features.live_frame 的列(可以多檔多天,要有 date、ticker、29 個特徵、cand_hi、cand_lo)。
    回傳同順序的 DataFrame:pred(low / high / none)、cand(規則候選 low / high,不是候選為 None)、
    score(OC-SVM decision 值;不是候選為 NaN)。判斷與分數直接來自 walkforward.MainlineSource.predict。"""
    if not len(frame):
        return pd.DataFrame(columns=["pred", "cand", "score"])
    frame = frame.reset_index(drop=True)
    sig = m["src"].predict(frame)
    pred = sig["pred"].map(CODE2KIND).to_numpy()
    lo, hi = frame["cand_lo"].to_numpy(bool), frame["cand_hi"].to_numpy(bool)
    cand = np.where(pred != "none", pred, np.where(lo, "low", np.where(hi, "high", None)))
    score = sig["score"].to_numpy(float).copy()
    score[~(lo | hi)] = np.nan
    return pd.DataFrame({"pred": pred, "cand": cand, "score": score})


def describe(m):
    return json.dumps(info(m), ensure_ascii=False)
