// 台股 11 天局部高低點三分類 — 回測結果與下一步(pptxgenjs,結構化:主題 + 版面 + 區段)
// 數字全部從 json 與圖例原樣抄(來源寫在各資料區塊上方)。
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
  slideNumber: { x: 12.25, y: 6.95, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent6, align: "right" },
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

// ---------- 資料(抄自 claude/kline-peak-predict-tool b324e42 的 backtest_long_only.json,34 檔、訓練門檻 0%) ----------
// [總報酬, 最大回撤(不用,null), 交易筆數, 勝率]
const BT = {
  "2024": { main: { net: [-24.82, null, 142, 44.4], gross: [-0.94, null, 142, 51.4] },
            stack: { net: [-45.02, null, 137, 38.0], gross: [-28.22, null, 137, 43.1] } },
  "2025": { main: { net: [-34.87, null, 140, 41.4], gross: [-14.51, null, 140, 48.6] },
            stack: { net: [-11.94, null, 132, 50.0], gross: [13.86, null, 132, 56.1] } },
  "2026": { main: { net: [0.09, null, 94, 38.3], gross: [20.19, null, 94, 50.0] },
            stack: { net: [0.5, null, 88, 40.9], gross: [19.18, null, 88, 50.0] } },
};
// ---------- TW200(抄自 claude/kline-peak-predict-tool b324e42 的 backtest_long_only_tw200_amp7.json,168 檔、訓練門檻 7%) ----------
const BT200 = {
  "2024": { main: { net: [-25.57, null, 136, 45.6], gross: [-3.15, null, 136, 48.5] },
            stack: { net: [-22.83, null, 129, 43.4], gross: [-0.88, null, 129, 45.7] } },
  "2025": { main: { net: [28.03, null, 139, 48.9], gross: [67.76, null, 139, 52.5] },
            stack: { net: [-0.87, null, 120, 43.3], gross: [25.13, null, 120, 48.3] } },
  "2026": { main: { net: [2.39, null, 96, 49.0], gross: [23.32, null, 96, 54.2] },
            stack: { net: [-4.65, null, 95, 46.3], gross: [14.69, null, 95, 49.5] } },
};
const fmtPct = (v) => (v > 0 ? "+" : "") + v.toFixed(2) + "%"; // 報酬一律兩位小數

// ======================= 1. 封面 =======================
pres.addSection({ title: "開場" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "開場" });
s.addText("台股 11 天局部高低點三分類\n回測結果與下一步", { placeholder: "title" });
s.addText([
  { text: "34 檔與 TW200 只做多回測(2024、2025、2026 至 9/11)", options: { breakLine: true } },
  { text: "南電 8046 個案:真實高低點 vs 兩方法判斷", options: { breakLine: true } },
  { text: "下一步:展示網頁系統 UI/UX" },
], { placeholder: "body" });
s.addNotes("本報告整理兩個方法在 34 檔(台灣50 剔除 16 檔低波動股)與 TW200(剔除低波動股後 168 檔)的只做多回測結果、南電 2024 的個案,以及網頁系統展示版的 UI/UX。數字都來自 repo 內既有的結果檔,沒有重跑。");

// ======================= 2. 兩個方法 + 訓練方式 =======================
pres.addSection({ title: "方法" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "方法" });
s.addText("兩個方法與訓練方式", { placeholder: "title" });
// 特徵條
card(s, { x: 0.6, y: 1.8, w: 12.15, h: 0.95, fill: { color: C.background2 }, objectName: "feat-card" });
T(s, "特徵 29 維", { x: 0.85, y: 1.9, w: 2.2, h: 0.75, fontSize: 18, bold: true, valign: "middle" });
T(s, "t-5 ~ t 共 6 根 K 線:開、高、低、收 ÷ t 收盤 取 log;成交量 ÷ 10 日均量 取 log", {
  x: 3.1, y: 1.9, w: 9.4, h: 0.75, fontSize: 15, valign: "middle" });
