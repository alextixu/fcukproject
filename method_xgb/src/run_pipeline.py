"""一鍵管線:特徵 → 各特徵集訓練 → (full) 重要性 → 剔除 → 重訓 → 同協定評估。

用法:
  python src/run_pipeline.py --tag e1-tw50-h1
  python src/run_pipeline.py --pool tw200 --horizon 5 --label cs --tag e5-tw200-h5-cs
  python src/run_pipeline.py --feature-sets full --prune none --seeds 42 --tag smoke
"""
import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

import argparse
import json
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(ROOT))
from common import paths as P

from data import load_pool, PAPER9_NAMES
from features import build_panel, CLASSIC_SETS
from labels import add_labels, label_col, HORIZONS
from split import time_split, filter_features, apply_deadzone
from train_xgb import fit_xgb, predict_p
from importance import (gain_importance, permutation_importance, shap_importance,
                        composite_rank, dedupe_correlated)
from prune import apply_rule, RULES
from evaluate import clf_metrics, clf_metrics_csmed, decile_eval
import plots

EXP = os.path.join(ROOT, "experiments")
FIGS = os.path.join(ROOT, "figs")
CFG = os.path.join(ROOT, "config")
os.makedirs(EXP, exist_ok=True)
os.makedirs(FIGS, exist_ok=True)


def _needed_columns(cfg, fam):
    """lowmem 模式只載入這次會用到的欄位。"""
    need = ["close"] + [f"{p}_h{h}" for h in HORIZONS for p in ("r", "y_bin", "y_cs")]
    for name in cfg["feature_sets"]:
        need += feature_list(name, fam)
    return list(dict.fromkeys(need))


def get_panel(cfg, rebuild=False):
    key = f"{cfg['pool']}_{cfg['start']}_{cfg['end']}" + ("_chip" if cfg.get("chip") else "")
    fp = os.path.join(P.FEATURES, f"features_{key}.parquet")
    lm_prefix = os.path.join(P.FEATURES, f"features_{key}_lowmem")
    cat_key_fp = os.path.join(CFG, f"feature_catalog_{key}.csv")
    cat_fp = cat_key_fp if os.path.exists(cat_key_fp) else os.path.join(CFG, f"feature_catalog_{cfg['pool']}.csv")
    from lowmem import build_lowmem, load_lowmem
    if os.path.exists(lm_prefix + "_cols.json") and not rebuild:
        fam = json.load(open(lm_prefix + "_cols.json", encoding="utf-8"))["family"]
        cols = _needed_columns(cfg, fam)
        panel, fam = load_lowmem(lm_prefix, cols, cfg["train_end"], cfg.get("stride", 1))
        cfg["_strided"] = True
        print(f"[FEAT] 讀 lowmem 快取 {lm_prefix} → 只載入 {len(cols)} 欄, {panel.shape}")
        return panel, fam
    if os.path.exists(fp) and os.path.exists(cat_fp) and not rebuild:
        print(f"[FEAT] 讀快取 {fp}")
        panel = pd.read_parquet(fp)
        fam = pd.read_csv(cat_fp, index_col=0)["family"].to_dict()
        fam = {k: v for k, v in fam.items() if k in panel.columns}
        return panel, fam
    t0 = time.time()
    data = load_pool(cfg["pool"], cfg["start"], cfg["end"])
    print(f"[DATA] {cfg['pool']}: {len(data)} 檔")
    chip = None
    if cfg.get("chip"):
        from chip_data import load_chip
        chip = load_chip(list(data.keys()), cfg["start"], cfg["end"])
        n3 = sum(len(v) == 3 for v in chip.values())
        print(f"[CHIP] {len(chip)}/{len(data)} 檔有籌碼資料(三種齊全 {n3} 檔)")
    if cfg.get("lowmem") or sum(len(d) for d in data.values()) > 600_000:
        fam = build_lowmem(data, lm_prefix, chip_data=chip)
        pd.DataFrame({"family": fam}).rename_axis("name").to_csv(cat_key_fp)
        del data, chip
        cols = _needed_columns(cfg, fam)
        panel, fam = load_lowmem(lm_prefix, cols, cfg["train_end"], cfg.get("stride", 1))
        cfg["_strided"] = True
        print(f"[FEAT] lowmem 建構完成 {time.time() - t0:.0f}s → {lm_prefix}.dat;載入 {len(cols)} 欄 {panel.shape}")
        return panel, fam
    panel, fam = build_panel(data, chip_data=chip)
    panel = add_labels(panel)
    feat_cols = list(fam.keys())
    panel.to_parquet(fp)
    pd.DataFrame({"family": fam}).rename_axis("name").to_csv(cat_key_fp)
    print(f"[FEAT] {panel.shape}, 特徵 {len(feat_cols)} 欄, {time.time() - t0:.0f}s → {fp}")
    return panel, fam


