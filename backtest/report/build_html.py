"""ncku/out/summary_ncku.json(框架結果,主體)+ results/*.json(自算扣成本對照)→ results/report_2026.html。"""
import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
from common import paths as P  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = P.RESULTS
NC = json.load(open(os.path.join(P.NCKU, "out", "summary_ncku.json"), encoding="utf-8"))
XG = json.load(open(os.path.join(RES, "xgb_2026.json"), encoding="utf-8")) if os.path.exists(os.path.join(RES, "xgb_2026.json")) else {}
KL = json.load(open(os.path.join(RES, "kline_2026.json"), encoding="utf-8")) if os.path.exists(os.path.join(RES, "kline_2026.json")) else {}
CG = json.load(open(os.path.join(RES, "cgcn_2026.json"), encoding="utf-8")) if os.path.exists(os.path.join(RES, "cgcn_2026.json")) else {}
LG_FP = os.path.join(P.NCKU, "out", "summary_logic.json")
LG = json.load(open(LG_FP, encoding="utf-8")) if os.path.exists(LG_FP) else {}
LG2_FP = os.path.join(P.NCKU, "out", "summary_logic2.json")
LG2 = json.load(open(LG2_FP, encoding="utf-8")) if os.path.exists(LG2_FP) else {}
FINAL1 = "no_dist|3ATR|30%"
FINAL = "vol2k|ret20|10|3ATR|30%"
if FINAL in LG2:
    NC["system_final"] = dict(LG2[FINAL], realized=0, unrealized=0, n_orders_ok=LG2[FINAL]["n_round_trips"] * 2)
if FINAL1 in LG:
    NC["system_v1"] = dict(LG[FINAL1], realized=0, unrealized=0, n_orders_ok=LG[FINAL1]["n_round_trips"] * 2)

LABEL = {
    "bench_0050": ("基準", "0050 買進持有", "—"),
    "bench_tw50_ew": ("基準", "tw50 等權買進持有", "—"),
    "bench_tw200_ew": ("基準", "tw200 等權買進持有", "—"),
    "kline_1d7": ("KLINE 系統 A", "1日-7特徵型態,持有 5 日", "訊號做多"),
    "kline_2d10": ("KLINE 系統 A", "2日-10特徵型態,持有 5 日", "訊號做多(框架不能放空,跌訊號略)"),
    "kline_3d12": ("KLINE 系統 A", "3日-12特徵型態,持有 5 日", "訊號做多"),
    "xgb_tw50_h5_top20frozen": ("XGB 老師的方法", "tw50 h=5,2024 篩出的 20 欄原封重訓", "每 5 日換股,機率前 10%(5 檔)"),
    "xgb_tw50_h5_permpos": ("XGB 老師的方法", "tw50 h=5,permpos 篩選", "每 5 日換股,機率前 10%(5 檔)"),
    "xgb_tw50_h5_full": ("XGB 老師的方法", "tw50 h=5,全 242 欄", "每 5 日換股,機率前 10%(5 檔)"),
    "xgb_tw50_h1_permpos": ("XGB 老師的方法", "tw50 h=1,permpos 篩選", "每日換股,機率前 10%(5 檔)"),
    "xgb_tw200_h5_top20frozen": ("XGB 老師的方法", "tw200 h=5,2024 篩出的 20 欄原封重訓", "每 5 日換股,機率前 10%(約 21 檔)"),
    "xgb_tw200_h5_top20": ("XGB 老師的方法", "tw200 h=5,top20 篩選", "每 5 日換股,機率前 10%(約 21 檔)"),
    "xgb_tw200_h5_full": ("XGB 老師的方法", "tw200 h=5,全 242 欄", "每 5 日換股,機率前 10%(約 21 檔)"),
    "xgb_tw200_h20_top20": ("XGB 老師的方法", "tw200 h=20,top20 篩選(不含籌碼)", "每 20 日換股,機率前 10%(約 21 檔)"),
    "xgb_tw200_h20_permpos": ("XGB 老師的方法", "tw200 h=20,permpos 篩選(不含籌碼)", "每 20 日換股,機率前 10%(約 21 檔)"),
    "xgb_tw200_h5_permpos": ("XGB 老師的方法", "tw200 h=5,permpos 篩選", "每 5 日換股,機率前 10%(約 21 檔)"),
    "xgb_tw200_h20_chip_top20frozen": ("XGB 老師的方法", "tw200 h=20 含籌碼,2024 最佳 e6c 的 20 欄原封重訓", "每 20 日換股,機率前 10%(約 22 檔)"),
    "xgb_tw200_h20_chip_full": ("XGB 老師的方法", "tw200 h=20 含籌碼,全 283 欄", "每 20 日換股,機率前 10%(約 22 檔)"),
    "system_final": ("最終系統", "XGB tw50 h=5 permpos + 流動性 ≥2,000 張 + 大盤 20 日報酬>0 才買 + 汰弱留強(前 10 名續抱)+ 3×ATR 停損 + 30% 停利", "每 5 日檢視;大盤弱只賣不買;停損停利盤中觸價"),
    "system_v1": ("XGB 老師的方法", "v1 邏輯層:排除出貨型 + 3×ATR 停損 + 30% 停利", "每 5 日全部換股 5 檔"),
    "cgcn_h1_rank": ("Chart-GCN 系統 B", "gridbest-date h=1,3 seed 平均", "每日換股,機率前 10%(5 檔)"),
    "cgcn_h5_rank": ("Chart-GCN 系統 B", "gridbest-date h=5,3 seed 平均", "每 5 日換股,機率前 10%(5 檔)"),
    "cgcn_h1_paper63": ("Chart-GCN 系統 B", "gridbest-date h=1,論文 §6.3 原始規則", "預測漲→買;預測跌或 MACD<0→賣"),
}
ORDER = list(LABEL)
SYS_COLOR = {"基準": "--bench", "KLINE 系統 A": "--s2", "XGB 老師的方法": "--s1", "Chart-GCN 系統 B": "--s3", "最終系統": "--s7"}
HEADLINE = ["system_final", "bench_0050", "bench_tw50_ew", "xgb_tw50_h5_permpos", "kline_1d7", "cgcn_h5_rank"]