// 兩方法卡片
const mcard = (x, color, num, name, lines) => {
  card(s, { x, y: 3.05, w: 5.95, h: 2.0, fill: { color: C.background1 }, line: { color: HEX.accent6, width: 1 },
    objectName: `method-${num}` });
  s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: 3.27, w: 0.55, h: 0.55, fill: { color }, line: { type: "none" } });
  T(s, num, { x: x + 0.25, y: 3.27, w: 0.55, h: 0.55, fontSize: 18, bold: true, color: C.background1, align: "center", valign: "middle" });
  T(s, name, { x: x + 0.95, y: 3.27, w: 4.8, h: 0.55, fontSize: 20, bold: true, valign: "middle" });
  T(s, bullets(lines), { x: x + 0.25, y: 4.0, w: 5.55, h: 0.95, fontSize: 14 });
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
], { x: 0.6, y: 5.35, w: 12.15, h: 0.5, fontSize: 16 });
s.addNotes("兩個方法用同一組 29 維特徵。主軸是規則候選加上每類一組線性 AE 與 OC-SVM;Stacking 把 AE/OC-SVM 的分數交給邏輯迴歸。walk-forward,前 4 年訓練、測下一年,種子 42。");

// ======================= 4. 回測規則 =======================
pres.addSection({ title: "回測" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "回測" });
s.addText("回測規則", { placeholder: "title" });
const steps = [
  ["t 收盤後", "股票池中判「低點」的,取分數最高的前 3 檔"],
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
  ["股票池", "34 檔(台灣50 剔除 16 檔低波動股)\nTW200(剔除低波動股後 168 檔)"],
  ["只做多", "判高點不放空"],
  ["成本 0.585%", "買 0.1425% + 賣 0.1425% + 證交稅 0.3%"],
  ["資金", "每年獨立 100 萬,年底結清"],
  ["模型", "訓練門檻:34 檔 0%、TW200 7%"],
];
// 第一列股票池(兩行)占滿寬度,其餘四項排成 2 × 2
facts.forEach(([h, d], i) => {
  const col = i === 0 ? 0 : (i - 1) % 2, row = i === 0 ? 0 : 1 + Math.floor((i - 1) / 2);
  const x = 0.6 + col * 5.75, y = 3.85 + row * 0.95;
  T(s, h, { x, y, w: 1.85, h: 0.8, fontSize: 18, bold: true, valign: "middle" });
  T(s, d, { x: x + 1.95, y, w: i === 0 ? 10.2 : (col === 0 ? 3.6 : 4.45), h: 0.8, fontSize: 15, valign: "middle", color: C.text2 });
});
s.addNotes("股票池有兩個:34 檔(台灣50 剔除 16 檔低波動股)和 TW200(剔除低波動股後 168 檔);訓練門檻 34 檔用 0%、TW200 用 7%。每天收盤後在股票池中挑判低點、分數最高的 3 檔,隔天開盤買、第 5 天收盤賣,每檔三分之一資金。一筆來回成本 0.585%。每年獨立 100 萬、年底結清。");

// ======================= 4. 結果表格(34 檔) =======================
const hdr = (t, o = {}) => ({ text: t, options: { bold: true, fill: { color: HEX.dk1 }, color: "FFFFFF", align: "center", valign: "middle", ...o } });
const cell = (t, o = {}) => ({ text: String(t), options: { align: "center", valign: "middle", ...o } });
const valCell = (v, o = {}) => cell(fmtPct(v), { color: v < 0 ? "C0392B" : (v > 0 ? "1E7B34" : HEX.dk1), ...o });
const yearLabel = { "2024": "2024", "2025": "2025", "2026": "2026\n(至 9/11)" };
const resultTable = (sl, data, poolRow) => {
  const rows = [];
  if (poolRow) rows.push([{ text: poolRow, options: { colspan: 7, bold: true, fill: { color: HEX.lt2 }, color: HEX.dk1, align: "left", valign: "middle" } }]);
  rows.push([hdr("年份", { rowspan: 2 }), hdr("方法", { rowspan: 2 }), hdr("扣成本", { colspan: 2 }), hdr("沒扣成本", { colspan: 2 }), hdr("交易筆數", { rowspan: 2 })]);
  rows.push([hdr("總報酬"), hdr("勝率"), hdr("總報酬"), hdr("勝率")]);
  ["2024", "2025", "2026"].forEach((y, yi) => {
    [["main", "主軸"], ["stack", "Stacking 邏輯迴歸"]].forEach(([k, name], mi) => {
      const r = data[y][k], fill = { color: yi % 2 === 0 ? HEX.lt1 : HEX.lt2 };
      const row = [];
      if (mi === 0) row.push(cell(yearLabel[y], { rowspan: 2, bold: true, fill }));
      row.push(cell(name, { fill, align: "left" }));
      row.push(valCell(r.net[0], { fill, bold: true }), cell(r.net[3].toFixed(1) + "%", { fill }));
      row.push(valCell(r.gross[0], { fill, bold: true }), cell(r.gross[3].toFixed(1) + "%", { fill }));
      row.push(cell(r.net[2], { fill }));
      rows.push(row);
    });
  });
  const d = 0.64; // 兩張表列高一致
  const rowH = [...(poolRow ? [0.45] : []), 0.45, 0.45, d, d, d, d, d, d];
  sl.addTable(rows, { x: 0.6, y: 1.45, w: 12.15, colW: [1.6, 3.0, 1.6, 1.4, 1.6, 1.4, 1.55],
    rowH, fontSize: 15, fontFace: THEME.bodyFontFace, color: HEX.dk1,
    border: { type: "solid", pt: 0.75, color: HEX.accent6 } });
};
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "回測" });
s.addText("34 檔回測結果(訓練門檻 0%)", { placeholder: "title" });
resultTable(s, BT, "股票池:34 檔(台灣50 剔除 16 檔低波動股)");
s.addNotes("這頁是 34 檔(台灣50 剔除 16 檔低波動股)、訓練門檻 0% 的結果,數字直接抄自 backtest_long_only.json。扣成本後:2024 主軸 -24.82%、Stacking -45.02%;2025 主軸 -34.87%、Stacking -11.94%;2026 到 9/11 主軸 +0.09%、Stacking +0.50%。交易筆數 2024 為 142 / 137、2025 為 140 / 132、2026 為 94 / 88;扣成本和沒扣成本的筆數一樣,差別只在每筆扣 0.585%。");

