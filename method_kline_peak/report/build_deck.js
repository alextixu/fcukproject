// TW50 局部高低點偵測 — 專題進度簡報(pptxgenjs,結構化:主題 + 版面 + 區段)
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const THEME = {
  name: "TW50 Turning Points",
  headFontFace: "Microsoft JhengHei",
  bodyFontFace: "Microsoft JhengHei",
  colors: {
    dk1: "13202A", lt1: "FFFFFF", dk2: "47545F", lt2: "EEF2F5",
    accent1: "EB6834",   // 高點
    accent2: "2A78D6",   // 低點
    accent3: "0CA30C",   // 判對
    accent4: "D03B3B",   // 判錯
    accent5: "7A8691",   // 次要文字
    accent6: "C9D2D9",   // 中性
    hlink: "2A78D6", folHlink: "6250D6",
  },
};
const HEX = THEME.colors;
const OUT = process.argv[2] || "TW50_局部高低點_專題進度.pptx";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";            // 13.33" × 7.5"
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "TW50 局部高低點偵測";
pres.author = "fcukproject";
const C = pres.SchemeColor;

// 版面上的「11 日窗口」記號:11 個小方塊,第 6 個是 t
const motif = (x0, y0, s, gap) => Array.from({ length: 11 }, (_, k) => ({
  rect: { x: x0 + k * (s + gap), y: y0, w: s, h: s, fill: { color: k === 5 ? C.accent1 : C.accent6 } },
}));

pres.defineSlideMaster({
  title: "DARK",
  background: { color: HEX.dk1 },
  objects: [
    ...motif(0.8, 1.55, 0.22, 0.07),
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.1, w: 11.7, h: 1.5, fontSize: 44, bold: true,
      color: C.background1, valign: "top", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.75, w: 11.7, h: 2.6, fontSize: 18,
      color: C.background2, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: HEX.lt1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    ...motif(11.1, 0.62, 0.11, 0.035),
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 10.3, h: 0.85, fontSize: 32, bold: true,
      color: C.text1, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "TW50 局部高低點偵測 · 專題進度 2026-10", options: { x: 0.6, y: 6.95, w: 6, h: 0.3, fontSize: 10,
      color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.25, y: 6.95, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent5, align: "right" },
});

const T = (slide, text, o) => slide.addText(text, { isTextBox: true, margin: 0, fontSize: 15, color: C.text1, valign: "top", ...o });
const card = (slide, x, y, w, h, fill, name) => slide.addShape(pres.shapes.ROUNDED_RECTANGLE,
  { x, y, w, h, fill: { color: fill || C.background2 }, line: { color: fill || C.background2 }, rectRadius: 0.08, objectName: name });
const bullets = (items, size = 15) => items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 8, fontSize: size } }));
const S = (title) => { pres.addSection({ title }); return title; };

// ───────────────────────── 1. 封面 ─────────────────────────
let sec = S("開場");
let s = pres.addSlide({ masterName: "DARK", sectionTitle: sec });
s.addText("TW50 局部高低點偵測", { placeholder: "title" });
s.addText([
  { text: "11 日窗口 · 論文標籤 + 規則候選 + AE + OC-SVM", options: { breakLine: true } },
  { text: " ", options: { breakLine: true, fontSize: 10 } },
  { text: "專題進度報告 · 2026-10-19", options: { fontSize: 15, color: C.accent6 } },
], { placeholder: "body" });
s.addNotes("今天報告我們把題目從「找 K 線型態預測漲跌」改成「找 11 天窗口裡的局部高點和低點」之後的結果。上面這排 11 個小方塊就是一個窗口,中間橘色那格是要判斷的那一天 t。");

