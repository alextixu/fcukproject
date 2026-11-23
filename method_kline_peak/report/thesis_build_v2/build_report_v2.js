// 專題研究報告 v2(逢甲大學資訊工程學系 大學部專題研究報告格式規範;方法與數字同 final 分支、簡報 v2、海報 v2)
// 數字全部讀 data.json(由 figs_v2.py 從 final 分支 results/ 的 json 產生);不跑實驗。
// 用法: node build_report_v2.js <data.json 與 fig/ 所在目錄> <輸出 docx>
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

// ───────── 數字(全部來自 data.json,即 final 分支 results/ 的 json) ─────────
const Y = ["2024", "2025", "2026"];
const YL = { "2024": "2024", "2025": "2025", "2026": "2026(1–9 月)" };
const YD = D.years, TT = D.total, RU = D.agg_rule, MA = D.agg_main, BT = D.bt, TM = D.timing, MK = D.mtk;
const p1 = (v) => `${Number(v).toFixed(1)}%`;
const p2 = (v) => `${Number(v).toFixed(2)}%`;
const n0 = (v) => Number(v).toLocaleString("en-US");
const sg = (v) => `${v > 0 ? "+" : "−"}${Math.abs(Number(v)).toFixed(2)}%`;
const mf = (y) => YD[y].m.macro_f1.toFixed(2);
const RAND = D.random_pct;                       // 三年合計:真高、真低點占全部股票日的平均比例
const RATIO = MA.both_prec / RAND;
const TRAIN = TM["訓練"], DAY = TM["一天的判斷"], MEM = TM["記憶體_RSS峰值_MB"], ENV = TM["環境"];
const ENVS = `Intel Xeon 2.10 GHz、${ENV["邏輯核心數"]} 個邏輯核心、只用 CPU(Python ${ENV.python.split(".").slice(0, 2).join(".")}、PyTorch ${ENV.torch.split("+")[0]})`;

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
  coverLine("　　　呂偉湘 D1286314", 22),
  ...EMPTY(6),
  coverLine("中 華 民 國 一 百 一 十 五 年 十 一 月", 20),
];

// ══════════════════════════ 前言(羅馬數字頁碼) ══════════════════════════
const front = [];
front.push(H1("誌謝", { first: true }));
front.push(P("本專題得以完成,首先感謝指導教授李俊宏老師一路以來的指導。從研究題目的方向、標籤的定義到實驗結果的解讀,老師在每個關鍵的轉折點都給了明確的方向,也提醒我們以嚴謹、誠實的態度對待實驗結果;也感謝系上提供的學習環境,以及在專題過程中給予意見與協助的同學與家人。專題中仍有許多不足之處,尚祈各位先進不吝指正。"));
front.push(new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: 480, ...BODY_LINE }, children: [run("郭家齊、呂偉湘 謹誌")] }));
front.push(new Paragraph({ alignment: AlignmentType.RIGHT, spacing: BODY_LINE, children: [run("中華民國一百一十五年十一月")] }));

front.push(H1("摘要"));
front.push(P("台股每天的局部高點、低點各只占約 7%,投資人每天逐檔看盤相當費時。本研究以台股日K線辨識「11 天局部高低點」:以第 t 日為中心、前後各 5 個交易日的收盤價為視窗,t 日收盤價為視窗內最高者標為高點、最低者標為低點,其餘為非極值。系統在 t 日收盤後判斷,只使用 t−5 至 t 共 6 根 K 線。"));
front.push(P(`本系統分兩步:先以規則篩出候選日(t 日收盤是最近 6 天的最高或最低),其他日子直接判為非極值;再把候選日的 6 根 K 線轉成 29 維型態特徵,高點、低點各以一組自編碼器(29 → 16 維)與單類支持向量機(One-Class SVM)判斷「像不像過去真正的高點或低點」,像才判為高點或低點。資料為 TW200 剔除低波動股後的 ${D.n_stocks} 檔股票,以 walk-forward 方式逐年驗證:測哪一年就用之前 4 年訓練,測試期間為 2024 年至 2026 年 9 月。`));
front.push(P(`三年合計,本系統找到 ${p1(MA.both_rec)} 的真轉折點(約 8 成),命中率 ${p1(MA.both_prec)},約為隨機猜(${p1(RAND)})的 ${Math.round(RATIO)} 倍;macro-F1 三年依序為 ${Y.map(mf).join("%、")}%,且高低點從未判反,這是規則候選在設計上的保證。與「只用規則」比較,成績主要來自規則:自編碼器與單類支持向量機讓判出的訊號少約兩成(${p1(D.fewer_signals_pct)}),命中率持平,找到率則由 100% 降到 ${p1(MA.both_rec)}。以 2024–2025 年回測 ${BT.n} 種只做多的進出方式,扣除交易成本後全部虧損,同期 0050 買進持有為 ${sg(BT.etf0050)};因判出的訊號約七成不是真轉折,本系統定位為看盤輔助,而非自動交易訊號。本研究並實作網頁系統,提供今日判斷、個股查詢與成績追蹤,其判斷與研究結果逐列核對一致。`));
front.push(new Paragraph({ spacing: { before: 240, ...BODY_LINE }, indent: { left: 480 },
  children: [run("關鍵詞:K線型態、局部高低點、自編碼器、單類支持向量機、walk-forward、看盤輔助", { bold: true })] }));

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
body.push(P("技術分析以價格與成交量的歷史型態推估後續走勢,其中 K 線(蠟燭圖)以開、高、低、收四個價格呈現每日的多空變化,是台股投資人最常使用的工具之一。對短線操作而言,能否在轉折點附近注意到變化,往往比判斷長期方向更直接:若能在局部低點附近留意買點、在局部高點附近留意賣點,就能掌握一段波動。"));
body.push(P("然而轉折點必須等到之後的價格走出來才能確認。本研究以 11 天的收盤價視窗定義局部高點與局部低點:t 日收盤是前後 5 天的最高即為高點、最低即為低點。t 日收盤時無法知道之後 5 天的價格,因此需要從 t 日以前的 K 線型態判斷當天是否可能是轉折點。"));
body.push(H2("1.2 研究動機"));
body.push(P("局部高點與局部低點在所有交易日中各只占約 7%(見 4.1.2 節),大多數日子都是非極值;投資人若要每天逐檔檢查 K 線,所需時間相當可觀。傳統技術指標(例如 KD、RSI)通常要等轉折發生幾天後才反應。如果能在收盤當天就從 K 線型態中挑出「可能是高點或低點」的股票,並把每一次判斷存檔、事後對答案,就能成為投資人看盤時的輔助工具。"));
body.push(H2("1.3 研究目的"));
body.push(P("本研究的目的如下:"));
body.push(L("(1)", "以規則篩出候選日,並以自編碼器與單類支持向量機分別學習真高點、真低點的 K 線型態,判斷候選日是否像過去的真轉折點。"));
body.push(L("(2)", "以 walk-forward 方式逐年評估本系統的分類成績,並與隨機猜測、只用規則兩種基準比較,釐清成績的來源。"));
body.push(L("(3)", "以聯發科(2454)2025 年為例說明單一股票上的判斷,並以回測檢驗訊號能否直接用於交易。"));
body.push(L("(4)", "依研究結果實作網頁系統,讓使用者查詢每日判斷與歷史成績,作為看盤輔助。"));
body.push(H2("1.4 研究範圍"));
body.push(L("(1)", "市場:台灣股票市場上市股票的日K線(還原權息價格)。"));
body.push(L("(2)", `股票池:TW200 清單中有資料的 216 檔,剔除 ${D.n_excluded} 檔低波動股後的 ${D.n_stocks} 檔(剔除規則見 4.1.1 節)。`));
body.push(L("(3)", "資料期間:2016 年 1 月 1 日至 2026 年 9 月 11 日的日K線。"));
body.push(L("(4)", "測試期間:2024 年、2025 年與 2026 年 1 月至 9 月 11 日,每一年都只用該年以前的資料訓練。"));
body.push(L("(5)", "只使用日線;回測只做多,期間為 2024 至 2025 年。"));
body.push(H2("1.5 研究方法"));
body.push(P("本研究先依 11 天視窗的定義為每個交易日貼上高點、低點或非極值的標籤;判斷時先以「t 日收盤是最近 6 天最高或最低」的規則篩出候選日,再把候選日的 6 根 K 線轉成 29 維型態特徵,以自編碼器壓縮到 16 維、以單類支持向量機判斷是否像過去的真轉折點。評估採 walk-forward,以混淆矩陣、macro-F1、找到率(recall)與命中率(precision)衡量分類成績,並與隨機、只用規則比較;再以聯發科為例觀察單一股票上的判斷、以回測檢驗交易可行性、量測執行時間,最後將模型實作成網頁系統。"));
body.push(H2("1.6 研究流程"));
body.push(P("研究流程如圖 1.1 所示。"));
body.push(...FIG("fig1_1_flow.png", 4.6, "圖 1.1 研究流程"));
body.push(H2("1.7 章節結構"));
body.push(P("第一章說明研究背景、動機、目的、範圍與流程。第二章回顧本研究使用的文獻與方法。第三章定義問題與標籤,說明規則候選、自編碼器與單類支持向量機的理論基礎,以及特徵、訓練步驟與 walk-forward 的設計。第四章為實證分析,包含資料分析、混淆矩陣與分類成績、與基準的比較、聯發科個案、回測、實測時間與網頁系統評估。第五章為結論、研究限制、成果、貢獻、後續研究方向,以及專題過程中導入的 AI 工具。"));

