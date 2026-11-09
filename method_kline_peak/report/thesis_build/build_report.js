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
const POOLN = { "34": "34 檔", tw200: "TW200(168 檔)" };
const MN = { main: "主軸", stack: "Stacking" };
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

const a34 = C["34"].avg, a200 = C.tw200.avg;
front.push(H1("摘要"));
front.push(P(`本研究以台股日K線辨識「11 天局部高低點」:以第 t 日為中心、前後各 5 個交易日的收盤價為視窗,t 日收盤價為視窗內最高者標為高點、最低者標為低點,其餘為非極值。模型在 t 日收盤後判斷,只使用 t−5 至 t 共 6 根 K 線的開、高、低、收與成交量,共 29 維特徵。`));
front.push(P(`本研究比較兩個方法:① 主軸:先以規則挑出候選日,再以線性自編碼器(29 → 16 維)與單類支持向量機(One-Class SVM)篩選候選並給出分數;② Stacking:不使用規則,以高點、低點兩組自編碼器與單類支持向量機的分數為輸入,由多類別邏輯迴歸輸出三類機率。實驗採 walk-forward 方式,以前 4 年資料訓練、測試下一年,股票池為台灣50 剔除 16 檔低波動股後的 34 檔,以及 TW200 剔除低波動股後的 168 檔,測試期間為 2024 年至 2026 年 9 月。`));
front.push(P(`結果顯示,主軸的 macro-F1 三年平均在 34 檔為 ${a34.main.macro_f1}%、在 TW200 為 ${a200.main.macro_f1}%,均高於 Stacking(${a34.stack.macro_f1}%、${a200.stack.macro_f1}%);主軸找到真低點的比例為 ${a34.main.rec_low}% 與 ${a200.main.rec_low}%,判低點的命中率約三成,高於隨機猜測的約 7%,且三年中從未把高點判成低點或把低點判成高點。然而以「每天買進分數最高的前 3 檔、t+1 開盤買、t+5 收盤賣、來回成本 0.585%」回測,兩個方法三年平均扣成本報酬皆為負(34 檔 ${sg(B["34"].avg.main)} / ${sg(B["34"].avg.stack)};TW200 ${sg(B.tw200.avg.main)} / ${sg(B.tw200.avg.stack)})。後處理分析亦顯示,能明顯提高命中率的做法多半需要等待後續價格確認,而晚進場的代價抵銷了效益。`));
front.push(P("據此,本研究將模型定位為「提醒可能的轉折點」的決策輔助工具,而非自動交易系統,並實作網頁系統提供每日判斷、個股查詢與成績追蹤;系統以 47 項自動化測試驗證,其正式模型重現研究結果的 macro-F1 與混淆矩陣。"));
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
body.push(P("然而轉折點必須等到之後的價格走出來才能確認。同系郭念慈、李俊宏的研究 [1] 以 11 天的收盤價視窗定義局部高點與局部低點,並指出:若 t 日收盤是前後 5 天的最高,它必然也是 t−5 到 t 這 6 天的最高,而後者在 t 日收盤後就能知道。據此可以用簡單的規則在 t 日挑出「可能是高點 / 低點」的候選日,做為比較的基準。"));
body.push(H2("1.2 研究動機"));
body.push(P("規則基準不會漏掉任何真正的局部高低點,但候選日中多數其實不是轉折點。以本研究的 34 檔股票池為例,規則在 2024 年找到全部的真高點與真低點,但判高點與判低點的命中率都只有約 27%(見 4.2.1 節)。換言之,大約每 4 個候選日中只有 1 個是真正的轉折點。如果能從 t 日以前的 K 線型態中學到「真轉折點長什麼樣子」,就有機會刪去一部分假候選、讓訊號更可信,並進一步把訊號用在選股與交易上。"));
body.push(H2("1.3 研究目的"));
body.push(P("本研究的目的如下:"));
body.push(L("(1)", "在 [1] 的標籤與規則框架下,以自編碼器與單類支持向量機學習真高點、真低點的 K 線型態,篩選規則候選並給出可排序的分數(主軸)。"));
body.push(L("(2)", "比較不使用規則、改以邏輯迴歸組合兩組模型分數的 Stacking 方法。"));
body.push(L("(3)", "以 walk-forward 方式評估兩個方法的分類成績與交易模擬,並分析各種減少訊號的後處理做法。"));
body.push(L("(4)", "依研究結果實作網頁系統,讓使用者查詢每日判斷與歷史成績,作為決策輔助。"));
body.push(H2("1.4 研究範圍"));
body.push(L("(1)", "市場:台灣股票市場上市股票的日K線(還原權息價格)。"));
body.push(L("(2)", "股票池:台灣50 成分股剔除 16 檔低波動股後的 34 檔,以及 TW200 清單中有資料的 216 檔剔除 48 檔低波動股後的 168 檔(剔除規則見 4.1 節)。"));
body.push(L("(3)", "資料期間:2016 年 1 月至 2026 年 9 月 11 日的日K線。"));
body.push(L("(4)", "測試期間:2024 年、2025 年與 2026 年 1 月至 9 月 11 日,每一年都只用該年以前的資料訓練。"));
body.push(L("(5)", "交易模擬只做多,不考慮融券放空、滑價與漲跌停無法成交等情況(詳見 4.3 節與 5.2 節)。"));
body.push(H2("1.5 研究方法"));
body.push(P("本研究先依 [1] 為每個交易日貼上高點、低點或非極值的標籤,再以 t 日以前 6 根 K 線的 29 維特徵建立兩個三分類方法:主軸以規則挑候選,再由自編碼器把特徵壓縮到 16 維、由單類支持向量機判斷候選是否落在真轉折點的範圍內;Stacking 則以兩組模型的分數訓練多類別邏輯迴歸。評估採 walk-forward,以混淆矩陣、macro-F1、找到率(recall)與命中率(precision)衡量分類成績,再以只做多的回測、個股案例與後處理分析評估交易上的可行性,最後將模型實作成網頁系統。"));
body.push(H2("1.6 研究流程"));
body.push(P("研究流程如圖 1.1 所示。"));
body.push(...FIG("fig1_1_flow.png", 4.6, "圖 1.1 研究流程"));
body.push(H2("1.7 章節結構"));
body.push(P("第一章說明研究背景、動機、目的、範圍與流程。第二章回顧本研究使用的文獻與方法,並說明與前人研究的差別。第三章定義問題與標籤,介紹自編碼器、單類支持向量機與邏輯迴歸的理論基礎,以及兩個方法的架構與訓練方式。第四章為實證分析,包含資料分析、分類成績、回測與個案、後處理分析與網頁系統評估。第五章為結論、研究限制、成果、貢獻、後續研究方向,以及專題過程中導入的 AI 工具。"));

