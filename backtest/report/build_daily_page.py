"""每日選股推薦頁:把採用版本(tw50 h5、95 欄 + Autoencoder 17 欄 → XGBoost;抱 3 檔、前 8 名內續抱、連 2 天掉出才賣、
3×ATR 停損 + 30% 停利、隔日開盤成交、扣手續費與證交稅)的系統輸出組成頁面資料,灌進 daily_template.html。
輸入: results/fullpred_<TAG>_aefull.parquet 的 <PCOL>、ncku/out/strategy_grid_ae_x26/ 的回測 xlsx、common/cache/official 官方日資料。
每日動作由「委託紀錄 + 排名」重建,並逐筆對回測紀錄驗證(不一致就中止),不另外重跑回測。
用法: python build_daily_page.py [--out <html>]   → backtest/report/out/daily_page.html、daily_page_data.json"""
import argparse, json, os, sys
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, ROOT)
from common import paths as P
TAG, PCOL = "x26-tw50-h5-cs-xf", "p_ae"
K, EXIT_RANK, OUT_DAYS, MAXRANK, MIN_LOTS, TAKE = 3, 8, 2, 15, 2000, 0.30
FEE_BUY, FEE_SELL, INIT = 0.001425, 0.001425 + 0.003, 1_000_000.0
XLSX = os.path.join(P.NCKU, "out", "strategy_grid_ae_x26", f"{TAG}_aefull:{PCOL}_全年_K3_前8名_連2天_3ATR_30pct_none.xlsx")
EW_XLSX = os.path.join(P.NCKU, "out", "strategy_grid_ae_x26", "ew_全年.xlsx")