// ───── 第二章 ─────
body.push(H1("第二章 相關文獻回顧"));
body.push(H2("2.1 局部高低點的定義與規則候選"));
body.push(P("本研究以第 t 日收盤價 C_t 與前後各 5 日構成的 11 日視窗定義標籤:C_t 為視窗內最高者為高點、最低者為低點,其餘為非極值(正式定義見 3.1 節)。由定義可知,真高點的 t 日收盤必然也是 t−5 至 t 這 6 天的最高(真低點同理),這是 t 日收盤時就能檢查的必要條件。本研究以此條件作為規則,先篩出候選日,再由模型分辨候選中的真假(見 3.2 節)。"));
body.push(H2("2.2 自編碼器"));
body.push(P("自編碼器(Autoencoder, AE)由編碼器與解碼器組成,以重建輸入為目標進行訓練,中間的低維表示可視為資料的壓縮特徵。Hinton 與 Salakhutdinov [1] 證明以神經網路學習的低維編碼比主成分分析更能保留資料結構。本研究採用一層線性編碼器(29 → 16 維),只以真高點(或真低點)訓練;訓練使用 Adam 最佳化器 [2]。"));
body.push(H2("2.3 單類支持向量機"));
body.push(P("單類支持向量機(One-Class SVM, OC-SVM)由 Schölkopf 等人 [3] 提出,只用單一類別的樣本學習一個能涵蓋大部分樣本的區域,常用於異常偵測。參數 ν 為訓練樣本落在區域外比例的上界,也是支持向量比例的下界;決策函數大於 0 表示落在區域內。本研究分別以真高點、真低點的樣本各訓練一個 OC-SVM,判斷候選日是否「像」過去的真轉折點。"));
body.push(H2("2.4 時間序列的驗證方式"));
body.push(P("時間序列資料前後相關,若隨機切分訓練與測試資料,模型可能看到測試期以後的資訊。Bergmeir 與 Benítez [4] 討論時間序列預測的交叉驗證方式,指出保留時間順序的評估較能反映實際使用情況。本研究採用 walk-forward 的方式,以「用過去一段期間訓練、在下一段期間測試,再整體往後移動」重複評估:每個測試年都只用之前 4 年的資料訓練,並剔除訓練期最後 5 個交易日,因為這些日子的標籤需要看到測試年的價格。"));
body.push(H2("2.5 分類評估指標"));
body.push(P("三分類中非極值占大多數,單看準確率會被多數類主導。Sokolova 與 Lapalme [5] 整理了多類別分類的評估指標,其中 macro-F1 為各類 F1 的平均,對每一類一視同仁。本研究以 macro-F1 為整體指標,並分別報告高點、低點的找到率(recall,真轉折點中被判出的比例)與命中率(precision,判出的訊號中真的是轉折點的比例)。"));
body.push(H2("2.6 實作工具"));
body.push(P("本研究以 scikit-learn [6] 實作標準化與單類支持向量機,以 PyTorch [7] 實作自編碼器,日K線以 yfinance 套件 [8] 取得。"));
body.push(H2("2.7 本研究的做法"));
body.push(P("本研究在 2.1 節的標籤定義上,結合 2.2 至 2.6 節的方法,做法如下:(1)以規則篩出候選日,不是候選的日子直接判為非極值;(2)高點、低點各以一組 AE + OC-SVM 分辨候選日的真假;(3)以 walk-forward 在 2024 至 2026 三個測試年評估 168 檔股票的分類成績,並與隨機猜測、只用規則比較;(4)以個案、回測與實測時間檢驗系統的用途與限制;(5)將模型實作為網頁系統,並核對系統輸出與研究結果一致。"));

// ───── 第三章 ─────
body.push(H1("第三章 論文主體"));
body.push(H2("3.1 研究方法:問題定義與標籤"));
body.push(P(["令第 t 個交易日的收盤價為 ", I("C"), SUB("t"), ",以 t 為中心、前後各 5 日構成 11 日視窗,t 為視窗的第 6 天:"]));
body.push(EQ([I("W"), SUB("t"), " = { ", I("C"), SUB("t−5"), ", ", I("C"), SUB("t−4"), ", …, ", I("C"), SUB("t+5"), " }"], 1));
body.push(P(["標籤 ", I("y"), SUB("t"), " 定義如下:"]));
body.push(EQ([I("y"), SUB("t"), " = 高點,若 ", I("C"), SUB("t"), " = max ", I("W"), SUB("t"), ";  ", I("y"), SUB("t"), " = 低點,若 ", I("C"), SUB("t"), " = min ", I("W"), SUB("t")], 2));
body.push(P("其餘日子為非極值。與他日並列最高(最低)者也標為高點(低點);視窗內收盤價全部相同時為非極值;資料頭尾不足 11 天的日子不納入。由 Eq. (2) 可知,標籤需要 t+1 至 t+5 的價格,只能用於訓練與對答案;系統在 t 日收盤後判斷,只能使用 t 日以前的資料。圖 3.1 為三種標籤的示意。"));
body.push(...FIG("fig3_1_label.png", 5.6, "圖 3.1 高點、低點與非極值的標籤示意"));