// ───── 第二章 ─────
body.push(H1("第二章 相關文獻回顧"));
body.push(H2("2.1 局部高低點標籤與規則基準"));
body.push(P("本研究的出發點是同系郭念慈、李俊宏的研究 [1]。該研究以第 t 日收盤價 C_t 與前後各 5 日構成的 11 日視窗定義標籤:C_t 為視窗內最高者為高點、最低者為低點,與他日並列者也算,其餘為非極值;並提出規則基準:t 日收盤為 t−5 至 t 最高者判為高點、最低者判為低點。本研究沿用此標籤與規則,並沿用其以「訓練資料中各類頻率的平方根倒數」設定類別權重的做法。"));
body.push(H2("2.2 自編碼器"));
body.push(P("自編碼器(Autoencoder, AE)由編碼器與解碼器組成,以重建輸入為目標進行訓練,中間的低維表示可視為資料的壓縮特徵。Hinton 與 Salakhutdinov [2] 證明以神經網路學習的低維編碼比主成分分析更能保留資料結構。本研究採用一層線性編碼器(29 → 16 維),在線性情況下其效果近似主成分分析;訓練使用 Adam 最佳化器 [3]。"));
body.push(H2("2.3 單類支持向量機"));
body.push(P("單類支持向量機(One-Class SVM, OC-SVM)由 Schölkopf 等人 [4] 提出,只用單一類別的樣本學習一個能涵蓋大部分樣本的區域,常用於異常偵測。參數 ν 為訓練樣本落在區域外比例的上界,也是支持向量比例的下界;決策函數大於 0 表示落在區域內。本研究分別以真高點、真低點的樣本各訓練一個 OC-SVM,判斷新的一天是否「像」過去的真轉折點,並以決策函數的值作為分數。"));
body.push(H2("2.4 堆疊泛化(Stacking)"));
body.push(P("Wolpert [5] 提出的堆疊泛化(Stacked Generalization)以第一層模型的輸出作為第二層模型的輸入,第二層模型必須用第一層沒看過的資料訓練,才能學到如何組合第一層的輸出。本研究依指導教授的建議,以高點、低點兩組 AE + OC-SVM 為第一層,以多類別邏輯迴歸為第二層,兩層使用不同年份的資料訓練。"));
body.push(H2("2.5 邏輯迴歸"));
body.push(P("邏輯迴歸由 Cox [6] 提出,以 logistic 函數將線性組合轉為機率;多類別情況下以 softmax 函數輸出各類機率 [7]。邏輯迴歸的係數可直接解讀,適合作為第二層模型,讓每一天的判斷可以手算驗證(見 3.3.5 節)。"));
body.push(H2("2.6 時間序列的驗證方式"));
body.push(P("時間序列資料前後相關,若隨機切分訓練與測試資料,模型可能看到測試期以後的資訊。Bergmeir 與 Benítez [8] 討論時間序列預測的交叉驗證方式,指出保留時間順序的評估較能反映實際使用情況。交易策略領域常用的 walk-forward 分析 [9] 則以「用過去一段期間訓練、在下一段期間測試,再整體往後移動」的方式重複評估。本研究採用 walk-forward:每個測試年都只用之前 4 年的資料訓練,並剔除訓練期最後 5 個交易日,因為這些日子的標籤需要看到測試年的價格。"));
body.push(H2("2.7 分類評估指標"));
body.push(P("三分類中非極值占大多數,單看準確率會被多數類主導。Sokolova 與 Lapalme [10] 整理了多類別分類的評估指標,其中 macro-F1 為各類 F1 的平均,對每一類一視同仁。本研究以 macro-F1 為主要指標,並分別報告高點、低點的找到率(recall,真轉折點中被判出的比例)與命中率(precision,判出的訊號中真的是轉折點的比例)。"));
body.push(H2("2.8 實作工具"));
body.push(P("本研究以 scikit-learn [11] 實作標準化、單類支持向量機與邏輯迴歸,以 PyTorch [12] 實作自編碼器。"));
body.push(H2("2.9 本研究與前人研究的差別"));
body.push(P("與 [1] 相比,本研究沿用相同的標籤與規則基準,差別在於:(1)在規則候選之上加入 AE + OC-SVM 篩選,並以決策函數作為可排序的分數;(2)另提出不使用規則的 Stacking 方法作為對照;(3)以 walk-forward 在 2024 至 2026 三個測試年、兩個股票池評估,並加入只做多的交易模擬與後處理分析,檢驗分類成績能否轉換成交易上的價值;(4)將模型實作為每日更新的網頁系統,並以自動化測試確認系統輸出與研究結果一致。"));

// ───── 第三章 ─────
body.push(H1("第三章 論文主體"));
body.push(H2("3.1 研究方法:問題定義與標籤"));
body.push(P(["令第 t 個交易日的收盤價為 ", I("C"), SUB("t"), ",以 t 為中心、前後各 5 日構成 11 日視窗,t 為視窗的第 6 天:"]));
body.push(EQ([I("W"), SUB("t"), " = { ", I("C"), SUB("t−5"), ", ", I("C"), SUB("t−4"), ", …, ", I("C"), SUB("t+5"), " }"], 1));
body.push(P(["標籤 ", I("y"), SUB("t"), " 定義如下:"]));
body.push(EQ([I("y"), SUB("t"), " = 高點,若 ", I("C"), SUB("t"), " = max ", I("W"), SUB("t"), ";  ", I("y"), SUB("t"), " = 低點,若 ", I("C"), SUB("t"), " = min ", I("W"), SUB("t")], 2));
body.push(P("其餘日子為非極值。與他日並列最高(最低)者也標為高點(低點);視窗內收盤價全部相同時為非極值;資料頭尾不足 11 天的日子不納入。由 Eq. (2) 可知,標籤需要 t+1 至 t+5 的價格,只能用於訓練與評估;模型在 t 日收盤後判斷,只能使用 t 日以前的資料。圖 3.1 為三種標籤的示意。"));
body.push(...FIG("fig3_1_label.png", 5.6, "圖 3.1 高點、低點與非極值的標籤示意"));
body.push(P("規則基準在 t 日收盤後判斷:若 C_t 為 t−5 至 t 這 6 天的最高,判為高點候選;若為最低,判為低點候選;其餘判為非極值。由 Eq. (2) 可知真高點一定是高點候選、真低點一定是低點候選,因此規則不會漏掉任何真轉折點,問題轉為「如何從候選中刪去假候選」。"));

body.push(H2("3.2 理論基礎"));
body.push(H3("3.2.1 自編碼器"));
body.push(P(["給定標準化後的特徵向量 ", I("x"), " ∈ R", SUP("29"), ",本研究使用的線性自編碼器為:"]));
body.push(EQ([I("z"), " = ", I("W"), SUB("e"), I("x"), " + ", I("b"), SUB("e"), ",  ", I("x̂"), " = ", I("W"), SUB("d"), I("z"), " + ", I("b"), SUB("d")], 3));
body.push(P(["其中 ", I("z"), " ∈ R", SUP("16"), " 為潛在表示。訓練目標為最小化平均平方重建誤差:"]));
body.push(EQ([I("L"), " = (1/", I("N"), ") Σ", SUB("i"), " ‖ ", I("x"), SUB("i"), " − ", I("x̂"), SUB("i"), " ‖", SUP("2")], 4));
body.push(P("訓練使用 Adam [3](學習率 0.001、權重衰減 0.00001)、餘弦退火學習率、批次大小 256,共 60 輪。"));
body.push(H3("3.2.2 單類支持向量機的決策函數"));
body.push(P(["OC-SVM [4] 在潛在空間中以核函數學習一個涵蓋訓練樣本的區域,其決策函數為:"]));
body.push(EQ([I("f"), "(", I("z"), ") = Σ", SUB("i"), " α", SUB("i"), " ", I("K"), "(", I("z"), SUB("i"), ", ", I("z"), ") − ρ"], 5));
body.push(EQ([I("K"), "(", I("z"), SUB("i"), ", ", I("z"), ") = exp(−γ ‖ ", I("z"), SUB("i"), " − ", I("z"), " ‖", SUP("2"), ")"], 6));
body.push(P("其中 α_i 為支持向量的係數,ρ 為偏移量,γ 為 RBF 核參數(本研究使用 scikit-learn 的 scale 設定)。f(z) > 0 表示 z 落在區域內。ν 設為 0.1。訓練時每個樣本另給一個相似度權重:在標準化後的特徵空間中,與該樣本歐氏距離不超過 3.0 的其他樣本裡,同為該類的比例,使型態較具代表性的樣本有較大的影響。本研究以 f(z) 作為分數:分數越高,表示越像過去的真轉折點。"));
body.push(H3("3.2.3 邏輯迴歸與 softmax"));
body.push(P(["Stacking 的第二層為多類別邏輯迴歸 [6][7]。以 ", I("s"), " = (", I("s"), SUB("high"), ", ", I("s"), SUB("low"), ") 表示兩個 OC-SVM 標準化後的分數,對類別 k ∈ {低點, 非極值, 高點}:"]));
body.push(EQ([I("z"), SUB("k"), " = ", I("w"), SUB("k"), " · ", I("s"), " + ", I("b"), SUB("k")], 7));
body.push(EQ([I("P"), "(", I("y"), " = ", I("k"), " | ", I("s"), ") = exp(", I("z"), SUB("k"), ") / Σ", SUB("j"), " exp(", I("z"), SUB("j"), ")"], 8));
body.push(P("判斷為機率最大的類別,分數為該類的機率。由於非極值占大多數,訓練時依 [1] 以類別頻率的平方根倒數設定類別權重,並正規化為平均 1:"));
body.push(EQ([I("w"), SUB("c"), " = (1/√", I("p"), SUB("c"), ") / mean", SUB("c′"), "(1/√", I("p"), SUB("c′"), ")"], 9));
body.push(P("其中 p_c 為類別 c 在訓練資料中的比例。"));

