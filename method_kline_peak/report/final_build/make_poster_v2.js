// 專題海報(A1 直式 59.4 × 84.1 cm)。數字只用 final 分支的結果檔(fig/numbers.json)。
// 執行:node make_poster_v2.js [輸出路徑]
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const HERE = __dirname, FIG = path.join(HERE, "fig");
const OUT = process.argv[2] || path.join(HERE, "..", "專題海報_v2.pptx");
const NUM = JSON.parse(fs.readFileSync(path.join(FIG, "numbers.json"), "utf8"));
const FONT = "Microsoft JhengHei";
const BG = "F5F7FA", INK = "2B3640", INK2 = "5B6670", ACC = "2A6FD6", CARD = "FFFFFF", LINE = "D5DCE3";
const W = 59.4 / 2.54, H = 84.1 / 2.54, M = 0.85;

const pres = new pptxgen();
pres.defineLayout({ name: "A1P", width: W, height: H });
pres.layout = "A1P";
pres.title = "以深度學習為基礎之自動化K線辨識系統";
pres.author = "郭家齊、呂偉湘";
const s = pres.addSlide();
s.background = { color: BG };
const T = (text, o) => s.addText(text, { isTextBox: true, margin: 0, fontFace: FONT, fontSize: 26, color: INK, valign: "top", ...o });
const rect = (o) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { rectRadius: 0.18, line: { type: "none" }, ...o });
const pill = (x, y, text, w) => {
  const ww = w || (0.62 * text.length * 0.5 + 1.0);
  rect({ x, y, w: ww, h: 0.78, rectRadius: 0.39, fill: { color: ACC } });
  T(text, { x, y, w: ww, h: 0.78, fontSize: 34, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
};
const img = (f, x, y, w, h, alt) => s.addImage({ path: path.join(FIG, f), x, y, w, h, altText: alt });
const size = (f) => { const b = fs.readFileSync(path.join(FIG, f)); return [b.readUInt32BE(16), b.readUInt32BE(20)]; };
const hOf = (f, w) => { const [a, b] = size(f); return w * b / a; };
const wOf = (f, h) => { const [a, b] = size(f); return h * a / b; };
const arrow = (x, y, w, h = 0, o = {}) => s.addShape(pres.shapes.LINE, { x, y, w, h, line: { color: INK2, width: 3, endArrowType: "triangle" }, ...o });
const pending = (x, y, w, h, text) => {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.15, fill: { color: "FFFFFF" }, line: { color: "8A96A1", width: 2, dashType: "dash" } });
  T(text, { x, y, w, h, fontSize: 26, color: "8A96A1", align: "center", valign: "middle" });
};
const pc = (v, n = 1) => `${(v * 100).toFixed(n)}%`;
const CW = W - 2 * M;

// ── 標題區 ──
rect({ x: 0, y: 0, w: W, h: 3.7, rectRadius: 0, fill: { color: "FFFFFF" } });
s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 3.7, w: W, h: 0.08, fill: { color: ACC }, line: { type: "none" } });
T("以深度學習為基礎之自動化K線辨識系統", { x: M, y: 0.55, w: CW, h: 1.5, fontSize: 76, bold: true, align: "center", valign: "middle", fit: "none" });
{
  const tags = ["指導老師:李俊宏 老師", "學生:郭家齊、呂偉湘"];
  const tw = [7.2, 7.2], gap = 0.6, x0 = (W - tw[0] - tw[1] - gap) / 2;
  tags.forEach((t, i) => {
    const x = x0 + i * (tw[0] + gap);
    rect({ x, y: 2.4, w: tw[i], h: 0.9, rectRadius: 0.45, fill: { color: "FFFFFF" }, line: { color: ACC, width: 2.5 } });
    T(t, { x, y: 2.4, w: tw[i], h: 0.9, fontSize: 32, color: ACC, bold: true, align: "center", valign: "middle" });
  });
}

// ── 摘要 ──
let y = 4.05;
pill(M, y, "摘要", 3.2);
rect({ x: M, y: y + 1.0, w: CW, h: 3.0, fill: { color: CARD } });
const B = (t) => ({ text: t, options: { bold: true, color: INK } }), N_ = (t) => ({ text: t });
T([N_("台股每天的局部高點、低點各只占約 7%,人工每天看盤費時。本系統在收盤當天只看最近 "), B("6 根 K 線"),
  N_(",轉成 "), B("29 維型態特徵"), N_(",先以規則篩出候選日,再以自編碼器(AE)壓縮、單類支持向量機(OC-SVM)判斷像不像真正的高點或低點。以 "),
  B("168 檔股票、2024–2026 三年逐年驗證"), N_(`:真正的轉折點${pc(NUM.both_rec)}被找到(`), B("約 8 成"),
  N_(`),命中率 ${pc(NUM.both_prec)} 是隨機猜(${pc(NUM.random)})的 `), B("約 4 倍"), N_(",且"), B("高低點從不判反"),
  N_("。但多判的訊號仍多,本系統"), B("定位為看盤輔助"), N_(",而非自動交易訊號。")],
  { x: M + 0.45, y: y + 1.15, w: CW - 0.9, h: 2.7, fontSize: 29, color: INK2, valign: "middle", lineSpacingMultiple: 1.2 });

