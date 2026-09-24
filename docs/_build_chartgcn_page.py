# -*- coding: utf-8 -*-
"""
Chart-GCN 架構圖頁產生器。執行: python3 docs/_build_chartgcn_page.py
版本、各站說明與疑慮狀態都在 _chartgcn_state.json; 每次改完程式或跑完實驗就改那個檔再重建。
輸出 chartgcn_architecture.html (發佈成 artifact, 路徑不變網址就不變)。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
state = json.load(open(os.path.join(HERE, "_chartgcn_state.json"), encoding="utf-8"))
tpl = open(os.path.join(HERE, "_chartgcn_page_template.html"), encoding="utf-8").read()
page = tpl.replace("/*STATE*/", json.dumps(state, ensure_ascii=False).replace("</", "<\\/"))
open(os.path.join(HERE, "chartgcn_architecture.html"), "w", encoding="utf-8").write(page)
print("wrote chartgcn_architecture.html", state["current"], len(page) // 1024, "KB")
