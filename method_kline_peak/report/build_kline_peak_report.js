// 台股 11 天局部高低點三分類 — 回測結果與下一步(pptxgenjs,結構化:主題 + 版面 + 區段)
// 數字全部抄自 results/backtest_long_only_tw50.json 與 results/outputs_2379_2024.png 的圖例。
// 執行:PPTX_SKILL=<pptx skill 目錄> node report/build_kline_peak_report.js [輸出路徑]
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const HERE = __dirname;
const OUT = process.argv[2] || path.join(HERE, "kline_peak_report.pptx");

const THEME = {
  name: "Kline Peak Report",
  headFontFace: "Microsoft JhengHei",
  bodyFontFace: "Microsoft JhengHei",
  colors: {
    dk1: "13202A", lt1: "FFFFFF", dk2: "47545F", lt2: "EEF2F5",
    accent1: "EB6834",   // 高點
    accent2: "2A78D6",   // 低點
    accent3: "0B7A75",   // 主軸
    accent4: "6250D6",   // Stacking
    accent5: "7A8691",   // 次要文字
    accent6: "C9D2D9",   // 中性
    hlink: "2A78D6", folHlink: "6250D6",
  },
};
const HEX = THEME.colors;
const LIGHT = { main: "93D1CD", stack: "C2BAF0" };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33" × 7.5"
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "台股 11 天局部高低點三分類";
pres.author = "fcukproject";
const C = pres.SchemeColor;

// 版面記號:11 個小方塊,第 6 個(t)上色
const motif = (x0, y0, s, gap) => Array.from({ length: 11 }, (_, k) => ({
  rect: { x: x0 + k * (s + gap), y: y0, w: s, h: s, fill: { color: k === 5 ? C.accent1 : C.accent6 } },
}));

pres.defineSlideMaster({
  title: "DARK",
  background: { color: HEX.dk1 },
  objects: [
    ...motif(0.8, 1.55, 0.22, 0.07),
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.1, w: 11.7, h: 1.6, fontSize: 40, bold: true, align: "left",
      color: C.background1, valign: "top", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.9, w: 11.7, h: 2.6, fontSize: 18, align: "left",
      color: C.background2, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: HEX.lt1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    ...motif(11.1, 0.62, 0.11, 0.035),
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 10.3, h: 0.85, fontSize: 30, bold: true, align: "left",
      color: C.text1, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "台股 11 天局部高低點三分類 · 2026-11", options: { x: 0.6, y: 6.95, w: 6, h: 0.3, fontSize: 10,
      color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.25, y: 6.95, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent5, align: "right" },
});

const T = (slide, text, o) => slide.addText(text, { isTextBox: true, margin: 0, fontSize: 15, color: C.text1, valign: "top", ...o });
const card = (slide, o) => slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { rectRadius: 0.08, fill: { color: C.background2 },
  line: { type: "none" }, ...o });
const bullets = (items, o = {}) => items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1,
  paraSpaceAfter: 8, ...o } }));

// ---------- 資料(抄自 backtest_long_only_tw50.json) ----------
const BT = {
  "2024": { main: { net: [-28.83, -33.35, 144, 41.0, -0.68], gross: [-5.82, -17.35, 144, 49.3, -0.1] },
            stack: { net: [-30.22, -30.22, 141, 42.6, -0.71], gross: [-8.19, -18.24, 141, 47.5, -0.13] } },
  "2025": { main: { net: [-41.72, -45.08, 141, 39.0, -1.12], gross: [-23.32, -31.2, 141, 48.2, -0.54] },
            stack: { net: [-18.6, -24.27, 138, 47.8, -0.39], gross: [6.52, -20.16, 138, 53.6, 0.2] } },
  "2026": { main: { net: [15.95, -10.86, 94, 46.8, 0.51], gross: [39.31, -8.19, 94, 54.3, 1.1] },
            stack: { net: [9.95, -19.8, 97, 53.6, 0.36], gross: [32.76, -17.64, 97, 58.8, 0.95] } },
};
const pct = (v) => (v > 0 ? "+" : "") + v.toFixed(2).replace(/0$/, "").replace(/\.$/, "") + "%";
const fmtPct = (v) => (v > 0 ? "+" : "") + String(v) + "%";

