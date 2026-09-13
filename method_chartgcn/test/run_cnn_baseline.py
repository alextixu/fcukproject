"""
CNN 序列基線 — 模型對照實驗 (Chart GCN vs 1D-CNN)。

控制變因設計: 直接讀取 run_paper_repro 產生的 dscache (meta + 標籤),
與 Chart GCN 使用「完全相同的樣本集合、標籤與 train/val/test 切分」;
唯一差異是輸入表示 —
  Chart GCN: PIP 子圖 (g×N×F = 4×10×9, 經 VG/BFS 選點, 丟失時序方向)
  CNN:       同一 140 日窗的完整 9 指標序列 (window×9, 保留時序方向)
模型仿照序列基準常規: 兩層 Conv1d + BN + MaxPool + GAP + FC。
訓練協定與 GCN 相同: Adam lr 1e-3 / wd 5e-5 / CE 無權重 / 30 epochs /
val F1 macro 選模。

用法:
  python test/run_cnn_baseline.py --tickers elec_all --horizon 1 --seed 42 --tag cnn-h1-elec-s42
  python test/run_cnn_baseline.py --tickers elec_all --horizon 5 --val-split time --seed 42 --tag cnn-h5-elec-s42
"""
import argparse
import json
import time
import os as _os
import sys as _sys
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn

_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _root)
_sys.path.insert(0, _os.path.join(_root, "core"))

from data_loader import fetch_tw_stocks, TICKER_SETS
from dataset import split_by_date
from indicators import compute_indicators
from run_paper_repro import load_ds_cache, PAPER

from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score)


class SeqIndex:
    """把 dscache 樣本 (ticker, 決策日) 對映到指標矩陣的列區間."""

    def __init__(self, ds, price_data, window, feats_by_tk):
        self.window = window
        self.feats = feats_by_tk
        self.tickers = []
        self.pos = []
        self.y = []
        self.dates = []
        pos_maps = {}
        for i, (tk, ddate) in enumerate(ds.meta):
            df = price_data.get(tk)
            if df is None:
                continue
            pm = pos_maps.get(tk)
            if pm is None:
                pm = {d: p for p, d in enumerate(df.index)}
                pos_maps[tk] = pm
            p = pm.get(ddate)
            if p is None or p < window - 1:
                continue
            self.tickers.append(tk)
            self.pos.append(p)
            self.y.append(int(ds.y[i]))
            self.dates.append(str(ddate)[:10])
        self.y = np.asarray(self.y, dtype=np.int64)
        self.pos = np.asarray(self.pos)
        self.date_to_indices = {}
        for i, d in enumerate(self.dates):
            self.date_to_indices.setdefault(d, []).append(i)

    def __len__(self):
        return len(self.y)

    def gather(self, indices, buf=None):
        """把一批樣本的 window×F 序列填進 (B, F, window) 緩衝."""
        F = next(iter(self.feats.values())).shape[1]
        if buf is None or buf.shape[0] != len(indices):
            buf = np.empty((len(indices), F, self.window), dtype=np.float32)
        for j, i in enumerate(indices):
            p = self.pos[i]
            buf[j] = self.feats[self.tickers[i]][p - self.window + 1:p + 1].T
        return buf


class CNN1D(nn.Module):
    """兩層一維卷積 + BN + 池化 (對齊常見序列基準設計)."""

    def __init__(self, F_dim=9, n_classes=2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(F_dim, 32, 5, padding=2), nn.BatchNorm1d(32),
            nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(32, 64, 5, padding=2), nn.BatchNorm1d(64),
            nn.ReLU(), nn.MaxPool1d(2),
            nn.AdaptiveAvgPool1d(1), nn.Flatten(),
            nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, n_classes),
        )

    def forward(self, x):
        return self.net(x)


