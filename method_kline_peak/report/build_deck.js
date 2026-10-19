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

let s;
let sec = S("問題與資料");

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
  [0.6, "輸入", "29 維\n價 ÷ t 日收盤\n量 ÷ 10 日均量", C.background2, C.text1],
  [3.0, "AE 編碼器", "29 → 16\n一層,不先升維", C.background2, C.text1],
  [5.4, "潛在向量", "16 維", C.text1, C.background1],
  [7.8, "OC-SVM", "rbf · nu 0.1\n圈出真候選的範圍", C.background2, C.text1],
  [10.2, "判斷", "範圍內 → 保留\n範圍外 → 非極值", C.background2, C.text1],
];
boxes.forEach(([x, h, d, fill, ink], j) => {
  card(s, x, 1.8, 2.1, 1.9, fill, `ae-box-${j}`);
  T(s, h, { x: x + 0.2, y: 1.95, w: 1.7, h: 0.45, fontSize: 15, bold: true, color: ink, align: "center" });
  T(s, d, { x: x + 0.2, y: 2.45, w: 1.7, h: 1.1, fontSize: 13, color: ink, align: "center" });
  if (j < 4) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.13, y: 2.6, w: 0.25, h: 0.3, fill: { color: C.accent6 }, line: { color: C.accent6 }, objectName: `ae-arrow-${j}` });
});
T(s, "AE 解碼器 16 → 29,把輸入重建回來(MSE,訓練 60 輪);只拿編碼後的 16 維給 OC-SVM。",
  { x: 0.6, y: 3.95, w: 12.1, h: 0.45, fontSize: 13, color: C.accent5 });
T(s, bullets([
  "訓練樣本:訓練期(2020–2023)的規則候選點;高點、低點各訓練一組 AE + OC-SVM",
  "樣本權重:距離 3 以內的相似候選中,同樣是真高(低)點的比例(沿用原系統的「重要性」概念)",
  "編碼器只有一層 29 → 16(973 個參數);原系統 29 → 58 → 8 → 4 有 4,637 個,兩者結果相同;OC-SVM 的 rbf、nu 0.1 沿用原系統",
], 15), { x: 0.6, y: 4.6, w: 12.1, h: 1.9, color: C.text2 });
s.addNotes("模型沿用我們原本系統的 AE 加 OC-SVM。AE 的輸入是 t-5 到 t 六根 K 線的 29 個數字:每天的開高低收都除以 t 日收盤(t 日收盤自己固定是 1,所以拿掉),每天的量除以 10 日均量。AE 只用一層、不先升維,直接把這 29 個數字壓成 16 維,OC-SVM 在這 16 維空間裡圈出真高點候選的範圍。測試時,候選點落在範圍內就保留,否則改判非極值。高點和低點各訓練一組。");

// ───────────────────────── 9. 混淆矩陣 ─────────────────────────
sec = S("結果");
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("測試結果:真高低點幾乎都在模型的判斷裡", { placeholder: "title" });
const cm = [[1222, 310, 0], [2646, 11414, 3127], [0, 432, 1038]];
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
  ["規則 + AE + OC-SVM", "67.7%", "53.3%", "93.9%"],
].map((r, i) => i === 0 ? r : r.map((c, j) => ({ text: c, options: { align: j ? "right" : "left", bold: i === 3 } })));
s.addTable(mRows, { x: 7.6, y: 1.6, w: 5.1, colW: [2.0, 0.9, 1.1, 1.1], rowH: 0.55, fontSize: 13, fontFace: THEME.bodyFontFace,
  color: HEX.dk1, valign: "middle", border: { type: "solid", pt: 0.75, color: "D9E0E6" }, margin: [0, 0.08, 0, 0.08] });
T(s, bullets([
  "真高點 1,470 個:判對 1,038 個(70.6%),沒有一個被判成低點",
  "真低點 1,532 個:判對 1,222 個(79.8%),沒有一個被判成高點",
  "判非極值的 12,156 天中,11,414 天真的不是高低點(93.9%)",
], 13), { x: 7.6, y: 3.95, w: 5.1, h: 2.2, color: C.text2 });
s.addNotes("這是測試期的混淆矩陣。看第一列和最後一列:真低點有 79.8% 被判成低點,真高點有 70.6% 被判成高點,而且高點和低點從來不會互相判錯。右邊的表比較三種做法,模型的 acc 是 67.7%,判非極值時 93.9% 正確。");

