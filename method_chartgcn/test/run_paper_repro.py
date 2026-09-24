"""
論文復現實驗執行器 (Li et al., KBS 2022 Chart GCN).

每次執行會自動:
  1. 訓練 + 測試 + 交易模擬
  2. 結果 JSON 存到 experiments_paper/<EXP_ID>.json
  3. 實驗摘要 append 到 實驗記錄_論文對齊.md (供人工審閱)
  4. 回測淨值圖存到 experiments_paper/<EXP_ID>_backtest.png

用法範例:
  python test/run_paper_repro.py --tag baseline                 # TW50 論文設定
  python test/run_paper_repro.py --tickers tw100 --tag tw100    # 100 檔
  python test/run_paper_repro.py --tickers electronics --tag el # 電子族群
  python test/run_paper_repro.py --batch-mode date --tag dateb  # 同日批次變體
"""
import argparse
import json
import time
import os as _os
import sys as _sys
from datetime import datetime

import numpy as np
import torch
from torch.utils.data import random_split, Subset

_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _root)
_sys.path.insert(0, _os.path.join(_root, "core"))

from data_loader import fetch_tw_stocks, TICKER_SETS
from dataset import ChartGCNDataset, split_by_date
from train import fit
from backtest import run_backtest, plot_backtest

import pandas as pd


class ArrayDataset(torch.utils.data.Dataset):
    """從快取陣列重建、介面相容 ChartGCNDataset 的輕量 Dataset."""

    def __init__(self, X, y, meta):
        self.X = X
        self.y = y
        self.meta = meta
        self.date_to_indices = {}
        for i, (tk, date) in enumerate(meta):
            self.date_to_indices.setdefault(str(date)[:10], []).append(i)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return (torch.from_numpy(self.X[idx]).float(),
                torch.tensor(self.y[idx], dtype=torch.long))


def save_ds_cache(path, ds):
    np.savez_compressed(
        path, X=ds.X, y=ds.y,
        tickers=np.array([m[0] for m in ds.meta]),
        dates=np.array([str(m[1]) for m in ds.meta]),
    )


def load_ds_cache(path):
    z = np.load(path, allow_pickle=False)
    meta = [(str(tk), pd.Timestamp(str(d)))
            for tk, d in zip(z["tickers"], z["dates"])]
    return ArrayDataset(z["X"], z["y"], meta)


def time_split_indices(ds, horizon=1, frac=0.8):
    """
    時間序 train/val 切分 (修正 P4: 重疊滑窗 + 隨機切分的驗證集污染)。
    以「決策日」為單位: 前 frac 的交易日訓練、其餘驗證, 同一天的股票整批在同一邊;
    訓練尾端丟 horizon 個決策日當 embargo, 訓練標籤才不會用到 val 期的價格。
    回傳 (tr_idx, val_idx, n_tr_dates, n_val_dates)。
    """
    dates = sorted(ds.date_to_indices)
    cut = int(len(dates) * frac)
    tr_dates = dates[:max(0, cut - horizon)]
    val_dates = dates[cut:]
    tr_idx = [i for d in tr_dates for i in ds.date_to_indices[d]]
    val_idx = [i for d in val_dates for i in ds.date_to_indices[d]]
    return tr_idx, val_idx, len(tr_dates), len(val_dates)


def derive_horizon_ds(src, price_data, horizon):
    """
    從 horizon=1 快取衍生 horizon>1 資料集: X 特徵不變 (輸入窗相同),
    只重算標籤、並丟棄尾端取不到標籤的樣本。

    price_data 必須是與原始建構相同的 df dict (train 用 train_data 截斷版,
    test 用 test_data), 標籤才不會越過 train/test 邊界 (embargo 由截斷自動達成)。
    樣本保留條件 pos + horizon < len(df) - 1 與 ChartGCNDataset 的
    range(window, len(df) - horizon) 逐位元一致。
    """
    pos_maps = {}
    keep, y_new, meta_new = [], [], []
    for i, (tk, ddate) in enumerate(src.meta):
        df = price_data.get(tk)
        if df is None:
            continue
        pos_map = pos_maps.get(tk)
        if pos_map is None:
            pos_map = {d: p for p, d in enumerate(df.index)}
            pos_maps[tk] = pos_map
        pos = pos_map.get(ddate)
        if pos is None or pos + horizon >= len(df) - 1:
            continue
        close = df['close'].values
        keep.append(i)
        y_new.append(1 if close[pos + horizon] > close[pos] else 0)
        meta_new.append((tk, ddate))
    return ArrayDataset(src.X[keep], np.asarray(y_new, dtype=src.y.dtype),
                        meta_new)

