// 專題發表簡報 v3(12 頁):封面 / 問題動機 / 系統架構 / 方法技術 / 成果數據 / 應用價值 / Demo / 結論,每頁左上角標段落名稱。
// 方法與數字只用 final 分支的結果檔(fig/numbers.json 由 figs_final.py 產生;fig/f_swing.png 由 figs_v3.py 產生)。
// 執行:PPTX_SKILL=<pptx skill 目錄> node make_presentation_v3.js [輸出路徑]
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const HERE = __dirname;
const FIG = path.join(HERE, "fig");
const OUT = process.argv[2] || path.join(HERE, "..", "專題簡報_v3.pptx");
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
  { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.52, w: 10.3, h: 0.75, fontSize: 28, bold: true, align: "left",
    color: C.text1, valign: "middle", margin: 0 }, text: "" } } ],
  slideNumber: { x: 12.25, y: 6.95, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent5, align: "right" } });

const T = (sl, text, o) => sl.addText(text, { isTextBox: true, margin: 0, fontSize: 16, color: C.text1, valign: "top", ...o });
// 左上角的段落名稱
const sec = (sl, name, dark = false) => T(sl, name, { x: dark ? 0.8 : 0.6, y: dark ? 0.6 : 0.17, w: 3, h: 0.32, fontSize: 13, bold: true,
  color: C.accent1, valign: "middle", charSpacing: 1 });
const card = (sl, o) => sl.addShape(pres.shapes.ROUNDED_RECTANGLE, { rectRadius: 0.08, fill: { color: C.background2 }, line: { type: "none" }, ...o });
const dark = (sl, o) => sl.addShape(pres.shapes.ROUNDED_RECTANGLE, { rectRadius: 0.1, fill: { color: HEX.dk1 }, line: { type: "none" }, ...o });
const stat = (sl, x, y, w, h, value, label, color = C.accent3, size = 32) => {
  card(sl, { x, y, w, h });
  T(sl, value, { x: x + 0.2, y: y + 0.1, w: w - 0.3, h: h * 0.58, fontSize: size, bold: true, color, valign: "middle", fit: "none" });
  T(sl, label, { x: x + 0.2, y: y + h * 0.64, w: w - 0.3, h: h * 0.3, fontSize: 14, color: C.text2 });
};
const arrow = (sl, x, y, w, h = 0, flipV = false) => sl.addShape(pres.shapes.LINE, { x, y, w, h, flipV,
  line: { color: HEX.accent5, width: 2, endArrowType: "triangle" } });
const img = (sl, file, x, y, w, h, alt) => sl.addImage({ path: path.join(FIG, file), x, y, w, h, altText: alt });
const imgSize = (file) => { const b = fs.readFileSync(path.join(FIG, file)); return [b.readUInt32BE(16), b.readUInt32BE(20)]; };
const fitW = (file, w) => { const [pw, ph] = imgSize(file); return w * ph / pw; };
const fitH = (file, h) => { const [pw, ph] = imgSize(file); return h * pw / ph; };
const pc = (v, n = 1) => `${(v * 100).toFixed(n)}%`;
const Y3 = ["2024", "2025", "2026"];
const yr = NUM.yearly, mtk = NUM.mtk, bt = NUM.backtest, RU = NUM.rule;
// 實測(final 的 results/timing_mainline.json)
const TM = { day_s: "2.48", train_s: "19.0", env: "Intel Xeon 2.10GHz、4 核、只用 CPU" };
// 聯發科 2025 年 6–9 月的兩段波段價差(還原價;figs_v3.py 由 outputs_2454_2025_tw200.csv 算出)
const SW = ["15.8%", "12.9%"];
const EACH = pc((NUM.share_low + NUM.share_high) / 2);   // 高點、低點各約占(三年合計)
const RAND = pc(NUM.random);

// ═════ 1. 封面 ═════
let s = pres.addSlide({ masterName: "DARK" });
sec(s, "封面", true);
s.addText("以深度學習為基礎之\n自動化K線辨識系統", { placeholder: "title" });
s.addText([{ text: "指導老師 李俊宏 老師", options: { breakLine: true } }, { text: "郭家齊 D1245765 · 呂偉湘 D1286314", options: { breakLine: true } },
  { text: "2026 年 11 月" }], { placeholder: "body" });
