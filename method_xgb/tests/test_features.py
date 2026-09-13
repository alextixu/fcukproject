"""smoke test:無 inf、無未來洩漏、欄數。執行:python tests/test_features.py"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from features import single_stock_features  # noqa: E402


def synth(n=400, seed=0):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    o = c * (1 + rng.normal(0, 0.005, n))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.005, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.005, n)))
    v = rng.integers(1000, 100000, n).astype(float)
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": v}, index=idx)


def main():
    df = synth()
    f, fam = single_stock_features(df)
    print(f"欄數 {f.shape[1]};族群:", pd.Series(fam).value_counts().to_dict())
    assert not np.isinf(f.values).any(), "有 inf"
    nan_tail = f.iloc[-1].isna().sum()
    assert nan_tail == 0, f"最後一列仍有 {nan_tail} 個 NaN: {list(f.columns[f.iloc[-1].isna()])}"

    # 未來洩漏:改動 t 之後的價格,t 的特徵不可變
    t = 300
    df2 = df.copy()
    df2.iloc[t + 1:, :4] *= 1.5
    df2.iloc[t + 1:, 4] *= 3
    f2, _ = single_stock_features(df2)
    diff = (f.iloc[:t + 1] - f2.iloc[:t + 1]).abs().max()
    leaky = diff[diff > 1e-9]
    assert leaky.empty, f"未來洩漏欄位: {leaky.to_dict()}"
    print("OK: 無 inf、暖機後無 NaN、無未來洩漏")


if __name__ == "__main__":
    main()
