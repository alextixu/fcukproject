# Chart GCN 復現/否證專題 — 第三方稽核報告(僅列記錄中「尚未寫到」的缺失)

稽核範圍:`c:\Users\alex\Desktop\專題進度\chartgcn`(唯讀;未執行任何腳本)。
已讀:`實驗記錄_論文對齊.md` 全章節標題 + §一~六、§七、§八、§十一~十八 全文;`core/*.py` 全部;`test/run_paper_repro.py`、`grid_search_paper.py`、`event_data.py`、`run_event_experiment.py`、`run_cnn_baseline.py`;`analysis/repr_knn.py`、`decile_ls.py`、`block_bootstrap.py`;`backtest.py`、`README.md`;`analysis/output/*.json`;`experiments_paper/*.json`(73 筆 EXP + 6 筆 CNN);論文純文字檔 §3.2、§4.1、§4.3、§6.3。

---

## (1) 總評

資料層與切分層的「洩漏」問題基本上已被專案自己抓完(z-score 統計量、標籤邊界、warm-up、min_date、PIP 只看窗內、指標因果性:我逐行複核後**全部無新發現**);記錄裡 P1~P4 與 §三 的 10 項也涵蓋了絕大多數程式層缺陷。**剩下會被口試委員攻擊的,不在「有沒有洩漏」,而在「否證的統計效力與論述一致性」**:(a) 全部結論建立在**單一測試年 2024**(台股大多頭年)上,沒有任何 walk-forward;(b) 記錄從未寫出最小可偵測效應(MDE ≈ 2.5pp),因此「0/24 顯著」無法區分「無訊號」與「檢定力不足」,h=20 只有 12 期更是零效力;(c) §18.4 的關鍵論點「全押同一邊時 H-L 恆為 0、無法被退化解欺騙」**與程式碼行為相反**——`np.argsort(kind="stable")` 在機率近乎常數時會依股票代碼順序分組,`h5-elec_all-s44`(prob_std 0.0008)因此得到 H-L +10.76%;(d) §16.1 說「PIP→VG→子圖破壞了原始序列中本來存在的成分」,§17.4 判定「原始序列本來就沒有訊號」,兩章互相矛盾,而 §16.1 的 CNN +1.2~1.7pp 從未做過 bootstrap CI(以 n_eff≈1,600 估算約 1σ);(e) 現行乾淨協定(date 批次)下**從未跑過 no-attention 對照**(僅有的 2 個 no-attention run 是 2026-07-21 paper 批次時期),而 §18 十分位檢定所用的機率全部經過「跨股票 attention 混合」,因此「輸出機率不含橫斷面排序資訊」這句話,無法歸因到表示法還是 attention。其餘為文件與程式數字不符(ka/kv、參數量)、已知 bug 未修、股票池存活偏誤未聲明等中低度問題。

---

## (2) 稽核清單判定表