body.push(H2("3.3 方法架構"));
body.push(H3("3.3.1 特徵"));
body.push(P(["特徵只使用 t−5 至 t 共 6 根 K 線。對 k = 0, 1, …, 5,取開、高、低價相對 t 日收盤的對數比,以及 k ≥ 1 時的收盤價對數比:"]));
body.push(EQ(["ln(", I("O"), SUB("t−k"), " / ", I("C"), SUB("t"), "), ln(", I("H"), SUB("t−k"), " / ", I("C"), SUB("t"), "), ln(", I("L"), SUB("t−k"), " / ", I("C"), SUB("t"), "), ln(", I("C"), SUB("t−k"), " / ", I("C"), SUB("t"), ")"], 10));
body.push(P(["成交量則除以「到 t 日為止的 10 日均量」後取對數:ln(", I("V"), SUB("t−k"), " / ", I("V̄"), SUB("t"), ")。合計開、高、低各 6 個(18 維)、收盤 5 個(t 日本身為 0,不計)與成交量 6 個,共 29 維。特徵先以訓練期的中位數補缺值、標準化,再截斷在 ±5 之間。"]));
body.push(H3("3.3.2 主軸:規則候選 + AE + OC-SVM"));
body.push(P("主軸的架構如圖 3.2。高點、低點各一組模型,步驟如下:"));
body.push(L("(1)", "規則候選:以 3.1 節的規則挑出高點候選與低點候選;非候選一律判為非極值。"));
body.push(L("(2)", "標準化:以訓練期候選日的特徵計算中位數(補缺值)與標準化參數。"));
body.push(L("(3)", "AE:只用訓練期的真候選(例如真高點)訓練 29 → 16 的線性自編碼器。"));
body.push(L("(4)", "OC-SVM:以 AE 的 16 維編碼與相似度權重訓練 RBF 核、ν = 0.1 的 OC-SVM。"));
body.push(L("(5)", "判斷與分數:測試時,候選日的決策函數 > 0 才保留為該類,否則改判非極值;決策函數同時作為分數,用於回測排序。"));
body.push(...FIG("fig3_2_main_arch.png", 5.7, "圖 3.2 主軸架構"));
body.push(H3("3.3.3 Stacking:兩層模型"));
body.push(P("Stacking 的架構如圖 3.3。第一層不使用規則,以 A 期(3 年)的全部日子計算標準化與相似度權重,高點、低點兩組 AE + OC-SVM 只用 A 期的真高點(真低點)訓練,並對每一天輸出兩個分數 s_high、s_low。第二層以 B 期(1 年)每一天的兩個分數(標準化後)為輸入,訓練多類別邏輯迴歸(L2 正則化、類別權重如 Eq. (9)),輸出三類機率。A、B 兩期之間剔除 5 個交易日,避免標籤重疊。"));
body.push(...FIG("fig3_3_stack_arch.png", 5.7, "圖 3.3 Stacking 兩層架構"));
body.push(H3("3.3.4 walk-forward 訓練期間"));
body.push(P("每個測試年都只用之前 4 年的資料訓練,種子固定為 42。各測試年的訓練期間如表 3.1 與圖 3.4。以 2025 年為例:主軸以 2021 至 2024 年訓練;Stacking 的第一層以 2021 至 2023 年訓練,第二層以 2024 年訓練;測試期間為 2025 年全年。"));
body.push(...TAB("表 3.1 walk-forward 訓練與測試期間", ["測試年", "規則基準", "① 主軸", "② Stacking 第一層 A", "② Stacking 第二層 B"], [
  ["2024", "不需訓練", "2020–2023", "2020–2022", "2023"],
  ["2025", "不需訓練", "2021–2024", "2021–2023", "2024"],
  ["2026(1–9 月)", "不需訓練", "2022–2025", "2022–2024", "2025"],
], [1.4, 1.1, 1.3, 1.6, 1.6], { size: 22, note: "註:每段訓練期都剔除最後 5 個交易日,因為其標籤需要看到下一段的價格。" }));
body.push(...FIG("fig3_4_walkforward.png", 5.6, "圖 3.4 walk-forward 時間軸"));

body.push(H3("3.3.5 邏輯迴歸的計算實例"));
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
body.push(P("例子 (d) 與 (a) 相隔一天,兩天的分數幾乎相同,都被判為低點,但只有 (a) 是真低點。這說明模型能指出「低點附近」,卻難以分辨是哪一天,這也是第四章後處理分析的出發點。"));

// ───── 第四章 ─────
body.push(H1("第四章 實證分析"));
body.push(H2("4.1 資料分析"));
body.push(H3("4.1.1 資料來源與股票池"));
body.push(P("日K線取自 Yahoo Finance(透過 yfinance 套件 [13])的還原權息價格,期間為 2016 年 1 月 1 日至 2026 年 9 月 11 日。部分股票的每日漲跌幅很小,標籤多半只是小起伏,因此本研究剔除低波動股:計算 2020 年 1 月以後每日收盤漲跌幅絕對值的中位數,低於 0.725% 者剔除。此標準套用在台灣50 時正好剔除 16 檔(中華電、台灣大、合庫金、台灣高鐵、第一金、遠傳、華南金、兆豐金、統一超、玉山金、亞泥、台新金、統一、永豐金、台泥、中信金),剩 34 檔。TW200 清單共 222 檔,有資料者 216 檔,剔除 48 檔低波動股後剩 168 檔。"));
body.push(...TAB("表 4.1 股票池", ["股票池", "原始檔數", "有資料", "剔除低波動", "使用檔數"], [
  ["34 檔(台灣50)", "50", "50", String(B["34"].excluded_n), String(B["34"].pool_n)],
  ["TW200", "222", "216", String(B.tw200.excluded_n), String(B.tw200.pool_n)],
], [2.2, 1.2, 1.2, 1.4, 1.2], { size: 22 }));
body.push(H3("4.1.2 標籤比例"));
body.push(P("表 4.2 為各測試年的標籤分布(個數取自混淆矩陣的列加總)。高點、低點各約占 7%,非極值約占 86%,類別相當不平衡,因此以 macro-F1 為主要指標,並以「隨機猜的命中率約等於該類比例」作為基準。"));
const labRows = [];
for (const p of ["34", "tw200"]) for (const y of Y) {
  const l = C[p][y].labels;
  labRows.push([`${POOLN[p]} ${YL[y]}`, l.n.toLocaleString(), `${l.low.toLocaleString()}(${(l.low / l.n * 100).toFixed(2)}%)`,
    `${l.flat.toLocaleString()}(${(l.flat / l.n * 100).toFixed(2)}%)`, `${l.high.toLocaleString()}(${(l.high / l.n * 100).toFixed(2)}%)`]);
}
body.push(...TAB("表 4.2 測試期的標籤分布(股票日數)", ["股票池・測試年", "總數", "低點", "非極值", "高點"], labRows, [2.6, 1.1, 1.6, 1.8, 1.6], { size: 20 }));

