"""Bao, Yue & Rao (2017) WSAEs-LSTM 的復現:資料、小波去噪、堆疊自編碼器、LSTM / RNN、滾動預測、指標與交易策略。

論文沒寫清楚、由我決定的地方都集中在這個檔案的常數與註解裡,README 有完整清單。
"""
import os, re, json, time, warnings
import numpy as np, pandas as pd, pywt, torch, torch.nn as nn

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(HERE, "data", "RawData.xlsx")
INDEX_SHEETS = {"csi300": ("CSI300 Index Data", "CSI300 Index Future Data"), "nifty50": ("Nifty 50 index Data", "Nifty 50 index future Data"),
                "hangseng": ("HangSeng Index Data", "HangSeng Index Future Data"), "nikkei225": ("Nikkei 225 index Data", "Nikkei 225 index future Data"),
                "sp500": ("S&P500 Index Data", "S&P500 Index Future Data"), "djia": ("DJIA index Data", "DJIA index future data")}


# ───────────────────────── 資料 ─────────────────────────
def load_index(name):
    idx_sheet, fut_sheet = INDEX_SHEETS[name]
    d = pd.read_excel(RAW, sheet_name=idx_sheet)
    dcol = [c for c in d.columns if str(c).strip().lower() in ("ntime", "time")][0]
    if d[dcol].iloc[0] < 19000000:                                       # CSI300 的 Time 欄是 Matlab 序號
        d["date"] = pd.to_datetime(d[dcol] - 719529, unit="D")
    else:
        d["date"] = pd.to_datetime(d[dcol].astype(int).astype(str), format="%Y%m%d")
    drop = [c for c in d.columns if str(c).strip().lower() in ("ntime", "time", "matlab_time")]
    d = d.drop(columns=drop).set_index("date").sort_index().astype(float)
    close = [c for c in d.columns if re.match(r"clos", str(c).strip().lower())][0]
    f = pd.read_excel(RAW, sheet_name=fut_sheet); fd = f.columns[0]
    f["date"] = pd.to_datetime(f[fd].astype(int).astype(str), format="%Y%m%d")
    fut = f.set_index("date")[[c for c in f.columns if re.match(r"clos", str(c).strip().lower())][0]].astype(float).sort_index()
    return d, close, fut


# ───────────────────────── 小波去噪 ─────────────────────────
def _denoise_once(x, level=2):
    """Haar 小波 level 層分解;細節係數用通用門檻(σ = median|d1| / 0.6745,門檻 = σ√(2 ln n))做軟門檻;重建。論文沒寫門檻規則。"""
    c = pywt.wavedec(x, "haar", level=level, mode="periodization" if len(x) % (2 ** level) == 0 else "symmetric")
    sigma = np.median(np.abs(c[-1])) / 0.6745; thr = sigma * np.sqrt(2 * np.log(len(x)))
    c = [c[0]] + [np.sign(v) * np.maximum(np.abs(v) - thr, 0.0) for v in c[1:]]      # 軟門檻(自己寫:pywt.threshold 遇到係數為 0 會算出 0/0 = NaN)
    return pywt.waverec(c, "haar", mode="periodization" if len(x) % (2 ** level) == 0 else "symmetric")[:len(x)]


def denoise(x, times=2, level=2):
    for _ in range(times):                                               # 論文:二層小波「做兩次」
        x = _denoise_once(np.asarray(x, float), level)
    return x


def denoise_frame(df, mode, window=256):
    """mode = full:整段序列(含未來)一次去噪,照論文字面;causal:第 t 天只用 t 以前的 window 天去噪、取最後一點;none:不去噪。"""
    if mode == "none": return df.copy()
    out = df.copy()
    for col in df.columns:
        v = df[col].values.astype(float)
        if mode == "full": out[col] = denoise(v)
        else:
            r = v.copy()
            for t in range(8, len(v)):
                seg = v[max(0, t + 1 - window):t + 1]; seg = seg[len(seg) % 4:]        # 長度取 4 的倍數(二層 Haar)
                r[t] = denoise(seg)[-1]
            out[col] = r
    return out


# ───────────────────────── 模型 ─────────────────────────
class SingleAE(nn.Module):
    def __init__(self, k, n):
        super().__init__(); self.enc, self.dec = nn.Linear(k, n), nn.Linear(n, k)

    def forward(self, x):
        a = torch.sigmoid(self.enc(x)); return torch.sigmoid(self.dec(a)), a                    # 式 (14)(15),f = sigmoid


