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
    accent3: "0B7A75",   // 輔助色
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

// ---------- 34 檔(抄自 claude/kline-peak-predict-tool 的 backtest_long_only.json「Stacking 邏輯迴歸」,train_min_amp 0) ----------
// [總報酬, 最大回撤(不用,null), 交易筆數, 勝率];avg = 三年扣成本總報酬平均(由 json 逐年數字算出)
const BT = {
  "2024": { net: [-45.02, null, 137, 38.0], gross: [-28.22, null, 137, 43.1] },
  "2025": { net: [-11.94, null, 132, 50.0], gross: [13.86, null, 132, 56.1] },
  "2026": { net: [0.5, null, 88, 40.9], gross: [19.18, null, 88, 50.0] },
  avg: -18.82,
};
// ---------- TW200(抄自 backtest_long_only_tw200.json「Stacking 邏輯迴歸」,168 檔、train_min_amp 0) ----------
const BT200 = {
  "2024": { net: [-10.58, null, 144, 45.8], gross: [18.4, null, 144, 50.0] },
  "2025": { net: [-39.46, null, 142, 37.3], gross: [-20.27, null, 142, 42.3] },
  "2026": { net: [-15.03, null, 99, 44.4], gross: [3.07, null, 99, 49.5] },
  avg: -21.69,
};
const fmtPct = (v) => (v > 0 ? "+" : "") + v.toFixed(2) + "%"; // 報酬一律兩位小數

// ======================= 1. 封面 =======================
pres.addSection({ title: "開場" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "開場" });
s.addText("台股 11 天局部高低點三分類\n回測結果與下一步", { placeholder: "title" });
s.addText([
  { text: "34 檔與 TW200 只做多回測(2024、2025、2026 至 9/11)", options: { breakLine: true } },
  { text: "南電 8046 個案:真實高低點 vs Stacking 判斷", options: { breakLine: true } },
  { text: "下一步:展示網頁系統 UI/UX" },
], { placeholder: "body" });
s.addNotes("本報告整理 Stacking 方法在 34 檔(台灣50 剔除 16 檔低波動股)與 TW200(剔除低波動股後 168 檔)的只做多回測結果、南電 2024 的個案,以及網頁系統展示版的 UI/UX。數字都來自 repo 內既有的結果檔,沒有重跑。");

// ======================= 2. 方法 + 訓練方式 =======================
pres.addSection({ title: "方法" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "方法" });
s.addText("方法與訓練方式", { placeholder: "title" });
// 特徵條
card(s, { x: 0.6, y: 1.45, w: 12.15, h: 0.85, fill: { color: C.background2 }, objectName: "feat-card" });
T(s, "特徵 29 維", { x: 0.85, y: 1.5, w: 2.2, h: 0.75, fontSize: 18, bold: true, valign: "middle" });
T(s, "t-5 ~ t 共 6 根 K 線:開、高、低、收 ÷ t 收盤 取 log;成交量 ÷ 10 日均量 取 log", {
  x: 3.1, y: 1.5, w: 9.4, h: 0.75, fontSize: 15, valign: "middle" });
// Stacking 兩層:第一層兩組卡片 → 第二層
const lcard = (x, y, w, h, color, head, body, name) => {
  card(s, { x, y, w, h, fill: { color: C.background1 }, line: { color, width: 1.5 }, objectName: name });
  T(s, head, { x: x + 0.25, y: y + 0.15, w: w - 0.4, h: 0.42, fontSize: 17, bold: true, color });
  T(s, body, { x: x + 0.25, y: y + 0.6, w: w - 0.4, h: h - 0.7, fontSize: 14 });
};
T(s, "第一層:每一天打兩個分數(不經規則篩選)", { x: 0.6, y: 2.55, w: 6.2, h: 0.4, fontSize: 15, bold: true, color: C.text2 });
lcard(0.6, 3.0, 5.9, 1.2, C.accent1, "高點組:AE + OC-SVM → s_high", "只用真高點訓練:線性 AE 29 → 16,再以 OC-SVM 學「像真高點」的範圍", "layer1-high");
lcard(0.6, 4.35, 5.9, 1.2, C.accent2, "低點組:AE + OC-SVM → s_low", "只用真低點訓練,做法相同;分數 = OC-SVM 的 decision_function", "layer1-low");
T(s, "→", { x: 6.55, y: 3.95, w: 0.55, h: 0.6, fontSize: 28, bold: true, color: C.accent5, align: "center" });
T(s, "第二層:組合兩個分數", { x: 7.15, y: 2.55, w: 5.6, h: 0.4, fontSize: 15, bold: true, color: C.text2 });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.15, y: 3.0, w: 5.6, h: 2.55, rectRadius: 0.08, fill: { color: HEX.dk1 },
  line: { type: "none" }, objectName: "layer2" });