// ───────────────────────── 2. 一頁看結果 ─────────────────────────
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("一頁看結果:真高低點不漏,判非極值很準", { placeholder: "title" });
const stats = [
  ["100%", C.accent1, "真高低點全部進候選", "測試期 1,470 個 11 日高點,規則一個都沒漏;低點 1,532 個找到 1,531 個(99.9%)"],
  ["94.5%", C.accent3, "判「不是高低點」時正確", "模型判非極值的 11,942 天裡,11,288 天真的不是高低點"],
  ["3.5–4.2×", C.accent2, "候選的命中率是亂猜的倍數", "隨機挑一天是高(低)點的機率只有 7.3%(7.6%);被挑出的候選是 25.7%(31.5%)"],
];
stats.forEach(([v, col, k, d], j) => {
  const x = 0.6 + j * 4.1;
  card(s, x, 1.6, 3.8, 3.7, C.background2, `stat-${j}`);
  T(s, v, { x: x + 0.3, y: 1.9, w: 3.3, h: 1.1, fontSize: 54, bold: true, color: col, valign: "middle" });
  T(s, k, { x: x + 0.3, y: 3.1, w: 3.3, h: 0.5, fontSize: 18, bold: true });
  T(s, d, { x: x + 0.3, y: 3.65, w: 3.3, h: 1.5, fontSize: 13, color: C.text2 });
});
T(s, "測試期 2025-01 ~ 2026-09,TW50 共 20,189 個股票日。限制:被挑出的候選中只有 25–32% 是真高低點,見第 13 頁。",
  { x: 0.6, y: 5.6, w: 12.1, h: 0.6, fontSize: 14, color: C.text2 });
s.addNotes("先講結論。第一,真正的 11 日高點我們一個都沒漏,低點也只漏一個。第二,模型說「這天不是高低點」的時候,94.5% 是對的。第三,被我們挑出來的候選,是真高低點的機率是隨便挑一天的 3.5 到 4 倍。最後一行是目前的限制,後面會說明。");

// ───────────────────────── 3. 題目怎麼變 ─────────────────────────
sec = S("問題與資料");
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("我們的找尋怎麼變成找 11 天高低點", { placeholder: "title" });
card(s, 0.6, 1.55, 5.6, 3.95, C.background2, "before");
T(s, "之前(2026-03 ~ 09)", { x: 0.9, y: 1.8, w: 5, h: 0.4, fontSize: 13, color: C.accent5 });
T(s, "K 線型態 + AE + OC-SVM 預測 5 日大漲大跌", { x: 0.9, y: 2.2, w: 5, h: 0.9, fontSize: 20, bold: true });
T(s, bullets([
  "輸入 1 / 2 / 3 日 K 線特徵,找「之後 5 天漲超過 5%」的相似型態",
  "2026 回測勝率 52.9%,組合 +40.9%,輸給同期買進持有 +73.9%",
  "問題:「會不會大漲」太難,而且跟買賣時點沒有直接關係",
], 14), { x: 0.9, y: 3.15, w: 5.0, h: 2.2, color: C.text2 });
s.addShape(pres.shapes.RIGHT_ARROW, { x: 6.35, y: 3.25, w: 0.6, h: 0.55, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: "arrow" });
card(s, 7.1, 1.55, 5.6, 3.95, C.background2, "after");
T(s, "現在(2026-10 起)", { x: 7.4, y: 1.8, w: 5, h: 0.4, fontSize: 13, color: C.accent5 });
T(s, "找 11 天窗口裡的局部高點與低點", { x: 7.4, y: 2.2, w: 5, h: 0.9, fontSize: 20, bold: true });
T(s, bullets([
  "參考逢甲大學郭念慈、李俊宏的局部極值定義",
  "目標貼近「低點進場、高點出場」:找轉折點,不猜漲多少",
  "標籤只用個股自己的價格,不需要大盤當比較基準",
], 14), { x: 7.4, y: 3.15, w: 5.0, h: 2.2, color: C.text2 });
card(s, 0.6, 5.7, 12.1, 0.9, C.text1, "same-model");
T(s, [
  { text: "不變的:", options: { bold: true, color: C.accent1 } },
  { text: "模型仍是 AE + OC-SVM;改變的是「要找什麼」:從會大漲的型態,變成 11 天窗口的第 6 天是不是轉折點。", options: { color: C.background1 } },
], { x: 0.9, y: 5.7, w: 11.5, h: 0.9, fontSize: 15, valign: "middle" });
s.addNotes("原本的系統是用 AE 加 OC-SVM 找會大漲的 K 線型態,但回測輸給買進持有。所以我們參考逢甲大學的論文,把目標改成找 11 天窗口裡的局部高點和低點,也就是波段的轉折點。");

