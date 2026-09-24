#!/usr/bin/env python3
"""簡易靜態伺服器,強制以 UTF-8 送出 HTML(python -m http.server 不會指定編碼 → 中文變亂碼)。"""
import functools, os, sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class H(SimpleHTTPRequestHandler):
    def guess_type(self, path):
        t = super().guess_type(path)
        return t + "; charset=utf-8" if t in ("text/html", "text/plain", "text/css", "application/javascript") else t


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
os.chdir(os.path.dirname(os.path.abspath(__file__)))
print(f"serving http://0.0.0.0:{port}", flush=True)
ThreadingHTTPServer(("0.0.0.0", port), functools.partial(H, directory=os.getcwd())).serve_forever()