body.push(H2("4.2 統計分析"));
body.push(H3("4.2.1 混淆矩陣"));
body.push(P("圖 4.1 與圖 4.2 分別為 34 檔與 TW200 在 2024 至 2026 年的混淆矩陣,上排為主軸、下排為 Stacking;列為真實標籤、欄為判斷,每格下方為該方法當年的找到率與命中率。為了在版面上清楚呈現,本研究將原圖的六個矩陣重新排列為三欄(年份)兩列(方法)。"));
body.push(...FIG("fig4_1_conf_34.png", 5.75, "圖 4.1 34 檔混淆矩陣(2024–2026)"));
body.push(...FIG("fig4_2_conf_tw200.png", 5.75, "圖 4.2 TW200 混淆矩陣(2024–2026)"));
const mRows = [];
for (const p of ["34", "tw200"]) for (const k of ["main", "stack"]) for (const y of Y) {
  const v = C[p][y][k];
  mRows.push([`${POOLN[p]} ${MN[k]}`, YL[y], v.macro_f1.toFixed(2), pct(v.rec_low), pct(v.rec_high), pct(v.prec_low), pct(v.prec_high), String(C[p][y].reversed[k])]);
}
body.push(...TAB("表 4.3 逐年分類成績", ["股票池・方法", "測試年", "macro-F1(%)", "找到率 低點", "找到率 高點", "命中率 低點", "命中率 高點", "高低點判反"], mRows,
  [2.1, 1.45, 1.1, 0.95, 0.95, 0.95, 0.95, 0.8], { size: 18, note: "註:高低點判反 = 真低點判成高點與真高點判成低點的個數合計。" }));
body.push(P("由表 4.3 可得到三點觀察:第一,兩個方法在兩個股票池、三個測試年中,高低點判反的個數都是 0,模型從未把低點判成高點或把高點判成低點。第二,主軸找到大部分的轉折點,例如 TW200 2024 年找到真低點 " +
  pct(C.tw200["2024"].main.rec_low) + "、真高點 " + pct(C.tw200["2024"].main.rec_high) + "。第三,判高點、判低點的命中率約為三成。作為對照,規則基準在 34 檔 2024 年找到全部的真高低點,命中率高點、低點各約 27%;主軸在 34 檔的 macro-F1 與規則相差 0.2 至 1.3 點(規則三年依序為 52.10、53.30、54.22)。"));
body.push(H3("4.2.2 隨機基準"));
body.push(P(`若隨機挑一個股票日,它剛好是真低點(真高點)的機率等於該類的比例。以 TW200 為例,${D.random_line.replace("隨機猜的命中率基準(真低點 / 真高點占全部股票日):", "真低點 / 真高點占全部股票日的比例為:")}因此隨機猜的命中率約為 7%,兩個方法約三成的命中率約為隨機的 4 倍。`));
body.push(H3("4.2.3 主軸與 Stacking 的比較"));
body.push(P("表 4.4 為三年平均的比較,圖 4.3 為逐年的 macro-F1。"));
const avgRow = (name, f) => [name, ...["34", "tw200"].flatMap((p) => ["main", "stack"].map((k) => f(C[p].avg[k], p, k)))];
body.push(...TAB("表 4.4 主軸與 Stacking 的三年平均比較", ["指標(三年平均)", "34 檔 主軸", "34 檔 Stacking", "TW200 主軸", "TW200 Stacking"], [
  avgRow("macro-F1(%)", (v) => v.macro_f1.toFixed(2)),
  avgRow("找到率 低點", (v) => pct(v.rec_low)),
  avgRow("找到率 高點", (v) => pct(v.rec_high)),
  avgRow("命中率 低點", (v) => pct(v.prec_low)),
  avgRow("命中率 高點", (v) => pct(v.prec_high)),
  avgRow("回測扣成本報酬", (v, p, k) => sg(B[p].avg[k])),
], [2.0, 1.4, 1.4, 1.4, 1.4], { size: 20, note: "註:三年平均由逐年數字計算;回測為「每天前 3 檔、持有 5 天」(見 4.3 節)。" }));
body.push(...FIG("fig4_3_macro_f1.png", 5.6, "圖 4.3 主軸與 Stacking 的逐年 macro-F1"));
const dif = (p) => Y.map((y) => (C[p][y].main.macro_f1 - C[p][y].stack.macro_f1).toFixed(2));
body.push(P(`分類上主軸較佳:兩個股票池的每一年,主軸的 macro-F1 都比 Stacking 高 3 至 4 點(34 檔逐年差 ${dif("34").join("、")} 點;TW200 逐年差 ${dif("tw200").join("、")} 點),主要差在找到率:主軸找到的真低點在 34 檔為 ${a34.main.rec_low}%、Stacking 只有 ${a34.stack.rec_low}%。命中率兩個方法差不多,約三成,主軸略高 1.6 至 3.0 點。Stacking 判得較少,例如 34 檔 2024 年判低點 ${B["34"]["2024"].stack.n_low.toLocaleString()} 天,主軸為 ${B["34"]["2024"].main.n_low.toLocaleString()} 天。回測上三年平均 Stacking 虧得少一點,但兩個方法每年的報酬起伏都很大,而且三年平均都是虧損(見 4.4 節)。`));

body.push(H2("4.3 實驗設計"));
body.push(P("為檢驗分類結果能否轉換成交易上的價值,本研究設計只做多的回測,規則如下:"));
const rl = B["34"].rule;
body.push(L("(1)", "每天 t 收盤後,在股票池中選出判為低點、分數最高的前 3 檔。"));
body.push(L("(2)", "t+1 開盤買進,每檔投入 1/3 資金;t+5 收盤賣出(持有 5 個交易日)。"));
body.push(L("(3)", "判高點不放空。持股中的股票不重複買進;空位不足時依分數排序。"));
body.push(L("(4)", "每一年獨立以 100 萬元開始,年底結清;2026 年只到 9 月 11 日。"));
body.push(L("(5)", "漲停時也假設買得到,不考慮滑價。"));
body.push(P(`交易成本為買進手續費 ${(rl.buy_fee * 100).toFixed(4)}%、賣出手續費 ${(rl.sell_fee * 100).toFixed(4)}% 與證券交易稅 ${(rl.tax * 100).toFixed(1)}%,一次來回合計:`));
body.push(EQ(["0.1425% × 2 + 0.3% = 0.585%"], 11));
body.push(P("報告中同時列出扣成本與沒扣成本的報酬,以區分模型本身的方向判斷與交易成本的影響。"));

body.push(H2("4.4 模擬分析"));
body.push(H3("4.4.1 回測結果"));
const btRows = (p) => {
  const rows = [];
  for (const y of Y) for (const k of ["main", "stack"]) {
    const v = B[p][y][k];
    rows.push([YL[y], MN[k], sg(v.net), sg(v.gross), sg(v.dd), pct(v.win), String(v.n)]);
  }
  rows.push({ opt: { bold: true }, cells: ["三年平均", "主軸 / Stacking", `${sg(B[p].avg.main)} / ${sg(B[p].avg.stack)}`, "", "", "", ""] });
  return rows;
};
body.push(...TAB("表 4.5 34 檔回測結果", ["年", "方法", "扣成本報酬", "沒扣成本報酬", "最大回撤(扣成本)", "勝率(扣成本)", "交易筆數"],
  btRows("34"), [1.5, 1.4, 1.3, 1.3, 1.4, 1.1, 0.9], { size: 20 }));