def relabel_cs_median(src, price_data, horizon=1, min_stocks=10):
    """
    標籤改成橫斷面相對強弱 (v1.6, 疑慮 S2): 同一個決策日裡,
    這檔股票未來 horizon 日的報酬是否「高於當天所有股票的中位數」。
    X 特徵不變, 只重算標籤; 當天股票數不到 min_stocks 的日子整天丟掉。
    大盤當天漲或跌會被中位數扣掉, 類別天生接近 50/50, 模型沒辦法靠全猜一邊拿分數。
    price_data 的要求同 derive_horizon_ds (train 用截斷版, 標籤不越過 train/test 邊界)。
    """
    pos_maps, closes = {}, {}
    rows = []                      # (原索引, 日期字串, 未來報酬)
    for i, (tk, ddate) in enumerate(src.meta):
        df = price_data.get(tk)
        if df is None:
            continue
        if tk not in pos_maps:
            pos_maps[tk] = {d: p for p, d in enumerate(df.index)}
            closes[tk] = df['close'].values
        pos = pos_maps[tk].get(ddate)
        if pos is None or pos + horizon >= len(closes[tk]):
            continue
        c = closes[tk]
        rows.append((i, str(ddate)[:10], c[pos + horizon] / c[pos] - 1.0))
    by_date = {}
    for i, d, r in rows:
        by_date.setdefault(d, []).append(r)
    med = {d: float(np.median(v)) for d, v in by_date.items()
           if len(v) >= min_stocks}
    keep = [(i, 1 if r > med[d] else 0) for i, d, r in rows if d in med]
    idx = [k[0] for k in keep]
    return ArrayDataset(src.X[idx],
                        np.asarray([k[1] for k in keep], dtype=src.y.dtype),
                        [src.meta[i] for i in idx])


# 論文 Table 3 結果 (供對照)
PAPER = {
    "SZ-50":   {"acc": 69.26, "pre_1": 65.76, "pre_0": 72.26, "f1_1": 66.40, "f1_0": 71.67},
    "CSI-300": {"acc": 68.62, "pre_1": 64.87, "pre_0": 71.91, "f1_1": 65.93, "f1_0": 70.91},
}