def official(c):
    x = pd.read_parquet(os.path.join(P.OFFICIAL, f"{c}.parquet")); x["date"] = pd.to_datetime(x["date"])
    return x.sort_values("date").drop_duplicates("date").set_index("date")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=os.path.join(HERE, "out", "daily_page.html")); a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    names = {k: v["name"] for k, v in json.load(open(os.path.join(P.NCKU, "backtest", "stock_api", "stock_symbol_map.json"), encoding="utf-8")).items()}
    p = pd.read_parquet(os.path.join(P.RESULTS, f"fullpred_{TAG}_aefull.parquet"))[PCOL].unstack("ticker").sort_index()
    p.columns = [t.split(".")[0] for t in p.columns]
    px = {c: official(c) for c in list(p.columns) + ["0050"] if os.path.exists(os.path.join(P.OFFICIAL, f"{c}.parquet"))}
    p = p[[c for c in p.columns if c in px]]                       # 與回測同口徑:只留有官方資料的股票
    vol5 = {c: (x["capacity"].astype(float) / 1000).rolling(5).mean() for c, x in px.items()}

    orders = pd.read_excel(XLSX, sheet_name="歷史交易委託", dtype={"股票代碼": str}); orders["交易日期"] = pd.to_datetime(orders["交易日期"])
    daily = pd.read_excel(XLSX, sheet_name="每日資產變化"); daily["記錄日期"] = pd.to_datetime(daily["記錄日期"])
    tdays = list(daily["記錄日期"]); nxt = dict(zip(tdays[:-1], tdays[1:]))
    fee = orders.assign(f=orders["成交價格"] * orders["交易股數"] * orders["交易動作"].map({"買入": FEE_BUY, "賣出": FEE_SELL})).groupby("交易日期")["f"].sum()
    eq = (daily["股票資產價值"] + daily["現金資產"] - daily["記錄日期"].map(fee).fillna(0).cumsum()) / INIT
    eq.index = tdays
    ew = pd.read_excel(EW_XLSX, sheet_name="每日資產變化"); ew_eq = ((ew["股票資產價值"] + ew["現金資產"]) / INIT).set_axis(pd.to_datetime(ew["記錄日期"]))
    o50 = px["0050"]; b50 = (o50["close"] / o50.loc[tdays[1], "open"]).reindex(tdays); b50.iloc[0] = 1.0   # 與策略同一天(第 2 個交易日開盤)進場

    held, out_cnt, days, n_done, mism = {}, {}, [], 0, []      # held: code → {entry, date}
    for d in p.index:
        if d not in nxt: continue                                  # 預測檔有、但官方行事曆沒開市的日子(如颱風假),回測不會用到
        n = nxt[d]; row = p.loc[d].dropna().sort_values(ascending=False); rank = {c: i + 1 for i, c in enumerate(row.index)}
        med = float(row.median())
        liq_ok = {c: bool(d in vol5[c].index and vol5[c].loc[d] >= MIN_LOTS) for c in row.index}
        for c in held:
            out_cnt[c] = 0 if rank.get(c, 999) <= EXIT_RANK else out_cnt.get(c, 0) + 1
        keep = {c for c in held if out_cnt[c] < OUT_DAYS}
        cands = [c for c in list(row.index)[:MAXRANK] if liq_ok[c] and c not in keep]
        exp_sell, exp_buy = set(held) - keep, cands[:K - len(keep)]
        od = orders[orders["交易日期"] == n]
        sells = {r["股票代碼"]: float(r["成交價格"]) for _, r in od[od["交易動作"] == "賣出"].iterrows()}
        buys = {r["股票代碼"]: float(r["成交價格"]) for _, r in od[od["交易動作"] == "買入"].iterrows()}
        if set(buys) != set(exp_buy) or not exp_sell <= set(sells):
            mism.append((d.date(), sorted(exp_sell), sorted(sells), exp_buy, sorted(buys)))
        intraday = []                                              # 隔日盤中觸及停損 / 停利(收盤時無法預知)
        for c in set(sells) - exp_sell:
            ret = sells[c] / held[c]["entry"] - 1
            intraday.append({"c": c, "kind": "tp" if ret >= TAKE - 1e-9 else "sl", "px": sells[c], "ret": round(ret * 100, 2)})
        act = {c: ("sell" if c in exp_sell else "hold") for c in held} | {c: "buy" for c in buys}
        show = [c for c in row.index if rank[c] <= 10 or c in act]
        days.append({"d": d.strftime("%Y-%m-%d"), "n": n.strftime("%Y-%m-%d"), "med": round(med, 4), "npool": len(row),
                     "rows": [{"r": rank[c], "c": c, "nm": names.get(c, c), "pt": round((float(row[c]) - med) * 100, 2), "a": act.get(c, "watch"),
                               "liq": liq_ok[c], "out": out_cnt.get(c, 0) if c in held else None,
                               "ret": round((float(px[c].loc[d, "close"]) / held[c]["entry"] - 1) * 100, 2) if c in held else None} for c in show],
                     "sell": [{"c": c, "nm": names.get(c, c)} for c in sorted(exp_sell)], "buy": [{"c": c, "nm": names.get(c, c), "r": rank[c]} for c in exp_buy],
                     "intraday": [x | {"nm": names.get(x["c"], x["c"])} for x in intraday],
                     "eq": round(float(eq[d] - 1) * 100, 2), "mdd": round(float((eq[:d] / eq[:d].cummax() - 1).min()) * 100, 2), "trades": n_done,
                     "b50": round(float(b50[d] - 1) * 100, 2), "ew": round(float(ew_eq[d] - 1) * 100, 2)})
        n_done += len(sells)
        for c in sells: held.pop(c)
        for c, v in buys.items(): held[c] = {"entry": v, "date": n}
    if mism:
        for m in mism: print("[MISMATCH]", m)
        sys.exit(f"重建的動作與回測委託紀錄不一致({len(mism)} 天),中止")
    last = tdays[-1]
    data = {"tag": f"{TAG}:{PCOL}", "rule": {"K": K, "exit_rank": EXIT_RANK, "out_days": OUT_DAYS, "maxrank": MAXRANK, "min_lots": MIN_LOTS, "take_pct": TAKE * 100},
            "days": days, "curve": [{"d": d.strftime("%Y-%m-%d"), "s": round(float(eq[d] - 1) * 100, 2), "b": round(float(b50[d] - 1) * 100, 2), "e": round(float(ew_eq[d] - 1) * 100, 2)} for d in tdays],
            "final": {"d": last.strftime("%Y-%m-%d"), "eq": round(float(eq[last] - 1) * 100, 2), "mdd": round(float((eq / eq.cummax() - 1).min()) * 100, 2), "trades": n_done, "b50": round(float(b50[last] - 1) * 100, 2)}}
    print(f"[OK] {len(days)} 個排名日 {days[0]['d']} ~ {days[-1]['d']};動作與委託紀錄 100% 吻合;期末({data['final']['d']})淨 {data['final']['eq']:+.2f}% MDD {data['final']['mdd']}% 交易 {n_done} 筆 0050 {data['final']['b50']:+.2f}%")
    json.dump(data, open(os.path.join(os.path.dirname(a.out), "daily_page_data.json"), "w", encoding="utf-8"), ensure_ascii=False)
    tpl = open(os.path.join(HERE, "daily_template.html"), encoding="utf-8").read()
    open(a.out, "w", encoding="utf-8").write(tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
    print(f"[SAVED] {os.path.relpath(a.out, ROOT)} ({os.path.getsize(a.out)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
