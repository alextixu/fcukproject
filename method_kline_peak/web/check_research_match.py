"""確認網頁系統的模型和 final 分支的研究結果一致(不跑新實驗,只重現既有設定)。

比對三件事:
  1. 2026 年(1–9 月):網頁系統的正式模型(data/tw200/models/model_2026.joblib)對研究股票池 168 檔、2026 每一天判斷,
     混淆矩陣與 macro-F1 要等於 results/confusion_2024_2026_tw200.json 的 2026 年。
     另外用研究程式(walkforward.run_year + MainlineSource)重跑一次 2026,逐列比判斷與分數。
  2. 2024、2025 年:網頁系統用同一套程式訓練那兩年的模型(存在暫存資料夾,不碰正式存檔),混淆矩陣要等於結果檔。
  3. 網頁的回放存檔(data/tw200/days):168 檔 2026 年 1–9 月存下的判斷,和研究逐列比;不同的列附上原因(K 線不同)。
資料:1、2 用研究快取(common/cache/yf_2026,和 final 同一份);3 是網頁系統自己的 K 線快取算出來的存檔。
用法: python method_kline_peak/web/check_research_match.py
"""
import json
import os
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from system import config as C, model as MD, store as ST  # noqa: E402
from system.datasource import PriceStore, research_store  # noqa: E402
from system.features import KIND2CODE  # noqa: E402
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
from confusion import summarize  # noqa: E402
from paper_aeocsvm import NAMES  # noqa: E402

CM = "confusion_rows_true_cols_pred(漲,不漲不跌,跌)"


def ref_year(year):
    with open(os.path.join(C.RESULTS, "confusion_2024_2026_tw200.json"), encoding="utf-8") as f:
        return json.load(f)[str(year)]["主軸"]


def compare(year, te, pred_codes):
    s = summarize(te.y.to_numpy(), np.asarray(pred_codes), NAMES)
    ref = ref_year(year)
    return {"年": year, "測試股票日": len(te), "macro-F1": round(s["macro_f1"] * 100, 4),
            "結果檔 macro-F1": round(ref["macro_f1"] * 100, 4), "混淆矩陣": s[CM], "結果檔混淆矩陣": ref[CM],
            "完全相同": s[CM] == ref[CM] and abs(s["macro_f1"] - ref["macro_f1"]) < 1e-12,
            "高低點判反": int(s[CM][0][2] + s[CM][2][0])}


def main():
    C.set_profile("tw200", 0.0)
    out = {}
    prod = MD.load(2026)
    assert prod is not None and "src" in prod, "沒有正式模型,先跑 run.py train --year 2026 或 replay"
    data = ML.load_data(pool="tw200")                                     # 研究快取、168 檔、同順序
    assert list(data) == prod["pool"]
    panel, fc = ML.build_panel(data, 6, [])

    # 1. 2026:正式模型 vs 結果檔;研究程式重跑一次逐列比
    te = WF.year_split(panel, 2026)["test"]
    web = MD.predict(prod, te)
    out["2026_正式模型"] = compare(2026, te, web.pred.map(KIND2CODE))
    sig, _ = WF.run_year(panel, fc, 2026, WF.MainlineSource())
    cand = te.cand_hi.to_numpy() | te.cand_lo.to_numpy()
    out["2026_研究程式重跑_逐列"] = {
        "股票日": len(sig), "判斷相同": int((sig.pred.to_numpy() == web.pred.map(KIND2CODE).to_numpy()).sum()),
        "分數最大差距(候選)": float(np.abs(sig.score.to_numpy()[cand] - web.score.to_numpy()[cand]).max())}
    print(json.dumps(out, ensure_ascii=False), flush=True)

    # 2. 2024、2025:網頁系統的訓練程式(暫存資料夾)
    real = C.DATA
    C.DATA = tempfile.mkdtemp()
    try:
        for y in (2024, 2025):
            m = MD.train(y, PriceStore(), log=lambda *_: None)
            t = WF.year_split(panel, y)["test"]
            out[f"{y}_網頁訓練"] = compare(y, t, MD.predict(m, t).pred.map(KIND2CODE))
            print(json.dumps(out[f"{y}_網頁訓練"], ensure_ascii=False), flush=True)
    finally:
        C.DATA = real

    # 3. 網頁回放存檔(網頁自己的 K 線快取)vs 研究,168 檔 2026 年 1–9 月
    if ST.list_days():
        tab = ST.table()
        tab = tab[tab.pred.notna()]
        r = te[["date", "ticker", "y"]].assign(code=te.ticker.str.split(".").str[0], date=te.date.dt.strftime("%Y-%m-%d"),
                                              research=sig.pred.map({v: k for k, v in KIND2CODE.items()}).to_numpy())
        mg = r.merge(tab[["date", "code", "pred"]], on=["date", "code"], how="left")
        miss = mg.pred.isna()
        diff = mg[~miss & (mg.pred != mg.research)]
        st = PriceStore()
        why = {}
        for tk in sorted(set(diff.ticker) | set(mg.loc[miss, "ticker"])):
            a, b = st.load(tk), data[tk]
            a = a.loc[:b.index[-1]]
            only_r = [str(d.date()) for d in b.index.difference(a.index)]
            only_w = [str(d.date()) for d in a.index.difference(b.index)]
            com = a.index.intersection(b.index)
            rel = float((a.loc[com, "close"] / b.loc[com, "close"]).pipe(lambda x: x.max() / x.min() - 1))
            why[tk] = {"不同的列": int((diff.ticker == tk).sum()), "沒有存檔的列": int((mg.loc[miss, "ticker"] == tk).sum()),
                       "只有研究有的日子": only_r[:5], "只有網頁有的日子": only_w[:5], "還原比例變動": round(rel, 6)}
        ok = mg[~miss]
        s = summarize(ok.y.to_numpy(), ok.pred.map(KIND2CODE).to_numpy(), NAMES)
        out["網頁回放存檔_vs_研究"] = {"股票日": len(mg), "有存檔": int((~miss).sum()), "判斷相同": int((~miss).sum() - len(diff)),
                                "判斷不同": len(diff), "原因(K 線和研究快取不同)": why,
                                "混淆矩陣(研究標籤)": s[CM], "macro-F1": round(s["macro_f1"] * 100, 4)}
        print(json.dumps(out["網頁回放存檔_vs_研究"], ensure_ascii=False), flush=True)
    path = os.path.join(C.WEB, "samples", "research_match.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"記錄於 {path}")


if __name__ == "__main__":
    main()