s.addNotes("各位老師、同學好,我們是郭家齊和呂偉湘,指導老師是李俊宏老師。我們的題目是「以深度學習為基礎之自動化K線辨識系統」。接下來大約十一分鐘,我們會依照問題動機、系統架構、方法技術、成果數據、應用價值、Demo 和結論的順序報告。");

// ═════ 2. 問題動機:給使用者判斷高低點 ═════
s = pres.addSlide({ masterName: "CONTENT" });
sec(s, "問題動機");
s.addText("給使用者判斷高低點", { placeholder: "title" });
{
  T(s, [{ text: "有波動才有利潤", options: { bold: true, color: C.text1 } }, { text: "  →  低點附近買、高點附近賣,關鍵是找出極值環境", options: { color: C.text2 } }],
    { x: 0.6, y: 1.45, w: 12.15, h: 0.5, fontSize: 20, valign: "middle" });
  const iw = 8.45, ih = fitW("f_swing.png", iw);
  img(s, "f_swing.png", 0.6, 2.15, iw, ih, `聯發科 2025 年 6–9 月收盤與真實高低點,兩段波段 +${SW[0]}、+${SW[1]}`);
  T(s, "聯發科 2025 年 6–9 月收盤(還原價)", { x: 0.6, y: 2.2 + ih, w: iw, h: 0.3, fontSize: 12, color: C.text2 });
  const rx = 9.35, rw = 12.75 - rx;
  stat(s, rx, 2.15, rw, 1.45, `各約 ${EACH}`, "真正的高點、低點", C.accent1, 28);
  stat(s, rx, 3.8, rw, 1.45, pc(NUM.share_non), "其餘都不是轉折", C.accent3, 28);
  dark(s, { x: 0.6, y: 5.85, w: 12.15, h: 0.9 });
  T(s, "高低點要事後 5 天才能確認,當天很難判斷", { x: 0.6, y: 5.85, w: 12.15, h: 0.9, fontSize: 22, bold: true, color: C.background1, align: "center", valign: "middle" });
}
s.addNotes(`先說動機。股市有波動才有利潤:獲利來自在低點附近買進、在高點附近賣出,所以關鍵是找出股價正處在極值的環境。我們這樣定義極值:某一天的收盤價,如果是它前後各五天、共十一天裡最高的,就是高點;最低的,就是低點;其他日子都不是轉折。這張圖是聯發科 2025 年六到九月的收盤,橘色三角形是高點、藍色是低點。像六月底的低點到七月中的高點,這一段漲了 ${SW[0]};九月初到九月中,也漲了 ${SW[1]}。如果能在低點附近注意到、在高點附近提高警覺,就能掌握這樣的波動;反過來,在高點附近才追進去,就可能買在最貴的位置。這就是我們關心極值環境的原因。困難在兩個地方。第一,極值很少:在 168 檔股票、三年的資料裡,高點和低點各只占約 ${EACH},其餘 ${pc(NUM.share_non)} 都不是轉折。第二,高低點要等之後五天的價格出來才能確認,所以當天很難判斷。所以我們要幫使用者判斷的,是「現在是不是極值環境」:系統標出值得留意的時機,至於要不要買賣,由使用者自己決定。`);

