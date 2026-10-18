"""11 日窗格中心轉折標籤(頂 / 底 / 其他)與決策日因果特徵。

窗格 = t-5 .. t+5 共 11 個交易日,中心日 t 是第 6 天。
  頂(1):中心日的高點嚴格高於左側 5 日、不低於右側 5 日的高點(題目定義:「第 6 天是 11 日的最高點」)
  底(2):中心日的低點嚴格低於左側 5 日、不高於右側 5 日的低點(對稱的另一端)
  其他(0)
  同時是頂又是底(大振幅包覆 K)→ AMBIG(-1),不進訓練也不進評估
  平盤(窗格內有同價高 / 低點,相對差 ≤ TOL)算給第一次出現的那天:每個頂恰好算一次。
  若改成兩側都嚴格,同價雙頂會整個消失,TW50 頂會少 22%,低價低波動股(中華電、金融股)少一半以上。
三種價格口徑(variant):
  hl     = 用 High / Low(題目原始定義)
  close  = 用 Close
  hl_atr = hl 再加幅度門檻:頂之後 5 日內最低價須跌破 H[t] - ATR14,底之後最高價須漲過 L[t] + ATR14

決策時點 = t 收盤。此時只看得到 t-5..t(左半 + 中心),右半 t+1..t+5 就是標籤本身,
所以特徵只能用 ≤ t 的資料(causal_features);把整個 11 日窗格餵給模型 = 標籤洩漏(必得 100%)。
左半條件(left_top / left_bot)在 t 收盤已知,頂 ⊆ left_top、底 ⊆ left_bot。
"""

import numpy as np
import pandas as pd

HALF = 5
# 「嚴格高於」的相對容差:還原價 = 原價 × 還原因子,因子本身有 ~1e-7 的浮點抖動,
# 會把原價上的平盤(同價高點)隨機拆成嚴格大小(兩側嚴格定義下 TW50 頂多出 23%)。1e-5 遠小於一檔跳動單位。
TOL = 1e-5
OTHER, TOP, BOTTOM, AMBIG = 0, 1, 2, -1
CLASS_NAMES = {OTHER: '其他', TOP: '頂', BOTTOM: '底'}
VARIANTS = ('hl', 'close', 'hl_atr')