// ======================= 1. 封面 =======================
pres.addSection({ title: "開場" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "開場" });
s.addText("台股 11 天局部高低點三分類\n回測結果與下一步", { placeholder: "title" });
s.addText([
  { text: "台灣50 只做多回測(2024、2025、2026 至 9/11)", options: { breakLine: true } },
  { text: "瑞昱 2379 個案:真實高低點 vs 兩方法判斷", options: { breakLine: true } },
  { text: "下一步:輸入股票代號 → 系統輸出建議" },
], { placeholder: "body" });
s.addNotes("本報告整理兩個方法在台灣50 的只做多回測結果、瑞昱 2024 的個案,以及下一步改成決策輔助工具的規劃。數字都來自 repo 內既有的結果檔,沒有重跑。");

// ======================= 2. 問題與標籤定義 =======================
pres.addSection({ title: "方法" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "方法" });
s.addText("問題與標籤定義", { placeholder: "title" });
T(s, "每天、每檔股票分成三類", { x: 0.6, y: 1.5, w: 5.4, h: 0.45, fontSize: 20, bold: true });
T(s, bullets([
  "取 11 天視窗,t = 第 6 天(前 5 天 + t + 後 5 天)",
  "t 的收盤是 11 天最高 → 高點",
  "t 的收盤是 11 天最低 → 低點",
  "其他 → 非極值",
  "標籤要看到 t 之後 5 天,所以只能用來訓練與評估;實際判斷時只能用 t 當天以前的資料",
]), { x: 0.6, y: 2.1, w: 5.4, h: 4.3, fontSize: 16 });

// 示意:11 根收盤,t 最高
const closes = [52, 55, 58, 63, 70, 82, 74, 66, 60, 57, 54];
const bx = 6.8, by = 1.75, bw = 0.42, gap = 0.12, base = 5.4, scale = 0.036;
card(s, { x: 6.5, y: 1.45, w: 6.25, h: 5.15, objectName: "label-demo-card" });
closes.forEach((c, k) => {
  const h = c * scale;
  s.addShape(pres.shapes.RECTANGLE, { x: bx + k * (bw + gap), y: base - h, w: bw, h, objectName: `bar-${k}`,
    fill: { color: k === 5 ? C.accent1 : C.accent6 }, line: { type: "none" } });
  T(s, k === 5 ? "t" : (k < 5 ? `t-${5 - k}` : `t+${k - 5}`), { x: bx + k * (bw + gap) - 0.05, y: base + 0.08, w: bw + 0.1,
    h: 0.3, fontSize: 11, align: "center", color: k === 5 ? C.accent1 : C.accent5, bold: k === 5 });
});
T(s, "▼ 高點:t 收盤是 11 天最高", { x: bx, y: by, w: 5.6, h: 0.4, fontSize: 15, bold: true, color: C.accent1 });
T(s, "示意圖(數值為虛構):長條高度 = 收盤價", { x: bx, y: 5.95, w: 5.6, h: 0.35, fontSize: 11, color: C.accent5 });
s.addNotes("標籤定義:11 天視窗,t 為第 6 天。t 的收盤是 11 天最高就標高點、最低就標低點,其餘為非極值。右圖只是示意,數值是虛構的。");

// ======================= 3. 兩個方法 + 訓練方式 =======================
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "方法" });
s.addText("兩個方法與訓練方式", { placeholder: "title" });
// 特徵條
card(s, { x: 0.6, y: 1.45, w: 12.15, h: 0.95, fill: { color: C.background2 }, objectName: "feat-card" });
T(s, "特徵 29 維", { x: 0.85, y: 1.55, w: 2.2, h: 0.75, fontSize: 18, bold: true, valign: "middle" });
T(s, "t-5 ~ t 共 6 根 K 線:開、高、低、收 ÷ t 收盤 取 log;成交量 ÷ 10 日均量 取 log", {
  x: 3.1, y: 1.55, w: 9.4, h: 0.75, fontSize: 15, valign: "middle" });