s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "回測" });
s.addText("TW200 回測結果(訓練門檻 7%)", { placeholder: "title" });
resultTable(s, BT200, "股票池:TW200 剔除低波動股後 168 檔");
s.addNotes("這頁是 TW200 剔除低波動股後 168 檔、訓練門檻 7% 的結果,數字直接抄自 backtest_long_only_tw200_amp7.json。門檻是看測試年選的。扣成本後:2024 主軸 -25.57%、Stacking -22.83%;2025 主軸 +28.03%、Stacking -0.87%;2026 到 9/11 主軸 +2.39%、Stacking -4.65%。交易筆數 2024 為 136 / 129、2025 為 139 / 120、2026 為 96 / 95。");

// ======================= 南電(三段合併一頁) =======================
pres.addSection({ title: "南電 2024" });
const stockSlide = (title, tag, mainDays, stackDays, mainHL, stackHL, notes) => {
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "南電 2024" });
  sl.addText(title, { placeholder: "title" });
  const iw = 7.6, x0 = 0.6, lh = 0.28, gap = 0.08, rx = 8.55, rw = 4.2;
  const panels = [
    { file: "kline_peak_8046_true.png", px: 458, label: "真實標籤(11 天收盤最高 / 最低)", color: C.text2,
      lines: [["真高點", "17 個", C.accent1], ["真低點", "16 個", C.accent2]] },
    { file: `kline_peak_8046_${tag}_mainline.png`, px: 454, label: `① 主軸:${mainDays}`, color: C.accent3,
      lines: [["判高點", mainHL[0], C.accent1], ["判低點", mainHL[1], C.accent2]] },
    { file: `kline_peak_8046_${tag}_stacking.png`, px: 489, label: `② Stacking 邏輯迴歸:${stackDays}`, color: C.accent4,
      lines: [["判高點", stackHL[0], C.accent1], ["判低點", stackHL[1], C.accent2]] },
  ];
  let y = 1.3;
  panels.forEach((p, pi) => {
    const ih = iw * p.px / 2335;
    T(sl, p.label, { x: x0, y, w: iw, h: lh, fontSize: 12, bold: true, color: p.color, valign: "middle" });
    sl.addImage({ path: path.join(HERE, p.file), x: x0, y: y + lh, w: iw, h: ih, altText: `南電 8046 2024 ${p.label}` });
    const cy = y + lh, ch = ih;
    card(sl, { x: rx, y: cy, w: rw, h: ch, objectName: `stat-${pi}` });
    T(sl, p.lines.map(([h, v, col], k) => [
      { text: h + "  ", options: { color: C.text2, fontSize: 15 } },
      { text: v, options: { color: col, bold: true, fontSize: 20, breakLine: k < p.lines.length - 1 } },
    ]).flat(), { x: rx + 0.3, y: cy + 0.1, w: rw - 0.5, h: ch - 0.2, valign: "middle", paraSpaceAfter: 6 });
    y += lh + ih + gap;
  });
  sl.addNotes(notes);
};
stockSlide("南電 2024:34 檔模型(門檻 6%)", "34amp6", "判低點 17 天、判高點 5 天", "判低點 32 天、判高點 9 天",
  ["對 2 / 錯 3", "對 5 / 錯 12"], ["對 3 / 錯 6", "對 7 / 錯 25"],
  "南電 8046 的 2024 年,模型是 34 檔、訓練門檻 6%,和第 4 頁回測同一個模型。上段是真實標籤:真高點 17 個、真低點 16 個。中段是主軸:判低點 17 天、判高點 5 天;判高點對 2 錯 3,判低點對 5 錯 12。下段是 Stacking 邏輯迴歸:判低點 32 天、判高點 9 天;判高點對 3 錯 6,判低點對 7 錯 25。實心三角形是判對、空心是判錯,綠色區間是回測的持有期間。");