// ───────────────────────── 4. 標籤怎麼貼 ─────────────────────────
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("標籤怎麼貼:第 6 天是不是 11 天的最高或最低", { placeholder: "title" });
s.addImage({ path: "window_annotated.png", x: 0.6, y: 1.5, w: 7.4, h: 4.01, objectName: "window-example" });
T(s, "實例:台積電 2026-02-25,t 日收盤 2003 是前後各 5 天裡最高 → 高點", { x: 0.6, y: 5.65, w: 7.4, h: 0.5, fontSize: 12, color: C.accent5 });
card(s, 8.4, 1.5, 4.3, 4.65, C.background2, "rules");
T(s, [
  { text: "窗口", options: { bold: true, breakLine: true } },
  { text: "t-5 ~ t+5,共 11 個交易日,t 是第 6 天", options: { color: C.text2, breakLine: true, paraSpaceAfter: 10 } },
  { text: "高點", options: { bold: true, color: C.accent1, breakLine: true } },
  { text: "t 日收盤是 11 天最高", options: { color: C.text2, breakLine: true, paraSpaceAfter: 10 } },
  { text: "低點", options: { bold: true, color: C.accent2, breakLine: true } },
  { text: "t 日收盤是 11 天最低", options: { color: C.text2, breakLine: true, paraSpaceAfter: 10 } },
  { text: "非極值", options: { bold: true, breakLine: true } },
  { text: "其餘;與別天並列最高(低)也算高(低)點", options: { color: C.text2, breakLine: true, paraSpaceAfter: 10 } },
  { text: "判斷時點", options: { bold: true, breakLine: true } },
  { text: "t 日收盤後,只看得到 t-5 ~ t", options: { color: C.text2 } },
], { x: 8.7, y: 1.75, w: 3.8, h: 4.2, fontSize: 14 });
s.addNotes("每個樣本是連續 11 個交易日,中間的第 6 天叫 t。t 日收盤如果是這 11 天最高就標高點、最低就標低點,其他都是非極值。左邊淺色的部分是 t 日收盤當下看得到的;右邊未來 5 天只用來貼標籤,模型看不到。");

// ───────────────────────── 5. 資料量 ─────────────────────────
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("資料量:TW50 · 2016 ~ 2026 · 12.9 萬個股票日", { placeholder: "title" });
const head = (t) => ({ text: t, options: { bold: true, color: HEX.accent5, fontSize: 12 } });
const dataRows = [
  [head("項目"), head("內容")],
  ["股票", "TW50 成分股 50 檔"],
  ["價格", "yfinance 還原權息日 K(開高低收量)"],
  ["期間", "2016-01 ~ 2026-09,可貼標的股票日 129,067"],
  ["訓練", "2020-01 ~ 2023-12:48,585 筆"],
  ["　其中候選", "高點候選 13,994、低點候選 11,465"],
  ["測試", "2025-01 ~ 2026-09:20,189 筆"],
  ["防止偷看", "測試期開始前 5 個交易日剔除(標籤用到 t+5)"],
].map((r, i) => i === 0 ? r : [{ text: r[0], options: { bold: true } }, { text: r[1], options: { color: HEX.dk2 } }]);
s.addTable(dataRows, { x: 0.6, y: 1.55, w: 6.6, colW: [1.5, 5.1], fontSize: 14, fontFace: THEME.bodyFontFace, color: HEX.dk1,
  border: { type: "solid", pt: 0.75, color: "D9E0E6" }, rowH: 0.52, valign: "middle", margin: [0, 0.1, 0, 0.1] });
s.addChart(pres.charts.BAR, [
  { name: "訓練 2020–2023", labels: ["低點", "非極值", "高點"], values: [7.5, 84.6, 7.8] },
  { name: "測試 2025–2026", labels: ["低點", "非極值", "高點"], values: [7.6, 85.1, 7.3] },
], { x: 7.6, y: 1.5, w: 5.1, h: 3.6, barDir: "col", barGrouping: "clustered", chartColors: [HEX.accent5, HEX.dk1],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', dataLabelColor: HEX.dk2, dataLabelFontSize: 12,
  dataLabelFontFace: "+mn-lt", showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt", legendColor: HEX.dk2,
  catAxisLabelColor: HEX.dk2, catAxisLabelFontSize: 13, catAxisLabelFontFace: "+mn-lt", valAxisHidden: true, valAxisMinVal: 0,
  valAxisMaxVal: 100, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showTitle: true, title: "三類標籤比例",
  titleFontSize: 14, titleColor: HEX.dk1, titleFontFace: "+mn-lt", barGapWidthPct: 50, objectName: "class-share" });
T(s, "每 100 天只有約 7–8 天是高點、7–8 天是低點,其餘 85 天都不是。所以全猜「非極值」acc 就有 85%。",
  { x: 7.6, y: 5.25, w: 5.1, h: 1.0, fontSize: 13, color: C.text2 });