def evaluate(model, seq, indices, batch_size, device):
    model.eval()
    preds = np.empty(len(indices), dtype=np.int64)
    with torch.no_grad():
        for s in range(0, len(indices), batch_size):
            chunk = indices[s:s + batch_size]
            X = torch.from_numpy(seq.gather(chunk)).to(device)
            preds[s:s + len(chunk)] = model(X).argmax(1).cpu().numpy()
    true = seq.y[indices]
    return {
        'preds': preds,          # [2026-09-05] 供 §19.3 實驗 D 的區塊 bootstrap 使用
        'acc': accuracy_score(true, preds),
        'pre_1': precision_score(true, preds, pos_label=1, zero_division=0),
        'pre_0': precision_score(true, preds, pos_label=0, zero_division=0),
        'rec_1': recall_score(true, preds, pos_label=1, zero_division=0),
        'rec_0': recall_score(true, preds, pos_label=0, zero_division=0),
        'f1_1': f1_score(true, preds, pos_label=1, zero_division=0),
        'f1_0': f1_score(true, preds, pos_label=0, zero_division=0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="elec_all", choices=list(TICKER_SETS))
    ap.add_argument("--n-stocks", type=int, default=0)
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--train-end", default="2023-12-31")
    ap.add_argument("--end", default="2024-12-31")
    ap.add_argument("--window", type=int, default=140)
    ap.add_argument("--m-pips", type=int, default=80)
    ap.add_argument("--N", type=int, default=10)
    ap.add_argument("--g", type=int, default=4)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--horizon", type=int, default=1)
    ap.add_argument("--val-split", default="random", choices=["random", "time"])
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--batch-size", type=int, default=512)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default="experiments_paper")
    ap.add_argument("--dscache-dir", default=None,
                    help="GCN dscache 位置 (預設 experiments_paper/dscache)")
    ap.add_argument("--md-file", default="實驗記錄_論文對齊.md")
    ap.add_argument("--save-preds", action="store_true",
                    help="存下測試集 y/pred/dates 到 analysis/output/preds_<tag>.npz(供區塊 bootstrap)")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    exp_id = "CNN-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    if args.tag:
        exp_id += f"_{args.tag}"
    out_dir = _os.path.join(_root, args.out_dir)
    _os.makedirs(out_dir, exist_ok=True)
    print(f"\n{'='*70}\n {exp_id}\n{'='*70}")
    print(json.dumps(vars(args), indent=2, ensure_ascii=False))

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = "cpu"

    # ── 樣本集合: 直接沿用 GCN 的 dscache (同樣本、同標籤) ──
    base_key = (f"{args.tickers}{args.n_stocks}_{args.start}_{args.train_end}_"
                f"{args.end}_w{args.window}m{args.m_pips}N{args.N}g{args.g}"
                f"s{args.stride}_raw")
    key = base_key + (f"_h{args.horizon}" if args.horizon != 1 else "")
    cache_dir = (args.dscache_dir if args.dscache_dir
                 else _os.path.join(_root, "experiments_paper", "dscache"))
    tr_cache = _os.path.join(cache_dir, f"{key}_train.npz")
    te_cache = _os.path.join(cache_dir, f"{key}_test.npz")
    if not (_os.path.exists(tr_cache) and _os.path.exists(te_cache)):
        raise SystemExit(f"找不到 dscache {key} — 請先跑對應的 run_paper_repro")
    print(f"[CACHE] 沿用 GCN 樣本集合 {key}")
    tr_src = load_ds_cache(tr_cache)
    te_src = load_ds_cache(te_cache)

    # ── 價格與指標 (與 dataset 建構同一套計算, raw 無正規化) ──
    tickers = TICKER_SETS[args.tickers]
    if args.n_stocks > 0:
        tickers = tickers[:args.n_stocks]
    data = fetch_tw_stocks(tickers=tickers, start=args.start, end=args.end)
    train_data, test_data = split_by_date(
        data, args.train_end, warmup_rows=2 * args.window)

    t0 = time.time()
    feats_tr = {tk: compute_indicators(df, n=args.window, stats=(0.0, 1.0))
                    .astype(np.float32)
                for tk, df in train_data.items()}
    feats_te = {tk: compute_indicators(df, n=args.window, stats=(0.0, 1.0))
                    .astype(np.float32)
                for tk, df in test_data.items()}
    train_seq = SeqIndex(tr_src, train_data, args.window, feats_tr)
    test_seq = SeqIndex(te_src, test_data, args.window, feats_te)
    build_time = time.time() - t0
    assert len(train_seq) == len(tr_src) and len(test_seq) == len(te_src), \
        "樣本對映不完整 — 與 GCN 樣本集合不一致"

    n_total = len(train_seq)
    if args.val_split == "time":
        dates = sorted(train_seq.date_to_indices)
        cut = int(len(dates) * 0.8)
        tr_dates = dates[:max(0, cut - args.horizon)]
        val_dates = dates[cut:]
        tr_idx = np.array([i for d in tr_dates
                           for i in train_seq.date_to_indices[d]])
        val_idx = np.array([i for d in val_dates
                            for i in train_seq.date_to_indices[d]])
        print(f"[SPLIT] time: train {len(tr_dates)} 日 / "
              f"embargo {args.horizon} 日 / val {len(val_dates)} 日")
    else:
        perm = torch.randperm(
            n_total, generator=torch.Generator().manual_seed(args.seed)
        ).numpy()
        n_train = int(n_total * 0.8)
        tr_idx, val_idx = perm[:n_train], perm[n_train:]

    train_pos = float((train_seq.y == 1).mean()) * 100
    test_pos = float((test_seq.y == 1).mean()) * 100
    print(f"[STATS] train={n_total} (漲 {train_pos:.1f}%) | "
          f"test={len(test_seq)} (漲 {test_pos:.1f}%)")

    # ── 訓練 (協定同 GCN: Adam/CE/val F1 macro 選模) ──
    model = CNN1D(F_dim=9).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr,
                                 weight_decay=5e-5)
    criterion = nn.CrossEntropyLoss()
    all_test_idx = np.arange(len(test_seq))

    best_val, best_state = 0.0, None
    t0 = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        ep_perm = np.random.permutation(tr_idx)
        total_loss = n_correct = n_seen = 0
        for s in range(0, len(ep_perm), args.batch_size):
            chunk = ep_perm[s:s + args.batch_size]
            X = torch.from_numpy(train_seq.gather(chunk)).to(device)
            yb = torch.from_numpy(train_seq.y[chunk]).to(device)
            optimizer.zero_grad()
            logits = model(X)
            loss = criterion(logits, yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(chunk)
            n_correct += (logits.argmax(1) == yb).sum().item()
            n_seen += len(chunk)
        vm = evaluate(model, train_seq, val_idx, args.batch_size, device)
        val_f1m = (vm['f1_1'] + vm['f1_0']) / 2
        if val_f1m > best_val:
            best_val = val_f1m
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        print(f"Epoch {epoch:02d} | loss={total_loss/n_seen:.4f} "
              f"acc={n_correct/n_seen:.4f} | val_acc={vm['acc']:.4f} "
              f"val_f1m={val_f1m:.4f}")
    train_time = time.time() - t0

    if best_state is not None:
        model.load_state_dict(best_state)
    metrics = evaluate(model, test_seq, all_test_idx, args.batch_size, device)
    test_preds = metrics.pop('preds')      # [2026-09-05] 供 §19.3 實驗 D
    metrics['val_f1_macro'] = best_val
    f1_macro = (metrics['f1_1'] + metrics['f1_0']) / 2

    print(f"\n=== Test Metrics (CNN) ===")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")
    print(f"  f1_macro: {f1_macro:.4f}")

    record = {
        "exp_id": exp_id,
        "model": "cnn1d(32-64, k5, BN, GAP)",
        "datetime": datetime.now().isoformat(timespec="seconds"),
        "params": vars(args),
        "n_stocks": len(data),
        "n_train_samples": n_total,
        "n_test_samples": len(test_seq),
        "train_pos_pct": round(train_pos, 2),
        "test_pos_pct": round(test_pos, 2),
        "metrics": {k: round(float(v), 4) for k, v in metrics.items()},
        "f1_macro": round(f1_macro, 4),
        "paper_ref_sz50": PAPER["SZ-50"],
        "build_time_s": round(build_time, 1),
        "train_time_s": round(train_time, 1),
    }
    # [2026-09-05] 存下測試集預測與模型:原本只回報點估計,
    # 導致 §16.1 的 CNN gap 無法做區塊 bootstrap(§19 稽核第 4 項)。
    if args.save_preds:
        import numpy as _np
        _dates = _np.asarray(test_seq.dates)[all_test_idx].astype(str)
        _pdir = _os.path.join(_root, "analysis", "output")
        _os.makedirs(_pdir, exist_ok=True)
        _np.savez_compressed(_os.path.join(_pdir, f"preds_{args.tag or exp_id}.npz"),
                             y=_np.asarray(test_seq.y)[all_test_idx],
                             pred=test_preds, dates=_dates)
        torch.save(model.state_dict(), _os.path.join(out_dir, f"{exp_id}_model.pt"))
        print(f"  [saved] analysis/output/preds_{args.tag or exp_id}.npz")

    json_path = _os.path.join(out_dir, f"{exp_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    md_path = _os.path.join(_root, args.md_file)
    block = f"""
### {exp_id}

- **模型**: 1D-CNN 序列基線(與 GCN 同樣本/同標籤/同協定,輸入 {args.window}×9 指標序列)
- **時間**: {record['datetime']}　**標的**: {args.tickers} ({len(data)} 檔)　**期間**: {args.start} ~ {args.end} (train_end={args.train_end})
- **參數**: window={args.window}, horizon={args.horizon}, val={args.val_split}, epochs={args.epochs}, lr={args.lr}, batch={args.batch_size}, seed={args.seed}
- **樣本**: train {n_total} (漲 {train_pos:.1f}%) / test {len(test_seq)} (漲 {test_pos:.1f}%)

| 指標 | 本實驗 | 論文 SZ-50 | 差距 |
|---|---|---|---|
| Accuracy | {metrics['acc']*100:.2f}% | 69.26% | {metrics['acc']*100-69.26:+.2f}% |
| Pre_1 / Pre_0 | {metrics['pre_1']*100:.2f}% / {metrics['pre_0']*100:.2f}% | 65.76% / 72.26% | — |
| F1_1 / F1_0 | {metrics['f1_1']*100:.2f}% / {metrics['f1_0']*100:.2f}% | 66.40% / 71.67% | — |
| F1 macro | {f1_macro*100:.2f}% | 69.04% | {f1_macro*100-69.04:+.2f}% |
| Val F1 macro (選模) | {best_val*100:.2f}% | — | — |

- **耗時**: 建構 {build_time:.0f}s / 訓練 {train_time:.0f}s
- **檔案**: `experiments_paper/{exp_id}.json`
"""
    with open(md_path, "a", encoding="utf-8") as f:
        f.write(block)

    print(f"\n[SAVED] {json_path}")
    print(f"{exp_id} 完成. Test Acc = {metrics['acc']*100:.2f}% "
          f"F1m = {f1_macro*100:.2f}%")


if __name__ == "__main__":
    main()
