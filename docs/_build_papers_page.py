# -*- coding: utf-8 -*-
"""
文獻對照頁產生器。執行: python3 docs/_build_papers_page.py
讀 2026-09-20_文獻摘要與對照_24篇.md,輸出單檔 papers_page.html(發佈成 artifact 用)。
需要系統 python 的 markdown 套件(.venv 裡沒有)。
"""
import html
import json
import os
import re

import markdown

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "2026-09-20_文獻摘要與對照_24篇.md")
OUT = os.path.join(HERE, "papers_page.html")

CATS = {"A": "自編碼器", "B": "選股模型", "C": "XGBoost 與特徵篩選", "D": "綜述與方法論"}
# level: 5 高 / 4 中高 / 3 中 / 2 中偏低 / 1 低
LEVELS = {5: "高", 4: "中高", 3: "中", 2: "中偏低", 1: "低"}

# (標題開頭, 簡稱, 分類, 相近, 附註, 讀取, 期刊, DOI, [(免費版標籤, 網址)], 一句話)
PAPERS = [
    ("Fischer & Krauss (2018)", "Fischer & Krauss 2018", "B", 5, "", "全文(工作論文版)",
     "European Journal of Operational Research", "10.1016/j.ejor.2017.11.054",
     [("工作論文版", "https://econpapers.repec.org/paper/zbwiwqwdp/112017.htm")],
     "標籤同為「是否高於橫斷面中位數」,同樣每天排名買前幾名;準確率 52.4~54.3%;2010 年後扣成本只能持平。"),
    ("Krauss, Do & Huck (2017)", "Krauss, Do & Huck 2017", "B", 5, "", "全文(工作論文版)",
     "European Journal of Operational Research", "10.1016/j.ejor.2016.10.031",
     [("工作論文版 PDF", "https://www.iwf.rw.fau.de/files/2016/03/03-2016.pdf")],
     "和上一篇同一框架,而且直接比了梯度提升樹:樹模型贏 DNN;2010~2015 扣成本後所有模型年化為負。"),
    ("Nobre & Neves (2019)", "Nobre & Neves 2019", "C", 5, "", "全文(碩論版)",
     "Expert Systems with Applications", "10.1016/j.eswa.2019.01.083",
     [("碩論版 PDF", "https://fenix.tecnico.ulisboa.pt/downloadFile/844820067125485/Tese.pdf")],
     "技術指標 → PCA 降維 → XGBoost → 含成本回測,依時間切分;測試準確率 51~53%,和我們同一水準。"),
    ("Chong, Han & Park (2017)", "Chong, Han & Park 2017", "A", 5, "", "全文(作者接受稿)",
     "Expert Systems with Applications", "10.1016/j.eswa.2017.04.030",
     [("作者接受稿(存檔)", "https://web.archive.org/web/20230607224418/https://dro.dur.ac.uk/21533/1/21533.pdf")],
     "韓國 38 檔股票上,自編碼器、PCA、RBM 三種降維都沒贏過原始特徵;深度模型在測試集只略勝線性模型。"),
    ("Htun, Biehl & Petkov (2023)", "Htun, Biehl & Petkov 2023", "C", 5, "方法依據", "全文",
     "Financial Innovation", "10.1186/s40854-022-00441-7",
     [("開放取用全文", "https://pmc.ncbi.nlm.nih.gov/articles/PMC9834034/")],
     "特徵篩選綜述。我們漏斗的四層(去共線、重要性排序、RFE、自編碼器)都對得上它的分類。"),
    ("Bailey, Borwein", "Bailey 等 2017", "D", 5, "方法依據", "全文(作者修訂稿)",
     "Journal of Computational Finance", "10.21314/JCF.2016.322",
     [("作者網站 PDF", "https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf")],
     "提出回測過擬合機率 PBO;列出單一保留期的五個缺點,直接支持「+258% 為樣本內、不可外推」。"),
    ("Harvey, Liu & Zhu (2016)", "Harvey, Liu & Zhu 2016", "D", 5, "方法依據", "全文(NBER 版)",
     "Review of Financial Studies", "10.1093/rfs/hhv059",
     [("NBER 工作論文 PDF", "https://www.nber.org/system/files/working_papers/w20592/w20592.pdf")],
     "試得越多,顯著門檻越高(t 值要大於 3.0);自己保留的一段測試期不算真正的樣本外。"),
    ("Gunduz (2021)", "Gunduz 2021", "A", 4, "", "全文",
     "Financial Innovation", "10.1186/s40854-021-00243-3",
     [("開放取用全文", "https://doi.org/10.1186/s40854-021-00243-3")],
     "技術指標 → VAE 降維 → RFE → 樹模型,流程最像;降維後準確率沒有變好;66~68% 的準確率存疑。"),
    ("Feng, He, Wang", "Feng 等 2019", "B", 4, "", "全文(arXiv 版)",
     "ACM Transactions on Information Systems", "10.1145/3309547",
     [("arXiv PDF", "https://arxiv.org/pdf/1809.09441")],
     "把選股當排序題,每天買第 1 名。各方法預測誤差幾乎一樣但報酬差很多;跑 5 次的結果很不穩。"),
    ("Jiang (2021)", "Jiang 2021(綜述)", "D", 4, "", "全文(arXiv 版)",
     "Expert Systems with Applications", "10.1016/j.eswa.2021.115537",
     [("arXiv PDF", "https://arxiv.org/pdf/2003.01859")],
     "124 篇的綜述,用四步驟流程分類。點名的通病:忽略交易成本、很少做顯著性檢定、難重現。"),
    ("Gu, Kelly & Xiu (2020)", "Gu, Kelly & Xiu 2020", "B", 3, "", "全文(NBER 版)",
     "Review of Financial Studies", "10.1093/rfs/hhaa009",
     [("NBER 工作論文 PDF", "https://www.nber.org/system/files/working_papers/w25398/w25398.pdf")],
     "美股 60 年月資料。樹模型和神經網路同一級;最重要的特徵是動能、流動性、波動。"),
    ("Jiang, Kelly & Xiu (2023)", "Jiang, Kelly & Xiu 2023", "B", 3, "", "全文(工作論文版)",
     "Journal of Finance", "10.1111/jofi.13268",
     [("工作論文版 PDF", "https://www.aidf.nus.edu.sg/wp-content/uploads/2022/02/Xiu-Re-Imagining-Price-Trends.pdf")],
     "K 線影像餵 CNN,樣本外準確率只有 52.5~53.6%;大型股效果弱;關鍵訊號就是我們的 close_pos。"),
    ("Bao, Yue & Rao (2017)", "Bao, Yue & Rao 2017", "A", 3, "", "全文",
     "PLoS ONE", "10.1371/journal.pone.0180944",
     [("開放取用全文", "https://doi.org/10.1371/journal.pone.0180944")],
     "技術指標 → 小波 → 堆疊自編碼器 → LSTM。年報酬 45~64% 沒有天真基準,需保留看待。"),
    ("Sezer, Gudelek & Ozbayoglu (2020)", "Sezer 等 2020(綜述)", "D", 3, "", "全文(arXiv 版)",
     "Applied Soft Computing", "10.1016/j.asoc.2020.106181",
     [("arXiv PDF", "https://arxiv.org/pdf/1911.13288")],
     "140 篇的目錄式綜述。作者自己寫「DL 與傳統 ML 常表現相當」「準確率高不等於獲利」。"),
    ("Patel, Shah", "Patel 等 2015", "B", 3, "反面教材", "全文",
     "Expert Systems with Applications", "10.1016/j.eswa.2014.07.040", [],
     "指標轉成 ±1 後準確率 90%。但切分是隨機抽樣、不是按時間,極可能有資料洩漏。"),
    ("Yun, Yoon & Won (2021)", "Yun, Yoon & Won 2021", "C", 3, "", "只讀摘要",
     "Expert Systems with Applications", "10.1016/j.eswa.2021.115716", [],
     "67 個技術指標 → 基因演算法選特徵 → XGBoost,預測韓國指數隔日漲跌。數字未核對。"),
    ("Basak, Kar", "Basak 等 2019", "C", 3, "反面教材", "只讀摘要",
     "North American Journal of Economics and Finance", "10.1016/j.najef.2018.06.013",
     [("前身論文(不是同一篇)", "https://arxiv.org/abs/1605.00003")],
     "隨機森林 + XGBoost 預測 n 日後漲跌。前身論文的 85~95% 準確率疑似重疊標籤造成的洩漏。"),
    ("Sezer & Ozbayoglu (2018)", "Sezer & Ozbayoglu 2018", "B", 3, "", "只讀摘要",
     "Applied Soft Computing", "10.1016/j.asoc.2018.04.024",
     [("作者程式碼", "https://github.com/omerbsezer/CNN-TA")],
     "15 種指標 × 15 種參數排成 15×15 影像餵 CNN,分買/持有/賣三類。數字未核對。"),
    ("Hoseinzade & Haratizadeh (2019)", "CNNpred 2019", "B", 2, "", "全文(arXiv 版)",
     "Expert Systems with Applications", "10.1016/j.eswa.2019.03.029",
     [("arXiv", "https://arxiv.org/abs/1810.08923")],
     "82 個特徵的 CNN 預測美股指數隔日方向;平均 macro-F1 全部低於 0.5,沒有交易回測。"),
    ("Chen, Leung & Daouk (2003)", "Chen, Leung & Daouk 2003", "B", 2, "台股", "全文",
     "Computers & Operations Research", "10.1016/S0305-0548(02)00037-0",
     [("SSRN 工作論文版", "https://doi.org/10.2139/ssrn.237038")],
     "用總經變數預測台股大盤 3~12 個月方向(月頻擇時);作者自己說結果「異常地強」。"),
    ("Gu, Kelly & Xiu (2021)", "Gu, Kelly & Xiu 2021", "A", 1, "", "只讀摘要",
     "Journal of Econometrics", "10.1016/j.jeconom.2020.07.009", [],
     "自編碼器本身就是資產定價模型,用途和我們「先降維再餵分類器」不同。"),
    ("Heaton, Polson & Witte (2017)", "Heaton, Polson & Witte 2017", "A", 1, "", "全文(arXiv 版)",
     "Applied Stochastic Models in Business and Industry", "10.1002/asmb.2209",
     [("arXiv 1602.06561", "https://arxiv.org/abs/1602.06561"), ("arXiv 1605.07230", "https://arxiv.org/abs/1605.07230")],
     "用自編碼器的還原誤差挑股票來追蹤指數;概念文,沒有績效數字。"),
    ("Chen & Guestrin (2016)", "Chen & Guestrin 2016", "C", 1, "必引・會議論文", "全文(arXiv 版)",
     "KDD '16(ACM SIGKDD 會議)", "10.1145/2939672.2939785",
     [("arXiv PDF", "https://arxiv.org/pdf/1603.02754")],
     "XGBoost 的出處。賣點是快、能處理大資料,不是比別的梯度提升更準。內附我們超參數的對照表。"),
    ("Hinton & Salakhutdinov (2006)", "Hinton & Salakhutdinov 2006", "A", 1, "必引", "全文",
     "Science", "10.1126/science.1127647",
     [("作者網站 PDF", "https://www.cs.toronto.edu/~hinton/absps/science.pdf")],
     "自編碼器降維的出處。它證明的是「還原得比 PCA 好」,不是「壓完更好預測」。"),
]

