// 台股 11 天局部高低點三分類 — 回測結果與下一步(pptxgenjs,結構化:主題 + 版面 + 區段)
// 數字全部抄自 results/backtest_long_only.json(34 檔) 與 results/outputs_2379_2024.png 的圖例。
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
  ],
  slideNumber: { x: 12.25, y: 6.95, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent5, align: "right" },
});

const T = (slide, text, o) => slide.addText(text, { isTextBox: true, margin: 0, fontSize: 15, color: C.text1, valign: "top", ...o });
const card = (slide, o) => slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { rectRadius: 0.08, fill: { color: C.background2 },
  line: { type: "none" }, ...o });
const bullets = (items, o = {}) => items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1,
  paraSpaceAfter: 8, ...o } }));

// ---------- 資料(抄自 backtest_long_only.json,34 檔、訓練門檻 0%) ----------
// [總報酬, 最大回撤, 交易筆數, 勝率, 每筆平均報酬]
const BT = {
  "2024": { main: { net: [-24.82, -28.23, 142, 44.4, -0.57], gross: [-0.94, -16.78, 142, 51.4, 0.02] },
            stack: { net: [-45.02, -45.92, 137, 38.0, -1.24], gross: [-28.22, -37.02, 137, 43.1, -0.66] } },
  "2025": { main: { net: [-34.87, -36.81, 140, 41.4, -0.87], gross: [-14.51, -20.61, 140, 48.6, -0.29] },
            stack: { net: [-11.94, -32.01, 132, 50.0, -0.21], gross: [13.86, -27.63, 132, 56.1, 0.37] } },
  "2026": { main: { net: [0.09, -15.16, 94, 38.3, 0.06], gross: [20.19, -13.05, 94, 50.0, 0.65] },
            stack: { net: [0.5, -23.63, 88, 40.9, 0.09], gross: [19.18, -18.11, 88, 50.0, 0.68] } },
};
const fmtPct = (v) => (v > 0 ? "+" : "") + String(v) + "%";

// ======================= 1. 封面 =======================
pres.addSection({ title: "開場" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "開場" });
s.addText("台股 11 天局部高低點三分類\n回測結果與下一步", { placeholder: "title" });
s.addText([
  { text: "34 檔只做多回測(台灣50 剔除 16 檔低波動股;2024、2025、2026 至 9/11)", options: { breakLine: true } },
  { text: "瑞昱 2379 個案:真實高低點 vs 兩方法判斷", options: { breakLine: true } },
  { text: "下一步:輸入股票代號 → 系統輸出建議" },
], { placeholder: "body" });
s.addNotes("本報告整理兩個方法在 34 檔股票池(台灣50 剔除 16 檔低波動股)的只做多回測結果、瑞昱 2024 的個案,以及下一步改成決策輔助工具的規劃。數字都來自 repo 內既有的結果檔,沒有重跑。");

// ======================= 2. 兩個方法 + 訓練方式 =======================
pres.addSection({ title: "方法" });
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
pres.addSection({ title: "回測(34 檔)" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "回測(34 檔)" });
s.addText("回測規則", { placeholder: "title" });
const steps = [
  ["t 收盤後", "34 檔中判「低點」的,取分數最高的前 3 檔"],
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
  ["股票池", "34 檔(台灣50 剔除 16 檔低波動股)"],
  ["只做多", "判高點不放空"],
  ["成本 0.585%", "買 0.1425% + 賣 0.1425% + 證交稅 0.3%"],
  ["資金", "每年獨立 100 萬,年底結清"],
  ["其他假設", "漲停也算買得到;2026 年只到 9/11"],
  ["模型", "訓練門檻 0%(瑞昱個案圖同樣設定)"],
];
facts.forEach(([h, d], i) => {
  const x = 0.6 + (i % 2) * 6.15, y = 3.85 + Math.floor(i / 2) * 0.95;
  T(s, h, { x, y, w: 1.9, h: 0.8, fontSize: 18, bold: true, valign: "middle" });
  T(s, d, { x: x + 2.0, y, w: 3.95, h: 0.8, fontSize: 15, valign: "middle", color: C.text2 });
});
s.addNotes("股票池是 34 檔(台灣50 剔除 16 檔低波動股),和瑞昱個案的模型一致。每天收盤後在 34 檔中挑判低點、分數最高的 3 檔,隔天開盤買、第 5 天收盤賣,每檔三分之一資金。一筆來回成本 0.585%。每年獨立 100 萬、年底結清;漲停也當作買得到;2026 只到 9 月 11 日。");