T(s, "邏輯迴歸 → 三類機率", { x: 7.4, y: 3.15, w: 5.2, h: 0.45, fontSize: 18, bold: true, color: C.background1 });
T(s, bullets(["輸入 s_high、s_low,輸出三類機率", "判斷 = 機率最大的類;分數 = 該機率", "類別權重 = 頻率平方根倒數"]),
  { x: 7.4, y: 3.7, w: 5.2, h: 1.75, fontSize: 14, color: C.background1 });
// 訓練方式
T(s, [
  { text: "訓練方式:", options: { bold: true } },
  { text: "walk-forward,前 4 年訓練、測下一年;第一層用前 3 年、第二層用最後 1 年(例:測 2025 → 第一層 2021–2023、第二層 2024),種子 42" },
], { x: 0.6, y: 5.85, w: 12.15, h: 0.75, fontSize: 15 });
s.addNotes("方法是 Stacking,兩層。特徵是 t-5 到 t 六根 K 線的 29 維。第一層有高點、低點兩組模型:高點組只用真高點訓練一個線性自編碼器(29 維壓到 16 維),再用 OC-SVM 學「像真高點」的範圍;低點組做法一樣。第一層對每一天都打分數,不經規則篩選,得到 s_high 和 s_low。第二層是邏輯迴歸,把兩個分數變成低點、非極值、高點三類機率,判斷取機率最大的類,分數就是那個機率。訓練用 walk-forward:每個測試年用之前 4 年,前 3 年訓練第一層、最後 1 年訓練第二層,例如測 2025 年時第一層用 2021 到 2023、第二層用 2024,種子 42。");