stockSlide("南電 2024:TW200 模型(門檻 7%)", "tw200amp7", "判低點 29 天、判高點 14 天", "判低點 24 天、判高點 7 天",
  ["對 4 / 錯 10", "對 7 / 錯 22"], ["對 3 / 錯 4", "對 5 / 錯 19"],
  "同一檔南電 2024,換成 TW200(168 檔)、訓練門檻 7% 的模型,和第 5 頁回測同一個模型。真實標籤一樣是真高點 17 個、真低點 16 個。主軸判低點 29 天、判高點 14 天;判高點對 4 錯 10,判低點對 7 錯 22。Stacking 判低點 24 天、判高點 7 天;判高點對 3 錯 4,判低點對 5 錯 19。同一檔股票,兩個模型判的天數和對錯都不同。");

// ======================= 展示網頁 =======================
pres.addSection({ title: "下一步" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "下一步" });
s.addText("展示網頁", { placeholder: "title" });
const flow = [
  ["輸入代號", "使用者在網頁輸入股票代號"],
  ["看今天的判斷", "今天是 高點 / 低點 / 非極值,\n附信心值"],
  ["5 天後對答案", "5 個交易日後用真實結果對答案,\n累積命中率"],
];
flow.forEach(([h, d], i) => {
  const x = 0.6 + i * 4.15;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.5, w: 3.75, h: 2.1, rectRadius: 0.08,
    fill: { color: i === 2 ? HEX.dk1 : HEX.lt2 }, line: { type: "none" }, objectName: `flow-${i}` });
  T(s, h, { x: x + 0.2, y: 1.7, w: 3.45, h: 0.5, fontSize: 20, bold: true, color: i === 2 ? C.background1 : C.accent2 });
  T(s, d, { x: x + 0.2, y: 2.3, w: 3.45, h: 1.1, fontSize: 14, color: i === 2 ? C.background1 : C.text1 });
  if (i < 2) T(s, "→", { x: x + 3.78, y: 2.25, w: 0.35, h: 0.6, fontSize: 24, bold: true, color: C.accent5, align: "center" });
});
T(s, "系統定位", { x: 0.6, y: 4.05, w: 12.15, h: 0.45, fontSize: 18, bold: true });
T(s, bullets([
  "決策輔助工具:使用者自己決定要不要交易,系統提供判斷與信心值",
  "接下來兩頁是網頁系統展示版(真實模型輸出),共四個頁面:今日判斷、個股查詢、成績追蹤、方法與說明",
  "展示版資料到 2026-09-10;股票池為 TW100 剔除低波動股;模型與研究結果一致",
]), { x: 0.6, y: 4.6, w: 12.15, h: 1.8, fontSize: 15 });
s.addNotes("接下來展示網頁系統。系統怎麼用:使用者在網頁輸入股票代號,系統回答今天是高點、低點或非極值,附信心值;5 個交易日後用真實結果對答案,累積命中率。系統定位是決策輔助,交易與否由使用者決定。接下來兩頁是網頁系統的展示版,畫面是真實模型輸出:資料到 2026-09-10,股票池為 TW100 剔除低波動股,模型與研究結果一致。");