def f(v, suf="%"):
    return "—" if v is None else f"{v:+.2f}{suf}"


def row(k, r):
    sysname, setting, kind = LABEL.get(k, ("其他", k, ""))
    return (f"<tr><td><span class='dot' style='background:var({SYS_COLOR.get(sysname, '--ink3')})'></span>{sysname}</td><td>{setting}</td><td class='note'>{kind}</td>"
            f"<td class='num {'pos' if r['total_return_pct'] > 0 else 'neg'}'><b>{f(r['total_return_pct'])}</b></td>"
            f"<td class='num'>{r['max_dd_pct']:.1f}%</td><td class='num'>{r['daily_sharpe_ann']:.2f}</td>"
            f"<td class='num'>{r['n_orders_ok']}</td><td class='num'>{r['n_round_trips']}</td><td class='num'>{r['win_rate'] if r['win_rate'] is not None else '—'}</td>"
            f"<td class='num'>{r['realized']:,.0f}</td><td class='num'>{r['unrealized']:,.0f}</td></tr>")


keys = [k for k in ORDER if k in NC] + [k for k in NC if k not in ORDER]
rows_html = "\n".join(row(k, NC[k]) for k in keys)

# 對照:自算(扣成本 0.585%/趟,yfinance 還原價)
cross = []
if XG:
    for tag, r in XG.items():
        for name, s in r["sets"].items():
            cross.append((f"XGB {tag} / {name}", s["long_net"]["cum_pct"], s["long_net"]["t"], s["hl_net"]["cum_pct"], s["hl_net"]["t"], s["test_auc"]))
if CG:
    for hk, m in CG["models"].items():
        rd = m.get("rank_decile")
        if rd:
            cross.append((f"Chart-GCN {hk} 排名", rd["long_net"]["cum_pct"], rd["long_net"]["t"], rd["hl_net"]["cum_pct"], rd["hl_net"]["t"], None))
if KL:
    for n, s in KL["results"].items():
        cross.append((f"KLINE {n}(open 口徑,扣 0.42%/筆)", s["open"]["portfolio_ret_pct"], s["open"]["t_stat"], None, None, None))
cross_html = "\n".join(
    f"<tr><td>{c[0]}</td><td class='num {'pos' if c[1] > 0 else 'neg'}'>{f(c[1])}</td><td class='num'>{c[2] if c[2] is not None else '—'}</td>"
    f"<td class='num'>{f(c[3]) if c[3] is not None else '—'}</td><td class='num'>{c[4] if c[4] is not None else '—'}</td><td class='num'>{c[5] if c[5] else '—'}</td></tr>"
    for c in cross)

def lg_tab(rows, cols):
    head = "".join(f"<th{' class=num' if i else ''}>{c}</th>" for i, c in enumerate(cols))
    body = "".join("<tr>" + "".join(f"<td{' class=num' if i else ''}>{v}</td>" for i, v in enumerate(r)) + "</tr>" for r in rows)
    return f"<div class='tbl'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
def lg_rows(sel, key, extra):
    out = []
    for n, r in LG.items():
        if all(r[k] == v for k, v in sel.items()):
            out.append([r[key], f"{r['total_return_pct']:+.1f}%", f"{r['max_dd_pct']:.1f}%", r["daily_sharpe_ann"], r["win_rate"], r[extra]])
    return out
