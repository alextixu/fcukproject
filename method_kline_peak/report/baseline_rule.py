"""只用規則 vs 主軸(168 檔、walk-forward 2024 / 2025 / 2026、種子 42、門檻 0%;不改模型)。

規則 = 主軸的規則候選直接當判斷(walkforward.RuleSource):t 收盤是最近 6 天最高 → 判高點、最低 → 判低點,其餘非極值。
主軸判斷取自 backtest_strategies 的每日判斷快取(每年先核對 confusion_2024_2026_tw200.json)。
隨機基準 = 依真實類別占比隨機猜:每類的找到率 = 命中率 = 該類占比(期望值),macro-F1 = 三類占比平均 = 33.3%。
另算主軸相對規則:判的天數少了多少(%)、命中率提升幾個百分點、找到率少了幾個百分點(高、低各自)。
用法: python method_kline_peak/report/baseline_rule.py
輸出: results/baseline_rule_vs_mainline_2024_2026.json
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import backtest_strategies as BS  # noqa: E402
from confusion import summarize  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402
from paper_aeocsvm import NAMES  # noqa: E402

YEARS = (2024, 2025, 2026)
OUT = os.path.join(ML.OUT, "baseline_rule_vs_mainline_2024_2026.json")


def metrics(y, p):
    s = summarize(y, p, NAMES)
    r = {"macro_f1": round(s["macro_f1"] * 100, 2), "天數": int(len(y)),
         "判反": int(((p == UP) & (y == DOWN)).sum() + ((p == DOWN) & (y == UP)).sum())}
    for cls, nm in ((UP, "低點"), (DOWN, "高點")):
        r[nm] = {"真": int((y == cls).sum()), "判": int((p == cls).sum()), "對": int(((p == cls) & (y == cls)).sum()),
                 "找到率": round(s["recall"][nm] * 100, 1), "命中率": round((s["precision"][nm] or 0) * 100, 1)}
    r["判高低合計天數"] = r["低點"]["判"] + r["高點"]["判"]
    r["_cm"] = s[BS.KEY]
    return r


def random_base(y):
    share = {nm: float((y == c).mean()) for c, nm in ((UP, "低點"), (FLAT, "非極值"), (DOWN, "高點"))}
    return {"說明": "依真實類別占比隨機猜的期望值:找到率 = 命中率 = 占比", "macro_f1": round(np.mean(list(share.values())) * 100, 2),
            **{nm: {"占比_找到率_命中率": round(v * 100, 1)} for nm, v in share.items()}}


def gain(main, rule):
    out = {"判高低天數_少了_pct": round((1 - main["判高低合計天數"] / rule["判高低合計天數"]) * 100, 1),
           "macro_f1_提升_百分點": round(main["macro_f1"] - rule["macro_f1"], 2)}
    for nm in ("低點", "高點"):
        out[nm] = {"判的天數_少了_pct": round((1 - main[nm]["判"] / rule[nm]["判"]) * 100, 1),
                   "命中率_提升_百分點": round(main[nm]["命中率"] - rule[nm]["命中率"], 1),
                   "找到率_少了_百分點": round(rule[nm]["找到率"] - main[nm]["找到率"], 1)}
    return out


def main():
    data = ML.load_data(pool=BS.POOL)
    panel, fc = ML.build_panel(data, 6, [])
    main_sig = BS.load_signals(YEARS, data)
    ref = json.load(open(os.path.join(ML.OUT, "confusion_2024_2026_tw200.json"), encoding="utf-8"))
    res = {"pool": BS.POOL, "n_stocks": len(data), "years": {}}
    ys, rs, ms = [], [], []
    for y in YEARS:
        rule, _ = WF.run_year(panel, fc, y, WF.RuleSource())
        m = main_sig[main_sig.date.dt.year == y]
        assert (rule["date"].to_numpy() == m["date"].to_numpy()).all() and (rule["ticker"].to_numpy() == m["ticker"].to_numpy()).all()
        yy = m["y"].to_numpy()
        e = {"規則": metrics(yy, rule["pred"].to_numpy()), "主軸": metrics(yy, m["pred"].to_numpy()), "隨機": random_base(yy)}
        assert e["主軸"]["_cm"] == ref[str(y)]["主軸"][BS.KEY], y
        e["主軸相對規則"] = gain(e["主軸"], e["規則"])
        res["years"][str(y)] = e
        ys.append(yy), rs.append(rule["pred"].to_numpy()), ms.append(m["pred"].to_numpy())
    yy = np.concatenate(ys)
    e = {"規則": metrics(yy, np.concatenate(rs)), "主軸": metrics(yy, np.concatenate(ms)), "隨機": random_base(yy)}
    e["主軸相對規則"] = gain(e["主軸"], e["規則"])
    res["years"]["合計"] = e
    for v in res["years"].values():
        for k in ("規則", "主軸"):
            v[k].pop("_cm")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(pd.DataFrame({y: {"規則 F1": v["規則"]["macro_f1"], "主軸 F1": v["主軸"]["macro_f1"], "隨機 F1": v["隨機"]["macro_f1"],
                            **{f"{k}": x for k, x in v["主軸相對規則"].items() if not isinstance(x, dict)}}
                        for y, v in res["years"].items()}).to_string())
    print(json.dumps({y: v["主軸相對規則"] for y, v in res["years"].items()}, ensure_ascii=False))
    print(OUT)


if __name__ == "__main__":
    main()
