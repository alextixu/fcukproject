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
T(s, "實例:台積電 2024-09-26,t 日收盤 989 是前後各 5 天裡最高 → 高點", { x: 0.6, y: 5.65, w: 7.4, h: 0.5, fontSize: 12, color: C.accent5 });
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
s.addText("資料量:TW50 · 2020 ~ 2026 · 8.1 萬個股票日", { placeholder: "title" });
const head = (t) => ({ text: t, options: { bold: true, color: HEX.accent5, fontSize: 12 } });
const dataRows = [
  [head("項目"), head("內容")],
  ["股票", "TW50 成分股 50 檔"],
  ["價格", "yfinance 還原權息日 K(開高低收量)"],
  ["全部", "2020-01 ~ 2026-09:80,872 個股票日"],
  ["訓練", "2020–2023:48,335 筆(剔除 2023 最後 5 天)"],
  ["　其中候選", "高點 13,866(真 3,769)、低點 11,458(真 3,651)"],
  ["測試", "2024 整年:12,098 筆"],
  ["2025–2026", "20,189 筆:這份報告沒用到", true],
].map((r, i) => i === 0 ? r : [{ text: r[0], options: { bold: true, color: r[2] ? HEX.accent5 : HEX.dk1 } },
  { text: r[1], options: { color: r[2] ? HEX.accent5 : HEX.dk2 } }]);
s.addTable(dataRows, { x: 0.6, y: 1.55, w: 6.6, colW: [1.5, 5.1], fontSize: 14, fontFace: THEME.bodyFontFace, color: HEX.dk1,
  border: { type: "solid", pt: 0.75, color: "D9E0E6" }, rowH: 0.5, valign: "middle", margin: [0, 0.1, 0, 0.1] });
s.addChart(pres.charts.BAR, [
  { name: "訓練 2020–2023", labels: ["低點", "非極值", "高點"], values: [7.6, 84.6, 7.8] },
  { name: "測試 2024", labels: ["低點", "非極值", "高點"], values: [7.5, 85.0, 7.4] },
], { x: 7.6, y: 1.5, w: 5.1, h: 3.6, barDir: "col", barGrouping: "clustered", chartColors: [HEX.accent5, HEX.dk1],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', dataLabelColor: HEX.dk2, dataLabelFontSize: 12,
  dataLabelFontFace: "+mn-lt", showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt", legendColor: HEX.dk2,
  catAxisLabelColor: HEX.dk2, catAxisLabelFontSize: 13, catAxisLabelFontFace: "+mn-lt", valAxisHidden: true, valAxisMinVal: 0,
  valAxisMaxVal: 100, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showTitle: true, title: "三類標籤比例",
  titleFontSize: 14, titleColor: HEX.dk1, titleFontFace: "+mn-lt", barGapWidthPct: 50, objectName: "class-share" });
T(s, "每 100 天只有約 7–8 天是高點、7–8 天是低點,其餘 85 天都不是。所以全猜「非極值」acc 就有 85%。",
  { x: 7.6, y: 5.25, w: 5.1, h: 1.0, fontSize: 13, color: C.text2 });
s.addNotes("資料是 TW50 的 50 檔股票,2020 到 2026 年 9 月的還原日 K,總共 80,872 個股票日。訓練用 2020 到 2023 年 48,335 筆,測試用 2024 年整年 12,098 筆。2023 年最後 5 個交易日的 250 筆剔除,因為它們的標籤會用到 2024 年的價格,不剔除等於偷看測試期。2025 年以後這份報告沒有用到。加起來剛好是 80,872。高點和低點各只佔 7 到 8%,這個不平衡很重要,後面算 acc 時會再提到。");