// ======================= 3–4. 混淆矩陣(claude/kline-peak-predict-tool 的 confusion_2024_2026_*_amp0.png,只取 Stacking 那一排) =======================
// 數字抄自 confusion_2024_2026_tw50_amp0.json / _tw200_amp0.json「② Stacking 邏輯迴歸」;三年平均由逐年數字算出
pres.addSection({ title: "混淆矩陣" });
const confSlide = (title, file, alt, cols, notes) => {
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "混淆矩陣" });
  sl.addText(title, { placeholder: "title" });
  const iw = 10.6, ih = iw * 685 / 2016, x0 = (13.333 - iw) / 2, y0 = 1.7;
  const tw = iw * 648 / 2016, g = iw * 36 / 2016;
  ["測試 2024", "測試 2025", "測試 2026(1–9 月)"].forEach((t, k) =>
    T(sl, t, { x: x0 + k * (tw + g), y: 1.32, w: tw, h: 0.32, fontSize: 14, bold: true, color: C.text2, align: "center", valign: "middle" }));
  sl.addImage({ path: path.join(HERE, file), x: x0, y: y0, w: iw, h: ih, altText: alt });
  const cy = 5.3, ch = 1.5, cw = (12.15 - 0.25 * 3) / 4;
  cols.forEach(([h, v, sub], k) => {
    const cx = 0.6 + k * (cw + 0.25);
    card(sl, { x: cx, y: cy, w: cw, h: ch, objectName: `conf-card-${k}` });
    T(sl, h, { x: cx + 0.2, y: cy + 0.12, w: cw - 0.35, h: 0.35, fontSize: 13, bold: true, color: C.text2 });
    T(sl, v, { x: cx + 0.2, y: cy + 0.5, w: cw - 0.3, h: 0.45, fontSize: 16, bold: true, color: C.accent2, fit: "none" });
    T(sl, sub, { x: cx + 0.2, y: cy + 1.02, w: cw - 0.3, h: 0.32, fontSize: 12, color: C.text2 });
  });
  sl.addNotes(notes);
};
confSlide("34 檔混淆矩陣(Stacking,2024–2026)", "kline_peak_confusion_tw50_stack.png", "34 檔 2024–2026 Stacking 混淆矩陣", [
  ["找到率(三年平均)", "低 50.6% / 高 41.0%", "真轉折點中被判出的比例"],
  ["命中率(三年平均)", "低 26.8% / 高 23.4%", "隨機猜約 7%"],
  ["macro-F1(逐年)", "48.54 / 49.43 / 49.45", "2024 / 2025 / 2026"],
  ["高低點從未判反", "0", "真低判高、真高判低"],
], "這頁是 34 檔、2024 到 2026 年 Stacking 的混淆矩陣,列是真實標籤、欄是判斷,顏色是每列的比例。第一,高低點從未判反:真低點被判成高點、真高點被判成低點的格子三年都是 0。第二,找到真轉折點的比例:三年平均真低點 50.6%、真高點 41.0%;逐年真高 / 真低點為 2024 年 46.7% / 55.7%、2025 年 35.3% / 45.2%、2026 年 41.2% / 51.0%。第三,命中率約 3 成以內:三年平均判低點 26.8%、判高點 23.4%,隨機猜約 7%。macro-F1 三年 48.54、49.43、49.45。");
confSlide("TW200 混淆矩陣(Stacking,2024–2026)", "kline_peak_confusion_tw200_stack.png", "TW200 2024–2026 Stacking 混淆矩陣", [
  ["找到率(三年平均)", "低 48.4% / 高 41.8%", "真轉折點中被判出的比例"],
  ["命中率(三年平均)", "低 27.7% / 高 26.0%", "隨機猜約 7%"],
  ["macro-F1(逐年)", "50.31 / 50.37 / 50.43", "2024 / 2025 / 2026"],
  ["高低點從未判反", "0", "真低判高、真高判低"],
], "TW200(剔除低波動股後 168 檔)的 Stacking 混淆矩陣。高低點一樣三年都沒有判反。找到率三年平均真低點 48.4%、真高點 41.8%;逐年真高 / 真低點為 2024 年 38.7% / 51.9%、2025 年 41.5% / 42.7%、2026 年 45.2% / 50.5%。命中率三年平均判低點 27.7%、判高點 26.0%,約 3 成,隨機約 7%。macro-F1 三年 50.31、50.37、50.43,三年很穩定,也比 34 檔高一點。");

