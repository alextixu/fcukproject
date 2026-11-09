"""等確認再出訊號(2026-11-08 使用者要求;不改模型、不調參數)。

模型同報告:TW200(168 檔)、訓練門檻 0%、種子 42、walk-forward 前 4 年訓練;測試 2024 / 2025 / 2026,主軸、Stacking 邏輯迴歸。
確認規則(k = 1、2、3;k = 0 = 不確認,當對照;高低點分開、每檔各自):
  低點:t 判低點,t+1 ~ t+k 每天收盤都 ≥ t 收盤 → 在 t+k 收盤確認;任一天收盤 < t 收盤 → 取消
  高點:t+1 ~ t+k 收盤都 ≤ t 收盤才確認(只用來算分類成績)
  收盤 = 和標籤相同的還原價(feasibility.clean);t+k 超出該檔資料 → 取消;只用到 t+k 以前的價格。
分類成績:確認的訊號算在 t(原判斷日)、和 t 的真實標籤比對,取消的改判非極值;指標同 postproc_signals.py
  (訊號數、命中率、找到率 當天 / ±2 天、macro-F1);並列 A0 原始、1a 上限(重算,和 postproc_signals_tw200.json 核對)。
回測(只做多、用確認的低點):把確認的訊號當成「t+k 的買進訊號」丟進 backtest_years.simulate(分數 = t 的原始分數),
  所以 t+k+1 開盤買、t+k+5 收盤賣;其餘同 backtest_top3(前 3 檔、每檔 1/3、同分隨機 seed 0、不加碼、漲停照常成交、
  成本 0.585% 另列沒扣成本、每年獨立 100 萬、年底收盤平倉、進場日超過年底不進場)。k = 0 應等於 backtest_long_only_tw200.json。
晚進場代價:同一批確認的低點(不限有沒有買到),「t+1 開盤進、t+5 收盤出」vs「t+k+1 開盤進、t+k+5 收盤出」的平均報酬
  (都扣 0.585%;兩種都在資料範圍內的訊號才算)。
用法: python method_kline_peak/confirm_signals.py
輸出: results/confirm_signals_tw200.json、results/confirm_signals_tw200_curves.png
"""
import json
import os
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import backtest_years as BY  # noqa: E402
import postproc_signals as PP  # noqa: E402
from feasibility import END, clean  # noqa: E402
from learn5_trade6 import FLAT, UP, DOWN  # noqa: E402

POOL, YEARS, SOURCES, KS = "tw200", (2024, 2025, 2026), ["主軸", "Stacking 邏輯迴歸"], (0, 1, 2, 3)
HOLD = BY.TradeRule().hold
COLORS = {"主軸": ("#2a78d6", "#86b6ef"), "Stacking 邏輯迴歸": ("#eb6834", "#f0956b")}
INK, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False


def confirm(df, k, px):
    """回傳 (確認後的判斷, 每列在該檔價格序列的位置 i)。px = {ticker: DataFrame[open, close]}。"""
    pred = df["pred"].to_numpy().copy()
    pos = np.full(len(df), -1)
    for tk, g in df.groupby("ticker"):
        idx = px[tk].index
        pos[g.index] = idx.get_indexer(g["date"])
    assert (pos >= 0).all()
    if k == 0:
        return pred, pos
    for tk, g in df.groupby("ticker"):
        c = px[tk]["close"].to_numpy()
        rows = g.index.to_numpy()
        for r in rows[np.isin(pred[rows], (UP, DOWN))]:
            i = pos[r]
            if i + k >= len(c):
                pred[r] = FLAT
                continue
            fut = c[i + 1:i + k + 1]
            ok = (fut >= c[i]).all() if pred[r] == UP else (fut <= c[i]).all()
            if not ok:
                pred[r] = FLAT
    return pred, pos


def late_cost(df, pred, pos, k, px, rule):
    """確認的低點:t+1 進 vs t+k+1 進(各持有 HOLD 天,扣成本)的平均報酬。"""
    early, late = [], []
    for r in np.flatnonzero(pred == UP):
        p = px[df["ticker"].iat[r]]
        i = pos[r]
        if i + k + HOLD >= len(p):
            continue
        o, c = p["open"].to_numpy(), p["close"].to_numpy()
        f = lambda a, b: c[b] * (1 - rule.sell_fee - rule.tax) / (o[a] * (1 + rule.buy_fee)) - 1  # noqa: E731
        early.append(f(i + 1, i + HOLD))
        late.append(f(i + k + 1, i + k + HOLD))
    if not early:
        return {"n": 0}
    e, l_ = float(np.mean(early)) * 100, float(np.mean(late)) * 100
    return {"n": len(early), "t+1 進場": round(e, 3), "t+k+1 進場": round(l_, 3), "差距(晚 − 早)": round(l_ - e, 3)}