body.push(H2("3.2 規則候選"));
body.push(P(["以最近 6 天的收盤價 ", I("V"), SUB("t"), " = { ", I("C"), SUB("t−5"), ", …, ", I("C"), SUB("t"), " } 定義候選:"]));
body.push(EQ(["高點候選:", I("C"), SUB("t"), " = max ", I("V"), SUB("t"), " 且 ", I("C"), SUB("t"), " ≠ min ", I("V"), SUB("t"), ";  低點候選:", I("C"), SUB("t"), " = min ", I("V"), SUB("t"), " 且 ", I("C"), SUB("t"), " ≠ max ", I("V"), SUB("t")], 3));
body.push(P("不是候選的日子一律判為非極值。由於 V_t ⊂ W_t,真高點必為高點候選、真低點必為低點候選;唯一的例外是 6 天收盤全部相同,此時同時是最高與最低,不列為候選。本系統判高點的日子一定是高點候選、判低點的日子一定是低點候選,而高點候選與低點候選互斥,因此真低點不可能被判成高點、真高點也不可能被判成低點。第四章「高低點判反為 0」即來自這個設計上的保證,並非模型學到的結果。"));

body.push(H2("3.3 理論基礎"));
body.push(H3("3.3.1 自編碼器"));
body.push(P(["給定標準化後的特徵向量 ", I("x"), " ∈ R", SUP("29"), ",本研究使用的線性自編碼器為:"]));
body.push(EQ([I("z"), " = ", I("W"), SUB("e"), I("x"), " + ", I("b"), SUB("e"), ",  ", I("x̂"), " = ", I("W"), SUB("d"), I("z"), " + ", I("b"), SUB("d")], 4));
body.push(P(["其中 ", I("z"), " ∈ R", SUP("16"), " 為潛在表示。訓練目標為最小化平均平方重建誤差:"]));
body.push(EQ([I("L"), " = (1/", I("N"), ") Σ", SUB("i"), " ‖ ", I("x"), SUB("i"), " − ", I("x̂"), SUB("i"), " ‖", SUP("2")], 5));
body.push(P("訓練使用 Adam [2](學習率 0.001、權重衰減 0.00001)、餘弦退火學習率、批次大小 256,共 60 輪;高點、低點各訓練一個,只用該類的真轉折點。"));
body.push(H3("3.3.2 單類支持向量機的決策函數"));
body.push(P(["OC-SVM [3] 在潛在空間中以核函數學習一個涵蓋訓練樣本的區域,其決策函數為:"]));
body.push(EQ([I("f"), "(", I("z"), ") = Σ", SUB("i"), " α", SUB("i"), " ", I("K"), "(", I("z"), SUB("i"), ", ", I("z"), ") − ρ"], 6));
body.push(EQ([I("K"), "(", I("z"), SUB("i"), ", ", I("z"), ") = exp(−γ ‖ ", I("z"), SUB("i"), " − ", I("z"), " ‖", SUP("2"), ")"], 7));
body.push(P("其中 α_i 為支持向量的係數,ρ 為偏移量,γ 為 RBF 核參數(本研究使用 scikit-learn 的 scale 設定),ν 設為 0.1。候選日的 f(z) > 0 表示落在區域內,即「像過去的真轉折點」,判為高點(低點);否則改判為非極值。f(z) 同時作為分數,網頁系統以此排序。"));
body.push(H3("3.3.3 相似樣本權重"));
body.push(P(["同一段漲跌中,真轉折點與前後幾天的候選日型態往往相似。為了讓型態較具代表性的真轉折點有較大的影響,訓練 OC-SVM 時每個真轉折點 ", I("i"), " 另給一個權重:在標準化後的 29 維空間中,找出與它歐氏距離不超過 3.0 的其他候選日集合 ", I("N"), SUB("i"), ",權重為其中同為真轉折點的比例:"]));
body.push(EQ([I("w"), SUB("i"), " = max( |{ ", I("j"), " ∈ ", I("N"), SUB("i"), " : ", I("y"), SUB("j"), " = ", I("c"), " }| / |", I("N"), SUB("i"), "| , 0.001 )"], 8));
body.push(P("其中 c 為該組的類別(高點或低點);若 N_i 為空,比例視為 0,再取下限 0.001。權重再除以平均值後傳入 OC-SVM。"));

body.push(H2("3.4 方法架構"));
body.push(H3("3.4.1 特徵"));
body.push(P(["特徵只使用 t−5 至 t 共 6 根 K 線,全部取對數並以 t 日收盤為基準,因此與股價高低無關,不同股票可以共用一組模型。對 k = 0, 1, …, 5:"]));
body.push(EQ(["ln(", I("O"), SUB("t−k"), " / ", I("C"), SUB("t"), "), ln(", I("H"), SUB("t−k"), " / ", I("C"), SUB("t"), "), ln(", I("L"), SUB("t−k"), " / ", I("C"), SUB("t"), "), ln(", I("C"), SUB("t−k"), " / ", I("C"), SUB("t"), "), ln(", I("V"), SUB("t−k"), " / ", I("V̄"), SUB("t"), ")"], 9));
body.push(P(["其中 ", I("V̄"), SUB("t"), " 為到 t 日為止的 10 日均量;t 日收盤本身恆為 0,不計入。特徵的組成如表 3.1,共 29 維。特徵以訓練期候選日的中位數補缺值、標準化,再截斷在 ±5 之間。圖 3.2 與圖 3.3 以聯發科 2025 年 2 月 26 日為例,左為 6 根 K 線(價格以相對 t 日收盤的百分比表示),右為對應的 29 個數字(價格為對數比 × 100,量為對數比)。"]));
body.push(...TAB("表 3.1 29 維型態特徵", ["項目", "天數", "個數"], [
  ["開、高、低 ÷ t 日收盤(取對數)", "t−5 至 t", "18"],
  ["收盤 ÷ t 日收盤(取對數)", "t−5 至 t−1", "5"],
  ["成交量 ÷ 10 日均量(取對數)", "t−5 至 t", "6"],
  { opt: { bold: true }, cells: ["合計", "", "29"] },
], [3.6, 1.6, 1.0], { size: 22 }));
body.push(...FIG("fig3_3a_feat_kline.png", 3.8, "圖 3.2 聯發科 2025-02-26 的 t−5 至 t 六根 K 線"));
body.push(...FIG("fig3_3b_feat_grid.png", 4.4, "圖 3.3 聯發科 2025-02-26 的 29 個型態特徵"));
body.push(H3("3.4.2 訓練與判斷步驟"));
body.push(P("本系統的判斷流程如圖 3.4。高點、低點各有一組模型,訓練與判斷步驟如下(以高點為例,低點相同):"));
body.push(L("(1)", "候選:在訓練期中找出全部高點候選(Eq. (3)),計算 29 維特徵。"));
body.push(L("(2)", "標準化:以訓練期候選日的特徵計算中位數(補缺值)與標準化參數,標準化後截斷在 ±5 之間;測試期使用同一組參數。"));
body.push(L("(3)", "權重:依 Eq. (8) 計算每個真高點的相似樣本權重。"));
body.push(L("(4)", "自編碼器:只用真高點訓練 29 → 16 的線性自編碼器(Eq. (4)、(5))。"));
body.push(L("(5)", "OC-SVM:以真高點的 16 維編碼與權重訓練 RBF 核、ν = 0.1 的 OC-SVM(Eq. (6)、(7))。"));
body.push(L("(6)", "判斷:測試期的每一天先檢查是否為高點候選;是候選才計算特徵、經自編碼器編碼,f(z) > 0 判為高點,否則判為非極值;不是任何候選的日子判為非極值。"));
body.push(...FIG("fig3_2_arch.png", 5.75, "圖 3.4 本系統的判斷流程"));
body.push(H3("3.4.3 walk-forward 訓練期間"));
body.push(P("所有股票一起訓練一組模型(高點、低點各一組)。每個測試年都只用之前 4 年的資料訓練,並剔除訓練期最後 5 個交易日;亂數種子固定為 42,訓練時使用全部真高低點(不設漲跌幅門檻)。各測試年的期間如表 3.2 與圖 3.5。"));
body.push(...TAB("表 3.2 walk-forward 訓練與測試期間", ["測試年", "訓練期間", "測試期間"], [
  ["2024", "2020–2023", "2024 年全年"],
  ["2025", "2021–2024", "2025 年全年"],
  ["2026", "2022–2025", "2026 年 1 月至 9 月 11 日"],
], [1.2, 2.0, 2.8], { size: 22, note: "註:訓練期最後 5 個交易日剔除,因為其標籤需要看到測試年的價格。" }));
body.push(...FIG("fig3_4_walkforward.png", 5.6, "圖 3.5 walk-forward 時間軸"));

