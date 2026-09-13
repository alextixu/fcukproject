"""彙整 results/ 的 JSON 成 markdown 表(門檻曲線三池同表、階段二三 all + 4σ 的四大指標與對照組)。
用法:python summarize_bigmove.py  → results/bigmove_summary_2026-09-14.md(同時印到螢幕)
"""
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
OUT = os.path.join(RES, "bigmove_summary_2026-09-14.md")
L = []
p = L.append


def f1(x):
    return "—" if x is None or x != x else f"{x:.1f}"


def f2(x):
    return "—" if x is None or x != x else f"{x:.2f}"


def f3(x):
    return "—" if x is None or x != x else f"{x:.3f}"


# ── 一、門檻曲線 ────────────────────────────────────────────────
p("# 大漲 AE + OC-SVM:門檻曲線與 all 池 4σ 完整結果(2026-09-14)\n")
p("## 一、門檻曲線:tw200 / tw500 / all 同表(輸入 C,z=16,OC-SVM nu=0.1,gamma=scale)\n")
p("tw200 的 C 是 method_xgb 現成面板(346 欄,含 20 欄橫斷面 cs_/mkt_);tw500 與 all 由 add_ta.py 逐檔補單股指標(326 欄,無橫斷面欄)。"
  "「隨機」= 該段正例比例;「倍數」= Precision / 隨機。kNN 純度倍數 = 驗證段正例的 20 個訓練鄰居中正例比例 / 訓練正例比例。\n")
p("| 池 | 門檻 | 訓練正例 | 正例比例 train/val/test | kNN 純度倍數 | AE 誤差 AUC val/test | OC-SVM 前10% P test(倍數) | OC-SVM 前1% P test(倍數) | XGB AUC val/test | XGB 前10% P test(倍數) | XGB 前1% P test(倍數) |")
p("|---|---|---:|---|---:|---|---|---|---|---|---|")
pools = ["tw200", "tw500", "all"]
thr_order = ["2σ√5", "3σ√5", "4σ√5", "5σ√5", "固定+10%", "固定+15%", "固定+20%"]
for name in thr_order:
    for pool in pools:
        fp = os.path.join(RES, f"bigmove_threshold_curve_{pool}.json")
        if not os.path.exists(fp):
            continue
        d = json.load(open(fp, encoding="utf-8"))
        if name not in d:
            continue
        r = d[name]
        b = r["base"]
        bt = b["te"] * 100
        mult = lambda P: f"{P:.2f}%({P / bt:.1f}x)" if bt > 0 else "—"
        p(f"| {pool} | {name} | {r['n_pos']['tr']:,} | {b['tr']*100:.2f}/{b['va']*100:.2f}/{b['te']*100:.2f}% | {r['knn_purity']/r['knn_base']:.2f}x | "
          f"{f3(r['recon_auc']['va'])}/{f3(r['recon_auc']['te'])} | {mult(r['ocsvm_top10']['te']['P'])} | {mult(r['ocsvm_top1']['te']['P'])} | "
          f"{f3(r['xgb_auc']['va'])}/{f3(r['xgb_auc']['te'])} | {mult(r['xgb_top10']['te']['P'])} | {mult(r['xgb_top1']['te']['P'])} |")
p("")