| 編號 | 項目 | 判定 | 檔案:行 | 說明 |
|---|---|---|---|---|
| 1a | z-score 統計量來源 | 已記錄 | `core/indicators.py:90-95`、`core/dataset.py:81-84`、`test/run_paper_repro.py:199-213` | 訓練期全期統計(in-sample,§三 low);測試注入訓練統計;現行標準協定 `--raw-features` → `stats=(0.0,1.0)` 完全不正規化。無新問題。 |
| 1b | PIP / VG 只用窗內資料 | 無問題 | `core/dataset.py:115-116`(`close_by_tk[ticker][start:end]`)、`core/pip_algorithm.py:44-46` | 只切 `[start, end)`,決策日 = `end-1`,無未來列。 |
| 1c | 指標 lookahead / warm-up 跨界 | 已記錄 | `core/indicators.py:37-80`;`core/dataset.py:198-203` | 9 指標皆 rolling/shift/ewm 因果;測試段 EMA 自 warm-up 起點重算(§三 low)。無新問題。 |
| 2a | 2024 測試嚴格晚於訓練 | 無問題 | `core/dataset.py:197`(`df[df.index <= train_end]`)、`:89`(`range(window, len(df)-horizon)`)、`:96`(`close[end-1+horizon]`) | 訓練標籤最遠到 `close[len(df)-2]`,仍在 2023 內;h>1 由 `derive_horizon_ds` 以截斷 df 重算(`run_paper_repro.py:94`),同樣不越界。 |
| 2b | 測試首樣本回溯 2023 / 決策日過濾 | 無問題 | `core/dataset.py:93-95`(`decision_date <= min_date → continue`);`run_paper_repro.py:167-168`(`warmup_rows=2*window`) | 輸入窗回溯 2023 屬合法;決策日 > 2023-12-31。 |
| 3a | checkpoint 選擇 | 無問題 | `core/train.py:159-164, 174-176` | 每 epoch val macro-F1 取最佳;test 只在最後評一次。邊角:`best_val_score = 0.0`(`:152`)若 val F1m 全為 0 會靜默用最後 epoch,實務不會發生。 |
| 3b | val 是否等於 test | 無問題 | `run_paper_repro.py:236-241`、`grid_search_paper.py:84-91, 117, 138` | val 來自 train 內部;網格只以 `val_f1_macro` 選參。random split 汙染屬 P4(已記錄)。 |
| 3c | 超參數是否用 2024 選 | 無問題 / 疑慮 | `grid_search_paper.py:36-37, 117, 138` | 網格以 val 選,但**單一 seed=42、stride 5、15 epochs**,val F1m 0.47–0.53 為噪音帶(記錄 §六 已承認)。注意 `decile_ls.py:184` 預設名單中的 `gridbest-s43` 是 **2026-07-21 paper 批次舊 run**(w130/m60/N20/g3),與 `gridbest-date-s43` 同名易混淆(見 Top-6)。 |
| 4 | 類別不平衡 / 退化解守衛 | 已記錄 / 疑慮 | `core/train.py:150`(`nn.CrossEntropyLoss()` 無權重)、`:92-100`(回傳 rec_1/rec_0) | 無 class weight、無自動守衛;記錄以「預測漲%」人工標註塌縮。**新疑慮**:十分位分析沒有以 `prob_std` 做守衛(見 Top-1)。 |
| 5 | 多 seed 與 seed 挑選 | 無問題 / 疑慮 | 73 筆 EXP JSON:date/random 45、paper/random 14、date/time 12、paper/no-attn 2 | gridbest 三 seed 全數報告,無 seed hacking。**疑慮**:§18 的 8 組模型挑選規則未寫(w60-elec_all 只取 F1m 最佳的 s43;sector-date-elec455 只有 s42)。 |
| 6a | k-NN 鄰居池是否只含訓練期 | 無問題 | `analysis/repr_knn.py:72-76, 131-132, 287-289` | 庫 = 2016–2023 事件樣本、查詢 = 2024;`knn_similarity.json` 的 `same_ticker_adjacent5d_pct = 0.0` 佐證無同檔相鄰日鄰居。 |
| 6b | k-NN 設計弱點 | 疑慮 | `repr_knn.py:72-76`(庫 50,395 / 736,530 = 6.8%)、`:209`(`n_perm=20`)、`:213`(k 偶數平手判 0) | 「最像的歷史圖形」只在**事件日子庫**中找;日曆全庫從未搜過(§13.4 的日曆對照只有 10 萬/1 萬抽樣)。3σ 門檻的 σ 由 20 次置換估計,相對誤差約 16%。 |
| 7a | 十分位報酬起算點 | 疑慮(僅回測有記錄) | `analysis/decile_ls.py:84-88`(`c[j+h]/c[j]`,j = 決策日) | 訊號用決策日收盤、報酬也自決策日收盤起算 = 同收盤成交假設,且零成本。§7.1-6 只對 backtest 記過,§18 未聲明。 |
| 7b | 平手排序 | **問題** | `decile_ls.py:102`(`np.argsort(p, kind="stable")`) | 機率近常數時分位 = 股票代碼字母序 → H-L ≠ 0(Top-1)。 |
| 7c | t 統計 / 年化 / 基準 | 疑慮 | `decile_ls.py:111-118`(plain t、`TDAYS=246`)、`:106`(基準 = 當日樣本等權) | 非重疊持有期下 plain t 可接受,但 h=20 只有 12 期(df=11)、tw50 每分位僅 5 檔;「H-L 年化報酬 > 等權買進持有」是**零成本多空 vs 純多頭**的不對等比較(JSON 已有 `hl_sharpe` 0.87 vs `bench_sharpe` 1.0 卻未採用)。 |
| 8 | 復現忠實度 | 已記錄 / 疑慮 | 論文 txt `:706-712`(2010–2017 train/val、2018 test、隨機 80/20)、`:719-721`(Eq.11)、`:726-741`(網格、wd 5e-5、batch 128、F1=84/F2=32)、`:570-572`(「between S samples」)、`:545-546`(「typical configuration」) | 記錄 §六 已逐條對齊。**未記錄的缺口**:(i) **CSI-300**(論文第二資料集,543k 訓練樣本)從未復現,只做 SZ-50;(ii) 論文 §6.3 另有 rb2010 期貨分鐘資料驗證(`:930-935`),未觸及(可合理不做,但應聲明);(iii) SZ-50 成分股快照日不明(`data_loader.py:145-146` 有註)。 |
| 9a | 文件 vs 程式數字 | **問題** | `core/model.py:60-61`(`ka = 32`, `kv = 32`)vs `README.md:105`、記錄 `:181, :193`(「ka=kv=16」);記錄 `:1581`(「38,130 參數」) | 38,130 是 N=15/g=5 的數字;§17.6 對照的 evC/evD 為 N=10/g=4 → 28,476(evD 含 extra_dim=2 → 28,644)。 |
| 9b | 已記錄但未修的 bug | 疑慮 | `core/data_loader.py:379, 407`(`df.index < t_end`,缺 12-31)、`:350`(`dropna()` 未濾 volume=0)、`core/dataset.py:89`(off-by-one)、`core/pip_algorithm.py:44-45`(尺度混算) | §五第 3 點列為「修正優先序」,之後 60+ 個 run 仍帶著這些 bug 跑。委員會問:為何知道卻不修? |
| 9c | 靜默例外 | 疑慮 | `core/dataset.py:35-36`(`except Exception: return None`) | 失敗樣本數 `total - n_ok` 從未印出/存檔,無法排除特定股票系統性失敗。 |
| 9d | 硬編碼 | 疑慮 | `decile_ls.py:40, 184-186`;`block_bootstrap.py:17-19`(寫死 elec_all 快取路徑) | 分析腳本綁死特定實驗,無法直接套用到 CNN 或其他 run。 |
| 10 | 可補實驗與現成腳本 | — | `run_paper_repro.py:138-139`(`--no-attention`)、`:117-119`(`--train-end/--end`) | attention-off 與 walk-forward 都**不需新程式**;決策見 §(4)。 |

