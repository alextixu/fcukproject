// 專題發表簡報(12 頁):問題 → 解法 → 成果 → 價值。方法與數字只用 final 分支的結果檔(fig/numbers.json 由 figs_final.py 產生)。
// 執行:PPTX_SKILL=<pptx skill 目錄> node build_presentation.js [輸出路徑]
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const HERE = __dirname;
const FIG = path.join(HERE, "fig");
const OUT = process.argv[2] || path.join(HERE, "..", "final_presentation.pptx");
const NUM = JSON.parse(fs.readFileSync(path.join(FIG, "numbers.json"), "utf8"));

const THEME = {
  name: "Kline Final", headFontFace: "Microsoft JhengHei", bodyFontFace: "Microsoft JhengHei",
  colors: { dk1: "1F2A33", lt1: "FFFFFF", dk2: "4A5661", lt2: "EEF2F5", accent1: "E8622C", accent2: "2A6FD6",
    accent3: "1F2A33", accent4: "4A5661", accent5: "7A8691", accent6: "C9D2D9", hlink: "2A6FD6", folHlink: "4A5661" },
};
const HEX = THEME.colors;
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "以深度學習為基礎之自動化K線辨識系統";
pres.author = "郭家齊、呂偉湘";
const C = pres.SchemeColor;

const motif = (x0, y0, s, gap) => Array.from({ length: 11 }, (_, k) => ({
  rect: { x: x0 + k * (s + gap), y: y0, w: s, h: s, fill: { color: k === 5 ? C.accent1 : C.accent6 } } }));
pres.defineSlideMaster({ title: "DARK", background: { color: HEX.dk1 }, objects: [
  ...motif(0.8, 1.45, 0.22, 0.07),
  { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.0, w: 11.7, h: 1.9, fontSize: 44, bold: true, align: "left",
    color: C.background1, valign: "top", margin: 0 }, text: "" } },
  { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 4.35, w: 11.7, h: 2.3, fontSize: 20, align: "left",
    color: C.background2, valign: "top", margin: 0 }, text: "" } } ],
  slideNumber: { x: 12.25, y: 6.95, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent6, align: "right" } });
pres.defineSlideMaster({ title: "CONTENT", background: { color: HEX.lt1 }, margin: [0.5, 0.6, 0.6, 0.6], objects: [
  ...motif(11.1, 0.62, 0.11, 0.035),
  { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 10.3, h: 0.85, fontSize: 30, bold: true, align: "left",
    color: C.text1, valign: "middle", margin: 0 }, text: "" } } ],
  slideNumber: { x: 12.25, y: 6.95, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent5, align: "right" } });

const T = (sl, text, o) => sl.addText(text, { isTextBox: true, margin: 0, fontSize: 16, color: C.text1, valign: "top", ...o });
const card = (sl, o) => sl.addShape(pres.shapes.ROUNDED_RECTANGLE, { rectRadius: 0.08, fill: { color: C.background2 }, line: { type: "none" }, ...o });
const stat = (sl, x, y, w, h, value, label, color = C.accent3, size = 32) => {
  card(sl, { x, y, w, h });
  T(sl, value, { x: x + 0.2, y: y + 0.1, w: w - 0.3, h: h * 0.58, fontSize: size, bold: true, color, valign: "middle", fit: "none" });
  T(sl, label, { x: x + 0.2, y: y + h * 0.64, w: w - 0.3, h: h * 0.3, fontSize: 14, color: C.text2 });
};
const pending = (sl, x, y, w, h, text, size = 15) => {
  sl.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: "FFFFFF" },
    line: { color: HEX.accent5, width: 1.25, dashType: "dash" } });
  T(sl, text, { x, y, w, h, fontSize: size, color: C.accent5, align: "center", valign: "middle" });
};
const arrow = (sl, x, y, w, h = 0, flipV = false) => sl.addShape(pres.shapes.LINE, { x, y, w, h, flipV,
  line: { color: HEX.accent5, width: 2, endArrowType: "triangle" } });
