# -*- coding: utf-8 -*-
"""
AE + XGBoost 流程圖頁產生器。執行: python3 docs/_build_aexgb_page.py
版本、各站說明與問題狀態都在 _aexgb_state.json; 每次改完系統或跑完實驗就改那個檔再重建。
輸出 aexgb_architecture.html (發佈成 artifact, 路徑不變網址就不變)。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
state = json.load(open(os.path.join(HERE, "_aexgb_state.json"), encoding="utf-8"))
ids = {c["id"] for c in state["concerns"]}
for v in state["versions"] + state["roadmap"]:
    missing = [i for i in v["concerns"] if i not in ids]
    assert not missing, f"{v['v']} 引用了不存在的問題編號 {missing}"
tpl = open(os.path.join(HERE, "_aexgb_page_template.html"), encoding="utf-8").read()
page = tpl.replace("/*STATE*/", json.dumps(state, ensure_ascii=False).replace("</", "<\\/"))
open(os.path.join(HERE, "aexgb_architecture.html"), "w", encoding="utf-8").write(page)
print("wrote aexgb_architecture.html", state["current"], len(page) // 1024, "KB")