// ======================= 5. 回測規則 =======================
pres.addSection({ title: "回測" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "回測" });
s.addText("回測規則", { placeholder: "title" });
const steps = [
  ["t 收盤後", "股票池中判「低點」的,取低點機率最高的前 3 檔"],
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
// 四項排成 2 × 2:左欄 股票池 / 只做多,右欄 成本 / 資金
const facts = [
  ["股票池", "34 檔(台灣50 剔除 16 檔低波動股)\nTW200(剔除低波動股後 168 檔)"],
  ["成本 0.585%", "買 0.1425% + 賣 0.1425% + 證交稅 0.3%"],
  ["只做多", "判高點不放空"],
  ["資金", "每年獨立 100 萬,年底結清"],
];
facts.forEach(([h, d], i) => {
  const col = i % 2, row = Math.floor(i / 2);
  // 左欄標籤短(3 字),右欄「成本 0.585%」較長;兩欄說明框各留餘裕給正黑體
  const x = col === 0 ? 0.6 : 6.25, y = 4.0 + row * 1.0, lw = col === 0 ? 1.2 : 1.8;
  T(s, h, { x, y, w: lw, h: 0.8, fontSize: 18, bold: true, valign: "middle" });
  T(s, d, { x: x + lw + 0.1, y, w: col === 0 ? 4.15 : 4.6, h: 0.8, fontSize: 15, valign: "middle", color: C.text2 });
});
s.addNotes("股票池有兩個:34 檔(台灣50 剔除 16 檔低波動股)和 TW200(剔除低波動股後 168 檔)。每天收盤後在股票池中挑 Stacking 判低點、低點機率最高的 3 檔,隔天開盤買、第 5 天收盤賣,每檔三分之一資金。一筆來回成本 0.585%。每年獨立 100 萬、年底結清。");

// ======================= 4. 結果表格(34 檔) =======================
const hdr = (t, o = {}) => ({ text: t, options: { bold: true, fill: { color: HEX.dk1 }, color: "FFFFFF", align: "center", valign: "middle", ...o } });
const cell = (t, o = {}) => ({ text: String(t), options: { align: "center", valign: "middle", ...o } });
const valCell = (v, o = {}) => cell(fmtPct(v), { color: v < 0 ? "C0392B" : (v > 0 ? "1E7B34" : HEX.dk1), ...o });
const yearLabel = { "2024": "2024", "2025": "2025", "2026": "2026\n(至 9/11)" };
const resultTable = (sl, data, poolRow) => {
  const rows = [];
  rows.push([{ text: poolRow, options: { colspan: 6, bold: true, fill: { color: HEX.lt2 }, color: HEX.dk1, align: "left", valign: "middle" } }]);
  rows.push([hdr("年份", { rowspan: 2 }), hdr("扣成本", { colspan: 2 }), hdr("沒扣成本", { colspan: 2 }), hdr("交易筆數", { rowspan: 2 })]);
  rows.push([hdr("總報酬"), hdr("勝率"), hdr("總報酬"), hdr("勝率")]);
  ["2024", "2025", "2026"].forEach((y, yi) => {
    const r = data[y], fill = { color: yi % 2 === 0 ? HEX.lt1 : HEX.lt2 };
    rows.push([cell(yearLabel[y], { bold: true, fill }),
      valCell(r.net[0], { fill, bold: true }), cell(r.net[3].toFixed(1) + "%", { fill }),
      valCell(r.gross[0], { fill, bold: true }), cell(r.gross[3].toFixed(1) + "%", { fill }),
      cell(r.net[2], { fill })]);
  });
  const af = { color: HEX.lt2 };
  rows.push([cell("三年平均", { bold: true, fill: af }), valCell(data.avg, { bold: true, fill: af }), cell("", { fill: af }), cell("", { fill: af }), cell("", { fill: af }), cell("", { fill: af })]);
  sl.addTable(rows, { x: 0.6, y: 1.45, w: 12.15, colW: [2.15, 2.1, 1.9, 2.1, 1.9, 2.0],
    rowH: [0.5, 0.5, 0.5, 0.85, 0.85, 0.85, 0.65], fontSize: 16, fontFace: THEME.bodyFontFace, color: HEX.dk1,
    border: { type: "solid", pt: 0.75, color: HEX.accent6 } });
};
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "回測" });
s.addText("34 檔回測結果(Stacking)", { placeholder: "title" });
resultTable(s, BT, "股票池:34 檔(台灣50 剔除 16 檔低波動股)");
s.addNotes("這頁是 34 檔(台灣50 剔除 16 檔低波動股)Stacking 的結果,數字直接抄自 backtest_long_only.json。扣成本後:2024 年 -45.02%、2025 年 -11.94%、2026 年到 9/11 +0.50%,三年平均 -18.82%。沒扣成本時 2025、2026 年是正的(+13.86%、+19.18%),顯示方向判斷有部分價值,但不夠支付每筆 0.585% 的成本。交易筆數 2024 為 137、2025 為 132、2026 為 88;扣成本和沒扣成本的筆數一樣。");

s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "回測" });
s.addText("TW200 回測結果(Stacking)", { placeholder: "title" });
resultTable(s, BT200, "股票池:TW200 剔除低波動股後 168 檔");
s.addNotes("這頁是 TW200 剔除低波動股後 168 檔 Stacking 的結果,交易規則和 34 檔相同,數字直接抄自 backtest_long_only_tw200.json。扣成本後:2024 年 -10.58%、2025 年 -39.46%、2026 年到 9/11 -15.03%,三年平均 -21.69%。沒扣成本時 2024 年 +18.40%、2026 年 +3.07%。交易筆數 2024 為 144、2025 為 142、2026 為 99。兩個股票池扣成本後都是虧損,所以系統定位是推薦和提醒,不是自動交易。");

