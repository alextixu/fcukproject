// 台股 11 天局部高低點三分類 — Stacking 模型與決策輔助系統(pptxgenjs,結構化:主題 + 版面 + 區段)
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

// 數字來源:claude/kline-peak-predict-tool 的 results/confusion_2024_2026_tw200_amp0.json、confusion_8046_2024_tw200_amp0.json、
// compare_8046_2024_tw200.json、README 的後處理 / 機率門檻表(Stacking、TW200 168 檔);網頁截圖:claude/kline-peak-web-app d0bbce2。
// 版面原則:標題 + 主圖 + 最多 4 個大數字卡;說明一律放講稿。
const L = (t, o = {}) => ({ text: t, options: { breakLine: true, ...o } });
// 大數字卡:大數字 + 短標籤
const stat = (sl, x, y, w, h, value, label, color = C.accent2, size = 26) => {
  card(sl, { x, y, w, h });
  T(sl, value, { x: x + 0.2, y: y + 0.12, w: w - 0.3, h: h * 0.58, fontSize: size, bold: true, color, valign: "middle", fit: "none" });
  T(sl, label, { x: x + 0.2, y: y + h * 0.62, w: w - 0.3, h: h * 0.32, fontSize: 13, color: C.text2, valign: "top" });
};
const arrow = (sl, x, y, w, h, flipV = false) => sl.addShape(pres.shapes.LINE, { x, y, w, h, flipV,
  line: { color: HEX.accent5, width: 2, endArrowType: "triangle" } });
const shot = (sl, file, x, y, w, h, alt) => {
  sl.addShape(pres.shapes.RECTANGLE, { x: x - 0.02, y: y - 0.02, w: w + 0.04, h: h + 0.04, fill: { color: HEX.lt1 },
    line: { color: HEX.accent6, width: 1 }, shadow: { type: "outer", color: "000000", opacity: 0.12, blur: 6, offset: 2, angle: 90 } });
  sl.addImage({ path: path.join(HERE, file), x, y, w, h, altText: alt });
};

// ======================= 1. 封面 =======================
pres.addSection({ title: "開場" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "開場" });
s.addText("台股 11 天局部高低點三分類\nStacking 模型與決策輔助系統", { placeholder: "title" });
s.addText("TW200 訓練 · 台灣 50 建議", { placeholder: "body" });
s.addNotes("這份報告說明本專題的最終方向。模型是 Stacking,用 TW200 剔除低波動股後的 168 檔訓練。先看 2024 到 2026 年的混淆矩陣,再用南電 8046 說明模型找得到高低點、但即使篩掉低機率的訊號也沒有更準,最後說明為什麼改做給使用者方向的決策輔助系統,並展示網頁。數字都來自 repo 內既有的結果檔,沒有重跑。");