// ───────────────────────── 10. 局部準確度 ─────────────────────────
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("局部準確度:挑出的候選比亂猜準 3.4–4.2 倍", { placeholder: "title" });
s.addChart(pres.charts.BAR, [
  { name: "隨機挑一天", labels: ["高點", "低點"], values: [7.3, 7.6] },
  { name: "規則基準", labels: ["高點", "低點"], values: [25.4, 32.0] },
  { name: "規則 + AE + OC-SVM", labels: ["高點", "低點"], values: [24.9, 31.6] },
], { x: 0.6, y: 1.5, w: 7.2, h: 4.8, barDir: "col", barGrouping: "clustered", chartColors: [HEX.accent6, HEX.accent5, HEX.dk1],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', dataLabelColor: HEX.dk2, dataLabelFontSize: 12,
  dataLabelFontFace: "+mn-lt", showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt", legendColor: HEX.dk2,
  catAxisLabelColor: HEX.dk2, catAxisLabelFontSize: 14, catAxisLabelFontFace: "+mn-lt", valAxisHidden: true, valAxisMaxVal: 40,
  valAxisMinVal: 0, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showTitle: true,
  title: "命中率:判成高(低)點的日子中真的是高(低)點", titleFontSize: 14, titleColor: HEX.dk1, titleFontFace: "+mn-lt",
  barGapWidthPct: 60, objectName: "precision-chart" });
const loc = [
  ["100% / 99.9%", "規則找到的真高點 / 真低點", C.accent1],
  ["70.6% / 79.8%", "模型判對的真高點 / 真低點", C.accent2],
  ["93.9%", "模型判非極值時的正確率", C.accent3],
];
loc.forEach(([v, k, col], j) => {
  const y = 1.6 + j * 1.6;
  card(s, 8.2, y, 4.5, 1.4, C.background2, `loc-${j}`);
  T(s, v, { x: 8.45, y: y + 0.15, w: 4.1, h: 0.65, fontSize: 28, bold: true, color: col });
  T(s, k, { x: 8.45, y: y + 0.82, w: 4.1, h: 0.45, fontSize: 13, color: C.text2 });
});
s.addNotes("這頁是我們說的局部準確度。左圖是命中率:隨機挑一天是高點的機率只有 7.3%,被我們挑出來的候選是 25 到 32%,大約是 3.4 到 4.2 倍。右邊三個數字:真高低點全部進了候選,模型判對 71 到 80%,判非極值時 93.9% 正確。");

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

// ───────────────────────── 總結 ─────────────────────────
sec = S("總結");
s = pres.addSlide({ masterName: "DARK", sectionTitle: sec });
s.addText("總結:成功找到 11 日窗口的局部高低點", { placeholder: "title" });
const wins = [
  ["100%", "真高低點都進了候選", "高點 1,470 / 1,470\n低點 1,531 / 1,532", C.accent1],
  ["0 次", "高點與低點互相判錯", "真高點沒被判成低點,\n真低點沒被判成高點", C.background1],
  ["93.9%", "判「非極值」的正確率", "12,156 天裡 11,414 天\n真的不是高低點", C.accent3],
  ["3.4–4.2×", "命中率是隨機挑的倍數", "高點 7.3% → 24.9%\n低點 7.6% → 31.6%", C.accent2],
];
wins.forEach(([v, k, d, col], j) => {
  const x = 0.8 + j * 2.95;
  T(s, v, { x, y: 3.9, w: 2.75, h: 0.95, fontSize: 40, bold: true, color: col, valign: "middle" });
  T(s, k, { x, y: 4.9, w: 2.75, h: 0.45, fontSize: 16, bold: true, color: C.background1 });
  T(s, d, { x, y: 5.4, w: 2.75, h: 0.9, fontSize: 13, color: C.accent6 });
});
T(s, "測試期 2025-01 ~ 2026-09 · TW50 · 20,189 個股票日;模型判對 70.6% 的真高點、79.8% 的真低點",
  { x: 0.8, y: 6.6, w: 11.7, h: 0.4, fontSize: 13, color: C.accent5 });
s.addNotes("總結。我們把題目定成找 11 天窗口裡的局部高低點,在 TW50 的測試期:真高低點全部進了候選;模型判出的高點和低點從來不會互相搞錯;模型說「這天不是高低點」時 93.9% 是對的;挑出來的候選是真高低點的機率是隨便挑一天的 3.4 到 4.2 倍。模型最後判對了 71% 的真高點和 80% 的真低點。謝謝。");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