s.addNotes("資料是 TW50 的 50 檔股票,2016 到 2026 年 9 月的還原日 K,總共約 12.9 萬個股票日。訓練用 2020 到 2023 年 48,585 筆,測試用 2025 年到 2026 年 9 月 20,189 筆。高點和低點各只佔 7 到 8%,這個不平衡很重要,後面算 acc 時會再提到。");

// ───────────────────────── 6. 方法流程 ─────────────────────────
sec = S("方法與計分");
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("方法流程:規則挑候選,AE + OC-SVM 篩候選", { placeholder: "title" });
const steps = [
  ["1", "t 日收盤後", "取 t-5 ~ t 六根 K 線(開高低收量,29 個數字)"],
  ["2", "規則挑候選", "t 日收盤是近 6 天最高 → 高點候選;最低 → 低點候選;其餘直接判非極值"],
  ["3", "AE + OC-SVM 篩選", "候選落在「真高(低)點」的範圍內才保留,範圍外改判非極值"],
  ["4", "輸出", "每天一個判斷:高點 / 非極值 / 低點"],
];
steps.forEach(([n, h, d], j) => {
  const x = 0.6 + j * 3.1;
  card(s, x, 1.7, 2.8, 3.2, C.background2, `step-${n}`);
  s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: 1.95, w: 0.55, h: 0.55, fill: { color: j === 2 ? C.accent1 : C.text1 }, line: { color: j === 2 ? C.accent1 : C.text1 }, objectName: `step-dot-${n}` });
  T(s, n, { x: x + 0.25, y: 1.95, w: 0.55, h: 0.55, fontSize: 18, bold: true, color: C.background1, align: "center", valign: "middle" });
  T(s, h, { x: x + 0.25, y: 2.7, w: 2.35, h: 0.5, fontSize: 18, bold: true });
  T(s, d, { x: x + 0.25, y: 3.25, w: 2.35, h: 1.6, fontSize: 13, color: C.text2 });
  if (j < 3) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.83, y: 3.15, w: 0.24, h: 0.3, fill: { color: C.accent6 }, line: { color: C.accent6 }, objectName: `step-arrow-${n}` });
});
card(s, 0.6, 5.2, 12.1, 1.15, C.background2, "why-rule");
T(s, [
  { text: "為什麼規則不會漏:", options: { bold: true } },
  { text: "t 日如果是 11 天最高,一定也是近 6 天(t-5 ~ t)最高,而這在 t 日收盤就知道。所以真高低點全部都在候選裡,模型的工作只剩「從候選裡刪掉之後 5 天被超越的假候選」。", options: { color: C.text2 } },
], { x: 0.9, y: 5.38, w: 11.5, h: 0.85, fontSize: 14 });
s.addNotes("流程分四步。關鍵在第二步的規則:真正的 11 日高點,一定也是近 6 天的高點,所以規則先把所有可能的候選挑出來,保證不漏。第三步才是我們的 AE 加 OC-SVM,它要從候選裡刪掉那些之後 5 天又被超越的假候選。");

// ───────────────────────── 7. AE + OC-SVM ─────────────────────────
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("AE + OC-SVM:學「真高低點」長什麼樣", { placeholder: "title" });
const boxes = [
  [0.6, "輸入", "29 維\n6 根 K 線形態", C.background2, C.text1],
  [3.0, "AE 編碼器", "29 → 58 → 8 → 4", C.background2, C.text1],
  [5.4, "潛在向量", "4 維", C.text1, C.background1],
  [7.8, "OC-SVM", "rbf · nu 0.1\n圈出真候選的範圍", C.background2, C.text1],
  [10.2, "判斷", "範圍內 → 保留\n範圍外 → 非極值", C.background2, C.text1],
];
boxes.forEach(([x, h, d, fill, ink], j) => {
  card(s, x, 1.8, 2.1, 1.9, fill, `ae-box-${j}`);
  T(s, h, { x: x + 0.2, y: 1.95, w: 1.7, h: 0.45, fontSize: 15, bold: true, color: ink, align: "center" });
  T(s, d, { x: x + 0.2, y: 2.45, w: 1.7, h: 1.1, fontSize: 13, color: ink, align: "center" });
  if (j < 4) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.13, y: 2.6, w: 0.25, h: 0.3, fill: { color: C.accent6 }, line: { color: C.accent6 }, objectName: `ae-arrow-${j}` });
});
T(s, "AE 解碼器 4 → 8 → 58 → 29,把輸入重建回來(MSE,訓練 60 輪);只拿編碼後的 4 維給 OC-SVM。",
  { x: 0.6, y: 3.95, w: 12.1, h: 0.45, fontSize: 13, color: C.accent5 });
