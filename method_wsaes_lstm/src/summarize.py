"""步驟 8 的彙總:把 results/ 裡已跑完的組合整理成和論文表 3 ~ 6 對照的表,寫到 results/summary.md。
用法: python src/summarize.py
天真基準只報 MAPE / R / Theil U:它的預測值 = 今天收盤,買賣訊號永遠是「賣」,報酬與方向正確率沒有意義。報酬的對照用買進持有(論文也有這一欄)。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from wsaes import load_index, quarters, HERE

RES = os.path.join(HERE, "results")
NAMES = {"csi300": "滬深 300", "nifty50": "Nifty 50", "hangseng": "恆生", "nikkei225": "日經 225", "sp500": "S&P 500", "djia": "道瓊"}
MODELS = ["WSAEs-LSTM", "WLSTM", "LSTM", "RNN"]
PAPER_ACC = {  # 論文 Table 3 ~ 5 的六年平均 (MAPE, R, Theil U)
    "csi300": [(0.019, 0.944, 0.013), (0.028, 0.868, 0.018), (0.056, 0.617, 0.035), (0.066, 0.581, 0.043)],
    "nifty50": [(0.019, 0.841, 0.013), (0.029, 0.695, 0.019), (0.034, 0.569, 0.024), (0.038, 0.557, 0.025)],
    "hangseng": [(0.015, 0.931, 0.011), (0.022, 0.876, 0.014), (0.024, 0.847, 0.015), (0.034, 0.730, 0.021)],
    "nikkei225": [(0.017, 0.937, 0.011), (0.028, 0.867, 0.018), (0.031, 0.814, 0.020), (0.036, 0.766, 0.023)],
    "sp500": [(0.011, 0.946, 0.007), (0.015, 0.894, 0.010), (0.017, 0.875, 0.011), (0.018, 0.847, 0.012)],
    "djia": [(0.011, 0.949, 0.007), (0.014, 0.901, 0.009), (0.020, 0.809, 0.013), (0.033, 0.627, 0.021)]}
PAPER_RET = {"csi300": (63.0, 39.6, 17.4, 7.5, 1.7), "nifty50": (45.4, 23.6, 15.1, 7.7, 3.7), "hangseng": (64.5, 36.0, 25.3, 16.4, -1.0),
             "nikkei225": (59.4, 34.6, 19.6, 12.0, 6.8), "sp500": (46.0, 25.6, 11.6, 8.2, 7.0), "djia": (64.0, 38.0, 18.5, 12.2, 5.5)}   # 論文 Table 6,最後一格 = 買進持有


def buy_and_hold(name, buy=0.0025, sell=0.0045, fcost=0.0001):
    """買進持有:現貨,每個測試年第一個交易日收盤買、最後一個交易日收盤賣,成本買 0.25%、賣 0.45%(論文設定)。
    另外回傳「期貨天天做多」在式 (33) 下的年均報酬(每天都收兩邊成本),給策略報酬當同一條公式下的參考。"""
    raw, close, fut = load_index(name); q = quarters(); yr = []
    for y in range(6):
        c = raw.loc[(raw.index >= q[4 * y][0]) & (raw.index <= q[4 * y + 3][1]), close]
        yr.append(100 * (c.iloc[-1] - c.iloc[0] - (c.iloc[0] * buy + c.iloc[-1] * sell)) / c.iloc[0])
    d = raw.index[(raw.index >= q[0][0]) & (raw.index <= q[-1][1])]; f0, f1 = fut.reindex(d).values, fut.shift(-1).reindex(d).values; ok = ~np.isnan(f0) & ~np.isnan(f1)
    long_all = 100 * np.sum((f1[ok] - f0[ok] - (f0[ok] + f1[ok]) * fcost) / f0[ok]) / 6
    return float(np.mean(yr)), float(long_all)


def load(tag):
    p = os.path.join(RES, f"{tag}_metrics.csv")
    return pd.read_csv(p) if os.path.exists(p) else None


def main():
    out = ["# 步驟 8 彙總:復現結果對照論文表 3 ~ 6", "", "每格是 24 季的平均(MAPE 另列中位數);年均報酬 = 24 季報酬合計 ÷ 6。去噪方式:整段 = 整條序列一次去噪(有前視)、因果 = 只用當天以前、無 = 不去噪。", ""]
    acc, ret = [], []
    for idx, zh in NAMES.items():
        m = {w: load(f"{idx}_{w}") for w in ("full", "causal", "none")}
        if m["full"] is None: continue
        g = {w: (d.groupby("model").agg(MAPE=("MAPE", "mean"), MAPE_med=("MAPE", "median"), R=("R", "mean"), U=("TheilU", "mean"), dir=("dir_acc", "mean"), ret=("ret_pct", "sum")) if d is not None else None) for w, d in m.items()}
        for k, mod in enumerate(MODELS):
            pm, pr, pu = PAPER_ACC[idx][k]
            for w, wzh in (("full", "整段"), ("causal", "因果"), ("none", "無")):
                if g[w] is None or (w != "full" and not mod.startswith("W")): continue            # LSTM / RNN 和去噪無關,只列一次
                r = g[w].loc[mod]; label = wzh if mod.startswith("W") else "—"
                acc.append(f"| {zh} | {mod} | {label} | {r.MAPE:.4f} | {r.MAPE_med:.4f} | {pm:.3f} | {r.R:.3f} | {pr:.3f} | {r.U:.4f} | {pu:.3f} | {r['dir']:.3f} |")
        r = g["full"].loc["naive"]; acc.append(f"| {zh} | 天真基準(明天 = 今天) | — | **{r.MAPE:.4f}** | {r.MAPE_med:.4f} | 論文沒有 | {r.R:.3f} | — | {r.U:.4f} | — | 不適用 |")
        bh, long_all = buy_and_hold(idx); row = f"| {zh} |"
        for k, mod in enumerate(MODELS):
            cells = [f"{g[w].loc[mod].ret / 6:+.1f}" for w in (("full", "causal") if mod.startswith("W") else ("full",)) if g[w] is not None]
            row += f" {' / '.join(cells)}({PAPER_RET[idx][k]:.1f})|"
        ret.append(row + f" {bh:+.1f}({PAPER_RET[idx][4]:.1f})| {long_all:+.1f} |")
    out += ["## 準確度(論文 Table 3 ~ 5)", "", "| 指數 | 模型 | 去噪 | MAPE 平均 | MAPE 中位 | 論文 MAPE | R | 論文 R | Theil U | 論文 U | 方向正確率 |", "|---|---|---|---|---|---|---|---|---|---|---|"] + acc
    out += ["", "## 年均策略報酬 %(論文 Table 6;括號內是論文的數字)", "", "有小波的兩個模型寫成「整段 / 因果」。買進持有:現貨、每個測試年頭買尾賣、成本買 0.25% 賣 0.45%。最後一欄是期貨天天做多在同一條公式(每天收兩邊成本 0.01%)下的結果,當策略報酬的參考。", "",
            "| 指數 | WSAEs-LSTM 整段 / 因果 | WLSTM 整段 / 因果 | LSTM | RNN | 買進持有 | 期貨天天做多 |", "|---|---|---|---|---|---|---|"] + ret
    # C:多個 seed
    rows = []
    for idx, zh in NAMES.items():
        for w, wzh in (("full", "整段"), ("causal", "因果")):
            v = [(d[d.model == "WLSTM"].ret_pct.sum() / 6, d[d.model == "WLSTM"].dir_acc.mean()) for d in (load(f"{idx}_{w}{t}") for t in ("", "_s1", "_s2")) if d is not None]
            if len(v) == 3: rows.append(f"| {zh} | {wzh} | " + " / ".join(f"{a:+.1f}" for a, _ in v) + f" | {np.mean([a for a, _ in v]):+.1f} | " + " / ".join(f"{b:.3f}" for _, b in v) + " |")
    if rows: out += ["", "## WLSTM:三個 seed(0 / 1 / 2)的年均報酬 % 與方向正確率", "", "| 指數 | 去噪 | 年均報酬(三個 seed) | 平均 | 方向正確率(三個 seed) |", "|---|---|---|---|---|"] + rows
    # D:照原文設定
    d = load("csi300_full_paper")
    if d is not None:
        g = d.groupby("model").agg(MAPE=("MAPE", "mean"), MAPE_med=("MAPE", "median"), R=("R", "mean"), U=("TheilU", "mean"), dir=("dir_acc", "mean"), ret=("ret_pct", "sum")); b = load("csi300_full").groupby("model").agg(MAPE=("MAPE", "mean"), ret=("ret_pct", "sum"))
        out += ["", "## 照原文設定的一組(滬深 300、整段去噪;SGD 學習率 0.05、5,000 回合、5 層 × 16 單元、不早停)", "", "| 模型 | MAPE 平均 | MAPE 中位 | R | Theil U | 方向正確率 | 年均報酬 % | 原設定的 MAPE / 年均報酬 | 論文 MAPE / 年均報酬 |", "|---|---|---|---|---|---|---|---|---|"]
        for k, mod in enumerate(MODELS):
            r = g.loc[mod]; out.append(f"| {mod} | {r.MAPE:.4f} | {r.MAPE_med:.4f} | {r.R:.3f} | {r.U:.4f} | {r['dir']:.3f} | {r.ret / 6:+.1f} | {b.loc[mod].MAPE:.4f} / {b.loc[mod].ret / 6:+.1f} | {PAPER_ACC['csi300'][k][0]:.3f} / {PAPER_RET['csi300'][k]:.1f} |")
    open(os.path.join(RES, "summary.md"), "w", encoding="utf-8").write("\n".join(out) + "\n"); print("\n".join(out))


if __name__ == "__main__":
    main()
