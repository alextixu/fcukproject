"""每日判斷與對答案的存檔。兩種檔案都是「寫過就不再改」:用獨佔建立(open 'x'),檔案已存在就不寫。

  data/<設定>/days/<日期>.json     當天收盤後的判斷(所有計算的股票),之後不重算
  data/<設定>/grades/<日期>.json   t+5 收盤後的答案(每檔:真實類別、t+1 開 → t+5 收 扣成本報酬)
  <設定> = 股票池 + 訓練門檻,例:tw100、tw200_amp3(config.profile)
"""
import json
import os

import pandas as pd

from . import config as C


class AlreadyFrozen(Exception):
    pass


def _dir(kind):
    d = C.profile_dir(kind)
    os.makedirs(d, exist_ok=True)
    return d


def _write_once(path, obj):
    try:
        with open(path, "x", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), default=_default)
    except FileExistsError as e:
        raise AlreadyFrozen(path) from e


def _default(o):
    if hasattr(o, "item"):
        return o.item()
    if isinstance(o, pd.Timestamp):
        return str(o.date())
    raise TypeError(type(o))


def day_path(date):
    return os.path.join(_dir("days"), f"{pd.Timestamp(date).date()}.json")


def grade_path(date):
    return os.path.join(_dir("grades"), f"{pd.Timestamp(date).date()}.json")


def has_day(date):
    return os.path.exists(day_path(date))


def has_grade(date):
    return os.path.exists(grade_path(date))


def write_day(day):
    """day = {"date", "created", "source", "model", "rows": [...]}。已存在就丟 AlreadyFrozen。"""
    _write_once(day_path(day["date"]), day)


def write_grade(date, grades):
    _write_once(grade_path(date), {"date": str(pd.Timestamp(date).date()), "grades": grades})


def read_day(date):
    with open(day_path(date), encoding="utf-8") as f:
        return json.load(f)


def read_grade(date):
    p = grade_path(date)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)["grades"]


def list_days():
    return sorted(f[:-5] for f in os.listdir(_dir("days")) if f.endswith(".json"))


def table():
    """所有存檔攤平成一張表:每列 = 一天 × 一檔,含判斷與答案(還沒答案的為 NaN)。"""
    rows = []
    for d in list_days():
        day = read_day(d)
        g = read_grade(d) or {}
        for r in day["rows"]:
            m, s = r.get("main") or {}, r.get("stack") or {}
            a = g.get(r["code"]) or {}
            rows.append({"date": d, "source": day.get("source", "daily"), "code": r["code"], "status": r["status"],
                         "close": r.get("close"),
                         "main_pred": m.get("pred"), "main_score": m.get("score"), "main_level": m.get("level"),
                         "stack_pred": s.get("pred"), "stack_score": s.get("score"), "stack_level": s.get("level"),
                         "truth": a.get("truth"), "ret_pct": a.get("ret_pct")})
    return pd.DataFrame(rows)
