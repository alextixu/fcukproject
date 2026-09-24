"""把 Bao 2017(WSAEs-LSTM)論文的輸入特徵換進我們的流程:市值前 100 大、標籤 y_oo_h5、7 個測試年 walk-forward(2026-09-22 使用者要求)。

  論文的特徵(以滬深 300 那張表為準,共 19 欄):開高低收量 5 + 技術指標 12 + 總體變數 2(美元指數、銀行同業拆款利率)。
  指標的算法是拿論文自己的資料表反推的(12 個有 10 個完全對上,相關 1.00000):
    MACD = EMA12 − EMA26(只有快慢線差,沒有訊號線)、CCI(14)、ATR = 單日真實波幅 TR(不是平均)、BOLL = 26 日均線(中軌)、
    EMA20、MA10、MA5、MTM6 = C − C[t−6]、MTM12 = C − C[t−12](是「日」不是論文寫的「月」)、ROC = 100 × (C / C[t−12] − 1)。
    SMI、WVAD 兩欄對不上論文的數字(最高相關 0.92、0.11),改用教科書定義:SMI(13, 25, 2)、WVAD = Σ24 (C−O)/(H−L)×V。
  總體變數 2 欄不放:同一天 100 檔的值都一樣,無法在當天排出高低(和原本 mkt_roc_* 的情況相同),而且快取裡沒有台灣的拆款利率。

  兩個版本:
    paper_raw(17 欄):照論文用原始數值(價格水準、成交量、以價格為單位的指標)。論文是單一指數的時間序列,水準值沒問題;
                        換到 100 檔的橫斷面,價格水準等於在告訴模型「這是哪一檔」,列出來當對照。
    paper_rel(16 欄):同樣的指標改成跨股票可比的比例(除以收盤價或均量)。MTM12 改成比例後和 ROC 完全相同,只留一欄。
  五組:raw38(基準,重跑做配對)、paper_raw、paper_rel、ae10_raw(17→10)、ae10_rel(16→10);自編碼器 10 維 = 論文的隱藏層大小。
  前處理 / 自編碼器 / 切分 / XGBoost / 評分:完全沿用 exp_ae_shortlist.py。

輸出 experiments/paper_features_summary.json
"""
import os, sys, json, time
import numpy as np, pandas as pd
from joblib import Parallel, delayed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exp_ae_shortlist as B
from common import paths as P

YEARS, SEEDS = B.YEARS, B.SEEDS


def paper_features(df):
    """df = 單一股票依時間排序的 open / high / low / close / volume。回傳 (原始數值版 17 欄, 比例版 16 欄);回看期不足的列是缺值。"""
    O, H, L, C, V = (df[c].astype(float) for c in ("open", "high", "low", "close", "volume"))
    ema = lambda s, n: s.ewm(span=n, adjust=False).mean()
    warm = lambda s, k: s.where(np.arange(len(s)) >= k - 1)
    macd = warm(ema(C, 12) - ema(C, 26), 26); ema20 = warm(ema(C, 20), 20); ma5, ma10, ma26 = (C.rolling(n).mean() for n in (5, 10, 26))
    tp = (H + L + C) / 3; cci = (tp - tp.rolling(14).mean()) / (0.015 * tp.rolling(14).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True))
    tr = pd.concat([H - L, (H - C.shift()).abs(), (L - C.shift()).abs()], axis=1).max(axis=1).where(C.shift().notna())
    hh, ll = H.rolling(13).max(), L.rolling(13).min(); smi = warm(100 * ema(ema(C - (hh + ll) / 2, 25), 2) / (0.5 * ema(ema(hh - ll, 25), 2)).replace(0, np.nan), 40)
    w = (C - O) / (H - L).replace(0, np.nan) * V; wvad = w.fillna(0).rolling(24).sum(); roc = 100 * (C / C.shift(12) - 1)
    raw = pd.DataFrame({"open": O, "high": H, "low": L, "close": C, "volume": V, "MACD": macd, "CCI": cci, "ATR": tr, "BOLL": ma26, "EMA20": ema20, "MA10": ma10,
                        "MTM6": C - C.shift(6), "MA5": ma5, "MTM12": C - C.shift(12), "ROC": roc, "SMI": smi, "WVAD": wvad})
    rel = pd.DataFrame({"open_rel": O / C - 1, "high_rel": H / C - 1, "low_rel": L / C - 1, "ret_1": C / C.shift() - 1, "volume_rel": V / V.rolling(20).mean().replace(0, np.nan),
                        "MACD_rel": macd / C, "CCI": cci, "ATR_rel": tr / C, "BOLL_rel": ma26 / C - 1, "EMA20_rel": ema20 / C - 1, "MA10_rel": ma10 / C - 1,
                        "MTM6_rel": C / C.shift(6) - 1, "MA5_rel": ma5 / C - 1, "ROC": roc, "SMI": smi, "WVAD_rel": wvad / V.rolling(24).sum().replace(0, np.nan)})
    return raw, rel


def zscore(F):
    g = F.groupby(level="date")
    return ((F - g.transform("mean")) / g.transform("std").replace(0, np.nan)).clip(-5, 5).fillna(0.0).values.astype(np.float32)


