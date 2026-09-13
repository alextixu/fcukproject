"""最終報告 v3 資料:最佳系統改為「掉出前 8 名連續 2 天才賣」,並整理模型版本、訓練參數、特徵清單與明細 → results/final_best.json
(沿用 final_template.html;舊版 v2 的「前 3 名 + 抱滿 10 日」當對照線)
"""
import json
import os
import re
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
import run_ncku as R                                   # noqa: E402
from run_ncku import assemble_csv, code                 # noqa: E402
from run_logic import load_indicators                   # noqa: E402
import run_logic2 as L2                                 # noqa: E402
from run_window import ranking                          # noqa: E402
from prep_final_report import ledger, monthly           # noqa: E402
import prep_final_report as P                           # noqa: E402
from data_loader import TICKER_SETS                     # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
XGB = os.path.join(ROOT, "method_xgb")
OUT = os.path.join(HERE, "out", "final_best")
os.makedirs(OUT, exist_ok=True)
P.OUT = OUT
END = "20260911"
NAMES = P.NAMES
CFG = dict(K=3, exit_rank=8, out_days=2, min_hold=0, mkt="none")
PREV = dict(K=3, exit_rank=3, out_days=1, min_hold=10, mkt="none")
TAG, SET = "x26-tw50-h5-cs", "full_permpos"

FAM = {"trend": "趨勢", "momentum": "動量", "volatility": "波動", "volume": "量能", "candle": "K 棒", "stats": "統計分布", "cross_section": "橫斷面", "event": "事件"}
CS_COL = {"roc_5": "5 日報酬", "roc_20": "20 日報酬", "roc_60": "60 日報酬", "roc_120": "120 日報酬", "ret_std_20": "20 日報酬波動", "ret_std_60": "60 日報酬波動",
          "vol_z_20": "20 日量能 z 分數", "turnover_z_20": "20 日成交額 z 分數", "rsi_14": "RSI(14)"}