// ======================= 2. 方法(流程圖) =======================
pres.addSection({ title: "方法" });
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "方法" });
  sl.addText("方法:Stacking", { placeholder: "title" });
  const box = (x, y, w, h, text, o = {}) => {
    sl.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: o.fill || HEX.lt2 },
      line: o.line ? { color: o.line, width: 1.5 } : { type: "none" } });
    T(sl, text, { x, y, w, h, fontSize: o.size || 18, bold: true, color: o.color || C.text1, align: "center", valign: "middle" });
  };
  const cy = 4.05;                                   // 主軸線的中心高度
  box(0.6, cy - 0.65, 2.2, 1.3, "特徵\n29 維");
  T(sl, "第一層", { x: 3.35, y: 1.55, w: 3.1, h: 0.4, fontSize: 15, bold: true, color: C.text2, align: "center" });
  box(3.35, 2.15, 3.1, 1.25, "高點組\nAE + OC-SVM", { fill: HEX.lt1, line: HEX.accent1, color: C.accent1 });
  box(3.35, 4.7, 3.1, 1.25, "低點組\nAE + OC-SVM", { fill: HEX.lt1, line: HEX.accent2, color: C.accent2 });
  arrow(sl, 2.85, 2.78, 0.45, cy - 2.78, true);
  arrow(sl, 2.85, cy, 0.45, 5.32 - cy);
  T(sl, "第二層", { x: 7.15, y: 1.55, w: 2.6, h: 0.4, fontSize: 15, bold: true, color: C.text2, align: "center" });
  box(7.15, cy - 0.7, 2.6, 1.4, "邏輯迴歸", { fill: HEX.dk1, color: C.background1, size: 20 });
  arrow(sl, 6.5, 2.78, 0.6, cy - 2.78);
  arrow(sl, 6.5, cy, 0.6, 5.32 - cy, true);
  const outs = [["高點", HEX.accent1], ["非極值", HEX.accent5], ["低點", HEX.accent2]];
  outs.forEach(([t, col], i) => {
    const y = 2.35 + i * 1.25;
    box(10.45, y, 2.3, 0.95, t, { fill: HEX.lt1, line: col, color: col });
  });
  arrow(sl, 9.8, cy, 0.6, 0);
  T(sl, "三類機率", { x: 10.45, y: 1.55, w: 2.3, h: 0.4, fontSize: 15, bold: true, color: C.text2, align: "center" });
  sl.addNotes("方法是 Stacking,也是本專題的最終版本,分兩層。特徵是 t-5 到 t 六根 K 線的 29 維:開、高、低、收除以 t 日收盤取 log,成交量除以 10 日均量取 log。第一層有高點、低點兩組模型:高點組只用真高點訓練一個線性自編碼器(29 維壓到 16 維),再用 OC-SVM 學「像真高點」的範圍,分數是 OC-SVM 的 decision_function;低點組做法一樣。第一層對每一天都打分數,不經規則篩選,得到 s_high 和 s_low。第二層是邏輯迴歸,把兩個分數變成高點、非極值、低點三類機率,判斷取機率最大的類,類別權重是頻率平方根倒數。訓練資料是 TW200 剔除低波動股後的 168 檔,walk-forward:每個測試年用之前 4 年,前 3 年訓練第一層、最後 1 年訓練第二層,例如測 2025 年時第一層用 2021 到 2023、第二層用 2024,種子 42。");
}

// ======================= 3. TW200 混淆矩陣 =======================
pres.addSection({ title: "混淆矩陣" });
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "混淆矩陣" });
  sl.addText("TW200 混淆矩陣(2024–2026)", { placeholder: "title" });
  const iw = 11.2, ih = iw * 685 / 2016, x0 = (13.333 - iw) / 2;
  sl.addImage({ path: path.join(HERE, "kline_peak_confusion_tw200_stack.png"), x: x0, y: 1.3, w: iw, h: ih, altText: "TW200 2024–2026 Stacking 混淆矩陣" });
  const cw = (12.15 - 0.25 * 3) / 4, cy = 5.3, ch = 1.45;
  [["48.4% / 41.8%", "找到率 低 / 高"], ["27.7% / 26.0%", "命中率 低 / 高"], ["約 7%", "隨機猜"], ["0", "高低點判反"]]
    .forEach(([v, l], k) => stat(sl, 0.6 + k * (cw + 0.25), cy, cw, ch, v, l, k === 3 ? C.text1 : C.accent2, k < 2 ? 22 : 26));
  sl.addNotes("這頁是 TW200(剔除低波動股後 168 檔)Stacking 在 2024 到 2026 年的混淆矩陣,列是真實標籤、欄是判斷,每個矩陣上方標了訓練期間和 macro-F1。第一,高低點從未判反:真低點被判成高點、真高點被判成低點的格子三年都是 0,錯誤都發生在轉折點和非極值之間。第二,找到率三年平均真低點 48.4%、真高點 41.8%,也就是找到約一半的低點、四成的高點。第三,命中率三年平均判低點 27.7%、判高點 26.0%,約 3 成;隨機挑一天剛好是低點的機率約 7%。macro-F1 三年 50.31、50.37、50.43,很穩定。");
}