T(s, bullets([
  "訓練樣本:訓練期(2020–2023)的規則候選點;高點、低點各訓練一組 AE + OC-SVM",
  "樣本權重:距離 3 以內的相似候選中,同樣是真高(低)點的比例(沿用原系統的「重要性」概念)",
  "AE 與 OC-SVM 的結構、潛在維度 4、nu 0.1 都直接沿用 method_kline 原系統",
], 15), { x: 0.6, y: 4.6, w: 12.1, h: 1.9, color: C.text2 });
s.addNotes("模型沿用我們原本系統的 AE 加 OC-SVM。AE 把 6 根 K 線的 29 個數字壓成 4 維,OC-SVM 在這 4 維空間裡圈出真高點候選的範圍。測試時,候選點落在範圍內就保留,否則改判非極值。高點和低點各訓練一組。");

// ───────────────────────── 8. acc 怎樣算對 ─────────────────────────
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("acc 怎樣算對:判斷與 11 日窗口標籤相同", { placeholder: "title" });
card(s, 0.6, 1.55, 5.9, 3.15, C.background2, "rule-of-right");
T(s, [
  { text: "一天算「判對」", options: { bold: true, fontSize: 18, breakLine: true } },
  { text: " ", options: { fontSize: 8, breakLine: true } },
  { text: "模型在 t 日收盤後給的判斷(高點 / 非極值 / 低點),和用 t-5 ~ t+5 貼出來的標籤一樣。", options: { color: C.text2, breakLine: true } },
  { text: " ", options: { fontSize: 8, breakLine: true } },
  { text: "例:判高點,而 t 日收盤真的是 11 天最高 → 對", options: { color: C.accent3, breakLine: true } },
  { text: "例:判高點,但之後 5 天收盤更高 → 錯(假候選)", options: { color: C.accent4, breakLine: true } },
  { text: "例:判非極值,而那天真的不是高低點 → 對", options: { color: C.accent3 } },
], { x: 0.9, y: 1.8, w: 5.3, h: 2.75, fontSize: 15 });
card(s, 0.6, 4.9, 5.9, 1.45, C.background2, "acc-trap");
T(s, "85.1%", { x: 0.9, y: 5.0, w: 2.1, h: 1.25, fontSize: 36, bold: true, color: C.accent4, valign: "middle" });
T(s, [
  { text: "全猜「非極值」的 acc", options: { bold: true, breakLine: true } },
  { text: "一個高低點都沒找到,macro-F1 只有 30.7%。所以不能只看 acc。", options: { color: C.text2 } },
], { x: 3.0, y: 5.0, w: 3.3, h: 1.25, fontSize: 13, valign: "middle" });
const defs = [
  ["acc", "判對的天數 ÷ 全部天數"],
  ["找到率(召回)", "真高點中被判成高點的比例"],
  ["命中率(精確)", "判成高點的天數中真的是高點的比例"],
  ["macro-F1", "高點、非極值、低點三類 F1 的平均;論文的主要指標"],
];
defs.forEach(([k, v], j) => {
  const y = 1.7 + j * 1.15;
  if (j) s.addShape(pres.shapes.LINE, { x: 6.9, y: y - 0.12, w: 5.8, h: 0, line: { color: HEX.accent6, width: 0.75 }, objectName: `def-rule-${j}` });
  T(s, k, { x: 6.9, y, w: 2.2, h: 0.8, fontSize: 16, bold: true, valign: "middle" });
  T(s, v, { x: 9.1, y, w: 3.6, h: 0.8, fontSize: 14, color: C.text2, valign: "middle" });
});
s.addNotes("判對的定義很簡單:模型的判斷和 11 日窗口貼出來的標籤一樣就算對。acc 是判對的天數除以全部天數。但因為 85% 的日子都是非極值,全猜非極值 acc 就有 85%,卻一個高低點都沒找到,所以論文和我們都用 macro-F1 當主要指標,同時看找到率和命中率。");