// ======================= 5. 結果表格 =======================
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "回測(34 檔)" });
s.addText("回測結果:報酬、勝率、筆數", { placeholder: "title" });
const hdr = (t, o = {}) => ({ text: t, options: { bold: true, fill: { color: HEX.dk1 }, color: "FFFFFF", align: "center", valign: "middle", ...o } });
const cell = (t, o = {}) => ({ text: String(t), options: { align: "center", valign: "middle", ...o } });
const valCell = (v, o = {}) => cell(fmtPct(v), { color: v < 0 ? "C0392B" : (v > 0 ? "1E7B34" : HEX.dk1), ...o });
const rows = [
  [hdr("年份", { rowspan: 2 }), hdr("方法", { rowspan: 2 }), hdr("扣成本", { colspan: 2 }), hdr("沒扣成本", { colspan: 2 }), hdr("交易筆數", { rowspan: 2 })],
  [hdr("總報酬"), hdr("勝率"), hdr("總報酬"), hdr("勝率")],
];
const yearLabel = { "2024": "2024", "2025": "2025", "2026": "2026\n(至 9/11)" };
["2024", "2025", "2026"].forEach((y, yi) => {
  [["main", "主軸"], ["stack", "Stacking 邏輯迴歸"]].forEach(([k, name], mi) => {
    const r = BT[y][k], fill = { color: yi % 2 === 0 ? HEX.lt1 : HEX.lt2 };
    const row = [];
    if (mi === 0) row.push(cell(yearLabel[y], { rowspan: 2, bold: true, fill }));
    row.push(cell(name, { fill, align: "left" }));
    row.push(valCell(r.net[0], { fill, bold: true }), cell(r.net[3].toFixed(1) + "%", { fill }));
    row.push(valCell(r.gross[0], { fill, bold: true }), cell(r.gross[3].toFixed(1) + "%", { fill }));
    row.push(cell(r.net[2], { fill }));
    rows.push(row);
  });
});
s.addTable(rows, { x: 0.6, y: 1.45, w: 12.15, colW: [1.6, 3.0, 1.6, 1.4, 1.6, 1.4, 1.55],
  rowH: [0.45, 0.45, 0.68, 0.68, 0.68, 0.68, 0.68, 0.68], fontSize: 15, fontFace: THEME.bodyFontFace, color: HEX.dk1,
  border: { type: "solid", pt: 0.75, color: HEX.accent6 } });
s.addNotes("表格數字直接抄自 backtest_long_only.json(34 檔)。扣成本和沒扣成本的交易筆數一樣,差別只在每筆扣 0.585%。2024、2025 兩方法扣成本後都虧損;2026 到 9/11 沒扣成本主軸 +20.19%、Stacking +19.18%,扣成本後只剩 +0.09%、+0.5%。");

// ======================= 瑞昱(三段合併一頁) =======================
pres.addSection({ title: "瑞昱 2024" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "瑞昱 2024" });
s.addText("瑞昱 2024:真實高低點 vs 兩方法(34 檔模型)", { placeholder: "title" });
{
  const iw = 7.6, x0 = 0.6, lh = 0.28, gap = 0.08, rx = 8.55, rw = 4.2;
  const panels = [
    { key: "true", px: 458, label: "真實標籤(11 天收盤最高 / 最低)", color: C.text2,
      lines: [["真高點", "18 個", C.accent1], ["真低點", "19 個", C.accent2]] },
    { key: "mainline", px: 454, label: "① 主軸:判低點 45 天、判高點 52 天", color: C.accent3,
      lines: [["判高點", "對 16 / 錯 36", C.accent1], ["判低點", "對 16 / 錯 29", C.accent2]] },
    { key: "stacking", px: 489, label: "② Stacking 邏輯迴歸:判低點 40 天、判高點 42 天", color: C.accent4,
      lines: [["判高點", "對 11 / 錯 31", C.accent1], ["判低點", "對 14 / 錯 26", C.accent2]] },
  ];
  let y = 1.3;
  panels.forEach((p) => {
    const ih = iw * p.px / 2335;
    T(s, p.label, { x: x0, y, w: iw, h: lh, fontSize: 12, bold: true, color: p.color, valign: "middle" });
    s.addImage({ path: path.join(HERE, `kline_peak_2379_${p.key}.png`), x: x0, y: y + lh, w: iw, h: ih,
      altText: `瑞昱 2379 2024 ${p.label}` });
    const cy = y + lh, ch = ih;
    card(s, { x: rx, y: cy, w: rw, h: ch, objectName: `stat-${p.key}` });
    T(s, p.lines.map(([h, v, col], k) => [
      { text: h + "  ", options: { color: C.text2, fontSize: 15 } },
      { text: v, options: { color: col, bold: true, fontSize: 20, breakLine: k < p.lines.length - 1 } },
    ]).flat(), { x: rx + 0.3, y: cy + 0.1, w: rw - 0.5, h: ch - 0.2, valign: "middle", paraSpaceAfter: 6 });
    y += lh + ih + gap;
  });
}
s.addNotes("上段是真實標籤:真高點 18 個、真低點 19 個。中段是主軸:判高點對 16 錯 36,判低點對 16 錯 29。下段是 Stacking 邏輯迴歸:判高點對 11 錯 31,判低點對 14 錯 26。實心三角形是判對、空心是判錯,綠色區間是回測的持有期間。兩方法判出的高低點都比真實多,錯的比對的多;Stacking 判的天數比主軸少,判對的也比較少。這張圖是 34 檔模型的輸出(台灣50 剔除 16 檔低波動股)。");

// ======================= 5. 下一步 =======================
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
  "目前是 34 檔(台灣50 剔除 16 檔低波動股);目的是收集更多高點 / 低點標籤來訓練",
]), { x: 0.6, y: 4.2, w: 5.9, h: 2.2, fontSize: 15 });
T(s, "為什麼改成決策輔助", { x: 6.85, y: 3.65, w: 5.9, h: 0.45, fontSize: 18, bold: true });
T(s, bullets([
  "純回測的資產曲線可能不好看:2024、2025 扣成本都虧損",
  "改成工具:使用者自己決定要不要交易,系統提供判斷與信心值",
]), { x: 6.85, y: 4.2, w: 5.9, h: 2.2, fontSize: 15 });
s.addNotes("下一步把系統改成決策輔助工具:使用者在網頁輸入股票代號,系統回答今天是高點、低點或非極值,附信心值與建議。訓練資料擴大到台灣100,95 檔有資料,剔除低波動後 73 檔,目的是取得更多高低點標籤。");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