def feature_list(name, fam):
    if name == "full":
        return [k for k, v in fam.items() if v != "paper9"]
    if name == "paper9":
        return list(PAPER9_NAMES)
    if name in CLASSIC_SETS:
        return list(CLASSIC_SETS[name])
    if name.startswith("family:"):
        f = name.split(":", 1)[1]
        return [k for k, v in fam.items() if v == f]
    if name.startswith("nofamily:"):
        f = name.split(":", 1)[1]
        return [k for k, v in fam.items() if v not in ("paper9", f)]
    if name.startswith("top:"):
        _, tag, k = name.split(":")
        imp = pd.read_csv(os.path.join(EXP, f"{tag}_importance.csv"), index_col=0)
        return [f for f in imp.sort_values("rank_mean").index[:int(k)] if f in fam]
    if name.startswith("frozen:"):
        _, tag, sname = name.split(":")
        feats = json.load(open(os.path.join(EXP, f"{tag}.json"), encoding="utf-8"))["results"][sname]["features"]
        return [f for f in feats if f in fam]
    raise ValueError(name)


def run_set(name, feats, tr, va, te, ycol, cfg, seeds, null_reps, want_importance=False):
    Xtr, ytr = tr[feats], tr[ycol].values.astype(int)
    Xva, yva = va[feats], va[ycol].values.astype(int)
    Xte, yte = te[feats], te[ycol].values.astype(int)
    per_seed, probs_te, imp_tables = [], [], {"gain": [], "perm": [], "shap": []}
    models = []
    for seed in seeds:
        t0 = time.time()
        m = fit_xgb(Xtr, ytr, Xva, yva, seed, cfg["xgb"])
        p_va, p_te = predict_p(m, Xva), predict_p(m, Xte)
        r = {"seed": seed, "best_iter": int(m.best_iteration),
             "val": clf_metrics(yva, p_va), "test": clf_metrics(yte, p_te),
             "test_csmed": clf_metrics_csmed(yte, p_te, te.index.get_level_values("date")) if ycol.startswith("y_cs") else None,
             "decile": decile_eval(te, p_te, HORIZONS, null_reps=0)}
        per_seed.append(r)
        probs_te.append(p_te)
        models.append(m)
        if want_importance:
            imp_tables["gain"].append(gain_importance(m, feats))
            perm, base = permutation_importance(m, Xva, yva, feats, seed=seed)
            imp_tables["perm"].append(perm)
            sh = shap_importance(m, Xva, feats, seed=seed)
            if sh is not None:
                imp_tables["shap"].append(sh)
        dh = r['decile'].get(f"h{cfg['horizon']}") or {}
        csm = (f"| 日中位 acc={r['test_csmed']['acc']*100:.2f}% f1m={r['test_csmed']['f1_macro']*100:.2f}% "
               if r.get('test_csmed') else "")
        print(f"  [{name} s{seed}] iters={m.best_iteration} "
              f"test acc={r['test']['acc']*100:.2f}% f1m={r['test']['f1_macro']*100:.2f}% {csm}"
              f"auc={r['test']['auc']:.4f} | h{cfg['horizon']} H-L "
              f"{dh.get('hl_ann_ret_pct', float('nan')):+.1f}% "
              f"ρ={dh.get('monotonic_spearman', float('nan')):+.2f} "
              f"({time.time() - t0:.0f}s)")
    p_ens = np.mean(probs_te, axis=0)
    ens = {"test": clf_metrics(yte, p_ens),
           "test_csmed": clf_metrics_csmed(yte, p_ens, te.index.get_level_values("date")) if ycol.startswith("y_cs") else None,
           "decile": decile_eval(te, p_ens, HORIZONS, null_reps=null_reps, null_h=cfg["horizon"])}
    out = {"features": feats, "n_feat": len(feats), "per_seed": per_seed, "ensemble": ens,
           "summary": summarize(per_seed, cfg["horizon"]),
           "_p_ens": p_ens}
    imp = None
    if want_importance:
        imp = pd.DataFrame(index=feats)
        imp["gain_mean"] = pd.concat(imp_tables["gain"], axis=1).mean(axis=1)
        imp["perm_mean"] = pd.concat(imp_tables["perm"], axis=1).mean(axis=1)
        tables = imp_tables["gain"] + imp_tables["perm"]
        if imp_tables["shap"]:
            imp["shap_mean"] = pd.concat(imp_tables["shap"], axis=1).mean(axis=1)
            tables += imp_tables["shap"]
        imp = imp.join(composite_rank(tables))
    return out, imp