// ======================= 網頁系統展示版(真實畫面,claude/kline-peak-web-app b3856d7) =======================
const shot = (sl, file, x, y, w, h, alt) => {
  sl.addShape(pres.shapes.RECTANGLE, { x: x - 0.02, y: y - 0.02, w: w + 0.04, h: h + 0.04, fill: { color: HEX.lt1 },
    line: { color: HEX.accent6, width: 1 }, shadow: { type: "outer", color: "000000", opacity: 0.12, blur: 6, offset: 2, angle: 90 } });
  sl.addImage({ path: path.join(HERE, file), x, y, w, h, altText: alt });
};
const capt = (sl, text, x, y, w) => T(sl, text, { x, y, w, h: 0.3, fontSize: 13, bold: true, color: C.text2, valign: "middle" });
// 第 1 頁:四個頁面說明 + 今日判斷(桌機、手機)
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "下一步" });
s.addText("網頁系統展示版:今日判斷", { placeholder: "title" });
const pagesInfo = [
  ["① 今日判斷", "收盤後列出判低點 / 判高點分數最高的前 3 檔,可切換兩方法"],
  ["② 個股查詢", "輸入代號,看今天的判斷、各類分數、兩方法比較與過去訊號對錯"],
  ["③ 成績追蹤", "每天的判斷存檔,5 個交易日後對答案,看命中率"],
  ["④ 方法與說明", "研究結果、回測摘要與免責說明"],
];
pagesInfo.forEach(([h, d], i) => {
  const y = 1.3 + i * 1.25;
  card(s, { x: 0.6, y, w: 3.55, h: 1.12, objectName: `page-${i}` });
  T(s, h, { x: 0.8, y: y + 0.1, w: 3.2, h: 0.35, fontSize: 15, bold: true, color: C.accent2 });
  T(s, d, { x: 0.8, y: y + 0.45, w: 3.2, h: 0.62, fontSize: 13, color: C.text1 });
});
{
  const y0 = 1.65, h = 4.55, wd = h * 1280 / 1000, wm = h * 780 / 1650, xd = 4.5, xm = 12.75 - wm;
  capt(s, "① 今日判斷 · 桌機(2026-09-10 收盤,真實模型輸出)", xd, 1.3, wd);
  shot(s, "kline_peak_ui_today_desktop.png", xd, y0, wd, h, "今日判斷(桌機)展示版畫面");
  capt(s, "手機", xm, 1.3, wm);
  shot(s, "kline_peak_ui_today_mobile.png", xm, y0, wm, h, "今日判斷(手機)展示版畫面");
}
s.addNotes("網頁有四個頁面:今日判斷、個股查詢、成績追蹤、方法與說明。這頁是今日判斷的真實畫面(展示版,資料到 2026-09-10 收盤),列出判低點和判高點分數最高的前 3 檔,可以切換主軸和 Stacking;左邊是桌機、右邊是手機版。股票池為 TW100 剔除低波動股,模型與研究結果一致。截圖只取每頁上半部。");
// 第 2 頁:個股查詢 + 成績追蹤
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "下一步" });
s.addText("網頁系統展示版:個股查詢、成績追蹤", { placeholder: "title" });
{
  const y0 = 1.65, h = 4.6, w1 = h * 1280 / 1240, w2 = h * 1280 / 1000, gap = 0.45;
  const x1 = 0.6 + (12.15 - w1 - w2 - gap) / 2, x2 = x1 + w1 + gap;
  capt(s, "② 個股查詢(以池內 8454 富邦媒為例)", x1, 1.3, w1);
  shot(s, "kline_peak_ui_stock_desktop.png", x1, y0, w1, h, "個股查詢(桌機)展示版畫面");
  capt(s, "③ 成績追蹤", x2, 1.3, w2);
  shot(s, "kline_peak_ui_track_desktop.png", x2, y0, w2, h, "成績追蹤(桌機)展示版畫面");
}
s.addNotes("左邊是個股查詢,以池內的 8454 富邦媒為例:輸入代號後看到今天的判斷、各類分數、兩方法比較,下方是最近 60 個交易日的 K 線與過去訊號的對錯。右邊是成績追蹤:每天的判斷存檔,5 個交易日後對答案,顯示命中率。兩張都是展示版的真實畫面,資料到 2026-09-10。方法與說明頁放研究結果、回測摘要和免責說明,這裡沒有附圖。");

// 主題的東亞字型(ea)預設是空的,繁中(Hant)會落到新細明體;改成正黑體,中文字才會用 Microsoft JhengHei
async function fixEastAsianFont(file, face) {
  const fs = require("fs");
  const JSZip = require("jszip");
  const zip = await JSZip.loadAsync(fs.readFileSync(file));
  const name = Object.keys(zip.files).find((n) => /^ppt\/theme\/theme\d+\.xml$/.test(n));
  let xml = await zip.file(name).async("string");
  xml = xml.replace(/<a:ea typeface="[^"]*"\/>/g, `<a:ea typeface="${face}"/>`)
           .replace(/<a:font script="Hant" typeface="[^"]*"\/>/g, `<a:font script="Hant" typeface="${face}"/>`);
  zip.file(name, xml);
  fs.writeFileSync(file, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  await fixEastAsianFont(OUT, THEME.bodyFontFace);
  console.log("wrote", OUT);
})();