// ───── 第四章 ─────
body.push(H1("第四章 實證分析"));
body.push(H2("4.1 資料分析"));
body.push(H3("4.1.1 資料來源與股票池"));
body.push(P(`日K線取自 Yahoo Finance(透過 yfinance 套件 [8])的還原權息價格,期間為 2016 年 1 月 1 日至 2026 年 9 月 11 日。股票池使用 TW200 候選清單,有資料者 216 檔。部分股票的每日漲跌幅很小,標籤多半只是小起伏,因此本研究剔除低波動股:計算 2020 年 1 月以後每日收盤漲跌幅絕對值的中位數,低於 0.725% 者剔除,共剔除 ${D.n_excluded} 檔,剩 ${D.n_stocks} 檔(表 4.1)。`));
body.push(...TAB("表 4.1 股票池", ["股票池", "有資料", "剔除低波動", "使用檔數"], [
  ["TW200", "216", String(D.n_excluded), String(D.n_stocks)],
], [2.2, 1.4, 1.6, 1.4], { size: 22 }));
body.push(H3("4.1.2 標籤比例"));
body.push(P(`表 4.2 為各測試年的標籤分布(個數取自混淆矩陣的列加總)。三年合計共 ${n0(TT.n)} 個股票日,高點、低點各約占 7%,非極值約占 86%,類別相當不平衡;隨機猜的命中率約等於該類的比例,因此本研究以約 ${p1(RAND)} 作為隨機基準。`));
const labRows = Y.map((y) => {
  const l = YD[y].labels, n = YD[y].n;
  return [YL[y], n0(n), `${n0(l[0])}(${(l[0] / n * 100).toFixed(2)}%)`, `${n0(l[1])}(${(l[1] / n * 100).toFixed(2)}%)`, `${n0(l[2])}(${(l[2] / n * 100).toFixed(2)}%)`];
});
{ const l = TT.labels, n = TT.n;
  labRows.push({ opt: { bold: true }, cells: ["三年合計", n0(n), `${n0(l[0])}(${(l[0] / n * 100).toFixed(2)}%)`, `${n0(l[1])}(${(l[1] / n * 100).toFixed(2)}%)`, `${n0(l[2])}(${(l[2] / n * 100).toFixed(2)}%)`] }); }
body.push(...TAB("表 4.2 測試期的標籤分布(股票日數)", ["測試年", "總數", "低點", "非極值", "高點"], labRows, [1.9, 1.3, 1.8, 1.9, 1.8], { size: 20 }));
body.push(H3("4.1.3 規則候選的範圍"));
body.push(P(`三年合計,規則候選共 ${n0(RU["判高低合計天數"])} 個股票日(低點候選 ${n0(RU["低點"]["判"])}、高點候選 ${n0(RU["高點"]["判"])}),其餘 ${p1(D.rule_filtered_pct)} 的股票日不是候選,直接判為非極值。由 3.2 節可知,候選涵蓋全部的真高點與真低點,因此模型只需在約一半的日子中分辨真假候選;候選中真轉折點的比例(即只用規則的命中率)為 ${p1(RU.both_prec)}。`));

body.push(H2("4.2 統計分析"));
body.push(H3("4.2.1 混淆矩陣"));
body.push(P("圖 4.1 為本系統在 2024 至 2026 年逐年的混淆矩陣,圖 4.2 為三年合計;列為真實標籤、欄為判斷,每格為個數與該列的比例,橘框為高低點判反的兩格。表 4.3 整理逐年與三年合計的分類成績。"));
body.push(...FIG("fig4_1_conf_years.png", 5.9, "圖 4.1 逐年混淆矩陣(2024–2026)"));
body.push(...FIG("fig4_2_conf_total.png", 3.3, "圖 4.2 三年合計混淆矩陣"));
const mRow = (name, v, rev, o) => {
  const c = [name, v.macro_f1.toFixed(2), p1(v["低點"].rec), p1(v["高點"].rec), p1(v["低點"].prec), p1(v["高點"].prec), String(rev)];
  return o ? { opt: o, cells: c } : c;
};
const mRows = Y.map((y) => mRow(YL[y], YD[y].m, YD[y].reversed));
mRows.push(mRow("三年合計", TT.m, TT.reversed, { bold: true }));
body.push(...TAB("表 4.3 逐年分類成績", ["測試年", "macro-F1\n(%)", "找到率\n低點", "找到率\n高點", "命中率\n低點", "命中率\n高點", "高低點\n判反"], mRows,
  [1.6, 1.1, 1.0, 1.0, 1.0, 1.0, 0.9], { size: 20, note: "註:高低點判反 = 真低點判成高點與真高點判成低點的個數合計,由規則候選保證為 0(3.2 節);三年合計由三個混淆矩陣相加後計算。" }));
