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
// compare_8046_2024_tw200.json、README 的後處理 / 機率門檻表(Stacking、TW200 168 檔);三年平均由逐年數字算出。
const L = (t, o = {}) => ({ text: t, options: { breakLine: true, ...o } });

// ======================= 1. 封面 =======================
pres.addSection({ title: "開場" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "開場" });
s.addText("台股 11 天局部高低點三分類\nStacking 模型與決策輔助系統", { placeholder: "title" });
s.addText([
  { text: "TW200 訓練的 Stacking:2024–2026 混淆矩陣", options: { breakLine: true } },
  { text: "南電 8046 個案:找得到高低點,但篩訊號也沒有更準", options: { breakLine: true } },
  { text: "方向:不做自動交易,用 TW200 訓練、對台灣 50 給建議" },
], { placeholder: "body" });
s.addNotes("這份報告說明本專題的最終方向。模型是 Stacking,用 TW200 剔除低波動股後的 168 檔訓練。先看 2024 到 2026 年的混淆矩陣,再用南電 8046 說明模型找得到高低點、但即使篩掉低機率的訊號也沒有更準,最後說明為什麼改做給使用者方向的決策輔助系統。數字都來自 repo 內既有的結果檔,沒有重跑。");

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
  { text: "TW200 剔除低波動股後 168 檔;walk-forward,前 4 年訓練、測下一年:第一層用前 3 年、第二層用最後 1 年(例:測 2025 → 2021–2023 / 2024),種子 42" },
], { x: 0.6, y: 5.85, w: 12.15, h: 0.75, fontSize: 15 });
s.addNotes("方法是 Stacking,也是本專題的最終版本,分兩層。特徵是 t-5 到 t 六根 K 線的 29 維。第一層有高點、低點兩組模型:高點組只用真高點訓練一個線性自編碼器(29 維壓到 16 維),再用 OC-SVM 學「像真高點」的範圍;低點組做法一樣。第一層對每一天都打分數,不經規則篩選,得到 s_high 和 s_low。第二層是邏輯迴歸,把兩個分數變成低點、非極值、高點三類機率,判斷取機率最大的類,分數就是那個機率。訓練資料是 TW200 剔除低波動股後的 168 檔。訓練用 walk-forward:每個測試年用之前 4 年,前 3 年訓練第一層、最後 1 年訓練第二層,例如測 2025 年時第一層用 2021 到 2023、第二層用 2024,種子 42。");

// ======================= 3. TW200 混淆矩陣(只取 Stacking 那一排) =======================
pres.addSection({ title: "混淆矩陣" });
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "混淆矩陣" });
  sl.addText("TW200 混淆矩陣(Stacking,2024–2026)", { placeholder: "title" });
  const iw = 10.6, ih = iw * 685 / 2016, x0 = (13.333 - iw) / 2, y0 = 1.7;
  const tw = iw * 648 / 2016, g = iw * 36 / 2016;
  ["測試 2024", "測試 2025", "測試 2026(1–9 月)"].forEach((t, k) =>
    T(sl, t, { x: x0 + k * (tw + g), y: 1.32, w: tw, h: 0.32, fontSize: 14, bold: true, color: C.text2, align: "center", valign: "middle" }));
  sl.addImage({ path: path.join(HERE, "kline_peak_confusion_tw200_stack.png"), x: x0, y: y0, w: iw, h: ih, altText: "TW200 2024–2026 Stacking 混淆矩陣" });
  const cy = 5.3, ch = 1.5, cw = (12.15 - 0.25 * 3) / 4;
  [["找到率(三年平均)", "低 48.4% / 高 41.8%", "找到約一半低點、四成高點"],
   ["命中率(三年平均)", "低 27.7% / 高 26.0%", "隨機猜約 7%"],
   ["macro-F1(逐年)", "50.31 / 50.37 / 50.43", "2024 / 2025 / 2026"],
   ["高低點從未判反", "0", "真低判高、真高判低"]].forEach(([h, v, sub], k) => {
    const cx = 0.6 + k * (cw + 0.25);
    card(sl, { x: cx, y: cy, w: cw, h: ch, objectName: `conf-card-${k}` });
    T(sl, h, { x: cx + 0.2, y: cy + 0.12, w: cw - 0.35, h: 0.35, fontSize: 13, bold: true, color: C.text2 });
    T(sl, v, { x: cx + 0.2, y: cy + 0.5, w: cw - 0.3, h: 0.45, fontSize: 16, bold: true, color: C.accent2, fit: "none" });
    T(sl, sub, { x: cx + 0.2, y: cy + 1.02, w: cw - 0.3, h: 0.32, fontSize: 12, color: C.text2 });
  });
  sl.addNotes("這頁是 TW200(剔除低波動股後 168 檔)Stacking 在 2024 到 2026 年的混淆矩陣,列是真實標籤、欄是判斷。第一,高低點從未判反:真低點被判成高點、真高點被判成低點的格子三年都是 0,錯誤都發生在轉折點和非極值之間。第二,找到率三年平均真低點 48.4%、真高點 41.8%,也就是找到約一半的低點、四成的高點。第三,命中率三年平均判低點 27.7%、判高點 26.0%,約 3 成;隨機挑一天剛好是低點的機率約 7%。macro-F1 三年 50.31、50.37、50.43,很穩定。");
}

