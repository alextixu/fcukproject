#!/usr/bin/env bash
# 專題網站(內網):http://192.168.1.52:8000  ;停止:pkill -f "site/serve.py"
cd "$(dirname "$0")"
exec python3 serve.py 8000