FIXED = {
    "close_pos": "收盤在當日高低區間的位置(0 = 收在最低,1 = 收在最高)", "upper_shadow": "上影線長度 ÷ 當日振幅", "lower_shadow": "下影線長度 ÷ 當日振幅",
    "body_range": "K 棒實體(收盤 − 開盤)÷ 當日振幅,正值為紅 K", "range_ratio": "當日振幅 ÷ 收盤價", "gap": "開盤相對前一日收盤的跳空幅度",
    "cs_idio_std_60": "扣除 tw50 等權大盤後的個股殘差報酬,60 日標準差", "cs_beta_60": "相對 tw50 等權大盤的 60 日 beta",
    "vortex_neg_14": "Vortex 負向指標(14),下跌動能", "psar_dist": "收盤相對拋物線 SAR 的距離(÷ 收盤)", "stochrsi_14": "StochRSI(14):RSI 在近 14 日區間的位置",
    "cmo_14": "錢德動量擺盪 CMO(14)", "uo_7_14_28": "終極震盪指標 UO(7, 14, 28)", "ao_5_34": "Awesome Oscillator(5, 34)÷ 收盤", "ulcer_14": "潰瘍指數(14):近 14 日回撤的均方根",
    "vol_ratio_5_60": "5 日報酬波動 ÷ 60 日報酬波動", "force_13": "勁道指數 Force(13),以均量與收盤正規化", "ev_vol_vs_max20": "今日量 ÷ 過去 20 日最大量(> 1 為量創 20 日新高)",
    "ev_days_since_limit_up": "距離上次收漲停的交易日數(上限 20)", "ev_amt_pctile250": "今日成交金額在過去一年的分位", "ev_bigmove5_cnt20": "近 20 日單日漲跌超過 5% 的次數",
    "trix_15": "TRIX(15)", "aroon_up_25": "Aroon 上升(25):近 25 日最高點出現得多近",
}
PAT = [
    (r"^(\w+)_ma(\d+)$", lambda m: f"{desc(m.group(1))},{m.group(2)} 日平均"),
    (r"^mkt_roc_(\d+)$", lambda m: f"tw50 等權大盤近 {m.group(1)} 日報酬(全部股票同值)"),
    (r"^cs_excess_roc_(\d+)$", lambda m: f"個股近 {m.group(1)} 日報酬減去等權大盤同期報酬"),
    (r"^cs_rank_(.+)$", lambda m: f"當日在 tw50 中「{CS_COL.get(m.group(1), m.group(1))}」的百分位排名"),
    (r"^adx_(\d+)$", lambda m: f"ADX({m.group(1)}):趨勢強度,不分方向"), (r"^pdi_(\d+)$", lambda m: f"+DI({m.group(1)}):上漲方向強度"),
    (r"^mdi_(\d+)$", lambda m: f"−DI({m.group(1)}):下跌方向強度"), (r"^ema_ratio_(\d+)$", lambda m: f"收盤相對 {m.group(1)} 日 EMA 的乖離"),
    (r"^sma_ratio_(\d+)$", lambda m: f"收盤相對 {m.group(1)} 日均線的乖離"), (r"^sma_cross_(\d+)_(\d+)$", lambda m: f"{m.group(1)} 日均線相對 {m.group(2)} 日均線的差距"),
    (r"^macd_hist_(\d+)_(\d+)_(\d+)$", lambda m: f"MACD 柱狀體({m.group(1)}, {m.group(2)}, {m.group(3)})÷ 收盤"),
    (r"^macd_signal_(\d+)_(\d+)_(\d+)$", lambda m: f"MACD 訊號線({m.group(1)}, {m.group(2)}, {m.group(3)})÷ 收盤"),
    (r"^linreg_slope_(\d+)$", lambda m: f"近 {m.group(1)} 日收盤線性回歸斜率 ÷ 收盤"), (r"^roc_(\d+)$", lambda m: f"近 {m.group(1)} 日報酬"),
    (r"^rsi_(\d+)$", lambda m: f"RSI({m.group(1)})"), (r"^stoch_d_(\d+)_3$", lambda m: f"隨機指標 D 值({m.group(1)}, 3)"),
    (r"^willr_(\d+)$", lambda m: f"威廉指標 %R({m.group(1)})"), (r"^cci_(\d+)$", lambda m: f"CCI({m.group(1)})"),
    (r"^ret_lag_(\d+)$", lambda m: f"{int(m.group(1)) - 1} 個交易日前的單日報酬"), (r"^up_ratio_(\d+)$", lambda m: f"近 {m.group(1)} 日上漲天數比例"),
    (r"^ret_std_(\d+)$", lambda m: f"近 {m.group(1)} 日日報酬標準差"), (r"^gk_vol_(\d+)$", lambda m: f"Garman-Klass 波動率({m.group(1)} 日)"),
    (r"^parkinson_(\d+)$", lambda m: f"Parkinson 高低價波動率({m.group(1)} 日)"), (r"^atr_ratio_(\d+)$", lambda m: f"ATR({m.group(1)})÷ 收盤"),
    (r"^bb_bw_(\d+)$", lambda m: f"布林帶寬({m.group(1)} 日,4σ ÷ 中線)"), (r"^mdd_(\d+)$", lambda m: f"近 {m.group(1)} 日最大回撤"),
    (r"^dist_high_(\d+)$", lambda m: f"收盤距 {m.group(1)} 日最高價的幅度"), (r"^dist_low_(\d+)$", lambda m: f"收盤距 {m.group(1)} 日最低價的幅度"),
    (r"^donchian_pos_(\d+)$", lambda m: f"收盤在 {m.group(1)} 日唐奇安通道中的位置"), (r"^vol_sma_ratio_(\d+)$", lambda m: f"今日量 ÷ {m.group(1)} 日均量 − 1"),
    (r"^ad_roc_(\d+)$", lambda m: f"累積 / 派發線 {m.group(1)} 日變化 ÷ 同期成交量"), (r"^vwap_ratio_(\d+)$", lambda m: f"收盤相對 {m.group(1)} 日量加權均價"),
    (r"^ev_new_high_(\d+)$", lambda m: f"收盤創 {m.group(1)} 日新高(是 = 1)"), (r"^ev_new_low_(\d+)$", lambda m: f"收盤創 {m.group(1)} 日新低(是 = 1)"),
    (r"^kurt_(\d+)$", lambda m: f"近 {m.group(1)} 日報酬峰態"), (r"^skew_(\d+)$", lambda m: f"近 {m.group(1)} 日報酬偏態"),
    (r"^autocorr_(\d+)$", lambda m: f"近 {m.group(1)} 日報酬一階自相關"), (r"^cumret_ex1_(\d+)$", lambda m: f"{m.group(1)} 日前到昨天的累積報酬(不含今日)"),
]


def desc(name):
    if name in FIXED:
        return FIXED[name]
    for pat, fn in PAT:
        m = re.match(pat, name)
        if m:
            return fn(m)
    return name


def run_cfg(start, name, c):
    R.START, R.END, L2.START, L2.END = start, END, start, END
    rk = ranking(pd.Timestamp(start), 1)
    st = L2.Logic2(name, UNI, rk, IND, LIQ, MKT, L2.LIQ["vol2k"], L2.MKT[c["mkt"]], c["exit_rank"], None, None,
                   topk=c["K"], maxrank=max(15, 2 * c["K"]), min_hold=c["min_hold"], out_days=c["out_days"])
    return L2.run_one(name, st, UNI, OUT)