body.push(...TAB("表 4.6 TW200 回測結果", ["年", "方法", "扣成本報酬", "沒扣成本報酬", "最大回撤(扣成本)", "勝率(扣成本)", "交易筆數"],
  btRows("tw200"), [1.5, 1.4, 1.3, 1.3, 1.4, 1.1, 0.9], { size: 20 }));
body.push(P(`每年約 88 至 144 筆交易,每筆來回成本 0.585%,扣成本前後差距很大。以 34 檔主軸為例,2024 年每筆平均報酬扣成本為 ${sg(B["34"]["2024"].main.avg_net)}。兩個股票池、兩個方法的三年平均扣成本報酬都是負的;沒扣成本時則有幾個年份為正(例如 34 檔 2026 年主軸 ${sg(B["34"]["2026"].main.gross)}、TW200 2024 年主軸 ${sg(B.tw200["2024"].main.gross)}),顯示模型的方向判斷有部分價值,但不足以支付交易成本。圖 4.4 與圖 4.5 為逐日資產曲線,實線為扣成本、虛線為沒扣成本。`));
body.push(...FIG("fig4_4_curves_34.png", 5.75, "圖 4.4 34 檔回測資產曲線"));
body.push(...FIG("fig4_5_curves_tw200.png", 5.75, "圖 4.5 TW200 回測資產曲線"));

body.push(H3("4.4.2 個案:南電 2024 年"));
body.push(P("為觀察模型在單一股票上的行為,本研究選擇南電(8046)作為範例:在 34 檔中,其 2020 年以後每日漲跌幅絕對值的中位數最高。南電 2024 年共 242 個交易日,真高點 17 個、真低點 16 個,全年大致下跌。圖 4.6 與圖 4.7 分別為 34 檔模型與 TW200 模型的每日判斷,上段為真實標籤、中段為主軸、下段為 Stacking;實心三角形為判對、空心為判錯,綠色區間為回測中實際持有的期間。"));
const nd = D.nandian;
const ndRow = (p, k) => {
  const v = nd[p][k], cm = v.cm;
  const pl = cm[0][0] + cm[1][0] + cm[2][0], ph = cm[0][2] + cm[1][2] + cm[2][2];
  return [`${POOLN[p]} ${MN[k]}`, `${pl}(${cm[0][0]} / ${pl - cm[0][0]})`, `${ph}(${cm[2][2]} / ${ph - cm[2][2]})`,
    v.macro_f1.toFixed(2), `${v.rec["低點"]}% / ${v.rec["高點"]}%`, `${v.prec["低點"]}% / ${v.prec["高點"]}%`];
};
body.push(...TAB("表 4.7 南電 2024 年的判斷", ["模型・方法", "判低點天數(對 / 錯)", "判高點天數(對 / 錯)", "macro-F1(%)", "找到率 低 / 高", "命中率 低 / 高"],
  [ndRow("34", "main"), ndRow("34", "stack"), ndRow("tw200", "main"), ndRow("tw200", "stack")], [2.3, 1.5, 1.5, 1.0, 1.4, 1.4], { size: 20 }));
body.push(P("兩個模型判出的低點都遠多於真低點(例如 TW200 主軸判低點 70 天,只有 13 天是真低點),假訊號多集中在真低點前後的連續下跌日。同一檔股票換成不同股票池訓練的模型,判斷的天數與對錯也明顯不同。"));
body.push(...FIG("fig4_6_nandian_34.png", 5.75, "圖 4.6 南電 2024 年:34 檔模型的每日判斷"));
body.push(...FIG("fig4_7_nandian_tw200.png", 5.75, "圖 4.7 南電 2024 年:TW200 模型的每日判斷"));

body.push(H3("4.4.3 後處理分析"));
body.push(P("4.4.2 節顯示模型的問題主要是「同一段走勢連續多天出訊號」。本節在不改變模型、不調參數的前提下,以 TW200 模型 2024 至 2026 年的輸出比較幾種減少訊號的後處理,被拿掉的訊號改判非極值,對答案一律使用原本的標籤:"));
body.push(L("(1)", ["1a 合併連續・事後最高分:同一檔同一類相鄰交易日都有訊號視為一段,每段只留分數最高的一天。要等這段結束才知道哪天最高,用到未來資訊,", ["僅作上限參考,實務不可行", { bold: true }], "。"]));
body.push(L("(2)", "1b 合併連續・即時版:段內某天只有分數高於這段之前每一天才保留,第一天一定保留;只用當天以前的資訊。"));
body.push(L("(3)", "每天前 X%:每天同一類的訊號依分數排序,只留前 X%。"));
body.push(L("(4)", "等確認 k 天:t 判低點後,t+1 至 t+k 的收盤都不低於 t 的收盤才確認,否則取消(高點反之);交易須等到 t+k+1 才能進場。"));
body.push(L("(5)", "Stacking 機率門檻:Stacking 輸出的最大機率達到門檻(例如 0.7)才出訊號。此處的門檻是指模型輸出的機率。"));
body.push(P("找到率 ±2 天表示真轉折點前後 2 個交易日內(同一檔)有同類訊號。結果如表 4.8 至表 4.12。"));
const postRows = (tab) => pick(tab, ["規則", "macro-F1", "低 命中率", "低 找到率", "低 找到率 ±2 天", "高 命中率", "高 找到率", "高 找到率 ±2 天"], (r) => [label(r[0]), ...r.slice(1)]);
const POSTH = ["做法", "macro-F1", "低 命中率", "低 找到率", "低 ±2 天", "高 命中率", "高 找到率", "高 ±2 天"];
const POSTW = [2.6, 1.0, 0.95, 0.95, 0.95, 0.95, 0.95, 0.95];
const FUTNOTE = "註:† 用到未來資訊,僅作上限參考,實務不可行。";
body.push(...TAB("表 4.8 後處理比較:主軸(TW200,三年平均)", POSTH, postRows(R.post_main), POSTW, { size: 18, note: FUTNOTE }));
body.push(...TAB("表 4.9 後處理比較:Stacking(TW200,三年平均)", POSTH, postRows(R.post_stack), POSTW, { size: 18, note: FUTNOTE }));
body.push(P("合併連續的即時版(1b)與每天前 X% 都會降低 macro-F1:命中率幾乎不變,找到率卻下降。只有用到未來資訊的 1a 能同時提高命中率,但實務上無法使用。"));
const ccRows = pick(R.conf_cls, ["方法", "規則", "macro-F1(2024 / 2025 / 2026)", "命中率", "找到率 當天", "找到率 ±2 天"],
  (r) => [r[0].replace("Stacking 邏輯迴歸", "Stacking"), /^k=/.test(r[1]) ? `${r[1]}‡` : label(r[1]), r[2].split("(")[0], r[3], r[4], r[5]]);
body.push(...TAB("表 4.10 等確認 k 天的分類成績(TW200,三年平均;低 / 高)", ["方法", "做法", "macro-F1", "命中率", "找到率 當天", "找到率 ±2 天"], ccRows,
  [1.3, 1.3, 1.1, 1.6, 1.6, 1.6], { size: 18, note: "註:† 用到未來資訊,僅作上限參考,實務不可行。‡ 分類成績在 t 日評分,但用到 t+1 至 t+k 的價格,僅作上限參考,實務不可行;實際交易須在 t+k+1 進場,見表 4.11。" }));
body.push(P("等確認後分類成績大幅提高(主軸 macro-F1 由 54 提高到 72 至 85),但這主要是定義造成的:真低點本來就要求 t+1 至 t+5 的收盤都不低於 t,確認條件是真低點的必要條件,所以真低點一定會被確認,被取消的全是假訊號。實際交易必須等到 t+k+1 才能進場,回測結果如表 4.11。"));
const cbRows = pick(R.conf_bt, ["k", "方法", "2024 扣 / 沒扣", "2025 扣 / 沒扣", "2026 扣 / 沒扣", "3 年平均 扣 / 沒扣"],
  (r) => [r[0], r[1].replace("Stacking 邏輯迴歸", "Stacking"), r[2], r[3], r[4], r[5]]);