# TICKER_SETS 已移至 data_loader (此處 re-export 供 grid_search_paper /
# run_xgb_baseline 沿用既有 import 路徑)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="tw50", choices=list(TICKER_SETS))
    ap.add_argument("--n-stocks", type=int, default=0, help="0 = 全部")
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--train-end", default="2023-12-31")
    ap.add_argument("--end", default="2024-12-31")
    ap.add_argument("--window", type=int, default=140)
    ap.add_argument("--m-pips", type=int, default=60)
    ap.add_argument("--N", type=int, default=15)
    ap.add_argument("--g", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--horizon", type=int, default=1,
                    help="標籤視野 (交易日): close[t+h] vs close[t]; 1=論文 Eq.(11)")
    ap.add_argument("--indicator-n", type=int, default=None,
                    help="9 個技術指標的週期 (天)。不給 = 跟著 --window (論文設定); "
                         "v1.3 起可單獨設, 例如 5 = 一週")
    ap.add_argument("--label", default="abs", choices=["abs", "cs"],
                    help="標籤: abs=單檔未來漲跌 (論文); cs=未來報酬是否高於當天所有股票的中位數 (v1.6)")
    ap.add_argument("--pip-mode", default="minmax", choices=["raw", "minmax", "vd"],
                    help="關鍵點距離算法: minmax=視窗內價格先縮放到和時間軸同長度 (v1.5 起預設); "
                         "raw=論文原式(原始股價, 挑點受股價高低影響, 僅供對照); vd=垂直距離")
    ap.add_argument("--val-split", default="time", choices=["random", "time"],
                    help="train/val 切分: time=前 80%% 交易日訓練+embargo+後 20%% 驗證 "
                         "(v1.1 起預設); random=論文 4.3 隨機 80/20 (驗證集會被污染, 僅供對照)")
    ap.add_argument("--batch-mode", default="paper", choices=["paper", "date"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--no-backtest", action="store_true")
    ap.add_argument("--raw-features", action="store_true",
                    help="不做 z-score, 用原始指標值 (論文未提及正規化)")
    ap.add_argument("--no-attention", action="store_true",
                    help="論文消融變體 Chart GCN-2 (無 self-attention)")
    ap.add_argument("--out-dir", default="experiments_paper",
                    help="結果輸出目錄 (相對專案根)")
    ap.add_argument("--md-file", default="實驗記錄_論文對齊.md",
                    help="實驗記錄 markdown (相對專案根)")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    exp_id = "EXP-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    if args.tag:
        exp_id += f"_{args.tag}"
    out_dir = _os.path.join(_root, args.out_dir)
    _os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'='*70}\n {exp_id}\n{'='*70}")
    print(json.dumps(vars(args), indent=2, ensure_ascii=False))

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    # ── 1. 資料 ──────────────────────────────────────────────
    tickers = TICKER_SETS[args.tickers]
    if args.n_stocks > 0:
        tickers = tickers[:args.n_stocks]
    t0 = time.time()
    data = fetch_tw_stocks(tickers=tickers, start=args.start, end=args.end)
    print(f"\n[DATA] {len(data)} 檔股票 ({time.time()-t0:.0f}s)")

    train_data, test_data = split_by_date(
        data, args.train_end, warmup_rows=2 * args.window)

    # ── 2. Dataset (訓練期統計量 → 測試集, 無前視) ────────────
    t0 = time.time()
    cache_dir = _os.path.join(out_dir, "dscache")
    _os.makedirs(cache_dir, exist_ok=True)
    base_key = (f"{args.tickers}{args.n_stocks}_{args.start}_{args.train_end}_"
                f"{args.end}_w{args.window}m{args.m_pips}N{args.N}g{args.g}"
                f"s{args.stride}{'_raw' if args.raw_features else ''}"
                f"{f'_in{args.indicator_n}' if args.indicator_n else ''}"
                f"{f'_pip{args.pip_mode}' if args.pip_mode != 'raw' else ''}")
    # horizon=1 沿用舊 key (相容既有快取); h>1 加後綴
    key = base_key + (f"_h{args.horizon}" if args.horizon != 1 else "")
    tr_cache = _os.path.join(cache_dir, f"{key}_train.npz")
    te_cache = _os.path.join(cache_dir, f"{key}_test.npz")
    tr_h1 = _os.path.join(cache_dir, f"{base_key}_train.npz")
    te_h1 = _os.path.join(cache_dir, f"{base_key}_test.npz")

    if _os.path.exists(tr_cache) and _os.path.exists(te_cache):
        print(f"[BUILD] 使用快取 {key}")
        train_full = load_ds_cache(tr_cache)
        test_ds = load_ds_cache(te_cache)
    elif (args.horizon != 1
          and _os.path.exists(tr_h1) and _os.path.exists(te_h1)):
        # X 特徵與 h=1 完全相同 → 直接重算標籤, 免重建 (elec_all 省 ~50 分鐘)
        print(f"[BUILD] 由 horizon=1 快取衍生 h={args.horizon} ...")
        train_full = derive_horizon_ds(
            load_ds_cache(tr_h1), train_data, args.horizon)
        test_ds = derive_horizon_ds(
            load_ds_cache(te_h1), test_data, args.horizon)
        save_ds_cache(tr_cache, train_full)
        save_ds_cache(te_cache, test_ds)
    else:
        raw_stats = ({tk: (0.0, 1.0) for tk in data}
                     if args.raw_features else None)
        print("[BUILD] train dataset ...")
        train_full = ChartGCNDataset(
            train_data, window=args.window, m_pips=args.m_pips,
            N=args.N, g=args.g, stride=args.stride, n_workers=args.workers,
            norm_stats=raw_stats, horizon=args.horizon,
            indicator_n=args.indicator_n, pip_mode=args.pip_mode,
        )
        print("[BUILD] test dataset (沿用訓練期 norm_stats) ...")
        test_ds = ChartGCNDataset(
            test_data, window=args.window, m_pips=args.m_pips,
            N=args.N, g=args.g, stride=1, n_workers=args.workers,
            norm_stats=(raw_stats if args.raw_features
                        else train_full.norm_stats),
            min_date=args.train_end, horizon=args.horizon,
            indicator_n=args.indicator_n, pip_mode=args.pip_mode,
        )
        save_ds_cache(tr_cache, train_full)
        save_ds_cache(te_cache, test_ds)
    if args.label == "cs":
        # 特徵和快取共用, 只在這裡換標籤
        n0, m0 = len(train_full), len(test_ds)
        train_full = relabel_cs_median(train_full, train_data, args.horizon)
        test_ds = relabel_cs_median(test_ds, test_data, args.horizon)
        print(f"[LABEL] 橫斷面中位數標籤: train {n0} → {len(train_full)} "
              f"(正例 {train_full.y.mean()*100:.1f}%), test {m0} → {len(test_ds)} "
              f"(正例 {test_ds.y.mean()*100:.1f}%)")
    build_time = time.time() - t0

    n_total = len(train_full)
    if args.val_split == "time":
        # 時間切分: 前 80% 交易日訓練 + embargo + 後 20% 驗證 (見 time_split_indices)
        tr_idx, val_idx, n_tr_d, n_val_d = time_split_indices(
            train_full, horizon=args.horizon)
        train_ds = Subset(train_full, tr_idx)
        val_ds = Subset(train_full, val_idx)
        print(f"[SPLIT] time: train {n_tr_d} 日 / "
              f"embargo {args.horizon} 日 / val {n_val_d} 日")
    else:
        # 論文 4.3: 隨機 80/20 切 train/val
        n_train = int(n_total * 0.8)
        train_ds, val_ds = random_split(
            train_full, [n_train, n_total - n_train],
            generator=torch.Generator().manual_seed(args.seed),
        )

    train_pos = float((train_full.y == 1).mean()) * 100
    test_pos = float((test_ds.y == 1).mean()) * 100
    print(f"[STATS] train={n_total} (漲 {train_pos:.1f}%) | "
          f"test={len(test_ds)} (漲 {test_pos:.1f}%)")

    # ── 3. 訓練 ──────────────────────────────────────────────
    t0 = time.time()
    model, metrics = fit(
        train_ds, val_ds, test_ds,
        N=args.N, g=args.g, F_dim=9,
        epochs=args.epochs, lr=args.lr, weight_decay=5e-5,
        batch_mode=args.batch_mode, batch_size=128,
        paper_exact=True,
        use_attention=not args.no_attention,
    )
    train_time = time.time() - t0

    f1_macro = (metrics["f1_1"] + metrics["f1_0"]) / 2

    # ── 4. 對照論文 ──────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f" {'指標':<10} {'本實驗':>10} {'論文 SZ-50':>12} {'差距':>10}")
    print(f"{'─'*60}")
    for k, pk in [("acc", "acc"), ("pre_1", "pre_1"), ("pre_0", "pre_0"),
                  ("f1_1", "f1_1"), ("f1_0", "f1_0")]:
        ours = metrics[k] * 100
        ref = PAPER["SZ-50"][pk]
        print(f" {k:<10} {ours:>9.2f}% {ref:>11.2f}% {ours-ref:>+9.2f}%")

    # ── 5. 交易模擬 ──────────────────────────────────────────
    bt_summary = None
    if not args.no_backtest:
        bt = run_backtest(model, test_ds, test_data,
                          indicator_n=args.window,
                          batch_mode=args.batch_mode,
                          )
        png_path = _os.path.join(out_dir, f"{exp_id}_backtest.png")
        plot_backtest(bt, save_path=png_path)
        bt_summary = {
            "strategy_nv": bt["avg_final_nv"],
            "benchmark_nv": bt["benchmark_final"],
            "excess_pct": (bt["avg_final_nv"] - bt["benchmark_final"]) * 100,
        }

    # ── 6. 記錄 ──────────────────────────────────────────────
    record = {
        "exp_id": exp_id,
        "datetime": datetime.now().isoformat(timespec="seconds"),
        "params": vars(args),
        "n_stocks": len(data),
        "n_train_samples": n_total,
        "n_test_samples": len(test_ds),
        "train_pos_pct": round(train_pos, 2),
        "test_pos_pct": round(test_pos, 2),
        "metrics": {k: round(float(v), 4) for k, v in metrics.items()},
        "f1_macro": round(f1_macro, 4),
        "paper_ref_sz50": PAPER["SZ-50"],
        "acc_gap_vs_paper": round(metrics["acc"] * 100 - PAPER["SZ-50"]["acc"], 2),
        "backtest": bt_summary,
        "build_time_s": round(build_time, 1),
        "train_time_s": round(train_time, 1),
    }
    json_path = _os.path.join(out_dir, f"{exp_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    model_path = _os.path.join(out_dir, f"{exp_id}_model.pt")
    torch.save(model.state_dict(), model_path)

    # append 到實驗記錄 markdown
    md_path = _os.path.join(_root, args.md_file)
    test_year = args.end[:4]
    bt_txt = (f"策略 {bt_summary['strategy_nv']:.4f} vs 大盤 "
              f"{bt_summary['benchmark_nv']:.4f} "
              f"(超額 {bt_summary['excess_pct']:+.2f}%)"
              if bt_summary else "未執行")
    block = f"""
### {exp_id}

- **時間**: {record['datetime']}　**標的**: {args.tickers} ({len(data)} 檔)　**期間**: {args.start} ~ {args.end} (train_end={args.train_end})
- **參數**: window={args.window}, m={args.m_pips}, N={args.N}, g={args.g}, stride={args.stride}, epochs={args.epochs}, lr={args.lr}, batch={args.batch_mode}, seed={args.seed}, horizon={args.horizon}, val={args.val_split}, indicator_n={args.indicator_n or args.window}, pip={args.pip_mode}, label={args.label}
- **樣本**: train {n_total} (漲 {train_pos:.1f}%) / test {len(test_ds)} (漲 {test_pos:.1f}%)

| 指標 | 本實驗 | 論文 SZ-50 | 差距 |
|---|---|---|---|
| Accuracy | {metrics['acc']*100:.2f}% | 69.26% | {metrics['acc']*100-69.26:+.2f}% |
| Pre_1 / Pre_0 | {metrics['pre_1']*100:.2f}% / {metrics['pre_0']*100:.2f}% | 65.76% / 72.26% | — |
| F1_1 / F1_0 | {metrics['f1_1']*100:.2f}% / {metrics['f1_0']*100:.2f}% | 66.40% / 71.67% | — |
| F1 macro | {f1_macro*100:.2f}% | 69.04% | {f1_macro*100-69.04:+.2f}% |
| Val F1 macro (選模) | {metrics.get('val_f1_macro', 0)*100:.2f}% | — | — |

- **回測 ({test_year})**: {bt_txt}
- **耗時**: 建構 {build_time:.0f}s / 訓練 {train_time:.0f}s
- **檔案**: `experiments_paper/{exp_id}.json`
"""
    with open(md_path, "a", encoding="utf-8") as f:
        f.write(block)

    print(f"\n[SAVED] {json_path}")
    print(f"[SAVED] {md_path} (已 append 實驗摘要)")
    print(f"\n{exp_id} 完成. Test Acc = {metrics['acc']*100:.2f}% "
          f"(論文 SZ-50: 69.26%)")


if __name__ == "__main__":
    main()