// 兩方法卡片
const mcard = (x, color, num, name, lines) => {
  card(s, { x, y: 2.7, w: 5.95, h: 2.75, fill: { color: C.background1 }, line: { color: HEX.accent6, width: 1 },
    objectName: `method-${num}` });
  s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: 2.92, w: 0.55, h: 0.55, fill: { color }, line: { type: "none" } });
  T(s, num, { x: x + 0.25, y: 2.92, w: 0.55, h: 0.55, fontSize: 18, bold: true, color: C.background1, align: "center", valign: "middle" });
  T(s, name, { x: x + 0.95, y: 2.92, w: 4.8, h: 0.55, fontSize: 20, bold: true, valign: "middle" });
  T(s, bullets(lines), { x: x + 0.3, y: 3.65, w: 5.4, h: 1.7, fontSize: 15 });
};
mcard(0.6, C.accent3, "1", "主軸", [
  "規則先挑候選(t 收盤是 t-5 ~ t 最高 / 最低)",
  "每類一組線性 AE + OC-SVM,把不像的候選改判非極值",
]);
mcard(6.8, C.accent4, "2", "Stacking 邏輯迴歸", [
  "把兩組 AE / OC-SVM 的分數當輸入",
  "再用邏輯迴歸做三分類",
]);
// 訓練方式
T(s, [
  { text: "訓練方式:", options: { bold: true } },
  { text: "walk-forward,用前 4 年訓練、測下一年(2024、2025、2026 各一次),種子 42" },
], { x: 0.6, y: 5.75, w: 12.15, h: 0.5, fontSize: 16 });
s.addNotes("兩個方法用同一組 29 維特徵。主軸是規則候選加上每類一組線性 AE 與 OC-SVM;Stacking 把 AE/OC-SVM 的分數交給邏輯迴歸。walk-forward,前 4 年訓練、測下一年,種子 42。");

// ======================= 4. 回測規則 =======================
pres.addSection({ title: "台灣50 回測" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "台灣50 回測" });
s.addText("台灣50 回測規則", { placeholder: "title" });
const steps = [
  ["t 收盤後", "50 檔中判「低點」的,取分數最高的前 3 檔"],
  ["t+1 開盤", "買進,每檔 1/3 資金"],
  ["t+5 收盤", "賣出"],
];
steps.forEach(([h, d], i) => {
  const x = 0.6 + i * 4.15;
  card(s, { x, y: 1.5, w: 3.75, h: 2.0, objectName: `step-${i}` });
  T(s, h, { x: x + 0.3, y: 1.7, w: 3.2, h: 0.5, fontSize: 20, bold: true, color: C.accent2 });
  T(s, d, { x: x + 0.3, y: 2.3, w: 3.2, h: 1.1, fontSize: 15 });
  if (i < 2) T(s, "→", { x: x + 3.78, y: 2.2, w: 0.35, h: 0.6, fontSize: 24, bold: true, color: C.accent5, align: "center" });
});
const facts = [
  ["只做多", "判高點不放空"],
  ["成本 0.585%", "買 0.1425% + 賣 0.1425% + 證交稅 0.3%"],
  ["資金", "每年獨立 100 萬,年底結清"],
  ["其他假設", "漲停也算買得到;2026 年只到 9/11"],
];
facts.forEach(([h, d], i) => {
  const x = 0.6 + (i % 2) * 6.15, y = 3.95 + Math.floor(i / 2) * 1.25;
  T(s, h, { x, y, w: 2.2, h: 0.9, fontSize: 18, bold: true, valign: "middle" });
  T(s, d, { x: x + 2.3, y, w: 3.6, h: 0.9, fontSize: 15, valign: "middle", color: C.text2 });
});
s.addNotes("每天收盤後在台灣50 中挑判低點、分數最高的 3 檔,隔天開盤買、第 5 天收盤賣,每檔三分之一資金。一筆來回成本 0.585%。每年獨立 100 萬、年底結清;漲停也當作買得到;2026 只到 9 月 11 日。");