body.push(...TAB("表 4.11 等確認 k 天的回測(TW200,報酬 %,扣成本 / 沒扣成本)", ["k", "方法", "2024", "2025", "2026(1–9 月)", "三年平均"], cbRows,
  [0.5, 1.2, 1.6, 1.6, 1.6, 1.6], { size: 18, note: "註:k = 0 即不確認,與表 4.6 相同;確認後於 t+k+1 開盤買進,其餘規則同 4.3 節。" }));
body.push(P("等確認的回測扣成本報酬三年平均沒有變好(主軸 −26.05% → −27.06% / −24.77% / −23.90%;Stacking −21.69% → −28.95% / −42.61% / −35.14%)。同一批確認的低點,若能在 t+1 進場,平均每筆為 +0.1% 至 +4.7%(這要先知道會被確認,實際做不到);等到 t+k+1 進場則變成 −0.8% 至 +0.7%,每晚 1 天約少 0.8 至 1.5 個百分點。"));
const pRows = pick(R.prob_all, ["門檻", "訊號數", "命中率", "找到率 當天", "找到率 ±2 天", "macro-F1"],
  (r) => [r[0].replace("不設門檻(原始)", "不設機率門檻(原始)"), r[1], r[2], r[3], r[4], r[5]]);
body.push(...TAB("表 4.12 Stacking 機率門檻(TW200 168 檔,三年平均;低 / 高)", ["機率門檻", "訊號數(每年)", "命中率", "找到率 當天", "找到率 ±2 天", "macro-F1"], pRows,
  [2.0, 1.5, 1.4, 1.4, 1.4, 0.9], { size: 18, note: "註:此處的門檻為 Stacking 輸出的最大機率;未達門檻者改判非極值。最大機率 ≥ 0.9 只有 2024 年有 39 個判低點,2025、2026 年沒有,故三年平均命中率記為「—」。" }));
body.push(P(`機率門檻越高,命中率只小幅上升(低點由 27.7% 到 32.8%),找到率卻大幅下降(低點由 48.4% 到 4.9%)。${D.prob_median_line.replace(/。$/, "")},多數訊號的機率集中在 0.6 左右,因此提高門檻主要是減少訊號,而不是篩出更準的訊號。圖 4.8 與圖 4.9 以南電 2024 年為例,呈現各種後處理與機率門檻留下的訊號。`));
body.push(...FIG("fig4_8_post_nandian.png", 5.2, "圖 4.8 南電 2024 年:各種後處理留下的訊號(主軸,TW200 模型)"));
body.push(...FIG("fig4_9_probcut.png", 5.6, "圖 4.9 南電 2024 年:Stacking 機率門檻留下的訊號(TW200 模型)"));

body.push(H3("4.4.4 低點進、高點出"));
body.push(P("4.4.1 節的回測固定持有 5 天。本節改成「低點進場、高點出場」:判低點(或後處理後的低點)隔天開盤買進,持有中出現判高點時隔天開盤賣出,沒有最長持有天數,年底平倉,成本 0.585%。單一股票以南電 2024 年為例(100 萬全部投入),多檔組合以 34 檔 2025 年為例(最多同時 3 檔、每檔前一天總資產的 1/3)。"));
const lohiRows = (tab) => pick(tab, ["方法", "列", "扣成本", "沒扣成本", "筆數", "勝率", "平均持有(天)", "最大回撤"],
  (r) => [r[0].replace("Stacking 邏輯迴歸", "Stacking"), label(r[1]), r[2], r[3], r[4], r[5], r[6], r[7]]);
const LOHIH = ["方法", "訊號", "扣成本", "沒扣成本", "筆數", "勝率", "平均持有(天)", "最大回撤"];
const LOHIW = [1.1, 2.4, 1.1, 1.1, 0.6, 0.9, 1.0, 1.0];
body.push(...TAB("表 4.13 南電 2024 年:低點進、高點出(TW200 模型)", LOHIH, lohiRows(R.nd_lohi), LOHIW,
  { size: 17, note: `註:† 用到未來資訊,僅作上限參考,實務不可行。${D.lohi_bh_line}` }));
body.push(...TAB("表 4.14 34 檔 2025 年:低點進、高點出(多檔組合)", LOHIH, lohiRows(R.lohi34), LOHIW,
  { size: 17, note: `註:† 用到未來資訊,僅作上限參考,實務不可行。${D.lohi34_base_line}` }));
body.push(P("若事先知道真實標籤(僅作上限參考,實務不可行),低點進、高點出在南電 2024 年可得扣成本 +144.10%,在 34 檔 2025 年可得 +629.07%,說明標籤本身代表的波動很大;但以模型的訊號實際操作,南電 2024 年主軸為 −40.95%、Stacking 為 −28.05%,仍優於買進持有的 −47.17%;34 檔 2025 年主軸為 −15.13%,低於等權買進持有的 +19.16%,Stacking 等確認 1 天為 +22.42%,是表中除真實標籤外唯一超過等權買進持有的做法。由於這些比較都是直接看測試年的結果,並未事先以驗證期選定做法,不應視為可穩定獲利的證據。"));
body.push(...FIG("fig4_10_lohi_nandian.png", 5.2, "圖 4.10 南電 2024 年:低點進、高點出的持有期間(主軸)"));
body.push(...FIG("fig4_11_lohi_34.png", 5.75, "圖 4.11 34 檔 2025 年:低點進、高點出的資產曲線"));

body.push(H2("4.5 系統評估"));
body.push(H3("4.5.1 系統架構"));
body.push(P("依前述結果,模型適合用來提醒「哪裡可能是高點、低點」,不適合直接拿來自動買賣。因此本研究將模型實作為本機執行的網頁系統(展示版),每天收盤後產生判斷,並提供個股查詢與成績追蹤。系統的運作方式如表 4.15。"));
body.push(...TAB("表 4.15 網頁系統的運作方式", ["項目", "做法"], [
  ["股票池", "設定值,預設 TW100 剔除低波動股(2026 年為 73 檔);可換成 TW200 等股票池"],
  ["模型", "與研究 walk-forward 相同的主軸與 Stacking;Y 年以 Y−4 至 Y−1 年訓練,種子 42"],
  ["重訓", "每年 1 月第 6 個交易日之後第一次執行批次時自動訓練新的一年"],
  ["資料", "yfinance 還原價,增量下載並快取;還原價變動時重抓整段"],
  ["每日判斷", "股票池內、池外、低波動股都計算;推薦清單只列池內股票,依分數排序"],
  ["存檔", "當天判斷與 5 天後的答案分別存檔,寫入後不再修改"],
  ["對答案", "t+5 收盤後以研究的同一個標籤規則判斷,並記錄 t+1 開盤至 t+5 收盤的報酬(扣成本 0.585%)"],
  ["前端", "靜態網頁,讀取每次批次產生的資料檔;支援淺色、深色主題與手機版面"],
], [1.3, 6.0], { size: 20, align: [AlignmentType.CENTER, AlignmentType.LEFT] }));
body.push(H3("4.5.2 系統功能"));
body.push(P("網頁共有五個頁面:今日判斷(判低點、判高點依分數排序,並依「已幾天沒破底 / 沒創高」分組)、個股查詢(兩個方法的判斷、各類分數、K 線與過去訊號的對錯)、成績追蹤(每天的判斷 5 天後對答案、命中率)、研究發現(本研究的結論與後處理分析表),以及方法與說明(標籤定義、兩個方法、研究命中率與回測、免責聲明)。圖 4.12 至圖 4.14 為主要頁面的截圖(資料至 2026 年 9 月 10 日),其餘頁面見附錄二。"));
body.push(...FIG("fig4_12_web_today.png", 5.4, "圖 4.12 網頁系統:今日判斷"));
body.push(...FIG("fig4_13_web_stock.png", 5.0, "圖 4.13 網頁系統:個股查詢(池內股票 8454 富邦媒)"));
body.push(...FIG("fig4_14_web_track.png", 5.4, "圖 4.14 網頁系統:成績追蹤"));
body.push(H3("4.5.3 系統測試與一致性"));
body.push(P("系統以 47 項自動化測試驗證,涵蓋:資料更新(增量下載、還原價變動重抓、網路失敗、休市)、判斷存檔不覆蓋、5 天後才對答案、池內 / 池外 / 低波動 / 不支援股票的判定、判斷檔格式、股票池設定、兩方法一致時的命中率、連續天數與沒破底天數不偷看未來、研究發現頁的數字與結果檔一致、特徵不偷看未來、每日批次與回放結果相同,以及正式模型重現研究結果。"));
body.push(P("其中「正式模型重現研究結果」的測試以系統的正式模型重新判斷 2026 年 TW100 股票池的 11,826 筆測試資料,確認兩個方法的 macro-F1 與混淆矩陣和研究結果檔完全相同(macro-F1 差距小於 10⁻¹²)。因此網頁上的每日判斷與研究評估的是同一套模型。"));