FN = {"none": "不過濾", "up_vol": "量增價漲才買", "no_dist": "排除量增價跌", "vol_only": "只要量增", "up_only": "只要價漲"}
logic_html = ""
if LG:
    fr = lg_rows({"stop": "none", "take": "none"}, "filter", "n_filtered_out"); fr = [[FN.get(r[0], r[0])] + r[1:] for r in fr]
    sr = lg_rows({"filter": "none", "take": "none"}, "stop", "n_stop_exits")
    tr = lg_rows({"filter": "none", "stop": "none"}, "take", "n_tp_exits")
    both = sorted([(n, r) for n, r in LG.items() if r["stop"] != "none" and r["take"] != "none"], key=lambda x: -x[1]["total_return_pct"])[:8]
    br = [[n.replace("|", " / "), f"{r['total_return_pct']:+.1f}%", f"{r['max_dd_pct']:.1f}%", r["daily_sharpe_ann"], r["win_rate"], f"{r['n_stop_exits']} / {r['n_tp_exits']}"] for n, r in both]
    logic_html = f"""<section>
<h2>交易邏輯層(接在 XGB tw50 h=5 permpos 排名後面,{len(LG)} 組網格)</h2>
<p class="lede">三個維度各自單獨看(其餘兩個關掉),再看「停損與停利都有設」的前 8 組。基準:不加任何邏輯 = +{LG['none|none|none']['total_return_pct']:.1f}%。</p>
<div class="grid3">
<div><h3>量價進場過濾</h3>{lg_tab(fr, ["過濾", "總收益", "MDD", "Sharpe", "勝率", "被濾掉"])}</div>
<div><h3>停損</h3>{lg_tab(sr, ["停損", "總收益", "MDD", "Sharpe", "勝率", "觸發次數"])}</div>
<div><h3>停利</h3>{lg_tab(tr, ["停利", "總收益", "MDD", "Sharpe", "勝率", "觸發次數"])}</div>
</div>
<h3>停損 + 停利都設定的前 8 組</h3>{lg_tab(br, ["過濾 / 停損 / 停利", "總收益", "MDD", "Sharpe", "勝率", "停損 / 停利次數"])}
</section>"""

logic2_html = ""
if LG2:
    def rows2(sel, key, extra):
        out = []
        for n, r in LG2.items():
            if all(r[k] == v for k, v in sel.items()):
                out.append([r[key], f"{r['total_return_pct']:+.1f}%", f"{r['max_dd_pct']:.1f}%", r["daily_sharpe_ann"], f"{r['avg_exposure_pct']}%", r["win_rate"], r[extra]])
        return out
    B = {"liq": "none", "mkt": "none", "hys": "none", "stops": "3ATR|30%"}
    LN = {"none": "不過濾", "to1e": "5 日均成交額 ≥ 1 億", "to3e": "≥ 3 億", "vol2k": "5 日均量 ≥ 2,000 張"}
    MN = {"none": "不看大盤", "ma20": "0050 > MA20", "ma60": "0050 > MA60", "ret20": "0050 20 日報酬 > 0"}
    HN = {"none": "每次全換", "10": "前 10 名續抱", "15": "前 15 名續抱", "20": "前 20 名續抱"}
    lr = [[LN[r[0]]] + r[1:] for r in rows2({k: v for k, v in B.items() if k != "liq"}, "liq", "n_liq_filtered")]
    mr = [[MN[r[0]]] + r[1:] for r in rows2({k: v for k, v in B.items() if k != "mkt"}, "mkt", "n_mkt_blocked")]
    hr = [[HN[r[0]]] + r[1:] for r in rows2({k: v for k, v in B.items() if k != "hys"}, "hys", "n_kept")]
    allon = sorted([(n, r) for n, r in LG2.items() if r["liq"] != "none" and r["mkt"] != "none" and r["hys"] != "none" and r["stops"] != "none"], key=lambda x: -x[1]["daily_sharpe_ann"])[:8]
    ar = [[n.replace("|", " / "), f"{r['total_return_pct']:+.1f}%", f"{r['max_dd_pct']:.1f}%", r["daily_sharpe_ann"], f"{r['avg_exposure_pct']}%", r["win_rate"], f"{r['n_mkt_blocked']} / {r['n_kept']}"] for n, r in allon]
    cols = ["", "總收益", "MDD", "Sharpe", "平均持股比", "勝率", ""]
    logic2_html = f"""<section>
<h2>交易邏輯層 v2:流動性、大盤濾網、汰弱留強({len(LG2)} 組網格,停損停利固定 3×ATR + 30%)</h2>
<p class="lede">取代 v1 的量價過濾。三個維度各自單獨看(其餘關掉),再看「三個都開」的組合依 Sharpe 排序。基準:三個都關 = +{LG2['none|none|none|3ATR|30%']['total_return_pct']:.1f}%、MDD {LG2['none|none|none|3ATR|30%']['max_dd_pct']}%。</p>
<div class="grid3">
<div><h3>流動性過濾</h3>{lg_tab(lr, ["門檻"] + cols[1:6] + ["濾掉"])}</div>
<div><h3>大盤濾網(弱勢時只賣不買)</h3>{lg_tab(mr, ["條件"] + cols[1:6] + ["擋下買單"])}</div>
<div><h3>汰弱留強</h3>{lg_tab(hr, ["規則"] + cols[1:6] + ["續抱次數"])}</div>
</div>
<h3>三個機制都開的組合,依 Sharpe 排序前 8</h3>{lg_tab(ar, ["流動性 / 大盤 / 續抱 / 停損停利"] + cols[1:6] + ["擋下 / 續抱"])}
</section>"""