const img = (sl, file, x, y, w, h, alt) => sl.addImage({ path: path.join(FIG, file), x, y, w, h, altText: alt });
const imgSize = (file) => { const b = fs.readFileSync(path.join(FIG, file)); return [b.readUInt32BE(16), b.readUInt32BE(20)]; };
const fitW = (file, w) => { const [pw, ph] = imgSize(file); return w * ph / pw; };
const fitH = (file, h) => { const [pw, ph] = imgSize(file); return h * pw / ph; };
const pc = (v, n = 1) => `${(v * 100).toFixed(n)}%`;
const Y3 = ["2024", "2025", "2026"];
const yr = NUM.yearly, mtk = NUM.mtk, bt = NUM.backtest;

// ═════ 1. 封面 ═════
let s = pres.addSlide({ masterName: "DARK" });
s.addText("以深度學習為基礎之\n自動化K線辨識系統", { placeholder: "title" });
s.addText([{ text: "指導老師 李俊宏 老師", options: { breakLine: true } }, { text: "郭家齊 D1245765 · 呂偉湘 D1286314", options: { breakLine: true } },
  { text: "2026 年 11 月" }], { placeholder: "body" });
s.addNotes("各位老師、同學好,我們是郭家齊和呂偉湘,指導老師是李俊宏老師。我們的專題題目是「以深度學習為基礎之自動化K線辨識系統」。簡單來說,這個系統每天收盤後,會看每一檔股票最近六天的K線,判斷今天是不是一段走勢裡的局部高點或局部低點。接下來大約十分鐘,我們會依照「問題、解法、成果、價值」的順序來說明:先講為什麼這件事難,再講我們怎麼做,接著用 168 檔股票、三年的逐年驗證來看成果,最後說明它可以怎麼被使用,以及它的限制在哪裡。");

// ═════ 2. 現況痛點 ═════
s = pres.addSlide({ masterName: "CONTENT" });
s.addText("轉折點太少,人工也看不完", { placeholder: "title" });
img(s, "f_ratio.png", 0.6, 1.5, 12.15, fitW("f_ratio.png", 12.15));
{
  const y = 4.0, w = (12.15 - 0.3) / 2;
  stat(s, 0.6, y, w, 2.3, pc(NUM.share_non), "全猜「非極值」的準確率 — 但一個轉折也找不到", C.accent3, 54);
  stat(s, 0.6 + w + 0.3, y, w, 2.3, "168 檔", "每天收盤後都要看一遍", C.accent3, 54);
}
s.addNotes(`我們先定義什麼是轉折點:如果某一天的收盤價,是它前後各五天、共十一天裡最高的,就叫局部高點;最低的,叫局部低點;其他日子叫非極值。上面這條長條就是 168 檔股票三年的實際比例:低點只占 ${pc(NUM.share_low)},高點只占 ${pc(NUM.share_high)},其餘 ${pc(NUM.share_non)} 都是非極值。這帶來兩個問題。第一,資料非常不平衡:一個模型就算什麼都不學、每天都猜非極值,準確率也有 ${pc(NUM.share_non)},看起來很高,卻一個轉折點都找不到,所以準確率不能拿來評估。第二,人工看盤不實際:要每天收盤後把 168 檔的K線都看一遍,再判斷哪些可能是轉折,非常花時間。`);