// ───── 第五章 ─────
body.push(H1("第五章 結論與建議"));
body.push(H2("5.1 結論"));
body.push(L("(1)", `模型抓得到大方向:兩個股票池、三個測試年中,兩個方法都沒有把高點判成低點或把低點判成高點;主軸找到大部分的轉折點(三年平均找到真低點 34 檔 ${a34.main.rec_low}%、TW200 ${a200.main.rec_low}%),判低點的命中率約三成,約為隨機猜測(約 7%)的 4 倍。`));
body.push(L("(2)", `主軸的分類成績優於 Stacking:每一年 macro-F1 都高 3 至 4 點(三年平均 34 檔 ${a34.main.macro_f1}% 對 ${a34.stack.macro_f1}%、TW200 ${a200.main.macro_f1}% 對 ${a200.stack.macro_f1}%),差別主要在找到率;命中率兩者相近。`));
body.push(L("(3)", "模型當天分不出真假:假訊號集中在真轉折點前後的連續日子。即時可用的後處理(合併連續的即時版、每天前 X%、提高機率門檻)都無法在不犧牲找到率的情況下提高命中率;等待確認雖然能剔除假訊號,但晚進場的代價抵銷了效益。"));
body.push(L("(4)", `以「每天前 3 檔、持有 5 天」交易,兩個方法三年平均扣成本報酬皆為負(34 檔 ${sg(B["34"].avg.main)} / ${sg(B["34"].avg.stack)};TW200 ${sg(B.tw200.avg.main)} / ${sg(B.tw200.avg.stack)}),每年起伏也大。因此本研究將模型定位為決策輔助,而非自動交易。`));
body.push(L("(5)", "報告與網頁系統以主軸為主、Stacking 為對照;網頁系統的正式模型重現研究結果,可作為每日提醒與成績追蹤的工具。"));
body.push(H2("5.2 研究限制"));
body.push(L("(1)", "特徵只使用 6 根 K 線的價格與成交量;研究過程中加入位階、技術指標、大盤與籌碼等特徵的實驗,並未使真候選的保留率明顯高於假候選。"));
body.push(L("(2)", "低波動股的剔除以 2020 年 1 月至 2026 年 9 月的每日漲跌幅計算,涵蓋了測試期間;TW200 也使用目前的清單,未處理成分股變動,可能有存活者偏誤。"));
body.push(L("(3)", "回測為簡化設定:假設漲停時買得到、沒有滑價、每年獨立 100 萬元且只取前 3 檔,單一年份的結果受少數幾筆交易影響大;2026 年只有 1 至 9 月。"));
body.push(L("(4)", "主要結果只使用種子 42;後處理與低點進高點出的比較是直接看測試年的結果,沒有以驗證期事先選定做法。"));
body.push(L("(5)", "標籤需要 t+5 的價格,網頁系統的成績追蹤也必須等 5 個交易日後才能對答案。"));
body.push(H2("5.3 研究成果"));
body.push(L("(1)", "在 [1] 的標籤與規則框架下,完成主軸(規則 + AE + OC-SVM)與 Stacking(兩組 AE + OC-SVM + 邏輯迴歸)兩個三分類方法,並可輸出每日的分數與機率。"));
body.push(L("(2)", "完成兩個股票池、三個測試年的 walk-forward 評估,包括混淆矩陣、回測、個股案例、後處理、等確認、機率門檻與低點進高點出等分析,所有數字都保存在結果檔中、可重現。"));
body.push(L("(3)", "完成網頁系統(展示版):每日批次、判斷存檔、5 天後對答案、今日判斷、個股查詢、成績追蹤、研究發現與方法說明頁,並以 47 項自動化測試驗證。"));
body.push(H2("5.4 研究貢獻"));
body.push(L("(1)", "以實證說明「分類成績不錯」與「交易能賺錢」之間的落差:模型找得到大部分轉折點,但當天分不出真假,扣除 0.585% 的交易成本後無法獲利。"));
body.push(L("(2)", "區分可實行與用到未來資訊的後處理,並量化晚進場的代價,避免高估等確認類做法的效果。"));
body.push(L("(3)", "提供可解讀的範例:以真實數字逐步計算邏輯迴歸的機率,並與套件輸出核對誤差為 0。"));
body.push(L("(4)", "將研究模型與網頁系統以自動化測試連結,確保系統輸出與研究結果一致。"));
body.push(H2("5.5 後續研究方向"));
body.push(L("(1)", "加入能區分「低點當天」與「低點前後」的資訊,例如當天以後的盤中資料或分時成交量,改善當天分不出真假的問題。"));
body.push(L("(2)", "以驗證期事先選定後處理與交易規則,再於測試期評估,並增加多個亂數種子的結果。"));
body.push(L("(3)", "使用歷史成分股清單與不含測試期的低波動判定,降低存活者偏誤與資訊洩漏。"));
body.push(L("(4)", "網頁系統持續累積實際上線後的判斷與答案,以真實時間序列評估長期表現。"));
body.push(H2("5.6 專題過程導入的 AI 工具"));
body.push(P("本專題使用 Claude Code(Anthropic)[14] 作為輔助工具,協助以下工作:"));
body.push(L("(1)", "程式撰寫:標籤、特徵、主軸與 Stacking 模型、walk-forward 回測、後處理分析、網頁系統與其自動化測試的程式碼。"));
body.push(L("(2)", "實驗執行與結果核對:依指示執行實驗、把結果寫入結果檔,並核對不同程式之間的數字一致(例如後處理的原始列與回測結果檔相同、網頁正式模型重現研究結果)。"));
body.push(L("(3)", "圖表與報告整理:繪製混淆矩陣、資產曲線與個案圖,整理簡報與本報告的初稿。"));
body.push(L("(4)", "多個 session 分工:以一個監督用的 session 接收與轉達指令,再由不同的 session 分別負責研究分支、網頁系統分支與報告分支,彼此以訊息交接。"));
body.push(P("人工決策與檢查的部分包括:研究方向與題目的決定;標籤定義、改用規則候選加 AE + OC-SVM、加入 Stacking 對照等方法上的選擇;股票池的選擇與剔除低波動股;回測規則(只做多、前 3 檔、持有 5 天、成本)的確認;要求不改模型、不調參數的後處理分析;以及報告呈現方式與最終內容的決定。AI 工具產生的程式與數字,均經人工閱讀結果、對照結果檔與圖表後才採用;本報告中無法確認的文獻資訊均標示【待補】或【待確認】。"));

