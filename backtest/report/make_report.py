"""彙整 results/*.json + *_curves.parquet → results/summary_2026.md 與 results/report_2026.html(Artifact 用)。

各系統「事前指定」的代表設定(避免事後挑最好的):
  KLINE   : 1日-7特徵(2026-03-12 初始提交的原始特徵集),open 口徑(隔日開盤進出、扣 0.42%)
  XGB     : tw50 h=5 cs,沿用 2024 篩出的 20 欄(frozen:e4-tw50-h5-cs:full_top20);另列 2024 最佳 e6c 設定(tw200 h=20 chip)若已跑完
  Chart-GCN: gridbest-date(2024 網格最佳 w140/m80/N10/g4),h=1 模型;排名選股(前 10%)與論文 §6.3 模擬皆列
其餘設定全部進明細表。
"""
import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
from common import paths as P  # noqa: E402

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RES = P.RESULTS
TEST_START, TEST_END = "2026-01-01", "2026-09-10"


def load(name):
    fp = os.path.join(RES, name)
    return json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else None


def load_curves(name):
    fp = os.path.join(RES, name)
    return pd.read_parquet(fp) if os.path.exists(fp) else None


def shift_to_realized(s: pd.Series, h: int) -> pd.Series:
    """曲線索引是決策日;報酬在 h 個交易日後才實現,畫圖時往後移。"""
    s = s.copy()
    s.index = s.index + pd.tseries.offsets.BDay(h)
    return s