// ── 系統流程 ──
y = 8.25;
pill(M, y, "系統流程", 4.2);
rect({ x: M, y: y + 1.0, w: CW, h: 3.9, fill: { color: CARD } });
{
  const nodes = [["開始", 1.15, "oval"], ["抓每日股價", 1.9], ["計算 29 維\n特徵", 1.9], ["最近 6 天\n最高 / 最低?", 2.75, "dia"],
    ["AE 壓縮", 1.6], ["OC-SVM\n像高(低)點?", 2.75, "dia"], ["高點 / 低點", 1.9], ["存檔\n5 天後對答案", 2.2], ["網頁顯示", 1.7]];
  const gap = 0.36, total = nodes.reduce((a, n) => a + n[1], 0) + gap * (nodes.length - 1);
  let x = M + (CW - total) / 2; const cy = y + 2.15, bh = 1.3;
  const pos = [];
  nodes.forEach(([t, w, kind], i) => {
    const hh = kind === "dia" ? 1.7 : bh;
    const shape = kind === "dia" ? pres.shapes.DIAMOND : (kind === "oval" ? pres.shapes.OVAL : pres.shapes.ROUNDED_RECTANGLE);
    const dark = i === 6;
    s.addShape(shape, { x, y: cy - hh / 2, w, h: hh, rectRadius: 0.15, fill: { color: dark ? INK : (kind === "dia" ? "E7EEF9" : "EEF2F5") },
      line: kind === "dia" ? { color: ACC, width: 2 } : { type: "none" } });
    T(t, { x: x - (kind === "dia" ? 0.1 : 0), y: cy - hh / 2, w: w + (kind === "dia" ? 0.2 : 0), h: hh, fontSize: 24, bold: true,
      align: "center", valign: "middle", color: dark ? "FFFFFF" : INK });
    pos.push([x, w]);
    if (i < nodes.length - 1) {
      arrow(x + w + 0.03, cy, gap - 0.06);
      if (kind === "dia") T("是", { x: x + w - 0.05, y: cy - 0.62, w: gap + 0.1, h: 0.45, fontSize: 22, bold: true, color: ACC, align: "center" });
    }
    x += w + gap;
  });
  [3, 5].forEach((i) => {
    const [nx, nw] = pos[i], mx = nx + nw / 2, by = y + 3.85;
    arrow(mx, cy + 0.86, 0, by - cy - 0.86);
    T("否", { x: mx + 0.1, y: cy + 0.95, w: 0.6, h: 0.45, fontSize: 22, bold: true, color: ACC });
    rect({ x: mx - 1.0, y: by, w: 2.0, h: 0.72, rectRadius: 0.36, fill: { color: "D9DEE3" } });
    T("非極值", { x: mx - 1.0, y: by, w: 2.0, h: 0.72, fontSize: 24, bold: true, align: "center", valign: "middle", color: INK2 });
  });
}

// ── 欄位(格線:左欄 LW、右欄 RW,區塊間距 GAP;所有座標由下面的常數推出) ──
const top = 13.5, BOT = H - M, COLG = 0.45, LW = 6.4, RX = M + LW + COLG, RW = W - M - RX;
const PILLH = 0.78, PILLG = 0.22, GAP = 0.35, PAD = 0.3, IW = RW - 2 * PAD;
const LAYOUT = {};
const pillAt = (x, y, text, w) => { pill(x, y, text, w); return y + PILLH + PILLG; };
const frame = (f, x, y, w, h, alt) => {
  s.addShape(pres.shapes.RECTANGLE, { x: x - 0.03, y: y - 0.03, w: w + 0.06, h: h + 0.06, fill: { color: "FFFFFF" }, line: { color: LINE, width: 1.5 } });
  img(f, x, y, w, h, alt);
};
const RPW = 8.2;                                   // 三個成果標題膠囊同寬