// ======================= 4. 南電 2024:真實高低點 vs Stacking 原始判斷 =======================
pres.addSection({ title: "南電 2024" });
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "南電 2024" });
  sl.addText("南電 2024:找得到高點和低點", { placeholder: "title" });
  T(sl, [{ text: "上:收盤與真實標籤   下:Stacking 原始判斷(TW200 模型)", options: { bold: true } },
    { text: "   實心 = 判對、空心 = 判錯", options: { color: C.text2 } }],
    { x: 0.6, y: 1.25, w: 12.15, h: 0.35, fontSize: 14, valign: "middle" });
  const iw = 12.15, ih = iw * 710 / 2676;
  sl.addImage({ path: path.join(HERE, "kline_peak_8046_tw200_stack_raw.png"), x: 0.6, y: 1.65, w: iw, h: ih, altText: "南電 8046 2024 真實高低點與 Stacking 原始判斷" });
  const cy = 5.15, ch = 1.6, cw = (12.15 - 0.25 * 3) / 4;
  [["真實轉折點", "高 17 / 低 16", "2024 年共 242 個交易日"],
   ["判低點 58 天", "對 10 / 錯 48", "16 個真低點抓到 10 個"],
   ["判高點 22 天", "對 7 / 錯 15", "17 個真高點抓到 7 個"],
   ["高低點判反", "0", "方向從未判錯"]].forEach(([h, v, sub], k) => {
    const cx = 0.6 + k * (cw + 0.25);
    card(sl, { x: cx, y: cy, w: cw, h: ch, objectName: `nd-card-${k}` });
    T(sl, h, { x: cx + 0.2, y: cy + 0.14, w: cw - 0.35, h: 0.35, fontSize: 14, bold: true, color: C.text2 });
    T(sl, v, { x: cx + 0.2, y: cy + 0.55, w: cw - 0.3, h: 0.5, fontSize: 20, bold: true, color: k === 1 ? C.accent2 : (k === 2 ? C.accent1 : C.text1), fit: "none" });
    T(sl, sub, { x: cx + 0.2, y: cy + 1.1, w: cw - 0.3, h: 0.35, fontSize: 12, color: C.text2 });
  });
  sl.addNotes("以南電 8046 的 2024 年為例,用 TW200 訓練的 Stacking(第一層 2020 到 2022、第二層 2023)。上面是收盤和真實標籤:真高點 17 個、真低點 16 個,全年大致下跌。下面是 Stacking 的原始判斷,實心是判對、空心是判錯。混淆矩陣的數字:判低點 58 天,對 10 錯 48;判高點 22 天,對 7 錯 15;真低點沒有被判成高點,真高點也沒有被判成低點。所以模型找得到大部分低點和部分高點,方向也沒有錯,但多判的訊號不少,錯的大多是真低點前後的連續下跌日。");
}