// ═════ 3. 現有方案的限制 + 一句話價值 ═════
s = pres.addSlide({ masterName: "CONTENT" });
s.addText("傳統指標要等幾天,我們收盤當天就判斷", { placeholder: "title" });
{
  card(s, { x: 0.6, y: 1.5, w: 4.3, h: 2.45 });
  T(s, "KD、RSI", { x: 0.85, y: 1.7, w: 3.9, h: 0.8, fontSize: 34, bold: true, color: C.text2 });
  T(s, "轉折出現後,要等幾天才反應", { x: 0.85, y: 2.65, w: 3.9, h: 1.0, fontSize: 18, color: C.text2 });
  arrow(s, 5.1, 2.72, 0.75);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.05, y: 1.5, w: 6.7, h: 2.45, rectRadius: 0.08, fill: { color: HEX.dk1 }, line: { type: "none" } });
  T(s, "收盤當天就指出可能的高低點", { x: 6.35, y: 1.7, w: 6.2, h: 0.8, fontSize: 28, bold: true, color: C.background1 });
  T(s, `找到約 8 成轉折點,命中率是隨機的 4 倍`, { x: 6.35, y: 2.65, w: 6.2, h: 0.9, fontSize: 20, color: C.background1 });
  const y = 4.3, w = (12.15 - 0.6) / 3;
  stat(s, 0.6, y, w, 2.2, pc(NUM.both_rec), "轉折點找到率(三年合計)", C.accent3, 48);
  stat(s, 0.6 + w + 0.3, y, w, 2.2, `${pc(NUM.both_prec)} / ${pc(NUM.random)}`, "命中率 / 隨機猜", C.accent3, 32);
  pending(s, 0.6 + 2 * (w + 0.3), y, w, 2.2, "待補:全市場掃描時間\n(timing_mainline.json)");
}
s.addNotes(`現在投資人最常用的是 KD、RSI 這類技術指標,但它們是用過去一段時間的價格平滑計算出來的,通常要等轉折發生後好幾天才會反應。我們的系統是在每天收盤後、只用當天以前的資料,就直接指出「今天可能是局部高點或低點」。用一句話說:收盤當天就指出可能的高低點,找到約 8 成的轉折點,命中率是隨機的 4 倍。這兩個數字來自 168 檔、2024 到 2026 三年的合計:真正的高點和低點,有 ${pc(NUM.both_rec)} 被系統判出來;系統判為高點或低點的日子裡,有 ${pc(NUM.both_prec)} 真的是轉折,而隨便挑一天剛好是轉折的比例只有 ${pc(NUM.random)}。右邊的全市場掃描時間,我們會用實測的數字補上。`);

// ═════ 4. 系統架構 ═════
s = pres.addSlide({ masterName: "CONTENT" });
s.addText("系統架構", { placeholder: "title" });
{
  const steps = ["每日股價", "規則篩候選", "29 維\n型態特徵", "AE +\nOC-SVM"];
  const bw = 1.85, gap = 0.45, y = 2.75, h = 1.5;
  steps.forEach((t, i) => {
    const x = 0.6 + i * (bw + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: bw, h, rectRadius: 0.1, fill: { color: i === 3 ? HEX.dk1 : HEX.lt2 }, line: { type: "none" } });
    T(s, t, { x, y, w: bw, h, fontSize: 20, bold: true, align: "center", valign: "middle", color: i === 3 ? C.background1 : C.text1 });
    arrow(s, x + bw + 0.07, y + h / 2, gap - 0.14);
  });
  const ox = 0.6 + 4 * (bw + gap), ow = 1.55;
  [["高點", HEX.accent1], ["非極值", HEX.accent5], ["低點", HEX.accent2]].forEach(([t, col], i) => {
    const yy = 2.05 + i * 1.0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: ox, y: yy, w: ow, h: 0.8, rectRadius: 0.08, fill: { color: "FFFFFF" }, line: { color: col, width: 2 } });
    T(s, t, { x: ox, y: yy, w: ow, h: 0.8, fontSize: 20, bold: true, align: "center", valign: "middle", color: col.replace("#", "") });
  });
  const wx = ox + ow + 0.45;
  arrow(s, ox + ow + 0.07, y + h / 2, 0.31);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: wx, y, w: 12.75 - wx, h, rectRadius: 0.1, fill: { color: HEX.lt2 }, line: { type: "none" } });
  T(s, "網頁", { x: wx, y, w: 12.75 - wx, h, fontSize: 20, bold: true, align: "center", valign: "middle" });
}
s.addNotes("這是整個系統的架構,從左到右。第一步,每天收盤後抓 168 檔股票的日K線。第二步,用一條簡單的規則先篩候選:如果今天收盤是最近六天最高,就是高點候選;最低,就是低點候選;其他日子直接判為非極值。第三步,把候選日最近六天的K線轉成 29 個型態特徵。第四步,高點和低點各有一組模型:先用自編碼器 AE 把 29 維壓縮成 16 維,再用 OC-SVM 判斷這個型態像不像過去真正的高點或低點;像,就判為高點或低點,不像就改判非極值。最後每天的判斷會存下來,在網頁上顯示,五個交易日後自動對答案。");

