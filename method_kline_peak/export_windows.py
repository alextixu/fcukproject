"""匯出主軸(mainline base:論文標籤 + 規則候選 + AE + OC-SVM nu 0.1,種子 42)的逐日資料,給網頁畫 11 日窗口。

切分 = 我們的切分(訓練 2020–2023、測試 2025-01 ~ 2026-09),TW50。
量的基準跟主軸一樣(mainline.VOL_MA,目前 10 日均量)。
每檔輸出:日期、還原 O/H/L/C、標籤(0 非極值 / 1 低點 / 2 高點,窗格不完整為 -1)、
          規則候選(0 無 / 1 低點候選 / 2 高點候選)、模型判斷(只有測試期;訓練期為 -1)、t+1 開 → t+5 收報酬(%)
另輸出摘要:樣本數、類別比例、規則與模型的混淆矩陣

用法: python method_kline_peak/export_windows.py --out <資料夾>
輸出: <資料夾>/windows_data.json
"""
import argparse
import json
import os
import re
import sys
from argparse import Namespace

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mainline as ML  # noqa: E402
from feasibility import P, START, END, load_pool, clean  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402
from paper_aeocsvm import SPLITS, NAMES, rule_pred  # noqa: E402
from confusion import summarize  # noqa: E402

SPLIT = SPLITS["我們的切分"]
SEED, NU = 42, 0.1


def ticker_names():
    src = open(os.path.join(P.CHARTGCN_CORE, "data_loader.py"), encoding="utf-8").read()
    return dict(re.findall(r'"(\d{4}\.TW)",\s*#\s*(\S+)', src))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data = load_pool("tw50", START, END)
    panel, feat_cols = ML.build_panel(data, 6, [])
    d = ML.split(panel, SPLIT)
    tr, te = d["train"], d["test"]

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    args = Namespace(weight="purity", gamma="scale", nu=[NU])
    pred = np.full(len(te), FLAT)
    for cls in (DOWN, UP):
        m = ML.fit_class(tr, cls, feat_cols, args)
        c = te[ML.CAND[cls]].to_numpy()
        Xt = np.clip(m["sc"].transform(te.loc[c, feat_cols].fillna(m["med"])), -5, 5).astype(np.float32)
        with torch.no_grad():
            zt = m["ae"].encode(torch.FloatTensor(Xt)).numpy()
        pred[np.flatnonzero(c)[m["ocs"][NU].predict(zt) == 1]] = cls
    te = te.assign(pred=pred)
    yte = te["y"].to_numpy()
    summary = {
        "split": {k: list(v) for k, v in SPLIT.items()},
        "n_train": len(tr), "n_test": len(te), "n_tickers": len(data),
        "dist_train": {NAMES[c]: float((tr["y"] == c).mean()) for c in (UP, FLAT, DOWN)},
        "dist_test": {NAMES[c]: float((yte == c).mean()) for c in (UP, FLAT, DOWN)},
        "rule": summarize(yte, rule_pred(te), NAMES),
        "model": summarize(yte, pred, NAMES),
    }

    names = ticker_names()
    lab = panel.set_index(["ticker", "date"])["y"]
    cand = panel.set_index(["ticker", "date"])[["cand_hi", "cand_lo"]]
    prd = te.set_index(["ticker", "date"])["pred"]
    stocks = []
    for tk, df in data.items():
        df = clean(df)
        r5 = (df["close"].shift(-5) / df["open"].shift(-1) - 1) * 100
        periods = {}
        for key, (a0, b0) in (("train", SPLIT["train"]), ("test", SPLIT["test"])):
            w = df.loc[a0:b0]
            idx = [(tk, t) for t in w.index]
            y = lab.reindex(idx).fillna(-1).astype(int).to_numpy()
            ch = cand.reindex(idx).fillna(False).astype(bool).to_numpy()
            cd = np.where(ch[:, 0], 2, np.where(ch[:, 1], 1, 0))
            pr = prd.reindex(idx).fillna(-1).astype(int).to_numpy() if key == "test" else np.full(len(w), -1)
            periods[key] = {
                "d": [t.strftime("%Y-%m-%d") for t in w.index],
                "o": np.round(w["open"].to_numpy(), 2).tolist(), "h": np.round(w["high"].to_numpy(), 2).tolist(),
                "l": np.round(w["low"].to_numpy(), 2).tolist(), "c": np.round(w["close"].to_numpy(), 2).tolist(),
                "y": y.tolist(), "cand": cd.tolist(), "pred": pr.tolist(),
                "r5": [None if np.isnan(x) else round(float(x), 2) for x in r5.reindex(w.index).to_numpy()],
            }
        stocks.append({"ticker": tk, "name": names.get(tk, tk.split(".")[0]), **periods})
    os.makedirs(a.out, exist_ok=True)
    fp = os.path.join(a.out, "windows_data.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "stocks": stocks}, f, ensure_ascii=False, separators=(",", ":"),
                  default=lambda x: None)
    print(f"輸出 {fp}({os.path.getsize(fp) / 1e6:.1f} MB),{len(stocks)} 檔;測試 acc 規則 {summary['rule']['acc']:.1%}"
          f" / 模型 {summary['model']['acc']:.1%},macro-F1 {summary['rule']['macro_f1']:.2%} / {summary['model']['macro_f1']:.2%}")


if __name__ == "__main__":
    main()