// ======================= 4. 南電 2024 =======================
pres.addSection({ title: "南電 2024" });
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "南電 2024" });
  sl.addText("南電 2024:找得到高點和低點", { placeholder: "title" });
  const iw = 12.15, ih = iw * 710 / 2676;
  sl.addImage({ path: path.join(HERE, "kline_peak_8046_tw200_stack_raw.png"), x: 0.6, y: 1.3, w: iw, h: ih, altText: "南電 8046 2024 真實高低點與 Stacking 原始判斷" });
  const cw = (12.15 - 0.25 * 3) / 4, cy = 4.95, ch = 1.6;
  [["17 / 16", "真高點 / 真低點", C.text1], ["10 / 48", "判低點 對 / 錯", C.accent2],
   ["7 / 15", "判高點 對 / 錯", C.accent1], ["0", "高低點判反", C.text1]]
    .forEach(([v, l, col], k) => stat(sl, 0.6 + k * (cw + 0.25), cy, cw, ch, v, l, col, 28));
  sl.addNotes("以南電 8046 的 2024 年為例,用 TW200 訓練的 Stacking(第一層 2020 到 2022、第二層 2023)。上面是收盤和真實標籤:真高點 17 個、真低點 16 個,2024 年共 242 個交易日,全年大致下跌。下面是 Stacking 的原始判斷,朝下的三角形是判高點、朝上的是判低點,實心是判對、空心是判錯。判低點 58 天,對 10 錯 48,也就是 16 個真低點抓到 10 個;判高點 22 天,對 7 錯 15,17 個真高點抓到 7 個;真低點沒有被判成高點,真高點也沒有被判成低點。所以模型找得到大部分低點和部分高點,方向也沒有錯,但多判的訊號不少,錯的大多是真低點前後的連續下跌日。");
}

// ======================= 5. 篩掉低機率訊號 =======================
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "南電 2024" });
  sl.addText("篩掉低機率的訊號,有更準嗎?", { placeholder: "title" });
  const ix = 2.7, iw = 6.0, ih = iw * 1844 / 2676, iy = 1.4;
  sl.addImage({ path: path.join(HERE, "kline_peak_8046_tw200_filters.png"), x: ix, y: iy, w: iw, h: ih, altText: "南電 2024 各種篩選規則留下的訊號" });
  const cent = [0.0879, 0.2852, 0.4826, 0.68, 0.888];
  const labs = [["真實標籤", ""], ["原始", "17.2%"], ["合併連續", "24.3%"], ["每天前 50%", "21.6%"], ["機率 ≥ 0.7", "23.5%"]];
  labs.forEach(([h, v], k) => {
    const cy = iy + ih * cent[k];
    T(sl, v ? [L(h, { bold: true, fontSize: 13 }), { text: v, options: { fontSize: 16, bold: true, color: C.accent2 } }] : [{ text: h, options: { bold: true, fontSize: 13 } }],
      { x: 0.6, y: cy - 0.36, w: 2.05, h: 0.72, valign: "middle", align: "right" });
  });
  const rx = 8.85, rw = 12.75 - rx;
  const v = (t, o = {}) => ({ text: t, options: { align: "center", valign: "middle", ...o } });
  const hd = (t) => ({ text: t, options: { bold: true, fill: { color: HEX.dk1 }, color: "FFFFFF", align: "center", valign: "middle" } });
  const rows = [[hd("168 檔平均"), hd("命中率"), hd("找到率")],
    [v("原始", { align: "left" }), v("27.7%"), v("48.4%")],
    [v("合併連續", { align: "left" }), v("29.0%"), v("37.9%")],
    [v("每天前 50%", { align: "left" }), v("28.8%"), v("24.8%")],
    [v("機率 ≥ 0.7", { align: "left" }), v("30.0%"), v("17.7%")]];
  sl.addTable(rows, { x: rx, y: 1.6, w: rw, colW: [1.7, 1.1, 1.1], rowH: 0.5, fontSize: 14, fontFace: THEME.bodyFontFace,
    color: HEX.dk1, border: { type: "solid", pt: 0.75, color: HEX.accent6 } });
  sl.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: rx, y: 4.45, w: rw, h: 1.5, rectRadius: 0.08, fill: { color: HEX.dk1 }, line: { type: "none" }, objectName: "filter-takeaway" });
  T(sl, [L("命中率幾乎沒提升"), { text: "找到率反而下降" }], { x: rx + 0.25, y: 4.45, w: rw - 0.4, h: 1.5, fontSize: 19, bold: true,
    color: C.background1, valign: "middle", paraSpaceAfter: 6 });
  sl.addNotes("這頁回答:如果用規則把低機率或重複的訊號篩掉,能不能更準地找出高低點?左邊是南電 2024 年在每種規則下留下的訊號,旁邊的數字是判低點的命中率。合併連續(即時版)是連續幾天都有訊號時,只有分數比之前都高才保留;每天前 50% 是每天依分數只留一半;機率 ≥ 0.7 是 Stacking 的最大機率要到 0.7 才出訊號。南電的判低點天數:原始 58 天、合併連續 37 天、前 50% 37 天、機率 ≥ 0.7 34 天,命中率從 17.2% 只提到 24.3%、21.6%、23.5%,抓到的真低點也從 10 個掉到 8、9 個。右邊是全部 168 檔、2024 到 2026 三年平均:判低點命中率從 27.7% 只到 28.8% 到 30.0%,找到率卻從 48.4% 掉到 17.7% 到 37.9%。結論:篩訊號沒辦法更準地找出高低點。");
}