// ======================= 5. 結果表格 =======================
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "台灣50 回測" });
s.addText("台灣50 回測結果:報酬、回撤、筆數、勝率", { placeholder: "title" });
const hdr = (t, o = {}) => ({ text: t, options: { bold: true, fill: { color: HEX.dk1 }, color: "FFFFFF", align: "center", valign: "middle", ...o } });
const cell = (t, o = {}) => ({ text: String(t), options: { align: "center", valign: "middle", ...o } });
const valCell = (v, o = {}) => cell(fmtPct(v), { color: v < 0 ? "C0392B" : (v > 0 ? "1E7B34" : HEX.dk1), ...o });
const rows = [
  [hdr("年份", { rowspan: 2 }), hdr("方法", { rowspan: 2 }), hdr("扣成本", { colspan: 3 }), hdr("沒扣成本", { colspan: 3 }), hdr("交易筆數", { rowspan: 2 })],
  [hdr("總報酬"), hdr("最大回撤"), hdr("勝率"), hdr("總報酬"), hdr("最大回撤"), hdr("勝率")],
];
const yearLabel = { "2024": "2024", "2025": "2025", "2026": "2026\n(至 9/11)" };
["2024", "2025", "2026"].forEach((y, yi) => {
  [["main", "主軸"], ["stack", "Stacking 邏輯迴歸"]].forEach(([k, name], mi) => {
    const r = BT[y][k], fill = { color: yi % 2 === 0 ? HEX.lt1 : HEX.lt2 };
    const row = [];
    if (mi === 0) row.push(cell(yearLabel[y], { rowspan: 2, bold: true, fill }));
    row.push(cell(name, { fill, align: "left" }));
    row.push(valCell(r.net[0], { fill, bold: true }), valCell(r.net[1], { fill }), cell(r.net[3] + "%", { fill }));
    row.push(valCell(r.gross[0], { fill, bold: true }), valCell(r.gross[1], { fill }), cell(r.gross[3] + "%", { fill }));
    row.push(cell(r.net[2], { fill }));
    rows.push(row);
  });
});
s.addTable(rows, { x: 0.6, y: 1.45, w: 12.15, colW: [1.35, 2.6, 1.25, 1.25, 1.1, 1.25, 1.25, 1.1, 1.0],
  rowH: [0.42, 0.42, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6], fontSize: 14, fontFace: THEME.bodyFontFace, color: HEX.dk1,
  border: { type: "solid", pt: 0.75, color: HEX.accent6 } });
T(s, "資料:results/backtest_long_only_tw50.json(50 檔)。交易筆數扣不扣成本相同。最大回撤為負值;紅 = 負、綠 = 正。", {
  x: 0.6, y: 6.25, w: 12.15, h: 0.4, fontSize: 11, color: C.accent5 });
s.addNotes("表格數字直接抄自 backtest_long_only_tw50.json。扣成本和沒扣成本的交易筆數一樣,差別只在每筆扣 0.585%。");

// ======================= 6. 長條圖 + 解讀 =======================
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "台灣50 回測" });
s.addText("結果解讀:成本吃掉大部分報酬", { placeholder: "title" });
const years = ["2024", "2025", "2026(至 9/11)"];
const ser = (name, k, which) => ({ name, labels: years, values: ["2024", "2025", "2026"].map((y) => BT[y][k][which][0]) });
s.addChart(pres.charts.BAR, [
  ser("主軸 扣成本", "main", "net"), ser("主軸 沒扣成本", "main", "gross"),
  ser("Stacking 扣成本", "stack", "net"), ser("Stacking 沒扣成本", "stack", "gross"),
], {
  x: 0.5, y: 1.4, w: 7.3, h: 5.35, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60,
  chartColors: [HEX.accent3, LIGHT.main, HEX.accent4, LIGHT.stack],
  showTitle: true, title: "總報酬(%)", titleFontSize: 13, titleColor: HEX.dk2, titleFontFace: "+mn-lt",
  showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 9, dataLabelColor: HEX.dk2, dataLabelFontFace: "+mn-lt",
  dataLabelFormatCode: "0.0",
  catAxisLabelColor: HEX.dk2, valAxisLabelColor: HEX.accent5, catAxisLabelFontSize: 12, valAxisLabelFontSize: 10,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", catAxisLabelPos: "low",
  valGridLine: { color: "E3E8EC", size: 0.75 }, catGridLine: { style: "none" },
  showLegend: true, legendPos: "b", legendFontSize: 11, legendFontFace: "+mn-lt", legendColor: HEX.dk2,
});
T(s, "只看 json 的事實", { x: 8.2, y: 1.45, w: 4.55, h: 0.45, fontSize: 18, bold: true });
T(s, bullets([
  "每年約 140 筆(2024:144 / 141;2025:141 / 138),每筆成本 0.585%",
  "每筆平均報酬:主軸 2024 沒扣 -0.1% → 扣後 -0.68%;Stacking 2025 沒扣 +0.2% → 扣後 -0.39%",
  "2024、2025 兩方法扣成本都虧損;主軸 2025 扣成本 -41.72%,最大回撤 -45.08%",
  "Stacking 2025 沒扣成本 +6.52%,扣成本變 -18.6%",
  "2026(至 9/11)扣成本後為正:主軸 +15.95%、Stacking +9.95%",
]), { x: 8.2, y: 2.0, w: 4.55, h: 4.7, fontSize: 14 });
s.addNotes("長條圖比較兩方法三年的總報酬,深色是扣成本、淺色是沒扣成本。每年約 140 筆交易、每筆 0.585%,所以扣成本前後差距很大。2024、2025 扣成本都虧,2026 到 9/11 為正。");

