"""匯出 242 欄完整清單:分類、層級、需要的回看列數、程式位置與算式(取自原始碼)。
輸出 docs/2026-09-21_242欄特徵清單.csv 與 .md(每族群一張表)。"""
import os, re, sys
import pandas as pd

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(R, "method_xgb", "src"))
from features.lookback import required_rows

FDIR = os.path.join(R, "method_xgb", "src", "features")
cat = pd.read_csv(os.path.join(R, "method_xgb", "config", "feature_catalog_top100.csv"))
CAT_ZH = {"candle": "K 棒", "trend": "趨勢", "momentum": "動能", "volatility": "波動", "volume": "成交量", "event": "事件", "stats": "統計", "cross_section": "橫斷面"}

pats = []
for fn in sorted(os.listdir(FDIR)):
    if not fn.endswith(".py") or fn in ("__init__.py", "_util.py", "lookback.py", "chip.py"):
        continue
    for i, line in enumerate(open(os.path.join(FDIR, fn), encoding="utf-8"), 1):
        for m in re.finditer(r'(?:f|out)\[(f?)"([^"]+)"\]\s*=\s*(.+)|^\s*"([a-z_0-9]+)":\s*(.+?),?\s*$', line):
            key, expr = (m[2], m[3]) if m[2] else (m[4], m[5])
            rx = "^" + re.sub(r"\\\{[^}]*\\\}", r"[0-9a-z_]+", re.escape(key)) + "$"
            pats.append((re.compile(rx), fn, i, re.sub(r"\s+#.*$", "", expr.strip()), (re.search(r"#\s*(.+)$", line) or [None, ""])[1].strip()))

rows = []
for name, fam in zip(cat.name, cat.family):
    hit = [p for p in pats if p[0].match(name)]
    hit = sorted(hit, key=lambda p: -len(p[0].pattern))[:1]
    if not hit:
        stem = re.sub(r"\d+", "", name).rstrip("_")
        for fn_ in sorted(os.listdir(FDIR)):
            if fn_.endswith(".py") and fn_ not in ("__init__.py", "_util.py", "lookback.py", "chip.py"):
                for i_, line_ in enumerate(open(os.path.join(FDIR, fn_), encoding="utf-8"), 1):
                    if re.search(r'f"' + re.escape(stem.split("_")[0]) + r'[a-z_]*_\{', line_) and stem.split("_")[0] in line_:
                        hit = [(None, fn_, i_, line_.strip(), "同一行指定多個欄位")]; break
            if hit: break
    fn, ln, expr, note = (hit[0][1], hit[0][2], hit[0][3], hit[0][4]) if hit else ("(迴圈產生,見族群檔)", "", "", "")
    level = "同日常數(市場層級)" if name.startswith("mkt_") else "同日常數(日曆)" if name.startswith("dow_") else "橫斷面(當日池內比較)" if fam == "cross_section" else "個股"
    catzh = "市場層級" if name.startswith("mkt_") else CAT_ZH[fam]
    rows.append({"name": name, "category": catzh, "level": level, "lookback_rows": required_rows(name),
                 "code": f"features/{fn}:{ln}" if ln else fn, "expression": expr, "note": note})
df = pd.DataFrame(rows)
df.to_csv(os.path.join(R, "docs", "2026-09-21_242欄特徵清單.csv"), index=False)
L = ["# 242 欄特徵清單(2026-09-21 匯出)\n",
     "來源:`method_xgb/src/features/*.py`;算式欄是原始碼裡的那一行(c/o/h/l/v = 收開高低量,r = 日報酬,pc = 前一日收盤)。回看列數見 `features/lookback.py`,不足的列設為缺值。",
     "市場層級(mkt_roc_w)= 股票池內當日有報酬的股票之**等權平均日報酬**累乘後的 w 日報酬;這一輪股票池是 2026-08-31 市值前 100 大,所以就是這 100 檔的等權平均。\n",
     "| 分類 | 欄數 | 層級 |", "|---|---|---|"]
for k, g in df.groupby("category", sort=False):
    L.append(f"| {k} | {len(g)} | {'、'.join(sorted(set(g.level)))} |")
for k, g in df.groupby("category", sort=False):
    L += [f"\n## {k}({len(g)} 欄)\n", "| 欄位 | 回看列數 | 程式位置 | 算式(原始碼) | 說明 |", "|---|---|---|---|---|"]
    for _, r in g.iterrows():
        L.append(f"| `{r['name']}` | {r.lookback_rows} | {r.code} | `{r.expression[:110].replace('|', '/')}` | {r.note} |")
open(os.path.join(R, "docs", "2026-09-21_242欄特徵清單.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print(df.category.value_counts().to_dict()); print("找不到程式位置的:", df[df.expression == ""].name.tolist())