---

## (3) 依嚴重度排序的 Top 8 新缺失

### 1.【問題|高】§18.4「全押同一邊時 H-L 恆為 0」與程式行為相反 — 退化模型的十分位是「代碼字母序」

**證據**
```python
# analysis/decile_ls.py:101-105
p, r = probs[m], rets[m]
order = np.argsort(p, kind="stable")
edges = np.linspace(0, len(p), n_dec + 1).astype(int)
per = [float(r[order[edges[k]:edges[k + 1]]].mean()) for k in range(n_dec)]
```
`ds.meta` 依 (決策日, ticker) 排序(`core/dataset.py:100`),`m` 是布林遮罩 → 同日樣本的原始順序就是 ticker 字母序;`kind="stable"` 在機率相等/幾乎相等時保留該順序 → 第 1 分位 = 代碼最小的 10%、第 10 分位 = 代碼最大的 10%。

`analysis/output/decile_ls.json`:`h5-elec_all-s44` 的 `prob_std = 0.0008`(全押跌,F1m 34.04),h=1 的 H-L 卻是 **+10.76%**(t=0.83)、h=20 +8.93%;`gridbest-date-s42`(prob_std 0.032、F1_1 7.2%)H-L +4.95%。記錄 `:1634` 與 `十分位多空_講稿.md:129` 都寫「全押同一邊的話 H-L 恆等於 0,騙不了」,這句話在口試會被當場推翻。