// ───────────────────────── 9. 混淆矩陣 ─────────────────────────
sec = S("結果");
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("測試結果:真高低點幾乎都在模型的判斷裡", { placeholder: "title" });
const cm = [[1237, 295, 0], [2690, 11288, 3209], [0, 359, 1111]];
const names = ["低點", "非極值", "高點"];
const ramp = ["F4F8FD", "CDE2FB", "86B6EF", "3987E5", "1C5CAB", "104281"];
const shade = (p) => ramp[Math.min(5, Math.floor(p * 6))];
const cmRows = [[{ text: "實際 \\ 判斷", options: { bold: true, color: HEX.accent5, fontSize: 12 } },
  ...names.map(n => ({ text: `判${n}`, options: { bold: true, align: "center", color: HEX.dk1 } }))]];
cm.forEach((r, i) => {
  const tot = r.reduce((a, b) => a + b, 0);
  cmRows.push([{ text: `真${names[i]}`, options: { bold: true } },
    ...r.map(v => { const p = v / tot; return { text: `${v.toLocaleString("en-US")}\n${(p * 100).toFixed(1)}%`,
      options: { align: "center", fill: { color: shade(p) }, color: p > 0.5 ? "FFFFFF" : HEX.dk1, fontSize: 14 } }; })]);
});
s.addTable(cmRows, { x: 0.6, y: 1.6, w: 6.6, colW: [1.5, 1.7, 1.7, 1.7], rowH: [0.5, 0.95, 0.95, 0.95], fontSize: 14,
  fontFace: THEME.bodyFontFace, color: HEX.dk1, valign: "middle", border: { type: "solid", pt: 1, color: "FFFFFF" } });
T(s, "規則 + AE + OC-SVM(主軸,種子 42);格內為天數與該列(實際類別)的比例", { x: 0.6, y: 5.15, w: 6.6, h: 0.5, fontSize: 12, color: C.accent5 });
const mRows = [
  [head(""), head("acc"), head("macro-F1"), head("非極值判對率")],
  ["全猜非極值", "85.1%", "30.7%", "85.1%"],
  ["規則基準(論文)", "62.4%", "53.5%", "100.0%"],
  ["規則 + AE + OC-SVM", "67.5%", "53.7%", "94.5%"],
].map((r, i) => i === 0 ? r : r.map((c, j) => ({ text: c, options: { align: j ? "right" : "left", bold: i === 3 } })));
s.addTable(mRows, { x: 7.6, y: 1.6, w: 5.1, colW: [2.0, 0.9, 1.1, 1.1], rowH: 0.55, fontSize: 13, fontFace: THEME.bodyFontFace,
  color: HEX.dk1, valign: "middle", border: { type: "solid", pt: 0.75, color: "D9E0E6" }, margin: [0, 0.08, 0, 0.08] });
T(s, bullets([
  "真高點 1,470 個:判對 1,111 個(75.6%),沒有一個被判成低點",
  "真低點 1,532 個:判對 1,237 個(80.7%),沒有一個被判成高點",
  "3 個種子平均 macro-F1 53.60 ± 0.15%",
], 13), { x: 7.6, y: 3.95, w: 5.1, h: 2.2, color: C.text2 });
s.addNotes("這是測試期的混淆矩陣。看第一列和最後一列:真低點有 80.7% 被判成低點,真高點有 75.6% 被判成高點,而且高點和低點從來不會互相判錯。右邊的表比較三種做法,模型的 acc 是 67.5%,判非極值時 94.5% 正確。");

// ───────────────────────── 10. 局部準確度 ─────────────────────────
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("局部準確度:挑出的候選比亂猜準 3.5–4.2 倍", { placeholder: "title" });
s.addChart(pres.charts.BAR, [
  { name: "隨機挑一天", labels: ["高點", "低點"], values: [7.3, 7.6] },
  { name: "規則基準", labels: ["高點", "低點"], values: [25.4, 32.0] },
  { name: "規則 + AE + OC-SVM", labels: ["高點", "低點"], values: [25.7, 31.5] },
], { x: 0.6, y: 1.5, w: 7.2, h: 4.8, barDir: "col", barGrouping: "clustered", chartColors: [HEX.accent6, HEX.accent5, HEX.dk1],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', dataLabelColor: HEX.dk2, dataLabelFontSize: 12,
  dataLabelFontFace: "+mn-lt", showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt", legendColor: HEX.dk2,
  catAxisLabelColor: HEX.dk2, catAxisLabelFontSize: 14, catAxisLabelFontFace: "+mn-lt", valAxisHidden: true, valAxisMaxVal: 40,
  valAxisMinVal: 0, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showTitle: true,
  title: "命中率:判成高(低)點的日子中真的是高(低)點", titleFontSize: 14, titleColor: HEX.dk1, titleFontFace: "+mn-lt",
  barGapWidthPct: 60, objectName: "precision-chart" });