# ── 股票池階梯 + tw50 優化 ──
LAD_FP = os.path.join(P.NCKU, "out", "pool_ladder_yf.json")
OPT_FP = os.path.join(P.NCKU, "out", "summary_opt_tw50_official.json")
ladder_html = ""
if os.path.exists(LAD_FP):
    LAD = json.load(open(LAD_FP, encoding="utf-8"))
    PN = {"tw50": "tw50", "tw100": "tw100", "tw200": "tw200", "tw500": "tw500", "electronics": "電子 46", "semi": "半導體", "elec_liq100": "電子流動性前 100", "elec_liq200": "電子流動性前 200", "elec_all": "電子全部"}
    lr = [[PN.get(r["池"], r["池"]), r["檔數"], f"{r['AUC']:.3f}", f"{r['等權']:+.1f}%", f"{r['模型5日permpos淨']:+.1f}%", f"{r['v2最佳淨']:+.1f}%", r["v2設定"].replace("full_permpos", "permpos").replace("full_top20", "top20").replace("full/", "全欄位/"), f"{r['v2淨MDD']:.1f}%", r["v2淨Sharpe"]] for r in sorted(LAD, key=lambda r: -r["v2最佳淨"])]
    ladder_html = f"""<section>
<h2>股票池階梯:同一套 XGB(h=5、各池自行重訓)換不同股票池</h2>
<p class="lede">每個池子都用 2016~2024 資料各自訓練,2026 在框架引擎上跑「只有模型」(每 5 日前 5 名全換)與 v2 系統(5 日 / 每日檢視 × 三種特徵集取最好),數字全部扣成本(買 0.1425%、賣 0.4425%)。篩選用 yfinance 還原價餵框架;tw50 用同法校準,與官方資料差不到 3 個百分點。</p>
{lg_tab(lr, ["股票池", "檔數", "AUC", "同池等權", "只有模型 5 日", "v2 最佳", "v2 設定", "淨 MDD", "淨 Sharpe"])}
<p class="lede" style="margin-top:10px">池子越大 AUC 越高、報酬反而越低:只買前 5 名時,大池的頭部是冷門高波動股,排序整體準、頭部不準,加上換手成本。tw500 扣成本後連同池等權都勉強打平。</p>
</section>"""
opt_html = ""
if os.path.exists(OPT_FP):
    OPT = json.load(open(OPT_FP, encoding="utf-8"))
    A = [r for r in OPT.values() if r["liq"] == "vol2k" and r["mkt"] == "ret20" and r["stops"] == "3ATR|30%"]
    ar = [[f"每 {r['freq']} 日", r["K"], ("不續抱" if r["hys_mult"] == 0 else f"前 {r['hys_mult'] * r['K']} 名"), f"{r['net_return_pct']:+.1f}%", f"{r['net_max_dd_pct']:.1f}%", r["net_sharpe"], f"{r['buy_turnover_x']}x"]
          for r in sorted(A, key=lambda r: -r["net_sharpe"])[:10]]
    B = [r for r in OPT.values() if r["freq"] == 5 and r["K"] == 5 and r["hys_mult"] == 2]
    LNm = {"vol1k": "均量 ≥ 1,000 張", "vol2k": "≥ 2,000 張", "vol5k": "≥ 5,000 張", "to3e": "成交額 ≥ 3 億"}
    MNm = {"none": "不看", "ma20": "> MA20", "ma60": "> MA60", "ret20": "20 日報酬 > 0"}
    br = [[LNm[r["liq"]], MNm[r["mkt"]], r["stops"].replace("|", " + "), f"{r['net_return_pct']:+.1f}%", f"{r['net_max_dd_pct']:.1f}%", r["net_sharpe"]]
          for r in sorted(B, key=lambda r: -r["net_sharpe"])[:12]]
    opt_html = f"""<section>
<h2>tw50 優化({len(OPT)} 組,證交所官方資料,扣成本排名)</h2>
<p class="lede">兩階段座標搜尋。A 先掃結構(檢視頻率 × 持股數 × 續抱門檻,過濾與停損停利固定),B 再在最佳結構上掃流動性 × 大盤 × 停損停利。四個機制都開、扣成本 Sharpe 最高的組合就是原本的 v2 系統,優化確認了現行設定而沒有找到更好的。</p>
<div class="grid3" style="grid-template-columns:repeat(auto-fit,minmax(460px,1fr))">
<div><h3>A 結構,依淨 Sharpe 前 10</h3>{lg_tab(ar, ["頻率", "K", "續抱", "扣成本", "淨 MDD", "淨 Sharpe", "週轉"])}</div>
<div><h3>B 過濾與出場(每 5 日、K=5、前 10 名續抱),前 12</h3>{lg_tab(br, ["流動性", "大盤", "停損停利", "扣成本", "淨 MDD", "淨 Sharpe"])}</div>
</div>
</section>"""

