"""把 site/ 打包成 claude.ai Artifact 要發布的資料夾(dist/,不進 git)。

Artifact 發布時會自己包上 <!doctype html><html><head><body>,所以 index.html 只放頁面內容:
title、viewport-fit-sides meta、樣式表連結、site/index.html 裡 page:start ~ page:end 之間的內容、app.js。
其餘檔案(style.css、app.js、data/*.json、data/img/*.png)原樣複製,前端用相對路徑讀。
用法:先 run.py publish(或 daily),再 python method_kline_peak/web/build_artifact.py
"""
import os
import re
import shutil
import sys

WEB = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(WEB, "site")
DIST = os.path.join(WEB, "dist")


def build(dist=DIST):
    if not os.path.exists(os.path.join(SITE, "data", "meta.json")):
        sys.exit("site/data 還沒有資料,請先執行 run.py publish")
    if os.path.exists(dist):
        shutil.rmtree(dist)
    os.makedirs(dist)
    html = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
    body = re.search(r"<!-- page:start.*?-->(.*?)<!-- page:end -->", html, re.S).group(1).strip()
    page = "\n".join(['<title>K 線高低點判斷</title>',
                      '<meta name="claude:viewport-fit-sides" content="cover">',
                      '<link rel="stylesheet" href="style.css">',
                      body,
                      '<script src="app.js"></script>', ""])
    open(os.path.join(dist, "index.html"), "w", encoding="utf-8").write(page)
    for f in ("style.css", "app.js"):
        shutil.copy(os.path.join(SITE, f), os.path.join(dist, f))
    shutil.copytree(os.path.join(SITE, "data"), os.path.join(dist, "data"))
    files = sorted(os.path.relpath(os.path.join(r, f), dist).replace(os.sep, "/")
                   for r, _, fs in os.walk(dist) for f in fs if f != "index.html")
    size = sum(os.path.getsize(os.path.join(dist, f)) for f in files)
    print(f"{dist}:index.html + {len(files)} 個檔案,共 {size / 1e6:.1f} MB")
    return files


if __name__ == "__main__":
    build()
