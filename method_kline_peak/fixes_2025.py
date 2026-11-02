"""改善方法 A–E,兩個方法(主軸、Stacking 邏輯迴歸)都加,只測 2025(2026-11-02 使用者要求)。

共同:34 檔、訓練 2021–2024(Stacking:A 2021–2023 + B 2024)、訓練門檻 0%、種子 42;
回測 = 只做多前 3 檔(每檔 1/3、t+1 開盤買、t+5 收盤賣、成本 0.585%;另列沒扣成本);混淆矩陣對原本的標籤。
  原本  判低點就買(對照,和 backtest_top3 相同)
  A     止跌確認:判低點的那天 t 要收紅 K(收盤 > 開盤)才算低點、才買
  B     等低點訊號停下來:連續判低點的最後一天 k 才算低點;第 k+1 天不再判低點 → 第 k+2 天開盤買
  C     趨勢過濾:t 日收盤 > 該股 60 日均線(含 t)才算低點、才買
  D     加長期特徵:29 個形狀特徵 + ctx 15 個(5/10/20/60 日報酬、離 20/60 日高低點、均線距離、波動、ATR、RSI、量比)
        + mkt 5 個(0050 的報酬、離 20 日高點、波動)= 49 個,重新訓練
  E     預測報酬:另訓練 HistGradientBoosting 迴歸(同 29 特徵,訓練期全部股票日)預測 t+1 開盤 → t+5 收盤報酬;
        判低點而且預測報酬 > 成本才算低點、才買,排序用預測報酬
A、C、E 只把不合條件的低點改成非極值;B 只留每段的最後一天;高點判斷都不變(交易不用)。
用法: python method_kline_peak/fixes_2025.py [--plot-only(只用 results/fixes_2025.json 重畫圖)]
輸出: results/fixes_2025.json、results/fixes_2025_confusion.png
"""
import json
import os
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "report"))
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import backtest_years as BY  # noqa: E402
import confusion_compare as CC  # noqa: E402
from confusion import summarize  # noqa: E402
from feasibility import END, clean  # noqa: E402
from learn5_trade6 import FLAT, UP  # noqa: E402
from paper_aeocsvm import NAMES  # noqa: E402

YEAR = 2025
SOURCES = ["主軸", "Stacking 邏輯迴歸"]
COLS = ["date", "ticker", "score"]
COST = 1 - (1 - 0.001425 - 0.003) / (1 + 0.001425)
VARIANTS = ["原本", "A 止跌確認(t 日收紅 K)", "B 等低點訊號停下來", "C 趨勢過濾(收盤 > 60 日均線)",
            "D 加長期特徵(49 個)", "E 預測報酬 > 成本"]


def day_table(data):
    rows = []
    for tk, df in data.items():
        df = clean(df)
        rows.append(pd.DataFrame({"date": df.index, "ticker": tk, "red": (df["close"] > df["open"]).to_numpy(),
                                  "above_ma60": (df["close"] > df["close"].rolling(60, min_periods=60).mean()).to_numpy()}))
    return pd.concat(rows, ignore_index=True)


def gate(sig, keep):
    """不合條件的低點改成非極值;回傳 (新的判斷, 買進訊號)。"""
    pred = sig.pred.where(~((sig.pred == UP) & ~keep), FLAT)
    return pred, sig[pred == UP][COLS]


def streak_end(sig):
    """B:每段連續判低點只留最後一天 k;買進訊號日 = 第 k+1 天(該股下一個交易日),分數用第 k 天的。"""
    s = sig.sort_values(["ticker", "date"])
    g = s.groupby("ticker")
    nxt_pred, nxt_date = g["pred"].shift(-1), g["date"].shift(-1)
    end = (s.pred == UP) & nxt_pred.notna() & (nxt_pred != UP)
    pred = s.pred.where(~((s.pred == UP) & ~end), FLAT).reindex(sig.index)
    buys = pd.DataFrame({"date": nxt_date[end].to_numpy(), "ticker": s.ticker[end].to_numpy(), "score": s.score[end].to_numpy()})
    return pred, buys


def ret_model(panel, fc):
    d = WF.year_split(panel, YEAR)
    tr = d["train"].dropna(subset=["r5"])
    X = tr[fc].fillna(tr[fc].median())
    m = HistGradientBoostingRegressor(max_depth=3, max_iter=300, learning_rate=0.05, random_state=0).fit(X, tr["r5"])
    te = d["test"]
    return pd.Series(m.predict(te[fc].fillna(tr[fc].median())), index=te.index)