# ── 換股日相位敏感度 + 7/1~9/11 區間 ──
phase_html = ""
PH_FP = os.path.join(P.NCKU, "out", "fullyear_phase_sensitivity.json")
WS_FP = os.path.join(P.NCKU, "out", "window_start_sensitivity.json")
if os.path.exists(PH_FP) and os.path.exists(WS_FP):
    PH = json.load(open(PH_FP, encoding="utf-8")); WS = json.load(open(WS_FP, encoding="utf-8"))
    pr = [[r["第一訊號日"], f"{r['系統扣成本']:+.1f}%", f"{r['系統淨MDD']:.1f}%", f"{r['只有模型扣成本']:+.1f}%", f"{r['只有模型淨MDD']:.1f}%", f"{r['tw50等權']:+.1f}%", f"{r['0050']:+.1f}%"] for r in PH]
    avg = lambda L, k: sum(r[k] for r in L) / len(L)
    pr.append(["平均", f"{avg(PH, '系統扣成本'):+.1f}%", f"{avg(PH, '系統淨MDD'):.1f}%", f"{avg(PH, '只有模型扣成本'):+.1f}%", f"{avg(PH, '只有模型淨MDD'):.1f}%", f"{avg(PH, 'tw50等權'):+.1f}%", f"{avg(PH, '0050'):+.1f}%"])
    wr = [[r["第一訊號日"], f"{r['系統扣成本']:+.1f}%", f"{r['系統淨MDD']:.1f}%", f"{r['停損']} / {r['停利']}", f"{r['只有模型扣成本']:+.1f}%", f"{r['tw50等權']:+.1f}%", f"{r['0050']:+.1f}%"] for r in WS]
    wr.append(["平均", f"{avg(WS, '系統扣成本'):+.1f}%", f"{avg(WS, '系統淨MDD'):.1f}%", "", f"{avg(WS, '只有模型扣成本'):+.1f}%", f"{avg(WS, 'tw50等權'):+.1f}%", f"{avg(WS, '0050'):+.1f}%"])
    phase_html = f"""<section>
<h2>穩健度檢查:換股日相位(重要,修正上方的 +233%)</h2>
<p class="lede">系統每 5 個交易日換一次股,所以「從哪一天開始算」有 5 種相位。上方所有結果都只用了 1/2 起算的那一種。把 5 種相位全部跑過(框架 + 官方資料 + 扣成本,至 9/11):</p>
{lg_tab(pr, ["第一訊號日", "最終系統 扣成本", "淨 MDD", "只有模型 扣成本", "淨 MDD", "tw50 等權", "0050"])}
<p class="lede" style="margin-top:10px"><b>+233% 是 5 種相位裡最幸運的一種。</b>模型本身的訊號站得住:只有模型在每一種相位都贏兩個基準 50 到 160 個百分點。但交易邏輯層是在 1/2 相位上挑出來的,換到其他相位反而把報酬砍掉 60 到 110 個百分點,平均 +113% 還輸給只有模型的 +160%;它剩下的價值是回撤較低。交易邏輯層需要用 5 相位平均重新挑選。</p>
<h3 style="margin-top:18px">7/1 ~ 9/11 全新起跑(100 萬,第一個訊號日落在第一週的 5 個交易日)</h3>
{lg_tab(wr, ["第一訊號日", "最終系統 扣成本", "淨 MDD", "停損 / 停利", "只有模型 扣成本", "tw50 等權", "0050"])}
<p class="lede" style="margin-top:10px">7 月初進場剛好碰上 0050 七月下跌約 10%,前幾筆全被 3×ATR 停損(國巨 -22%、南亞 -19%、日月光 -10%、台積電 -8%)。5 種起跑日的最終系統全都輸給 tw50 等權;若是從 1 月一路跑下來(帶著 6 月的持股與進場價),同一段是 +28.8%。只有 10 週、5 檔持股,結果幾乎由起跑日決定。</p>
</section>"""

curves = {k: NC[k]["curve"] for k in keys}
dates = sorted({d for c in curves.values() for d in c})
series = {k: [curves[k].get(d) for d in dates] for k in keys}
# 缺日往前補
for k, s in series.items():
    last = 0.0
    for i, v in enumerate(s):
        if v is None:
            s[i] = last
        else:
            last = v
labels = {k: f"{LABEL.get(k, ('', k, ''))[1]}" for k in keys}
sysof = {k: LABEL.get(k, ("其他",))[0] for k in keys}