body.push(P(`由圖 4.1、圖 4.2 與表 4.3 可得到三點觀察:第一,三年合計找到 ${p1(TT.m["低點"].rec)} 的真低點與 ${p1(TT.m["高點"].rec)} 的真高點,合計 ${p1(MA.both_rec)},約 8 成;2026 年的找到率較低(${p1(YD["2026"].m["低點"].rec)} 與 ${p1(YD["2026"].m["高點"].rec)})。第二,判低點、判高點的命中率約為三成(三年合計 ${p1(TT.m["低點"].prec)} 與 ${p1(TT.m["高點"].prec)}),也就是判出的訊號約七成其實是非極值;錯誤全部發生在轉折點與非極值之間。第三,macro-F1 在三個測試年之間相當穩定(${Y.map(mf).join("%、")}%),高低點判反都是 0。`));
body.push(H3("4.2.2 與隨機、只用規則比較"));
body.push(P(`為釐清成績的來源,本研究以兩個基準比較:隨機猜(依真實類別占比隨機判斷,找到率與命中率的期望值都等於占比,macro-F1 為 33.33%),以及只用規則(把規則候選直接當成判斷)。表 4.4 為三年合計的比較,圖 4.3 為找到率與命中率的對照。`));
const cmpRow = (name, v, f1) => [name, f1, p1(v["低點"]["找到率"]), p1(v["高點"]["找到率"]), p1(v["低點"]["命中率"]), p1(v["高點"]["命中率"]), n0(v["判高低合計天數"])];
const ruleF1 = (() => { // 三年合計的只用規則 macro-F1:由 baseline 逐年個數相加後重算非極值類
  const n = TT.n, lab = TT.labels;
  const f = (tp, pr, tr) => { const p = tp / pr, r = tp / tr; return 2 * p * r / (p + r); };
  const lo = RU["低點"], hi = RU["高點"];
  const predFlat = n - lo["判"] - hi["判"];
  const tpFlat = predFlat;                        // 規則判非極值的日子全部是真非極值(候選涵蓋全部真高低點)
  return ((f(lo["對"], lo["判"], lo["真"]) + f(hi["對"], hi["判"], hi["真"]) + f(tpFlat, predFlat, lab[1])) / 3 * 100).toFixed(2);
})();
body.push(...TAB("表 4.4 三年合計:隨機、只用規則與本系統", ["方法", "macro-F1\n(%)", "找到率\n低點", "找到率\n高點", "命中率\n低點", "命中率\n高點", "判高低\n天數"], [
  ["隨機猜", "33.33", p1(TT.labels[0] / TT.n * 100), p1(TT.labels[2] / TT.n * 100), p1(TT.labels[0] / TT.n * 100), p1(TT.labels[2] / TT.n * 100), "—"],
  cmpRow("只用規則", RU, ruleF1),
  { opt: { bold: true }, cells: cmpRow("本系統", MA, TT.m.macro_f1.toFixed(2)) },
], [1.4, 1.1, 1.0, 1.0, 1.0, 1.0, 1.2], { size: 20, note: "註:隨機猜的找到率與命中率為該類占全部股票日的比例;只用規則與本系統的三年合計由逐年個數相加後計算。" }));
body.push(...FIG("fig4_3_compare.png", 5.75, "圖 4.3 找到率與命中率:隨機猜、只用規則與本系統(三年合計)"));
body.push(P(`由表 4.4 與圖 4.3 可見,本系統與只用規則的命中率幾乎相同(${p1(MA.both_prec)} 與 ${p1(RU.both_prec)}),兩者都約為隨機猜的 4 倍;成績主要來自規則候選。自編碼器與單類支持向量機的作用是讓判出的訊號少約兩成(判高低天數由 ${n0(RU["判高低合計天數"])} 降到 ${n0(MA["判高低合計天數"])},少 ${p1(D.fewer_signals_pct)}),但刪掉的真轉折點與假候選比例相近,因此命中率持平,找到率則由 100% 降到 ${p1(MA.both_rec)};macro-F1 兩者相近(${ruleF1}% 與 ${TT.m.macro_f1.toFixed(2)}%)。逐年的情形相同:2024 至 2026 年本系統的判高低天數依序少 ${Y.map((y) => p1(YD[y].vs["判高低天數_少了_pct"])).join("、")}。`));

body.push(H2("4.3 實驗設計"));
body.push(H3("4.3.1 walk-forward 切分"));
body.push(P(`實驗以 2024、2025 與 2026 年(1 月至 9 月 11 日)為三個測試年,每個測試年都只用之前 4 年的資料訓練(表 3.2、圖 3.5),種子固定為 42。測試樣本為 ${D.n_stocks} 檔股票在測試年中有標籤的全部交易日(表 4.2),所有樣本都以同一套規則與模型判斷,不另外挑選。模型設定與股票池在三個測試年之間保持不變,只依時間往後移動訓練期間。`));
body.push(H3("4.3.2 評估指標"));
body.push(P(["對類別 k ∈ {低點, 高點},令 ", I("TP"), SUB("k"), " 為真實為 k 且判為 k 的個數、", I("FP"), SUB("k"), " 為判為 k 但真實不是 k 的個數、", I("FN"), SUB("k"), " 為真實為 k 但沒有判為 k 的個數。命中率(precision)與找到率(recall)為:"]));
body.push(EQ([I("P"), SUB("k"), " = ", I("TP"), SUB("k"), " / (", I("TP"), SUB("k"), " + ", I("FP"), SUB("k"), ")"], 10));
body.push(EQ([I("R"), SUB("k"), " = ", I("TP"), SUB("k"), " / (", I("TP"), SUB("k"), " + ", I("FN"), SUB("k"), ")"], 11));
body.push(P("各類的 F1 為命中率與找到率的調和平均,macro-F1 為三類(低點、非極值、高點)F1 的平均:"));
body.push(EQ([I("F1"), SUB("k"), " = 2", I("P"), SUB("k"), I("R"), SUB("k"), " / (", I("P"), SUB("k"), " + ", I("R"), SUB("k"), "),  macro-F1 = (1/3) Σ", SUB("k"), " ", I("F1"), SUB("k")], 12));
body.push(P("由 Eq. (10) 可知,命中率回答「判出來的訊號有幾成是真的」;由 Eq. (11) 可知,找到率回答「真的轉折點有幾成被判出來」。本研究另外計算「高低點判反」的個數,即混淆矩陣中真低點判成高點與真高點判成低點兩格的合計。4.4.1 節的個案另以「前後 2 天內找到」表示真轉折點前後 2 個交易日內(同一檔)有同類判斷的情形。"));

body.push(H2("4.4 模擬分析"));
body.push(H3("4.4.1 個案:聯發科 2025 年"));
const mh = MK["高點"], ml = MK["低點"];
body.push(P(`為具體說明系統在單一股票上的判斷,本研究以聯發科(2454)2025 年為例,使用測試 2025 年的模型(訓練期 2021–2024 年)。聯發科 2025 年全年漲跌幅 ${MK["漲跌幅_pct"] > 0 ? "+" : ""}${MK["漲跌幅_pct"]}%、年化波動 ${MK["年化波動_pct"]}%,真高點 ${mh["真"]} 個、真低點 ${ml["真"]} 個。圖 4.4 上段為收盤價與真實高低點,下段為系統的每日判斷:朝下的三角形為判高點、朝上的為判低點,實心為判對、空心為判錯。表 4.5 整理高點與低點的判斷結果。`));
body.push(...FIG("fig4_4_2454.png", 5.75, "圖 4.4 聯發科 2025 的高低點判斷"));
const mkRow = (k, v) => [k, String(v["真"]), String(v["判"]), `${v["對"]} / ${v["錯"]}`, p1(v["找到率_當天"]), p1(v["找到率_±2天"]), p1(v["命中率"])];
body.push(...TAB("表 4.5 聯發科 2025 年的判斷結果", ["類別", "真實個數", "判斷天數", "判對 / 判錯", "找到率\n(當天)", "找到率\n(前後 2 天)", "命中率"],
  [mkRow("高點", mh), mkRow("低點", ml)], [0.9, 1.0, 1.0, 1.1, 1.2, 1.4, 1.0], { size: 20, note: `註:單檔 macro-F1 ${MK.macro_f1}%,高低點判反 ${MK["判反"]}。` }));
body.push(P(`由圖 4.4 與表 4.5 可見:第一,${mh["真"]} 個真高點中有 ${mh["對"]} 個、${ml["真"]} 個真低點中有 ${ml["對"]} 個在當天被判出,找到率分別為 ${p1(mh["找到率_當天"])} 與 ${p1(ml["找到率_當天"])}。第二,方向從未判反。第三,多判的訊號仍多:判高點 ${mh["判"]} 天中有 ${mh["錯"]} 天、判低點 ${ml["判"]} 天中有 ${ml["錯"]} 天是非極值,多半集中在真轉折點前後的連續上漲或下跌日。聯發科這一年的命中率(${p1(mh["命中率"])} 與 ${p1(ml["命中率"])})與 macro-F1(${MK.macro_f1}%)都高於 168 檔三年合計(表 4.3),個股之間的差異不小,整體成績仍以 4.2 節為準。`));

