"""「還在一定名次內就不要換」的三種做法(每日檢視、不看大盤、不設停損停利、流動性 2,000 張、官方資料、扣成本)。

  A 放寬續抱名次:持股還在前 N 名就不賣,不設最短持有
  B 連續掉出才賣:掉出前 N 名連續 M 個交易日才賣
  C 平滑分數排名:每檔股票的模型機率取近 w 日平均後再排名(只用當日以前的分數),持股還在前 N 名就不賣
另附原最佳系統(前 3 名 + 抱滿 10 日)當基準。K = 3(主)與 5(對照)。全年排名,前幾名再跑 7/1 起。
用法: NCKU_SRC=official python run_hold_rules.py
輸出: out/hold_rules/*.xlsx、out/summary_hold_rules.json
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
import run_ncku as R                                   # noqa: E402
from run_ncku import assemble_csv, code                 # noqa: E402
from run_logic import load_indicators                   # noqa: E402
import run_logic2 as L2                                 # noqa: E402
from data_loader import TICKER_SETS                     # noqa: E402

OUT = os.path.join(HERE, "out", "hold_rules")
os.makedirs(OUT, exist_ok=True)
SUMM = os.path.join(HERE, "out", "summary_hold_rules.json")
PRED = os.path.join(HERE, "..", "results", "tw50_h5_permpos_fullpred.parquet")
END = "20260911"


def rankings(start, w):
    """每日排名;w > 1 時用各股近 w 日機率平均(含當日,只看過去)。"""
    p = pd.read_parquet(PRED)["p"].unstack("ticker").sort_index()
    if w > 1:
        p = p.rolling(w, min_periods=1).mean()
    p = p[p.index >= pd.Timestamp(start)]
    return {d.strftime("%Y%m%d"): [code(t) for t in row.dropna().sort_values(ascending=False).index] for d, row in p.iterrows()}


def main():
    summ = json.load(open(SUMM, encoding="utf-8")) if os.path.exists(SUMM) else {}
    tw50 = [code(t) for t in TICKER_SETS["tw50"]]
    avail = assemble_csv(tw50 + ["0050"])
    with open(os.path.join(HERE, "tmp", "save_data_info.yaml"), "w") as f:
        f.write(f"end_date: '{END}'\nstart_date: '20251001'\n")
    uni = [c for c in tw50 if c in avail]
    ind, liq, mkt = load_indicators(uni), L2.load_liquidity(uni), L2.load_market()
    cache = {}

    def run(win, fam, k, n, m=1, w=1, mh=0):
        key = f"{win}|{fam}|K{k}|前{n}名|連{m}日|平均{w}日|最短{mh}日"
        if key in summ:
            return summ[key]
        start = "20260102" if win == "全年" else "20260630"
        R.START, R.END, L2.START, L2.END = start, END, start, END
        if (start, w) not in cache:
            cache[(start, w)] = rankings(start, w)
        st = L2.Logic2(key, uni, cache[(start, w)], ind, liq, mkt, L2.LIQ["vol2k"], L2.MKT["none"], n, None, None,
                       topk=k, maxrank=max(15, 2 * k), min_hold=mh, out_days=m)
        r = L2.run_one(key.replace("|", "_"), st, uni, OUT)
        summ[key] = {x: v for x, v in r.items() if x not in ("curve", "curve_net")} | {"window": win, "fam": fam, "K": k, "N": n, "M": m, "w": w, "mh": mh}
        json.dump(summ, open(SUMM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return summ[key]

    combos = []
    for k in (3, 5):
        combos.append(("原最佳", k, k, 1, 1, 10))
        combos += [("A 放寬名次", k, n, 1, 1, 0) for n in (k, 5, 8, 10, 15, 20) if n >= k]
        combos += [("B 連續掉出", k, n, m, 1, 0) for n in (k, 5, 8, 10) if n >= k for m in (2, 3, 5)]
        combos += [("C 平滑分數", k, n, 1, w, 0) for n in (k, 5, 8, 10, 15) if n >= k for w in (3, 5, 10)]
    combos = list(dict.fromkeys(combos))
    print(f"全年 {len(combos)} 組", flush=True)
    for i, c in enumerate(combos, 1):
        run("全年", *c)
    rows = [r for r in summ.values() if r["window"] == "全年"]
    for r in rows:
        j = run("7月後", r["fam"], r["K"], r["N"], r["M"], r["w"], r["mh"])
        r["jul"] = j["net_return_pct"]; r["jul_mdd"] = j["net_max_dd_pct"]
    json.dump(summ, open(SUMM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[SAVED]", os.path.relpath(SUMM, HERE), len(summ))


if __name__ == "__main__":
    main()
