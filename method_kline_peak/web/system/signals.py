"""推薦頁的兩個標記:「連續第 N 天」與「已 M 天沒破底 / 沒創高」。只用判斷日(含)以前已知的資料。

- 連續第 N 天:這檔在訊號日 t 往前,連續幾個交易日都判同一類(t 當天算第 1 天)。判斷來自每日存檔(當天就凍結的判斷)。
- 已 M 天沒破底:最近一次判低點的日子 t 之後,到今天為止每天收盤都 ≥ t 的收盤,M = t 之後已經過的交易日數(上限 5);
  有任何一天收盤 < t 的收盤 → 這個訊號已破底,不再列出。判高點反之(沒創高 = 每天收盤 ≤ t 的收盤)。
  M = 0 表示今天剛判(剛出現)。這就是研究 confirm_signals.py 的確認規則(t+1 ~ t+k 收盤都 ≥ t 收盤,k = M),
  只用到今天以前的價格。超過 5 天的訊號答案已經揭曉,不再列出。
"""
import pandas as pd

CAP = 5


def run_length(preds, kind):
    """preds:依時間排序到訊號日為止的判斷(舊 → 新)。回傳結尾連續等於 kind 的天數。"""
    n = 0
    for p in reversed(list(preds)):
        if p != kind:
            break
        n += 1
    return n


def hold_days(closes_after, close_t, kind):
    """t 之後每天的收盤(到今天為止)。全部沒破底(低點)/ 沒創高(高點)→ 已過天數;否則 None。"""
    c = list(closes_after)
    ok = all(x >= close_t for x in c) if kind == "low" else all(x <= close_t for x in c)
    return min(len(c), CAP) if ok else None


def active_signal(preds, closes, kind, cap=CAP):
    """這檔最近一次判 kind 的訊號,如果還沒破底 / 沒創高就回傳 {date, days, run},否則 None。

    preds:Series,索引 = 交易日(有存檔的日子),值 = 那天的判斷(low / high / none),只含今天以前。
    closes:Series,索引 = 交易日,這檔的收盤(還原價),只含今天以前;最後一天 = 今天。
    只看最近 cap + 1 個交易日(今天和前 cap 天)內的訊號。"""
    if closes is None or not len(closes) or preds is None or not len(preds):
        return None
    window = closes.index[-(cap + 1):]
    hits = [d for d in window if d in preds.index and preds.loc[d] == kind]
    if not hits:
        return None
    t = hits[-1]
    after = closes.loc[closes.index > t]
    days = hold_days(after.to_numpy(), float(closes.loc[t]), kind)
    if days is None:
        return None
    upto = preds.loc[:t]
    # 連續天數只算存檔裡連在一起的交易日(中間缺存檔就停)
    days_idx = closes.index[closes.index <= t]
    seq = []
    for d in reversed(days_idx):
        if d not in upto.index:
            break
        seq.append(upto.loc[d])
    return {"date": str(pd.Timestamp(t).date()), "days": days, "run": run_length(reversed(seq), kind)}


def group_of(days):
    """推薦頁的分組:剛出現 / 已 1–2 天 / 已 3 天以上。"""
    return "new" if days == 0 else "d12" if days <= 2 else "d3"