def train_ae(Z, hidden, Y, seed):
    """和 exp_ae_shortlist.train_ae 相同的設定(tanh、Adam 1e-3、權重衰減 1e-5、批次 512、最多 200 回合、驗證年還原誤差連 10 回合不降就停),只是輸入矩陣當參數傳。"""
    import torch, torch.nn as nn
    torch.set_num_threads(1); torch.manual_seed(seed); np.random.seed(seed); tr, va, te = B.FOLDS[Y]
    E_, D_ = nn.Sequential(nn.Linear(Z.shape[1], hidden), nn.Tanh()), nn.Sequential(nn.Linear(hidden, Z.shape[1]))
    opt = torch.optim.Adam(list(E_.parameters()) + list(D_.parameters()), 1e-3, weight_decay=1e-5)
    Xt, Xv = torch.from_numpy(Z[tr]), torch.from_numpy(Z[va]); best, state, bad, ep = np.inf, None, 0, 0
    for ep in range(1, 201):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 512):
            xb = Xt[perm[i:i + 512]]; opt.zero_grad(); ((D_(E_(xb)) - xb) ** 2).mean().backward(); opt.step()
        with torch.no_grad(): v = float(((D_(E_(Xv)) - Xv) ** 2).mean())
        if v < best - 1e-5: best, bad, state = v, 0, {k: t.clone() for k, t in E_.state_dict().items()}
        else:
            bad += 1
            if bad >= 10: break
    E_.load_state_dict(state)
    with torch.no_grad(): return tuple(E_(torch.from_numpy(Z[i])).numpy() for i in (tr, va, te)), {"epochs": ep, "val_mse": best}


if __name__ == "__main__":
    T0 = time.time(); px = pd.read_parquet(os.path.join(P.FEATURES, "features_top100_2016-01-01_2026-09-11.parquet"), columns=["open", "high", "low", "close", "volume"])
    parts = [paper_features(d.droplevel("ticker").sort_index()) for _, d in px.groupby(level="ticker", sort=False)]; tks = [t for t, _ in px.groupby(level="ticker", sort=False)]
    FR, FL = (pd.concat({t: p[k] for t, p in zip(tks, parts)}, names=["ticker"]).swaplevel().reindex(B.panel.index) for k in (0, 1))
    print(f"論文特徵:原始數值版 {FR.shape[1]} 欄、比例版 {FL.shape[1]} 欄;樣本 {len(FR)};缺值比例 {FR.isna().mean().mean():.4f} / {FL.isna().mean().mean():.4f}  {time.time()-T0:.0f}s", flush=True)
    RAWX = {"raw38": B.RAW, "paper_raw": FR.values.astype(np.float32), "paper_rel": FL.values.astype(np.float32)}; ZX = {"ae10_raw": zscore(FR), "ae10_rel": zscore(FL)}
    aj = [(a, Y, s) for a in ZX for Y in YEARS for s in SEEDS]; ar = Parallel(n_jobs=8, verbose=5)(delayed(train_ae)(ZX[a], 10, Y, s) for a, Y, s in aj)
    LAT = {k: v[0] for k, v in zip(aj, ar)}; print(f"自編碼器 {len(aj)} 個訓練完 {time.time()-T0:.0f}s", flush=True)

    def feats(arm, Y, s):
        if arm in RAWX: return tuple(RAWX[arm][i] for i in B.FOLDS[Y])
        return LAT[(arm, Y, s)]
    ARMS = ["raw38", "paper_raw", "paper_rel", "ae10_raw", "ae10_rel"]; xj = [(a, Y, s) for a in ARMS for Y in YEARS for s in SEEDS]
    xr = Parallel(n_jobs=8, verbose=5)(delayed(B.fit_xgb)(*feats(a, Y, s), Y, s) for a, Y, s in xj); PR = dict(zip(xj, xr))
    out = {"features": {"paper_raw": list(FR.columns), "paper_rel": list(FL.columns)}, "arms": {}, "diff": {}, "ae_info": {}}; S = {}
    for a in ARMS:
        prob = np.concatenate([np.mean([PR[(a, Y, s)][0] for s in SEEDS], axis=0) for Y in YEARS]); summ, ic, top = B.score(prob)
        summ["trees_median"] = int(np.median([PR[(a, Y, s)][1] for Y in YEARS for s in SEEDS])); out["arms"][a] = summ; S[a] = (ic, top)
        print(f"{a:10s} rank IC {summ['ic_mean']:.4f}(t {summ['ic_t']:.2f}) 準確率 {summ['acc']:.4f} AUC {summ['auc']:.4f} 前 10 檔 {summ['top10_bp']:+.1f} 基點(t {summ['top10_t']:.2f}) 樹 {summ['trees_median']}  各年 {summ['ic_by_year']}", flush=True)
    for a, b in [("paper_raw", "raw38"), ("paper_rel", "raw38"), ("paper_rel", "paper_raw"), ("ae10_raw", "paper_raw"), ("ae10_rel", "paper_rel")]:
        d, dt = (S[a][0] - S[b][0]).dropna(), (S[a][1] - S[b][1]).dropna()
        out["diff"][f"{a} − {b}"] = {"ic_mean": float(d.mean()), "ic_t": B.block_t(d.values), "top10_bp": float(dt.mean()), "top10_t": B.block_t(dt.values)}
        print(f"{a} − {b}: rank IC {d.mean():+.4f}(t {out['diff'][f'{a} − {b}']['ic_t']:.2f})、前 10 檔 {dt.mean():+.1f} 基點(t {out['diff'][f'{a} − {b}']['top10_t']:.2f})", flush=True)
    for a in ZX:
        v = [ar[i][1] for i, j in enumerate(aj) if j[0] == a]; out["ae_info"][a] = {"epochs_median": int(np.median([x["epochs"] for x in v])), "val_mse": float(np.mean([x["val_mse"] for x in v]))}
    out["elapsed_s"] = round(time.time() - T0); json.dump(out, open(os.path.join(P.XGB_EXP, "paper_features_summary.json"), "w"), ensure_ascii=False, indent=1)
    print("[DONE]", out["elapsed_s"], "s", flush=True)