**影響**:不動搖「無訊號」結論(這些 H-L 也不顯著),但 §18 宣稱的「協定不可被退化解欺騙」是錯的;且 24 個組合裡至少 2~3 個的十分位曲線其實是噪音排序。

**建議修法**:(a) `decile_ls.py` 對每個再平衡日檢查 `np.unique(p).size` 與 `p.std()`,低於門檻(如 std < 0.01 或唯一值 < n_dec)即跳過該日並統計跳過率;(b) 平手改隨機打散(`rng.permutation` 後再 stable sort);(c) 加一組「隨機機率」對照跑 200 次,得到 H-L 與 ρ 的**零假設分佈**,把 24 組結果畫在上面;(d) 改寫 §18.4 第 2 點。

### 2.【疑慮|高】全部否證只有單一測試年(2024 大多頭),沒有 walk-forward

**證據**:73 筆 EXP JSON 的 `params.train_end` 全為 `2023-12-31`、`end` 全為 `2024-12-31`;記錄 grep 「walk / 滾動 / 2023 測試」零筆。`decile_ls.json` 基準等權買進持有 +19.6%(elec455)。論文自身用 2018(A 股空頭年,txt `:930-931`「even when the market exhibited a downturn in 2018」)。

**委員會的攻擊**:「你只在一個多頭年上得到 null;技術型態訊號常在空頭/震盪年才顯現(論文自己也是在空頭年報告最好結果)。」另外 `§12.4` 的 n_eff ≈ 1,599 是**一年**的有效樣本;多一年就多一倍效力。

**建議修法**:用現成參數做 3~4 折 walk-forward:`--train-end 2020-12-31 --end 2021-12-31`、`…2021/2022`、`…2022/2023`、`…2023/2024`(tw50 或 elec_liq200,每折 3 seed,date 批次)。dscache key 含日期(`run_paper_repro.py:174-178`)會自動另建。把 4 年 × 十分位 ρ / H-L 合併做 pooled t,效力提升約 2 倍。

### 3.【疑慮|高】從未陳述最小可偵測效應(MDE);「0/24 顯著」在 h=20(12 期)與 tw50(每分位 5 檔)幾乎零效力

**證據**:§12.4 給了 CI [48.81, 53.71](半寬 2.45pp)但未換算成 MDE。`decile_ls.json`:所有 h=20 的 `n_periods = 12`(t 的 df = 11,|t|≥2 需要年化 H-L 超過約 2 倍年化波動);tw50 三組 `stocks_per_date = 50` → 每分位 5 檔,`gridbest-s43` h=1 分位報酬 −15.6/−17.7/+48.6/+30.9…,純粹是 5 檔平均的抽樣噪音。§18.2 的門檻「|ρ| ≥ 0.65」在 n=10 上對應 p≈0.04,但單年 h=1 的分位年化報酬 SE 本身就 ±10pp 等級。

**影響**:專題可以強力否證「69.26%」(距 CI 上界 15pp),但**不能**主張「無任何訊號」——只能主張「訊號 < 2.5pp(Acc)/ 十分位 H-L 未達單年可偵測水準」。現在的措辭(§16.3「十維全 ✗」、§17.5「三者皆 = 隨機」)是把「未檢出」寫成「不存在」。

**建議修法**:在 §12.4 後補一段「效力分析」:Acc 的 MDE(95%,雙尾)= 1.96 × 1.25pp ≈ 2.5pp;十分位 H-L 的 MDE 用每期 H-L 標準差 × 1.96/√n_periods 算出(h=1 約 ±13% 年化、h=20 約 ±40%);結論改寫為「效應若存在,其大小 < MDE」。h=20 與 tw50 的十分位結果應標註「效力不足,僅供參考」。

### 4.【問題|中高】§16.1 與 §17.4 互相矛盾;CNN +1.2~1.7pp 從未做 CI(約 1σ)

