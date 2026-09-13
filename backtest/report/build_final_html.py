"""results/final_best.json + final_template.html → results/final_best.html(資料內嵌)。持股另算「已抱幾個交易日」。"""
import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
from common import paths as P  # noqa: E402

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(P.RESULTS, "final_best.json"), encoding="utf-8"))
cal = pd.to_datetime(pd.read_parquet(os.path.join(P.OFFICIAL, "2330.parquet"))["date"]).sort_values()
for win in ("full", "jul"):
    for h in d[win]["held"]:
        h["held_days"] = int(((cal > pd.Timestamp(h["buy_date"])) & (cal <= pd.Timestamp(h["last_date"]))).sum())
Y = json.load(open(os.path.join(P.NCKU, "out", "summary_years.json"), encoding="utf-8"))
d["years"] = {y: {k: ({kk: vv for kk, vv in v.items() if kk != "curve"} if isinstance(v, dict) else v) for k, v in r.items()} for y, r in Y.items()}
d["years_model"] = json.load(open(os.path.join(P.NCKU, "out", "years_model.json"), encoding="utf-8"))
tpl = open(os.path.join(HERE, "final_template.html"), encoding="utf-8").read()
html = tpl.replace("/*__DATA__*/null", json.dumps(d, ensure_ascii=False, separators=(",", ":")))
fp = os.path.join(P.RESULTS, "final_best.html")
open(fp, "w", encoding="utf-8").write(html)
print("[SAVED]", fp, len(html) // 1024, "KB;持股", [(h["name"], h["held_days"]) for h in d["full"]["held"]])