// ═════ 5. 方法:把 K 線變成型態 ═════
s = pres.addSlide({ masterName: "CONTENT" });
s.addText("把 K 線變成可比對的型態", { placeholder: "title" });
{
  const h = 3.95, wk = fitH("f_feat_kline.png", h), wg = fitH("f_feat_grid.png", h);
  const gapA = 0.8, x0 = (13.333 - wk - wg - gapA) / 2;
  img(s, "f_feat_kline.png", x0, 1.45, wk, h, "聯發科 2025-02-26 的 t-5 到 t 六根 K 線");
  arrow(s, x0 + wk + 0.15, 1.45 + h / 2, gapA - 0.3);
  img(s, "f_feat_grid.png", x0 + wk + gapA, 1.45, wg, h, "29 個型態特徵");
  const y = 6.0, w = (12.15 - 0.3 * 2) / 3;
  [["÷ 當天收盤取 log", "不同股價共用模型"], ["只用當天以前", "不偷看未來"], ["29 個數字", "6 天 × 5 項 − 1"]].forEach(([a, b], i) => {
    const x = 0.6 + i * (w + 0.3);
    card(s, { x, y, w, h: 0.85 });
    T(s, [{ text: a, options: { bold: true, fontSize: 16, breakLine: true } }, { text: b, options: { fontSize: 13, color: C.text2 } }],
      { x: x + 0.2, y, w: w - 0.3, h: 0.85, valign: "middle" });
  });
}
s.addNotes("模型要比對的是「型態」,不是股價本身。左邊是聯發科 2025 年 2 月 26 日,也就是 t 日,和它前面五天、共六根K線。我們把每一根K線的開盤、最高、最低、收盤,都除以 t 日收盤再取 log,所以 t 日收盤就是 0,其他價格變成「比當天收盤高或低多少」;成交量則除以到當天為止的 10 日均量再取 log。這樣一千元的股票和一百元的股票,只要走勢形狀一樣,算出來的數字就一樣,所有股票可以共用同一個模型。右邊就是轉換後的結果:六天、每天五個數字,共 30 個,扣掉恆為 0 的 t 日收盤,剩下 29 個。所有特徵只用到 t 日收盤以前的資料,不會偷看未來;而這一天,事後確認也真的是局部高點,系統當天就判對了。");