**證據**:記錄 `§16.1` 第 3 點:「PIP→VG→子圖 的壓縮過程**破壞了原始序列中本來存在的成分**」;`§17.4`:「判定:情況乙 … **原始序列裡本來就沒有可被 PIP+VG 破壞的東西**」。兩段相隔一天、結論相反,且 §17.5 只用一句「表示法不是瓶頸」帶過。

CNN 六筆 JSON(`experiments_paper/CNN-*.json`)只有點估計、無 CI 欄位;`analysis/block_bootstrap.py:14-19` 寫死讀 `span_vs_perf.npz` 與 elec_all 快取,無法直接套用 CNN。h=5 三 seed 53.29/52.84/53.21% vs floor 51.62%,gap = +1.67/+1.22/+1.59pp;以 §12.4 同量級 n_eff(103,447 樣本、SE 膨脹 8×)估 SE ≈ 1.25pp → **每個 seed 約 1.0~1.3σ**,不顯著。

**建議修法**:(a) 把 CNN 的 test 預測存下來(`run_cnn_baseline.py:105-123` `evaluate` 只回指標),對 CNN 跑同一套日期區塊 bootstrap;(b) §16.1 第 2、3 點改為「CNN h=5 高於 floor 但未達顯著(CI 含 0)」;(c) 在 §17.5 明確寫「本節結果修正 §16.1 第 3 點」。

### 5.【疑慮|中高】乾淨協定下沒有 no-attention 對照,§18 的機率全經跨股 attention 混合

**證據**:73 筆 EXP 中 `no_attention=True` 僅 2 筆(`EXP-20260721-045427_noattn-raw`、`…045535_noattn-zscore`),皆 `batch_mode='paper'`(舊洩漏協定,附錄 A)。`core/model.py:164-165`:
```python
attn = F.softmax(Q @ K.T, dim=-1)    # Eq.(8)(9): 無縮放
Va = attn @ V                        # Va = α · V(l), 無殘差
```
無殘差 → 每檔的分類輸入是同日其他股票 V 的凸組合;P1 實測 attention 近 one-hot(winner mass 0.9997)→ 多檔股票共用同一個 winner 的 V → 機率近乎相同(這也是 Top-1 平手的來源)。`decile_ls.py:55-70` 推論時同樣經過 attention。

**影響**:§18「輸出機率不含橫斷面排序資訊」目前**無法歸因**:是子圖表示法沒有訊號,還是 attention 把橫斷面差異抹平?後者是論文 Eq.7-9 自身的缺陷,前者才是表示法的問題。§17 k-NN 是繞過模型的旁證,但不是模型層的對照。

**建議修法**:`python test/run_paper_repro.py --raw-features --batch-mode date --tickers elec_all --window 140 --m-pips 80 --N 10 --g 4 --no-attention --seed 42/43/44 --tag noattn-date-elec-sXX`(dscache 已存在,只需訓練 ~10 分鐘/run),再把三個 tag 加進 `decile_ls.py --exps` 重跑。若 no-attention 的 prob_std 明顯變大而 ρ/H-L 仍為 0,才能說「表示法無橫斷面訊號」。

### 6.【問題|中】§18 的 8 組模型含一個洩漏協定模型,且挑選規則未寫

**證據**:`decile_ls.py:184-186` 預設 `--exps` 含 `gridbest-s43`;`experiments_paper/EXP-20260721-060137_gridbest-s43.json` → `batch_mode: "paper"`, window 130 / m 60 / N 20 / g 3(7/21 舊網格),`predict_proba` 在 paper 模式用連續 128 筆(`decile_ls.py:61-64`),即 P1 描述的「t+1 樣本混入同批」洩漏路徑。§18 只寫「8 組已訓練模型(含不同…批次模式…)」,未說明為何選這 8 組、為何 `w60-elec_all` 只取 s43(該池 F1m 最佳者)、`sector-date-elec455` 只有單 seed。

**影響**:混入洩漏模型仍得 null,對否證方向是「保守」的;但與 §6.1「日後所有論文對齊實驗一律 date」自相矛盾,且名稱與 `gridbest-date-s43` 撞名,讀者會誤以為是乾淨協定。