body.push(H3("4.4.2 回測:能否直接用於交易"));
body.push(P(`為檢驗訊號能否直接用於交易,本研究以 2024 至 2025 年回測只做多的進出方式。交易慣例為:t 日收盤出訊號、t+1 日開盤買進;交易成本一趟來回 ${BT.cost}%(手續費 0.1425% × 2 + 證交稅 0.3%);起始資金 100 萬元,每檔投入前一天總資產的 1/K;訊號多於空位時分數高者優先。變化的項目包括持有天數、檔數、判高點出場、等待確認、均線過濾、只取高分與 8% 停損,共 ${BT.n} 種組合。結果如表 4.6 與圖 4.5。`));
body.push(...TAB("表 4.6 30 種只做多策略的回測結果(2024–2025)", ["策略", "扣成本", "未扣成本", "最大回撤"], [
  ["最好:168 檔等權,判高點賣出、判低點買回", sg(BT.best.total_return_net_pct), sg(BT.best_gross), sg(BT.best.max_dd_net_pct)],
  ["第 2:個股與 0050 都在 60 日線上 + 停損", sg(BT.second.total_return_net_pct), sg(BT.second_gross), sg(BT.second.max_dd_net_pct)],
  ["最差:每天前 3 檔、持有 5 天", sg(BT.worst.total_return_net_pct), sg(BT.worst_gross), sg(BT.worst.max_dd_net_pct)],
  ["對照:0050 買進持有", sg(BT.etf0050), "—", "—"],
  ["對照:168 檔等權買進持有", sg(BT.eq168), "—", "—"],
], [3.8, 1.1, 1.1, 1.1], { size: 20, align: [AlignmentType.LEFT, AlignmentType.CENTER, AlignmentType.CENTER, AlignmentType.CENTER],
  note: `註:${BT.n} 種組合扣成本後全部虧損(${BT.n_negative} / ${BT.n})。` }));
body.push(...FIG("fig4_5_backtest.png", 5.6, "圖 4.5 30 種只做多策略扣成本後的報酬與 0050(2024–2025)"));
const T3 = D.top3;
body.push(P(`以最直接的「每天買分數最高的前 3 檔、持有 5 天」為例,扣成本後 2024 年 ${sg(T3["2024"].total_return_pct)}、2025 年 ${sg(T3["2025"].total_return_pct)}、2026 年 1–9 月 ${sg(T3["2026"].total_return_pct)},勝率 ${p1(T3["2024"].win_rate_pct)}、${p1(T3["2025"].win_rate_pct)} 與 ${p1(T3["2026"].win_rate_pct)}。回測的痛點在於誤判多:判出的訊號約七成不是真轉折,頻繁進出的成本會把少數判對的獲利磨平;最好的策略未扣成本時為 ${sg(BT.best_gross)},扣成本後仍是 ${sg(BT.best.total_return_net_pct)},同期 0050 買進持有則為 ${sg(BT.etf0050)}。因此本系統定位為看盤輔助:提醒使用者「這裡可能是局部高點或低點」,是否交易由使用者自行判斷,而不是可以直接下單的自動交易訊號。`));

body.push(H3("4.4.3 實測時間與記憶體"));
body.push(P(`表 4.7 為本系統的實測時間與記憶體,測試環境為 ${ENVS}。判斷一天的時間取 ${DAY["日期"]} 的 ${DAY["重複"]} 次中位數,模型已訓練好、不含讀價格檔;訓練時間為 ${TRAIN["測試年"]} 年的模型(${TRAIN["訓練期"]} 年共 ${n0(TRAIN["訓練樣本數(股票日)"])} 個股票日,高點、低點各一組),不含讀資料與建特徵表。`));
body.push(...TAB("表 4.7 實測時間與記憶體", ["項目", "結果"], [
  [`${D.n_stocks} 檔判斷一天`, `${DAY["中位數_秒"].toFixed(2)} 秒`],
  ["  其中計算 29 維特徵與規則候選", `${DAY["其中_特徵與規則候選_中位數_秒"].toFixed(2)} 秒`],
  ["  其中標準化、自編碼器與 OC-SVM", `${DAY["其中_標準化AE與OCSVM_中位數_秒"]} 秒`],
  ["訓練一個年份的模型", `${TRAIN["秒"].toFixed(1)} 秒`],
  ["記憶體峰值:判斷(讀價格、載入模型、判斷一天)", `${n0(Math.round(MEM["只做判斷的行程(讀 168 檔價格 + 載入模型 + 判斷一天)"]))} MB`],
  ["記憶體峰值:訓練(讀 168 檔、建特徵表、訓練)", `${n0(Math.round(MEM["訓練行程(讀 168 檔 + 建特徵表 + 訓練)"]))} MB`],
], [4.6, 2.0], { size: 20, align: [AlignmentType.LEFT, AlignmentType.CENTER], note: `註:測試環境 ${ENVS};記憶體為行程的常駐記憶體(RSS)峰值。` }));
body.push(P(`由表 4.7 可見,判斷一天的時間大多花在逐檔整理 K 線與計算特徵,模型本身只占 ${DAY["其中_標準化AE與OCSVM_中位數_秒"]} 秒;全程只用 CPU,不需要 GPU。一天的判斷與 walk-forward 的判斷逐檔相同。`));