def train_sae(X, hidden=10, depth=4, epochs=300, lam=1e-4, beta=0.003, rho=0.05, lr=1e-2, seed=0):
    """逐層貪婪訓練 4 個單層自編碼器(5 層 SAE)。損失 = ½·平方還原誤差 + ½λ‖W‖² + β·ΣKL(ρ‖ρ̂)(式 16~19)。λ、β、ρ 論文沒給。β 由「驗證段的整條 SAE 還原誤差」在 {0.3, 0.1, 0.03, 0.01, 0.003, 0}(4 季)上選出 = 0.003(β=0 幾乎相同但就不是稀疏自編碼器了);β≥0.1 會把 10 個單元壓成同一個方向(有效維度 1)。"""
    torch.manual_seed(seed); layers, decs, H = [], [], torch.tensor(X, dtype=torch.float32)
    for _ in range(depth):
        ae = SingleAE(H.shape[1], hidden); opt = torch.optim.Adam(ae.parameters(), lr=lr)
        for _ in range(epochs):
            opt.zero_grad(); rec, a = ae(H); rho_hat = a.mean(0).clamp(1e-6, 1 - 1e-6)
            kl = (rho * torch.log(rho / rho_hat) + (1 - rho) * torch.log((1 - rho) / (1 - rho_hat))).sum()
            loss = 0.5 * ((rec - H) ** 2).sum(1).mean() + 0.5 * lam * (ae.enc.weight.pow(2).sum() + ae.dec.weight.pow(2).sum()) + beta * kl
            loss.backward(); opt.step()
        with torch.no_grad(): H = ae(H)[1]
        layers.append(ae.enc); decs.append(ae.dec)                                               # 論文:還原層丟掉,只留隱藏層(decs 僅供驗證用)
    def encode(Z):
        with torch.no_grad():
            h = torch.tensor(Z, dtype=torch.float32)
            for enc in layers: h = torch.sigmoid(enc(h))
        return h.numpy()
    encode.decoders = decs                     # 逐層的還原層,只用來驗證「整條 SAE 還原得多好」,不參與特徵產生
    return encode


class SeqReg(nn.Module):
    def __init__(self, d, kind="lstm", hidden=16, layers=1):
        super().__init__(); cell = nn.LSTM if kind == "lstm" else nn.RNN
        self.rnn = cell(d, hidden, num_layers=layers, batch_first=True); self.out = nn.Linear(hidden, 1)

    def forward(self, x): return self.out(self.rnn(x)[0][:, -1]).squeeze(-1)


