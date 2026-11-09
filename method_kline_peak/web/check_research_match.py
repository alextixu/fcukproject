"""確認網頁系統的 Stacking 和研究版 TW200 模型輸出一致(2026-11-09 監督要求;不跑新實驗,只重現既有設定)。

比對三件事:
  1. 2026 年模型:研究程式(mainline.load_data(pool="tw200") → walkforward.year_split → stacking.StackingSource)訓練一份,
     和網頁系統的正式模型(data/tw200/models/model_2026.joblib)對台灣 50 這 50 檔、2026 每一天算三類機率,比最大差距。
  2. 2024 年:研究存下的南電每日輸出 results/outputs_8046_2024_tw200_amp0.csv(Stacking 判斷、最大機率,4 位小數),
     和網頁系統訓練的 2024 年模型比。
  3. 2025 年:研究存下的南電例子 results/lr_example_tw200_2025.json(三類機率,4 位小數),和網頁系統訓練的 2025 年模型比。
2、3 的模型訓練在暫存資料夾,不碰 data/ 的正式存檔。
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

from system import config as C, model as MD, universe as U  # noqa: E402
from system.datasource import PriceStore  # noqa: E402
from system.features import live_frame, KIND2CODE  # noqa: E402
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import stacking as S  # noqa: E402

ZH = {"低點": "low", "非極值": "none", "高點": "high"}


def probs(src, frame):
    F = src.base.transform(frame)
    X = src.meta.fsc.transform(F[S.INPUTS[src.meta.inputs]].to_numpy())
    p = src.meta.model.predict_proba(X)
    idx = {c: i for i, c in enumerate(src.meta.model.classes_)}
    return np.column_stack([p[:, idx[KIND2CODE[k]]] for k in ("low", "none", "high")])


def main():
    C.set_profile("tw200", 0.0)
    store = PriceStore()
    out = {}

    # 1. 2026:研究程式訓練 vs 正式模型,台灣 50 全部 50 檔、2026 每一天
    prod = MD.load(2026)
    assert prod is not None, "沒有正式模型,先跑 run.py daily 或 replay"
    data = ML.load_data(pool="tw200")
    panel, fc = ML.build_panel(data, 6, [])
    research = S.StackingSource("lr", "score")
    research.fit(WF.year_split(panel, 2026)["train"], fc)
    frames = []
    for tk in U.recommend_list():
        df = store.load(tk)
        fr = live_frame(tk, df.loc[:ML.END])
        frames.append(fr[fr.date >= "2026-01-01"])
    fr = pd.concat(frames, ignore_index=True)
    pa, pb = probs(research, fr), probs(prod["stack"], fr)
    diff = np.abs(pa - pb)
    same_pred = (pa.argmax(1) == pb.argmax(1)).mean()
    sample = fr.assign(r_low=pa[:, 0], r_none=pa[:, 1], r_high=pa[:, 2], w_low=pb[:, 0], w_none=pb[:, 1], w_high=pb[:, 2])
    pick = sample[sample.ticker.isin(["2330.TW", "8046.TW", "2412.TW", "2603.TW"]) &
                  sample.date.isin(pd.to_datetime(["2026-03-02", "2026-06-15", "2026-09-10"]))]
    out["2026_research_vs_web"] = {
        "股票數": int(fr.ticker.nunique()), "股票日數": len(fr), "日期": [str(fr.date.min().date()), str(fr.date.max().date())],
        "三類機率最大差距": float(diff.max()), "判斷相同比例": float(same_pred),
        "抽樣": [{"代號": r.ticker, "日期": str(r.date.date()),
                "研究 低/非極值/高": [round(r.r_low, 6), round(r.r_none, 6), round(r.r_high, 6)],
                "網頁 低/非極值/高": [round(r.w_low, 6), round(r.w_none, 6), round(r.w_high, 6)]} for r in pick.itertuples()]}
    print(json.dumps(out["2026_research_vs_web"], ensure_ascii=False, indent=1), flush=True)

    tmp = tempfile.mkdtemp()
    real = C.DATA
    C.DATA = tmp
    try:
        df8 = store.load("8046.TW")
        # 2. 2024:研究存的南電每日輸出(Stacking 判斷 + 最大機率,4 位小數)
        m24 = MD.train(2024, store, log=lambda *_: None)
        ref = pd.read_csv(os.path.join(C.RESULTS, "outputs_8046_2024_tw200_amp0.csv"), parse_dates=["date"])
        f8 = live_frame("8046.TW", df8.loc[:"2024-12-31"])
        f8 = f8[f8.date.isin(ref.date)].reset_index(drop=True)
        pr = MD.predict(m24, f8)
        got = pd.DataFrame({"date": f8.date, "pred": pr.stack_pred, "p": pr[["stack_p_low", "stack_p_none", "stack_p_high"]].max(axis=1)})
        mg = ref.merge(got, on="date")
        out["2024_outputs_csv"] = {"天數": len(mg), "判斷相同": int((mg["Stacking 邏輯迴歸 判斷"].map(ZH) == mg.pred).sum()),
                                   "最大機率差距(csv 4 位小數)": float((mg["Stacking 邏輯迴歸 分數"] - mg.p.round(4)).abs().max())}
        print(json.dumps(out["2024_outputs_csv"], ensure_ascii=False), flush=True)
        # 3. 2025:研究存的南電例子(三類機率,4 位小數)
        m25 = MD.train(2025, store, log=lambda *_: None)
        ex = json.load(open(os.path.join(C.RESULTS, "lr_example_tw200_2025.json"), encoding="utf-8"))
        f25 = live_frame("8046.TW", df8.loc[:"2025-12-31"]).set_index("date")
        rows = []
        for key, c in ex["cases"].items():
            d = pd.Timestamp(c["日期"])
            p = MD.predict(m25, f25.loc[[d]].reset_index()).iloc[0]
            mine = {"低點": round(p.stack_p_low, 4), "非極值": round(p.stack_p_none, 4), "高點": round(p.stack_p_high, 4)}
            rows.append({"例子": key, "日期": c["日期"], "研究": c["機率"], "網頁": mine,
                         "最大差距": max(abs(mine[k] - c["機率"][k]) for k in mine)})
        out["2025_lr_example"] = rows
        print(json.dumps(rows, ensure_ascii=False), flush=True)
    finally:
        C.DATA = real
    path = os.path.join(C.WEB, "samples", "research_match.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"記錄於 {path}")


if __name__ == "__main__":
    main()
