// 專題研究報告(逢甲大學資訊工程學系 大學部專題研究報告格式規範)
// 數字全部讀 data.json(由 figs.py 從 results/ 的 json 與 README 表格產生);不跑實驗。
// 用法: node build_report.js <data.json 與 fig/ 所在目錄> <輸出 docx>
const fs = require("fs");
const path = require("path");
const d = require("docx");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, TableOfContents, Footer, PageNumber, AlignmentType,
  NumberFormat, SectionType, Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, ImageRun,
  Tab, TabStopType, LineRuleType, VerticalAlign, TableLayoutType,
} = d;

const DIR = process.argv[2];
const OUT = process.argv[3];
const D = JSON.parse(fs.readFileSync(path.join(DIR, "data.json"), "utf8").replace(/`/g, ""));   // README 的程式碼標記不印
const FIGDIR = path.join(DIR, "fig");

// ───────── 版面與字型 ─────────
const F = { ascii: "Times New Roman", hAnsi: "Times New Roman", eastAsia: "標楷體", cs: "Times New Roman" };
const PAGE = { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1797, right: 1797, header: 850, footer: 992 } };
const TEXT_W = 11906 - 1797 * 2;            // 8312 DXA
const BODY_LINE = { line: 320, lineRule: LineRuleType.AT_LEAST };   // 最小行高 16 點

// ───────── 小工具 ─────────
const run = (t, o = {}) => new TextRun({ text: t, font: F, ...o });
const runs = (parts, base = {}) => (Array.isArray(parts) ? parts : [parts]).map((p) =>
  typeof p === "string" ? run(p, base) : run(p[0], { ...base, ...p[1] }));
// 內文段落:12 點、最小行高 16 點、左右對齊、首行縮排兩字
const P = (parts, o = {}) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED, spacing: { ...BODY_LINE, after: 60 }, indent: { firstLine: 480 }, ...o,
  children: runs(parts, o.run || {}),
});
// 條列:(1)… 懸掛縮排
const L = (label, parts, o = {}) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED, spacing: { ...BODY_LINE, after: 40 }, indent: { left: 480 + 480, hanging: 480 }, ...o,
  children: [run(label + " "), ...runs(parts)],
});
const H1 = (t, o = {}) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: !o.first, children: [run(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [run(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [run(t)] });
const EMPTY = (n = 1, size = 24) => Array.from({ length: n }, () => new Paragraph({ children: [run("", { size })] }));

// 圖:圖放上、圖名放下(置中)
const FIGS = [];
function FIG(file, widthIn, caption) {
  const p = path.join(FIGDIR, file);
  const buf = fs.readFileSync(p);
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);   // PNG IHDR
  const wpx = Math.round(widthIn * 96), hpx = Math.round(wpx * h / w);
  FIGS.push(caption);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60 },
      children: [new ImageRun({ type: "png", data: buf, transformation: { width: wpx, height: hpx },
        altText: { title: caption, description: caption, name: file } })] }),
    new Paragraph({ style: "FigCaption", children: [run(caption)] }),
  ];
}

// 表:表名放上(靠左),標題列在每頁頂端重複
const TABS = [];
function TAB(caption, header, rows, colW, o = {}) {
  TABS.push(caption);
  const size = o.size || 20;
  const sum = colW.reduce((a, b) => a + b, 0);
  const scale = TEXT_W / sum;
  const W = colW.map((x) => Math.floor(x * scale));
  W[W.length - 1] += TEXT_W - W.reduce((a, b) => a + b, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: "808080" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cell = (txt, i, isHead, rowOpt = {}) => new TableCell({
    width: { size: W[i], type: WidthType.DXA }, borders, verticalAlign: VerticalAlign.CENTER,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    shading: isHead ? { fill: "E7EBEE", type: ShadingType.CLEAR, color: "auto" } : (rowOpt.fill ? { fill: rowOpt.fill, type: ShadingType.CLEAR, color: "auto" } : undefined),
    children: String(txt).split("\n").map((ln) => new Paragraph({
      alignment: (o.align && o.align[i]) || (i === 0 && !isHead ? AlignmentType.LEFT : AlignmentType.CENTER),
      spacing: { line: 260, lineRule: LineRuleType.AT_LEAST },
      children: [run(ln, { size, bold: isHead || !!rowOpt.bold })] })),
  });
  const trows = [new TableRow({ tableHeader: true, cantSplit: true, children: header.map((h, i) => cell(h, i, true)) })];
  rows.forEach((r) => {
    const ro = r.opt || {};
    const cells = r.opt ? r.cells : r;
    trows.push(new TableRow({ cantSplit: true, children: cells.map((c, i) => cell(c, i, false, ro)) }));
  });
  const out = [
    new Paragraph({ style: "TabCaption", children: [run(caption)] }),
    new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: W, layout: TableLayoutType.FIXED, rows: trows }),
  ];
  if (o.note) out.push(new Paragraph({ spacing: { before: 60, after: 120, ...BODY_LINE }, children: runs(o.note, { size: 20 }) }));
  else out.push(new Paragraph({ spacing: { after: 120 }, children: [run("", { size: 12 })] }));
  return out;
}

// 公式:置中,編號靠右
const EQ = (parts, n) => new Paragraph({
  tabStops: [{ type: TabStopType.CENTER, position: Math.round(TEXT_W / 2) }, { type: TabStopType.RIGHT, position: TEXT_W }],
  spacing: { before: 100, after: 100, ...BODY_LINE },
  children: [new TextRun({ children: [new Tab()], font: F }), ...runs(parts), new TextRun({ children: [new Tab(), `(${n})`], font: F })],
});
const I = (t) => [t, { italics: true }];
const SUB = (t) => [t, { subScript: true, italics: true }];
const SUP = (t) => [t, { superScript: true }];

// ───────── 數字 ─────────
const Y = ["2024", "2025", "2026"];
const YL = { "2024": "2024", "2025": "2025", "2026": "2026(1–9 月)" };
const C = D.conf, B = D.bt, LR = D.lr, R = D.readme;
const pct = (v, n = 1) => `${Number(v).toFixed(n)}%`;
const sg = (v, n = 2) => `${v > 0 ? "+" : ""}${Number(v).toFixed(n)}%`;

const FUT = "(僅作上限參考,實務不可行)";

// README 表格:依欄名取欄
const col = (tab, name) => tab[0].indexOf(name);
function pick(tab, names, rowMap = (r) => r) {
  const idx = names.map((n) => { const k = col(tab, n); if (k < 0) throw new Error("no col " + n); return k; });
  return tab.slice(1).map((r) => rowMap(idx.map((k) => r[k]), r));
}
const futRow = (name) => /1a|真實標籤/.test(name);
const label = (name) => futRow(name) ? `${name.replace("(上限參考)", "")}†` : name;

// ══════════════════════════ 封面 ══════════════════════════
const coverLine = (t, size, o = {}) => new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 60, after: 0, line: 240, lineRule: LineRuleType.AUTO }, ...o,
  children: [run(t, { size: size * 2, bold: !!o.bold })] });
const cover = [
  ...EMPTY(2),
  coverLine("逢 甲 大 學", 32),
  coverLine("資 訊 工 程 學 系", 32),
  coverLine("專 題 研 究 報 告", 32),
  ...EMPTY(3),
  coverLine("以深度學習為基礎之", 24, { bold: true }),
  coverLine("自動化K線辨識系統", 24, { bold: true }),
  ...EMPTY(6),
  coverLine("指導教授：李俊宏 老師", 22),
  coverLine("學生：郭家齊 D1245765", 22),
  coverLine("\u3000\u3000\u3000呂偉湘 D1286314", 22),
  ...EMPTY(6),
  coverLine("中 華 民 國 一 百 一 十 五 年 十 一 月", 20),
];

// ══════════════════════════ 前言(羅馬數字頁碼) ══════════════════════════
const front = [];
front.push(H1("誌謝", { first: true }));
front.push(P("本專題得以完成,首先感謝指導教授李俊宏老師一路以來的指導。從研究題目的方向、標籤的定義,到建議以兩組模型的輸出再訓練第三個模型(Stacking),老師在每個關鍵的轉折點都給了明確的方向,也提醒我們以嚴謹的方式對待實驗結果。"));
front.push(P("也感謝系上提供的學習環境,以及在專題過程中給予意見與協助的同學與家人。專題中仍有許多不足之處,尚祈各位先進不吝指正。"));
front.push(new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: 480, ...BODY_LINE }, children: [run("郭家齊、呂偉湘 謹誌")] }));
front.push(new Paragraph({ alignment: AlignmentType.RIGHT, spacing: BODY_LINE, children: [run("中華民國一百一十五年十一月")] }));

const a200 = C.tw200.avg;
front.push(H1("摘要"));
front.push(P(`本研究以台股日K線辨識「11 天局部高低點」:以第 t 日為中心、前後各 5 個交易日的收盤價為視窗,t 日收盤價為視窗內最高者標為高點、最低者標為低點,其餘為非極值。模型在 t 日收盤後判斷,只使用 t−5 至 t 共 6 根 K 線的開、高、低、收與成交量,共 29 維特徵。`));
front.push(P(`本研究採用 Stacking 方法:第一層以高點、低點兩組線性自編碼器(29 → 16 維)與單類支持向量機(One-Class SVM)對每一天打分數,不經規則篩選;第二層以多類別邏輯迴歸組合兩個分數,輸出低點、非極值、高點三類機率。資料為 TW200 剔除低波動股後的 168 檔股票,實驗採 walk-forward 方式,每個測試年以之前 3 年訓練第一層、之前 1 年訓練第二層,測試期間為 2024 年至 2026 年 9 月。`));
front.push(P(`結果顯示,Stacking 的 macro-F1 在三個測試年依序為 ${Y.map((y) => C.tw200[y].stack.macro_f1.toFixed(2)).join("%、")}%;三年平均找到真低點 ${pct(a200.stack.rec_low)}、真高點 ${pct(a200.stack.rec_high)},判低點、判高點的命中率為 ${pct(a200.stack.prec_low)} 與 ${pct(a200.stack.prec_high)},約三成,高於隨機猜測的約 7%,且三年中從未把高點判成低點或把低點判成高點。以南電(8046)2024 年為例,16 個真低點中有 ${D.nd_cmp["低點"]["當天抓到"]} 個在當天被判為低點,17 個真高點中有 ${D.nd_cmp["高點"]["當天抓到"]} 個當天被判為高點,方向同樣從未判反;但判低點的 ${D.nd_cmp["低點"]["判"]} 天中只有 ${D.nd_cmp["低點"]["對"]} 天是真低點,多判的訊號不少。`));
front.push(P("據此,本研究將模型定位為「提醒可能的轉折點」的推薦與提醒系統:命中率約三成、多判的訊號也多,是否交易由使用者自行判斷。本研究並實作網頁系統,以 Stacking 的三類機率提供每日判斷、個股查詢與成績追蹤;系統以 49 項自動化測試驗證,其正式模型重現研究結果的 macro-F1 與混淆矩陣。"));
front.push(new Paragraph({ spacing: { before: 240, ...BODY_LINE }, indent: { left: 480 },
  children: [run("關鍵詞:K線型態、局部高低點、自編碼器、單類支持向量機、Stacking、推薦系統", { bold: true })] }));

front.push(new Paragraph({ style: "FrontTitle", pageBreakBefore: true, children: [run("目錄")] }));
front.push(new TableOfContents("目錄", { hyperlink: true, headingStyleRange: "1-2" }));
front.push(H1("圖目錄"));
front.push(new TableOfContents("圖目錄", { hyperlink: true, stylesWithLevels: [{ styleName: "FigCaption", level: 1 }] }));
front.push(H1("表目錄"));
front.push(new TableOfContents("表目錄", { hyperlink: true, stylesWithLevels: [{ styleName: "TabCaption", level: 1 }] }));

// ══════════════════════════ 本文(阿拉伯數字頁碼) ══════════════════════════
const body = [];
// ───── 第一章 ─────
body.push(H1("第一章 緒論", { first: true }));
body.push(H2("1.1 研究背景"));
body.push(P("技術分析以價格與成交量的歷史型態推估後續走勢,其中 K 線(蠟燭圖)以開、高、低、收四個價格呈現每日的多空變化,是台股投資人最常使用的工具之一。對短線交易而言,能否在轉折點附近進出場,往往比判斷長期方向更直接影響績效:若能在局部低點附近買進、在局部高點附近賣出,就能掌握一段波動。"));
body.push(P("然而轉折點必須等到之後的價格走出來才能確認。本研究以 11 天的收盤價視窗定義局部高點與局部低點:t 日收盤是前後 5 天的最高即為高點、最低即為低點。由定義可知,真高點的 t 日收盤必然也是 t−5 到 t 這 6 天的最高,但這只是必要條件;t 日收盤時無法知道之後 5 天的價格,因此需要從 t 日以前的 K 線型態判斷當天是否可能是轉折點。"));
body.push(H2("1.2 研究動機"));
body.push(P("局部高點與局部低點在所有交易日中各只占約 7%(見 4.1.2 節),大多數日子都是非極值,類別相當不平衡;而且在同一段漲跌中,轉折點與前後幾天的 K 線型態往往相似。如果能從 t 日以前的 K 線型態中學到「真轉折點長什麼樣子」,並以機率表示把握程度,就能依機率排序、提醒投資人注意可能的轉折點。"));
body.push(H2("1.3 研究目的"));
body.push(P("本研究的目的如下:"));
body.push(L("(1)", "以自編碼器與單類支持向量機分別學習真高點、真低點的 K 線型態,對每一天給出分數(Stacking 第一層)。"));
body.push(L("(2)", "以邏輯迴歸組合兩組分數(Stacking 第二層),輸出低點、非極值、高點三類機率。"));
body.push(L("(3)", "以 walk-forward 方式評估 Stacking 在 TW200 股票池的分類成績,並以南電(8046)為例說明模型在單一股票上找到的高點與低點。"));
body.push(L("(4)", "依研究結果實作網頁系統,讓使用者查詢每日判斷與歷史成績,作為決策輔助。"));
body.push(H2("1.4 研究範圍"));
body.push(L("(1)", "市場:台灣股票市場上市股票的日K線(還原權息價格)。"));
body.push(L("(2)", "股票池:TW200 清單中有資料的 216 檔,剔除 48 檔低波動股後的 168 檔(剔除規則見 4.1 節)。"));
body.push(L("(3)", "資料期間:2016 年 1 月至 2026 年 9 月 11 日的日K線。"));
body.push(L("(4)", "測試期間:2024 年、2025 年與 2026 年 1 月至 9 月 11 日,每一年都只用該年以前的資料訓練。"));
body.push(L("(5)", "本研究評估分類成績,不評估交易績效;模型輸出的訊號不應直接視為買賣建議。"));
body.push(H2("1.5 研究方法"));
body.push(P("本研究先依 11 天視窗的定義為每個交易日貼上高點、低點或非極值的標籤,再以 t 日以前 6 根 K 線的 29 維特徵建立 Stacking 三分類方法:第一層由自編碼器把特徵壓縮到 16 維、由單類支持向量機分別對高點與低點給出分數;第二層以邏輯迴歸組合兩個分數,輸出三類機率。評估採 walk-forward,以混淆矩陣、macro-F1、找到率(recall)與命中率(precision)衡量分類成績,再以南電(8046)2024 年為例觀察模型在單一股票上的判斷,最後將模型實作成網頁系統。"));
body.push(H2("1.6 研究流程"));
body.push(P("研究流程如圖 1.1 所示。"));
body.push(...FIG("fig1_1_flow.png", 4.6, "圖 1.1 研究流程"));
body.push(H2("1.7 章節結構"));
body.push(P("第一章說明研究背景、動機、目的、範圍與流程。第二章回顧本研究使用的文獻與方法,並說明本研究如何結合這些方法。第三章定義問題與標籤,介紹自編碼器、單類支持向量機與邏輯迴歸的理論基礎,以及 Stacking 的架構與訓練方式。第四章為實證分析,包含資料分析、TW200 的混淆矩陣與分類成績、實驗設計、南電個案與網頁系統評估。第五章為結論、研究限制、成果、貢獻、後續研究方向,以及專題過程中導入的 AI 工具。"));

// ───── 第二章 ─────
body.push(H1("第二章 相關文獻回顧"));
body.push(H2("2.1 局部高低點的定義"));
body.push(P("本研究以第 t 日收盤價 C_t 與前後各 5 日構成的 11 日視窗定義標籤:C_t 為視窗內最高者為高點、最低者為低點,與他日並列者也算,其餘為非極值(正式定義見 3.1 節)。由定義可知,真高點的 t 日收盤必然也是 t−5 至 t 這 6 天的最高(真低點同理);但這只是必要條件,t 日收盤時無法確認之後 5 天的走勢。本研究的模型不以此性質篩選日子,而是對每一天判斷。"));
body.push(H2("2.2 自編碼器"));
body.push(P("自編碼器(Autoencoder, AE)由編碼器與解碼器組成,以重建輸入為目標進行訓練,中間的低維表示可視為資料的壓縮特徵。Hinton 與 Salakhutdinov [1] 證明以神經網路學習的低維編碼比主成分分析更能保留資料結構。本研究採用一層線性編碼器(29 → 16 維),在線性情況下其效果近似主成分分析;訓練使用 Adam 最佳化器 [2]。"));
body.push(H2("2.3 單類支持向量機"));
body.push(P("單類支持向量機(One-Class SVM, OC-SVM)由 Schölkopf 等人 [3] 提出,只用單一類別的樣本學習一個能涵蓋大部分樣本的區域,常用於異常偵測。參數 ν 為訓練樣本落在區域外比例的上界,也是支持向量比例的下界;決策函數大於 0 表示落在區域內。本研究分別以真高點、真低點的樣本各訓練一個 OC-SVM,判斷每一天是否「像」過去的真轉折點,並以決策函數的值作為 Stacking 第一層的分數。"));
body.push(H2("2.4 堆疊泛化(Stacking)"));
body.push(P("Wolpert [4] 提出的堆疊泛化(Stacked Generalization)以第一層模型的輸出作為第二層模型的輸入,第二層模型必須用第一層沒看過的資料訓練,才能學到如何組合第一層的輸出。本研究依指導教授的建議,以高點、低點兩組 AE + OC-SVM 為第一層,以多類別邏輯迴歸為第二層,兩層使用不同年份的資料訓練。"));
body.push(H2("2.5 邏輯迴歸"));
body.push(P("邏輯迴歸由 Cox [5] 提出,以 logistic 函數將線性組合轉為機率;多類別情況下以 softmax 函數輸出各類機率 [6]。邏輯迴歸的係數可直接解讀,適合作為第二層模型,讓每一天的判斷可以手算驗證(見 3.3.4 節)。"));
body.push(H2("2.6 時間序列的驗證方式"));
body.push(P("時間序列資料前後相關,若隨機切分訓練與測試資料,模型可能看到測試期以後的資訊。Bergmeir 與 Benítez [7] 討論時間序列預測的交叉驗證方式,指出保留時間順序的評估較能反映實際使用情況。本研究採用 walk-forward 的方式,以「用過去一段期間訓練、在下一段期間測試,再整體往後移動」重複評估:每個測試年都只用之前 4 年的資料訓練,並剔除訓練期最後 5 個交易日,因為這些日子的標籤需要看到測試年的價格。"));
body.push(H2("2.7 分類評估指標"));
body.push(P("三分類中非極值占大多數,單看準確率會被多數類主導。Sokolova 與 Lapalme [8] 整理了多類別分類的評估指標,其中 macro-F1 為各類 F1 的平均,對每一類一視同仁。本研究以 macro-F1 為主要指標,並分別報告高點、低點的找到率(recall,真轉折點中被判出的比例)與命中率(precision,判出的訊號中真的是轉折點的比例)。"));
body.push(H2("2.8 實作工具"));
body.push(P("本研究以 scikit-learn [9] 實作標準化、單類支持向量機與邏輯迴歸,以 PyTorch [10] 實作自編碼器。"));
body.push(H2("2.9 本研究的做法"));
body.push(P("本研究在 2.1 節的標籤定義上,結合 2.2 至 2.8 節的方法,做法如下:(1)以高點、低點兩組 AE + OC-SVM 作為 Stacking 第一層,對每一天打分數,不經規則篩選;(2)以多類別邏輯迴歸作為第二層,輸出三類機率,並以真實數字示範其計算;(3)以 walk-forward 在 2024 至 2026 三個測試年評估 TW200 股票池的分類成績,並以南電為例觀察單一股票上的判斷;(4)將模型實作為每日更新的網頁系統,並以自動化測試確認系統輸出與研究結果一致。"));

// ───── 第三章 ─────
body.push(H1("第三章 論文主體"));
body.push(H2("3.1 研究方法:問題定義與標籤"));
body.push(P(["令第 t 個交易日的收盤價為 ", I("C"), SUB("t"), ",以 t 為中心、前後各 5 日構成 11 日視窗,t 為視窗的第 6 天:"]));
body.push(EQ([I("W"), SUB("t"), " = { ", I("C"), SUB("t−5"), ", ", I("C"), SUB("t−4"), ", …, ", I("C"), SUB("t+5"), " }"], 1));
body.push(P(["標籤 ", I("y"), SUB("t"), " 定義如下:"]));
body.push(EQ([I("y"), SUB("t"), " = 高點,若 ", I("C"), SUB("t"), " = max ", I("W"), SUB("t"), ";  ", I("y"), SUB("t"), " = 低點,若 ", I("C"), SUB("t"), " = min ", I("W"), SUB("t")], 2));
body.push(P("其餘日子為非極值。與他日並列最高(最低)者也標為高點(低點);視窗內收盤價全部相同時為非極值;資料頭尾不足 11 天的日子不納入。由 Eq. (2) 可知,標籤需要 t+1 至 t+5 的價格,只能用於訓練與評估;模型在 t 日收盤後判斷,只能使用 t 日以前的資料。圖 3.1 為三種標籤的示意。"));
body.push(...FIG("fig3_1_label.png", 5.6, "圖 3.1 高點、低點與非極值的標籤示意"));
body.push(P("由 Eq. (2) 可知,真高點的 C_t 必然也是 t−5 至 t 這 6 天的最高,真低點必然是最低;但這只是必要條件,滿足者不一定是真轉折點。本研究的模型不以此性質篩選日子,而是對每一天輸出三類機率。"));

body.push(H2("3.2 理論基礎"));
body.push(H3("3.2.1 自編碼器"));
body.push(P(["給定標準化後的特徵向量 ", I("x"), " ∈ R", SUP("29"), ",本研究使用的線性自編碼器為:"]));
body.push(EQ([I("z"), " = ", I("W"), SUB("e"), I("x"), " + ", I("b"), SUB("e"), ",  ", I("x̂"), " = ", I("W"), SUB("d"), I("z"), " + ", I("b"), SUB("d")], 3));
body.push(P(["其中 ", I("z"), " ∈ R", SUP("16"), " 為潛在表示。訓練目標為最小化平均平方重建誤差:"]));
body.push(EQ([I("L"), " = (1/", I("N"), ") Σ", SUB("i"), " ‖ ", I("x"), SUB("i"), " − ", I("x̂"), SUB("i"), " ‖", SUP("2")], 4));
body.push(P("訓練使用 Adam [2](學習率 0.001、權重衰減 0.00001)、餘弦退火學習率、批次大小 256,共 60 輪。"));
body.push(H3("3.2.2 單類支持向量機的決策函數"));
body.push(P(["OC-SVM [3] 在潛在空間中以核函數學習一個涵蓋訓練樣本的區域,其決策函數為:"]));
body.push(EQ([I("f"), "(", I("z"), ") = Σ", SUB("i"), " α", SUB("i"), " ", I("K"), "(", I("z"), SUB("i"), ", ", I("z"), ") − ρ"], 5));
body.push(EQ([I("K"), "(", I("z"), SUB("i"), ", ", I("z"), ") = exp(−γ ‖ ", I("z"), SUB("i"), " − ", I("z"), " ‖", SUP("2"), ")"], 6));
body.push(P("其中 α_i 為支持向量的係數,ρ 為偏移量,γ 為 RBF 核參數(本研究使用 scikit-learn 的 scale 設定)。f(z) > 0 表示 z 落在區域內。ν 設為 0.1。訓練時每個樣本另給一個相似度權重:在標準化後的特徵空間中,與該樣本歐氏距離不超過 3.0 的其他日子(A 期的全部日子,見 3.3.2 節)裡,同為該類的比例,使型態較具代表性的樣本有較大的影響。本研究以 f(z) 作為 Stacking 第一層的分數:分數越高,表示越像過去的真轉折點。"));
body.push(H3("3.2.3 邏輯迴歸與 softmax"));
body.push(P(["Stacking 的第二層為多類別邏輯迴歸 [5][6]。以 ", I("s"), " = (", I("s"), SUB("high"), ", ", I("s"), SUB("low"), ") 表示兩個 OC-SVM 標準化後的分數,對類別 k ∈ {低點, 非極值, 高點}:"]));
body.push(EQ([I("z"), SUB("k"), " = ", I("w"), SUB("k"), " · ", I("s"), " + ", I("b"), SUB("k")], 7));
body.push(EQ([I("P"), "(", I("y"), " = ", I("k"), " | ", I("s"), ") = exp(", I("z"), SUB("k"), ") / Σ", SUB("j"), " exp(", I("z"), SUB("j"), ")"], 8));
body.push(P("判斷為機率最大的類別,分數為該類的機率。由於非極值占大多數,訓練時以類別頻率的平方根倒數設定類別權重,並正規化為平均 1:"));
body.push(EQ([I("w"), SUB("c"), " = (1/√", I("p"), SUB("c"), ") / mean", SUB("c′"), "(1/√", I("p"), SUB("c′"), ")"], 9));
body.push(P("其中 p_c 為類別 c 在訓練資料中的比例。"));

body.push(H2("3.3 方法架構"));
body.push(H3("3.3.1 特徵"));
body.push(P(["特徵只使用 t−5 至 t 共 6 根 K 線。對 k = 0, 1, …, 5,取開、高、低價相對 t 日收盤的對數比,以及 k ≥ 1 時的收盤價對數比:"]));
body.push(EQ(["ln(", I("O"), SUB("t−k"), " / ", I("C"), SUB("t"), "), ln(", I("H"), SUB("t−k"), " / ", I("C"), SUB("t"), "), ln(", I("L"), SUB("t−k"), " / ", I("C"), SUB("t"), "), ln(", I("C"), SUB("t−k"), " / ", I("C"), SUB("t"), ")"], 10));
body.push(P(["成交量則除以「到 t 日為止的 10 日均量」後取對數:ln(", I("V"), SUB("t−k"), " / ", I("V̄"), SUB("t"), ")。合計開、高、低各 6 個(18 維)、收盤 5 個(t 日本身為 0,不計)與成交量 6 個,共 29 維。特徵先以訓練期的中位數補缺值、標準化,再截斷在 ±5 之間。"]));
body.push(H3("3.3.2 Stacking:兩層模型"));
body.push(P("Stacking 的架構如圖 3.2。每個測試年的訓練期(4 年)再切成兩段:前 3 年為 A 期,用來訓練第一層;最後 1 年為 B 期,用來訓練第二層;A 期最後 5 個交易日剔除,因為其標籤會用到 B 期的價格。步驟如下:"));
body.push(L("(1)", "標準化:以 A 期全部日子的特徵計算中位數(補缺值)與標準化參數,標準化後截斷在 ±5 之間;B 期與測試期使用同一組參數。"));
body.push(L("(2)", "第一層・高點組:只用 A 期的真高點訓練 29 → 16 的線性自編碼器,再以其 16 維編碼與相似度權重訓練 RBF 核、ν = 0.1 的 OC-SVM。低點組做法相同,只用 A 期的真低點。"));
body.push(L("(3)", "第一層打分數:對任何一天(B 期或測試期的每一天,不經規則篩選),以兩組模型的決策函數 Eq. (5) 得到兩個分數 s_high 與 s_low。"));
body.push(L("(4)", "第二層:以 B 期每一天的 (s_high, s_low) 標準化後為輸入、該天的真實標籤為答案,訓練多類別邏輯迴歸(L2 正則化、類別權重如 Eq. (9))。"));
body.push(L("(5)", "判斷與分數:測試期每一天依 Eq. (7)、Eq. (8) 算出三類機率,判斷為機率最大的類別,分數為該機率;網頁系統以此分數排序。"));
body.push(...FIG("fig3_3_stack_arch.png", 5.7, "圖 3.2 Stacking 兩層架構"));
body.push(H3("3.3.3 walk-forward 訓練期間"));
body.push(P("每個測試年都只用之前 4 年的資料訓練,種子固定為 42。各測試年的訓練期間如表 3.1 與圖 3.3。以 2025 年為例:第一層以 2021 至 2023 年(A 期)訓練,第二層以 2024 年(B 期)訓練,測試期間為 2025 年全年。"));
body.push(...TAB("表 3.1 walk-forward 訓練與測試期間", ["測試年", "第一層 A 期", "第二層 B 期", "測試期間"], [
  ["2024", "2020–2022", "2023", "2024 年全年"],
  ["2025", "2021–2023", "2024", "2025 年全年"],
  ["2026", "2022–2024", "2025", "2026 年 1 月至 9 月 11 日"],
], [1.2, 1.6, 1.6, 2.4], { size: 22, note: "註:A 期與 B 期的最後 5 個交易日都剔除,因為其標籤需要看到下一段的價格。" }));
body.push(...FIG("fig3_4_walkforward.png", 5.6, "圖 3.3 walk-forward 時間軸"));

body.push(H3("3.3.4 邏輯迴歸的計算實例"));
const m = LR.model;
body.push(P(`以下以 TW200 股票池、測試 2025 年的 Stacking 模型為例(第一層 A 為 ${m.A_years[0]}–${m.A_years[1]} 年,第二層 B 為 ${m.B_years[0]} 年),說明第二層邏輯迴歸如何算出每一天的機率。B 期共 ${m.B_rows.toLocaleString()} 筆(低點 ${m.B_class_counts["低點"].toLocaleString()}、非極值 ${m.B_class_counts["非極值"].toLocaleString()}、高點 ${m.B_class_counts["高點"].toLocaleString()}),依 Eq. (9) 得到類別權重低點 ${m.class_weight["低點"]}、非極值 ${m.class_weight["非極值"]}、高點 ${m.class_weight["高點"]}。標準化參數為 s_high 平均 ${m.scaler.s_high.mean}、標準差 ${m.scaler.s_high.std};s_low 平均 ${m.scaler.s_low.mean}、標準差 ${m.scaler.s_low.std}。訓練後的係數如表 3.2,這個模型 2025 年全部 168 檔的 macro-F1 為 ${m.test_macro_f1_pct}%。`));
const K3 = ["低點", "非極值", "高點"];
body.push(...TAB("表 3.2 Stacking 第二層邏輯迴歸係數(TW200,測試 2025)", ["類別", "係數 s_high", "係數 s_low", "截距"],
  K3.map((k) => [k, m.coef[k].s_high.toFixed(4), m.coef[k].s_low.toFixed(4), m.intercept[k].toFixed(4)]), [1.4, 1.6, 1.6, 1.6], { size: 22 }));
const cs = LR.cases;
const ca = cs.a;
body.push(P(`以南電(8046)${ca["日期"]} 為例(收盤 ${ca["收盤"]}):兩個 OC-SVM 的分數為 s_high = ${ca.s_high}、s_low = ${ca.s_low},標準化後為 (${ca.s_high} − (${m.scaler.s_high.mean})) / ${m.scaler.s_high.std} = ${ca["標準化 s_high"].toFixed(4)} 與 (${ca.s_low} − (${m.scaler.s_low.mean})) / ${m.scaler.s_low.std} = ${ca["標準化 s_low"].toFixed(4)}。代入 Eq. (7):`));
body.push(P(`z(低點) = ${m.coef["低點"].s_high} × ${ca["標準化 s_high"].toFixed(4)} + ${m.coef["低點"].s_low} × ${ca["標準化 s_low"].toFixed(4)} + (${m.intercept["低點"]}) = ${ca.z["低點"]}`, { indent: { left: 480 } }));
body.push(P(`同理 z(非極值) = ${ca.z["非極值"]}、z(高點) = ${ca.z["高點"]}。代入 Eq. (8) 的 softmax,得到機率低點 ${ca["機率"]["低點"]}、非極值 ${ca["機率"]["非極值"]}、高點 ${ca["機率"]["高點"]},因此判為低點,分數 ${ca["分數"]};這一天的真實標籤為${ca["真實"]}。手算的機率與 scikit-learn predict_proba 的最大誤差為 ${LR["手算 vs predict_proba 最大誤差(全年每天)"]}。表 3.3 列出南電 2025 年四種情況的例子(每組取判斷那一類的機率最接近該組中位數的一天)。`));
body.push(...TAB("表 3.3 南電 2025 年的邏輯迴歸計算例子", ["例子", "日期", "s_high / s_low", "z(低 / 非 / 高)", "機率(低 / 非 / 高)", "判斷", "真實"],
  ["a", "b", "c", "d"].map((k) => {
    const c = cs[k];
    return [`(${k}) ${c["說明"]}`, c["日期"], `${c.s_high}\n${c.s_low}`, `${c.z["低點"]} / ${c.z["非極值"]} / ${c.z["高點"]}`,
      `${c["機率"]["低點"]} / ${c["機率"]["非極值"]} / ${c["機率"]["高點"]}`, c["判斷"], c["真實"]];
  }), [2.0, 1.25, 1.25, 1.8, 1.8, 0.75, 0.75], { size: 18 }));
body.push(P("例子 (d) 與 (a) 相隔一天,兩天的分數幾乎相同,都被判為低點,但只有 (a) 是真低點。這說明模型能指出「低點附近」,卻難以分辨是哪一天;第四章的南電個案也可看到同樣的情形。"));

// ───── 第四章 ─────
body.push(H1("第四章 實證分析"));
body.push(H2("4.1 資料分析"));
body.push(H3("4.1.1 資料來源與股票池"));
body.push(P(`日K線取自 Yahoo Finance(透過 yfinance 套件 [11])的還原權息價格,期間為 2016 年 1 月 1 日至 2026 年 9 月 11 日。股票池使用 TW200 清單,共 222 檔,有資料者 216 檔。部分股票的每日漲跌幅很小,標籤多半只是小起伏,因此本研究剔除低波動股:計算 2020 年 1 月以後每日收盤漲跌幅絕對值的中位數,低於 0.725% 者剔除,共剔除 ${B.tw200.excluded_n} 檔,剩 ${B.tw200.pool_n} 檔(表 4.1)。`));
body.push(...TAB("表 4.1 股票池", ["股票池", "原始檔數", "有資料", "剔除低波動", "使用檔數"], [
  ["TW200", "222", "216", String(B.tw200.excluded_n), String(B.tw200.pool_n)],
], [2.2, 1.2, 1.2, 1.4, 1.2], { size: 22 }));
body.push(H3("4.1.2 標籤比例"));
body.push(P("表 4.2 為各測試年的標籤分布(個數取自混淆矩陣的列加總)。高點、低點各約占 7%,非極值約占 86%,類別相當不平衡,因此以 macro-F1 為主要指標,並以「隨機猜的命中率約等於該類比例」作為基準。"));
const labRows = Y.map((y) => {
  const l = C.tw200[y].labels;
  return [YL[y], l.n.toLocaleString(), `${l.low.toLocaleString()}(${(l.low / l.n * 100).toFixed(2)}%)`,
    `${l.flat.toLocaleString()}(${(l.flat / l.n * 100).toFixed(2)}%)`, `${l.high.toLocaleString()}(${(l.high / l.n * 100).toFixed(2)}%)`];
});
body.push(...TAB("表 4.2 TW200 測試期的標籤分布(股票日數)", ["測試年", "總數", "低點", "非極值", "高點"], labRows, [2.0, 1.3, 1.7, 1.9, 1.7], { size: 20 }));

body.push(H2("4.2 統計分析"));
body.push(H3("4.2.1 混淆矩陣"));
body.push(P("圖 4.1 為 Stacking 在 TW200 股票池 2024 至 2026 年的混淆矩陣;列為真實標籤、欄為判斷,每格為個數與該列的比例。每個矩陣上方標示該年第一層(A)與第二層(B)的訓練期間與 macro-F1,下方為該年的找到率與命中率。表 4.3 整理逐年的分類成績。"));
body.push(...FIG("fig4_2_conf_tw200.png", 5.75, "圖 4.1 TW200 Stacking 混淆矩陣(2024–2026)"));
const mRows = Y.map((y) => {
  const v = C.tw200[y].stack;
  return [YL[y], v.macro_f1.toFixed(2), pct(v.rec_low), pct(v.rec_high), pct(v.prec_low), pct(v.prec_high), String(C.tw200[y].reversed.stack)];
});
mRows.push({ opt: { bold: true }, cells: ["三年平均", a200.stack.macro_f1.toFixed(2), pct(a200.stack.rec_low), pct(a200.stack.rec_high), pct(a200.stack.prec_low), pct(a200.stack.prec_high), String(Y.reduce((t, y) => t + C.tw200[y].reversed.stack, 0))] });
body.push(...TAB("表 4.3 TW200 Stacking 逐年分類成績", ["測試年", "macro-F1(%)", "找到率 低點", "找到率 高點", "命中率 低點", "命中率 高點", "高低點判反"], mRows,
  [1.6, 1.1, 1.0, 1.0, 1.0, 1.0, 0.9], { size: 20, note: "註:高低點判反 = 真低點判成高點與真高點判成低點的個數合計;三年平均由逐年數字計算。" }));
body.push(P(`由圖 4.1 與表 4.3 可得到三點觀察:第一,三個測試年中高低點判反的個數都是 0,模型從未把低點判成高點或把高點判成低點,錯誤都發生在轉折點與非極值之間。第二,Stacking 找到約一半的真低點與約四成的真高點(三年平均 ${pct(a200.stack.rec_low)} 與 ${pct(a200.stack.rec_high)})。第三,判低點、判高點的命中率約為三成(三年平均 ${pct(a200.stack.prec_low)} 與 ${pct(a200.stack.prec_high)}),也就是每 10 個訊號中約有 3 個是真轉折點;macro-F1 在三個測試年之間相當穩定(${Y.map((y) => C.tw200[y].stack.macro_f1.toFixed(2)).join("、")})。`));
body.push(H3("4.2.2 隨機基準"));
body.push(P(`若隨機挑一個股票日,它剛好是真低點(真高點)的機率等於該類的比例。以 TW200 為例,${D.random_line.replace("隨機猜的命中率基準(真低點 / 真高點占全部股票日):", "真低點 / 真高點占全部股票日的比例為:")}因此隨機猜的命中率約為 7%,Stacking 約三成的命中率明顯高於隨機。`));

body.push(H2("4.3 實驗設計"));
body.push(H3("4.3.1 walk-forward 切分"));
body.push(P(`實驗以 2024、2025 與 2026 年(1 月至 9 月 11 日)為三個測試年,每個測試年都只用之前 4 年的資料訓練:前 3 年訓練第一層、最後 1 年訓練第二層(表 3.1、圖 3.3),種子固定為 42。測試樣本為 ${B.tw200.pool_n} 檔股票在測試年中有標籤的全部交易日(表 4.2),所有樣本都以同一個模型、同一套規則判斷,不另外挑選。模型與股票池在三個測試年之間保持不變,只依時間往後移動訓練期間。`));
body.push(H3("4.3.2 評估指標"));
body.push(P(["對類別 k ∈ {低點, 高點},令 ", I("TP"), SUB("k"), " 為真實為 k 且判為 k 的個數、", I("FP"), SUB("k"), " 為判為 k 但真實不是 k 的個數、", I("FN"), SUB("k"), " 為真實為 k 但沒有判為 k 的個數。命中率(precision)與找到率(recall)為:"]));
body.push(EQ([I("P"), SUB("k"), " = ", I("TP"), SUB("k"), " / (", I("TP"), SUB("k"), " + ", I("FP"), SUB("k"), ")"], 11));
body.push(EQ([I("R"), SUB("k"), " = ", I("TP"), SUB("k"), " / (", I("TP"), SUB("k"), " + ", I("FN"), SUB("k"), ")"], 12));
body.push(P("各類的 F1 為命中率與找到率的調和平均,macro-F1 為三類(低點、非極值、高點)F1 的平均:"));
body.push(EQ([I("F1"), SUB("k"), " = 2", I("P"), SUB("k"), I("R"), SUB("k"), " / (", I("P"), SUB("k"), " + ", I("R"), SUB("k"), "),  macro-F1 = (1/3) Σ", SUB("k"), " ", I("F1"), SUB("k")], 13));
body.push(P("由 Eq. (11) 可知,命中率回答「判出來的訊號有幾成是真的」;由 Eq. (12) 可知,找到率回答「真的轉折點有幾成被判出來」。此外,本研究另外計算「高低點判反」的個數,即混淆矩陣中真低點判成高點與真高點判成低點兩格的合計。在 4.4 節的個案中,另以「前後 2 天內抓到」表示真轉折點前後 2 個交易日內(同一檔)有同類判斷的情形。"));

body.push(H2("4.4 模擬分析"));
body.push(H3("4.4.1 個案:南電 2024 年"));
const nd = D.nandian.tw200, ndS = nd.stack, nc = D.nd_cmp;
body.push(P(`為具體說明模型在單一股票上找到高點與低點的情形,本研究以 TW200 股票池中的南電(8046)為例,使用測試 2024 年的 TW200 模型(第一層 2020–2022 年、第二層 2023 年)。南電 2024 年共 ${nd.n_days} 個交易日,真高點 ${nc["高點"]["真"]} 個、真低點 ${nc["低點"]["真"]} 個,全年大致下跌。圖 4.2 上段為收盤價與真實標籤,下段為 Stacking 的每日判斷:朝下的三角形為判高點、朝上的為判低點,實心為判對、空心為判錯。`));
body.push(...FIG("fig4_3_nandian.png", 5.75, "圖 4.2 南電 2024 年:真實高低點與 Stacking 的判斷(TW200 模型)"));
body.push(H3("4.4.2 南電的混淆矩陣"));
body.push(P(`圖 4.3 為南電 2024 年 Stacking 的混淆矩陣(macro-F1 ${ndS.macro_f1.toFixed(2)}%),表 4.4 整理高點與低點的判斷結果。`));
body.push(...FIG("fig4_4_nandian_conf.png", 3.4, "圖 4.3 南電 2024 年 Stacking 混淆矩陣(TW200 模型)"));
const ndRow = (k) => { const v = nc[k]; return [k, String(v["真"]), String(v["判"]), `${v["對"]} / ${v["錯"]}`, `${v["命中率"].toFixed(1)}%`, String(v["當天抓到"]), String(v["±2 天抓到"])]; };
body.push(...TAB("表 4.4 南電 2024 年:真轉折點與 Stacking 的判斷", ["類別", "真實個數", "判斷天數", "判對 / 判錯", "命中率", "當天抓到", "前後 2 天內抓到"],
  [ndRow("低點"), ndRow("高點")], [1.0, 1.0, 1.0, 1.2, 1.0, 1.0, 1.4], { size: 20, note: "註:當天抓到 = 真轉折點當天被判為同一類;前後 2 天內抓到 = 真轉折點前後 2 個交易日內有同類判斷。" }));
body.push(P(`由圖 4.2、圖 4.3 與表 4.4 可見:第一,模型找得到低點:${nc["低點"]["真"]} 個真低點中有 ${nc["低點"]["當天抓到"]} 個在當天就被判為低點(找到率 ${ndS.rec["低點"]}%)。第二,也找到部分高點:${nc["高點"]["真"]} 個真高點中有 ${nc["高點"]["當天抓到"]} 個在當天被判為高點(找到率 ${ndS.rec["高點"]}%),若放寬到前後 2 天內則有 ${nc["高點"]["±2 天抓到"]} 個。第三,方向從未判反:真低點沒有被判成高點、真高點也沒有被判成低點(圖 4.3 的兩個角落都是 0)。第四,多判的訊號不少:判低點 ${nc["低點"]["判"]} 天中只有 ${nc["低點"]["對"]} 天是真低點,其餘 ${nc["低點"]["錯"]} 天是非極值,多半集中在真低點前後的連續下跌日;判高點 ${nc["高點"]["判"]} 天中有 ${nc["高點"]["對"]} 天正確。因此模型適合提醒「這附近可能是低點 / 高點」,實際是哪一天仍需使用者自行判斷。`));

body.push(H2("4.5 系統評估"));
body.push(H3("4.5.1 系統架構"));
body.push(P("依前述結果,模型的命中率約三成、多判的訊號也多,適合用來提醒「哪裡可能是高點、低點」,是否交易由使用者自行判斷。因此本研究將模型實作為本機執行的網頁系統(展示版),每天收盤後產生判斷,並提供個股查詢與成績追蹤。系統的運作方式如表 4.5。"));
body.push(...TAB("表 4.5 網頁系統的運作方式", ["項目", "做法"], [
  ["股票池", "設定值,預設 TW100 剔除低波動股;可換成 TW200 等股票池"],
  ["模型", "本系統以 Stacking 的三類機率為主要輸出;與研究 walk-forward 相同,判斷 Y 年時第一層以 Y−4 至 Y−2 年、第二層以 Y−1 年訓練,種子 42"],
  ["重訓", "每年 1 月第 6 個交易日之後第一次執行批次時自動訓練新的一年"],
  ["資料", "yfinance 還原價,增量下載並快取;還原價變動時重抓整段"],
  ["每日判斷", "股票池內、池外、低波動股都計算;推薦清單只列池內股票,依機率(分數)排序"],
  ["存檔", "當天判斷與 5 天後的答案分別存檔,寫入後不再修改"],
  ["對答案", "t+5 收盤後以研究的同一個標籤規則判斷,並記錄 t+1 開盤至 t+5 收盤的報酬(扣成本 0.585%)"],
  ["前端", "靜態網頁,讀取每次批次產生的資料檔;支援淺色、深色主題與手機版面"],
], [1.3, 6.0], { size: 20, align: [AlignmentType.CENTER, AlignmentType.LEFT] }));
body.push(H3("4.5.2 系統功能"));
body.push(P("網頁共有五個頁面:今日判斷(判低點、判高點依分數排序,並依「已幾天沒破底 / 沒創高」分組)、個股查詢(三類機率與判斷、K 線與過去訊號的對錯)、成績追蹤(每天的判斷 5 天後對答案、命中率)、研究發現(研究結論),以及方法與說明(標籤定義、方法、免責聲明)。圖 4.4 至圖 4.6 為主要頁面的節錄(資料至 2026 年 9 月 10 日),其餘截圖見附錄二。"));
body.push(...FIG("fig4_5_web_today.png", 5.6, "圖 4.4 網頁系統:今日判斷(節錄)"));
body.push(P("個股查詢頁列出該股 Stacking 的三類機率,以及最近 60 個交易日的 K 線與 Stacking 過去判斷的對錯(圖 4.5)。以池內股票 8454 富邦媒為例,2026 年 9 月 10 日收盤後的機率為高點 0.00、低點 0.57、非極值 0.43,判為低點,信心等級為低。"));
body.push(...FIG("fig4_6_web_stock.png", 5.6, "圖 4.5 網頁系統:個股查詢(8454 富邦媒,節錄)"));
body.push(P("成績追蹤頁在每天的判斷 5 個交易日後對答案(圖 4.6)。網頁系統回放期(TW100 池內,資料 2026 年 1 月 2 日至 9 月 10 日)Stacking 的判低點整體命中率為 29.8%(435 / 1461);依信心等級分,高、中、低分別為 33.1%、30.9% 與 25.2%;每天判低點前 3 檔的近 60 天命中率為 26.1%。這些數字與研究結果的約三成相近,高於隨機猜測的約 7%。"));
body.push(...FIG("fig4_7_web_track.png", 5.6, "圖 4.6 網頁系統:成績追蹤(節錄)"));
body.push(H3("4.5.3 系統測試與一致性"));
body.push(P("系統以 49 項自動化測試驗證,涵蓋:資料更新(增量下載、還原價變動重抓、網路失敗、休市)、判斷存檔不覆蓋、5 天後才對答案、池內 / 池外 / 低波動 / 不支援股票的判定、判斷檔格式、股票池設定、命中率統計、連續天數與沒破底天數不偷看未來、研究發現頁的數字與結果檔一致、特徵不偷看未來、每日批次與回放結果相同,以及正式模型重現研究結果。"));
body.push(P("其中「正式模型重現研究結果」的測試以系統的正式模型重新判斷 2026 年 TW100 股票池的 11,826 筆測試資料,確認 Stacking 的 macro-F1 與混淆矩陣和研究結果檔完全相同(macro-F1 差距小於 10⁻¹²)。因此網頁上的每日判斷與研究評估的是同一套模型。"));

// ───── 第五章 ─────
body.push(H1("第五章 結論與建議"));
body.push(H2("5.1 結論"));
body.push(L("(1)", `模型抓得到大方向:在 TW200 股票池的三個測試年中,Stacking 都沒有把高點判成低點或把低點判成高點;三年平均找到真低點 ${pct(a200.stack.rec_low)}、真高點 ${pct(a200.stack.rec_high)}。`));
body.push(L("(2)", `命中率約三成:判低點、判高點的命中率三年平均為 ${pct(a200.stack.prec_low)} 與 ${pct(a200.stack.prec_high)},高於隨機猜測的約 7%;macro-F1 三年依序為 ${Y.map((y) => C.tw200[y].stack.macro_f1.toFixed(2)).join("、")},相當穩定。`));
body.push(L("(3)", `南電 2024 年的個案顯示,模型找得到高點與低點:${D.nd_cmp["低點"]["真"]} 個真低點中有 ${D.nd_cmp["低點"]["當天抓到"]} 個、${D.nd_cmp["高點"]["真"]} 個真高點中有 ${D.nd_cmp["高點"]["當天抓到"]} 個在當天被判出,方向從未判反;但判低點的 ${D.nd_cmp["低點"]["判"]} 天中有 ${D.nd_cmp["低點"]["錯"]} 天是非極值,多判的訊號集中在真低點前後。`));
body.push(L("(4)", "由於命中率約三成、多判的訊號也多,本研究將模型定位為推薦與提醒系統:提醒使用者哪裡可能是高點或低點,是否交易由使用者自行判斷。"));
body.push(L("(5)", "網頁系統以 Stacking 的三類機率為主要輸出,正式模型重現研究結果,可作為每日提醒與成績追蹤的工具。"));
body.push(H2("5.2 研究限制"));
body.push(L("(1)", "特徵只使用 6 根 K 線的價格與成交量,未納入技術指標、大盤與籌碼等資訊。"));
body.push(L("(2)", "低波動股的剔除以 2020 年 1 月至 2026 年 9 月的每日漲跌幅計算,涵蓋了測試期間;TW200 也使用目前的清單,未處理成分股變動,可能有存活者偏誤。"));
body.push(L("(3)", "主要結果只使用種子 42;個案只以南電一檔股票說明,其他股票的情形可能不同。"));
body.push(L("(4)", "本研究評估分類成績,未評估交易績效;模型的訊號未考慮交易成本與進出場規則,不能直接視為買賣建議。"));
body.push(L("(5)", "標籤需要 t+5 的價格,網頁系統的成績追蹤也必須等 5 個交易日後才能對答案。"));
body.push(H2("5.3 研究成果"));
body.push(L("(1)", "完成 Stacking 三分類方法(第一層兩組 AE + OC-SVM、第二層邏輯迴歸),對每一天輸出低點、非極值、高點三類機率與分數。"));
body.push(L("(2)", "完成 TW200 股票池三個測試年的 walk-forward 評估,包括混淆矩陣、找到率、命中率與南電個案,所有數字都保存在結果檔中、可重現。"));
body.push(L("(3)", "完成網頁系統(展示版):每日批次、判斷存檔、5 天後對答案、今日判斷、個股查詢、成績追蹤、研究發現與方法說明頁,並以 49 項自動化測試驗證。"));
body.push(H2("5.4 研究貢獻"));
body.push(L("(1)", "以實證說明 Stacking 能找到約一半的真低點與約四成的真高點,且高低點方向從未判反。"));
body.push(L("(2)", "誠實呈現命中率約三成、多判訊號多的限制,並據此說明模型適合作為提醒而非自動交易。"));
body.push(L("(3)", "提供可解讀的範例:以真實數字逐步計算邏輯迴歸的機率,並與套件輸出核對誤差為 0。"));
body.push(L("(4)", "將研究模型與網頁系統以自動化測試連結,確保系統輸出與研究結果一致。"));
body.push(H2("5.5 後續研究方向"));
body.push(L("(1)", "加入能區分「低點當天」與「低點前後」的資訊,例如當天以後的盤中資料或分時成交量,減少多判的訊號。"));
body.push(L("(2)", "在考慮交易成本與進出場規則的前提下,評估訊號用於交易的可行性,並增加多個亂數種子與更多個股的結果。"));
body.push(L("(3)", "使用歷史成分股清單與不含測試期的低波動判定,降低存活者偏誤與資訊洩漏。"));
body.push(L("(4)", "網頁系統持續累積實際上線後的判斷與答案,以真實時間序列評估長期表現。"));
body.push(H2("5.6 專題過程導入的 AI 工具"));
body.push(P("本專題使用 Claude Code(Anthropic)[12] 作為輔助工具,協助以下工作:"));
body.push(L("(1)", "程式撰寫:標籤、特徵、Stacking 模型、walk-forward 評估、網頁系統與其自動化測試的程式碼。"));
body.push(L("(2)", "實驗執行與結果核對:依指示執行實驗、把結果寫入結果檔,並核對不同程式之間的數字一致(例如網頁正式模型重現研究結果)。"));
body.push(L("(3)", "圖表與報告整理:繪製混淆矩陣與個案圖,整理簡報與本報告的初稿。"));
body.push(L("(4)", "多個 session 分工:以一個監督用的 session 接收與轉達指令,再由不同的 session 分別負責研究分支、網頁系統分支與報告分支,彼此以訊息交接。"));
body.push(P("人工決策與檢查的部分包括:研究方向與題目的決定;標籤定義、以兩組 AE + OC-SVM 加邏輯迴歸的 Stacking 架構等方法上的選擇;股票池的選擇與剔除低波動股;實驗範圍與個案的選擇;以及報告呈現方式與最終內容的決定。AI 工具產生的程式與數字,均經人工閱讀結果、對照結果檔與圖表後才採用。"));

// ───── 參考文獻 ─────
body.push(H1("參考文獻"));
const REF = (n, parts) => new Paragraph({ alignment: AlignmentType.LEFT, spacing: { ...BODY_LINE, after: 80 }, indent: { left: 600, hanging: 600 },
  children: [run(`[${n}]`), new TextRun({ children: [new Tab()], font: F }), ...runs(parts)], tabStops: [{ type: TabStopType.LEFT, position: 600 }] });
const it = (t) => [t, { italics: true }];
body.push(REF(1, ["G. E. Hinton and R. R. Salakhutdinov, \"Reducing the dimensionality of data with neural networks,\" ", it("Science"), ", vol. 313, no. 5786, pp. 504–507, Jul. 2006."]));
body.push(REF(2, ["D. P. Kingma and J. Ba, \"Adam: A method for stochastic optimization,\" ", it("Proceedings of the 3rd International Conference on Learning Representations (ICLR)"), ", San Diego, CA, USA, May 2015."]));
body.push(REF(3, ["B. Schölkopf, J. C. Platt, J. Shawe-Taylor, A. J. Smola, and R. C. Williamson, \"Estimating the support of a high-dimensional distribution,\" ", it("Neural Computation"), ", vol. 13, no. 7, pp. 1443–1471, Jul. 2001."]));
body.push(REF(4, ["D. H. Wolpert, \"Stacked generalization,\" ", it("Neural Networks"), ", vol. 5, no. 2, pp. 241–259, 1992."]));
body.push(REF(5, ["D. R. Cox, \"The regression analysis of binary sequences,\" ", it("Journal of the Royal Statistical Society: Series B (Methodological)"), ", vol. 20, no. 2, pp. 215–242, 1958."]));
body.push(REF(6, ["C. M. Bishop, ", it("Pattern Recognition and Machine Learning"), ". New York: Springer, 2006."]));
body.push(REF(7, ["C. Bergmeir and J. M. Benítez, \"On the use of cross-validation for time series predictor evaluation,\" ", it("Information Sciences"), ", vol. 191, pp. 192–213, May 2012."]));
body.push(REF(8, ["M. Sokolova and G. Lapalme, \"A systematic analysis of performance measures for classification tasks,\" ", it("Information Processing & Management"), ", vol. 45, no. 4, pp. 427–437, Jul. 2009."]));
body.push(REF(9, ["F. Pedregosa et al., \"Scikit-learn: Machine learning in Python,\" ", it("Journal of Machine Learning Research"), ", vol. 12, pp. 2825–2830, 2011."]));
body.push(REF(10, ["A. Paszke et al., \"PyTorch: An imperative style, high-performance deep learning library,\" ", it("Advances in Neural Information Processing Systems 32 (NeurIPS 2019)"), ", pp. 8024–8035, Dec. 2019."]));
body.push(REF(11, ["R. Aroussi, yfinance: Download market data from Yahoo! Finance's API. https://github.com/ranaroussi/yfinance(存取日期:2026 年 11 月 9 日)"]));
body.push(REF(12, ["Anthropic, Claude Code 說明文件. https://code.claude.com/docs(存取日期:2026 年 11 月 9 日)"]));

// ───── 附錄 ─────
body.push(H1("附錄"));
body.push(H2("附錄一 程式模組與執行指令"));
body.push(P("研究程式位於分支 claude/kline-peak-predict-tool 的 method_kline_peak/,網頁系統位於分支 claude/kline-peak-web-app 的 method_kline_peak/web/。以下指令皆在專題根目錄執行;未列出的參數使用預設值。"));
body.push(...TAB("附表 1 研究程式模組", ["模組", "用途"], [
  ["peak_labels.py、paper_aeocsvm.py", "11 日視窗標籤與評估指標"],
  ["mainline.py", "資料載入、特徵、股票池與低波動股剔除、自編碼器訓練(Stacking 共用)"],
  ["ae_ocsvm.py", "相似度權重與 AE + OC-SVM 的訓練"],
  ["stacking.py", "Stacking:第一層兩組 AE + OC-SVM、第二層邏輯迴歸"],
  ["walkforward.py", "逐年 walk-forward 的訓練與訊號來源"],
  ["report/confusion_2024_2026.py", "2024–2026 混淆矩陣圖與數字"],
  ["report/stock_outputs.py、report/confusion_stock.py", "單一股票的每日判斷圖與混淆矩陣"],
  ["report/compare_postproc.py", "南電 2024 每日判斷圖(本報告取其真實標籤與原始判斷兩段)"],
  ["report/lr_example.py", "邏輯迴歸計算實例"],
  ["web/run.py", "網頁系統:每日批次、回放、重訓、產生網頁資料、開啟網頁"],
], [2.8, 4.5], { size: 18, align: [AlignmentType.LEFT, AlignmentType.LEFT] }));
body.push(...TAB("附表 2 主要執行指令", ["用途", "指令"], [
  ["Stacking 實驗", "python method_kline_peak/stacking.py"],
  ["南電每日判斷圖", "python method_kline_peak/report/compare_postproc.py"],
  ["邏輯迴歸實例", "python method_kline_peak/report/lr_example.py"],
  ["網頁:第一次回放", "python method_kline_peak/web/run.py replay --start 2026-01-01"],
  ["網頁:每日批次並開網頁", "python method_kline_peak/web/run.py start"],
  ["網頁系統測試", "python -m pytest method_kline_peak/web/tests"],
], [1.9, 5.4], { size: 18, align: [AlignmentType.LEFT, AlignmentType.LEFT] }));
body.push(H2("附錄二 網頁系統各頁截圖"));
body.push(P("以下截圖為網頁系統展示版的真實畫面(資料至 2026 年 9 月 10 日),預設方法為 Stacking;各圖只取部分區塊。"));
body.push(...FIG("appB_today_mobile.png", 2.6, "圖 A.1 今日判斷(手機,節錄)"));
body.push(...FIG("appB_search.png", 5.4, "圖 A.2 個股查詢:代號自動完成"));
body.push(...FIG("appB_stock_outpool.png", 5.4, "圖 A.3 個股查詢:池外股票(2618 長榮航)的標示"));
body.push(...FIG("appB_stock_lowvol.png", 5.4, "圖 A.4 個股查詢:低波動股(2412 中華電)的提示"));
body.push(...FIG("appB_track.png", 5.0, "圖 A.5 成績追蹤:每日明細(判低點前 3 檔)"));
body.push(...FIG("appB_findings.png", 5.4, "圖 A.6 研究發現(結論卡片)"));
body.push(...FIG("appB_about.png", 5.0, "圖 A.7 方法與說明(節錄)"));

// ══════════════════════════ 文件 ══════════════════════════
const foot = () => new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: F, size: 20 })] })] });
const H1STYLE = { run: { font: F, size: 32, bold: true }, paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 240, after: 240, line: 360, lineRule: LineRuleType.AUTO }, keepNext: true, outlineLevel: 0 } };
const doc = new Document({
  creator: "郭家齊、呂偉湘", title: "以深度學習為基礎之自動化K線辨識系統", description: "逢甲大學資訊工程學系專題研究報告",
  features: { updateFields: true },
  styles: {
    default: {
      document: { run: { font: F, size: 24 }, paragraph: { spacing: BODY_LINE } },
      heading1: H1STYLE,
      heading2: { run: { font: F, size: 28, bold: true }, paragraph: { alignment: AlignmentType.LEFT, spacing: { before: 240, after: 120, ...BODY_LINE }, keepNext: true, outlineLevel: 1 } },
      heading3: { run: { font: F, size: 24, bold: true }, paragraph: { alignment: AlignmentType.LEFT, spacing: { before: 240, after: 120, ...BODY_LINE }, keepNext: true, outlineLevel: 2 } },
    },
    paragraphStyles: [
      { id: "FrontTitle", name: "FrontTitle", basedOn: "Normal", next: "Normal", run: { font: F, size: 32, bold: true },
        paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 240, after: 240, line: 360, lineRule: LineRuleType.AUTO }, keepNext: true } },
      { id: "FigCaption", name: "FigCaption", basedOn: "Normal", next: "Normal", run: { font: F, size: 22 },
        paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 0, after: 240, ...BODY_LINE } } },
      { id: "TabCaption", name: "TabCaption", basedOn: "Normal", next: "Normal", run: { font: F, size: 22 },
        paragraph: { alignment: AlignmentType.LEFT, keepNext: true, spacing: { before: 120, after: 60, ...BODY_LINE } } },
      { id: "TOC1", name: "toc 1", basedOn: "Normal", next: "Normal", run: { font: F, size: 24 }, paragraph: { spacing: { after: 60, ...BODY_LINE } } },
      { id: "TOC2", name: "toc 2", basedOn: "Normal", next: "Normal", run: { font: F, size: 24 }, paragraph: { indent: { left: 480 }, spacing: { after: 60, ...BODY_LINE } } },
    ],
  },
  sections: [
    { properties: { page: PAGE }, children: cover },
    { properties: { type: SectionType.NEXT_PAGE, page: { ...PAGE, pageNumbers: { start: 1, formatType: NumberFormat.LOWER_ROMAN } } }, footers: { default: foot() }, children: front },
    { properties: { type: SectionType.NEXT_PAGE, page: { ...PAGE, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } } }, footers: { default: foot() }, children: body },
  ],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(OUT, b); console.log("wrote", OUT, "figs", FIGS.length, "tables", TABS.length); });
