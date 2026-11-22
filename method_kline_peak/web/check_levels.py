"""信心等級要不要留:用回放資料(data/tw200 的每日存檔與 5 天後的答案)檢查各等級的命中率有沒有差別(不跑新實驗)。

信心等級 = 分數(OC-SVM decision 值)在訓練期同類判斷裡的三分位(高 ≥ 2/3 分位、中 ≥ 1/3 分位、其餘低;切點存在模型檔 cuts)。
事先定好的規則:判低點、判高點兩類都要「高 > 中 > 低」而且三個等級的命中率卡方檢定 p < 0.05,才保留信心等級;否則拿掉。
主要看推薦範圍(台灣 50,和成績追蹤同一群);另外列計算範圍全部股票(池外 + 台灣 50)當參考。
用法: python method_kline_peak/web/check_levels.py   → samples/level_check.json
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
from scipy.stats import chi2_contingency  # noqa: E402

from system import config as C, model as MD, store as ST, universe as U  # noqa: E402

KINDS = {"low": "判低點", "high": "判高點"}


def rates(t, kind):
    out = {}
    for lv in MD.LEVELS:
        g = t[t.lv == lv]
        out[lv] = {"n": int(len(g)), "hits": int((g.truth == kind).sum()),
                   "pct": round(float((g.truth == kind).mean() * 100), 1) if len(g) else None}
    tab = np.array([[out[lv]["hits"], out[lv]["n"] - out[lv]["hits"]] for lv in MD.LEVELS])
    p = float(chi2_contingency(tab)[1]) if (tab.sum(axis=0) > 0).all() else 1.0
    mono = out["高"]["pct"] is not None and out["中"]["pct"] is not None and out["低"]["pct"] is not None \
        and out["高"]["pct"] > out["中"]["pct"] > out["低"]["pct"]
    return {"等級": out, "卡方 p": round(p, 4), "高 > 中 > 低": bool(mono), "有差": bool(mono and p < 0.05)}


def main():
    C.set_profile("tw200", 0.0)
    tab = ST.table()
    tab = tab[tab.pred.isin(list(KINDS)) & tab.truth.notna()].copy()
    models = {}
    lv = []
    for r in tab.itertuples():
        y = int(r.date[:4])
        m = models.get(y) or models.setdefault(y, MD.load(y))
        lv.append(MD.level(r.score, m["cuts"][r.pred]))
    tab["lv"] = lv
    out = {"期間": [tab.date.min(), tab.date.max()], "切點(訓練期三分位)": {y: m["cuts"] for y, m in models.items()}}
    for name, t in (("台灣 50", tab[tab.status == U.POOL]), ("全部(台灣 50 + 池外)", tab[tab.status.isin([U.POOL, U.OUT])])):
        out[name] = {KINDS[k]: rates(t[t.pred == k], k) for k in KINDS}
    keep = all(out["台灣 50"][KINDS[k]]["有差"] for k in KINDS)
    out["結論"] = "保留信心等級" if keep else "拿掉信心等級(各等級命中率沒有明顯差別)"
    print(json.dumps(out, ensure_ascii=False, indent=1))
    with open(os.path.join(C.WEB, "samples", "level_check.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
