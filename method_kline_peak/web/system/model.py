"""正式模型:訓練、存檔、推論。

- 用在 Y 年的模型 = 研究 walk-forward 的 Y 年模型:股票池 pool_for_year(Y)(設定值 config.POOL),訓練 Y−4 ~ Y−1,
  訓練期最後 5 個交易日剔除(標籤會看到 Y 年),種子 42,訓練門檻 config.TRAIN_MIN_AMP(預設 0%)。
- 每組設定(股票池 + 門檻)的模型分開存在 data/<設定>/models/。
  主軸 = walkforward.MainlineSource;Stacking = stacking.StackingSource("lr", "score")。程式碼直接引用研究的類別。
- 訓練要用到 Y 年至少 5 個交易日的資料(剔除規則要知道 Y 年第一天在哪),所以 1 月第 6 個交易日之後才能重訓;
  在那之前沿用 Y−1 年的模型。
- 信心等級:訓練期內,模型判高點 / 低點的分數切三等分(高 / 中 / 低)。各等級的命中率由成績追蹤的實際對答案算出來。
"""
import json
import os
import time

import joblib
import numpy as np
import pandas as pd
import torch

from . import config as C
from .features import CODE2KIND
from .universe import pool_for_year
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import stacking as S  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402

LEVELS = ("高", "中", "低")


def model_path(year):
    return C.profile_dir("models", f"model_{year}.joblib")


class NotEnoughData(Exception):
    pass


def _cuts(scores):
    s = np.asarray(scores, dtype=float)
    if len(s) < 3:
        return [float("inf"), float("inf")]
    return [float(np.quantile(s, 2 / 3)), float(np.quantile(s, 1 / 3))]


def level(score, cuts):
    if score is None or not np.isfinite(score):
        return None
    return "高" if score >= cuts[0] else "中" if score >= cuts[1] else "低"


def training_set(year, store):
    """year 年模型的訓練資料:(訓練期 panel, 特徵欄, 股票池)。訓練門檻 config.TRAIN_MIN_AMP > 0 時,
    兩邊幅度未達門檻的高點 / 低點在訓練時改成非極值(walkforward.relabel,同研究的 --train-min-amp)。"""
    pool = pool_for_year(year, store)
    data = store.load_many(pool, end=f"{year}-01-31")
    data = {tk: df.loc[ML.START:] for tk, df in data.items() if len(df) >= 250}
    first = [df.index[df.index.year == year] for df in data.values()]
    if sum(len(f) >= C.HOLD for f in first) < len(data) * 0.8:
        raise NotEnoughData(f"{year} 年的交易日還不到 {C.HOLD} 天,先沿用 {year - 1} 年的模型")
    panel, fc = ML.build_panel(data, 6, [])
    tr = WF.relabel(WF.year_split(panel, year, C.TRAIN_YEARS)["train"], C.TRAIN_MIN_AMP)
    return tr, fc, list(data)                                                 # 保持 TICKER_SETS 順序(同研究)


def train(year, store, log=print):
    """訓練 year 年要用的模型並存檔;回傳模型 dict。"""
    t0 = time.time()
    tr, fc, pool = training_set(year, store)
    log(f"訓練 {year} 年模型({C.profile()}):{len(pool)} 檔,{tr.date.min().date()} ~ {tr.date.max().date()},{len(tr):,} 筆,"
        f"訓練門檻 {C.TRAIN_MIN_AMP:g}%")
    main = WF.MainlineSource(C.SEED)
    main.fit(tr, fc)
    stack = S.StackingSource("lr", "score", seed=C.SEED)
    stack.fit(tr, fc)
    m = {"main": main, "stack": stack, "fc": fc, "pool": pool, "year": year, "profile": C.profile(),
         "pool_name": C.POOL, "train_min_amp": C.TRAIN_MIN_AMP,
         "train": [str(tr.date.min().date()), str(tr.date.max().date())], "n_train": len(tr),
         "created": time.strftime("%Y-%m-%d %H:%M")}
    ins = predict(m, tr)                                                      # 訓練期內的分數 → 信心等級切點
    _, B = S.split_base_meta(tr, 1)
    ins_b = predict(m, B)
    m["cuts"] = {"main": {k: _cuts(ins.loc[ins.main_pred == k, "main_score"]) for k in ("low", "high")},
                 "stack": {k: _cuts(ins_b.loc[ins_b.stack_pred == k, "stack_score"]) for k in ("low", "high")}}
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
    if m is not None:
        return m
    try:
        return train(year, store, log)
    except NotEnoughData as e:
        log(str(e))
        prev = load(year - 1)
        return prev if prev is not None else train(year - 1, store, log)


def info(m):
    return {"year": m["year"], "train": m["train"], "n_train": m["n_train"], "n_pool": len(m["pool"]),
            "created": m["created"], "seed": C.SEED, "pool_name": m.get("pool_name", "tw100"),
            "train_min_amp": m.get("train_min_amp", 0.0)}


def predict(m, frame):
    """frame:features.live_frame 的列(可以多檔多天)。回傳同順序的 DataFrame:
    main_pred / main_score / main_s_high / main_s_low,stack_pred / stack_score / stack_p_low / stack_p_none / stack_p_high。
    pred 為 low / high / none。主軸分數 = 該類 OC-SVM 的 decision_function(只在同類候選間比大小);
    main_s_high / main_s_low = 兩個 OC-SVM 對這一天的 decision_function(> 0 = 在範圍內),不論是不是候選。"""
    if not len(frame):
        return pd.DataFrame()
    fc = m["fc"]
    frame = frame.reset_index(drop=True)
    torch.set_num_threads(max(1, torch.get_num_threads()))
    sig = m["main"].predict(frame)
    out = pd.DataFrame({"main_pred": [CODE2KIND[int(p)] for p in sig.pred], "main_score": sig.score.to_numpy()})
    out.loc[out.main_pred == "none", "main_score"] = np.nan
    for cls, tag in ((DOWN, "high"), (UP, "low")):
        mm = m["main"].models[cls]
        X = np.clip(mm["sc"].transform(frame[fc].fillna(mm["med"])), -5, 5).astype(np.float32)
        with torch.no_grad():
            z = mm["ae"].encode(torch.FloatTensor(X)).numpy()
        out[f"main_s_{tag}"] = mm["ocs"][WF.NU].decision_function(z)
    st = m["stack"]
    F = st.base.transform(frame)
    Xs = st.meta.fsc.transform(F[S.INPUTS[st.meta.inputs]].to_numpy())
    proba = st.meta.model.predict_proba(Xs)
    pred = st.meta.model.predict(Xs)
    cls_idx = {c: i for i, c in enumerate(st.meta.model.classes_)}
    out["stack_pred"] = [CODE2KIND[int(p)] for p in pred]
    for c, tag in ((UP, "low"), (FLAT, "none"), (DOWN, "high")):
        out[f"stack_p_{tag}"] = proba[:, cls_idx[c]]
    out["stack_score"] = proba.max(axis=1)
    out.loc[out.stack_pred == "none", "stack_score"] = np.nan
    return out


def describe(m):
    return json.dumps(info(m), ensure_ascii=False)
