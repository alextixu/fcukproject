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

// ── 欄位 ──
const top = 13.5, LW = 7.55, RX = M + LW + 0.5, RW = W - M - RX;
// 左:研究流程
pill(M, top, "研究流程", 4.2);
{
  const steps = [["資料蒐集", "TW200 剔除低波動股 168 檔,2016–2026 日K線"], ["標籤定義", "前後 5 天共 11 天的最高 / 最低收盤"],
    ["型態特徵", "t−5~t 六根K線 ÷ t 收盤取 log,29 維"], ["規則篩候選", "最近 6 天最高 / 最低才是候選"],
    ["AE + OC-SVM 訓練", "29→16 維,只學真的高(低)點"], ["逐年驗證", "前 4 年訓練、測下一年,2024–2026"], ["網頁系統", "每日判斷、5 天後對答案"]];
  const y0 = top + 1.2, step = 1.5;
  rect({ x: M, y: y0 - 0.2, w: LW, h: step * steps.length + 0.2, fill: { color: CARD } });
  s.addShape(pres.shapes.LINE, { x: M + 0.62, y: y0 + 0.3, w: 0, h: step * (steps.length - 1), line: { color: LINE, width: 4 } });
  steps.forEach(([h, d], i) => {
    const yy = y0 + i * step;
    s.addShape(pres.shapes.OVAL, { x: M + 0.35, y: yy + 0.03, w: 0.54, h: 0.54, fill: { color: ACC }, line: { color: "FFFFFF", width: 3 } });
    T(String(i + 1), { x: M + 0.35, y: yy + 0.03, w: 0.54, h: 0.54, fontSize: 22, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
    T(h, { x: M + 1.15, y: yy - 0.02, w: LW - 1.35, h: 0.6, fontSize: 30, bold: true });
    T(d, { x: M + 1.15, y: yy + 0.58, w: LW - 1.35, h: 0.85, fontSize: 24, color: INK2 });
  });
  // 使用技術與資料
  const ty = y0 + step * steps.length + 0.45;
  pill(M, ty, "使用技術與資料", 6.4);
  const tech = ["PyTorch", "scikit-learn", "pandas", "yfinance", "Matplotlib", "GitHub"];
  const tw = (LW - 0.35) / 2;
  tech.forEach((t, i) => {
    const xx = M + (i % 2) * (tw + 0.35), yy = ty + 1.1 + Math.floor(i / 2) * 0.95;
    rect({ x: xx, y: yy, w: tw, h: 0.8, rectRadius: 0.4, fill: { color: CARD }, line: { color: ACC, width: 2 } });
    T(t, { x: xx, y: yy, w: tw, h: 0.8, fontSize: 26, bold: true, color: ACC, align: "center", valign: "middle" });
  });
  const iy = ty + 1.1 + 3 * 0.95 + 0.3;
  const iw = LW, ih = Math.min(hOf("f_illus.png", iw), H - M - iy);
  img("f_illus.png", M + (LW - wOf("f_illus.png", ih)) / 2, iy, wOf("f_illus.png", ih), ih, "K 線插圖");
}
// 右:成果
let ry = top;
// (1)
pill(RX, ry, "成果 1  K 線型態特徵", 8.6);
{
  const y0 = ry + 1.2, h = 2.85;
  rect({ x: RX, y: y0 - 0.2, w: RW, h: h + 2.3, fill: { color: CARD } });
  const wk = wOf("f_feat_kline.png", h), wg = wOf("f_feat_grid.png", h), x0 = RX + (RW - wk - wg - 0.9) / 2;
  img("f_feat_kline.png", x0, y0, wk, h, "6 根 K 線");
  arrow(x0 + wk + 0.15, y0 + h / 2, 0.6);
  img("f_feat_grid.png", x0 + wk + 0.9, y0, wg, h, "29 格型態特徵");
  const cells = [["開、高、低 ÷ t 收盤", "× 6 天 = 18"], ["收盤 ÷ t 收盤", "× 5 天 = 5"], ["量 ÷ 10 日均量", "× 6 天 = 6"]];
  const cw = (RW - 0.6 - 0.3 * 2) / 3;
  cells.forEach(([a, b], i) => {
    const xx = RX + 0.3 + i * (cw + 0.3);
    rect({ x: xx, y: y0 + h + 0.15, w: cw, h: 1.0, fill: { color: "EEF2F5" } });
    T([{ text: a, options: { breakLine: true, bold: true } }, { text: b, options: { color: INK2 } }],
      { x: xx, y: y0 + h + 0.15, w: cw, h: 1.0, fontSize: 24, align: "center", valign: "middle" });
  });
  T("聯發科 2025-02-26 的 6 根 K 線 → 29 個數字", { x: RX + 0.3, y: y0 + h + 1.3, w: RW - 0.6, h: 0.6, fontSize: 24, color: INK2, align: "center" });
  ry = y0 + h + 2.1 + 0.3;
}
// (2)
pill(RX, ry, "成果 2  模型成績", 6.9);
{
  const y0 = ry + 1.2, th = 2.3, tw = 7.3, cpw = 6.4;
  const cfh = 4.6, cfw = wOf("f_conf_total.png", cfh);
  const cph = hOf("f_compare.png", cpw), blockH = Math.max(th + 0.15 + cph, cfh + 0.55) + 1.1;
  rect({ x: RX, y: y0 - 0.2, w: RW, h: blockH, fill: { color: CARD } });
  const hd = (t) => ({ text: t, options: { bold: true, fill: { color: INK }, color: "FFFFFF", align: "center", valign: "middle" } });
  const v = (t, o = {}) => ({ text: t, options: { align: "center", valign: "middle", ...o } });
  const RU = NUM.rule, MB = NUM.mine_from_baseline;
  const rows = [[hd("三年合計"), hd("macro-F1"), hd("找到率"), hd("命中率")],
    [v("隨機猜", { bold: true }), v("33.33%"), v(pc(NUM.random)), v(pc(NUM.random))],
    [v("只用規則", { bold: true }), v(pc(RU.macro_f1, 2)), v(pc(RU.both_rec)), v(pc(RU.both_prec))],
    [v("本系統", { bold: true }), v(pc(MB.macro_f1, 2)), v(pc(NUM.both_rec)), v(pc(NUM.both_prec))]];
  s.addTable(rows, { x: RX + 0.3, y: y0, w: tw, colW: [1.75, 1.85, 1.85, 1.85], rowH: th / 4, fontSize: 22, fontFace: FONT, color: INK,
    border: { type: "solid", pt: 1, color: LINE } });
  img("f_compare.png", RX + 0.3 + (tw - cpw) / 2, y0 + th + 0.15, cpw, cph, "找到率與命中率比較:隨機猜、只用規則、本系統");
  const cx = RX + 0.3 + tw + 0.4 + (RW - tw - 1.0 - cfw) / 2;
  img("f_conf_total.png", cx, y0, cfw, cfh, "三年合計混淆矩陣");
  T("三年合計;橘框(判反)= 0", { x: RX + tw + 0.6, y: y0 + cfh + 0.05, w: RW - tw - 0.8, h: 0.5, fontSize: 24, color: INK2, align: "center" });
  T([{ text: "成績主要來自規則;", options: { bold: true, color: INK } }, { text: `AE + OC-SVM 讓訊號少約兩成(${pc(NUM.signal_days_fewer)}),命中率持平。` }],
    { x: RX + 0.3, y: y0 + blockH - 0.95, w: RW - 0.6, h: 0.65, fontSize: 26, color: INK2, align: "center", valign: "middle" });
  ry = y0 + blockH + 0.1;
}
// (3)
pill(RX, ry, "成果 3  實驗結果", 6.9);
{
  const y0 = ry + 1.2, avail = H - M - y0 - 0.85;
  rect({ x: RX, y: y0 - 0.2, w: RW, h: avail + 1.05, fill: { color: CARD } });
  const half = (RW - 0.9) / 2;
  let h1 = Math.min(hOf("f_2454.png", half), avail), w1 = wOf("f_2454.png", h1);
  let h2 = Math.min(hOf("web_2454_year.png", half), avail), w2 = wOf("web_2454_year.png", h2);
  img("f_2454.png", RX + 0.3 + (half - w1) / 2, y0 + (avail - h1) / 2, w1, h1, "聯發科 2025 真實高低點與系統判斷");
  s.addShape(pres.shapes.RECTANGLE, { x: RX + 0.6 + half - 0.02 + (half - w2) / 2, y: y0 + (avail - h2) / 2 - 0.02, w: w2 + 0.04, h: h2 + 0.04, fill: { color: "FFFFFF" }, line: { color: LINE, width: 1.5 } });
  img("web_2454_year.png", RX + 0.6 + half + (half - w2) / 2, y0 + (avail - h2) / 2, w2, h2, "網頁:聯發科 2026 整年的判斷");
  T("聯發科 2025(表現較佳的個股)", { x: RX + 0.3, y: y0 + avail + 0.1, w: half, h: 0.55, fontSize: 24, color: INK2, align: "center" });
  T("網頁:聯發科 2026 即時判斷", { x: RX + 0.6 + half, y: y0 + avail + 0.1, w: half, h: 0.55, fontSize: 24, color: INK2, align: "center" });
}

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