// ======================= 5. 南電:篩掉低機率訊號後 =======================
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "南電 2024" });
  sl.addText("篩掉低機率的訊號,有更準嗎?", { placeholder: "title" });
  const ix = 3.05, iw = 5.55, ih = iw * 2208 / 2676, iy = 1.3;
  sl.addImage({ path: path.join(HERE, "kline_peak_8046_tw200_filters.png"), x: ix, y: iy, w: iw, h: ih, altText: "南電 2024 各種篩選規則留下的訊號" });
  const cent = [0.0734, 0.2382, 0.4031, 0.5679, 0.7416, 0.9153];
  const labs = [
    ["真實標籤", "真低點 16、真高點 17"],
    ["原始判斷", "判低點 58 天,命中 17.2%"],
    ["合併連續(即時)", "判低點 37 天,命中 24.3%"],
    ["每天只取前 50%", "判低點 37 天,命中 21.6%"],
    ["機率 ≥ 0.7", "判低點 34 天,命中 23.5%"],
    ["等確認 1 天 ‡", "判低點 25 天,命中 40.0%"],
  ];
  labs.forEach(([h, v], k) => {
    const cy = iy + ih * cent[k];
    T(sl, [L(h, { bold: true, fontSize: 13 }), { text: v, options: { fontSize: 11, color: C.text2 } }],
      { x: 0.6, y: cy - 0.33, w: 2.4, h: 0.66, valign: "middle", align: "right" });
  });
  // 右側:全部 168 檔三年平均
  const rx = 8.9, rw = 12.75 - rx;
  T(sl, "全部 168 檔、2024–2026 平均(判低點)", { x: rx, y: 1.3, w: rw, h: 0.4, fontSize: 14, bold: true, color: C.accent2 });
  const v = (t, o = {}) => ({ text: t, options: { align: "center", valign: "middle", ...o } });
  const hd = (t) => ({ text: t, options: { bold: true, fill: { color: HEX.dk1 }, color: "FFFFFF", align: "center", valign: "middle" } });
  const rows = [[hd("做法"), hd("命中率"), hd("找到率")],
    [v("原始", { align: "left" }), v("27.7%"), v("48.4%")],
    [v("合併連續(即時)", { align: "left" }), v("29.0%"), v("37.9%")],
    [v("每天前 50%", { align: "left" }), v("28.8%"), v("24.8%")],
    [v("機率 ≥ 0.7", { align: "left" }), v("30.0%"), v("17.7%")]];
  sl.addTable(rows, { x: rx, y: 1.8, w: rw, colW: [1.75, 1.05, 1.05], rowH: 0.42, fontSize: 13, fontFace: THEME.bodyFontFace,
    color: HEX.dk1, border: { type: "solid", pt: 0.75, color: HEX.accent6 } });
  sl.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: rx, y: 4.1, w: rw, h: 1.45, rectRadius: 0.08, fill: { color: HEX.dk1 }, line: { type: "none" }, objectName: "filter-takeaway" });
  T(sl, [L("命中率幾乎沒提升", { bold: true, fontSize: 16 }), L("27.7% → 28.8%–30.0%", { fontSize: 13 }),
    L("找到率反而下降", { bold: true, fontSize: 16 }), { text: "48.4% → 17.7%–37.9%", options: { fontSize: 13 } }],
    { x: rx + 0.2, y: 4.15, w: rw - 0.35, h: 1.35, color: C.background1, valign: "middle" });
  T(sl, "‡ 要等隔天收盤才知道;真低點依定義一定會通過確認,命中率變高是因為晚一天才用得到", { x: rx, y: 5.7, w: rw, h: 0.95, fontSize: 12, color: C.text2 });
  sl.addNotes("這頁回答:如果用規則把低機率或重複的訊號篩掉,能不能更準地找出高低點?左邊是南電 2024 年在每種規則下留下的訊號。合併連續(即時版)是連續幾天都有訊號時,只有分數比之前都高才保留;每天只取前 50% 是每天依分數只留一半;機率 ≥ 0.7 是 Stacking 的最大機率要到 0.7 才出訊號。南電的判低點命中率從 17.2% 只提到 24.3%、21.6%、23.5%,抓到的真低點也從 10 個掉到 8、9 個。右邊是全部 168 檔、三年平均:判低點命中率從 27.7% 只到 28.8% 到 30.0%,找到率卻從 48.4% 掉到 17.7% 到 37.9%。等確認 1 天的命中率看起來比較高(南電 40.0%),但要等隔天收盤才知道,而且真低點本來就要求之後 5 天收盤都不低於當天,所以一定會通過確認,命中率變高是因為晚一天才用得到。結論:篩訊號沒辦法更準地找出高低點。");
}