# ── 二、階段二三 ─────────────────────────────────────────────────
files = sorted(glob.glob(os.path.join(RES, "bigmove_stage2_*_k*.json")))
for fp in files:
    d = json.load(open(fp, encoding="utf-8"))
    pool, z, k = d["pool"], d["z"], d["k_sigma"]
    p(f"## 二、階段二 + 三:{pool} 池,{k:g}σ√5,潛在維度 z={z}(輸入 C {d['n_cols']} 欄)\n")
    n, npos, base = d["n"], d["n_pos"], d["base"]
    p(f"train {n['tr']:,} 列(正例 {npos['tr']:,},{base['tr']*100:.2f}%)/ val {n['va']:,}(正例 {npos['va']:,},{base['va']*100:.2f}%)/ "
      f"test {n['te']:,}(正例 {npos['te']:,},{base['te']*100:.2f}%);test 交易日 {d['test_days']}。\n")
    for tag in ("AE_大漲樣本", "AE_全部樣本(對照)"):
        if tag not in d:
            continue
        r = d[tag]
        p(f"### {tag}\n")
        p("| 驗收項目 | 值 | 過關標準 |")
        p("|---|---|---|")
        p(f"| 訓練輪數 | {r['epochs']} | 驗證正例 MSE 10 輪不降即停 |")
        p(f"| 正例 MSE train / val / test | {r['train_pos_mse']:.3f} / {r['mse_pos']['va']:.3f} / {r['mse_pos']['te']:.3f} | 全猜平均 = 1.0,要 < 0.3;val ≤ train × 1.3 |")
        p(f"| 非正例 MSE val / test | {r['mse_neg']['va']:.3f} / {r['mse_neg']['te']:.3f} | 要明顯 > 正例 |")
        p(f"| 逐欄重建相關 最低 / 中位;< 0.5 的欄數 | {r['col_corr_min']:.2f} / {r['col_corr_median']:.2f};{r['cols_corr_below_0.5']} / {d['n_cols']} | 不能有完全還原不了的欄 |")
        p(f"| 「誤差小 = 像大漲」AUC val / test | {r['recon_err_auc']['va']:.3f} / {r['recon_err_auc']['te']:.3f} | ≥ 0.60 |")
        p(f"| 潛在向量 logistic AUC val / test | {r['latent_lr_auc']['va']:.3f} / {r['latent_lr_auc']['te']:.3f} | 不低於原始輸入 − 0.02 |")
        p(f"| 原始輸入 logistic AUC val / test | {r['raw_lr_auc']['va']:.3f} / {r['raw_lr_auc']['te']:.3f} | (參考) |")
        p("")
        p("| 判法 | nu | 段 | 出訊號 % | Precision % | 隨機 % | 倍數 | Recall % | Accuracy % | F1 % | 每年訊號數(test) |")
        p("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|")

        def row(name, nu, seg, m, py=None):
            mult = m["P"] / m["base"] if m["base"] > 0 else float("nan")
            pys = ""
            if py:
                pys = ";".join(f"{yr}:{v['signals']:,}(中 {v['hits']}),年率 {v['signals_per_245d']:,}" for yr, v in py.items())
            p(f"| {name} | {nu} | {seg} | {m['sig']:.1f} | {m['P']:.2f} | {m['base']:.2f} | {mult:.2f}x | {m['R']:.1f} | {m['Acc']:.1f} | {m['F1']:.2f} | {pys} |")

        for nu, o in r["ocsvm"].items():
            for key, label in (("raw", "OC-SVM 原判法"), ("top10", "OC-SVM 前10%"), ("top1", "OC-SVM 前1%")):
                for seg in ("va", "te"):
                    row(label, nu, seg, o[key][seg], o.get("per_year_test", {}).get(key) if seg == "te" else None)
        for nm, c in r["contrast"].items():
            for seg in ("va", "te"):
                row("對照 " + nm, "—", seg, c[seg], c.get("per_year_test") if seg == "te" else None)
        p("")
    p("### 對照:原始 C + XGB(有反例,不經 AE)\n")
    if "對照_原始C+XGB_auc" in d:
        p(f"XGB AUC val {d['對照_原始C+XGB_auc']['va']:.3f} / test {d['對照_原始C+XGB_auc']['te']:.3f}。\n")
    p("| 判法 | 段 | 出訊號 % | Precision % | 隨機 % | 倍數 | Recall % | Accuracy % | F1 % | 每年訊號數(test) |")
    p("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for key in ("對照_原始C+XGB前10%", "對照_原始C+XGB前1%"):
        if key not in d:
            continue
        c = d[key]
        for seg in ("va", "te"):
            m = c[seg]
            pys = ";".join(f"{yr}:{v['signals']:,}(中 {v['hits']}),年率 {v['signals_per_245d']:,}" for yr, v in c["per_year_test"].items()) if seg == "te" else ""
            p(f"| {key.replace('對照_', '')} | {seg} | {m['sig']:.1f} | {m['P']:.2f} | {m['base']:.2f} | {m['P']/m['base']:.2f}x | {m['R']:.1f} | {m['Acc']:.1f} | {m['F1']:.2f} | {pys} |")
    p("")

# ── 三、穩定性:同一設定不同種子 / 不同 z,OC-SVM 各判法的 Precision 倍數 ─────────
runs = []
for fp in files:
    d = json.load(open(fp, encoding="utf-8"))
    if d["pool"] == "all" and d["k_sigma"] == 4:
        runs.append(d)
if runs:
    p("## 三、穩定性:all 池 4σ√5,z 與種子不同時 OC-SVM(AE 只用大漲樣本)的 Precision 倍數(val / test)\n")
    p("倍數 = Precision / 該段正例比例;目標 ≥ 2 倍且 val、test 都要過。每年訊號數 = 測試段該判法的訊號數換算 245 個交易日。\n")
    p("| z | seed | AE 誤差 AUC val/test | 判法 | nu=0.05 | nu=0.1 | nu=0.2 | nu=0.5 | 每年訊號數(nu=0.2) | 其中真 4σ 大漲(nu=0.2,2025 / 2026) |")
    p("|---|---|---|---|---|---|---|---|---|---|")
    for d in sorted(runs, key=lambda d: (d["z"], d.get("seed", 42))):
        r = d["AE_大漲樣本"]
        for key, label in (("raw", "原判法"), ("top10", "前10%"), ("top1", "前1%")):
            cells = []
            for nu in ("0.05", "0.1", "0.2", "0.5"):
                o = r["ocsvm"].get(nu)
                if not o:
                    cells.append("—"); continue
                mv, mt = o[key]["va"]["P"] / o[key]["va"]["base"], o[key]["te"]["P"] / o[key]["te"]["base"]
                cells.append(f"{mv:.1f} / {mt:.1f}" + (" ✓" if mv >= 2 and mt >= 2 else ""))
            py = r["ocsvm"].get("0.2", {}).get("per_year_test", {}).get(key, {})
            rate = ", ".join(f"{yr}:{v['signals_per_245d']:,}" for yr, v in py.items())
            hits = " / ".join(f"{v['hits']}" for v in py.values())
            p(f"| {d['z']} | {d.get('seed', 42)} | {r['recon_err_auc']['va']:.3f}/{r['recon_err_auc']['te']:.3f} | {label} | " + " | ".join(cells) + f" | {rate} | {hits} |")
    p("")
    p("對照組(同樣 all 池 4σ,倍數 val / test):\n")
    p("| z | seed | 重建誤差前10% | 重建誤差前1% | 潛在+logistic前10% | 潛在+logistic前1% | 原始C+XGB前10% | 原始C+XGB前1% |")
    p("|---|---|---|---|---|---|---|---|")
    for d in sorted(runs, key=lambda d: (d["z"], d.get("seed", 42))):
        r = d["AE_大漲樣本"]
        m = lambda c: f"{c['va']['P']/c['va']['base']:.1f} / {c['te']['P']/c['te']['base']:.1f}"
        p(f"| {d['z']} | {d.get('seed', 42)} | {m(r['contrast']['重建誤差前10%'])} | {m(r['contrast']['重建誤差前1%'])} | {m(r['contrast']['潛在+logistic前10%'])} | "
          f"{m(r['contrast']['潛在+logistic前1%'])} | {m(d['對照_原始C+XGB前10%'])} | {m(d['對照_原始C+XGB前1%'])} |")
    p("")

txt = "\n".join(L)
open(OUT, "w", encoding="utf-8").write(txt)
print(txt)
print(f"\n[SAVED] {OUT}")