// ======================= 7–8. 瑞昱 =======================
pres.addSection({ title: "瑞昱 2024" });
const realtek = (title, imgKey, label, hi, lo, color, note) => {
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "瑞昱 2024" });
  sl.addText(title, { placeholder: "title" });
  const iw = 9.3, ih1 = iw * 458 / 2335, ih2 = iw * (imgKey === "stacking" ? 489 : 454) / 2335;
  T(sl, "真實標籤(11 天收盤最高 / 最低)", { x: 0.6, y: 1.35, w: iw, h: 0.35, fontSize: 13, bold: true, color: C.text2 });
  sl.addImage({ path: path.join(HERE, "kline_peak_2379_true.png"), x: 0.6, y: 1.72, w: iw, h: ih1,
    altText: "瑞昱 2379 2024 收盤與真實高低點" });
  const y2 = 1.72 + ih1 + 0.3;
  T(sl, label, { x: 0.6, y: y2, w: iw, h: 0.35, fontSize: 13, bold: true, color });
  sl.addImage({ path: path.join(HERE, `kline_peak_2379_${imgKey}.png`), x: 0.6, y: y2 + 0.37, w: iw, h: ih2,
    altText: `瑞昱 2379 2024 ${label}` });
  // 右側數字
  const rx = 10.25, rw = 2.5;
  card(sl, { x: rx, y: 1.35, w: rw, h: 1.25, objectName: "truth-card" });
  T(sl, "真實", { x: rx + 0.2, y: 1.45, w: rw - 0.4, h: 0.3, fontSize: 12, color: C.accent5 });
  T(sl, [{ text: "高點 18", options: { color: C.accent1, breakLine: true } }, { text: "低點 19", options: { color: C.accent2 } }],
    { x: rx + 0.2, y: 1.78, w: rw - 0.4, h: 0.75, fontSize: 18, bold: true });
  const stat = (y, head, ok, ng, col) => {
    card(sl, { x: rx, y, w: rw, h: 1.45, objectName: `stat-${head}` });
    T(sl, head, { x: rx + 0.2, y: y + 0.1, w: rw - 0.4, h: 0.3, fontSize: 12, color: C.accent5 });
    T(sl, [{ text: "對 " + ok, options: { color: col, breakLine: true } }, { text: "錯 " + ng, options: { color: C.accent5 } }],
      { x: rx + 0.2, y: y + 0.42, w: rw - 0.4, h: 0.95, fontSize: 22, bold: true });
  };
  stat(2.8, "判高點 ▼", hi[0], hi[1], C.accent1);
  stat(4.45, "判低點 ▲", lo[0], lo[1], C.accent2);
  T(sl, note, { x: 0.6, y: 6.3, w: 12.15, h: 0.55, fontSize: 11, color: C.accent5 });
  return sl;
};
const NOTE = "34 檔模型的輸出(台灣50 剔除 16 檔低波動股)。實心 = 判對、空心 = 判錯;綠色區間 = 回測持有期間,上方數字 = 該筆扣成本報酬。x 軸為 2024/01–12。來源:results/outputs_2379_2024.png";
s = realtek("瑞昱 2024:真實高低點 vs 主軸", "mainline", "主軸:判低點 45 天、判高點 52 天", [16, 36], [16, 29], C.accent3, NOTE);
s.addNotes("上方是真實標籤:真高點 18 個、真低點 19 個。下方是主軸的判斷:判高點對 16 錯 36,判低點對 16 錯 29。主軸判出的高低點比真實多很多,錯的比對的多。這張圖是 34 檔模型的輸出。");
s = realtek("瑞昱 2024:真實高低點 vs Stacking", "stacking", "Stacking 邏輯迴歸:判低點 40 天、判高點 42 天", [11, 31], [14, 26], C.accent4, NOTE);
s.addNotes("Stacking 的判斷:判高點對 11 錯 31,判低點對 14 錯 26。判的天數比主軸少,但判對的也比較少。這張圖同樣是 34 檔模型的輸出。");