// ======================= 6. 方向 =======================
pres.addSection({ title: "方向" });
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "方向" });
  sl.addText("方向:給使用者方向的決策輔助系統", { placeholder: "title" });
  const reasons = [
    ["命中率約三成", "TW200 三年平均:判低點 27.7%、判高點 26.0%"],
    ["多判的訊號多", "南電 2024 判低點 58 天,只有 10 天是真低點"],
    ["篩訊號也沒有更準", "命中率幾乎沒提升,找到率反而下降"],
  ];
  const cw = (12.15 - 0.25 * 2) / 3;
  reasons.forEach(([h, d], i) => {
    const x = 0.6 + i * (cw + 0.25);
    card(sl, { x, y: 1.4, w: cw, h: 1.6, objectName: `reason-${i}` });
    T(sl, h, { x: x + 0.25, y: 1.55, w: cw - 0.45, h: 0.5, fontSize: 19, bold: true, color: C.accent2 });
    T(sl, d, { x: x + 0.25, y: 2.1, w: cw - 0.45, h: 0.8, fontSize: 14 });
  });
  T(sl, "所以不做自動交易,也不用回測來論證", { x: 0.6, y: 3.25, w: 12.15, h: 0.5, fontSize: 18, bold: true, align: "center", color: C.text2 });
  sl.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 3.95, w: 12.15, h: 2.35, rectRadius: 0.08, fill: { color: HEX.dk1 }, line: { type: "none" }, objectName: "direction" });
  T(sl, "改做決策輔助:提醒哪裡可能是高點、低點,交易與否由使用者決定", { x: 0.9, y: 4.1, w: 11.6, h: 0.55, fontSize: 19, bold: true, color: C.background1 });
  T(sl, bullets([
    "訓練:TW200 剔除低波動股後 168 檔;模型為 Stacking(最終版本)",
    "建議:每天收盤後,對台灣 50 成分股給出高點 / 低點 / 非極值的三類機率",
    "追蹤:5 個交易日後用真實結果對答案,累積命中率給使用者參考",
  ]), { x: 0.9, y: 4.75, w: 11.6, h: 1.8, fontSize: 16, color: C.background1 });
  sl.addNotes("綜合前面的結果:命中率約 3 成,多判的訊號也多,而且即使用規則篩掉低機率的訊號也沒有更準。所以我們不做自動交易,也不用回測來論證,而是做成給使用者方向的系統。做法是:用 TW200 剔除低波動股後的 168 檔訓練 Stacking,這是最終版本;每天收盤後對台灣 50 的成分股給出高點、低點、非極值的三類機率;5 個交易日後用真實結果對答案、累積命中率,讓使用者自己判斷要不要參考。接下來是網頁系統的展示。");
}