def fit_seq(Xtr, ytr, Xva, yva, kind, hidden, layers, epochs, lr, batch, seed, patience=80, optim="adam", early_stop=True):
    """早停耐心值 80(實測:30 太小,四季平均 MAPE 0.0244;80 → 0.0141;150 / 300 不再改善)。
    optim="sgd"、early_stop=False 是「照原文」那一組用的:固定跑完 epochs 回合、取最後一回合的權重、不看驗證段。"""
    torch.manual_seed(seed); m = SeqReg(Xtr.shape[2], kind, hidden, layers); opt = (torch.optim.Adam if optim == "adam" else torch.optim.SGD)(m.parameters(), lr=lr)
    Xt, yt, Xv, yv = (torch.tensor(a, dtype=torch.float32) for a in (Xtr, ytr, Xva, yva)); best, state, bad = np.inf, None, 0
    for ep in range(epochs):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), batch):
            b = perm[i:i + batch]; opt.zero_grad(); ((m(Xt[b]) - yt[b]) ** 2).mean().backward(); opt.step()
        if not early_stop: continue
        with torch.no_grad(): v = float(((m(Xv) - yv) ** 2).mean())
        if v < best - 1e-7: best, state, bad = v, {k: t.clone() for k, t in m.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= patience: break
    if early_stop: m.load_state_dict(state)
    return m, ep + 1


# ───────────────────────── 指標與策略 ─────────────────────────
def accuracy(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return {"MAPE": float(np.mean(np.abs((y - p) / y))), "R": float(np.corrcoef(y, p)[0, 1]),
            "TheilU": float(np.sqrt(np.mean((y - p) ** 2)) / (np.sqrt(np.mean(y ** 2)) + np.sqrt(np.mean(p ** 2))))}


def strategy_return(pred_next, cur_idx, fut_t, fut_t1, cost=0.0001):
    """式 (31)~(33):預測值 > 目前實際值 → 買期貨;反之 → 放空。回傳該期報酬 %(成本從報酬裡扣)。"""
    buy = pred_next > cur_idx; r = np.where(buy, (fut_t1 - fut_t - (fut_t + fut_t1) * cost) / fut_t, (fut_t - fut_t1 - (fut_t + fut_t1) * cost) / fut_t)
    return float(100 * np.nansum(r)), float(np.mean(buy == (fut_t1 > fut_t)))


# ───────────────────────── 滾動預測 ─────────────────────────
def quarters():
    starts = pd.date_range("2010-10-01", "2016-07-01", freq="QS-OCT")      # 24 個測試季
    return [(s, s + pd.offsets.QuarterEnd(0)) for s in starts]


def run_index(name, models, wavelet, delays=4, epochs=300, hidden=16, layers=1, lr=1e-3, batch=60, seed=0, n_quarters=None, log=print, optim="adam", early_stop=True, q_ids=None):
    raw, close, fut = load_index(name); feats = list(raw.columns)
    den = {w: denoise_frame(raw, w) for w in {wavelet if m.startswith("W") else "none" for m in models}}
    rows, preds = [], []
    for qi, (ts, te) in enumerate(quarters()[:n_quarters]):
        if q_ids is not None and qi not in q_ids: continue                                       # 只跑指定的季(多行程平行用)
        vs, tr_s = ts - pd.DateOffset(months=3), ts - pd.DateOffset(months=27)                   # 訓練 2 年、驗證 3 個月、測試 3 個月
        for mname in models:
            D = den[wavelet if mname.startswith("W") else "none"]; t0 = time.time()
            win = D[(D.index >= tr_s) & (D.index <= te)]; trm = np.asarray(win.index < vs)
            lo, hi = win[trm].min(), win[trm].max(); Z = ((win - lo) / (hi - lo).replace(0, 1)).clip(-0.5, 1.5)   # 縮放參數只用訓練段
            ylo, yhi = raw.loc[win.index[trm], close].min(), raw.loc[win.index[trm], close].max()
            if mname == "naive":
                F = None
            elif mname == "WSAEs-LSTM":
                F = train_sae(Z.values[trm], seed=seed)(Z.clip(0, 1).values)
            else:
                F = Z.values
            ynext = raw[close].shift(-1).reindex(win.index).values                                # 目標:隔天「實際」收盤價(未去噪)
            idx = np.arange(delays - 1, len(win) - 1); dts = win.index[idx]
            seg = lambda a, b: (dts >= a) & (dts <= b)
            mtr, mva, mte = dts < vs, seg(vs, ts - pd.Timedelta(days=1)), seg(ts, te)
            if mname == "naive":
                p = raw[close].reindex(dts[mte]).values; ep = 0
            else:
                X = np.stack([F[i - delays + 1:i + 1] for i in idx]); y = (ynext[idx] - ylo) / (yhi - ylo)
                kind = "rnn" if mname == "RNN" else "lstm"
                m, ep = fit_seq(X[mtr], y[mtr], X[mva], y[mva], kind, hidden, layers, epochs, lr, batch, seed, optim=optim, early_stop=early_stop)
                with torch.no_grad(): p = m(torch.tensor(X[mte], dtype=torch.float32)).numpy() * (yhi - ylo) + ylo
            d_te = dts[mte]; actual = ynext[idx][mte]; cur = raw[close].reindex(d_te).values
            f0 = fut.reindex(d_te).values; f1 = fut.shift(-1).reindex(d_te).values; ok = ~np.isnan(f0) & ~np.isnan(f1)
            ret, hit = strategy_return(p[ok], cur[ok], f0[ok], f1[ok])
            rows.append({"index": name, "model": mname, "wavelet": wavelet if mname.startswith("W") else "none", "quarter": qi + 1, "year": qi // 4 + 1,
                         "n": int(len(p)), **accuracy(actual, p), "ret_pct": ret, "dir_acc": float(np.mean((p > cur) == (actual > cur))), "epochs": ep})
            preds.append(pd.DataFrame({"index": name, "model": mname, "date": d_te, "actual_next": actual, "pred_next": p, "cur": cur}))
            log(f"[{name} Q{qi+1:02d} {mname:11s}] MAPE {rows[-1]['MAPE']:.4f} R {rows[-1]['R']:.3f} 方向 {rows[-1]['dir_acc']:.3f} 報酬 {ret:+.1f}%  {ep} 回合 {time.time()-t0:.0f}s")
    return pd.DataFrame(rows), pd.concat(preds)