// ═════ 6. 方法:為什麼這樣選 ═════
s = pres.addSlide({ masterName: "CONTENT" });
s.addText("為什麼先用規則,再用 OC-SVM", { placeholder: "title" });
{
  const y = 1.75, h = 2.6;
  const box = (x, w, head, sub, dark) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: dark ? HEX.dk1 : HEX.lt2 }, line: { type: "none" } });
    T(s, head, { x: x + 0.25, y: y + 0.35, w: w - 0.5, h: 0.9, fontSize: 30, bold: true, color: dark ? C.background1 : C.text1, align: "center" });
    T(s, sub, { x: x + 0.25, y: y + 1.35, w: w - 0.5, h: 1.0, fontSize: 18, color: dark ? C.background1 : C.text2, align: "center" });
  };
  box(0.6, 3.6, "每一天", "轉折只占約 14%");
  arrow(s, 4.3, y + h / 2, 0.6);
  box(5.0, 3.6, "規則候選", "最近 6 天最高 / 最低");
  arrow(s, 8.7, y + h / 2, 0.6);
  box(9.4, 3.35, "OC-SVM", "只學真的高(低)點", true);
  pending(s, 5.0, 4.6, 3.6, 0.85, "待補:規則濾掉的比例");
  T(s, "高低點太少,一般分類器會被非極值淹沒", { x: 0.6, y: 5.85, w: 12.15, h: 0.6, fontSize: 20, bold: true, color: C.text2, align: "center" });
}
s.addNotes("為什麼要先用規則、再用 OC-SVM?因為高點和低點加起來只占約 14%。如果直接拿一般的分類器來學三類,模型會被占八成以上的非極值淹沒,最省事的做法就是什麼都判非極值。所以我們分兩步。第一步用規則:真正的高點,收盤一定是最近六天最高;真正的低點,一定是最近六天最低。用這個條件先篩一次,不是候選的日子直接判非極值,大部分日子在這一步就被濾掉了,而且真正的高低點幾乎都會留在候選裡。第二步,在候選裡分辨真假。我們用 OC-SVM,也就是單類支持向量機,它只用「真的高點」(或真的低點)來學一個範圍,新的候選落在範圍內才保留。因為它只學一類,不需要在三類之間權衡,就不會被非極值淹沒。規則實際濾掉的比例,我們會用實際計算的數字補上。");

// ═════ 7. 成果:量化 ═════
s = pres.addSlide({ masterName: "CONTENT" });
s.addText("168 檔 × 三年,逐年驗證", { placeholder: "title" });
{
  const y = 1.45, w = (12.15 - 0.3 * 3) / 4, h = 1.75;
  stat(s, 0.6, y, w, h, pc(NUM.low_rec), "低點找到率", C.accent2, 40);
  stat(s, 0.6 + (w + 0.3), y, w, h, pc(NUM.high_rec), "高點找到率", C.accent1, 40);
  stat(s, 0.6 + 2 * (w + 0.3), y, w, h, `${pc(NUM.low_prec)}/${pc(NUM.high_prec)}`, "命中率 低 / 高", C.accent3, 26);
  stat(s, 0.6 + 3 * (w + 0.3), y, w, h, "0", "高低點判反(規則保證)", C.accent3, 40);
  const hd = (t) => ({ text: t, options: { bold: true, fill: { color: HEX.dk1 }, color: "FFFFFF", align: "center", valign: "middle" } });
  const v = (t, o = {}) => ({ text: t, options: { align: "center", valign: "middle", ...o } });
  const rows = [[hd("測試年"), hd("macro-F1"), hd("找到率 低 / 高"), hd("命中率 低 / 高"), hd("判反")]];
  Y3.forEach((yy) => {
    const r = yr[yy];
    rows.push([v(yy === "2026" ? "2026(1–9 月)" : yy, { bold: true }), v(pc(r.macro_f1, 2)), v(`${pc(r.low_rec)} / ${pc(r.high_rec)}`),
      v(`${pc(r.low_prec)} / ${pc(r.high_prec)}`), v(String(r.reversed))]);
  });
  s.addTable(rows, { x: 0.6, y: 3.55, w: 12.15, colW: [2.4, 2.1, 2.9, 2.9, 1.85], rowH: 0.62, fontSize: 18,
    fontFace: THEME.bodyFontFace, color: HEX.dk1, border: { type: "solid", pt: 0.75, color: HEX.accent6 } });
}
s.addNotes(`這是 168 檔股票、2024 到 2026 年的成績。驗證方式是逐年往前推:測 2024 年,就只用 2020 到 2023 年訓練;測 2025 年,用 2021 到 2024 年,以此類推,模型永遠沒看過測試年的資料。上面四個數字是三年合計:真低點有 ${pc(NUM.low_rec)} 被找到,真高點有 ${pc(NUM.high_rec)};判為低點的日子裡 ${pc(NUM.low_prec)} 是真的,判為高點的日子裡 ${pc(NUM.high_prec)} 是真的。下面的表是逐年的數字,macro-F1 三年都在 53 到 55 之間,很穩定;2026 年只有一到九月,找到率比較低一點。最右邊的判反三年都是 0,意思是系統從來沒有把高點判成低點、或把低點判成高點。這一點是規則設計保證的:判高點一定是最近六天最高,判低點一定是最近六天最低,兩者不可能同時成立。`);

