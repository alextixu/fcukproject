"""推薦頁的兩個標記:連續第 N 天、已 M 天沒破底 / 沒創高;只用當天以前的資料。"""
import pandas as pd

from kpweb_helpers import make_bars
from system import signals as SG


def _s(vals, idx):
    return pd.Series(vals, index=idx)


def test_run_length():
    """Given 判斷序列 none, low, low, high, low, low, low / When 算結尾連續判低點幾天 / Then 3 天;最後一天不是 low 時是 0"""
    assert SG.run_length(["none", "low", "low", "high", "low", "low", "low"], "low") == 3
    assert SG.run_length(["low", "low", "none"], "low") == 0
    assert SG.run_length([], "low") == 0


def test_hold_days_low_and_high():
    """Given 訊號日收盤 100 / When 之後收盤 101, 100, 105(都 ≥ 100)/ Then 已 3 天沒破底;其中一天 99.9 → 已破底(None);
    判高點反過來:之後收盤都 ≤ 100 才算沒創高;超過 5 天顯示 5"""
    assert SG.hold_days([101, 100, 105], 100, "low") == 3
    assert SG.hold_days([101, 99.9, 105], 100, "low") is None
    assert SG.hold_days([], 100, "low") == 0
    assert SG.hold_days([99, 100], 100, "high") == 2 and SG.hold_days([99, 100.1], 100, "high") is None
    assert SG.hold_days([101] * 8, 100, "low") == 5


def test_active_signal_counts_days_and_run():
    """Given 收盤 10 天:第 5、6 天判低點(收盤 95、94),之後 3 天收盤 96、97、95 / When 第 9 天收盤後看 /
    Then 最近一次訊號是第 6 天,已 3 天沒破底,連續第 2 天"""
    closes = [100, 99, 98, 97, 95, 94, 96, 97, 95]
    df = make_bars(closes)
    preds = _s(["none", "none", "none", "none", "low", "low", "none", "none", "none"], df.index)
    a = SG.active_signal(preds, df["close"], "low")
    assert a == {"date": str(df.index[5].date()), "days": 3, "run": 2}


def test_active_signal_broken_or_too_old():
    """Given 判低點後有一天收盤跌破訊號日 / When 看今天 / Then 不列出(已破底);
    Given 訊號是 6 個交易日以前 / Then 也不列出(答案已揭曉);Given 今天剛判 / Then 剛出現(0 天)"""
    df = make_bars([100, 99, 98, 97, 95, 94, 93, 97, 98])
    preds = _s(["none"] * 5 + ["low"] + ["none"] * 3, df.index)
    assert SG.active_signal(preds, df["close"], "low") is None                   # 第 7 天 93 < 94
    df2 = make_bars([100, 90, 91, 92, 93, 94, 95, 96, 97])
    preds2 = _s(["none", "low"] + ["none"] * 7, df2.index)
    assert SG.active_signal(preds2, df2["close"], "low") is None                  # 7 天前
    preds3 = _s(["none"] * 8 + ["low"], df2.index)
    assert SG.active_signal(preds3, df2["close"], "low")["days"] == 0
    assert SG.group_of(0) == "new" and SG.group_of(2) == "d12" and SG.group_of(3) == "d3" and SG.group_of(5) == "d3"


def test_no_lookahead_with_real_archive(real_store):
    """Given 回放存檔(每天當天凍結的判斷)與真實 K 線 / When 只給到 D 日為止的 K 線和存檔算標記,和給完整 K 線、完整存檔(到 2026-09-10)算 /
    Then 每檔、每天、兩個方法的標記完全相同;把 D 日之後的價格全部改掉也一樣(不偷看未來)"""
    import os
    import pytest
    from system import config as C, publish as PB, store as ST
    if not os.path.isdir(os.path.join(C.DATA, "tw100", "days")):
        pytest.skip("沒有回放存檔(先跑 run.py replay)")
    tab = ST.table()
    checked = 0
    for code in ("2330", "8046", "8454", "2618"):
        g = tab[tab.code == code].assign(date=lambda x: pd.to_datetime(x.date)).set_index("date")
        df = real_store.load(f"{code}.TW").loc[:"2026-09-10"]
        for d in ("2026-03-12", "2026-06-15", "2026-08-20", "2026-09-04"):
            D = pd.Timestamp(d)
            _, full = PB.stock_active(g, df, D)
            _, cut = PB.stock_active(g.loc[:D], df.loc[:D], D)
            fake = df.copy()
            fake.loc[fake.index > D, ["open", "high", "low", "close"]] *= 0.5
            _, alt = PB.stock_active(g, fake, D)
            assert full == cut == alt
            checked += bool(full)
    assert checked > 0                                    # 至少有幾天真的有訊號,測試才有意義