// ── 右欄 ──
// 成果一:模型成績(表 + 長條圖 | 混淆矩陣,上下緣對齊)
let ry = pillAt(RX, top, "成果一  模型成績", RPW);
{
  const mw = 5.6, mh = mw * 1217 / 1463, lw = IW - mw - 0.4, th = 2.0, cph = mh - th - 0.15, cpw = cph * 2.381;
  const capH = 0.95, h = PAD + mh + 0.12 + capH + 0.15;
  rect({ x: RX, y: ry, w: RW, h, fill: { color: CARD } });
  const y0 = ry + PAD, x0 = RX + PAD;
  const hd = (t) => ({ text: t, options: { bold: true, fill: { color: INK }, color: "FFFFFF", align: "center", valign: "middle" } });
  const v = (t, o = {}) => ({ text: t, options: { align: "center", valign: "middle", ...o } });
  const RU = NUM.rule, MB = NUM.mine_from_baseline;
  const rows = [[hd("三年合計"), hd("macro-F1"), hd("找到率"), hd("命中率")],
    [v("隨機猜", { bold: true }), v("33.33%"), v(pc(NUM.random)), v(pc(NUM.random))],
    [v("只用規則", { bold: true }), v(pc(RU.macro_f1, 2)), v(pc(RU.both_rec)), v(pc(RU.both_prec))],
    [v("本系統", { bold: true }), v(pc(MB.macro_f1, 2)), v(pc(NUM.both_rec)), v(pc(NUM.both_prec))]];
  s.addTable(rows, { x: x0, y: y0, w: lw, colW: [lw * 0.25, lw * 0.25, lw * 0.25, lw * 0.25], rowH: th / 4, fontSize: 22, fontFace: FONT, color: INK,
    border: { type: "solid", pt: 1, color: LINE } });
  img("f_compare.png", x0 + (lw - cpw) / 2, y0 + th + 0.15, cpw, cph, "找到率與命中率比較:隨機猜、只用規則、本系統");
  img("f_conf_total.png", x0 + lw + 0.4, y0, mw, mh, "三年合計混淆矩陣(橘框為判反,皆為 0)");
  T([{ text: "成績主要來自規則", options: { bold: true, color: INK, breakLine: true } }, { text: `AE + OC-SVM 讓訊號少約兩成(${pc(NUM.signal_days_fewer)}),命中率持平` }],
    { x: x0, y: y0 + mh + 0.12, w: lw, h: capH, fontSize: 24, color: INK2, align: "center", valign: "middle" });
  T("三年合計;橘框(判反)= 0", { x: x0 + lw + 0.4, y: y0 + mh + 0.12, w: mw, h: capH, fontSize: 24, color: INK2, align: "center", valign: "middle" });
  LAYOUT["成果一"] = [RX, ry, RW, h]; ry += h + GAP;
}
// 成果二:系統 Demo(三張同尺寸 4:3 截圖並排)
ry = pillAt(RX, ry, "成果二  系統 Demo", RPW);
{
  const g = 0.3, sw = (IW - 2 * g) / 3, sh = sw * 0.75, capH = 0.55, h = PAD + sh + 0.1 + capH + 0.15;
  rect({ x: RX, y: ry, w: RW, h, fill: { color: CARD } });
  [["web_p_today.png", "今日判斷"], ["web_p_2454.png", "個股查詢(2454)"], ["web_p_track.png", "成績追蹤"]].forEach(([f, cap], i) => {
    const x = RX + PAD + i * (sw + g);
    frame(f, x, ry + PAD, sw, sh, `網頁:${cap}`);
    T(cap, { x, y: ry + PAD + sh + 0.1, w: sw, h: capH, fontSize: 24, color: INK2, align: "center", valign: "middle" });
  });
  LAYOUT["成果二"] = [RX, ry, RW, h]; ry += h + GAP;
}
// 成果三:以聯發科為例(高度 = 剩下的空間,右欄剛好到底)
ry = pillAt(RX, ry, "成果三  以聯發科為例的高低點判斷", RPW);
{
  const h = BOT - ry, ih = h - PAD - 0.65 - 0.15, iw = wOf("f_2454.png", ih);
  rect({ x: RX, y: ry, w: RW, h, fill: { color: CARD } });
  img("f_2454.png", RX + PAD, ry + PAD, iw, ih, "聯發科 2025 真實高低點與系統判斷");
  T("聯發科 2025 的高低點判斷", { x: RX + PAD, y: ry + PAD + ih + 0.05, w: iw, h: 0.6, fontSize: 24, color: INK2, align: "center", valign: "middle" });
  const m = NUM.mtk, sx = RX + PAD + iw + 0.4, sw2 = (RX + RW - PAD - sx - 0.3) / 2, sh2 = (ih + 0.65 - 0.3) / 2;
  [[`${m["高點"]["找到率_當天"].toFixed(1)}%`, "高點找到率", "E8622C"], [`${m["低點"]["找到率_當天"].toFixed(1)}%`, "低點找到率", "2A6FD6"],
   [`${m["高點"]["命中率"].toFixed(1)}%`, "高點命中率", "E8622C"], [`${m["低點"]["命中率"].toFixed(1)}%`, "低點命中率", "2A6FD6"]].forEach(([val, lab, col], k) => {
    const x = sx + (k % 2) * (sw2 + 0.3), y = ry + PAD + Math.floor(k / 2) * (sh2 + 0.3);
    rect({ x, y, w: sw2, h: sh2, fill: { color: "EEF2F5" } });
    T(val, { x, y: y + 0.1, w: sw2, h: sh2 * 0.6, fontSize: 48, bold: true, color: col, align: "center", valign: "middle" });
    T(lab, { x, y: y + sh2 * 0.62, w: sw2, h: sh2 * 0.32, fontSize: 24, color: INK2, align: "center", valign: "middle" });
  });
  LAYOUT["成果三"] = [RX, ry, RW, h];
}