def side_extreme(s: pd.Series, half: int, future: bool, how: str) -> pd.Series:
    """t 左側(future=False)或右側 half 日的 max / min,不含 t;不足 half 日為 NaN。"""
    sign = -1 if future else 1
    cols = pd.concat([s.shift(sign * k) for k in range(1, half + 1)], axis=1)
    return cols.max(axis=1, skipna=False) if how == 'max' else cols.min(axis=1, skipna=False)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df['close'].shift(1)
    tr = pd.concat([df['high'] - df['low'], (df['high'] - pc).abs(), (df['low'] - pc).abs()],
                   axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def label_window(df: pd.DataFrame, variant: str = 'hl', half: int = HALF) -> pd.DataFrame:
    """回傳 label(0/1/2/-1,邊界 NaN)、left_top / left_bot(t 收盤已知)、tie_top / tie_bot(右側有同價點的頂 / 底)。"""
    hi, lo = (df['close'], df['close']) if variant == 'close' else (df['high'], df['low'])
    lmax, rmax = side_extreme(hi, half, False, 'max'), side_extreme(hi, half, True, 'max')
    lmin, rmin = side_extreme(lo, half, False, 'min'), side_extreme(lo, half, True, 'min')

    up, dn = 1 + TOL, 1 - TOL
    left_top, left_bot = hi > lmax * up, lo < lmin * dn
    top, bot = left_top & (hi >= rmax * dn), left_bot & (lo <= rmin * up)
    tie_top = top & (hi <= rmax * up)
    tie_bot = bot & (lo >= rmin * dn)
    valid = lmax.notna() & rmax.notna()

    if variant == 'hl_atr':
        a = atr(df)
        top &= rmin <= hi - a
        bot &= rmax >= lo + a
        valid &= a.notna()

    label = pd.Series(OTHER, index=df.index, dtype='float64')
    label[top] = TOP
    label[bot] = BOTTOM
    label[top & bot] = AMBIG
    return pd.DataFrame({
        'label': label.where(valid),
        'left_top': left_top.astype('int8'), 'left_bot': left_bot.astype('int8'),
        'tie_top': (tie_top & valid).astype('int8'), 'tie_bot': (tie_bot & valid).astype('int8'),
    }, index=df.index)


def _rsi(c: pd.Series, n: int = 14) -> pd.Series:
    r = c.diff()
    up = r.clip(lower=0).rolling(n, min_periods=n).mean()
    dn = (-r).clip(lower=0).rolling(n, min_periods=n).mean()
    return up / (up + dn)


def causal_features(df: pd.DataFrame, mkt: pd.DataFrame = None, half: int = HALF) -> pd.DataFrame:
    """決策日 t 收盤可得的特徵(只用 ≤ t 的資料)。價格一律以 C[t] 或 ATR 正規化,跨股可比。"""
    O, H, L, C, V = (df[k] for k in ('open', 'high', 'low', 'close', 'volume'))
    lc = np.log(C)
    v20 = V.rolling(20, min_periods=20).mean()
    a14 = atr(df)
    f = {}

    # 形態:窗格左半 + 中心日共 6 根 K 棒(相對 C[t] 的 log 價、相對 20 日均量的 log 量)
    for k in range(half + 1):
        f[f'o{k}'] = np.log(O.shift(k)) - lc
        f[f'h{k}'] = np.log(H.shift(k)) - lc
        f[f'l{k}'] = np.log(L.shift(k)) - lc
        if k:
            f[f'c{k}'] = np.log(C.shift(k)) - lc
        f[f'v{k}'] = np.log(V.shift(k) / v20)

    # 左半結構:t 突破前 5 日高 / 低點的幅度(> 0 表示 left_top / left_bot 成立)
    f['hi_margin'] = np.log(H / side_extreme(H, half, False, 'max'))
    f['lo_margin'] = np.log(side_extreme(L, half, False, 'min') / L)
    f['chi_margin'] = lc - np.log(side_extreme(C, half, False, 'max'))
    f['clo_margin'] = np.log(side_extreme(C, half, False, 'min')) - lc
    # 收盤離當日高 / 低點幾個 ATR:右半要「再創高」需要走多遠
    f['upper_atr'] = (H - C) / a14
    f['lower_atr'] = (C - L) / a14

    # 背景:趨勢、位階、波動、量能
    r = lc.diff()
    for n in (1, 5, 10, 20, 60):
        f[f'ret{n}'] = lc - lc.shift(n)
    for n in (20, 60):
        f[f'dhi{n}'] = np.log(H.rolling(n, min_periods=n).max()) - lc
        f[f'dlo{n}'] = lc - np.log(L.rolling(n, min_periods=n).min())
        f[f'ma{n}'] = lc - np.log(C.rolling(n, min_periods=n).mean())
    f['ma5'] = lc - np.log(C.rolling(5, min_periods=5).mean())
    f['vol20'] = r.rolling(20, min_periods=20).std()
    f['atr14'] = a14 / C
    f['rsi14'] = _rsi(C)
    f['vr5_20'] = np.log(V.rolling(5, min_periods=5).mean() / v20)

    out = pd.DataFrame(f, index=df.index)
    if mkt is not None:
        mc = np.log(mkt['close'])
        m = pd.DataFrame({
            'm_ret1': mc.diff(), 'm_ret5': mc - mc.shift(5), 'm_ret20': mc - mc.shift(20),
            'm_dhi20': np.log(mkt['high'].rolling(20, min_periods=20).max()) - mc,
            'm_vol20': mc.diff().rolling(20, min_periods=20).std(),
        }, index=mkt.index)
        out = out.join(m.reindex(df.index))
    return out.replace([np.inf, -np.inf], np.nan)


if __name__ == '__main__':
    # 自測:t=10 做出 11 日最高、t=30 最低、t=40 與 t=42 同價雙頂(只算第一次),檢查標籤與因果性
    n = 60
    c = np.full(n, 100.0)
    c[10], c[30], c[40], c[42] = 110.0, 90.0, 112.0, 112.0
    df = pd.DataFrame({'open': c, 'high': c + 1, 'low': c - 1, 'close': c,
                       'volume': np.full(n, 1e6)}, index=pd.date_range('2020-01-01', periods=n, freq='B'))
    for v in ('hl', 'close'):
        lab = label_window(df, v)
        print(f"{v}: 頂={np.where(lab['label'] == TOP)[0].tolist()}  底={np.where(lab['label'] == BOTTOM)[0].tolist()}  "
              f"右側同價的頂底={int(lab['tie_top'].sum())}/{int(lab['tie_bot'].sum())}")
        assert list(np.where(lab['label'] == TOP)[0]) == [10, 40]
        assert list(np.where(lab['label'] == BOTTOM)[0]) == [30]
    # 因果性:改動 t 之後的資料,t 的特徵不得改變
    f1 = causal_features(df)
    df2 = df.copy()
    df2.iloc[41:] *= 1.5
    f2 = causal_features(df2)
    assert np.allclose(f1.iloc[:41].fillna(0), f2.iloc[:41].fillna(0)), '特徵用到未來資料'
    print(f"causal_features: {f1.shape[1]} 欄,改動 t+1 之後資料不影響 ≤ t 的特徵 ✓")