// ======================= 7–9. 網頁系統(真實畫面,claude/kline-peak-web-app d0bbce2 的截圖) =======================
pres.addSection({ title: "網頁系統" });
const shot = (sl, file, x, y, w, h, alt) => {
  sl.addShape(pres.shapes.RECTANGLE, { x: x - 0.02, y: y - 0.02, w: w + 0.04, h: h + 0.04, fill: { color: HEX.lt1 },
    line: { color: HEX.accent6, width: 1 }, shadow: { type: "outer", color: "000000", opacity: 0.12, blur: 6, offset: 2, angle: 90 } });
  sl.addImage({ path: path.join(HERE, file), x, y, w, h, altText: alt });
};
const capt = (sl, text, x, y, w) => T(sl, text, { x, y, w, h: 0.3, fontSize: 13, bold: true, color: C.text2, valign: "middle" });
// 7. 今日判斷
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "網頁系統" });
  sl.addText("網頁系統:今日判斷", { placeholder: "title" });
  const info = [
    ["① 今日判斷", "收盤後對台灣 50 全部成分股給判斷,判低點 / 判高點依機率排序"],
    ["② 個股查詢", "輸入代號,看三類機率、近 60 天 K 線與過去判斷的對錯"],
    ["③ 成績追蹤", "判斷存檔,5 個交易日後自動對答案"],
    ["④ 方法與說明", "標籤定義、模型說明與免責聲明"],
  ];
  info.forEach(([h, d], i) => {
    const y = 1.3 + i * 1.25;
    card(sl, { x: 0.6, y, w: 3.55, h: 1.12, objectName: `page-${i}` });
    T(sl, h, { x: 0.8, y: y + 0.1, w: 3.2, h: 0.35, fontSize: 15, bold: true, color: C.accent2 });
    T(sl, d, { x: 0.8, y: y + 0.45, w: 3.2, h: 0.62, fontSize: 13, color: C.text1 });
  });
  const y0 = 1.65, h = 4.55, wd = h * 1280 / 1000, wm = h * 780 / 1650, xd = 4.5, xm = 12.75 - wm;
  capt(sl, "桌機(2026-09-10 收盤,真實模型輸出)", xd, 1.3, wd);
  shot(sl, "kline_peak_ui_today_desktop_tw200.png", xd, y0, wd, h, "今日判斷(桌機)展示版畫面");
  capt(sl, "手機", xm, 1.3, wm);
  shot(sl, "kline_peak_ui_today_mobile_tw200.png", xm, y0, wm, h, "今日判斷(手機)展示版畫面");
  sl.addNotes("接下來是網頁系統的展示版,畫面都是真實模型輸出,資料到 2026-09-10 收盤。網站只有 Stacking 一個方法,模型用 TW200 剔除低波動股訓練,推薦範圍是台灣 50,50 檔全部給判斷。網頁有四個頁面:今日判斷、個股查詢、成績追蹤、方法與說明。這頁是今日判斷:收盤後列出判低點、判高點,依三類機率中該類的機率排序,每檔附信心等級,並依「已幾天沒破底 / 沒創高」分組;答案要再過 5 個交易日才知道。左邊是桌機、右邊是手機版,截圖只取上半部。");
}
// 8. 個股查詢(南電)
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "網頁系統" });
  sl.addText("網頁系統:個股查詢(南電)", { placeholder: "title" });
  const y0 = 1.65, h = 5.05, w1 = h * 1280 / 1180, x1 = 0.6;
  capt(sl, "② 個股查詢:8046 南電(台灣 50)", x1, 1.3, w1);
  shot(sl, "kline_peak_ui_stock_8046_tw200.png", x1, y0, w1, h, "個股查詢:南電 8046 展示版畫面");
  const rx = x1 + w1 + 0.4, rw = 12.75 - rx;
  card(sl, { x: rx, y: 1.3, w: rw, h: 1.75, objectName: "stock-points" });
  T(sl, bullets(["三類機率:高點 / 低點 / 非極值,加起來是 1,最大的那類就是判斷",
    "K 線上標出過去的判斷,5 天後對答案:實心 = 對、空心 = 錯",
    "和第 4 頁同一檔股票"]), { x: rx + 0.2, y: 1.42, w: rw - 0.35, h: 1.55, fontSize: 13 });
  const ih = rw * 440 / 1280;
  capt(sl, "推薦範圍以外的股票(2618 長榮航)", rx, 3.35, rw);
  shot(sl, "kline_peak_ui_stock_2618_tw200.png", rx, 3.7, rw, ih, "個股查詢:池外股票 2618 展示版畫面");
  T(sl, "不在台灣 50 的股票照樣判斷,但會標示「僅供參考」", { x: rx, y: 3.8 + ih, w: rw, h: 0.55, fontSize: 13, color: C.text2 });
  sl.addNotes("個股查詢以南電 8046 為例,和第 4 頁是同一檔股票。2026-09-10 收盤後,三類機率是高點 0.03、低點 0.14、非極值 0.82,所以判為非極值。下方是最近 60 個交易日的 K 線,標出過去的判斷,5 個交易日後對答案,實心是判對、空心是判錯。右下是推薦範圍以外的股票,例如 2618 長榮航:不在台灣 50,網站一樣算出判斷,但會標示不在推薦範圍、僅供參考。");
}
// 9. 成績追蹤
{
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "網頁系統" });
  sl.addText("網頁系統:成績追蹤", { placeholder: "title" });
  const y0 = 1.65, h = 5.05, w1 = h * 1280 / 990, x1 = 0.6;
  capt(sl, "③ 成績追蹤:每天的判斷 5 個交易日後對答案", x1, 1.3, w1);
  shot(sl, "kline_peak_ui_track_tw200.png", x1, y0, w1, h, "成績追蹤展示版畫面");
  const rx = x1 + w1 + 0.4, rw = 12.75 - rx;
  const stats = [["判低點命中率", "31.7%", "2026 年台灣 50 全部判斷(226 / 712)"], ["依信心等級", "高 35.1% / 中 31.8% / 低 28.6%", "信心越高,命中率略高"], ["隨便挑一天剛好是低點", "7.6%", "台灣 50、已對答案的日子"]];
  stats.forEach(([hh, v, sub], i) => {
    const y = 1.3 + i * 1.5;
    card(sl, { x: rx, y, w: rw, h: 1.35, objectName: `track-${i}` });
    T(sl, hh, { x: rx + 0.2, y: y + 0.1, w: rw - 0.35, h: 0.32, fontSize: 13, bold: true, color: C.text2 });
    T(sl, v, { x: rx + 0.2, y: y + 0.42, w: rw - 0.35, h: 0.45, fontSize: i === 1 ? 15 : 22, bold: true, color: C.accent2 });
    T(sl, sub, { x: rx + 0.2, y: y + 0.9, w: rw - 0.35, h: 0.35, fontSize: 12, color: C.text2 });
  });
  sl.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: rx, y: 5.85, w: rw, h: 0.85, rectRadius: 0.08, fill: { color: HEX.dk1 }, line: { type: "none" }, objectName: "track-takeaway" });
  T(sl, "和研究結果一樣約三成,所以當提醒、不當指令", { x: rx + 0.2, y: 5.85, w: rw - 0.35, h: 0.85, fontSize: 14, bold: true, color: C.background1, valign: "middle" });
  sl.addNotes("成績追蹤:每天的判斷當天就存檔,不會事後修改,5 個交易日後自動對答案。資料 2026-01-02 到 2026-09-10 是回放,也就是上線前用同一個模型逐日產生,9/10 起是實際追蹤。2026 年台灣 50 全部的判低點命中率是 31.7%,也就是 712 次判斷中對 226 次;依信心等級分,高 35.1%、中 31.8%、低 28.6%;隨便挑一天剛好是低點的機率是 7.6%。這和研究結果的約三成一致,所以網站的定位是提醒,不是買賣指令。");
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