// ── 左欄:研究流程 + 使用技術與資料,底部和右欄對齊 ──
{
  const techH = 3 * 0.62 + 2 * 0.14 + 2 * PAD;
  const techPillY = BOT - techH - PILLG - PILLH;
  let ly = pillAt(M, top, "研究流程", 4.2);
  const flowH = techPillY - GAP - ly;
  rect({ x: M, y: ly, w: LW, h: flowH, fill: { color: CARD } });
  LAYOUT["研究流程"] = [M, ly, LW, flowH];
  const steps = [["資料蒐集", "168 檔股票\n2016–2026 日K線"], ["標籤定義", "前後 5 天共 11 天\n最高 / 最低收盤"],
    ["型態特徵", "t−5~t 六根K線\n÷ t 收盤取 log,29 維"], ["規則篩候選", "最近 6 天最高 / 最低\n才是候選"],
    ["AE + OC-SVM 訓練", "29→16 維\n只學真的高(低)點"], ["逐年驗證", "前 4 年訓練、測下一年\n2024–2026"], ["網頁系統", "每日判斷\n5 天後對答案"]];
  const step = (flowH - 2 * PAD) / steps.length, y0 = ly + PAD;
  s.addShape(pres.shapes.LINE, { x: M + 0.6, y: y0 + 0.32, w: 0, h: step * (steps.length - 1), line: { color: LINE, width: 4 } });
  steps.forEach(([hh, d], i) => {
    const yy = y0 + i * step;
    s.addShape(pres.shapes.OVAL, { x: M + 0.3, y: yy + 0.02, w: 0.6, h: 0.6, fill: { color: ACC }, line: { color: "FFFFFF", width: 3 } });
    T(String(i + 1), { x: M + 0.3, y: yy + 0.02, w: 0.6, h: 0.6, fontSize: 24, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
    T(hh, { x: M + 1.15, y: yy - 0.02, w: LW - 1.35, h: 0.65, fontSize: 32, bold: true });
    T(d, { x: M + 1.15, y: yy + 0.68, w: LW - 1.35, h: step - 0.8, fontSize: 26, color: INK2 });
  });
  const ty = pillAt(M, techPillY, "使用技術與資料", 6.0);
  rect({ x: M, y: ty, w: LW, h: techH, fill: { color: CARD } });
  LAYOUT["使用技術"] = [M, ty, LW, techH];
  const tech = ["PyTorch", "scikit-learn", "pandas", "yfinance", "Matplotlib", "GitHub"];
  const tw = (LW - 2 * PAD - 0.2) / 2;
  tech.forEach((t, i) => {
    const xx = M + PAD + (i % 2) * (tw + 0.2), yy = ty + PAD + Math.floor(i / 2) * 0.76;
    rect({ x: xx, y: yy, w: tw, h: 0.62, rectRadius: 0.31, fill: { color: "FFFFFF" }, line: { color: ACC, width: 1.5 } });
    T(t, { x: xx, y: yy, w: tw, h: 0.62, fontSize: 24, bold: true, color: ACC, align: "center", valign: "middle" });
  });
}
const fmt = (a) => a.map((v) => v.toFixed(2)).join(", ");
Object.entries(LAYOUT).forEach(([k, a]) => console.log(`${k}: x, y, w, h = ${fmt(a)}  (底 ${(a[1] + a[3]).toFixed(2)}, 右 ${(a[0] + a[2]).toFixed(2)})`));
console.log("頁面:", W.toFixed(2), "x", H.toFixed(2), " 下緣界線", BOT.toFixed(2));

// 拿掉 zip 裡的資料夾項目
(async () => {
  await pres.writeFile({ fileName: OUT });
  const JSZip = require("jszip");
  const src = await JSZip.loadAsync(fs.readFileSync(OUT));
  const dst = new JSZip();
  for (const [name, f] of Object.entries(src.files)) {
    if (!f.dir) dst.file(name, await f.async("nodebuffer"), { createFolders: false });
  }
  fs.writeFileSync(OUT, await dst.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
  console.log("wrote", OUT);
})();