html = f"""<title>2026 台股回測對照</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{color-scheme:light;--bg:#f7f6f2;--surface:#ffffff;--ink:#1c1b18;--ink2:#5a5750;--ink3:#8a877e;--line:#e2dfd6;--grid:#ebe8e0;
 --s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s7:#4a3aa7;--bench:#8a877e;--pos:#008300;--neg:#c93a3a;--accent:#2a4a7a}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--bg:#151513;--surface:#1e1e1b;--ink:#f3f1ea;--ink2:#c3c2b7;--ink3:#8d8b82;--line:#33322e;--grid:#2a2926;
 --s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s7:#9085e9;--bench:#8d8b82;--pos:#3fbf3f;--neg:#ef6b6b;--accent:#8fb3e6}}}}
:root[data-theme="dark"]{{color-scheme:dark;--bg:#151513;--surface:#1e1e1b;--ink:#f3f1ea;--ink2:#c3c2b7;--ink3:#8d8b82;--line:#33322e;--grid:#2a2926;
 --s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s7:#9085e9;--bench:#8d8b82;--pos:#3fbf3f;--neg:#ef6b6b;--accent:#8fb3e6}}
body{{background:var(--bg);color:var(--ink);font-family:"Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif;font-size:15px;line-height:1.6;padding:32px 20px 64px}}
main{{max-width:1120px;margin:0 auto;display:grid;gap:36px}}
h1{{font-size:28px;font-weight:700;margin:0 0 4px;text-wrap:balance;letter-spacing:-.01em}}
h2{{font-size:18px;font-weight:700;margin:0 0 12px}}
.eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink3);font-family:"IBM Plex Mono",monospace}}
.lede{{color:var(--ink2);max-width:68ch;margin:0}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}}
.kpi{{background:var(--surface);border:1px solid var(--line);padding:14px 16px;border-radius:6px;border-top:3px solid var(--c)}}
.kpi .l{{font-size:12px;color:var(--ink3)}}
.kpi .v{{font-family:"IBM Plex Mono",monospace;font-size:24px;font-weight:500;font-variant-numeric:tabular-nums}}
.kpi .s{{font-size:12px;color:var(--ink2)}}
.chart{{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:16px;position:relative}}
.chart svg{{width:100%;height:auto;display:block}}
.legend{{display:flex;flex-wrap:wrap;gap:6px 16px;margin:8px 0 0;font-size:12.5px;color:var(--ink2)}}
.legend label{{display:inline-flex;align-items:center;gap:6px;cursor:pointer}}
.legend i{{display:inline-block;width:18px;height:0;border-top:2px solid var(--c)}}
.legend i.dash{{border-top-style:dashed}}
.tip{{position:absolute;pointer-events:none;background:var(--surface);border:1px solid var(--line);border-radius:4px;padding:8px 10px;font-size:12px;
 font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;box-shadow:0 2px 8px rgba(0,0,0,.12);display:none;z-index:2;white-space:nowrap}}
.tbl{{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:6px}}
table{{border-collapse:collapse;width:100%;font-size:13.5px}}
th,td{{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{font-weight:500;color:var(--ink3);font-size:12px;letter-spacing:.04em;white-space:nowrap}}
td.num,th.num{{text-align:right;font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;white-space:nowrap}}
td.pos{{color:var(--pos)}} td.neg{{color:var(--neg)}}
td.note{{color:var(--ink2);font-size:12.5px}}
tr:last-child td{{border-bottom:0}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle}}
.grid3{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-bottom:16px}}
h3{{font-size:14px;font-weight:500;color:var(--ink2);margin:0 0 8px}}
.caveat{{border-left:3px solid var(--accent);padding:4px 16px;color:var(--ink2);max-width:74ch}}
.caveat li{{margin:4px 0}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
</style>
<main>
<header>
<div class="eyebrow">NCKU 回測框架 · 2026-01-02 → 2026-09-10 · 訓練資料 ≤ 2025-12-31 · 本金 100 萬</div>
<h1>2026 台股回測對照</h1>
<p class="lede">三套自有方法全部套進老師發的 <code>stock_backtest_v1</code> 框架:同一份證交所官方日資料(未還原權息)、同一套成交規則(委託價在當日高低之間即成交、無手續費證交稅)、同一個績效算法(期末現金 + 持股市值)。所有模型只用 2025 年底以前的資料訓練,2026 年是真正的樣本外。統一口徑:t 日收盤後產生訊號,t+1 日開盤價下單。</p>
</header>
<section class="kpis" id="kpis"></section>
<section class="chart">
<h2>框架每日總資產(相對本金)</h2>
<svg id="c1" viewBox="0 0 1080 420" role="img" aria-label="累積報酬曲線"></svg>
<div class="legend" id="l1"></div><div class="tip" id="t1"></div>
</section>
<section>
<h2>框架回測結果(全部策略)</h2>
<div class="tbl"><table><thead><tr><th>系統</th><th>設定</th><th>執行規則</th><th class="num">總收益率</th><th class="num">MDD</th><th class="num">日 Sharpe</th><th class="num">成交委託</th><th class="num">來回</th><th class="num">勝率</th><th class="num">已實現</th><th class="num">未實現</th></tr></thead>
<tbody>{rows_html}</tbody></table></div>
</section>
{phase_html}
{ladder_html}
{opt_html}
{logic2_html}
{logic_html}
<section>
<h2>對照:自算口徑(yfinance 還原價,扣一趟 0.585% 成本)</h2>
<div class="tbl"><table><thead><tr><th>設定</th><th class="num">前 10% 純多頭 淨</th><th class="num">t</th><th class="num">H-L 多空 淨</th><th class="num">t</th><th class="num">AUC</th></tr></thead>
<tbody>{cross_html}</tbody></table></div>
</section>
<section class="caveat">
<h2>怎麼讀</h2>
<ul>
<li>2026 年 1 到 9 月是大多頭,0050 在框架裡買進持有就有六成。任何純多頭策略先跟這條比。</li>
<li>框架<b>不扣任何成本</b>,所以換股越頻繁的設定(h=1 每日換)在這裡會被高估;下面自算口徑扣了 0.585% 一趟,h=1 在那裡淨值是負的。兩張表一起看才完整。</li>
<li>框架用未還原權息的官方價,除息日持股會憑空掉價;基準和策略都吃到同樣的影響,互相比較仍公平,但絕對數字比 yfinance 還原價低幾個百分點。</li>
<li>「來回」= 成功賣出的筆數;「勝率」= 已實現交易獲利為正的比例(框架 xlsx 的歷史已實現損益表)。</li>
<li>Chart-GCN 在 2024 的否證鏈結論是「無訊號」;這裡看到的任何正報酬都要對照它的排名是否退化(機率標準差)再判斷。</li>
<li><b>2024 最佳設定 e6c 在 2026 重現了,但只在多空版本</b>:tw200、h=20、含籌碼、沿用 2024 選出的 20 欄原封重訓,2026 多空 H-L 扣成本 +45.6%(t 2.52,隨機零分佈 99.5 百分位),2024 是 +30%(t 2.9)。全 283 欄版 +62.6%(t 2.67)。訊號跨年站得住,但主要來自「避開後段班」,框架不能放空,純做多只拿到 +47.8%,和同池等權 +45.2% 差不多。只有 8 個月期,t 值的自由度很小。</li>
<li><b>為什麼是 tw50、每 5 日</b>:9 個股票池裡 tw50 扣成本後第一(+234%),第二名電子 46 檔(每日 v2 +158%)。每日檢視在 tw50 最好只有 +119%,因為換手成本每年多吃 10 到 20 個百分點,而且模型預測的是 5 日報酬,每天重排會追到雜訊。K=5 對 K=8 差了 100 個百分點,代表 2026 的超額報酬高度集中在少數強勢股(南電 8046、國巨 2327、南亞 1303 等),這是這套系統最大的風險來源。</li>
<li><b>最終系統(v2)</b>:在 192 組裡挑「流動性、大盤、汰弱留強都開、有停損停利」中 Sharpe 最高的。相對於只有模型(+257%),總收益少 10 個百分點但 MDD 從 -17.7% 降到 -10.4%、Sharpe 4.26 → 4.94、平均持股比 79%(大盤弱時 17 次擋下買單、空手等)。三個機制的個別效果:流動性在 tw50 幾乎不觸發(全是大型股,留著是為了之後換大池);大盤濾網在大多頭年一律少賺、但都把 MDD 壓到 -15% 以下;汰弱留強「前 10 名續抱」是唯一單獨就加分的(+252% → +292%,續抱 83 次,勝率 61% → 65%),前 15、20 名就太鬆。</li>
<li><b>v1 邏輯層的選法</b>:先在 12 個模型設定裡挑框架與自算兩種口徑都第一的 XGB tw50 h=5 permpos,再在 180 組交易邏輯網格裡挑「停損與停利都有設」的最高者。180 組裡挑最好一定有選擇偏誤:邏輯層對總收益的貢獻只有 +23 個百分點(其中 +23 來自排除出貨型過濾,停損停利本身接近 0),真正的價值是 3×ATR 與 30% 兩道很寬的防線一年只各觸發 4 到 5 次,不干擾 5 日持有、只擋極端事件。任何緊一點的停損(5% 到 15%、移動停損)在 2026 都是扣分,因為 5 日持有的正常波動就會被掃到。</li>
<li>每個策略的框架原生 Excel(5 張表:績效、已實現、委託、每日資產、委託歷史)都在 <code>backtest_2026/ncku/out/</code>。</li>
</ul>
</section>
</main>
<script>
const DATES={json.dumps(dates)}, S={json.dumps(series)}, LAB={json.dumps(labels, ensure_ascii=False)}, SYS={json.dumps(sysof, ensure_ascii=False)}, NC={json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'curve'} for k, v in NC.items()}, ensure_ascii=False)};
const HEAD={json.dumps([k for k in HEADLINE if k in NC])};
const SYSC={json.dumps(SYS_COLOR, ensure_ascii=False)};
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const SHADES={{"XGB 老師的方法":["--s1","--s7","--s5","--s4"],"KLINE 系統 A":["--s2","--s4","--s5"],"Chart-GCN 系統 B":["--s3","--s7","--s4"],"基準":["--bench","--bench"]}};
function colorMap(keys){{ const cnt={{}}; const m={{}}; keys.forEach(k=>{{ const s=SYS[k]; const i=cnt[s]||0; cnt[s]=i+1; m[k]=css((SHADES[s]||["--ink3"])[i%(SHADES[s]||["--ink3"]).length]); }}); return m; }}
let visible=new Set(HEAD);
function draw(){{
  const svg=document.getElementById("c1"), W=1080, H=420, m={{t:18,r:190,b:34,l:56}}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const keys=Object.keys(S), col=colorMap(keys), on=keys.filter(k=>visible.has(k)), n=DATES.length;
  let lo=0,hi=0; on.forEach(k=>S[k].forEach(v=>{{lo=Math.min(lo,v);hi=Math.max(hi,v);}})); const pad=(hi-lo)*0.06||1; lo-=pad; hi+=pad;
  const x=i=>m.l+i/(n-1)*iw, y=v=>m.t+(hi-v)/(hi-lo)*ih;
  const mag=Math.pow(10,Math.floor(Math.log10(hi-lo))), step=(hi-lo)/mag>5?mag:mag/2;
  let g="";
  for(let v=Math.ceil(lo/step)*step; v<=hi; v+=step){{ g+=`<line x1="${{m.l}}" x2="${{m.l+iw}}" y1="${{y(v)}}" y2="${{y(v)}}" stroke="${{css('--grid')}}"/>`;
    g+=`<text x="${{m.l-8}}" y="${{y(v)+4}}" text-anchor="end" font-size="11" fill="${{css('--ink3')}}" font-family="IBM Plex Mono,monospace">${{v>0?'+':''}}${{v.toFixed(0)}}%</text>`; }}
  g+=`<line x1="${{m.l}}" x2="${{m.l+iw}}" y1="${{y(0)}}" y2="${{y(0)}}" stroke="${{css('--ink3')}}" stroke-dasharray="2 3"/>`;
  const months={{}}; DATES.forEach((d,i)=>{{const k=d.slice(0,7); if(!(k in months)) months[k]=i;}});
  Object.entries(months).forEach(([k,i])=>{{ g+=`<text x="${{x(i)}}" y="${{H-12}}" text-anchor="middle" font-size="11" fill="${{css('--ink3')}}" font-family="IBM Plex Mono,monospace">${{k.slice(5)}}月</text>`; }});
  let paths="", labs=[];
  on.forEach(k=>{{ const s=S[k]; const b=SYS[k]==="基準"; const d=s.map((v,i)=>(i?"L":"M")+x(i).toFixed(1)+" "+y(v).toFixed(1)).join("");
    paths+=`<path d="${{d}}" fill="none" stroke="${{col[k]}}" stroke-width="${{b?1.5:2}}" ${{b?'stroke-dasharray="5 4"':''}} stroke-linejoin="round"/>`;
    paths+=`<circle cx="${{x(n-1)}}" cy="${{y(s[n-1])}}" r="3.5" fill="${{col[k]}}" stroke="${{css('--surface')}}" stroke-width="2"/>`;
    labs.push({{k,yv:y(s[n-1]),v:s[n-1]}}); }});
  labs.sort((a,b)=>a.yv-b.yv); for(let i=1;i<labs.length;i++) if(labs[i].yv-labs[i-1].yv<14) labs[i].yv=labs[i-1].yv+14;
  let lab=""; labs.forEach(l=>{{ const t=LAB[l.k]; lab+=`<text x="${{m.l+iw+8}}" y="${{l.yv+4}}" font-size="11.5" fill="${{css('--ink2')}}" font-family="IBM Plex Mono,monospace">${{l.v>0?'+':''}}${{l.v.toFixed(1)}}% <tspan fill="${{css('--ink3')}}" font-family="Noto Sans TC,sans-serif" font-size="10.5">${{t.length>16?t.slice(0,15)+'…':t}}</tspan></text>`; }});
  svg.innerHTML=g+paths+lab+`<line id="xl" y1="${{m.t}}" y2="${{m.t+ih}}" stroke="${{css('--ink3')}}" style="display:none"/><rect x="${{m.l}}" y="${{m.t}}" width="${{iw}}" height="${{ih}}" fill="transparent"/>`;
  document.getElementById("l1").innerHTML=keys.map(k=>`<label><input type="checkbox" id="cb_${{k}}" ${{visible.has(k)?'checked':''}} data-k="${{k}}" style="margin:0"><i class="${{SYS[k]==='基準'?'dash':''}}" style="--c:${{col[k]}}"></i>${{LAB[k]}}</label>`).join("");
  document.querySelectorAll("#l1 input").forEach(cb=>cb.addEventListener("change",e=>{{ const k=e.target.dataset.k; if(e.target.checked) visible.add(k); else visible.delete(k); draw(); }}));
  const tip=document.getElementById("t1"), xl=document.getElementById("xl");
  svg.onmousemove=e=>{{ const r=svg.getBoundingClientRect(); const px=(e.clientX-r.left)/r.width*W; const i=Math.max(0,Math.min(n-1,Math.round((px-m.l)/iw*(n-1))));
    xl.setAttribute("x1",x(i)); xl.setAttribute("x2",x(i)); xl.style.display="";
    tip.style.display="block"; tip.innerHTML=`<b>${{DATES[i]}}</b><br>`+on.map(k=>`<span style="color:${{col[k]}}">■</span> ${{LAB[k]}} <b>${{S[k][i]>0?'+':''}}${{S[k][i].toFixed(1)}}%</b>`).join("<br>");
    const pr=svg.parentElement.getBoundingClientRect(); const tx=e.clientX-pr.left+14, ty=e.clientY-pr.top+10; tip.style.left=(tx+tip.offsetWidth>pr.width?tx-tip.offsetWidth-28:tx)+"px"; tip.style.top=ty+"px"; }};
  svg.onmouseleave=()=>{{tip.style.display="none"; xl.style.display="none";}};
}}
function kpis(){{ const el=document.getElementById("kpis"); el.innerHTML=HEAD.map(k=>{{ const r=NC[k]; return `<div class="kpi" style="--c:var(${{SYSC[SYS[k]]}})"><div class="l">${{SYS[k]}}</div><div class="v" style="color:${{r.total_return_pct>0?'var(--pos)':'var(--neg)'}}">${{r.total_return_pct>0?'+':''}}${{r.total_return_pct.toFixed(1)}}%</div><div class="s">${{LAB[k]}} · MDD ${{r.max_dd_pct}}%</div></div>`; }}).join(""); }}
kpis(); draw(); matchMedia("(prefers-color-scheme: dark)").addEventListener("change",draw); new MutationObserver(draw).observe(document.documentElement,{{attributes:true,attributeFilter:["data-theme"]}});
</script>
"""
open(os.path.join(RES, "report_2026.html"), "w", encoding="utf-8").write(html)
print("[SAVED] results/report_2026.html", len(html) // 1024, "KB;", len(keys), "策略")