// ═════ 3. 問題動機:現有做法的限制與一句話 ═════
s = pres.addSlide({ masterName: "CONTENT" });
sec(s, "問題動機");
s.addText("現有做法的限制,與我們的一句話", { placeholder: "title" });
{
  const y = 1.5, h = 2.15, w1 = 3.75;
  [["KD、RSI", "轉折發生後幾天才反應"], ["全猜「非極值」", `準確率 ${pc(NUM.share_non)}\n卻一個極值也找不到`]].forEach(([a, b], i) => {
    const x = 0.6 + i * (w1 + 0.25);
    card(s, { x, y, w: w1, h });
    T(s, a, { x: x + 0.25, y: y + 0.3, w: w1 - 0.5, h: 0.7, fontSize: 26, bold: true, color: C.text2 });
    T(s, b, { x: x + 0.25, y: y + 1.1, w: w1 - 0.5, h: 0.8, fontSize: 17, color: C.text2 });
  });
  const ax = 0.6 + 2 * w1 + 0.25;
  arrow(s, ax + 0.12, y + h / 2, 0.5);
  const dx = ax + 0.8, dw = 12.75 - dx;
  dark(s, { x: dx, y, w: dw, h });
  T(s, "收盤當天就判斷", { x: dx + 0.3, y: y + 0.3, w: dw - 0.5, h: 0.7, fontSize: 26, bold: true, color: C.background1 });
  T(s, "只用當天以前的資料", { x: dx + 0.3, y: y + 1.1, w: dw - 0.5, h: 0.8, fontSize: 18, color: C.background1 });
  // 一句話
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 4.05, w: 0.09, h: 2.6, fill: { color: HEX.accent1 }, line: { type: "none" } });
  T(s, [
    { text: "我們開發一套 K 線高低點辨識系統,", options: { breakLine: true } },
    { text: "在收盤當天就指出股價是否處在極值環境:", options: { breakLine: true } },
    { text: "找到約 8 成的高低點,命中率從隨機的 ", options: {} },
    { text: RAND, options: { bold: true, color: C.text2 } },
    { text: " 提高到 ", options: {} },
    { text: pc(NUM.both_prec), options: { bold: true, color: C.accent1 } },
  ], { x: 0.95, y: 4.05, w: 11.8, h: 2.6, fontSize: 26, bold: true, valign: "middle", lineSpacingMultiple: 1.2 });
}
s.addNotes(`現在常見的做法有兩個限制。第一是 KD、RSI 這類技術指標,它們用過去一段時間的價格平滑計算,通常要等轉折發生後好幾天才反應,看到訊號時,最好的位置往往已經過去。第二是一般的分類模型:因為非極值占了 ${pc(NUM.share_non)},模型就算全部猜非極值,準確率也有 ${pc(NUM.share_non)},看起來很高,卻一個高點或低點都找不到,所以不能只看準確率。因此我們後面看兩個指標:找到率,是真正的高低點有幾成被找出來;命中率,是系統說是高低點的日子裡,有幾成是真的。我們的突破是:在收盤當天就判斷,而且只用當天以前的資料,不偷看未來。用一句話說明我們的專題:我們開發一套 K 線高低點辨識系統,在收盤當天就指出股價是否處在極值環境;在 168 檔股票、三年的逐年驗證中,找到約 8 成的高低點,命中率從隨機的 ${RAND} 提高到 ${pc(NUM.both_prec)}。這裡的隨機 ${RAND},就是隨便挑一天剛好是高點或低點的比例。接下來先看系統的整體架構。`);

// ═════ 4. 系統架構:四個管線(fig/f_arch_v2.png 由 figs_arch.py 產生,畫布 = 投影片實際尺寸 12.15 × 5.6 吋) ═════
s = pres.addSlide({ masterName: "CONTENT" });
sec(s, "系統架構");
s.addText("整體流程", { placeholder: "title" });
img(s, "f_arch_v2.png", 0.6, 1.3, 12.15, 5.6, "系統架構:資料管線、特徵管線、訓練管線、判斷與服務管線");
s.addNotes("系統分成四條管線。A 是資料管線:每天從 Yahoo 抓股價,更新到 K 線資料庫。B 是特徵管線:取最近六根 K 線,先用規則判斷今天收盤是不是最近六天的最高或最低;不是,就直接判為非極值;是,就把六根 K 線轉成 29 維型態特徵。C 是訓練管線:用前四年的資料,依前後五天、共十一天的最高或最低貼上標籤,高點和低點各訓練一組 AE,把 29 維壓縮到 16 維,再訓練 OC-SVM,存進模型庫。D 是判斷與服務管線:每天把今天的特徵和候選交給載入的模型打分數,判出高點、低點或非極值,存檔並顯示在網頁上;五個交易日後再對答案,對錯回到成績追蹤。使用者就在網頁上查看今日判斷、個股和成績。");