body.push(H2("4.5 系統評估"));
body.push(H3("4.5.1 系統架構"));
body.push(P("依前述結果,本系統命中率約三成、多判的訊號也多,適合用來提醒「哪裡可能是高點、低點」。因此本研究將模型實作為本機執行的網頁系統(展示版),每天收盤後執行一次更新程式產生判斷,並提供個股查詢與成績追蹤;目前需要每天手動執行一次,尚未設定自動排程。系統的運作方式如表 4.8。"));
body.push(...TAB("表 4.8 網頁系統的運作方式", ["項目", "做法"], [
  ["模型", "與研究相同:規則候選 → 高點、低點各一組 AE(29 → 16)+ OC-SVM;判斷 Y 年時以 Y−4 至 Y−1 年訓練,種子 42"],
  ["推薦範圍", `TW200 剔除低波動股的 ${D.n_stocks} 檔(與研究的股票池相同);今日判斷與成績追蹤只看這些股票`],
  ["計算範圍", "全部上市、上櫃普通股與 ETF 都以同一個模型判斷,供個股查詢;推薦範圍以外的股票加上提示"],
  ["更新", "每天收盤後執行一次更新程式(run.py daily):下載 K 線 → 判斷並存檔 → 對答案 → 產生網頁資料"],
  ["重訓", "每年 1 月第 6 個交易日之後第一次執行更新時,訓練新的一年"],
  ["價格", "模型與對答案用還原價(與研究一致);畫面上的收盤、K 線與成交量顯示實際成交價"],
  ["今日判斷", "判低點、判高點依「已幾天沒破底 / 沒創高」分組、組內依分數排序;同一檔同時有兩種訊號時,只列訊號日較新的那個"],
  ["存檔與對答案", "當天判斷存檔後不再修改;5 個交易日後以研究的同一個標籤規則對答案"],
  ["前端", "靜態網頁,讀取每次更新產生的資料檔;支援淺色、深色主題與手機版面"],
], [1.3, 6.0], { size: 20, align: [AlignmentType.CENTER, AlignmentType.LEFT] }));
body.push(H3("4.5.2 系統功能"));
body.push(P("網頁共有五個頁面:今日判斷、個股查詢、成績追蹤、研究發現與方法說明。圖 4.6 至圖 4.8 為主要頁面的截圖(回放資料,判斷基準日 2026 年 11 月 20 日),其餘截圖見附錄二。"));
body.push(P("今日判斷頁(圖 4.6)上方的數字卡顯示今天判低點、判高點的檔數;下方左欄為判低點、右欄為判高點,每一欄依「今天剛出現」「1–2 天沒破底(沒創高)」「3 天以上」分組,組內依分數排序,每組先列前 3 檔、其餘收在「還有 N 檔」。"));
body.push(...FIG("fig4_6_web_today.png", 5.6, "圖 4.6 網頁系統:今日判斷"));
body.push(P("個股查詢頁(圖 4.7)可輸入代號或名稱,顯示最新收盤價與漲跌、是否在推薦範圍內,並以三列攤開當天的判斷過程:是否為規則候選、模型給的分數、最後的判斷;下方為今年整年的 K 線,標出每一天的判斷與對錯(實心為判對、空心為判錯、未滿 5 天為待驗證)。"));
body.push(...FIG("fig4_7_web_2454.png", 5.6, "圖 4.7 網頁系統:個股查詢(2454 聯發科)"));
body.push(P("成績追蹤頁(圖 4.8)在每天的判斷 5 個交易日後對答案,顯示最近 20 天、最近 60 天與今年全部的命中率、命中率隨時間的變化、推薦範圍內外的命中率,以及每天分數最高 3 檔的明細。"));
body.push(...FIG("fig4_8_web_track.png", 5.2, "圖 4.8 網頁系統:成績追蹤"));
body.push(H3("4.5.3 與研究結果的一致性"));
body.push(P("網頁系統的判斷已與研究結果逐列核對:以系統的正式模型重新判斷 2026 年(1–9 月)168 檔共 27,208 個股票日,混淆矩陣與 macro-F1 和研究結果檔完全相同,逐列的判斷全部相同、分數最大差距為 0;以同一套程式另外訓練 2024、2025 年的模型,混淆矩陣也和結果檔相同;網頁以自己的 K 線快取回放的 2026 年判斷,同樣 27,208 列全部相同。因此網頁上的每日判斷與第四章評估的是同一套方法。"));
body.push(P("系統另以自動化測試驗證,涵蓋資料更新(增量下載、還原價變動重抓、網路失敗、休市)、判斷存檔不覆蓋、5 天後才對答案、推薦範圍與池外 / 低波動 / 不支援股票的判定、今日判斷新訊號蓋掉舊訊號、畫面用實際成交價而模型用還原價、特徵與連續天數不使用未來資料、每日更新與回放結果相同,以及正式模型重現研究的混淆矩陣。"));

// ───── 第五章 ─────
body.push(H1("第五章 結論與建議"));
body.push(H2("5.1 結論"));
body.push(L("(1)", `收盤當天判斷:系統只使用 t 日以前的 6 根 K 線,在收盤當天就給出判斷,不需要等轉折發生後好幾天。`));
body.push(L("(2)", `找到約 8 成轉折:168 檔、三年逐年驗證下,本系統找到 ${p1(MA.both_rec)} 的真轉折點,命中率 ${p1(MA.both_prec)},約為隨機猜的 ${Math.round(RATIO)} 倍;macro-F1 三年依序為 ${Y.map(mf).join("%、")}%,高低點從未判反(由規則候選保證)。`));
body.push(L("(3)", `成績主要來自規則:與只用規則相比,自編碼器與單類支持向量機讓訊號少約兩成(${p1(D.fewer_signals_pct)}),命中率持平,找到率由 100% 降到 ${p1(MA.both_rec)}。`));
body.push(L("(4)", `不能直接當交易訊號:${BT.n} 種只做多策略扣成本後全部虧損(最好 ${sg(BT.best.total_return_net_pct)}),同期 0050 為 ${sg(BT.etf0050)};判出的訊號約七成不是真轉折,本系統定位為看盤輔助。`));
body.push(L("(5)", `可實際運行:168 檔判斷一天 ${DAY["中位數_秒"].toFixed(2)} 秒、訓練一個年份 ${TRAIN["秒"].toFixed(1)} 秒,只用 CPU;網頁系統的判斷與研究結果逐列一致。`));
body.push(H2("5.2 研究限制"));
body.push(L("(1)", "多判的訊號多:判出的高低點約七成是非極值,同一段漲跌中真轉折點前後的候選日難以分辨。"));
body.push(L("(2)", "自編碼器與單類支持向量機沒有提高命中率:它們減少約兩成訊號,但刪掉的真、假候選比例相近,命中率與只用規則持平,找到率則降低。"));
body.push(L("(3)", `只驗證 ${D.n_stocks} 檔:股票池為 TW200 剔除低波動股,使用目前的清單,未處理成分股變動;低波動股的剔除以 2020 年起的資料計算,涵蓋了測試期間。結果不一定能推廣到其他股票。`));
body.push(L("(4)", "只做日線:特徵只使用 6 根日 K 線的價格與成交量,未納入其他週期、技術指標、大盤與籌碼等資訊;主要結果只使用種子 42。"));
body.push(L("(5)", "標籤需要 t+5 的價格,成績追蹤必須等 5 個交易日後才能對答案;網頁系統目前需要每天手動執行一次更新。"));
body.push(H2("5.3 研究成果"));
body.push(L("(1)", "完成規則候選 + AE + OC-SVM 的判斷方法,對每一天輸出高點、低點或非極值的判斷與分數。"));
body.push(L("(2)", "完成 168 檔股票三個測試年的 walk-forward 評估,包括混淆矩陣、找到率、命中率、與隨機及只用規則的比較、聯發科個案、30 種策略的回測與實測時間,所有數字都保存在結果檔中、可重現。"));
body.push(L("(3)", "完成網頁系統(展示版):每日更新、判斷存檔、5 天後對答案、今日判斷、個股查詢、成績追蹤、研究發現與方法說明頁,並核對判斷與研究結果一致。"));
body.push(H2("5.4 研究貢獻"));
body.push(L("(1)", "以實證說明在收盤當天就能找到約 8 成的局部轉折點,且高低點方向不會判反。"));
body.push(L("(2)", "以「只用規則」基準釐清成績來源:成績主要來自規則候選,而非模型本身,避免高估模型的效果。"));
body.push(L("(3)", "以回測誠實呈現訊號不能直接用於交易,並據此將系統定位為看盤輔助。"));
body.push(L("(4)", "將研究模型與網頁系統逐列核對,確保使用者看到的判斷與研究評估的是同一套方法,且每一次判斷都存檔、可事後驗證。"));
body.push(H2("5.5 後續研究方向"));
body.push(L("(1)", "分辨真假候選:目前模型難以分辨同一段漲跌中真轉折點與前後的候選日,後續可嘗試能看更長 K 線脈絡的模型(例如序列模型),以提高命中率。"));
body.push(L("(2)", "每日自動更新:為網頁系統設定排程,在每天收盤後自動執行更新,並持續累積實際上線後的判斷與答案,以真實時間序列評估長期表現。"));
body.push(L("(3)", "擴大驗證範圍:使用歷史成分股清單與不含測試期的低波動判定、增加多個亂數種子與更多股票,降低存活者偏誤與資訊洩漏。"));
body.push(H2("5.6 專題過程導入的 AI 工具"));
body.push(P("本專題使用 Claude Code(Anthropic)[9] 作為輔助工具,協助以下工作:"));
body.push(L("(1)", "程式撰寫:標籤、規則候選、特徵、AE + OC-SVM 模型、walk-forward 評估、回測、網頁系統與其自動化測試的程式碼。"));
body.push(L("(2)", "實驗執行與結果核對:依指示執行實驗、把結果寫入結果檔,並核對不同程式之間的數字一致(例如網頁系統的判斷與研究結果逐列相同)。"));
body.push(L("(3)", "圖表與報告整理:繪製混淆矩陣與個案圖,整理簡報、海報與本報告的初稿。"));
body.push(L("(4)", "多個 session 分工:以一個監督用的 session 接收與轉達指令,再由不同的 session 分別負責研究程式、網頁系統與報告,彼此以訊息交接。"));
body.push(P("人工決策與檢查的部分包括:研究方向與題目的決定;標籤定義、規則候選與 AE + OC-SVM 等方法上的選擇;股票池的選擇與剔除低波動股;實驗範圍與個案的選擇;以及報告呈現方式與最終內容的決定。AI 工具產生的程式與數字,均經人工閱讀結果、對照結果檔與圖表後才採用。"));

