"""
事件驅動實驗 (實驗記錄 §十三): B / C / D 三組對照.

  B: --label nextday              事件日取樣 + 隔日標籤 (只換取樣)
  C: --label tb                   事件日取樣 + triple-barrier 標籤
  D: --label tb --dir-feat        C + swing 方向特徵
其餘協定與 run_paper_repro 對齊: Adam 1e-3 / wd 5e-5 / CE / 30 epochs /
val F1 macro 選模 / date batch / paper_exact. 不做回測 (事件策略另議).

附帶: 以事件日為區塊的 bootstrap (5,000 次) 估 Acc 與 Acc-floor 的 CI.

用法:
  python test/run_event_experiment.py --label tb --seed 42 --tag evC-s42
"""
import argparse
import json
import os as _os
import sys as _sys
import time
from datetime import datetime

import numpy as np
import torch
from torch.utils.data import random_split

_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _p in (_root, _os.path.join(_root, "core"),
           _os.path.dirname(_os.path.abspath(__file__))):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from train import fit, DateGroupedBatchSampler
from event_data import build_event_sets


@torch.no_grad()
def predict_by_date(model, ds, device="cpu"):
    """依 date batch 推論, 回傳與 ds 同序的預測."""
    model.eval()
    pred = np.full(len(ds), -1, dtype=np.int64)
    sampler = DateGroupedBatchSampler(ds, shuffle=False)
    for idxs in sampler:
        items = [ds[i] for i in idxs]
        X = torch.stack([it[0] for it in items]).to(device)
        extra = (torch.stack([it[1] for it in items]).to(device)
                 if len(items[0]) == 3 else None)
        pred[idxs] = model(X, extra).argmax(1).cpu().numpy()
    assert (pred >= 0).all()
    return pred


