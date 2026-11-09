"""南電 2024:每種後處理拿掉了哪些訊號(2026-11-09 使用者要求;同一套模型的判斷重新整理,不訓練新模型、不跑回測)。

模型 = TW200(168 檔)、訓練門檻 0%、種子 42(同 outputs_8046_2024_tw200_amp0.png)。規則直接重用
postproc_signals.py(A0、1a、1b、2-50)與 confirm_signals.py(確認 k = 1、2、3);2-50 是每天跨股票排序,
所以先對全部 168 檔套規則,再取出南電。對答案用原本的標籤。
圖:第 1 列真實標籤,之後每個規則一列(灰色收盤、▼ 判高點、▲ 判低點、實心 = 判對、空心 = 判錯,標在 t);
確認規則另在確認日 t+k 畫小點,用細線和 t 連起來。
用法: python method_kline_peak/report/compare_postproc.py
輸出: results/compare_8046_2024_tw200_main.png、_stack.png、results/compare_8046_2024_tw200.json
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mainline as ML  # noqa: E402
import walkforward as WF  # noqa: E402
import backtest_years as BY  # noqa: E402
import postproc_signals as PP  # noqa: E402
import confirm_signals as CS  # noqa: E402
from export_windows import ticker_names  # noqa: E402
from feasibility import clean  # noqa: E402
from learn5_trade6 import UP, DOWN  # noqa: E402

POOL, YEAR, TK = "tw200", 2024, "8046.TW"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
HI, LO = "#eb6834", "#2a78d6"
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False
RULES = [("A0 原始", PP.RULES[0], 0), ("1a 合併連續・事後最高分(用到未來資訊,實際用不了)", PP.RULES[1], 0),
         ("1b 合併連續・即時版", PP.RULES[2], 0), ("2-50 每天前 50%", PP.RULES[3], 0),
         ("確認 k=1", None, 1), ("確認 k=2", None, 2), ("確認 k=3", None, 3)]
FILES = {"主軸": "main", "Stacking 邏輯迴歸": "stack"}


def counts(y, pred):
    out = {}
    for side, cls in (("低點", UP), ("高點", DOWN)):
        p, t = pred == cls, y == cls
        hit = int((p & t).sum())
        near = 0
        for i in np.flatnonzero(t):
            near += int(p[max(0, i - PP.NEAR):i + PP.NEAR + 1].any())
        out[side] = {"判": int(p.sum()), "對": hit, "錯": int(p.sum()) - hit,
                     "命中率": round(hit / p.sum() * 100, 1) if p.sum() else None,
                     "真": int(t.sum()), "當天抓到": hit, "±2 天抓到": near}
    return out


def style(ax):
    for k in ("top", "right"):
        ax.spines[k].set_visible(False)
    for k in ("left", "bottom"):
        ax.spines[k].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, lw=0.8)


def main():
    data = ML.load_data(pool=POOL)
    panel, fc = ML.build_panel(data, 6, [])
    px = {tk: clean(df)[["open", "close"]] for tk, df in data.items()}
    nm = ticker_names().get(TK, TK)
    res = {"pool": POOL, "year": YEAR, "ticker": TK, "methods": {}}
    for name, tag in FILES.items():
        sig, _ = WF.run_year(panel, fc, YEAR, BY.SOURCE_FACTORIES[name]())
        df = sig.sort_values(["ticker", "date"]).reset_index(drop=True)
        rows = np.flatnonzero(df["ticker"].to_numpy() == TK)
        s = df.iloc[rows]
        dates, y = s["date"].to_numpy(), s["y"].to_numpy()
        close = px[TK]["close"]
        c = close.loc[s["date"]].to_numpy()
        idx = close.index
        preds, res["methods"][name] = {}, {}
        for title, rule, k in RULES:
            if rule is not None:
                pred = PP.apply_rule(df, rule)
            else:
                pred, _ = CS.confirm(df, k, px)
            preds[title] = (pred[rows], k)
            res["methods"][name][title] = counts(y, pred[rows])

        n = len(RULES) + 1
        fig, axes = plt.subplots(n, 1, figsize=(18, 3.1 * n), dpi=150, sharex=True, facecolor="white",
                                 gridspec_kw={"hspace": 0.42})
        fig.subplots_adjust(left=0.05, right=0.99, top=0.965, bottom=0.03)
        pad = (c.max() - c.min()) * 0.04
        for ax in axes:
            ax.plot(dates, c, color="#9a9994", lw=1.1, zorder=1)
            style(ax)
            ax.set_ylim(c.min() - pad * 3, c.max() + pad * 3)
        ax = axes[0]
        for cls, mk, col, off, lab in ((DOWN, "v", HI, pad, "真高點"), (UP, "^", LO, -pad, "真低點")):
            m = y == cls
            ax.scatter(dates[m], c[m] + off, marker=mk, s=40, color=col, zorder=3, label=f"{lab} {int(m.sum())} 個")
        ax.set_title(f"{TK[:4]} {nm} {YEAR}:收盤與真實標籤(11 天收盤最高 / 最低)", loc="left", fontsize=12, color=INK, fontweight="bold")
        ax.legend(frameon=True, facecolor="white", edgecolor=GRID, fontsize=9.5, labelcolor=INK, loc="lower left", ncol=2)
        for ax, (title, _, k) in zip(axes[1:], RULES):
            p, kk = preds[title]
            cnt = res["methods"][name][title]
            for cls, side, mk, col, off in ((DOWN, "高點", "v", HI, pad), (UP, "低點", "^", LO, -pad)):
                on = p == cls
                hit, miss = on & (y == cls), on & (y != cls)
                ax.scatter(dates[hit], c[hit] + off, marker=mk, s=44, color=col, zorder=3)
                ax.scatter(dates[miss], c[miss] + off, marker=mk, s=44, facecolors="white", edgecolors=col, lw=1.2, zorder=3)
                if kk:                                          # 確認日 t+k:小點 + 細線
                    for i in np.flatnonzero(on):
                        j = idx.get_loc(dates[i]) + kk
                        d2 = idx[j]
                        ax.plot([dates[i], d2], [c[i] + off, c[i] + off * 1.9], color=col, lw=0.7, zorder=2)
                        ax.scatter([d2], [c[i] + off * 1.9], s=9, color=col, zorder=3)
            L, H = cnt["低點"], cnt["高點"]
            ax.set_title(f"{title}:判低點 {L['判']} 天(對 {L['對']} / 錯 {L['錯']})、判高點 {H['判']} 天(對 {H['對']} / 錯 {H['錯']})"
                         + ("  · 小點 = 確認日 t+k" if kk else ""), loc="left", fontsize=11, color=INK, fontweight="bold")
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m 月"))
        axes[-1].xaxis.set_major_locator(mdates.MonthLocator())
        fig.suptitle(f"{TK[:4]} {nm} {YEAR}:各種後處理留下的訊號 — {name}(168 檔、訓練門檻 0%、種子 42)",
                     x=0.01, ha="left", fontsize=15, color=INK, y=0.99)
        fig.text(0.01, 0.008, "▼ 判高點、▲ 判低點,標在判斷日 t:實心 = 和真實標籤相同、空心 = 判錯。被拿掉的訊號改判非極值(圖上不畫)。",
                 fontsize=10, color=MUTED)
        out = os.path.join(ML.OUT, f"compare_{TK[:4]}_{YEAR}_{POOL}_{tag}.png")
        fig.savefig(out, facecolor="white", bbox_inches="tight")
        print(out)
    with open(os.path.join(ML.OUT, f"compare_{TK[:4]}_{YEAR}_{POOL}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for name, v in res["methods"].items():
        for t, cnt in v.items():
            print(name, t, cnt)


if __name__ == "__main__":
    main()