def main():
    kl, xg, cg = load("kline_2026.json"), load("xgb_2026.json"), load("cgcn_2026.json")
    klc, xgc, cgc = load_curves("kline_2026_curve.parquet"), load_curves("xgb_2026_curves.parquet"), load_curves("cgcn_2026_curves.parquet")
    bench = {}
    if xg:
        any_ = next(iter(xg.values()))
        bench["0050"] = any_["bh_0050_pct"]
    rows, curves, detail = [], {}, []

    # 0050 / tw50 等權 日曲線(由 cache_2026)
    cache = P.YF_2026_CACHE
    c50 = pd.read_parquet(os.path.join(cache, "0050.TW.parquet"))["close"].loc[TEST_START:TEST_END]
    curves["0050 買進持有"] = c50 / c50.iloc[0] - 1
    import sys
    sys.path.insert(0, P.CHARTGCN_CORE)
    from data_loader import TICKER_SETS
    ew = []
    for tk in TICKER_SETS["tw50"]:
        fp = os.path.join(cache, f"{tk}.parquet")
        if os.path.exists(fp):
            c = pd.read_parquet(fp)["close"].loc[TEST_START:TEST_END]
            if len(c) > 1:
                ew.append(c / c.iloc[0])
    curves["tw50 等權買進持有"] = pd.concat(ew, axis=1).ffill().mean(axis=1) - 1
    bench["tw50_ew"] = round(float(curves["tw50 等權買進持有"].iloc[-1]) * 100, 2)

    # ── KLINE ──
    if kl:
        for name, s in kl["results"].items():
            for k in ("open", "close"):
                if s.get(k):
                    detail.append(dict(system="KLINE(AE+OC-SVM)", setting=f"{name} / {k} 口徑", pool="tw50", h=5,
                                       kind="訊號做多(+做空)", n=s["n_trades"], ret=s[k]["portfolio_ret_pct"],
                                       t=s[k]["t_stat"], win=s[k]["win_rate"], extra=f"買 {s['n_buy']} / 賣 {s['n_sell']}"))
        s = kl["results"]["1日-7特徵"]
        rows.append(dict(system="KLINE 系統 A", setting="1日-7特徵,隔日開盤進出,持有 5 日,扣 0.42%/筆", kind="純多頭(訊號)",
                         ret=s["open"]["portfolio_ret_pct"], t=s["open"]["t_stat"], n=s["n_trades"]))
        if klc is not None:
            curves["KLINE 1日-7特徵(淨)"] = klc["1日-7特徵"]

    # ── XGB ──
    if xg:
        for tag, r in xg.items():
            for name, s in r["sets"].items():
                detail.append(dict(system="XGB 技術指標", setting=f"{tag} / {name}({s['n_feat']} 欄)", pool=r["pool"], h=r["h"],
                                   kind="排名前 10% 純多頭(淨)", n=s["n_periods"], ret=s["long_net"]["cum_pct"], t=s["long_net"]["t"],
                                   win=s["long_net"]["win_rate"], extra=f"AUC {s['test_auc']};H-L 淨 {s['hl_net']['cum_pct']:+.1f}% (t {s['hl_net']['t']:+.2f});週轉 {s['turnover_long']}"))
        pick = [("x26-tw50-h5-cs", "frozen:e4-tw50-h5-cs:full_top20", "tw50 h=5,2024 篩出的 20 欄原封重訓"),
                ("x26-tw200-h20-cs-chip", "frozen:e6c-tw200-h20-cs-chip:full_top20", "tw200 h=20 含籌碼,2024 最佳 e6c 的 20 欄原封重訓")]
        for tag, name, desc in pick:
            s = xg.get(tag, {}).get("sets", {}).get(name)
            if not s:
                continue
            rows.append(dict(system="XGB 系統(老師的方法)", setting=desc, kind="排名前 10% 純多頭(淨)",
                             ret=s["long_net"]["cum_pct"], t=s["long_net"]["t"], n=s["n_periods"]))
            rows.append(dict(system="XGB 系統(老師的方法)", setting=desc, kind="排名 H-L 多空(淨)",
                             ret=s["hl_net"]["cum_pct"], t=s["hl_net"]["t"], n=s["n_periods"]))
            if xgc is not None:
                h = xg[tag]["h"]
                lab = "XGB tw50 h5 20欄" if "tw50" in tag else "XGB tw200 h20 chip 20欄"
                curves[f"{lab} 前10%純多頭(淨)"] = shift_to_realized(xgc[f"{tag}|{name}|long_net"], h)
                curves[f"{lab} H-L(淨)"] = shift_to_realized(xgc[f"{tag}|{name}|hl_net"], h)

    # ── Chart-GCN ──
    if cg:
        for hk, m in cg["models"].items():
            h = int(hk[1:])
            rd, ps = m.get("rank_decile"), m.get("paper_sec63")
            if rd:
                detail.append(dict(system="Chart-GCN", setting=f"gridbest-date {hk} 3-seed 平均", pool="tw50", h=h,
                                   kind="排名前 10% 純多頭(淨)", n=rd["n_periods"], ret=rd["long_net"]["cum_pct"], t=rd["long_net"]["t"],
                                   win=rd["long_net"]["win_rate"], extra=f"acc {m['ens_acc']}%;prob_std {m['prob_std']};H-L 淨 {rd['hl_net']['cum_pct']:+.1f}% (t {rd['hl_net']['t']:+.2f});退化期 {rd['n_degenerate']}"))
            if ps:
                for k in ("gross", "net"):
                    detail.append(dict(system="Chart-GCN", setting=f"gridbest-date {hk} 3-seed 平均", pool="tw50", h=h,
                                       kind=f"論文 §6.3 訊號+MACD({'無成本' if k == 'gross' else '扣成本'})", n=ps[k]["avg_trades_per_stock"],
                                       ret=ps[k]["final_ret_pct"], t=None, win=None, extra=f"MDD {ps[k]['max_dd_pct']}%;日 Sharpe {ps[k]['sharpe_daily_ann']}"))
        m = cg["models"].get("h1")
        if m:
            if m.get("rank_decile"):
                rd = m["rank_decile"]
                rows.append(dict(system="Chart-GCN 系統 B", setting="gridbest-date h=1,3 seed 平均機率", kind="排名前 10% 純多頭(淨)",
                                 ret=rd["long_net"]["cum_pct"], t=rd["long_net"]["t"], n=rd["n_periods"]))
                rows.append(dict(system="Chart-GCN 系統 B", setting="gridbest-date h=1,3 seed 平均機率", kind="排名 H-L 多空(淨)",
                                 ret=rd["hl_net"]["cum_pct"], t=rd["hl_net"]["t"], n=rd["n_periods"]))
            if m.get("paper_sec63"):
                ps = m["paper_sec63"]
                rows.append(dict(system="Chart-GCN 系統 B", setting="gridbest-date h=1,論文 §6.3 原始交易模擬", kind="訊號做多+MACD 出場(扣成本)",
                                 ret=ps["net"]["final_ret_pct"], t=None, n=ps["net"]["avg_trades_per_stock"]))
            if cgc is not None:
                if "cgcn_h1|rank|long_net" in cgc:
                    curves["Chart-GCN 排名前10%(淨)"] = shift_to_realized(cgc["cgcn_h1|rank|long_net"], 1)
                    curves["Chart-GCN H-L(淨)"] = shift_to_realized(cgc["cgcn_h1|rank|hl_net"], 1)
                if "cgcn_h1|paper63|net" in cgc:
                    curves["Chart-GCN 論文§6.3(淨)"] = cgc["cgcn_h1|paper63|net"]

    rows.append(dict(system="基準", setting="0050 買進持有", kind="—", ret=bench.get("0050"), t=None, n=None))
    rows.append(dict(system="基準", setting="tw50 等權買進持有", kind="—", ret=bench.get("tw50_ew"), t=None, n=None))

    # ── markdown ──
    md = [f"# 2026 年回測總表(測試 {TEST_START} ~ {TEST_END};訓練/驗證資料 ≤ 2025-12-31)", "",
          "## 代表設定(事前指定)", "", "| 系統 | 設定 | 口徑 | 2026 累積報酬 | t | 期數/交易數 |", "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['system']} | {r['setting']} | {r['kind']} | {r['ret']:+.2f}% | {r['t'] if r['t'] is not None else '—'} | {r['n'] if r['n'] is not None else '—'} |")
    md += ["", "## 全部設定明細", "", "| 系統 | 設定 | 池 | h | 口徑 | n | 2026 累積報酬 | t | 勝率 | 備註 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for d in detail:
        md.append(f"| {d['system']} | {d['setting']} | {d['pool']} | {d['h']} | {d['kind']} | {d['n']} | {d['ret']:+.2f}% | "
                  f"{d['t'] if d['t'] is not None else '—'} | {d['win'] if d['win'] is not None else '—'} | {d['extra']} |")
    open(os.path.join(RES, "summary_2026.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")

    # ── 曲線對齊(交易日聯集,ffill,起點 0)──
    idx = pd.bdate_range(TEST_START, TEST_END)
    cdf = pd.DataFrame({k: v for k, v in curves.items()}).sort_index()
    cdf = cdf.reindex(cdf.index.union(idx)).ffill().reindex(idx).fillna(0.0)
    cdf = cdf[(cdf.index >= TEST_START)]
    cdf.to_parquet(os.path.join(RES, "curves_aligned_2026.parquet"))
    json.dump({"rows": rows, "detail": detail, "bench": bench,
               "curves": {"dates": [d.strftime("%Y-%m-%d") for d in cdf.index],
                          "series": {k: [round(float(x) * 100, 2) for x in cdf[k]] for k in cdf.columns}}},
              open(os.path.join(RES, "report_data_2026.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("\n".join(md[:len(rows) + 6]))
    print(f"[SAVED] results/summary_2026.md, report_data_2026.json ({len(detail)} 筆明細, {len(cdf.columns)} 條曲線)")


if __name__ == "__main__":
    main()