// ======================= 9. 下一步 =======================
pres.addSection({ title: "下一步" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "下一步" });
s.addText("下一步:輸入股票代號 → 系統輸出建議", { placeholder: "title" });
// 流程
const flow = [
  ["輸入", "使用者在網頁輸入股票代號"],
  ["判斷", "模型用到今天為止的 K 線判斷"],
  ["輸出", "今天是 高點 / 低點 / 非極值,附信心值與建議"],
];
flow.forEach(([h, d], i) => {
  const x = 0.6 + i * 4.15;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.5, w: 3.75, h: 1.75, rectRadius: 0.08,
    fill: { color: i === 2 ? HEX.dk1 : HEX.lt2 }, line: { type: "none" }, objectName: `flow-${i}` });
  T(s, h, { x: x + 0.3, y: 1.65, w: 3.2, h: 0.45, fontSize: 20, bold: true, color: i === 2 ? C.background1 : C.accent2 });
  T(s, d, { x: x + 0.3, y: 2.15, w: 3.2, h: 1.0, fontSize: 15, color: i === 2 ? C.background1 : C.text1 });
  if (i < 2) T(s, "→", { x: x + 3.78, y: 2.05, w: 0.35, h: 0.6, fontSize: 24, bold: true, color: C.accent5, align: "center" });
});
// 兩欄說明
T(s, "訓練資料改用台灣100", { x: 0.6, y: 3.65, w: 5.9, h: 0.45, fontSize: 18, bold: true });
T(s, bullets([
  "TW100 有資料的 95 檔,用同一門檻剔除低波動後剩 73 檔",
  "目的:收集更多高點 / 低點標籤來訓練(目前 34 檔)",
]), { x: 0.6, y: 4.2, w: 5.9, h: 2.2, fontSize: 15 });
T(s, "為什麼改成決策輔助", { x: 6.85, y: 3.65, w: 5.9, h: 0.45, fontSize: 18, bold: true });
T(s, bullets([
  "純回測的資產曲線可能不好看:2024、2025 扣成本都虧損",
  "改成工具:使用者自己決定要不要交易,系統提供判斷與信心值",
]), { x: 6.85, y: 4.2, w: 5.9, h: 2.2, fontSize: 15 });
s.addNotes("下一步把系統改成決策輔助工具:使用者在網頁輸入股票代號,系統回答今天是高點、低點或非極值,附信心值與建議。訓練資料擴大到台灣100,95 檔有資料,剔除低波動後 73 檔,目的是取得更多高低點標籤。");

// ======================= 10. 總結 =======================
s = pres.addSlide({ masterName: "DARK", sectionTitle: "下一步" });
s.addText("總結", { placeholder: "title" });
s.addText(bullets([
  "台灣50 只做多:每年約 140 筆,每筆 0.585% 成本,2024、2025 扣成本後兩方法都虧損,2026(至 9/11)為正",
  "瑞昱 2024:兩方法判出的高低點中,判錯多於判對",
  "下一步:用台灣100(73 檔)擴充標籤,做成「輸入代號 → 高 / 低 / 非極值 + 信心值」的網頁工具",
], { paraSpaceAfter: 14 }), { placeholder: "body" });
s.addNotes("總結三點:回測扣成本後 2024、2025 虧損;瑞昱個案判錯多於判對;下一步擴充資料並做成網頁決策輔助工具。");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
