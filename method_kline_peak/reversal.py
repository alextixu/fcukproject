"""單一股票反手交易:判高點 → 做多,判低點 → 做空(2026-11-02 使用者要求)。

訊號在 t 日收盤出現,t+1 開盤執行:
  - 還沒有部位:等第一個「判高點」才開始(之前的判低點不理會),t+1 開盤全部資金買進
  - 做多中判低點:t+1 開盤賣出,同一個開盤價反手放空(保證金 = 股數 × 放空價,不加槓桿、不計借券費)
  - 做空中判高點:t+1 開盤回補,同一個開盤價反手做多
  - 同方向的訊號重複出現不理會;期末最後一天收盤平倉
  - allow_short=False(只做多):做多中判低點 → t+1 開盤賣出後空手,等下一個判高點再買
成本:做多 買 buy_fee、賣 sell_fee + tax;做空 放空時 sell_fee + tax、回補時 buy_fee(同 backtest_years.TradeRule)。
"""
import math

import pandas as pd

from backtest_years import TradeRule
from learn5_trade6 import UP, DOWN


def simulate_reversal(px, pred, start, end, rule=TradeRule(), allow_short=True):
    """px: DataFrame[open, close](一檔股票);pred: Series(index = 日期,值 = 低點 / 非極值 / 高點)。
    回傳 {"equity": 每日收盤總資產 Series, "trades": 成交明細(side = 做多 / 做空,how = 反手 / 低點賣出 / 期末)}。"""
    px = px.loc[pd.Timestamp(start):pd.Timestamp(end)]
    days = px.index
    cash, pos, sh, entry_px, basis, entry_d = rule.init_cash, 0, 0, 0.0, 0.0, None
    pending, trades, equity = None, [], {}

    def close_pos(d, p, how):
        nonlocal cash, pos, sh
        if pos == 1:
            proceeds = sh * p * (1 - rule.sell_fee - rule.tax)
        else:
            proceeds = basis + sh * (entry_px * (1 - rule.sell_fee - rule.tax) - p * (1 + rule.buy_fee))
        cash += proceeds
        trades.append({"side": "做多" if pos == 1 else "做空", "entry": entry_d, "exit": d, "entry_px": entry_px, "exit_px": p,
                       "shares": sh, "net_ret": proceeds / basis - 1, "pnl": proceeds - basis, "how": how})
        pos, sh = 0, 0

    def open_pos(d, p, side):
        nonlocal cash, pos, sh, entry_px, basis, entry_d
        fee = rule.buy_fee if side == 1 else 0.0
        n = math.floor(cash / (p * (1 + fee)))
        if n <= 0:
            return
        pos, sh, entry_px, entry_d = side, n, p, d
        basis = n * p * (1 + fee)                                     # 做多:買進金額含手續費;做空:保證金
        cash -= basis

    for k, d in enumerate(days):
        o, c = px.at[d, "open"], px.at[d, "close"]
        if pending is not None:                                       # 開盤:執行昨天收盤的訊號
            if pos != 0:
                close_pos(d, o, "反手" if pending else "低點賣出")
            if pending:
                open_pos(d, o, pending)
            pending = None
        if k == len(days) - 1:                                        # 期末:收盤平倉
            if pos != 0:
                close_pos(d, c, "期末")
        else:
            p = pred.get(d)
            if p == DOWN and pos != 1:                                # 判高點 → 做多(第一筆一定從這裡開始)
                pending = 1
            elif p == UP and pos == 1:                                # 做多中判低點 → 反手做空(只做多時:只賣出)
                pending = -1 if allow_short else 0
        if pos == 1:
            equity[d] = cash + sh * c
        elif pos == -1:
            equity[d] = cash + basis + sh * (entry_px * (1 - rule.sell_fee - rule.tax) - c)
        else:
            equity[d] = cash
    return {"equity": pd.Series(equity), "trades": pd.DataFrame(trades)}