def figure(res):
    fig, axes = plt.subplots(len(SOURCES), len(VARIANTS), figsize=(5.2 * len(VARIANTS), 14), dpi=140)
    for r, name in enumerate(SOURCES):
        for c, v in enumerate(VARIANTS):
            o = res["results"][name][v]
            CC.panel(axes[r, c], f"{name} · {v}\n扣成本 {o['total_return_pct']:+.1f}%(沒扣 {o['gross_return_pct']:+.1f}%,{o['n_trades']} 筆)",
                     o[CC.KEY])
    fig.suptitle(f"{YEAR} 混淆矩陣與回測:改善方法 A–E(34 檔,訓練 2021–2024,種子 42;只做多前 3 檔;對答案用原本的標籤;顏色 = 每列比例)",
                 fontsize=15, color=CC.INK, x=0.01, ha="left", y=0.998)
    fig.text(0.01, 0.004, "A、C、E:不合條件的低點改成非極值;B:每段連續判低點只留最後一天(要看到第 k+1 天才知道,交易在第 k+2 天開盤);"
             "D:49 個特徵重新訓練;高點判斷都不變(交易不用)。", fontsize=11, color=CC.MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.965), h_pad=7, w_pad=2)
    out = os.path.join(ML.OUT, "fixes_2025_confusion.png")
    fig.savefig(out, facecolor="white")
    return out


def main():
    t0 = time.time()
    data = ML.load_data()
    panel, fc = ML.build_panel(data, 6, [])
    panel_d, fc_d = ML.build_panel(data, 6, ["ctx", "mkt"])
    prices = {tk: clean(df)[["open", "close"]] for tk, df in data.items()}
    days = day_table(data)
    start, end = f"{YEAR}-01-01", min(f"{YEAR}-12-31", END)
    rhat = ret_model(panel, fc)
    test = WF.year_split(panel, YEAR)["test"]
    rh = pd.DataFrame({"date": test.date.to_numpy(), "ticker": test.ticker.to_numpy(), "rhat": rhat.to_numpy()})
    print(f"資料與報酬模型完成,D 特徵 {len(fc_d)} 個  ({time.time() - t0:.0f}s)", flush=True)
    res, cms = {"year": YEAR, "variants": VARIANTS, "cost_pct": round(COST * 100, 3), "results": {}}, {}
    for name in SOURCES:
        sig, _ = WF.run_year(panel, fc, YEAR, BY.SOURCE_FACTORIES[name]())
        sig_d, _ = WF.run_year(panel_d, fc_d, YEAR, BY.SOURCE_FACTORIES[name]())
        x = sig.merge(days, on=["date", "ticker"], how="left").merge(rh, on=["date", "ticker"], how="left")
        assert len(x) == len(sig) and x.rhat.notna().all()
        out = {}
        for v in VARIANTS:
            if v.startswith("原本"):
                pred, buys = sig.pred, sig[sig.pred == UP][COLS]
                s_y = sig
            elif v.startswith("A"):
                pred, buys = gate(x, x.red.fillna(False).to_numpy())
                s_y = sig
            elif v.startswith("B"):
                pred, buys = streak_end(sig)
                s_y = sig
            elif v.startswith("C"):
                pred, buys = gate(x, x.above_ma60.fillna(False).to_numpy())
                s_y = sig
            elif v.startswith("D"):
                pred, buys = sig_d.pred, sig_d[sig_d.pred == UP][COLS]
                s_y = sig_d
            else:
                pred, _ = gate(x, (x.rhat > COST).to_numpy())
                low = pred == UP
                buys = pd.DataFrame({"date": x.date[low].to_numpy(), "ticker": x.ticker[low].to_numpy(), "score": x.rhat[low].to_numpy()})
                s_y = sig
            sim = BY.simulate(prices, buys, start, end, BY.TradeRule(slots=3))
            gross = BY.simulate(prices, buys, start, end, BY.TradeRule(slots=3, **BY.NO_COST))
            st = BY.stats(sim["equity"], sim["trades"])
            cm = summarize(s_y.y.to_numpy(), np.asarray(pred), NAMES)
            out[v] = {"n_buy_signals": len(buys), **st, "gross_return_pct": BY.stats(gross["equity"])["total_return_pct"],
                      "macro_f1_pct": round(cm["macro_f1"] * 100, 2),
                      "recall_pct": {k: round(cm["recall"][k] * 100, 1) for k in ("高點", "低點")},
                      "precision_pct": {k: round((cm["precision"][k] or 0) * 100, 1) for k in ("高點", "低點")},
                      CC.KEY: cm[CC.KEY]}
            cms[(name, v)] = cm
            print(f"{name:<12} {v:<22} 扣成本 {st['total_return_pct']:+7.2f}%  沒扣 {out[v]['gross_return_pct']:+7.2f}%  "
                  f"{st['n_trades']} 筆,勝 {st['win_rate_pct']}%,回撤 {st['max_dd_pct']}%  低點訊號 {len(buys)}  "
                  f"macro-F1 {out[v]['macro_f1_pct']}  找到低 {out[v]['recall_pct']['低點']}  命中低 {out[v]['precision_pct']['低點']}  "
                  f"({time.time() - t0:.0f}s)", flush=True)
        res["results"][name] = out
    with open(os.path.join(ML.OUT, "fixes_2025.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(figure(res))


if __name__ == "__main__":
    if "--plot-only" in sys.argv:
        print(figure(json.load(open(os.path.join(ML.OUT, "fixes_2025.json"), encoding="utf-8"))))
    else:
        main()