// ======================= 6. 方向 =======================
pres.addSection({ title: "方向" });
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "方向" });
  sl.addText("方向:決策輔助系統", { placeholder: "title" });
  const keys = [["命中率約三成", C.accent2], ["多判訊號多", C.accent2], ["篩訊號沒更準", C.accent2]];
  keys.forEach(([t, col], i) => {
    const y = 1.65 + i * 1.6;
    card(sl, { x: 0.6, y, w: 4.4, h: 1.25, objectName: `reason-${i}` });
    T(sl, t, { x: 0.6, y, w: 4.4, h: 1.25, fontSize: 24, bold: true, color: col, align: "center", valign: "middle" });
  });
  arrow(sl, 5.3, 4.05, 1.0, 0);
  sl.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.6, y: 1.65, w: 6.15, h: 4.45, rectRadius: 0.1, fill: { color: HEX.dk1 }, line: { type: "none" }, objectName: "direction" });
  T(sl, "決策輔助", { x: 6.9, y: 1.95, w: 5.55, h: 0.9, fontSize: 36, bold: true, color: C.background1 });
  ["TW200 訓練", "台灣 50 建議", "Stacking"].forEach((t, i) => {
    sl.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.9, y: 3.15 + i * 0.95, w: 5.55, h: 0.75, rectRadius: 0.08,
      fill: { color: "2A3A47" }, line: { type: "none" } });
    T(sl, t, { x: 7.15, y: 3.15 + i * 0.95, w: 5.1, h: 0.75, fontSize: 20, bold: true, color: C.background1, valign: "middle" });
  });
  sl.addNotes("綜合前面的結果:命中率約 3 成(TW200 三年平均判低點 27.7%、判高點 26.0%);多判的訊號多(南電 2024 判低點 58 天,只有 10 天是真低點);而且即使用規則篩掉低機率的訊號,命中率幾乎沒提升、找到率反而下降。所以我們不做自動交易,也不用回測來論證,而是做成給使用者方向的決策輔助系統:提醒哪裡可能是高點、低點,交易與否由使用者決定。做法是用 TW200 剔除低波動股後的 168 檔訓練 Stacking,這是最終版本;每天收盤後對台灣 50 的成分股給出高點、低點、非極值的三類機率;5 個交易日後用真實結果對答案、累積命中率給使用者參考。接下來是網頁系統的展示。");
}