// ======================= 南電(三段合併一頁) =======================
pres.addSection({ title: "南電 2024" });
const stockSlide = (title, tag, stackDays, stackHL, notes) => {
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "南電 2024" });
  sl.addText(title, { placeholder: "title" });
  const iw = 8.2, x0 = 0.6, lh = 0.32, gap = 0.15, rx = 9.1, rw = 3.65;
  const panels = [
    { file: "kline_peak_8046_true.png", px: 458, label: "真實標籤(11 天收盤最高 / 最低)", color: C.text2,
      lines: [["真高點", "17 個", C.accent1], ["真低點", "16 個", C.accent2]] },
    { file: `kline_peak_8046_${tag}_stacking.png`, px: 489, label: `Stacking:${stackDays}`, color: C.accent4,
      lines: [["判高點", stackHL[0], C.accent1], ["判低點", stackHL[1], C.accent2]] },
  ];
  let y = 1.3;
  panels.forEach((p, pi) => {
    const ih = iw * p.px / 2335;
    T(sl, p.label, { x: x0, y, w: iw, h: lh, fontSize: 14, bold: true, color: p.color, valign: "middle" });
    sl.addImage({ path: path.join(HERE, p.file), x: x0, y: y + lh, w: iw, h: ih, altText: `南電 8046 2024 ${p.label}` });
    const cy = y + lh, ch = ih;
    card(sl, { x: rx, y: cy, w: rw, h: ch, objectName: `stat-${pi}` });
    T(sl, p.lines.map(([h, v, col], k) => [
      { text: h + "  ", options: { color: C.text2, fontSize: 15 } },
      { text: v, options: { color: col, bold: true, fontSize: 20, breakLine: k < p.lines.length - 1 } },
    ]).flat(), { x: rx + 0.3, y: cy + 0.1, w: rw - 0.5, h: ch - 0.2, valign: "middle", paraSpaceAfter: 6 });
    y += lh + ih + gap;
  });
  sl.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.75, w: 12.15, h: 0.95, rectRadius: 0.08, fill: { color: HEX.dk1 },
    line: { type: "none" }, objectName: "nd-takeaway" });
  T(sl, "判出的低點遠多於真低點:假訊號多集中在真低點前後的連續下跌日,當天分不出哪一天才是真的", {
    x: 0.85, y: 5.75, w: 11.7, h: 0.95, fontSize: 16, bold: true, color: C.background1, valign: "middle" });
  sl.addNotes(notes);
};
stockSlide("南電 2024:34 檔模型", "34amp0", "判低點 65 天、判高點 23 天", ["對 5 / 錯 18", "對 10 / 錯 55"],
  "南電 8046 的 2024 年,模型是 34 檔的 Stacking,和第 6 頁回測同一個模型。上段是真實標籤:真高點 17 個、真低點 16 個。下段是 Stacking:判低點 65 天、判高點 23 天;判高點對 5 錯 18,判低點對 10 錯 55。實心三角形是判對、空心是判錯,綠色區間是回測的持有期間。判出的低點遠多於真低點,假訊號多集中在真低點前後的連續下跌日。");
stockSlide("南電 2024:TW200 模型", "tw200amp0", "判低點 58 天、判高點 22 天", ["對 7 / 錯 15", "對 10 / 錯 48"],
  "同一檔南電 2024,換成 TW200(168 檔)訓練的 Stacking,和第 7 頁回測同一個模型。真實標籤一樣是真高點 17 個、真低點 16 個。Stacking 判低點 58 天、判高點 22 天;判高點對 7 錯 15,判低點對 10 錯 48。和第 8 頁 34 檔模型相比,同一檔股票,換一個股票池訓練,判的天數和對錯也不同。");

// ======================= 展示網頁 =======================
pres.addSection({ title: "下一步" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "下一步" });
s.addText("展示網頁", { placeholder: "title" });
const flow = [
  ["輸入代號", "使用者在網頁輸入股票代號"],
  ["看今天的判斷", "Stacking 的三類機率:\n高點 / 低點 / 非極值,附信心值"],
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
  "接下來兩頁是網頁系統展示版(真實模型輸出、方法為 Stacking),四個頁面:今日判斷、個股查詢、成績追蹤、方法與說明",
  "展示版資料到 2026-09-10;股票池為 TW100 剔除低波動股;回放期判低點命中 29.8%(435 / 1461)",
]), { x: 0.6, y: 4.6, w: 12.15, h: 1.8, fontSize: 15 });
s.addNotes("接下來展示網頁系統。系統怎麼用:使用者在網頁輸入股票代號,系統以 Stacking 的三類機率回答今天是高點、低點或非極值,附信心值;5 個交易日後用真實結果對答案,累積命中率。系統定位是決策輔助,交易與否由使用者決定。接下來兩頁是網頁系統的展示版,畫面是真實模型輸出:資料到 2026-09-10,股票池為 TW100 剔除低波動股,模型與研究結果一致。網頁系統回放期(TW100 池內)Stacking 判低點的整體命中率是 29.8%(435 / 1461),和研究結果的約 3 成相近。");

