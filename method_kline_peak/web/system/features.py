"""即時特徵與事後對答案。特徵、候選、標籤都直接用研究的函式(mainline.shape_features、paper_aeocsvm.paper_label)。

- live_frame:每一天的 29 個特徵 + 規則候選。只用 t−5 ~ t 的 K 線和到 t 為止的 10 日均量,
  所以最後一天(今天)也有特徵;研究的 build_panel 會丟掉還沒有標籤的最後 5 天,這裡不丟。
- grade:t+5 收盤後,用同一個標籤規則判斷 t 是不是真高點 / 低點,並算 t+1 開盤 → t+5 收盤的報酬(扣成本)。
"""
import numpy as np
import pandas as pd

from . import config as C
import mainline as ML  # noqa: E402
from feasibility import clean  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402
from paper_aeocsvm import paper_label  # noqa: E402

CODE2KIND = {UP: "low", DOWN: "high", FLAT: "none"}
KIND2CODE = {v: k for k, v in CODE2KIND.items()}
WINDOW = 6


def live_frame(ticker, df):
    """回傳 DataFrame[date, ticker, 29 個特徵, cand_hi, cand_lo, close, open];特徵不完整的天數丟掉。"""
    df = clean(df)
    if len(df) < C.MIN_BARS:
        return pd.DataFrame()
    feats = ML.shape_features(df, WINDOW, ML.VOL_MA).replace([np.inf, -np.inf], np.nan)
    _, cand_hi, cand_lo = paper_label(df["close"])
    out = feats.copy()
    out["cand_hi"], out["cand_lo"] = cand_hi.astype(bool), cand_lo.astype(bool)
    out["close"], out["open"] = df["close"], df["open"]
    out["ticker"] = ticker
    out = out[feats.notna().all(axis=1)]
    out.index.name = "date"
    return out.reset_index()


def feature_cols():
    return [c for c in ML.shape_features(pd.DataFrame({k: [1.0] * 20 for k in ("open", "high", "low", "close", "volume")}),
                                         WINDOW, ML.VOL_MA).columns]


def labels(df):
    """每一天的答案表:y(標籤,未滿 5 天為 NaN)、ret(t+1 開 → t+5 收 扣成本,%)、on(對答案那天 = t+5)。"""
    df = clean(df)
    y, _, _ = paper_label(df["close"])
    ret = (df["close"].shift(-C.HOLD) / df["open"].shift(-1) - 1) * 100 - C.COST_PCT
    on = pd.Series(df.index, index=df.index).shift(-C.HOLD)
    return pd.DataFrame({"y": y, "ret": ret, "on": on})


def grade_from(tab, date):
    date = pd.Timestamp(date)
    if tab is None or date not in tab.index:
        return {"truth": None, "ret_pct": None}
    r = tab.loc[date]
    if pd.isna(r.on):
        return {"truth": None, "ret_pct": None}
    return {"truth": None if pd.isna(r.y) else CODE2KIND[int(r.y)], "ret_pct": round(float(r.ret), 3),
            "graded_on": str(pd.Timestamp(r.on).date())}


def grade(df, date):
    """t = date 的答案。回傳 {"truth": low/high/none 或 None(未滿 5 天), "ret_pct": t+1 開 → t+5 收 扣成本(%)}。"""
    return grade_from(labels(df), date)