// ═════ 8. 成果:比較 ═════
s = pres.addSlide({ masterName: "CONTENT" });
s.addText("和隨機猜、只用規則比較", { placeholder: "title" });
{
  const hc = 4.6, wc = Math.min(fitH("f_compare.png", hc), 4.5);
  img(s, "f_compare.png", 0.6, 1.8, wc, fitW("f_compare.png", wc), "命中率比較:隨機猜、只用規則、本系統");
  T(s, "命中率", { x: 0.6, y: 1.35, w: wc, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
  const rx = 5.4, rw = 12.75 - rx;
  T(s, "聯發科 2025(表現較佳的個股)", { x: rx, y: 1.35, w: rw, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
  const ih = 3.25, iw = fitH("f_2454.png", ih);
  img(s, "f_2454.png", rx + (rw - iw) / 2, 1.85, iw, ih, "聯發科 2025 真實高低點與系統判斷");
  const y = 5.3, w = (rw - 0.25 * 3) / 4, h = 1.4;
  [[`${mtk["高點"]["找到率_當天"]}%`, "高點找到率", C.accent1], [`${mtk["低點"]["找到率_當天"]}%`, "低點找到率", C.accent2],
   [`${mtk["高點"]["命中率"].toFixed(1)}%`, "高點命中率", C.accent1], [`${mtk["低點"]["命中率"].toFixed(1)}%`, "低點命中率", C.accent2]]
    .forEach(([v, l, col], i) => stat(s, rx + i * (w + 0.25), y, w, h, v, l, col, 24));
}
s.addNotes(`左邊比較三種做法的命中率,也就是判出來的高低點裡有多少是真的。隨便挑一天剛好是轉折的比例是 ${pc(NUM.random)};本系統是 ${pc(NUM.both_prec)},大約 4 倍。中間「只用規則」,也就是把所有候選都直接當成高低點,我們會補上實際的數字,用來說明 AE 加 OC-SVM 這一步額外帶來多少。右邊是一個實際例子:聯發科 2025 年,這是 168 檔裡表現較佳的個股。上面是真實的高低點,下面是系統每天的判斷,實心代表判對、空心代表判錯。這一年真高點 ${mtk["高點"]["真"]} 個、真低點 ${mtk["低點"]["真"]} 個;系統判高點 ${mtk["高點"]["判"]} 天,對 ${mtk["高點"]["對"]} 天,判低點 ${mtk["低點"]["判"]} 天,對 ${mtk["低點"]["對"]} 天。所以高點找到 ${mtk["高點"]["找到率_當天"]}%、低點找到 ${mtk["低點"]["找到率_當天"]}%,命中率分別是 ${mtk["高點"]["命中率"]}% 和 ${mtk["低點"]["命中率"]}%,也沒有任何判反。可以看到空心的錯誤多半集中在真正轉折的前後幾天。`);

// ═════ 9. 能不能拿來交易 ═════
s = pres.addSlide({ masterName: "CONTENT" });
s.addText("能不能直接拿來交易?", { placeholder: "title" });
{
  const wb = 7.6;
  img(s, "f_backtest.png", 0.6, 1.4, wb, fitW("f_backtest.png", wb), "30 種只做多策略扣成本後的報酬與 0050");
  const rx = 8.6, rw = 12.75 - rx;
  stat(s, rx, 1.4, rw, 1.55, `${bt.n} / ${bt.n} 虧損`, `扣成本 ${bt.cost}% 後(2024–2025)`, C.accent3, 30);
  stat(s, rx, 3.15, rw, 1.55, `約 ${Math.round((1 - NUM.both_prec) * 10)} 成`, "訊號不是真的轉折", C.accent3, 30);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.25, w: 12.15, h: 1.35, rectRadius: 0.1, fill: { color: HEX.dk1 }, line: { type: "none" } });
  T(s, "定位:看盤輔助,不是自動交易訊號", { x: 0.6, y: 5.25, w: 12.15, h: 1.35, fontSize: 28, bold: true, color: C.background1, align: "center", valign: "middle" });
}
s.addNotes(`很多人會問:既然找得到八成的轉折點,能不能直接拿來交易?我們照實回答:不行。痛點在於誤判太多,判出來的訊號約七成不是真的轉折點;如果照訊號頻繁進出,每一趟買賣的成本是 ${bt.cost}%,包含兩次手續費和證交稅,很快就把損益磨平。我們在 2024 到 2025 兩年,試了 ${bt.n} 種只做多的策略,包括不同的持有天數、檔數、判高點出場、等確認、均線過濾和停損,扣掉成本後全部虧損,最好的一種是 ${bt.best}%;同一段期間,直接買進持有 0050 是 +${bt.etf0050}%。所以我們把系統定位為看盤時的輔助:它告訴你「這裡可能是局部高點或低點,值得看一下」,要不要買賣由使用者自己判斷,而不是自動下單的交易訊號。`);

// ═════ 10. 應用價值 ═════
s = pres.addSlide({ masterName: "CONTENT" });
s.addText("應用價值", { placeholder: "title" });
{
  const cols = [["誰會用", ["自主投資人", "看盤軟體"]], ["效益", null], ["競爭對手", ["傳統技術指標", "KD、RSI 要等幾天"]]];
  const w = (12.15 - 0.3 * 2) / 3, y = 1.5, h = 3.9;
  cols.forEach(([head, items], i) => {
    const x = 0.6 + i * (w + 0.3);
    card(s, { x, y, w, h });
    T(s, head, { x: x + 0.3, y: y + 0.25, w: w - 0.5, h: 0.6, fontSize: 22, bold: true, color: C.accent3 });
    if (items) {
      items.forEach((t, k) => T(s, t, { x: x + 0.3, y: y + 1.1 + k * 1.05, w: w - 0.5, h: 0.9, fontSize: k === 0 ? 26 : 20,
        bold: k === 0, color: k === 0 ? C.text1 : C.text2 }));
    } else {
      pending(s, x + 0.3, y + 1.05, w - 0.6, 1.15, "待補:全市場掃描時間\n(timing_mainline.json)", 14);
      pending(s, x + 0.3, y + 2.4, w - 0.6, 1.15, "待補:運算環境\n(timing_mainline.json)", 14);
    }
  });
  pending(s, 0.6, 5.7, 12.15, 0.95, "待補:市場規模(有出處的公開數字,標註出處)", 16);
}
s.addNotes("這個系統可以給誰用?第一類是自主投資人:每天收盤後,不用一檔一檔看K線,系統先把可能是高點或低點的股票挑出來,再由自己判斷要不要進一步研究。第二類是看盤軟體:可以把這個判斷當成一個提醒功能,放在既有的看盤畫面裡。效益的部分,我們會用實測的全市場掃描時間和運算環境補上。競爭對手是傳統技術指標,例如 KD、RSI,它們通常要等轉折發生幾天後才反應;我們的系統則是在收盤當天就給出判斷,而且每一次判斷都會存檔、五天後對答案,命中率是公開可驗證的。市場規模的部分,我們會用有出處的公開統計數字補上並標註出處。");

// ═════ 11. Demo ═════
s = pres.addSlide({ masterName: "CONTENT" });
s.addText("Demo:網頁系統", { placeholder: "title" });
{
  const steps = ["今日判斷", "輸入 2454 聯發科", "整年的判斷", "成績追蹤"];
  const w = (12.15 - 0.4 * 3) / 4, y = 1.5;
  steps.forEach((t, i) => {
    const x = 0.6 + i * (w + 0.4);
    T(s, `${i + 1}  ${t}`, { x, y, w, h: 0.5, fontSize: 18, bold: true });
    pending(s, x, y + 0.6, w, 4.4, "截圖待補", 16);
    if (i < 3) arrow(s, x + w + 0.05, y + 2.8, 0.3);
  });
}
s.addNotes("接下來示範網頁系統。第一個畫面是今日判斷:每天收盤後,列出今天被判為低點和高點的股票。第二步,在個股查詢輸入 2454 聯發科,可以看到這一檔今天的判斷。第三步,往下看它今年整年的判斷:K線上標出每一次判斷,五天後對答案,判對和判錯一目了然。最後是成績追蹤:每天的判斷當天就存檔,不會事後修改,五個交易日後自動對答案,累積成命中率,讓使用者知道這個系統實際上有多準。(這一頁的截圖會在網頁完成後換上,之後也可能改成直接播放操作影片。)");

// ═════ 12. 結論 ═════
s = pres.addSlide({ masterName: "CONTENT" });
s.addText("結論", { placeholder: "title" });
{
  const hl = [["收盤當天判斷", "只用當天以前的資料"], [`找到約 8 成轉折`, `命中率約為隨機的 4 倍`], ["高低點從不判反", "168 檔 × 三年逐年驗證"]];
  const w = (12.15 - 0.3 * 2) / 3, y = 1.45, h = 2.2;
  hl.forEach(([a, b], i) => {
    const x = 0.6 + i * (w + 0.3);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: HEX.dk1 }, line: { type: "none" } });
    T(s, a, { x: x + 0.25, y: y + 0.35, w: w - 0.5, h: 0.9, fontSize: 26, bold: true, color: C.background1, align: "center" });
    T(s, b, { x: x + 0.25, y: y + 1.3, w: w - 0.5, h: 0.6, fontSize: 17, color: C.background1, align: "center" });
  });
  const y2 = 4.0, w2 = (12.15 - 0.3) / 2;
  card(s, { x: 0.6, y: y2, w: w2, h: 2.65 });
  T(s, "未來展望", { x: 0.9, y: y2 + 0.25, w: w2 - 0.5, h: 0.55, fontSize: 20, bold: true, color: C.accent3 });
  T(s, [{ text: "序列模型", options: { breakLine: true, fontSize: 24, bold: true } }, { text: "每日自動更新", options: { fontSize: 24, bold: true } }],
    { x: 0.9, y: y2 + 0.95, w: w2 - 0.5, h: 1.5, paraSpaceAfter: 10 });
  card(s, { x: 0.6 + w2 + 0.3, y: y2, w: w2, h: 2.65 });
  T(s, "致謝", { x: 0.9 + w2 + 0.3, y: y2 + 0.25, w: w2 - 0.5, h: 0.55, fontSize: 20, bold: true, color: C.accent3 });
  T(s, "感謝李俊宏老師的指導", { x: 0.9 + w2 + 0.3, y: y2 + 0.95, w: w2 - 0.5, h: 0.8, fontSize: 24, bold: true });
}
s.addNotes(`最後總結三個亮點。第一,系統在收盤當天就做判斷,只用當天以前的資料,不需要等轉折發生後好幾天。第二,在 168 檔股票、三年逐年驗證下,找到約 8 成的轉折點,命中率約為隨機的 4 倍。第三,高點和低點從來不會判反。我們也誠實面對限制:判出來的訊號裡,仍有約七成不是真的轉折,所以它是看盤的輔助,而不是交易訊號。未來我們想做兩件事:一是嘗試序列模型,看更長的K線脈絡,希望減少誤判;二是讓網頁每天收盤後自動更新。最後,感謝李俊宏老師一路以來的指導,也謝謝各位的聆聽,我們的報告到這裡,歡迎提問。`);

async function fixEastAsianFont(file, face) {
  const JSZip = require("jszip");
  const zip = await JSZip.loadAsync(fs.readFileSync(file), { createFolders: false });
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