// ======================= 網頁系統展示版(真實畫面,claude/kline-peak-web-app 81f2717 的 *_stack.png) =======================
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
  ["① 今日判斷", "收盤後列出 Stacking 判低點 / 判高點機率最高的前 3 檔"],
  ["② 個股查詢", "輸入代號,看三類機率、K 線與過去訊號的對錯"],
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
  capt(s, "① 今日判斷 · 桌機(2026-09-10 收盤,Stacking)", xd, 1.3, wd);
  shot(s, "kline_peak_ui_today_desktop_stack.png", xd, y0, wd, h, "今日判斷(桌機)展示版畫面");
  capt(s, "手機", xm, 1.3, wm);
  shot(s, "kline_peak_ui_today_mobile_stack.png", xm, y0, wm, h, "今日判斷(手機)展示版畫面");
}
s.addNotes("網頁有四個頁面:今日判斷、個股查詢、成績追蹤、方法與說明。這頁是今日判斷的真實畫面(展示版,資料到 2026-09-10 收盤),方法切到 Stacking,列出判低點和判高點機率最高的前 3 檔,每檔附信心等級;左邊是桌機、右邊是手機版。股票池為 TW100 剔除低波動股。截圖只取每頁上半部。");
// 第 2 頁:個股查詢 + 成績追蹤
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "下一步" });
s.addText("網頁系統展示版:個股查詢、成績追蹤", { placeholder: "title" });
{
  const y0 = 1.65, h = 4.6, w1 = h * 1280 / 1240, w2 = h * 1280 / 1000, gap = 0.45;
  const x1 = 0.6 + (12.15 - w1 - w2 - gap) / 2, x2 = x1 + w1 + gap;
  capt(s, "② 個股查詢(以池內 8454 富邦媒為例)", x1, 1.3, w1);
  shot(s, "kline_peak_ui_stock_desktop_stack.png", x1, y0, w1, h, "個股查詢(桌機)展示版畫面");
  capt(s, "③ 成績追蹤", x2, 1.3, w2);
  shot(s, "kline_peak_ui_track_desktop_stack.png", x2, y0, w2, h, "成績追蹤(桌機)展示版畫面");
}
s.addNotes("左邊是個股查詢,以池內的 8454 富邦媒為例:輸入代號後看到 Stacking 的三類機率,9/10 收盤後是高點 0.00、低點 0.57、非極值 0.43,判為低點、信心低;下方是最近的訊號與 K 線。右邊是成績追蹤,方法切到 Stacking:每天的判斷存檔,5 個交易日後對答案。回放期 TW100 池內判低點整體命中 29.8%(435 / 1461);依信心等級分,高、中、低分別是 33.1%、30.9%、25.2%;每天前 3 檔近 60 天命中 26.1%。命中率約 3 成、扣成本後回測虧損,所以這是推薦和提醒系統,不是自動交易。兩張都是展示版的真實畫面,資料到 2026-09-10。");

// 主題的東亞字型(ea)預設是空的,繁中(Hant)會落到新細明體;改成正黑體,中文字才會用 Microsoft JhengHei
async function fixEastAsianFont(file, face) {
  const fs = require("fs");
  const JSZip = require("jszip");
  const zip = await JSZip.loadAsync(fs.readFileSync(file), { createFolders: false }); // 不產生資料夾項目
  const name = Object.keys(zip.files).find((n) => /^ppt\/theme\/theme\d+\.xml$/.test(n));
  let xml = await zip.file(name).async("string");
  xml = xml.replace(/<a:ea typeface="[^"]*"\/>/g, `<a:ea typeface="${face}"/>`)
           .replace(/<a:font script="Hant" typeface="[^"]*"\/>/g, `<a:font script="Hant" typeface="${face}"/>`);
  zip.file(name, xml, { createFolders: false });
  fs.writeFileSync(file, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  await fixEastAsianFont(OUT, THEME.bodyFontFace);
  console.log("wrote", OUT);
})();