// ───────────────────────── 6. 訓練輸入:11 天中的哪幾天、哪些特徵 ─────────────────────────
sec = S("方法與計分");
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("訓練輸入:11 天中的前 6 天,每天 5 個特徵", { placeholder: "title" });
// 11 天的方塊:前 6 天丟進模型,後 5 天只貼標籤
for (let k = 0; k < 11; k++) {
  const x = 0.6 + k * 1.11, used = k < 6, isT = k === 5;
  const fill = isT ? C.accent1 : used ? C.text1 : C.background2;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.45, w: 1.0, h: 0.8, fill: { color: fill }, line: { color: fill }, rectRadius: 0.06, objectName: `day-${k + 1}` });
  T(s, [
    { text: `第 ${k + 1} 天`, options: { fontSize: 12, breakLine: true } },
    { text: k === 5 ? "t" : k < 5 ? `t-${5 - k}` : `t+${k - 5}`, options: { fontSize: 16, bold: true } },
  ], { x, y: 1.45, w: 1.0, h: 0.8, align: "center", valign: "middle", color: used ? C.background1 : C.accent5 });
}
s.addShape(pres.shapes.LINE, { x: 0.6, y: 2.4, w: 6.55, h: 0, line: { color: HEX.dk1, width: 1.5 }, objectName: "bracket-used" });
s.addShape(pres.shapes.LINE, { x: 7.26, y: 2.4, w: 5.44, h: 0, line: { color: HEX.accent6, width: 1.5 }, objectName: "bracket-label" });
T(s, "丟進模型:t 日收盤時都已經知道", { x: 0.6, y: 2.48, w: 6.55, h: 0.35, fontSize: 13, bold: true, align: "center" });
T(s, "不丟進模型:只用來貼標籤(看第 6 天是不是 11 天最高 / 最低)", { x: 7.26, y: 2.48, w: 5.44, h: 0.35, fontSize: 13, color: C.accent5, align: "center" });