// ───── 參考文獻 ─────
body.push(H1("參考文獻"));
const REF = (n, parts) => new Paragraph({ alignment: AlignmentType.LEFT, spacing: { ...BODY_LINE, after: 80 }, indent: { left: 600, hanging: 600 },
  children: [run(`[${n}]`), new TextRun({ children: [new Tab()], font: F }), ...runs(parts)], tabStops: [{ type: TabStopType.LEFT, position: 600 }] });
const it = (t) => [t, { italics: true }];
body.push(REF(1, ["G. E. Hinton and R. R. Salakhutdinov, \"Reducing the dimensionality of data with neural networks,\" ", it("Science"), ", vol. 313, no. 5786, pp. 504–507, Jul. 2006."]));
body.push(REF(2, ["D. P. Kingma and J. Ba, \"Adam: A method for stochastic optimization,\" ", it("Proceedings of the 3rd International Conference on Learning Representations (ICLR)"), ", San Diego, CA, USA, May 2015."]));
body.push(REF(3, ["B. Schölkopf, J. C. Platt, J. Shawe-Taylor, A. J. Smola, and R. C. Williamson, \"Estimating the support of a high-dimensional distribution,\" ", it("Neural Computation"), ", vol. 13, no. 7, pp. 1443–1471, Jul. 2001."]));
body.push(REF(4, ["C. Bergmeir and J. M. Benítez, \"On the use of cross-validation for time series predictor evaluation,\" ", it("Information Sciences"), ", vol. 191, pp. 192–213, May 2012."]));
body.push(REF(5, ["M. Sokolova and G. Lapalme, \"A systematic analysis of performance measures for classification tasks,\" ", it("Information Processing & Management"), ", vol. 45, no. 4, pp. 427–437, Jul. 2009."]));
body.push(REF(6, ["F. Pedregosa et al., \"Scikit-learn: Machine learning in Python,\" ", it("Journal of Machine Learning Research"), ", vol. 12, pp. 2825–2830, 2011."]));
body.push(REF(7, ["A. Paszke et al., \"PyTorch: An imperative style, high-performance deep learning library,\" ", it("Advances in Neural Information Processing Systems 32 (NeurIPS 2019)"), ", pp. 8024–8035, Dec. 2019."]));
body.push(REF(8, ["R. Aroussi, yfinance: Download market data from Yahoo! Finance's API. https://github.com/ranaroussi/yfinance(存取日期:2026 年 11 月 9 日)"]));
body.push(REF(9, ["Anthropic, Claude Code 說明文件. https://code.claude.com/docs(存取日期:2026 年 11 月 9 日)"]));

// ───── 附錄 ─────
body.push(H1("附錄"));
body.push(H2("附錄一 程式模組與執行指令"));
body.push(P("研究程式與結果位於分支 final 的 method_kline_peak/,網頁系統位於分支 claude/kline-peak-web-app 的 method_kline_peak/web/。以下指令皆在專題根目錄執行;未列出的參數使用預設值。"));
body.push(...TAB("附表 1 研究程式模組", ["模組", "用途"], [
  ["mainline.py", "標籤、規則候選、29 維特徵、股票池與低波動股剔除、AE + OC-SVM 訓練"],
  ["walkforward.py", "逐年 walk-forward 的訓練與判斷"],
  ["ae_ocsvm.py", "相似樣本權重"],
  ["paper_aeocsvm.py", "標籤與規則候選"],
  ["backtest_top3.py、backtest_strategies.py", "只做多前 3 檔回測、30 種策略回測與對照"],
  ["report/confusion_2024_2026.py", "2024–2026 混淆矩陣圖與數字"],
  ["report/baseline_rule.py", "只用規則與本系統的比較"],
  ["report/per_stock_rank.py、report/stock_outputs.py", "每檔股票的成績、個股每天的判斷圖"],
  ["report/timing_mainline.py", "實測時間與記憶體"],
  ["web/run.py", "網頁系統:每日更新、回放、重訓、產生網頁資料、開啟網頁"],
  ["web/check_research_match.py", "網頁系統的判斷與研究結果逐列核對"],
], [2.9, 4.4], { size: 18, align: [AlignmentType.LEFT, AlignmentType.LEFT] }));
body.push(...TAB("附表 2 主要執行指令", ["用途", "指令"], [
  ["混淆矩陣 2024–2026", "python method_kline_peak/report/confusion_2024_2026.py --pool tw200"],
  ["只用規則比較", "python method_kline_peak/report/baseline_rule.py"],
  ["30 種策略回測", "python method_kline_peak/backtest_strategies.py"],
  ["聯發科 2025 每日判斷", "python method_kline_peak/report/stock_outputs.py 2454.TW --years 2025"],
  ["實測時間與記憶體", "python method_kline_peak/report/timing_mainline.py"],
  ["網頁:第一次回放", "python method_kline_peak/web/run.py replay --start 2026-01-01"],
  ["網頁:每日更新並開網頁", "python method_kline_peak/web/run.py start"],
  ["網頁與研究結果核對", "python method_kline_peak/web/check_research_match.py"],
], [1.9, 5.4], { size: 18, align: [AlignmentType.LEFT, AlignmentType.LEFT] }));
body.push(H2("附錄二 網頁系統其他截圖"));
body.push(P("以下截圖為網頁系統展示版的真實畫面(回放資料,判斷基準日 2026 年 11 月 20 日),各圖只取頁面上半部。"));
body.push(...FIG("appB_today_mobile.png", 2.6, "圖 A.1 今日判斷(手機版面)"));
body.push(...FIG("appB_otc_3374.png", 5.4, "圖 A.2 個股查詢:推薦範圍外的上櫃股票(3374 精材)"));
body.push(...FIG("appB_findings.png", 5.4, "圖 A.3 研究發現"));
body.push(...FIG("appB_about.png", 5.4, "圖 A.4 方法與說明"));



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
