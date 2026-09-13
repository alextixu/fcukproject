"""
事件驅動取樣與 triple-barrier 標籤 (2026-08 新增, 見實驗記錄 §十三).

zigzag_confirm(close, x):
    因果 (causal) ZigZag 轉折確認. 追蹤目前 swing 的極值, 當收盤價自極值
    反向走滿 x (比例) 的第一天即為「確認日」. 確認日只用 <= t 的資料, 無前視;
    轉折日 (極值所在日) 是事後才知道的, 不可作為決策點.
    回傳 [(confirm_idx, swing_dir, turn_idx), ...]
        swing_dir = +1: 剛確認「底部」, 新 swing 向上
                    -1: 剛確認「頂部」, 新 swing 向下

triple_barrier(close, t, up, dn, T):
    自決策日 t 起 (只看 t+1..t+T), 收盤價相對 close[t] 先觸及 +up → 1,
    先觸及 -dn → 0; T 日內皆未觸及 → 以到期日報酬正負決定 (維持二分類).
    資料不足 T 日 → None (呼叫端丟棄; 與 derive_horizon_ds 的尾端處理同精神).
    回傳 (label, hit)  hit ∈ {"up", "dn", "time"}
"""
import numpy as np


def zigzag_confirm(close, x):
    close = np.asarray(close, dtype=float)
    n = len(close)
    events = []
    if n < 2:
        return events
    hi_i = lo_i = 0
    direction = 0          # 0: 尚未確認任何轉折
    for t in range(1, n):
        c = close[t]
        if direction == 0:
            if c > close[hi_i]:
                hi_i = t
            if c < close[lo_i]:
                lo_i = t
            if c <= close[hi_i] * (1 - x):
                events.append((t, -1, hi_i))
                direction = -1
                lo_i = hi_i + int(np.argmin(close[hi_i:t + 1]))
            elif c >= close[lo_i] * (1 + x):
                events.append((t, +1, lo_i))
                direction = +1
                hi_i = lo_i + int(np.argmax(close[lo_i:t + 1]))
        elif direction == +1:          # swing 向上, 等待頂部確認
            if c > close[hi_i]:
                hi_i = t
            elif c <= close[hi_i] * (1 - x):
                events.append((t, -1, hi_i))
                direction = -1
                lo_i = hi_i + int(np.argmin(close[hi_i:t + 1]))
        else:                          # swing 向下, 等待底部確認
            if c < close[lo_i]:
                lo_i = t
            elif c >= close[lo_i] * (1 + x):
                events.append((t, +1, lo_i))
                direction = +1
                hi_i = lo_i + int(np.argmax(close[lo_i:t + 1]))
    return events


def triple_barrier(close, t, up, dn, T):
    close = np.asarray(close, dtype=float)
    if t + T > len(close) - 1:
        return None
    c0 = close[t]
    for k in range(t + 1, t + T + 1):
        r = close[k] / c0 - 1.0
        if r >= up:
            return 1, "up"
        if r <= -dn:
            return 0, "dn"
    return (1 if close[t + T] > c0 else 0), "time"


if __name__ == "__main__":
    # 自我檢查: 人造序列 100 → 110 → 100 → 112
    s = np.array([100, 103, 106, 110, 108, 104.4, 102, 100, 103, 105.1, 108, 112])
    ev = zigzag_confirm(s, 0.05)
    print("events:", ev)
    # 預期: t=2 (106 >= 100*1.05) 確認初始底部@0, 方向 +1;
    #       t=5 (104.4 <= 110*0.95) 確認頂部@3, 方向 -1;
    #       t=9 (105.1 >= 100*1.05) 確認底部@7, 方向 +1
    assert ev == [(2, 1, 0), (5, -1, 3), (9, 1, 7)], ev
    print("tb from t=9:", triple_barrier(s, 9, 0.05, 0.05, 5))
    print("tb from t=9 (T too long):", triple_barrier(s, 9, 0.05, 0.05, 20))
    print("OK")