// ═════ 5. 方法技術:三個模組 ═════
s = pres.addSlide({ masterName: "CONTENT" });
sec(s, "方法技術");
s.addText("做了什麼:三個模組", { placeholder: "title" });
{
  const mods = [["①", "型態特徵", "6 根 K 線 → 29 個數字", "不同股價可共用模型"],
    ["②", "極值判斷", "規則 + AE + OC-SVM", "高點、低點各一組"],
    ["③", "網頁與對答案", "每天存檔", "5 天後自動對答案"]];
  const w = (12.15 - 0.3 * 2) / 3, y = 1.5, h = 3.35;
  mods.forEach(([n, head, a, b], i) => {
    const x = 0.6 + i * (w + 0.3);
    card(s, { x, y, w, h });
    T(s, n, { x: x + 0.3, y: y + 0.25, w: 0.8, h: 0.8, fontSize: 36, bold: true, color: C.accent1 });
    T(s, head, { x: x + 0.3, y: y + 1.05, w: w - 0.5, h: 0.7, fontSize: 26, bold: true });
    T(s, a, { x: x + 0.3, y: y + 1.9, w: w - 0.5, h: 0.55, fontSize: 18 });
    T(s, b, { x: x + 0.3, y: y + 2.5, w: w - 0.5, h: 0.55, fontSize: 16, color: C.text2 });
  });
  T(s, "克服的困難", { x: 0.6, y: 5.2, w: 3, h: 0.45, fontSize: 16, bold: true, color: C.text2 });
  const w2 = (12.15 - 0.3) / 2;
  [["極值太少", "高點、低點各約 7%"], ["不能偷看未來", "只用當天以前的資料"]].forEach(([a, b], i) => {
    const x = 0.6 + i * (w2 + 0.3);
    dark(s, { x, y: 5.75, w: w2, h: 0.95 });
    T(s, [{ text: a, options: { bold: true, fontSize: 20 } }, { text: `   ${b}`, options: { fontSize: 16 } }],
      { x: x + 0.3, y: 5.75, w: w2 - 0.5, h: 0.95, color: C.background1, valign: "middle" });
  });
}
s.addNotes("我們做了三個模組。第一是型態特徵:把六根 K 線的開高低收都除以當天收盤再取對數,成交量除以十日均量,得到 29 個數字;不同股價只要形狀一樣,數字就一樣,所有股票可以共用一個模型。第二是極值判斷,也就是規則加 AE 加 OC-SVM。第三是網頁與對答案:每天的判斷都存檔、不再修改,五個交易日後自動對答案。過程中要克服兩個困難:一是極值太少,高點、低點各只占約 7%;二是不能偷看未來,所有特徵只用當天以前的資料。");