def main():
    global UNI, IND, LIQ, MKT
    tw50 = [code(t) for t in TICKER_SETS["tw50"]]
    avail = assemble_csv(tw50 + ["0050"])
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write(f"end_date: '{END}'\nstart_date: '20251001'\n")
    UNI = [c for c in tw50 if c in avail]
    IND, LIQ, MKT = load_indicators(UNI), L2.load_liquidity(UNI), L2.load_market()

    out = {"config": CFG, "prev_config": PREV, "end": "2026-09-11", "init_cash": 1_000_000}
    for win, start in [("full", "20260102"), ("jul", "20260630")]:
        best = run_cfg(start, f"v3_{win}", CFG)
        prev = run_cfg(start, f"v2_{win}", PREV)
        trades, held = ledger(os.path.join(OUT, f"v3_{win}.xlsx"))
        bw = json.load(open(os.path.join(HERE, "out", f"summary_window_{start}_20260911.json"), encoding="utf-8"))
        out[win] = {
            "best": {k: v for k, v in best.items() if k not in ("curve", "curve_net")} | {"curve": best["curve_net"], "monthly": monthly(best["curve_net"])},
            "prev": {k: v for k, v in prev.items() if k not in ("curve", "curve_net")} | {"curve": prev["curve_net"], "monthly": monthly(prev["curve_net"])},
            "b0050": {"total_return_pct": bw["bench_0050"]["total_return_pct"], "max_dd_pct": bw["bench_0050"]["max_dd_pct"], "curve": bw["bench_0050"]["curve"], "monthly": monthly(bw["bench_0050"]["curve"])},
            "ew": {"total_return_pct": bw["bench_tw50_ew"]["total_return_pct"], "max_dd_pct": bw["bench_tw50_ew"]["max_dd_pct"], "curve": bw["bench_tw50_ew"]["curve"], "monthly": monthly(bw["bench_tw50_ew"]["curve"])},
            "trades": trades, "held": held,
        }
        print(win, "v3", best["net_return_pct"], best["net_max_dd_pct"], best["n_trade_days"], "| v2", prev["net_return_pct"], "| held", [h["code"] for h in held])

    # 最新排名(9/10 收盤 → 9/11 下單)與持股狀態
    p = pd.read_parquet(os.path.join(HERE, "..", "results", "tw50_h5_permpos_fullpred.parquet"))["p"].unstack("ticker").sort_index()
    rk = p.rank(axis=1, ascending=False)
    last = p.index.max()
    top = p.loc[last].sort_values(ascending=False)
    out["latest"] = {"date": last.strftime("%Y-%m-%d"), "top": [{"rank": i + 1, "code": code(t), "name": NAMES.get(code(t), ""), "p": round(float(v), 4)} for i, (t, v) in enumerate(top.head(10).items())]}
    for h in out["full"]["held"]:
        t = f"{h['code']}.TW"
        r = rk.loc[rk.index >= pd.Timestamp(h["buy_date"]) - pd.Timedelta(days=7), t]
        streak = 0
        for v in r.values[::-1]:
            if v > CFG["exit_rank"]:
                streak += 1
            else:
                break
        h["rank_now"] = int(rk.loc[last, t])
        h["out_streak"] = streak

    # 模型版本與訓練參數
    meta = json.load(open(os.path.join(XGB, "experiments", f"{TAG}.json"), encoding="utf-8"))
    res = meta["results"][SET]
    from importlib import util
    spec = util.spec_from_file_location("tx", os.path.join(XGB, "src", "train_xgb.py"))
    tx = util.module_from_spec(spec); spec.loader.exec_module(tx)
    params = dict(tx.DEFAULT_PARAMS) | meta["config"]["xgb"]
    imp = pd.read_csv(os.path.join(XGB, "experiments", f"{TAG}_importance.csv"), index_col=0)
    feats = imp.loc[res["features"]].sort_values("rank_mean")
    out["model"] = {
        "tag": TAG, "featset": SET, "trained": meta["time"], "pool": "tw50", "n_stocks": len(tw50),
        "data": "yfinance 還原權息日 K(開高低收量),2016-01-04 起", "label": meta["label"], "horizon": meta["config"]["horizon"],
        "split": {"train": ["2016-01-04", meta["config"]["train_end"]], "val": ["2025-01-01", meta["config"]["val_end"]], "test": ["2026-01-02", "2026-09-10"]},
        "n": {"train": meta["n_train"], "val": meta["n_val"], "test": meta["n_test"], "scored": 8400},
        "params": params, "seeds": meta["config"]["seeds"], "corr_thr": meta["config"]["corr_thr"], "max_nan": meta["config"]["max_nan"],
        "per_seed": [{"seed": s["seed"], "iter": s["best_iter"], "val_auc": round(s["val"]["auc"], 4), "val_acc": round(s["val"]["acc"], 4),
                      "test_auc": round(s["test"]["auc"], 4), "test_acc": round(s["test"]["acc"], 4)} for s in res["per_seed"]],
        "ens_test": {k: round(v, 4) for k, v in res["ensemble"]["test"].items()},
        "decile": res["ensemble"]["decile"]["h5"]["decile_ann_ret_pct"],
        "funnel": [{"step": "全部技術指標", "n": meta["results"]["full"]["n_feat"] + len(meta["results"]["full"].get("dedupe_dropped", [])) * 0},
                   {"step": "缺值 ≤ 30%、非常數", "n": meta["results"]["full"]["n_feat"]},
                   {"step": "高度相關去重(|ρ| > 0.95)", "n": meta["results"]["full"]["n_feat"] - len(meta["results"]["full"].get("dedupe_dropped", []))},
                   {"step": "驗證集排列重要性 > 0(permpos)", "n": res["n_feat"]}],
        "alt_auc": {n: round(meta["results"][n]["ensemble"]["test"]["auc"], 4) for n in ["classic4", "paper9", "full", "full_top20", SET]},
        "families": {FAM[k]: int(v) for k, v in feats["family"].value_counts().items()},
        "features": [{"i": i + 1, "name": n, "fam": FAM.get(r["family"], r["family"]), "desc": desc(n), "gain": round(float(r["gain_mean"]) * 100, 3),
                      "perm": round(float(r["perm_mean"]) * 1000, 3)} for i, (n, r) in enumerate(feats.iterrows())],
        "stocks": [{"code": code(t), "name": NAMES.get(code(t), "")} for t in TICKER_SETS["tw50"]],
    }

    # 規則比較:三種「還在名次內就不換」
    hr = json.load(open(os.path.join(HERE, "out", "summary_hold_rules.json"), encoding="utf-8"))
    b = [r for r in hr.values() if r["window"] == "全年" and r["K"] == 3 and r["fam"] == "B 連續掉出"]
    out["grid_b"] = [{"N": r["N"], "M": r["M"], "net": r["net_return_pct"], "mdd": r["net_max_dd_pct"], "days": r["n_trade_days"], "jul": r.get("jul")} for r in b]
    fams = {}
    for r in hr.values():
        if r["window"] == "全年" and r["K"] == 3 and r["fam"] != "原最佳":
            f = fams.setdefault(r["fam"], [])
            f.append(r)
    out["families_cmp"] = [{"fam": f, "n": len(v), "mean": round(sum(x["net_return_pct"] for x in v) / len(v), 1),
                            "best": max(v, key=lambda x: x["net_return_pct"])["net_return_pct"],
                            "jul_mean": round(sum(x.get("jul", 0) for x in v) / len(v), 1)} for f, v in fams.items()]

    ph = json.load(open(os.path.join(HERE, "out", "fullyear_phase_sensitivity.json"), encoding="utf-8"))
    avg = lambda k: round(sum(r[k] for r in ph) / len(ph), 1)
    nc = json.load(open(os.path.join(HERE, "out", "summary_ncku.json"), encoding="utf-8"))
    out["path"] = [
        {"stage": "KLINE K 線型態(系統 A)", "setting": "1 日 7 特徵,訊號做多持有 5 日", "net": None, "gross": nc["kline_1d7"]["total_return_pct"], "note": "框架未扣成本;平均只有四成資金在場"},
        {"stage": "Chart-GCN(系統 B)", "setting": "gridbest h=5,前 10% 每 5 日換", "net": None, "gross": nc["cgcn_h5_rank"]["total_return_pct"], "note": "框架未扣成本;模型輸出近乎常數,排序不可信"},
        {"stage": "XGB + 交易邏輯", "setting": "5 日檢視、抱 5 檔、大盤濾網、前 10 名續抱、3×ATR 停損 + 30% 停利", "net": avg("系統扣成本"), "gross": None, "note": "5 種起跑日平均"},
        {"stage": "XGB 只有模型", "setting": "5 日檢視、抱 5 檔、每次全換", "net": avg("只有模型扣成本"), "gross": None, "note": "5 種起跑日平均,範圍 +106% ~ +213%"},
        {"stage": "上一版", "setting": "每日檢視、抱 3 檔、掉出前 3 名且抱滿 10 日才換", "net": out["full"]["prev"]["net_return_pct"], "gross": None, "note": f"7/1 起 {out['jul']['prev']['net_return_pct']:+.1f}%"},
        {"stage": "最佳系統", "setting": "每日檢視、抱 3 檔、掉出前 8 名連續 2 天才換", "net": out["full"]["best"]["net_return_pct"], "gross": None, "note": f"前 10 名 / 連 2 天也有 +235%;7/1 起 {out['jul']['best']['net_return_pct']:+.1f}%"},
    ]
    fp = os.path.join(HERE, "..", "results", "final_best.json")
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[SAVED]", os.path.relpath(fp, HERE), "features", len(out["model"]["features"]))


if __name__ == "__main__":
    main()