// ───── 參考文獻 ─────
body.push(H1("參考文獻"));
const REF = (n, parts) => new Paragraph({ alignment: AlignmentType.LEFT, spacing: { ...BODY_LINE, after: 80 }, indent: { left: 600, hanging: 600 },
  children: [run(`[${n}]`), new TextRun({ children: [new Tab()], font: F }), ...runs(parts)], tabStops: [{ type: TabStopType.LEFT, position: 600 }] });
const it = (t) => [t, { italics: true }];
body.push(REF(1, ["郭念慈、李俊宏,【待補:論文題目/出處】,逢甲大學資訊工程學系。"]));
body.push(REF(2, ["G. E. Hinton and R. R. Salakhutdinov, \"Reducing the dimensionality of data with neural networks,\" ", it("Science"), ", vol. 313, no. 5786, pp. 504–507, Jul. 2006."]));
body.push(REF(3, ["D. P. Kingma and J. Ba, \"Adam: A method for stochastic optimization,\" ", it("Proceedings of the 3rd International Conference on Learning Representations (ICLR)"), ", San Diego, CA, USA, May 2015."]));
body.push(REF(4, ["B. Schölkopf, J. C. Platt, J. Shawe-Taylor, A. J. Smola, and R. C. Williamson, \"Estimating the support of a high-dimensional distribution,\" ", it("Neural Computation"), ", vol. 13, no. 7, pp. 1443–1471, Jul. 2001."]));
body.push(REF(5, ["D. H. Wolpert, \"Stacked generalization,\" ", it("Neural Networks"), ", vol. 5, no. 2, pp. 241–259, 1992."]));
body.push(REF(6, ["D. R. Cox, \"The regression analysis of binary sequences,\" ", it("Journal of the Royal Statistical Society: Series B (Methodological)"), ", vol. 20, no. 2, pp. 215–242, 1958."]));
body.push(REF(7, ["C. M. Bishop, ", it("Pattern Recognition and Machine Learning"), ". New York: Springer, 2006."]));
body.push(REF(8, ["C. Bergmeir and J. M. Benítez, \"On the use of cross-validation for time series predictor evaluation,\" ", it("Information Sciences"), ", vol. 191, pp. 192–213, May 2012."]));
body.push(REF(9, ["R. Pardo, ", it("The Evaluation and Optimization of Trading Strategies"), " (2nd ed.). Hoboken, NJ: John Wiley & Sons, 2008."]));
body.push(REF(10, ["M. Sokolova and G. Lapalme, \"A systematic analysis of performance measures for classification tasks,\" ", it("Information Processing & Management"), ", vol. 45, no. 4, pp. 427–437, Jul. 2009."]));
body.push(REF(11, ["F. Pedregosa et al., \"Scikit-learn: Machine learning in Python,\" ", it("Journal of Machine Learning Research"), ", vol. 12, pp. 2825–2830, 2011."]));
body.push(REF(12, ["A. Paszke et al., \"PyTorch: An imperative style, high-performance deep learning library,\" ", it("Advances in Neural Information Processing Systems 32 (NeurIPS 2019)"), ", pp. 8024–8035, Dec. 2019."]));
body.push(REF(13, ["R. Aroussi, yfinance: Download market data from Yahoo! Finance's API. https://github.com/ranaroussi/yfinance(存取日期:2026 年 11 月 9 日)"]));
body.push(REF(14, ["Anthropic, Claude Code 說明文件. https://code.claude.com/docs(存取日期:2026 年 11 月 9 日)"]));

// ───── 附錄 ─────
body.push(H1("附錄"));
body.push(H2("附錄一 程式模組與執行指令"));
body.push(P("研究程式位於分支 claude/kline-peak-predict-tool 的 method_kline_peak/,網頁系統位於分支 claude/kline-peak-web-app 的 method_kline_peak/web/。以下指令皆在專題根目錄執行;未列出的參數使用預設值。"));
body.push(...TAB("附表 1 研究程式模組", ["模組", "用途"], [
  ["peak_labels.py、paper_aeocsvm.py", "11 日視窗標籤、規則基準、評估指標"],
  ["mainline.py", "主軸:規則候選 + AE + OC-SVM;股票池載入與低波動股剔除"],
  ["ae_ocsvm.py", "相似度權重與 AE + OC-SVM 的訓練"],
  ["stacking.py", "Stacking:第一層兩組 AE + OC-SVM、第二層邏輯迴歸"],
  ["walkforward.py", "逐年 walk-forward 的訓練與訊號來源"],
  ["backtest_top3.py", "只做多前 3 檔回測"],
  ["postproc_signals.py、confirm_signals.py", "後處理與等確認分析"],
  ["report/confusion_2024_2026.py", "2024–2026 混淆矩陣圖與數字"],
  ["report/stock_outputs.py、report/confusion_stock.py", "單一股票的每日判斷圖與混淆矩陣"],
  ["report/prob_cut.py", "Stacking 機率門檻分析"],
  ["report/lohi_compare.py、report/lohi_portfolio.py", "低點進、高點出(單一股票、多檔組合)"],
  ["report/lr_example.py", "邏輯迴歸計算實例"],
  ["web/run.py", "網頁系統:每日批次、回放、重訓、產生網頁資料、開啟網頁"],
], [2.8, 4.5], { size: 18, align: [AlignmentType.LEFT, AlignmentType.LEFT] }));
body.push(...TAB("附表 2 主要執行指令", ["用途", "指令"], [
  ["主軸實驗", "python method_kline_peak/mainline.py --tag base"],
  ["Stacking 實驗", "python method_kline_peak/stacking.py"],
  ["TW200 回測", "python method_kline_peak/backtest_top3.py --pool tw200 --short-slots 0"],
  ["後處理分析", "python method_kline_peak/postproc_signals.py"],
  ["等確認分析", "python method_kline_peak/confirm_signals.py"],
  ["機率門檻分析", "python method_kline_peak/report/prob_cut.py"],
  ["南電後處理圖", "python method_kline_peak/report/compare_postproc.py"],
  ["低點進高點出", "python method_kline_peak/report/lohi_compare.py\npython method_kline_peak/report/lohi_portfolio.py"],
  ["邏輯迴歸實例", "python method_kline_peak/report/lr_example.py"],
  ["網頁:第一次回放", "python method_kline_peak/web/run.py replay --start 2026-01-01"],
  ["網頁:每日批次並開網頁", "python method_kline_peak/web/run.py start"],
  ["網頁系統測試", "python -m pytest method_kline_peak/web/tests"],
], [1.9, 5.4], { size: 18, align: [AlignmentType.LEFT, AlignmentType.LEFT] }));
body.push(H2("附錄二 網頁系統各頁截圖"));
body.push(P("以下截圖為網頁系統展示版的真實畫面(資料至 2026 年 9 月 10 日),部分頁面只取上半部。"));
body.push(...FIG("appB_today.png", 3.9, "圖 A.1 今日判斷(桌機)"));
body.push(...FIG("appB_today_mobile.png", 2.6, "圖 A.2 今日判斷(手機,上半部)"));
body.push(...FIG("appB_search.png", 5.4, "圖 A.3 個股查詢:代號自動完成"));
body.push(...FIG("appB_stock_pool.png", 4.6, "圖 A.4 個股查詢:池內股票(8454 富邦媒)"));
body.push(...FIG("appB_stock_outpool.png", 5.0, "圖 A.5 個股查詢:池外股票(2618 長榮航,上半部)"));
body.push(...FIG("appB_stock_lowvol.png", 5.0, "圖 A.6 個股查詢:低波動股(2412 中華電,上半部)"));
body.push(...FIG("appB_track.png", 5.0, "圖 A.7 成績追蹤(上半部)"));
body.push(...FIG("appB_findings.png", 5.4, "圖 A.8 研究發現(結論卡片)"));
body.push(...FIG("appB_about.png", 4.8, "圖 A.9 方法與說明(節錄)"));

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