def summarize(per_seed, h):
    def ms(vals):
        return {"mean": float(np.mean(vals)), "std": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0}
    s = {}
    for k in ("acc", "f1_macro", "auc", "prob_std", "pred_up_ratio",
              "acc_cov5", "acc_cov10", "acc_cov20", "acc_cov50"):
        s[k] = ms([r["test"][k] for r in per_seed])
    for hh in HORIZONS:
        for k in ("hl_ann_ret_pct", "hl_sharpe", "hl_t_stat", "monotonic_spearman",
                  "hl_net_ann_ret_pct", "hl_net_t_stat", "turnover_mean", "cost_ann_pct"):
            vals = [r["decile"][f"h{hh}"][k] for r in per_seed
                    if r["decile"][f"h{hh}"] and k in r["decile"][f"h{hh}"]]
            if vals:
                s[f"h{hh}_{k}"] = ms(vals)
    return s


def md_table(results, cfg):
    h = cfg["horizon"]
    lines = ["| 特徵集 | 欄數 | Acc | F1 macro | AUC | prob std | "
             f"H-L h{h} (年化%) | H-L t | 單調 ρ | 週轉 | 成本年化% | 淨 H-L | 淨 t | "
             "H-L h5 | H-L h20 | 零分佈百分位(H-L / ρ) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, r in results.items():
        s, e = r["summary"], r["ensemble"]["decile"][f"h{h}"]
        pct = f"{e.get('hl_null_pctile', '—')} / {e.get('rho_null_pctile', '—')}" if e else "—"
        f = lambda k, m=1, d=2: f"{s[k]['mean']*m:.{d}f} ± {s[k]['std']*m:.{d}f}" if k in s else "—"
        lines.append(f"| {name} | {r['n_feat']} | {f('acc',100)}% | {f('f1_macro',100)}% | "
                     f"{f('auc',1,4)} | {f('prob_std',1,4)} | {f(f'h{h}_hl_ann_ret_pct',1,1)} | "
                     f"{f(f'h{h}_hl_t_stat',1,2)} | {f(f'h{h}_monotonic_spearman',1,2)} | "
                     f"{f(f'h{h}_turnover_mean',1,2)} | {f(f'h{h}_cost_ann_pct',1,0)} | "
                     f"{f(f'h{h}_hl_net_ann_ret_pct',1,1)} | {f(f'h{h}_hl_net_t_stat',1,2)} | "
                     f"{f('h5_hl_ann_ret_pct',1,1)} | {f('h20_hl_ann_ret_pct',1,1)} | {pct} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(CFG, "default.json"))
    ap.add_argument("--pool"); ap.add_argument("--horizon", type=int)
    ap.add_argument("--start", help="資料起日(縮短訓練期用;快取 key 會不同)")
    ap.add_argument("--label", choices=["bin", "cs"])
    ap.add_argument("--seeds"); ap.add_argument("--feature-sets")
    ap.add_argument("--prune", help="逗號分隔規則或 none / all")
    ap.add_argument("--null-reps", type=int)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--chip", action="store_true", help="加入 FinMind 籌碼族群(需先跑 src/chip_data.py)")
    ap.add_argument("--deadzone", type=float, default=0.0, help="|r_h| < deadzone 的樣本全部剔除(漲跌標籤用)")
    ap.add_argument("--xgb-json", help="覆蓋 XGB 超參數的 JSON 檔(例如 tune_xgb.py 的輸出)")
    ap.add_argument("--lowmem", action="store_true", help="強制用 memmap 低記憶體路徑(tw500 自動啟用)")
    ap.add_argument("--stride", type=int, default=1, help="訓練列只取每 stride 個交易日(省記憶體;val/test 不變)")
    ap.add_argument("--sample-filter", default="", help="訓練前先篩「有量」樣本(train/val/test 同規則):liq50 = 近 20 日均成交金額在同池前 50%%;"
                    "spike12 = 當日量 ≥ 1.2 × 20 日均量;可用 + 串接,如 liq50+spike12")
    ap.add_argument("--lag", type=int, default=0,
                    help="洩漏診斷:所有特徵在各股內延後 lag 個交易日(用 t-lag 的特徵預測 t→t+h)")
    a = ap.parse_args()

    cfg = json.load(open(a.config, encoding="utf-8"))
    for k in ("pool", "horizon", "label", "null_reps", "start"):
        v = getattr(a, k)
        if v is not None:
            cfg[k] = v
    if a.chip:
        cfg["chip"] = True
    if a.lowmem:
        cfg["lowmem"] = True
    if a.deadzone > 0:
        cfg["deadzone"] = a.deadzone
    if a.xgb_json:
        cfg["xgb"].update(json.load(open(a.xgb_json, encoding="utf-8")))
        cfg["xgb_json"] = a.xgb_json
    if a.stride > 1:
        cfg["stride"] = a.stride
    if a.seeds:
        cfg["seeds"] = [int(s) for s in a.seeds.split(",")]
    if a.feature_sets:
        cfg["feature_sets"] = a.feature_sets.split(",")
    if a.prune:
        cfg["prune"] = [] if a.prune == "none" else (RULES if a.prune == "all" else a.prune.split(","))

    t_all = time.time()
    panel, fam = get_panel(cfg, rebuild=a.rebuild)
    if a.lag:
        fc = list(fam.keys())
        panel[fc] = panel.groupby(level="ticker")[fc].shift(a.lag)
        cfg["lag"] = a.lag
        print(f"[LAG] 特徵延後 {a.lag} 日")
    ycol = label_col(cfg["label"], cfg["horizon"])
    if a.sample_filter:
        cfg["sample_filter"] = a.sample_filter
        keep = pd.Series(True, index=panel.index)
        for rule in a.sample_filter.split("+"):
            if rule.startswith("liq"):
                q = int(rule[3:]) / 100
                amt = (panel["close"] * panel["volume"]).groupby(level="ticker").transform(lambda x: x.rolling(20, min_periods=10).mean())
                keep &= (amt.groupby(level="date").rank(pct=True) >= 1 - q).fillna(False)
            elif rule.startswith("spike"):
                k = int(rule[5:]) / 10
                keep &= (panel["vol_sma_ratio_20"] >= k - 1).fillna(False)
            else:
                raise ValueError(rule)
        panel.loc[~keep.values, ycol] = np.nan
        print(f"[SAMPLE] {a.sample_filter}:保留 {keep.mean() * 100:.1f}% 的樣本")
    tr, va, te = time_split(panel, cfg["train_end"], cfg["val_end"], cfg["horizon"], ycol)
    if cfg.get("stride", 1) > 1 and not cfg.get("_strided"):
        ud = np.array(sorted(tr.index.get_level_values("date").unique()))[::cfg["stride"]]
        tr = tr[tr.index.get_level_values("date").isin(ud)]
        print(f"[STRIDE] 訓練列每 {cfg['stride']} 日取一 → {len(tr)}")
    del panel
    if cfg.get("deadzone", 0) > 0:
        n0 = (len(tr), len(va), len(te))
        tr, va, te = apply_deadzone((tr, va, te), cfg["horizon"], cfg["deadzone"])
        print(f"[DEADZONE] |r| < {cfg['deadzone']} 剔除:{n0} → {(len(tr), len(va), len(te))};"
              f" test 漲比例 {te[ycol].mean():.3f}")
    print(f"[SPLIT] train {len(tr)} / val {len(va)} / test {len(te)}  label={ycol} "
          f"漲比例 train {tr[ycol].mean():.3f} test {te[ycol].mean():.3f}")

    results, importance_df = {}, None
    for name in cfg["feature_sets"]:
        feats = feature_list(name, fam)
        kept, stats = filter_features(tr, feats, cfg["max_nan"])
        if name == "full":
            stats.to_csv(os.path.join(EXP, f"{a.tag}_feature_stats.csv"))
        print(f"\n=== {name}: {len(feats)} 欄 → 過濾後 {len(kept)} ===")
        want_imp = (name == "full") and bool(cfg["prune"])
        results[name], imp = run_set(name, kept, tr, va, te, ycol, cfg, cfg["seeds"],
                                     cfg["null_reps"], want_importance=want_imp)
        if imp is not None:
            imp["family"] = [fam[f] for f in imp.index]
            importance_df = imp

    if importance_df is not None:
        imp_fp = os.path.join(EXP, f"{a.tag}_importance.csv")
        importance_df.sort_values("rank_mean").to_csv(imp_fp)
        plots.importance_bars(importance_df, os.path.join(FIGS, f"{a.tag}_importance_top40.png"))
        plots.family_bars(importance_df, os.path.join(FIGS, f"{a.tag}_importance_family.png"))
        order = list(importance_df.sort_values("rank_mean").index)
        kept, dropped = dedupe_correlated(tr, order, thr=cfg["corr_thr"])
        print(f"\n[DEDUPE] |ρ|>{cfg['corr_thr']}: {len(order)} → {len(kept)} 欄 (剔 {len(dropped)})")
        results["full"]["dedupe_dropped"] = dropped
        for rule in cfg["prune"]:
            sel = apply_rule(rule, kept, importance_df["gain_mean"], importance_df["perm_mean"],
                             importance_df["rank_mean"])
            if not sel:
                print(f"[PRUNE {rule}] 無特徵留下,跳過")
                continue
            print(f"\n=== full_{rule}: {len(sel)} 欄 ===")
            results[f"full_{rule}"], _ = run_set(f"full_{rule}", sel, tr, va, te, ycol, cfg,
                                                 cfg["seeds"], cfg["null_reps"])

    h = cfg["horizon"]
    plots.decile_bars({n: r["ensemble"]["decile"][f"h{h}"] for n, r in results.items() if r["ensemble"]["decile"].get(f"h{h}")},
                      h, os.path.join(FIGS, f"{a.tag}_decile_h{h}.png"),
                      f"{a.tag}  十分位年化報酬(test, 3-seed 平均機率)")

    pred = te[[c for c in te.columns if c.startswith("r_h")]].copy()
    for n, r in results.items():
        pred[f"p_{n}"] = np.asarray(r.pop("_p_ens"), dtype="float32")
    pred.to_parquet(os.path.join(EXP, f"{a.tag}_testpred.parquet"))

    exp = {"tag": a.tag, "time": datetime.now().isoformat(timespec="seconds"),
           "config": cfg, "label": ycol,
           "n_train": len(tr), "n_val": len(va), "n_test": len(te),
           "test_up_ratio": float(te[ycol].mean()), "train_up_ratio": float(tr[ycol].mean()),
           "results": results, "elapsed_s": round(time.time() - t_all)}
    with open(os.path.join(EXP, f"{a.tag}.json"), "w", encoding="utf-8") as f:
        json.dump(exp, f, indent=1, ensure_ascii=False, default=float)

    table = md_table(results, cfg)
    rec = [f"\n### {a.tag}  ({exp['time']})", "",
           f"- pool={cfg['pool']} label={ycol} seeds={cfg['seeds']} "
           f"train≤{cfg['train_end']} / val≤{cfg['val_end']} / test 之後;"
           f"n = {len(tr)} / {len(va)} / {len(te)};耗時 {exp['elapsed_s']}s",
           f"- XGB: {cfg['xgb']};剔除規則 {cfg['prune']};相關去重 |ρ|>{cfg['corr_thr']}",
           f"- 圖:figs/{a.tag}_decile_h{h}.png"
           + (f", figs/{a.tag}_importance_top40.png, figs/{a.tag}_importance_family.png"
              if importance_df is not None else ""), "", table, ""]
    with open(os.path.join(ROOT, "實驗記錄.md"), "a", encoding="utf-8") as f:
        f.write("\n".join(rec))
    print("\n" + table)
    print(f"\n[SAVED] experiments/{a.tag}.json  ({exp['elapsed_s']}s)")


if __name__ == "__main__":
    main()