// ═════ 6. 方法技術:為什麼這樣選、亮點 ═════
s = pres.addSlide({ masterName: "CONTENT" });
sec(s, "方法技術");
s.addText("為什麼這樣選、亮點在哪", { placeholder: "title" });
{
  T(s, "技術選擇", { x: 0.6, y: 1.45, w: 4, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
  const y = 2.0, h = 1.75;
  const box = (x, w, head, sub, isDark) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: isDark ? HEX.dk1 : HEX.lt2 }, line: { type: "none" } });
    T(s, head, { x: x + 0.2, y: y + 0.25, w: w - 0.4, h: 0.7, fontSize: 24, bold: true, color: isDark ? C.background1 : C.text1, align: "center" });
    T(s, sub, { x: x + 0.2, y: y + 1.0, w: w - 0.4, h: 0.55, fontSize: 16, color: isDark ? C.background1 : C.text2, align: "center" });
  };
  box(0.6, 3.6, "極值太少", "一般分類器傾向全判非極值");
  arrow(s, 4.3, y + h / 2, 0.6);
  box(5.0, 3.6, "先用規則縮小範圍", `${pc(NUM.rule_filtered_share)} 的日子直接判非極值`);
  arrow(s, 8.7, y + h / 2, 0.6);
  box(9.4, 3.35, "OC-SVM", "只學正樣本,不需平衡資料", true);
  T(s, "亮點", { x: 0.6, y: 4.1, w: 4, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
  const w = (12.15 - 0.3 * 2) / 3, y2 = 4.65, h2 = 1.75;
  stat(s, 0.6, y2, w, h2, "只用當天以前", "收盤當天就判斷,不偷看未來", C.accent3, 26);
  stat(s, 0.6 + (w + 0.3), y2, w, h2, "判反 0", "高低點不會判反(設計保證)", C.accent3, 30);
  stat(s, 0.6 + 2 * (w + 0.3), y2, w, h2, `${TM.train_s} 秒`, "只用 CPU 訓練一個年份", C.accent3, 30);
  T(s, `實測環境:${TM.env}`, { x: 0.6, y: 6.55, w: 12.15, h: 0.3, fontSize: 12, color: C.text2, align: "right" });
}
s.addNotes(`為什麼這樣選?因為極值太少,一般的分類器很容易把所有日子都判成非極值。所以我們先用規則把範圍縮小到可能是極值的日子:三年有 ${pc(NUM.rule_filtered_share)} 的日子在這一步就判為非極值,而真正的高低點全部留在候選裡。接著用 OC-SVM,它只用真的高點、或真的低點學習,不需要去平衡三類資料。亮點有三個:第一,只用收盤當天以前的資料;第二,高低點不會判反,因為判高點一定是最近六天最高、判低點一定是最低,這是設計上的保證;第三,只用 CPU,訓練一個年份只要 ${TM.train_s} 秒。`);

// ═════ 7. 成果數據:168 檔 × 三年 ═════
s = pres.addSlide({ masterName: "CONTENT" });
sec(s, "成果數據");
s.addText("168 檔 × 三年實測", { placeholder: "title" });
{
  const y = 1.45, w = (12.15 - 0.3 * 2) / 3, h = 1.85;
  stat(s, 0.6, y, w, h, pc(NUM.both_rec), "找到率(三年合計)", C.accent3, 44);
  stat(s, 0.6 + (w + 0.3), y, w, h, pc(NUM.both_prec), `命中率(隨機 ${RAND})`, C.accent1, 44);
  stat(s, 0.6 + 2 * (w + 0.3), y, w, h, "0", "高低點判反", C.accent3, 44);
  const hd = (t) => ({ text: t, options: { bold: true, fill: { color: HEX.dk1 }, color: "FFFFFF", align: "center", valign: "middle" } });
  const v = (t, o = {}) => ({ text: t, options: { align: "center", valign: "middle", ...o } });
  const rows = [[hd("測試年"), hd("macro-F1"), hd("找到率 低 / 高"), hd("命中率 低 / 高"), hd("判反")]];
  Y3.forEach((yy) => {
    const r = yr[yy];
    rows.push([v(yy === "2026" ? "2026(1–9 月)" : yy, { bold: true }), v(pc(r.macro_f1, 2)), v(`${pc(r.low_rec)} / ${pc(r.high_rec)}`),
      v(`${pc(r.low_prec)} / ${pc(r.high_prec)}`), v(String(r.reversed))]);
  });
  s.addTable(rows, { x: 0.6, y: 3.65, w: 12.15, colW: [2.4, 2.1, 2.9, 2.9, 1.85], rowH: 0.6, fontSize: 18,
    fontFace: THEME.bodyFontFace, color: HEX.dk1, border: { type: "solid", pt: 0.75, color: HEX.accent6 } });
}
s.addNotes(`成果是 168 檔股票、2024 到 2026 年的逐年實測。驗證方式是測哪一年,就只用前四年訓練,模型沒看過測試年的資料。三年合計,真正的高低點有 ${pc(NUM.both_rec)} 被找到;系統判為高點或低點的日子裡,有 ${pc(NUM.both_prec)} 是真的;高低點判反三年都是 0。下面是逐年的表,macro-F1 三年都在 53 到 55 之間,相當穩定;2026 年只有一到九月,找到率比較低。`);

// ═════ 8. 成果數據:跟 Baseline 比 ═════
s = pres.addSlide({ masterName: "CONTENT" });
sec(s, "成果數據");
s.addText("跟 Baseline 比", { placeholder: "title" });
{
  const wc = 5.0, hc = fitW("f_compare.png", wc);
  img(s, "f_compare.png", 0.6, 1.45, wc, hc, "找到率與命中率比較:隨機猜、只用規則、本系統");
  const cy = 1.65 + hc, ch = (6.75 - cy - 0.2) / 2;
  card(s, { x: 0.6, y: cy, w: wc, h: ch });
  T(s, [{ text: "比隨機", options: { bold: true, fontSize: 15, color: C.text2, breakLine: true } },
    { text: `命中率 ${RAND} → ${pc(NUM.both_prec)},約 4 倍`, options: { bold: true, fontSize: 18 } }],
    { x: 0.85, y: cy, w: wc - 0.4, h: ch, valign: "middle" });
  dark(s, { x: 0.6, y: cy + ch + 0.2, w: wc, h: ch });
  T(s, [{ text: "比只用規則", options: { bold: true, fontSize: 15, breakLine: true } },
    { text: `訊號少 ${pc(NUM.signal_days_fewer)}、命中率持平`, options: { bold: true, fontSize: 18, breakLine: true } },
    { text: `代價:找到率 100% → ${pc(NUM.both_rec)}`, options: { fontSize: 15 } }],
    { x: 0.85, y: cy + ch + 0.2, w: wc - 0.4, h: ch, valign: "middle", color: C.background1 });
  const rx = 6.0, rw = 12.75 - rx;
  T(s, "聯發科 2025 的高低點判斷", { x: rx, y: 1.4, w: rw, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
  const ih = 3.25, iw = fitH("f_2454.png", ih);
  img(s, "f_2454.png", rx + (rw - iw) / 2, 1.9, iw, ih, "聯發科 2025 真實高低點與系統判斷");
  const y = 5.35, w = (rw - 0.25 * 3) / 4, h = 1.4;
  [[`${mtk["高點"]["找到率_當天"]}%`, "高點找到率", C.accent1], [`${mtk["低點"]["找到率_當天"]}%`, "低點找到率", C.accent2],
   [`${mtk["高點"]["命中率"].toFixed(1)}%`, "高點命中率", C.accent1], [`${mtk["低點"]["命中率"].toFixed(1)}%`, "低點命中率", C.accent2]]
    .forEach(([v, l, col], i) => stat(s, rx + i * (w + 0.25), y, w, h, v, l, col, 24));
}
s.addNotes(`接著跟 Baseline 比較。比隨機:隨便挑一天剛好是極值的比例約 ${RAND},本系統的命中率是 ${pc(NUM.both_prec)},約 4 倍。比只用規則,也就是把所有候選直接當成高低點:它的找到率是 100%,命中率 ${pc(RU.both_prec)}。本系統的訊號少了 ${pc(NUM.signal_days_fewer)},命中率持平,代價是找到率降到 ${pc(NUM.both_rec)}。也就是說,成績主要來自規則;AE 加 OC-SVM 讓訊號變少,但還沒有讓命中率變高。右邊是聯發科 2025 年的例子,上面是真實的高低點,下面是系統的判斷,實心是判對、空心是判錯。這一年高點找到 ${mtk["高點"]["找到率_當天"]}%、低點找到 ${mtk["低點"]["找到率_當天"]}%,命中率 ${mtk["高點"]["命中率"].toFixed(1)}% 和 ${mtk["低點"]["命中率"].toFixed(1)}%,沒有判反。`);

// ═════ 9. 應用價值:效益與限制 ═════
s = pres.addSlide({ masterName: "CONTENT" });
sec(s, "應用價值");
s.addText("效益與限制", { placeholder: "title" });
{
  const cols = [
    ["效益", `約 ${Math.round(NUM.both_prec * 10)} 成`, "被標為訊號的日子是真的極值", `隨機只有 ${Math.round(NUM.random * 100)}%`],
    ["成本", `${TM.day_s} 秒`, "168 檔判斷一天", "只用 CPU、不需 GPU"],
    ["限制", `${bt.n} / ${bt.n} 虧損`, `${bt.n} 種策略扣成本後全部虧損`, `0050 同期 +${bt.etf0050}%`]];
  const w = (12.15 - 0.3 * 2) / 3, y = 1.5, h = 3.6;
  cols.forEach(([head, big, a, b], i) => {
    const x = 0.6 + i * (w + 0.3);
    card(s, { x, y, w, h });
    T(s, head, { x: x + 0.3, y: y + 0.25, w: w - 0.5, h: 0.5, fontSize: 20, bold: true, color: C.accent1 });
    T(s, big, { x: x + 0.3, y: y + 0.9, w: w - 0.5, h: 0.95, fontSize: 38, bold: true, fit: "none" });
    T(s, a, { x: x + 0.3, y: y + 2.0, w: w - 0.5, h: 0.6, fontSize: 16 });
    T(s, b, { x: x + 0.3, y: y + 2.65, w: w - 0.5, h: 0.6, fontSize: 16, color: C.text2 });
  });
  T(s, `實測環境:${TM.env};回測 2024–2025,30 種只做多策略,成本一趟 ${bt.cost}%`, { x: 0.6, y: 5.2, w: 12.15, h: 0.3, fontSize: 12, color: C.text2, align: "right" });
  dark(s, { x: 0.6, y: 5.7, w: 12.15, h: 1.05 });
  T(s, "看盤輔助:標出該留意的時機,買賣由使用者決定", { x: 0.6, y: 5.7, w: 12.15, h: 1.05, fontSize: 24, bold: true, color: C.background1, align: "center", valign: "middle" });
}
s.addNotes(`這個系統的效益,是把注意力集中在可能是極值的日子:被標為訊號的日子裡,約 ${Math.round(NUM.both_prec * 10)} 成是真的極值,隨便挑只有 ${Math.round(NUM.random * 100)}%。成本很低:在 ${TM.env} 的環境下,168 檔判斷一天只要 ${TM.day_s} 秒,不需要 GPU。限制也要照實說:誤判仍然多,約七成的訊號不是真的轉折;如果照訊號頻繁進出,手續費和稅會把獲利磨平。我們回測了 ${bt.n} 種只做多的策略,扣成本後全部虧損,同期 0050 是 +${bt.etf0050}%。回到第二頁說的:系統回答的是「現在是不是極值環境」,不是「現在該不該買賣」;它標出該留意的時機,買賣由使用者決定。所以它是看盤輔助,不是自動下單。`);

// ═════ 10. 應用價值:導入場域、誰會買、競爭對手 ═════
s = pres.addSlide({ masterName: "CONTENT" });
sec(s, "應用價值");
s.addText("導入場域、誰會買、競爭對手", { placeholder: "title" });
{
  const cols = [["導入場域", ["看盤軟體", "每日高低點提醒"], ["投資人", "收盤後篩選"]],
    ["誰會買", ["自主投資人", "盤後先看系統標出的股票"], ["看盤軟體業者", "增加提醒功能"]],
    ["競爭對手", ["KD、RSI", "等技術指標"], ["我們的差異", "收盤當天判斷、事後可對答案"]]];
  const w = (12.15 - 0.3 * 2) / 3, y = 1.5, h = 5.1;
  cols.forEach(([head, a, b], i) => {
    const x = 0.6 + i * (w + 0.3);
    card(s, { x, y, w, h });
    T(s, head, { x: x + 0.3, y: y + 0.3, w: w - 0.5, h: 0.6, fontSize: 22, bold: true, color: C.accent1 });
    [a, b].forEach(([big, sub], k) => {
      T(s, big, { x: x + 0.3, y: y + 1.25 + k * 1.75, w: w - 0.5, h: 0.65, fontSize: 26, bold: true });
      T(s, sub, { x: x + 0.3, y: y + 1.9 + k * 1.75, w: w - 0.5, h: 0.5, fontSize: 16, color: C.text2 });
    });
  });
}
s.addNotes("導入場域有兩個:一是看盤軟體,可以加上每日高低點提醒;二是投資人收盤後的篩選,先看系統標出的股票,再決定要不要深入研究。會買的人,是自主投資人,以及想增加提醒功能的看盤軟體業者。競爭對手是 KD、RSI 這類技術指標;它們要等轉折後幾天才反應,我們在收盤當天就判斷,而且每一次判斷都存檔、事後對答案,成績可以公開驗證。");

// ═════ 11. Demo(與 v2 第 11 頁相同:web-app 4832aa2 / 7ce69e3 的截圖與講稿) ═════
s = pres.addSlide({ masterName: "CONTENT" });
sec(s, "Demo");
s.addText("系統實機展示", { placeholder: "title" });
{
  const cells = [["今日判斷", "web_today.png"], ["輸入 2454 聯發科", "web_2454_search.png"], ["2026 整年的判斷", "web_2454_year.png"], ["成績追蹤", "web_track.png"]];
  const cw = (12.15 - 0.5) / 2, ch = 2.35, y0 = 1.3, lh = 0.4;
  cells.forEach(([t, f], i) => {
    const x = 0.6 + (i % 2) * (cw + 0.5), y = y0 + Math.floor(i / 2) * (ch + lh + 0.2);
    T(s, `${i + 1}  ${t}`, { x, y, w: cw, h: lh, fontSize: 16, bold: true });
    let w = cw, h = fitW(f, cw);
    if (h > ch) { h = ch; w = fitH(f, ch); }
    s.addShape(pres.shapes.RECTANGLE, { x: x - 0.02, y: y + lh - 0.02, w: w + 0.04, h: h + 0.04, fill: { color: "FFFFFF" }, line: { color: HEX.accent6, width: 1 } });
    img(s, f, x, y + lh, w, h, `網頁系統:${t}`);
  });
}
s.addNotes("接下來示範我們做的網頁系統,這裡的畫面都是系統實際運作的截圖。第一個畫面是今日判斷。每天收盤後執行一次更新,系統會抓當天的股價,重新計算每一檔股票的型態特徵,然後更新判斷。畫面上方的幾張數字卡,告訴使用者今天有幾檔被判為低點、幾檔被判為高點;下面分成左右兩欄,左邊是判低點的股票,右邊是判高點的股票。每一欄又依照「今天剛出現」和「前幾天判過、到今天還沒破底或還沒創新高」分組,組內依照分數排序,所以使用者一打開就知道今天最值得注意的是哪幾檔。第二步,如果想看某一檔股票,就到個股查詢,在搜尋框輸入代號,例如 2454 聯發科。輸入後,畫面會先顯示這檔股票最新的收盤價和漲跌,以及它是不是在推薦範圍內。第三步,往下看到今年整年的K線。K線上標出系統每一天的判斷:朝下的三角形是判高點,朝上的三角形是判低點,實心代表五天後對答案是對的,空心代表錯的,還沒滿五天的則標為待驗證。使用者可以很直觀地看到,系統過去在這檔股票上判了哪些位置。另外,個股頁也用三列把當天的判斷過程攤開來:第一列,今天是不是規則候選,也就是收盤是不是最近六天的最高或最低;第二列,模型給的分數;第三列,最後的判斷。這樣使用者不只看到結果,也看得到判斷是怎麼來的。最後是成績追蹤。系統每天的判斷在當天就會存檔,之後不會再修改;等五個交易日過後,系統會自動用真實的收盤價對答案,判斷是對還是錯,並把結果累積起來,算出命中率。畫面上可以看到最近 20 天、最近 60 天和今年全部的命中率,還有命中率隨時間變化的曲線,以及每天的明細。這讓使用者可以隨時檢查這個系統實際表現如何,再決定要怎麼參考它的判斷。");

// ═════ 12. 結論 ═════
s = pres.addSlide({ masterName: "CONTENT" });
sec(s, "結論");
s.addText("結論", { placeholder: "title" });
{
  const hl = [["收盤當天判斷", "只用當天以前的資料"], ["找到約 8 成高低點", "命中率約為隨機的 4 倍"], ["成績主要來自規則", "AE + OC-SVM:訊號少約兩成"]];
  const w = (12.15 - 0.3 * 2) / 3, y = 1.45, h = 2.2;
  hl.forEach(([a, b], i) => {
    const x = 0.6 + i * (w + 0.3);
    dark(s, { x, y, w, h });
    T(s, a, { x: x + 0.25, y: y + 0.35, w: w - 0.5, h: 0.9, fontSize: 26, bold: true, color: C.background1, align: "center" });
    T(s, b, { x: x + 0.25, y: y + 1.3, w: w - 0.5, h: 0.6, fontSize: 17, color: C.background1, align: "center" });
  });
  const y2 = 4.0, w2 = (12.15 - 0.3) / 2;
  card(s, { x: 0.6, y: y2, w: w2, h: 2.65 });
  T(s, "未來", { x: 0.9, y: y2 + 0.25, w: w2 - 0.5, h: 0.55, fontSize: 20, bold: true, color: C.accent1 });
  T(s, [{ text: "讓模型分辨真假極值(例如序列模型)", options: { breakLine: true, fontSize: 21, bold: true } }, { text: "每日自動更新", options: { fontSize: 21, bold: true } }],
    { x: 0.9, y: y2 + 0.95, w: w2 - 0.5, h: 1.5, paraSpaceAfter: 10 });
  card(s, { x: 0.6 + w2 + 0.3, y: y2, w: w2, h: 2.65 });
  T(s, "致謝", { x: 0.9 + w2 + 0.3, y: y2 + 0.25, w: w2 - 0.5, h: 0.55, fontSize: 20, bold: true, color: C.accent1 });
  T(s, "感謝李俊宏老師的指導", { x: 0.9 + w2 + 0.3, y: y2 + 0.95, w: w2 - 0.5, h: 0.8, fontSize: 24, bold: true });
}
s.addNotes("最後總結。回到一開始的問題:有波動才有利潤,而這個系統能在收盤當天,幫使用者標出可能是極值的時機。我們有三個亮點。第一,收盤當天判斷,只用當天以前的資料。第二,找到約 8 成的高低點,命中率約為隨機的 4 倍,而且高低點不會判反。第三,我們找到了成績的來源:主要來自規則,AE 加 OC-SVM 讓訊號少了約兩成,但命中率持平。未來我們想做兩件事:一是讓模型分辨真假極值,例如用序列模型看更長的 K 線脈絡;二是讓網頁每天收盤後自動更新。感謝李俊宏老師的指導,也謝謝各位的聆聽,歡迎提問。");

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