const loc = [
  ["100% / 99.9%", "規則找到的真高點 / 真低點", C.accent1],
  ["75.6% / 80.7%", "模型保留下來的真高點 / 真低點", C.accent2],
  ["94.5%", "模型判非極值時的正確率", C.accent3],
];
loc.forEach(([v, k, col], j) => {
  const y = 1.6 + j * 1.6;
  card(s, 8.2, y, 4.5, 1.4, C.background2, `loc-${j}`);
  T(s, v, { x: 8.45, y: y + 0.15, w: 4.1, h: 0.65, fontSize: 28, bold: true, color: col });
  T(s, k, { x: 8.45, y: y + 0.82, w: 4.1, h: 0.45, fontSize: 13, color: C.text2 });
});
s.addNotes("這頁是我們說的局部準確度。左圖是命中率:隨機挑一天是高點的機率只有 7.3%,被我們挑出來的候選是 25 到 32%,大約是 3.5 到 4 倍。右邊三個數字:真高低點幾乎全部找到,模型保留下 75 到 80%,判非極值時 94.5% 正確。");

// ───────────────────────── 11. 找到的結果長什麼樣 ─────────────────────────
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("找到的結果長什麼樣", { placeholder: "title" });
s.addImage({ path: "examples.png", x: 0.9, y: 1.4, w: 9.9, h: 5.58, objectName: "examples" });
T(s, [
  { text: "怎麼看", options: { bold: true, breakLine: true } },
  { text: "淺色底 = t 日看得到的 6 天;框起來的是 t;虛線是 t 日收盤。", options: { color: C.text2, breakLine: true, paraSpaceAfter: 10 } },
  { text: "怎麼挑", options: { bold: true, breakLine: true } },
  { text: "每類取「之後 5 天報酬」最接近該類中位數的窗口,是典型例子,不是最好看的。", options: { color: C.text2, breakLine: true, paraSpaceAfter: 10 } },
  { text: "互動版", options: { bold: true, breakLine: true } },
  { text: "網頁可逐檔、逐日點開每個 11 日窗口。", options: { color: C.text2 } },
], { x: 10.95, y: 1.6, w: 1.85, h: 5.0, fontSize: 12 });
s.addNotes("這是測試期四種情況的典型例子:左上判對的高點,右上判對的低點,左下是規則挑出來但被模型正確刪掉的假候選,右下是誤報,判了高點但之後又創新高。每一類都是取報酬最接近中位數的窗口,不是挑最好看的。互動網頁(連結:https://claude.ai/artifact/4YudK9qBr4fnsV4NQatjEe,需先分享權限)可以看全部 50 檔。");

// ───────────────────────── 12. 與論文比較 ─────────────────────────
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("與論文比較:規則基準完整重現", { placeholder: "title" });
const pRows = [
  [head(""), head("論文(12 檔,測試 2025-10 ~ 2026-03)"), head("我們 TW50 · 論文切分"), head("我們 TW50 · 我們的切分")],
  ["低點 / 非極值 / 高點", "8.5 / 84.5 / 7.0%", "8.0 / 85.0 / 7.0%", "7.6 / 85.1 / 7.3%"],
  ["規則基準 macro-F1", "53.38%", "52.32%", "53.54%"],
  ["規則基準 BalAcc", "84.90%", "84.69%", "85.27%"],
  ["模型 macro-F1", "54.81%(雙分支 GNN + 券商分點)", "52.52%(AE + OC-SVM)", "53.60%(AE + OC-SVM)"],
  ["模型 − 規則", "+1.43 點", "+0.21 點", "+0.05 點"],
].map((r, i) => i === 0 ? r : r.map((c, j) => ({ text: c, options: { bold: j === 0, align: j ? "center" : "left" } })));
s.addTable(pRows, { x: 0.6, y: 1.6, w: 12.1, colW: [2.6, 3.7, 2.9, 2.9], rowH: 0.62, fontSize: 14, fontFace: THEME.bodyFontFace,
  color: HEX.dk1, valign: "middle", border: { type: "solid", pt: 0.75, color: "D9E0E6" }, margin: [0, 0.1, 0, 0.1] });