def figure(curves, out, n):
    fig, axes = plt.subplots(len(KS), len(YEARS), figsize=(6.2 * len(YEARS), 3.6 * len(KS)), dpi=150, facecolor=SURF,
                             sharey=True, squeeze=False)
    for r, k in enumerate(KS):
        for c, y in enumerate(YEARS):
            ax = axes[r, c]
            ax.set_facecolor(SURF)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            for s in ("left", "bottom"):
                ax.spines[s].set_color(GRID)
            ax.tick_params(colors=MUTED, labelsize=9, length=0)
            ax.grid(axis="y", color=GRID, lw=0.8)
            ax.axhline(0, color=MUTED, lw=0.8, ls=":")
            txt = []
            for m, (dark, light) in COLORS.items():
                for key, col, ls, lab in (("沒扣成本", light, "--", "沒扣成本"), ("扣成本", dark, "-", "扣成本")):
                    s = curves[k][str(y)][m][key]
                    ax.plot(pd.to_datetime(list(s)), list(s.values()), color=col, ls=ls, lw=1.6 if ls == "-" else 1.2,
                            label=f"{m} {lab}")
                txt.append(f"{m[:2] if m == '主軸' else 'Stacking'} {list(curves[k][str(y)][m]['扣成本'].values())[-1]:+.1f}%")
            ax.set_title(f"k = {k} · {y}" + ("(1–9 月)" if y == 2026 else "") + "\n扣成本:" + "、".join(txt),
                         loc="left", fontsize=10.5, color=INK)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m 月"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
            if c == 0:
                ax.set_ylabel("相對年初 100 萬的報酬(%)", color=MUTED, fontsize=9)
    axes[0, 0].legend(frameon=False, fontsize=8.5, labelcolor=INK, loc="upper left")
    fig.suptitle(f"等確認再出訊號:資產曲線({n} 檔、訓練門檻 0%;列 = 確認天數 k(0 = 不確認)、欄 = 年;只做多前 3 檔、t+k+1 開盤買、"
                 f"持有 5 天;實線 = 扣成本 0.585%、虛線 = 沒扣成本)", x=0.01, ha="left", fontsize=13, color=INK, y=0.997)
    fig.tight_layout(rect=(0, 0, 1, 0.97), h_pad=2.2)
    fig.savefig(out, facecolor=SURF)


def main():
    t0 = time.time()
    data = ML.load_data(pool=POOL)
    panel, fc = ML.build_panel(data, 6, [])
    px = {tk: clean(df)[["open", "close"]] for tk, df in data.items()}
    rule, no_cost = BY.TradeRule(slots=3), BY.TradeRule(slots=3, **BY.NO_COST)
    res = {"pool": POOL, "n_stocks": len(data), "train_min_amp": 0, "ks": list(KS), "classification": {}, "backtest": {},
           "late_entry": {}}
    curves = {k: {} for k in KS}
    for y in YEARS:
        start, end = f"{y}-01-01", min(f"{y}-12-31", END)
        for name in SOURCES:
            sig, _ = WF.run_year(panel, fc, y, BY.SOURCE_FACTORIES[name]())
            df = sig.sort_values(["ticker", "date"]).reset_index(drop=True)
            cls = res["classification"].setdefault(str(y), {}).setdefault(name, {})
            cls["A0 原始"] = PP.metrics(df, PP.apply_rule(df, PP.RULES[0]))
            cls["1a 上限"] = PP.metrics(df, PP.apply_rule(df, PP.RULES[1]))
            for k in KS:
                pred, pos = confirm(df, k, px)
                if k:
                    cls[f"k={k}"] = PP.metrics(df, pred)
                    res["late_entry"].setdefault(f"k={k}", {}).setdefault(str(y), {})[name] = late_cost(df, pred, pos, k, px, rule)
                lo = np.flatnonzero(pred == UP)
                buys = pd.DataFrame({"date": [px[df["ticker"].iat[r]].index[pos[r] + k] if pos[r] + k < len(px[df["ticker"].iat[r]])
                                              else pd.Timestamp("2100-01-01") for r in lo],
                                     "ticker": df["ticker"].to_numpy()[lo], "score": df["score"].to_numpy()[lo]})
                buys = buys[buys.date <= pd.Timestamp(end)]
                out = {}
                for key, rl in (("扣成本", rule), ("沒扣成本", no_cost)):
                    sim = BY.simulate(px, buys, start, end, rl)
                    out[key] = BY.stats(sim["equity"], sim["trades"])
                    curves[k].setdefault(str(y), {}).setdefault(name, {})[key] = {
                        d.strftime("%Y-%m-%d"): round(v / rule.init_cash * 100 - 100, 3) for d, v in sim["equity"].items()}
                out["n_confirmed_lows"] = int(len(lo))
                res["backtest"].setdefault(f"k={k}", {}).setdefault(str(y), {})[name] = out
            print(f"{y} {name} " + "  ".join(f"k={k} {res['backtest'][f'k={k}'][str(y)][name]['扣成本']['total_return_pct']:+.2f}%"
                                              for k in KS) + f"  ({time.time() - t0:.0f}s)", flush=True)
    # 三年平均(分類)
    avg = {}
    for name in SOURCES:
        avg[name] = {}
        for r in ["A0 原始", "1a 上限"] + [f"k={k}" for k in KS if k]:
            ys = [res["classification"][str(y)][name][r] for y in YEARS]
            e = {"macro_f1": round(float(np.mean([v["macro_f1"] for v in ys])), 2)}
            for side in PP.SIDES:
                e[side] = {kk: round(float(np.mean([v[side][kk] for v in ys])), 2) for kk in ys[0][side]}
            avg[name][r] = e
    res["classification_三年平均"] = avg
    res["curves"] = {str(k): v for k, v in curves.items()}
    stem = os.path.join(ML.OUT, f"confirm_signals_{POOL}")
    with open(stem + ".json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    figure(curves, stem + "_curves.png", len(data))
    print(stem + ".json")


if __name__ == "__main__":
    main()