**建議修法**:從 §18 剔除 `gridbest-s43`(或改標「paper 批次,含 P1 洩漏,僅作上界」);寫明挑選規則(例如「每個設定取全部 seed」),補跑 `w60-elec_all` s42/s44 與 `sector-date-elec455` s43/s44 的十分位。

### 7.【疑慮|中】股票池存活偏誤未聲明

**證據**:`core/data_loader.py:36`「台灣 50 ETF 成分股 (完整清單)」= 現今成分股套用到 2016–2024;`:454`「2026-07-25 自 TWSE ISIN 產生」;記錄 `:567`「已剔除 6 檔下市」。全部池子都是 **2026 年仍上市**的公司回推 8 年。記錄 grep「存活 / survivorship」零筆。

**影響**:對 null 結論方向偏「有利於模型」(存活者漂移向上、型態較乾淨),所以不推翻否證;但 (a) 等權基準 +19.6%、(b) 2024 跌類先驗 55%(多頭年卻偏跌,部分來自 volume=0 假 bar 與平盤=跌)、(c) 十分位各分位 +8~+32% 這些「絕對數字」都被存活偏誤墊高,委員會一定會問。

**建議修法**:限制段落明寫「成分股為 2026 快照,存在 look-ahead/survivorship,方向上有利模型」;若要根治,用 TWSE 歷年成分股或以「訓練期首日已上市」為條件重建池子。

### 8.【問題|低中】文件與程式數字不符 + 已知 bug 未修

**證據**
```python
# core/model.py:60-61 (paper_exact=True)
ka = 32 if ka is None else ka
kv = 32 if kv is None else kv
```
vs `README.md:105`「`ka=kv=16` 論文未給」、記錄 `:181`「6/16/120、16/16」、`:193`「ka=kv=16」、`paper_analysis.md:135`「16/16 是我們的假設」。

記錄 `:1581`「**38,130 參數**、30 epochs、含 self-attention 的模型」:38,130 = N=15/g=5(conv3 = 16×120×11);§17.6 對照的 evC/evD 用 elec_all dscache(w140m80**N10g4**)→ 28,476;evD 含 `extra_dim=2` → 28,644。

已知未修:`data_loader.py:379/407` `df.index < t_end`(缺 2024-12-31)、`:350` 未濾 volume=0 假 bar(3,400+ 樣本必為跌)、`dataset.py:89` off-by-one、`pip_algorithm.py:44-45` 天數+價格混算。§五第 3 點列為修正順序 (b)(c)(d),但其後 §八~§十八 的 60+ run 全部帶 bug 執行。

**建議修法**:統一 ka/kv 敘述為 32(或把程式改 16 並註明歷史 run 用 32);§17.6 改為 28,476/28,644;在限制段落列出「四項已知資料層 bug 未修,對結論方向的影響:假 bar 使跌類先驗 +0.4pp、缺 12-31 少 1 日、off-by-one 每檔少 1 筆、PIP 尺度使跨股 importance 語意不一致——皆不足以產生 15pp 差距」。

---

### 其他中低度新發現(未進 Top 8)

- **k-NN 庫只含事件日**(`repr_knn.py:72-76`;50,395 / 736,530 = 6.8%):「找最像的歷史圖形」在只有 7% 的歷史裡找;`adjacent_distance.json` 顯示第 1 近鄰距離中位 14.2 vs 隨機配對 26.7,鄰居其實不算「像」。§13.4 的日曆對照僅 10 萬/1 萬抽樣。建議至少對 elec_liq200 做全庫(brute force 740k×105k×360 維在 CPU 上約需分批或用 FAISS)。
- **事件實驗 val 切分**:`run_event_experiment.py:117-120` 對 triple-barrier(T=20)標籤仍用 `random_split` → val 樣本的 20 日標籤窗與 train 重疊,比 P4(h=1)嚴重 20 倍;§13.0 只寫「隨機 80/20 val」。影響有限(結果為 null),但應註明。
- **十分位零成本與同收盤成交**(`decile_ls.py:84-88`):h=1 每日全換手,台股一回合約 0.585%,年化成本 > 100%;§18 未聲明(§7.1-6 只對 backtest 記過)。
- **H-L vs 純多頭基準的比較不對等**(`decile_ls.py:114-116`、§18.2 第三列):應改用已存在 JSON 的 `hl_sharpe` vs `bench_sharpe`(elec455 h1:0.87 vs 1.0),或 H-L 對市場的 alpha。
- **失敗樣本數未報**(`dataset.py:35-36, 149-151`):`total - n_ok` 未印出、未寫入 JSON。
- **CSI-300 未復現**(論文 txt `:613-617, :734-735`):論文的第二資料集(543k 樣本)與「Chart GCN-2 在 CSI-300 表現平庸」的說法從未被檢驗;應在限制段落聲明。

