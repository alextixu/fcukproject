"""
彙整事件驅動實驗 (§十三) B/C/D 各組 3 seeds 的 JSON → markdown 表.
用法: python analysis/summarize_events.py [--glob "EXP-*_ev*"]
"""
import argparse
import glob
import json
import os as _os

import numpy as np

_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default="EXP-*_ev[BCD]-*.json")
    ap.add_argument("--out-dir", default="experiments_paper")
    args = ap.parse_args()
    files = sorted(glob.glob(_os.path.join(_root, args.out_dir, args.glob)))
    recs = [json.load(open(f, encoding="utf-8")) for f in files]
    if not recs:
        print("no records")
        return
    groups = {}
    for r in recs:
        groups.setdefault(r["group"], []).append(r)

    desc = {"B": "事件日 + 隔日標籤", "C": "事件日 + triple-barrier",
            "D": "事件日 + triple-barrier + 方向特徵"}
    print("| 組 | 設定 | seeds | test n | floor | Acc (mean±sd) | Acc−floor | "
          "F1 macro | 預測漲% | P(>floor) 各 seed |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for g in sorted(groups):
        rs = sorted(groups[g], key=lambda r: r["params"]["seed"])
        acc = np.array([r["metrics"]["acc"] * 100 for r in rs])
        gap = np.array([r["gap_vs_floor_pp"] for r in rs])
        f1 = np.array([r["f1_macro"] * 100 for r in rs])
        pp = np.array([r["pred_pos_pct"] for r in rs])
        pab = [r["bootstrap"]["p_above_floor"] for r in rs]
        seeds = ",".join(str(r["params"]["seed"]) for r in rs)
        print(f"| {g} | {desc.get(g, g)} | {seeds} | {rs[0]['n_test_samples']} | "
              f"{rs[0]['floor_pct']:.2f}% | {acc.mean():.2f} ± {acc.std():.2f}% | "
              f"{gap.mean():+.2f}pp | {f1.mean():.2f}% | {pp.mean():.1f}% "
              f"(範圍 {pp.min():.0f}–{pp.max():.0f}) | "
              f"{' / '.join(f'{p:.3f}' for p in pab)} |")
    print()
    print("各 run 明細:")
    print("| exp_id | 組 | seed | Acc | gap | F1m | 預測漲% | Acc CI | gap CI | "
          "底部後 Acc/預測漲% | 頂部後 Acc/預測漲% |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(recs, key=lambda r: (r["group"], r["params"]["seed"])):
        bd = r["by_direction"]
        ab, at = bd.get("after_bottom", {}), bd.get("after_top", {})
        print(f"| {r['exp_id']} | {r['group']} | {r['params']['seed']} | "
              f"{r['metrics']['acc']*100:.2f}% | {r['gap_vs_floor_pp']:+.2f} | "
              f"{r['f1_macro']*100:.2f}% | {r['pred_pos_pct']:.1f}% | "
              f"{r['bootstrap']['acc_ci95']} | {r['bootstrap']['gap_ci95']} | "
              f"{ab.get('acc')}/{ab.get('pred_pos_pct')} | "
              f"{at.get('acc')}/{at.get('pred_pos_pct')} |")


if __name__ == "__main__":
    main()
