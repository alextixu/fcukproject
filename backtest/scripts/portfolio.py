"""共用:由「每日每檔 P(漲) + 未來 h 日報酬」算 2026 年可交易組合曲線。

輸入 DataFrame:MultiIndex (date, ticker),欄位 r_h{h}(決策日收盤 → h 日後收盤報酬)與若干 p_* 機率欄。
每 h 個交易日再平衡一次(非重疊持有):
  long  = 機率前 10%(等權)          short = 機率後 10%(等權)
  H-L   = long − short(零成本多空,與 evaluate.py / decile_ls.py 同定義)
成本:每次換倉,兩腿各自 (本期成員中上期不在者的比例) × 一趟成本 COST_RT(0.585%,同 xgb evaluate.py)。
基準:同池等權買進持有、0050。
"""
import numpy as np
import pandas as pd

COST_RT = 0.00585
TDAYS = 246


def _turnover(cur: set, prev: set | None) -> float:
    if prev is None:
        return 1.0
    return 1 - len(cur & prev) / max(len(cur), 1)


def portfolio_curves(df: pd.DataFrame, pcol: str, h: int, n_dec: int = 10, min_n: int = 30,
                     cost_rt: float = COST_RT, seed: int = 20260905) -> dict | None:
    rcol = f"r_h{h}"
    rng = np.random.default_rng(seed)
    dates = np.array(sorted(df.index.get_level_values("date").unique()))
    rebal = dates[::h]
    rows = []
    prev_lo = prev_hi = None
    for d in rebal:
        sub = df.xs(d, level="date")[[pcol, rcol]].dropna()
        if len(sub) < min_n:
            continue
        p = sub[pcol].values
        r = sub[rcol].values
        tk = sub.index.values
        shuf = rng.permutation(len(p))                       # 平手隨機打散(同 2026-09-05 修正)
        order = shuf[np.argsort(p[shuf], kind="stable")]
        k = len(p) // n_dec
        lo_i, hi_i = order[:k], order[-k:]
        lo, hi = set(tk[lo_i]), set(tk[hi_i])
        t_lo, t_hi = _turnover(lo, prev_lo), _turnover(hi, prev_hi)
        rows.append({"date": d, "long": r[hi_i].mean(), "short": r[lo_i].mean(), "ew": r.mean(),
                     "long_cost": t_hi * cost_rt, "short_cost": t_lo * cost_rt,
                     "n": len(p), "degenerate": bool(p.std() < 0.01)})
        prev_lo, prev_hi = lo, hi
    if not rows:
        return None
    t = pd.DataFrame(rows).set_index("date")
    t["long_net"] = t["long"] - t["long_cost"]
    t["hl"] = t["long"] - t["short"]
    t["hl_net"] = t["hl"] - t["long_cost"] - t["short_cost"]
    ppy = TDAYS / h

    def stats(x: pd.Series) -> dict:
        sd = x.std(ddof=1)
        return {"cum_pct": round(float(np.prod(1 + x) - 1) * 100, 2),
                "ann_pct": round(float(x.mean() * ppy) * 100, 2),
                "sharpe": round(float(x.mean() / sd * np.sqrt(ppy)), 2) if sd > 0 else 0.0,
                "t": round(float(x.mean() / (sd / np.sqrt(len(x)))), 2) if sd > 0 else 0.0,
                "win_rate": round(float((x > 0).mean()), 3),
                "max_dd_pct": round(float(((1 + x).cumprod() / (1 + x).cumprod().cummax() - 1).min()) * 100, 2)}

    return {
        "h": h, "n_periods": int(len(t)), "n_degenerate": int(t["degenerate"].sum()),
        "turnover_long": round(float(t["long_cost"].mean() / cost_rt), 3),
        "long_gross": stats(t["long"]), "long_net": stats(t["long_net"]),
        "short_gross": stats(t["short"]),
        "hl_gross": stats(t["hl"]), "hl_net": stats(t["hl_net"]),
        "ew_same_dates": stats(t["ew"]),
        "curve": {"long_net": ((1 + t["long_net"]).cumprod() - 1),
                  "hl_net": ((1 + t["hl_net"]).cumprod() - 1),
                  "ew": ((1 + t["ew"]).cumprod() - 1)},
    }


def buy_hold(close: pd.Series, start: str, end: str) -> float:
    c = close.loc[start:end].dropna()
    return float(c.iloc[-1] / c.iloc[0] - 1) if len(c) > 1 else np.nan