---

## (4) 建議補做的實驗(依 C/P 值排序)

| # | 實驗 | 目的 | 現成腳本 | 成本 |
|---|---|---|---|---|
| A | **date 批次 no-attention 對照**:elec_all、w140/m80/N10/g4、seeds 42/43/44,並納入十分位 | 把 §18 的 null 歸因到「表示法」而非「attention 抹平橫斷面」(Top-5);同時檢驗 Top-1 的平手問題是否隨 attention 移除而消失 | `run_paper_repro.py --no-attention`(dscache 已存在)+ `decile_ls.py --exps` | 3 × ~10 分鐘訓練 |
| B | **Walk-forward 4 折**(測試年 2021/2022/2023/2024),tw50 或 elec_liq200,date 批次,3 seed | 回應「單一多頭年」(Top-2);pooled 效力 ×2;順便看 2022 空頭年 | `run_paper_repro.py --train-end/--end`(需重建 dscache,tw50 每折 ~5 分鐘、elec_liq200 ~20 分鐘) | 12 run |
| C | **十分位零假設分佈**:對每組模型以隨機機率 / 標籤置換各 200 次重算 ρ、H-L、t,畫出 24 組實測值落點 | 把 §18 從「0/24 通過門檻」升級為「落在零分佈第幾百分位」,並順手量化 Top-1 平手偽訊號的大小 | 改 `decile_ls.py`(加 `rng.random(len(p))` 分支) | 幾分鐘 |
| D | **CNN 區塊 bootstrap** | 消除 §16.1/§17 矛盾(Top-4) | 改 `run_cnn_baseline.py` 存預測 + 泛化 `block_bootstrap.py` | 半小時工程 |
| E | **逐日 Acc vs 當日市場報酬 / 波動**(用既有 elec455 預測) | 檢查訊號是否只在特定 regime 出現;呼應委員「多頭年」質疑 | `span_vs_perf.npz` 已有 y/pred,補一支 20 行腳本 | 幾分鐘 |
| F | **全庫 k-NN**(elec_liq200 日曆全庫 → 2024) | 補 §17 只在 7% 事件庫中搜尋的缺口 | `knn_similarity.py` 改 `cal_lib` 上限 | CPU 數小時 |

---

## (5) 需要跑實驗才能確認的事項

1. **Top-1 的實際汙染量**:24 組中有多少再平衡日的 `np.unique(p).size < 10` 或 `p.std() < 0.01`?只能重跑 `decile_ls.py` 加統計才知道;目前 JSON 只有整體 `prob_std`。
2. **移除 attention 後 prob_std 是否顯著上升、ρ/H-L 是否仍為 0**(實驗 A)。
3. **2022 空頭年是否出現任何 Acc > floor 或 |ρ| ≥ 0.65 的折**(實驗 B)——這是唯一可能翻轉「無訊號」敘事的實驗,也是委員最可能要求的。
4. **CNN h=5 的 bootstrap CI 是否含 0**(實驗 D);若不含 0,§17.4「情況乙」需重新判定為「甲/乙之間」。
5. **失敗樣本數**(`dataset.py` 的 `total - n_ok`)是否集中在特定股票(例如低價股 PIP 退化);需加 log 重建一次 tw50 dscache 才能確認。
6. **存活偏誤的量級**:需以歷史成分股或「2016 已上市且含 2024 前下市者」重建 elec_liq200,比較 floor 與等權基準的差異。
