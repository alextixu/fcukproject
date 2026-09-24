#!/usr/bin/env python3
"""把 docs/ 產生的三個頁面複製進 site/,補上 UTF-8 宣告與回首頁連結。用法: python3 build.py"""
import os, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = {"aexgb.html": "docs/aexgb_architecture.html", "chartgcn.html": "docs/chartgcn_architecture.html",
       "daily.html": "backtest/report/out/daily_page.html"}
HEAD = ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head><body>\n')
NAV = ('<div style="max-width:1040px;margin:0 auto 18px;padding-inline:16px;font-size:14px;'
       'font-family:system-ui,sans-serif"><a href="index.html" style="color:#1B5FA8;text-decoration:none">'
       '← 回專題首頁</a></div>\n')
for dst, rel in SRC.items():
    s = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    if s.lstrip().lower().startswith("<!doctype"):                       # 已是完整 HTML(每日選股頁)
        out = s.replace("<body>", "<body>\n" + NAV, 1) if "<body>" in s else NAV + s
        if "charset" not in out[:400].lower():
            out = out.replace("<head>", '<head><meta charset="utf-8">', 1)
    else:                                                                # 片段(Artifact 格式):自己包一層
        out = HEAD + NAV + s + "\n</body></html>\n"
    open(os.path.join(HERE, dst), "w", encoding="utf-8").write(out)
    print(f"{dst:14s} {len(out)//1024:4d} KB  ← {rel}")