// 特徵表:5 個特徵 × 6 天,附台積電 2024-09-26 的實際數字
const days = ["t-5", "t-4", "t-3", "t-2", "t-1", "t"];
const ex = {
  開: [-7.4, -3.3, -4.3, -3.8, -1.5, -0.5], 高: [-5.4, -3.3, -3.7, -2.8, -1.0, 0.0],
  低: [-7.8, -4.3, -4.3, -4.3, -1.7, -1.0], 收: [-5.4, -4.1, -3.7, -2.8, -1.0, null],
  量: [1.03, 1.89, 0.45, 0.84, 1.24, 1.20],
};
const how = { 開: "開盤 ÷ t 日收盤", 高: "最高 ÷ t 日收盤", 低: "最低 ÷ t 日收盤", 收: "收盤 ÷ t 日收盤", 量: "成交量 ÷ 10 日均量" };
const fmt = (k, v) => v === null ? "拿掉" : k === "量" ? `${v.toFixed(2)}×` : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}%`;
const fRows = [[head("特徵"), head("算法"), ...days.map(d => ({ text: d, options: { bold: true, color: HEX.accent5, fontSize: 12, align: "center" } }))]];
Object.keys(ex).forEach(k => fRows.push([
  { text: k, options: { bold: true } }, { text: how[k], options: { color: HEX.dk2 } },
  ...ex[k].map((v, j) => ({ text: fmt(k, v), options: { align: "center", color: v === null ? HEX.accent5 : HEX.dk1,
    fill: { color: j === 5 ? "FCE9E0" : "FFFFFF" } } })),
]));
s.addTable(fRows, { x: 0.6, y: 3.05, w: 8.1, colW: [0.7, 2.3, 0.85, 0.85, 0.85, 0.85, 0.85, 0.85], rowH: 0.4, fontSize: 13,
  fontFace: THEME.bodyFontFace, color: HEX.dk1, valign: "middle", border: { type: "solid", pt: 0.75, color: "D9E0E6" }, margin: [0, 0.08, 0, 0.08] });
T(s, "例:台積電 2024-09-26(第 1 頁的高點)。價格以 % 顯示,模型實際用 ln 值;量的 10 日均量算到 t 日為止。",
  { x: 0.6, y: 5.5, w: 8.1, h: 0.35, fontSize: 11, color: C.accent5 });

card(s, 9.0, 3.05, 3.7, 2.8, C.background2, "count-29");
T(s, "6 天 × 5 − 1 = 29", { x: 9.25, y: 3.2, w: 3.3, h: 0.6, fontSize: 24, bold: true, color: C.accent1 });
T(s, bullets([
  "t 日收盤 ÷ 自己永遠是 1,沒有資訊,拿掉",
  "價格都除以 t 日收盤:只看形狀,不看股價高低",
  "量除以 10 日均量:看這幾天是平常的幾倍",
], 13), { x: 9.25, y: 3.9, w: 3.3, h: 1.85, color: C.text2 });

card(s, 0.6, 6.0, 12.1, 0.75, C.background2, "train-samples");
T(s, [
  { text: "訓練樣本:", options: { bold: true } },
  { text: "50 檔放在一起,不是每檔一個模型。2020–2023 的候選日裡,真高點 3,769 天訓練一組 AE + OC-SVM、真低點 3,651 天訓練另一組,共 2 組。", options: { color: C.text2 } },
], { x: 0.85, y: 6.0, w: 11.6, h: 0.75, fontSize: 13, valign: "middle" });
s.addNotes("這頁說明我們丟進模型的是什麼。一個樣本是 11 個交易日,第 6 天是 t。模型只看前 6 天,也就是 t-5 到 t,這些在 t 日收盤時都已經知道;後 5 天只用來貼標籤,模型看不到。每天取 5 個特徵:開、高、低、收都除以 t 日收盤,量除以 10 日均量。t 日收盤除以自己永遠是 1,所以拿掉,總共 29 個數字。表上是台積電 2024-09-26 的實際數字:前 5 天的價格都在 t 日收盤下方,代表一路往上收到 t 日。訓練時 50 檔股票放在一起,不是每檔一個模型:候選日裡真的是高點的 3,769 天訓練高點模型,真的是低點的 3,651 天訓練低點模型,總共只有 2 組。模型不知道樣本是哪一檔股票,因為價格都除以 t 日收盤、量都除以 10 日均量,不同股票可以放在一起比。");

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
  "訓練樣本:50 檔合在一起,2020–2023 候選中的真高點 3,769 天、真低點 3,651 天;高點、低點各一組 AE + OC-SVM",
  "樣本權重:距離 3 以內的相似候選中,同樣是真高(低)點的比例(沿用原系統的「重要性」概念)",
  "編碼器只有一層 29 → 16(973 個參數);原系統 29 → 58 → 8 → 4 有 4,637 個,兩者結果相同;OC-SVM 的 rbf、nu 0.1 沿用原系統",
], 15), { x: 0.6, y: 4.6, w: 12.1, h: 1.9, color: C.text2 });
s.addNotes("模型沿用我們原本系統的 AE 加 OC-SVM。AE 的輸入是 t-5 到 t 六根 K 線的 29 個數字:每天的開高低收都除以 t 日收盤(t 日收盤自己固定是 1,所以拿掉),每天的量除以 10 日均量。AE 只用一層、不先升維,直接把這 29 個數字壓成 16 維,OC-SVM 在這 16 維空間裡圈出真高點候選的範圍。測試時,候選點落在範圍內就保留,否則改判非極值。高點和低點各訓練一組。");

// ───────────────────────── 三分類流程圖 ─────────────────────────
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("三分類怎麼來:規則分流,兩個 OC-SVM 各判一種", { placeholder: "title" });
const ln = (x, y, w, h, arrow, name) => s.addShape(pres.shapes.LINE, { x, y, w, h,
  line: { color: HEX.accent5, width: 1.25, ...(arrow ? { endArrowType: "triangle" } : {}) }, objectName: name });
const node = (x, y, w, h, fill, lines, ink, name) => {
  card(s, x, y, w, h, fill, name);
  T(s, lines.map(([t, o], i) => ({ text: t, options: { breakLine: i < lines.length - 1, ...o } })),
    { x, y, w, h, align: "center", valign: "middle", color: ink || C.text1 });
};
const YT = 1.9, YM = 3.65, YB = 5.4;                       // 三條分支的中線
node(0.6, YM - 0.55, 1.9, 1.1, C.background2, [["t 日收盤後", { bold: true, fontSize: 15 }], ["算出 29 個數字", { fontSize: 12, color: C.text2 }]], null, "flow-start");
ln(2.5, YM, 0.5, 0, true, "flow-a1");
node(3.0, YM - 0.8, 2.4, 1.6, C.text1, [["規則", { bold: true, fontSize: 16 }], ["t 日收盤在近 6 天", { fontSize: 12 }], ["(t-5 ~ t)是…", { fontSize: 12 }]], C.background1, "flow-rule");
ln(5.4, YM, 0.3, 0, false, "flow-a2");
ln(5.7, YT, 0, YB - YT, false, "flow-trunk");
[YT, YM, YB].forEach((y, j) => ln(5.7, y, 0.3, 0, true, `flow-b${j}`));
node(6.0, YT - 0.5, 2.2, 1.0, C.background2, [["最高 → 高點候選", { bold: true, color: C.accent1, fontSize: 14 }], ["3,217 天", { fontSize: 12, color: C.text2 }]], null, "cand-high");
node(6.0, YM - 0.5, 2.2, 1.0, C.background2, [["都不是", { bold: true, fontSize: 14 }], ["5,865 天", { fontSize: 12, color: C.text2 }]], null, "cand-none");
node(6.0, YB - 0.5, 2.2, 1.0, C.background2, [["最低 → 低點候選", { bold: true, color: C.accent2, fontSize: 14 }], ["3,016 天", { fontSize: 12, color: C.text2 }]], null, "cand-low");
ln(8.2, YT, 0.4, 0, true, "flow-c1");
ln(8.2, YB, 0.4, 0, true, "flow-c3");
node(8.6, YT - 0.5, 1.9, 1.0, C.text1, [["高點 OC-SVM", { bold: true, fontSize: 14 }], ["只學過真高點", { fontSize: 11 }]], C.background1, "ocsvm-high");
node(8.6, YB - 0.5, 1.9, 1.0, C.text1, [["低點 OC-SVM", { bold: true, fontSize: 14 }], ["只學過真低點", { fontSize: 11 }]], C.background1, "ocsvm-low");
ln(8.2, YM, 2.65, 0, true, "flow-c2");
T(s, "不經過模型", { x: 8.6, y: YM - 0.4, w: 1.9, h: 0.3, fontSize: 11, color: C.accent5, align: "center" });
const chip = (y, fill, ink, text, name) => {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 10.85, y: y - 0.25, w: 1.88, h: 0.5, fill: { color: fill }, line: { color: fill }, rectRadius: 0.06, objectName: name });
  T(s, text, { x: 10.85, y: y - 0.25, w: 1.88, h: 0.5, fontSize: 12, bold: true, color: ink, align: "center", valign: "middle" });
};
[[YT, C.accent1, "範圍內:高點 2,638"], [YB, C.accent2, "範圍內:低點 2,591"]].forEach(([y, col, inside], j) => {
  ln(10.5, y, 0.12, 0, false, `fork-${j}`);
  ln(10.62, y - 0.3, 0, 0.6, false, `fork-v-${j}`);
  ln(10.62, y - 0.3, 0.23, 0, true, `fork-in-${j}`);
  ln(10.62, y + 0.3, 0.23, 0, true, `fork-out-${j}`);
  chip(y - 0.3, col, C.background1, inside, `out-in-${j}`);
  chip(y + 0.3, C.background2, C.text1, `範圍外:非極值 ${j ? "425" : "579"}`, `out-out-${j}`);
});
chip(YM, C.background2, C.text1, "非極值 5,865", "out-none");
T(s, [
  { text: "高點候選只會變成高點或非極值,低點候選只會變成低點或非極值,", options: { color: C.text2 } },
  { text: "所以高低點互相判錯 0 次是流程保證的。", options: { bold: true } },
  { text: "數字為 2024 測試期 12,098 天(種子 42)。", options: { color: C.accent5 } },
], { x: 0.6, y: 6.2, w: 12.1, h: 0.55, fontSize: 13, valign: "middle" });
s.addNotes("這頁回答 OC-SVM 只能分兩類,為什麼我們能做三分類。每個 OC-SVM 只回答一件事:這個樣本落不落在它圈出的範圍裡。三分類是規則加兩個 OC-SVM 組出來的:t 日收盤如果是近 6 天最高,就是高點候選,交給只學過真高點的高點 OC-SVM,範圍內判高點,範圍外判非極值;如果是近 6 天最低,就交給低點 OC-SVM;都不是就直接判非極值,不經過模型。一天不可能同時是近 6 天最高和最低,所以每天最多只問一個模型。2024 年 12,098 天裡,高點候選 3,217 天、低點候選 3,016 天,其餘 5,865 天直接判非極值。");

// ───────────────────────── 9. 混淆矩陣 ─────────────────────────
sec = S("結果");
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("測試結果:真高低點幾乎都在模型的判斷裡", { placeholder: "title" });
const cm = [[771, 142, 0], [1820, 6562, 1907], [0, 165, 731]];
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
  ["全猜非極值", "85.0%", "30.6%", "85.0%"],
  ["規則基準", "63.4%", "54.2%", "100.0%"],
  ["規則 + AE + OC-SVM", "66.7%", "54.0%", "95.5%"],
].map((r, i) => i === 0 ? r : r.map((c, j) => ({ text: c, options: { align: j ? "right" : "left", bold: i === 3 } })));
s.addTable(mRows, { x: 7.6, y: 1.6, w: 5.1, colW: [2.0, 0.9, 1.1, 1.1], rowH: 0.55, fontSize: 13, fontFace: THEME.bodyFontFace,
  color: HEX.dk1, valign: "middle", border: { type: "solid", pt: 0.75, color: "D9E0E6" }, margin: [0, 0.08, 0, 0.08] });
T(s, bullets([
  "真高點 896 個:判對 731 個(81.6%),沒有一個被判成低點",
  "真低點 913 個:判對 771 個(84.4%),沒有一個被判成高點",
  "判非極值的 6,869 天中,6,562 天真的不是高低點(95.5%)",
], 13), { x: 7.6, y: 3.95, w: 5.1, h: 2.2, color: C.text2 });
s.addNotes("這是 2024 年測試期的混淆矩陣。看第一列和最後一列:真低點有 84.4% 被判成低點,真高點有 81.6% 被判成高點,而且高點和低點從來不會互相判錯。右邊的表比較三種做法,模型的 acc 是 66.7%,判非極值時 95.5% 正確。");

// ───────────────────────── 10. 局部準確度 ─────────────────────────
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
s.addText("局部準確度:挑出的候選比亂猜準 3.7–3.9 倍", { placeholder: "title" });
s.addChart(pres.charts.BAR, [
  { name: "隨機挑一天", labels: ["高點", "低點"], values: [7.4, 7.5] },
  { name: "規則基準", labels: ["高點", "低點"], values: [27.8, 30.3] },
  { name: "規則 + AE + OC-SVM", labels: ["高點", "低點"], values: [27.7, 29.8] },
], { x: 0.6, y: 1.5, w: 7.2, h: 4.8, barDir: "col", barGrouping: "clustered", chartColors: [HEX.accent6, HEX.accent5, HEX.dk1],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', dataLabelColor: HEX.dk2, dataLabelFontSize: 12,
  dataLabelFontFace: "+mn-lt", showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt", legendColor: HEX.dk2,
  catAxisLabelColor: HEX.dk2, catAxisLabelFontSize: 14, catAxisLabelFontFace: "+mn-lt", valAxisHidden: true, valAxisMaxVal: 40,
  valAxisMinVal: 0, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showTitle: true,
  title: "命中率:判成高(低)點的日子中真的是高(低)點", titleFontSize: 14, titleColor: HEX.dk1, titleFontFace: "+mn-lt",
  barGapWidthPct: 60, objectName: "precision-chart" });
const loc = [
  ["99.9% / 100%", "規則找到的真高點 / 真低點", C.accent1],
  ["81.6% / 84.4%", "模型判對的真高點 / 真低點", C.accent2],
  ["95.5%", "模型判非極值時的正確率", C.accent3],
];
loc.forEach(([v, k, col], j) => {
  const y = 1.6 + j * 1.6;
  card(s, 8.2, y, 4.5, 1.4, C.background2, `loc-${j}`);
  T(s, v, { x: 8.45, y: y + 0.15, w: 4.1, h: 0.65, fontSize: 28, bold: true, color: col });
  T(s, k, { x: 8.45, y: y + 0.82, w: 4.1, h: 0.45, fontSize: 13, color: C.text2 });
});
s.addNotes("這頁是我們說的局部準確度。左圖是命中率:隨機挑一天是高點的機率只有 7.4%,被我們挑出來的候選是 28 到 30%,大約是 3.7 到 3.9 倍。右邊三個數字:真高低點 1,809 個只有 1 個沒進候選,模型判對 82 到 84%,判非極值時 95.5% 正確。");

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
  ["99.9%", "真高低點進了候選", "高點 895 / 896\n低點 913 / 913", C.accent1],
  ["0 次", "高點與低點互相判錯", "真高點沒被判成低點,\n真低點沒被判成高點", C.background1],
  ["95.5%", "判「非極值」的正確率", "6,869 天裡 6,562 天\n真的不是高低點", C.accent3],
  ["3.7–3.9×", "命中率是隨機挑的倍數", "高點 7.4% → 27.7%\n低點 7.5% → 29.8%", C.accent2],
];
wins.forEach(([v, k, d, col], j) => {
  const x = 0.8 + j * 2.95;
  T(s, v, { x, y: 3.9, w: 2.75, h: 0.95, fontSize: 40, bold: true, color: col, valign: "middle" });
  T(s, k, { x, y: 4.9, w: 2.75, h: 0.45, fontSize: 16, bold: true, color: C.background1 });
  T(s, d, { x, y: 5.4, w: 2.75, h: 0.9, fontSize: 13, color: C.accent6 });
});
T(s, "測試期 2024-01 ~ 2024-12 · TW50 · 12,098 個股票日;模型判對 81.6% 的真高點、84.4% 的真低點",
  { x: 0.8, y: 6.6, w: 11.7, h: 0.4, fontSize: 13, color: C.accent5 });
s.addNotes("總結。我們把題目定成找 11 天窗口裡的局部高低點,在 TW50 的 2024 年測試期:真高低點 1,809 個只有 1 個沒進候選;模型判出的高點和低點從來不會互相搞錯;模型說「這天不是高低點」時 95.5% 是對的;挑出來的候選是真高低點的機率是隨便挑一天的 3.7 到 3.9 倍。模型最後判對了 82% 的真高點和 84% 的真低點。謝謝。");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
