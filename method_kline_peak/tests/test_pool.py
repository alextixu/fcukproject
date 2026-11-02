"""股票池:TW100 剔除低波動股(2026-11-02 使用者要求;TW50 時剔除的 16 檔用同一個門檻)。"""
import mainline as ML
from feasibility import START, END, load_pool

TW50_DROPPED = {"2412.TW", "3045.TW", "5880.TW", "2633.TW", "2892.TW", "4904.TW", "2880.TW", "2886.TW",
                "2912.TW", "2884.TW", "1102.TW", "2887.TW", "1216.TW", "2890.TW", "1101.TW", "2891.TW"}


def test_module_rule_reproduces_tw50_drop(data):
    """Given 完整 TW50 50 檔 / When 用門檻 0.725%(每日漲跌幅中位數)找低波動股 /
    Then 正好是 2026-11-02 使用者在 TW50 剔除的 16 檔(中華電 ~ 中信金)"""
    assert set(ML.low_vol(data)) == TW50_DROPPED


def test_module_pool_is_tw100_minus_low_vol():
    """Given TW100(有資料的 95 檔) / When 讀主軸的股票池 / Then 剩 73 檔:每一檔的每日漲跌幅中位數都 ≥ 0.725%,
    TW50 剔除的 16 檔都不在裡面,TW50 其餘 34 檔都在"""
    full = load_pool("tw100", START, END)
    pool = ML.load_data()
    assert len(full) == 95 and len(pool) == 73 and set(pool) <= set(full)
    assert all(ML.daily_move(df) >= ML.MIN_MOVE for df in pool.values())
    tw50 = set(load_pool("tw50", START, END))
    assert not TW50_DROPPED & set(pool) and (tw50 - TW50_DROPPED) <= set(pool)