URL_RE = re.compile(r"(?<![<(\[`])https?://[!-;=?-_a-~]+")


def autolink(md_text):
    def fix(m):
        u = m.group(0)
        tail = ""
        while u and (u[-1] in ".,;:" or (u[-1] == ")" and u.count("(") < u.count(")"))):
            tail = u[-1] + tail
            u = u[:-1]
        return "<" + u + ">" + tail
    return URL_RE.sub(fix, md_text)


def md_to_html(block):
    # python-markdown 的巢狀清單要 4 格縮排,原稿是 2 格
    lines = []
    for ln in block.splitlines():
        stripped = ln.lstrip(" ")
        lines.append(" " * (2 * (len(ln) - len(stripped))) + stripped)
    out = markdown.markdown(autolink("\n".join(lines)), extensions=["tables"])
    out = out.replace("<a href=", '<a target="_blank" rel="noopener" href=')
    return out.replace("<table>", '<div class="tbl"><table>').replace("</table>", "</table></div>")


def parse_blocks(text):
    text = text.split("## 總表與結論")[0]
    blocks = {}
    for part in re.split(r"^### ", text, flags=re.M)[1:]:
        head, _, body = part.partition("\n")
        body = re.split(r"^(?:## |---\s*$)", body, flags=re.M)[0]
        blocks[head.strip()] = body.strip()
    return blocks


def build():
    blocks = parse_blocks(open(SRC, encoding="utf-8").read())
    data = []
    for key, short, cat, lvl, note, read, journal, doi, free, one in PAPERS:
        heads = [h for h in blocks if h.startswith(key)]
        assert len(heads) == 1, (key, heads)
        head = heads[0]
        m = re.match(r"(.*?\(\d{4}\))\s*(.*)", head)
        data.append({
            "short": short, "title": m.group(2), "cat": cat, "lvl": lvl, "note": note,
            "read": read, "abstractOnly": read.startswith("只讀摘要"), "journal": journal,
            "doi": doi, "free": free, "one": one, "body": md_to_html(blocks[head]),
        })
    assert len(data) == 24
    page = TEMPLATE.replace("/*DATA*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    page = page.replace("/*CATS*/", json.dumps(CATS, ensure_ascii=False))
    page = page.replace("/*LEVELS*/", json.dumps(LEVELS, ensure_ascii=False))
    open(OUT, "w", encoding="utf-8").write(page)
    print("wrote", OUT, len(page) // 1024, "KB")


TEMPLATE = open(os.path.join(HERE, "_papers_page_template.html"), encoding="utf-8").read()

if __name__ == "__main__":
    build()