// ======================= 7–9. 網頁系統 =======================
pres.addSection({ title: "網頁系統" });
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "網頁系統" });
  sl.addText("網頁:今日判斷", { placeholder: "title" });
  const h = 5.45, wd = h * 1280 / 1000, wm = h * 780 / 1650, gap = 0.45;
  const xd = (13.333 - wd - wm - gap) / 2, xm = xd + wd + gap;
  shot(sl, "kline_peak_ui_today_desktop_tw200.png", xd, 1.3, wd, h, "今日判斷(桌機)展示版畫面");
  shot(sl, "kline_peak_ui_today_mobile_tw200.png", xm, 1.3, wm, h, "今日判斷(手機)展示版畫面");
  sl.addNotes("接下來是網頁系統的展示版,畫面都是真實模型輸出,資料到 2026-09-10 收盤。網站只有 Stacking 一個方法,模型用 TW200 剔除低波動股訓練,推薦範圍是台灣 50,50 檔全部給判斷。網頁有四個頁面:今日判斷、個股查詢、成績追蹤、方法與說明。這頁是今日判斷:收盤後列出判低點、判高點,依該類的機率排序,每檔附信心等級,並依「已幾天沒破底 / 沒創高」分組;答案要再過 5 個交易日才知道。左邊是桌機、右邊是手機版,截圖只取上半部。");
}
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "網頁系統" });
  sl.addText("網頁:個股查詢", { placeholder: "title" });
  const h = 5.45, w1 = h * 1280 / 1180, x1 = 0.6;
  shot(sl, "kline_peak_ui_stock_8046_tw200.png", x1, 1.3, w1, h, "個股查詢:南電 8046 展示版畫面");
  const rx = x1 + w1 + 0.45, rw = 12.75 - rx, ih = rw * 440 / 1280;
  T(sl, "推薦範圍外", { x: rx, y: 1.3, w: rw, h: 0.4, fontSize: 15, bold: true, color: C.text2 });
  shot(sl, "kline_peak_ui_stock_2618_tw200.png", rx, 1.8, rw, ih, "個股查詢:推薦範圍以外的股票 2618 展示版畫面");
  sl.addNotes("個股查詢以南電 8046 為例,和第 4 頁是同一檔股票,屬於台灣 50。2026-09-10 收盤後,三類機率是高點 0.03、低點 0.14、非極值 0.82,加起來是 1,最大的那類就是判斷,所以判為非極值。下方是最近 60 個交易日的 K 線,標出過去的判斷,5 個交易日後對答案,實心是判對、空心是判錯。右邊是推薦範圍以外的股票,例如 2618 長榮航:不在台灣 50,網站一樣算出判斷,但會標示不在推薦範圍、僅供參考。");
}
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "網頁系統" });
  sl.addText("網頁:成績追蹤", { placeholder: "title" });
  const h = 5.45, w1 = h * 1280 / 990, x1 = 0.6;
  shot(sl, "kline_peak_ui_track_tw200.png", x1, 1.3, w1, h, "成績追蹤展示版畫面");
  const rx = x1 + w1 + 0.45, rw = 12.75 - rx;
  stat(sl, rx, 1.3, rw, 1.8, "31.7%", "判低點命中率", C.accent2, 36);
  stat(sl, rx, 3.35, rw, 1.8, "7.6%", "隨機猜", C.text1, 36);
  sl.addNotes("成績追蹤:每天的判斷當天就存檔,不會事後修改,5 個交易日後自動對答案。資料 2026-01-02 到 2026-09-10 是回放,也就是上線前用同一個模型逐日產生,9/10 起是實際追蹤。2026 年台灣 50 全部的判低點命中率是 31.7%,也就是 712 次判斷中對 226 次;依信心等級分,高 35.1%、中 31.8%、低 28.6%;隨便挑一天剛好是低點(台灣 50、已對答案的日子)的機率是 7.6%。這和研究結果的約三成一致,所以網站的定位是提醒,不是買賣指令。");
}

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