T(s, bullets([
  "照論文定義貼標,類別比例與規則基準的分數都和論文幾乎相同",
  "論文的模型比規則多 1.43 點,主要來自券商分點資料(我們沒有);論文自己的純價格模型只多 0.6 點",
], 14), { x: 0.6, y: 5.5, w: 12.1, h: 1.1, color: C.text2 });
s.addNotes("我們用論文的方法貼標,類別比例和規則基準的分數都跟論文幾乎一樣,代表我們的資料和流程是對的。論文的模型比規則多 1.43 點,主要是加了券商分點資料;它的純價格模型只多 0.6 點,我們的 AE 加 OC-SVM 也是同一個水準。");

// ───────────────────────── 13. 限制與下一步 ─────────────────────────
sec = S("收尾");
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("限制與下一步", { placeholder: "title" });
card(s, 0.6, 1.55, 5.9, 3.55, C.background2, "limits");
T(s, "目前的限制", { x: 0.9, y: 1.8, w: 5.3, h: 0.5, fontSize: 20, bold: true });
T(s, bullets([
  "判出的高點只有 25.7%、低點 31.5% 是真的;每 4 個約 3 個是之後 5 天被超越的假候選",
  "AE + OC-SVM(含真、假候選各學一組)保留真、假候選的比例相同,還沒贏過規則",
  "規則訊號直接交易(持有 5 天):低點做多勝率 54.3%,每天都做多 53.1%",
], 14), { x: 0.9, y: 2.4, w: 5.3, h: 2.6, color: C.text2 });
card(s, 6.8, 1.55, 5.9, 3.55, C.background2, "next");
T(s, "下一步", { x: 7.1, y: 1.8, w: 5.3, h: 0.5, fontSize: 20, bold: true });
T(s, bullets([
  "把低點候選的命中率從 31.5% 拉到 36% 以上:扣掉 0.42% 交易成本後的損益兩平點",
  "接入券商分點資料,這是論文提升的來源",
  "改預測「低點訊號之後 5 天會不會賺錢」,讓標籤直接對應交易",
], 14), { x: 7.1, y: 2.4, w: 5.3, h: 2.6, color: C.text2 });
[["低點候選命中率", "31.5%", "36%", C.accent2], ["高點候選命中率", "25.7%", "47%", C.accent1]].forEach(([k, now, need, col], j) => {
  const x = 0.6 + j * 6.2;
  card(s, x, 5.3, 5.9, 1.1, C.background2, `gap-${j}`);
  T(s, k, { x: x + 0.3, y: 5.3, w: 1.6, h: 1.1, fontSize: 14, bold: true, valign: "middle" });
  T(s, [
    { text: "現在 ", options: { fontSize: 12, color: C.text2 } }, { text: now, options: { fontSize: 22, bold: true, color: col } },
    { text: "  →  兩平 ", options: { fontSize: 12, color: C.text2 } }, { text: need, options: { fontSize: 22, bold: true, color: C.text1 } },
  ], { x: x + 1.95, y: 5.3, w: 3.85, h: 1.1, valign: "middle" });
});
s.addNotes("目前的限制是:被挑出來的候選裡,每 4 個大約有 3 個是假的,AE 加 OC-SVM 還分不出真假候選。下一步的具體目標是把低點候選的命中率拉到 36% 以上,這是扣掉交易成本後不賠錢的門檻。");

// ───────────────────────── 14. 結論 ─────────────────────────
s = pres.addSlide({ masterName: "DARK", sectionTitle: sec });
s.addText("結論", { placeholder: "title" });
s.addText(bullets([
  "依論文定義在 TW50 重現 11 日局部高低點標籤與規則基準(macro-F1 53.5%,論文 53.4%)",
  "局部準確度:真高低點 100% 進候選,判非極值 94.5% 正確,候選命中率是亂猜的 3.5–4.2 倍",
  "下一步:提高候選命中率,低點目標 36% 以上",
], 20), { placeholder: "body" });
s.addNotes("總結三點。第一,我們照論文方法重現了標籤和規則基準。第二,局部準確度很好:不漏掉真高低點、判非極值很準、候選比亂猜準 3.5 到 4 倍。第三,接下來要提高候選的命中率。謝謝。");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