def date_block_bootstrap(ds, pred, n_boot=5000, seed=0):
    y = ds.y
    dates = sorted(ds.date_to_indices)
    n_d = np.array([len(ds.date_to_indices[d]) for d in dates], float)
    c_d = np.array([(pred[ds.date_to_indices[d]] == y[ds.date_to_indices[d]]).sum()
                    for d in dates], float)
    p_d = np.array([(y[ds.date_to_indices[d]] == 1).sum() for d in dates], float)
    rng = np.random.default_rng(seed)
    accs, gaps = [], []
    for _ in range(n_boot):
        b = rng.integers(0, len(dates), len(dates))
        n, c, p = n_d[b].sum(), c_d[b].sum(), p_d[b].sum()
        acc = c / n
        floor = max(p / n, 1 - p / n)
        accs.append(acc)
        gaps.append(acc - floor)
    accs, gaps = np.array(accs), np.array(gaps)
    return {
        "n_blocks": len(dates),
        "acc_ci95": [round(float(np.percentile(accs, 2.5)) * 100, 2),
                     round(float(np.percentile(accs, 97.5)) * 100, 2)],
        "gap_ci95": [round(float(np.percentile(gaps, 2.5)) * 100, 2),
                     round(float(np.percentile(gaps, 97.5)) * 100, 2)],
        "p_above_floor": round(float((gaps > 0).mean()), 4),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="elec_all")
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--train-end", default="2023-12-31")
    ap.add_argument("--end", default="2024-12-31")
    ap.add_argument("--x", type=float, default=0.05, help="ZigZag 確認幅度")
    ap.add_argument("--up", type=float, default=0.05)
    ap.add_argument("--dn", type=float, default=0.05)
    ap.add_argument("--T", type=int, default=20)
    ap.add_argument("--label", default="tb", choices=["nextday", "tb"])
    ap.add_argument("--dir-feat", action="store_true")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--batch-mode", default="date", choices=["paper", "date"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default="experiments_paper")
    ap.add_argument("--md-file", default="實驗記錄_論文對齊.md")
    ap.add_argument("--tag", default="event")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    out_dir = _os.path.join(_root, args.out_dir)
    exp_id = f"EXP-{datetime.now().strftime('%Y%m%d-%H%M%S')}_{args.tag}"
    group = ("B" if args.label == "nextday"
             else ("D" if args.dir_feat else "C"))
    print(f"[EXP] {exp_id}  group={group} label={args.label} "
          f"dir_feat={args.dir_feat} seed={args.seed}")

    t0 = time.time()
    train_full, test_ds, stats, _ = build_event_sets(
        tickers=args.tickers, start=args.start, train_end=args.train_end,
        end=args.end, x=args.x, up=args.up, dn=args.dn, T=args.T,
        label=args.label, dir_feat=args.dir_feat, out_dir=args.out_dir)
    build_time = time.time() - t0

    n_total = len(train_full)
    n_train = int(n_total * 0.8)
    train_ds, val_ds = random_split(
        train_full, [n_train, n_total - n_train],
        generator=torch.Generator().manual_seed(args.seed))

    t0 = time.time()
    model, metrics = fit(
        train_ds, val_ds, test_ds, N=10, g=4, F_dim=9,
        epochs=args.epochs, lr=args.lr, weight_decay=5e-5,
        batch_mode=args.batch_mode, batch_size=128, paper_exact=True,
        extra_dim=2 if args.dir_feat else 0)
    train_time = time.time() - t0

    pred = predict_by_date(model, test_ds)
    test_pos = float((test_ds.y == 1).mean())
    floor = max(test_pos, 1 - test_pos)
    pred_pos = float((pred == 1).mean())
    boot = date_block_bootstrap(test_ds, pred, seed=args.seed)
    f1_macro = (metrics["f1_1"] + metrics["f1_0"]) / 2

    # 依 swing 方向分組的準確率 (方向盲檢查)
    dirs = np.array(test_ds.info["dirs"])
    by_dir = {}
    for d, name in [(1, "after_bottom"), (-1, "after_top")]:
        m = dirs == d
        if m.any():
            by_dir[name] = {
                "n": int(m.sum()),
                "acc": round(float((pred[m] == test_ds.y[m]).mean()) * 100, 2),
                "pos_pct": round(float((test_ds.y[m] == 1).mean()) * 100, 2),
                "pred_pos_pct": round(float((pred[m] == 1).mean()) * 100, 2),
            }

    print(f"\n[RESULT] acc={metrics['acc']*100:.2f}%  floor={floor*100:.2f}%  "
          f"gap={(metrics['acc']-floor)*100:+.2f}pp  "
          f"pred_pos={pred_pos*100:.1f}% (true {test_pos*100:.1f}%)  "
          f"F1m={f1_macro*100:.2f}%")
    print(f"[BOOT] acc CI {boot['acc_ci95']}  gap CI {boot['gap_ci95']}  "
          f"P(>floor)={boot['p_above_floor']}")
    print(f"[BY-DIR] {by_dir}")

    record = {
        "exp_id": exp_id, "group": group,
        "datetime": datetime.now().isoformat(timespec="seconds"),
        "params": vars(args), "event_stats": stats,
        "n_train_samples": n_total, "n_test_samples": len(test_ds),
        "train_pos_pct": stats["train"]["pos_pct"],
        "test_pos_pct": round(test_pos * 100, 2),
        "floor_pct": round(floor * 100, 2),
        "pred_pos_pct": round(pred_pos * 100, 2),
        "metrics": {k: round(float(v), 4) for k, v in metrics.items()},
        "f1_macro": round(f1_macro, 4),
        "gap_vs_floor_pp": round((metrics["acc"] - floor) * 100, 2),
        "bootstrap": boot, "by_direction": by_dir,
        "build_time_s": round(build_time, 1),
        "train_time_s": round(train_time, 1),
    }
    with open(_os.path.join(out_dir, f"{exp_id}.json"), "w",
              encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    torch.save(model.state_dict(),
               _os.path.join(out_dir, f"{exp_id}_model.pt"))
    np.savez_compressed(
        _os.path.join(out_dir, f"{exp_id}_pred.npz"), pred=pred, y=test_ds.y,
        tickers=np.array([m[0] for m in test_ds.meta]),
        dates=np.array([str(m[1])[:10] for m in test_ds.meta]), dirs=dirs)

    lab = {"nextday": "隔日 Eq.(11)",
           "tb": f"triple-barrier +{args.up:.0%}/-{args.dn:.0%}/{args.T}日"}
    block = f"""
### {exp_id}

- **組別**: {group}　**取樣**: 事件驅動 (ZigZag x={args.x:.0%} 確認日)　**標籤**: {lab[args.label]}　**方向特徵**: {'有' if args.dir_feat else '無'}　**seed**: {args.seed}
- **樣本**: train {n_total} (漲 {stats['train']['pos_pct']}%) / test {len(test_ds)} (漲 {record['test_pos_pct']}%, floor {record['floor_pct']}%)；事件日 {stats['test']['n_dates']} 日、平均每日 {stats['test']['per_date_mean']} 檔；test 觸及 {stats['test']['hit']}
- **結果**: Acc **{metrics['acc']*100:.2f}%** (vs floor {record['gap_vs_floor_pp']:+.2f}pp)，F1 macro {f1_macro*100:.2f}%，預測漲比例 {record['pred_pos_pct']}%
- **Block bootstrap** (事件日區塊, 5,000 次): Acc CI {boot['acc_ci95']}，Acc-floor CI {boot['gap_ci95']}，P(>floor)={boot['p_above_floor']}
- **依 swing 方向**: {json.dumps(by_dir, ensure_ascii=False)}
- 建構 {build_time:.0f}s / 訓練 {train_time:.0f}s
"""
    with open(_os.path.join(_root, args.md_file), "a", encoding="utf-8") as f:
        f.write(block)
    print(f"[SAVED] {exp_id}")


if __name__ == "__main__":
    main()
