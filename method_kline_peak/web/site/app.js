/* K 線高低點判斷:靜態前端。資料全部來自 data/*.json(每日批次產生)。 */
const D = {shards: {}};
const LBL = {low: '低點', high: '高點', none: '非極值'};
const MNAME = {main: '① 主軸', stack: '② Stacking'};
const STATUS = {pool: ['池內', 't-ok'], out: ['池外', 't-warn'], lowvol: ['低波動', 't-none'], nosup: ['不支援', 't-bad'], nodata: ['資料不足', 't-none'], halted: ['今日無交易', 't-none']};
const MARKET = {TWSE: '上市', OTC: '上櫃', ESB: '興櫃', ETF: 'ETF'};
/* 預設方法(2026-11-09 使用者決定:預設 Stacking,主軸可以切換過去);實際值在 boot() 依 meta.json 的 default_method 設定 */
let DEF = 'stack', METHOD = 'stack', TM = 'stack', TK = 'low', Q = '', FM = 'stack';
const other = m => m === 'stack' ? 'main' : 'stack';
const MSEG = () => [[DEF, MNAME[DEF]], [other(DEF), MNAME[other(DEF)]]];   // 切換鈕:預設的放前面
const sfmt = (m, x) => fmt(x, m === 'main' ? 1 : 2);

const fmt = (x, d = 2) => x == null || !isFinite(x) ? '—' : Number(x).toLocaleString('zh-TW', {minimumFractionDigits: d, maximumFractionDigits: d});
const pct = (x, d = 1) => x == null ? '—' : fmt(x, d) + '%';
const sgn = (x, d = 2) => x == null ? '—' : `<span class="${x >= 0 ? 'up' : 'dn'}">${x >= 0 ? '+' : ''}${fmt(x, d)}%</span>`;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const WD = '日一二三四五六';
const dlabel = d => { const t = new Date(d + 'T00:00:00'); return `${d}(${WD[t.getDay()]})`; };
const md = d => d ? d.slice(5).replace('-', '/') : '';
const tagCls = k => k === 'low' ? 't-low' : k === 'high' ? 't-high' : 't-none';

async function j(path) { const r = await fetch(path, {cache: 'no-store'}); if (!r.ok) throw new Error(path + ' ' + r.status); return r.json(); }

/* ---------- 共用 ---------- */
function disc() {
  return `<div class="disc">本網站為研究模型輸出展示,非證券投資顧問服務,不構成買賣建議。模型命中率約 3 成,依研究回測規則操作多數年度扣成本後為虧損。<a href="#about">完整免責聲明</a></div>`;
}
/* 目前的設定(股票池、訓練門檻)來自 meta.json 的 profile;預設 TW100 剔除低波動股、門檻 0% */
const PF = () => D.meta?.profile || {pool: 'tw100', pool_label: 'TW100', n_pool: 73, train_min_amp: 0};
const poolDesc = () => `${PF().pool_label} 剔除低波動股,${PF().n_pool} 檔${PF().train_min_amp ? `,訓練門檻 ${PF().train_min_amp}%` : ''}`;
const BT_POOL = {tw100: 'TW100 73 檔', tw200: 'TW200 168 檔'};
function researchBT(method, pool = BT_POOL[PF().pool]) {
  return (D.research?.backtest || []).filter(r => r.pool === pool && r.method === method).sort((a, b) => a.year.localeCompare(b.year));
}
function btText(method) {
  const r = researchBT(method);
  if (!r.length) return `研究沒有 ${esc(PF().pool_label)} 股票池的回測結果`;
  return `${r.map(x => x.year + (x.year === '2026' ? '(1–9 月)' : '')).join(' / ')} 扣成本為 <b>${r.map(x => (x.ret_pct >= 0 ? '+' : '') + fmt(x.ret_pct, 1) + '%').join(' / ')}</b>`
    + (PF().train_min_amp ? '(研究回測的訓練門檻為 0%)' : '');
}
function trk(method, kind) { return D.track?.methods?.[method]?.[kind] || {}; }
const HAS_LEVEL = {main: false, stack: true};   // 2026-11-03:主軸拿掉信心等級(三個等級命中率幾乎一樣),Stacking 保留
function allHit(method, kind) { const h = trk(method, kind).all; return h?.n ? `${MNAME[method]}判${LBL[kind]}整體命中 <b>${pct(h.pct)}</b>(${h.n} 筆)` : `${MNAME[method]}尚無對答案紀錄`; }
function bothTag(kind) { const h = D.today?.both_hit?.[kind] || D.track?.both?.[kind]; return `<span class="tag t-both">兩方法一致${h?.n ? `・一致時命中 ${pct(h.pct)}` : ''}</span>`; }
function lvHit(h) { return h && h.n >= 20 ? `同等級歷史命中 <b>${pct(h.pct)}</b>(${h.n} 筆)` : h && h.n ? `同等級命中 ${pct(h.pct)}(只有 ${h.n} 筆,僅供參考)` : '同等級尚無對答案紀錄'; }
function spark(vals, w = 86, h = 28) {
  if (!vals || vals.length < 2) return '';
  const mn = Math.min(...vals), mx = Math.max(...vals);
  const pts = vals.map((v, i) => `${(i / (vals.length - 1) * w).toFixed(1)},${(h - 2 - (v - mn) / (mx - mn || 1) * (h - 4)).toFixed(1)}`).join(' ');
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline points="${pts}" fill="none" stroke="${vals[vals.length - 1] >= vals[0] ? 'var(--up)' : 'var(--down)'}" stroke-width="1.6"/></svg>`;
}
function chg(x) { return x == null ? '' : `<span class="chg ${x >= 0 ? 'up' : 'dn'}">${x >= 0 ? '▲' : '▼'}${fmt(Math.abs(x))}%</span>`; }
function seg(cur, opts, setter) {
  return `<div class="seg">${opts.map(([k, n]) => `<button class="${k === cur ? 'on' : ''}" onclick="${setter}='${k}';render()">${n}</button>`).join('')}</div>`;
}

/* ---------- 今日判斷 ---------- */
/* 標記:連續第 N 天(同一類判斷連續幾個交易日)、已 M 天沒破底 / 沒創高(訊號日之後每天收盤都沒跌破 / 漲過訊號日收盤)。
   都只用當天以前的資料,在產生網頁資料時算好(system/signals.py)。 */
const HOLDWORD = {low: '沒破底', high: '沒創高'};
function marks(a, kind) {
  if (!a) return '';
  const run = `<span class="mark">連續第 ${a.run} 天</span>`;
  const hold = a.days === 0 ? '<span class="mark new">剛出現</span>' : `<span class="mark hold">已 ${a.days} 天${HOLDWORD[kind]}</span>`;
  return `<div class="marks">${hold}${run}</div>`;
}
const GROUPS = [['new', '剛出現(今天判)'], ['d12', '已 1–2 天'], ['d3', '已 3 天以上']];
function groupHit(method, kind, g) {
  const c = D.today.confirm_hit?.[method]?.[kind];
  if (!c) return '';
  if (g === 'new') return `研究命中 ${pct(c.k0)}`;
  if (g === 'd12') return `研究命中:1 天 ${pct(c.k1)}、2 天 ${pct(c.k2)}`;
  return `研究命中:3 天 ${pct(c.k3)}(4–5 天沒有研究數字)`;
}
function pickRow(s, i, kind) {
  const old = s.days > 0 ? `訊號日 ${md(s.date)} ・ ` : '';
  return `<div class="pick" onclick="go('stock-${s.code}')"><div class="rank">${i + 1}</div>
  <div><div class="nm">${s.code}<span>${esc(s.name)}</span> ${s.both ? bothTag(kind) : ''}</div>
  ${marks(s, kind)}
  <div class="info">${old}分數 ${fmt(s.score, METHOD === 'main' ? 1 : 2)} ・ ${HAS_LEVEL[METHOD] ? `信心 <b>${s.level || '—'}</b> ・ ${lvHit(s.level_hit)}` : allHit(METHOD, kind)}</div></div>
  <div class="right"><div class="px">${fmt(s.close)}</div>${chg(s.chg_pct)}<div class="hide-m">${spark(s.spark)}</div></div></div>`;
}
function groupBlock(L, kind, g, label) {
  const items = L.filter(s => s.group === g), top = items.slice(0, 3), rest = items.slice(3);
  const name = g === 'new' ? label : `${label}${HOLDWORD[kind]}`;
  return `<div class="grp"><b>${name}</b><span class="lbl">${items.length} 檔</span><span class="sp"></span><span class="hit">${groupHit(METHOD, kind, g)}</span></div>
  ${items.length ? top.map((s, i) => pickRow(s, i, kind)).join('') : `<div class="lbl" style="padding:8px 0">目前沒有。</div>`}
  ${rest.length ? `<details class="more"><summary>還有 ${rest.length} 檔(分數較低)</summary>
  <table class="minitable"><tr><th>代號</th><th>名稱</th><th>收盤</th><th>分數</th><th>連續</th><th>${HAS_LEVEL[METHOD] ? '信心' : '兩方法一致'}</th></tr>
  ${rest.map(s => `<tr onclick="go('stock-${s.code}')" style="cursor:pointer"><td>${s.code}</td><td>${esc(s.name)}</td><td>${fmt(s.close)}</td><td>${fmt(s.score, METHOD === 'main' ? 1 : 2)}</td><td>${s.run} 天</td><td>${HAS_LEVEL[METHOD] ? (s.level || '—') : (s.both ? '是' : '')}</td></tr>`).join('')}</table></details>` : ''}`;
}
function listCard(kind) {
  const L = D.today.methods[METHOD][kind] || [], isLow = kind === 'low';
  return `<div class="card"><div class="listhead"><span class="dot" style="background:${isLow ? 'var(--low)' : 'var(--high)'}"></span>
  <h2 style="margin:0">${isLow ? '判低點' : '判高點'}</h2><span class="lbl">共 ${L.length} 檔,依「${HOLDWORD[kind]}」天數分組,組內依分數排序</span></div>
  <div class="lbl" style="margin:-4px 0 6px">${isLow ? '收盤可能是前後 11 天最低。前幾天判的,只列到今天都還沒跌破那天收盤的' : '收盤可能是前後 11 天最高 ── 只當提醒,研究沒有回測過賣出規則'}</div>
  ${GROUPS.map(([g, label]) => groupBlock(L, kind, g, label)).join('')}</div>`;
}
function pageToday() {
  const T = D.today, lo = T.methods[METHOD].low || [], hi = T.methods[METHOD].high || [];
  const nNew = L => L.filter(s => s.group === 'new').length;
  const t60 = trk(METHOD, 'low').top_60 || {}, base = trk(METHOD, 'low').base_rate || {};
  return `<div class="row" style="margin-bottom:14px"><div><h1>今日判斷</h1>
  <p class="sub" style="margin:0">${dlabel(T.date)} 收盤後,模型對股票池 ${T.n_pool} 檔的判斷。答案要再過 5 個交易日收盤才知道。</p></div>
  <div class="sp"></div><div><div class="lbl" style="margin-bottom:4px">方法</div>${seg(METHOD, MSEG(), 'METHOD')}</div></div>
  <div class="summary">
   <div class="card"><div class="lbl">今天判低點</div><div class="kpi" style="color:var(--low)">${nNew(lo)} <small>檔</small></div><div class="info">另 ${lo.length - nNew(lo)} 檔前 1–5 天判、還沒破底</div></div>
   <div class="card"><div class="lbl">今天判高點</div><div class="kpi" style="color:var(--high)">${nNew(hi)} <small>檔</small></div><div class="info">另 ${hi.length - nNew(hi)} 檔前 1–5 天判、還沒創高</div></div>
   <div class="card"><div class="lbl">兩方法一致(低 / 高)</div><div class="kpi" style="color:var(--both)">${T.both.low} / ${T.both.high} <small>檔</small></div><div class="info">一致時命中 低 ${pct(T.both_hit?.low?.pct)} / 高 ${pct(T.both_hit?.high?.pct)}</div></div>
   <div class="card"><div class="lbl">${MNAME[METHOD]} 判低點前 3 檔命中率(近 60 天)</div><div class="kpi">${pct(t60.pct)} <small>隨機約 ${pct(base.pct, 0)}</small></div></div>
  </div>
  <div class="grid2">${listCard('low')}${listCard('high')}</div>
  <div class="note" style="margin-top:16px"><b>怎麼看這份清單</b><br>
  「判低點」10 次大約只有 3 次真的是低點,錯的大多是普通日子。判斷之後幾天都沒破底,真的是低點的比例會變高
  (${esc(T.confirm_hit?.source || '')});但這是因為那幾天的價格本來就是答案的一部分,等到確認才進場已經晚了,研究的回測沒有因此變好。<a href="#findings">看研究發現</a><br>
  研究回測的規則是:<b>判低點分數前 3 檔、下一個交易日開盤買、第 5 個交易日收盤賣</b>,
  ${btText(METHOD)}(研究結果,${esc(PF().pool_label)} ${MNAME[METHOD]})。分數只在同一個方法裡比大小。</div>
  ${disc()}`;
}

/* ---------- 個股查詢 ---------- */
function typeTag(st) { const [n, c] = STATUS[st] || ['?', 't-none']; return `<span class="tag ${c}">${n}</span>`; }
function chips() {
  const byCode = Object.fromEntries((D.index || []).map(r => [r[0], r]));
  const pick = (pref, st) => byCode[pref]?.[2] === st ? byCode[pref] : (D.index || []).find(r => r[2] === st);
  const list = [['2330', '台積電'], ['2379', '瑞昱']];
  for (const [pref, st] of [['2618', 'out'], ['2412', 'lowvol']]) { const r = pick(pref, st); if (r) list.push([r[0], r[1]]); }
  list.push(['0050', '元大台灣50']);
  return `<div class="chips">${list.map(([c, n]) => `<span class="chip" onclick="go('stock-${c}')">${c} ${esc(n)}</span>`).join('')}</div>`;
}
function searchBox() {
  return `<div class="search"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--axis)" stroke-width="2.2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
  <input id="q" placeholder="輸入代號或名稱,例如 2330 或 台積" autocomplete="off" value="${esc(Q)}" oninput="ac(this.value)" onfocus="ac(this.value)" onkeydown="acKey(event)"><div class="ac" id="ac"></div></div>${chips()}`;
}
let ACSEL = 0, ACL = [];
function ac(v) {
  Q = v; const el = document.getElementById('ac'); v = v.trim(); if (!v) { el.classList.remove('show'); return; }
  const idx = D.index || [];
  ACL = idx.filter(r => r[0].startsWith(v)).concat(idx.filter(r => !r[0].startsWith(v) && r[1].includes(v))).slice(0, 8); ACSEL = 0;
  el.innerHTML = ACL.length ? ACL.map((r, i) => `<div class="${i === 0 ? 'sel' : ''}" onmousedown="go('stock-${r[0]}')"><span class="code">${r[0]}</span><span class="sp">${esc(r[1])}</span>${r[2] === 'nosup' ? `<span class="tag t-bad">${MARKET[r[3]] || '不支援'}</span>` : typeTag(r[2])}</div>`).join('')
    : '<div style="color:var(--ink3)">找不到。目前只支援上市普通股</div>';
  el.classList.add('show');
}
function acKey(e) {
  const el = document.getElementById('ac'); if (!ACL.length) return;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { ACSEL = (ACSEL + (e.key === 'ArrowDown' ? 1 : -1) + ACL.length) % ACL.length; [...el.children].forEach((d, i) => d.classList.toggle('sel', i === ACSEL)); e.preventDefault(); }
  if (e.key === 'Enter') go('stock-' + ACL[ACSEL][0]);
}
function kchart(S, PM = DEF) {
  const M = innerWidth < 760, bars = S.bars.slice(M ? -30 : -60);
  if (!bars.length) return '<div class="mutebox">沒有 K 線資料</div>';
  const sig = Object.fromEntries((S.signals || []).map(s => [s.date, s]));
  const W = M ? 420 : 860, H = M ? 320 : 300, VH = 50, pad = 8, top = 22, bot = H - VH - 24;
  const mx = Math.max(...bars.map(b => b[2])) * 1.015, mn = Math.min(...bars.map(b => b[3])) * 0.985, y = v => top + (mx - v) / (mx - mn) * (bot - top);
  const bw = (W - pad * 2) / bars.length, vmax = Math.max(...bars.map(b => b[5])) || 1; let g = '';
  for (let k = 0; k < 4; k++) { const v = mn + (mx - mn) * k / 3; g += `<line x1="0" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--grid)"/><text x="2" y="${y(v) - 3}" font-size="10" fill="var(--axis)">${fmt(v, 1)}</text>`; }
  bars.forEach((b, i) => {
    const [d, o, h, l, c, v] = b, x = pad + i * bw + bw / 2, col = c >= o ? 'var(--up)' : 'var(--down)';
    g += `<line x1="${x}" x2="${x}" y1="${y(h)}" y2="${y(l)}" stroke="${col}"/><rect x="${x - bw * .34}" y="${y(Math.max(o, c))}" width="${bw * .68}" height="${Math.max(1, Math.abs(y(o) - y(c)))}" fill="${col}"/>`;
    g += `<rect x="${x - bw * .34}" y="${H - 24 - v / vmax * VH}" width="${bw * .68}" height="${v / vmax * VH}" fill="${col}" opacity=".35"/>`;
    const s = sig[d];
    if (s && s[PM] && s[PM] !== 'none') {
      const isL = s[PM] === 'low', c2 = isL ? 'var(--low)' : 'var(--high)', yy = isL ? y(l) + 11 : y(h) - 11;
      const st = s.truth == null ? 'wait' : s.truth === s[PM] ? 'ok' : 'bad';
      const tri = isL ? `M${x - 5},${yy + 4} L${x + 5},${yy + 4} L${x},${yy - 4} Z` : `M${x - 5},${yy - 4} L${x + 5},${yy - 4} L${x},${yy + 4} Z`;
      g += `<path d="${tri}" fill="${st === 'ok' ? c2 : 'var(--card)'}" stroke="${c2}" stroke-width="1.5" ${st === 'wait' ? 'stroke-dasharray="2 1.5"' : ''}><title>${d} ${MNAME[PM]}判${LBL[s[PM]]}:${st === 'wait' ? '待驗證' : st === 'ok' ? '對' : '錯'}</title></path>`;
      if (st === 'bad') g += `<text x="${x}" y="${isL ? yy + 16 : yy - 8}" font-size="9" fill="var(--bad)" text-anchor="middle">✕</text>`;
    }
    if (i === bars.length - 1) g += `<rect x="${x - bw / 2}" y="${top - 6}" width="${bw}" height="${bot - top + 12}" fill="var(--accent)" opacity=".06"/><text x="${x - bw}" y="${top - 9}" font-size="10" font-weight="700" fill="var(--accent)" text-anchor="end">今天 ▸</text>`;
  });
  const ticks = M ? [0, 10, 20, bars.length - 1] : [0, 15, 30, 45, bars.length - 1];
  ticks.filter(i => i < bars.length).forEach(i => g += `<text x="${pad + i * bw + bw / 2}" y="${H - 8}" font-size="10" fill="var(--axis)" text-anchor="middle">${md(bars[i][0])}</text>`);
  return `<div class="chartwrap"><svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block">${g}</svg></div>
  <div class="legend"><span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="var(--low)"/></svg>判低點・對</span><span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="var(--card)" stroke="var(--low)" stroke-width="1.4"/></svg>判低點・錯(✕)</span>
  <span><svg width="12" height="10"><path d="M1,1 L11,1 L6,9Z" fill="var(--high)"/></svg>判高點・對</span><span><svg width="12" height="10"><path d="M1,1 L11,1 L6,9Z" fill="var(--card)" stroke="var(--high)" stroke-width="1.4" stroke-dasharray="2 1.5"/></svg>虛線 = 待驗證(未滿 5 天)</span>
  <span>K 線為還原價,紅漲綠跌 ・ 標記為 ${MNAME[PM]}的判斷</span></div>`;
}
function bar(label, v, color, txt) {
  return `<div class="cls"><span>${label}</span><div class="bar" style="margin:0;height:8px"><i style="width:${Math.max(0, Math.min(1, v)) * 100}%;background:${color}"></i></div><span class="right">${txt}</span></div>`;
}
function classBlocks(t) {
  const m = t.main || {}, s = t.stack || {};
  const ocs = (v, cut) => v == null ? '—' : (v > 0 ? '範圍內 ' : '範圍外 ') + fmt(v, 1);
  const blk = {
    stack: `<div><div class="lbl">② Stacking:三類機率</div>
    ${bar('高點', s.p_high, 'var(--high)', fmt(s.p_high))}${bar('低點', s.p_low, 'var(--low)', fmt(s.p_low))}${bar('非極值', s.p_none, 'var(--ink3)', fmt(s.p_none))}</div>`,
    main: `<div><div class="lbl">① 主軸:兩個 OC-SVM 的分數</div>
    <div class="cls"><span>高點</span><span style="grid-column:span 2" class="num">${ocs(m.s_high)}</span></div>
    <div class="cls"><span>低點</span><span style="grid-column:span 2" class="num">${ocs(m.s_low)}</span></div>
    <div class="lbl" style="margin-top:4px">只有收盤創近 6 天新高(新低)時才看高點(低點)分數;> 0 才判高點(低點)。</div></div>`};
  return `<div class="grid2" style="gap:14px">${blk[DEF]}${blk[other(DEF)]}</div>`;
}
function pageSearch() {
  return `<h1>個股查詢</h1><p class="sub">輸入上市股票代號或名稱。池內 ${D.meta.counts.pool} 檔(${esc(poolDesc())})是訓練用的股票;池外股票會顯示警示;低波動股不適用。</p>${searchBox()}
  <div class="grid4 k2">${[['池內', 't-ok', `${D.meta.counts.pool} 檔,模型訓練用的股票`], ['池外', 't-warn', `${D.meta.counts.out} 檔,可查,但判斷沒有驗證過`], ['低波動', 't-none', `${D.meta.counts.lowvol} 檔,每日漲跌太小,判斷不適用`], ['不支援', 't-bad', 'ETF、上櫃、興櫃、特別股']].map(([a, c, d]) => `<div class="card"><span class="tag ${c}">${a}</span><div class="info" style="margin-top:6px">${d}</div></div>`).join('')}</div>${disc()}`;
}
/* 個股資料依代號前兩碼分檔(stocks/23.json 內含 2301–2399),讀過的分檔留在記憶體 */
async function loadStock(code) {
  const k = code.slice(0, 2);
  if (!D.shards[k]) D.shards[k] = await j(`data/stocks/${k}.json`);
  return D.shards[k][code];
}
function activeCard(S) {
  const rows = [];
  for (const m of [DEF, other(DEF)]) for (const k of ['low', 'high']) {
    const a = S.active?.[m]?.[k];
    if (!a) continue;
    const c = D.today.confirm_hit?.[m]?.[k], key = a.days >= 3 ? 'k3' : 'k' + a.days;
    const hitTxt = c && a.days <= 3 ? `研究命中 ${pct(c[key])}` : c ? `研究只算到 3 天(${pct(c.k3)})` : '';
    rows.push(`<tr><td>${MNAME[m]}</td><td><span class="tag ${tagCls(k)}">判${LBL[k]}</span></td><td>${md(a.date)}</td>
      <td>${a.days === 0 ? '剛出現' : `已 ${a.days} 天${HOLDWORD[k]}`}</td><td>連續第 ${a.run} 天</td><td>${hitTxt}</td></tr>`);
  }
  if (!rows.length) return '';
  return `<div class="card"><h3>最近的高 / 低點訊號</h3><div class="tblwrap"><table class="tbl"><tr><th>方法</th><th>判斷</th><th>訊號日</th><th>到今天</th><th>連續</th><th>研究數字(TW200)</th></tr>${rows.join('')}</table></div>
   <div class="lbl" style="margin-top:6px">只列最近 5 個交易日內、到今天都還沒破底(低點)/ 沒創高(高點)的訊號。等越多天,真的是低點的比例越高,但也越晚。研究數字:${esc(D.today.confirm_hit?.source || '')}。</div></div>`;
}
async function pageStock(code) {
  const ix = (D.index || []).find(r => r[0] === code);
  if (!ix) return `<h1>個股查詢</h1>${searchBox()}<div class="badbox">查無代號 ${esc(code)}。目前只支援上市普通股。</div>${disc()}`;
  if (ix[2] === 'nosup') return `<h1>個股查詢</h1>${searchBox()}<div class="card"><div class="row"><h2 style="margin:0">${code} ${esc(ix[1])}</h2>${typeTag('nosup')}<span class="tag t-none">${MARKET[ix[3]] || ''}</span></div>
    <div class="badbox" style="margin-top:12px"><b>目前不支援這檔。</b>${esc(ix[4])}</div></div>${disc()}`;
  let S; try { S = await loadStock(code); } catch (e) { S = null; }
  if (!S) return `<h1>個股查詢</h1>${searchBox()}<div class="badbox">讀不到 ${code} 的資料。</div>${disc()}`;
  // 主要顯示預設方法(PM,目前是 Stacking);另一個方法(OM)放在比較表當對照
  const PM = DEF, OM = other(DEF);
  const t = S.today, P = t[PM] || {}, O = t[OM] || {}, p = P.pred || 'none', po = O.pred || 'none';
  let pre = '';
  const outHit = trk(PM, 'low').out_pool;
  if (S.status === 'out') pre = `<div class="warnbox"><b>⚠ 這檔不在訓練股票池(${esc(poolDesc())})。</b>判斷照算,但準不準沒有直接驗證過。參考:回放期間池外股票的 ${MNAME[PM]} 判低點命中率 <b>${pct(outHit?.pct)}</b>(${outHit?.n || 0} 筆)。</div>`;
  if (S.status === 'lowvol') pre = `<div class="mutebox"><b>這檔是低波動股,判斷不適用。</b>2020 年起每日漲跌幅中位數 ${fmt(S.move)}%,低於門檻 ${D.meta.rules.min_move}%。這類股票的「11 天最低」常常只差一兩檔,判斷沒有參考價值,研究時已經剔除。
   <details style="margin-top:6px"><summary style="cursor:pointer">仍要看模型輸出</summary><div style="margin-top:6px">${MNAME[PM]}:${LBL[p]}${P.score != null ? `(分數 ${sfmt(PM, P.score)})` : ''};${MNAME[OM]}:${LBL[po]}。</div></details></div>`;
  if (S.status === 'halted') pre = `<div class="badbox"><b>這檔 ${S.date} 沒有交易資料</b>(停牌、處置或資料未更新),今天沒有判斷。</div>`;
  if (S.status === 'nodata') pre = `<div class="mutebox"><b>資料不足</b>,至少要 ${16} 個交易日的 K 線才能判斷。</div>`;
  const dim = S.status === 'lowvol' ? 'opacity:.45;filter:grayscale(1)' : '';
  const last = S.bars[S.bars.length - 1] || [];
  // 池內才有命中率:有信心等級的方法用同等級命中率,沒有的用整體命中率;池外看上方警示的池外命中率
  const hit = S.status !== 'pool' || p === 'none' ? null : HAS_LEVEL[PM] ? trk(PM, p).levels?.[P.level] : trk(PM, p).all;
  const hitWord = HAS_LEVEL[PM] ? `過去 ${MNAME[PM]} 同信心等級(${P.level})的判${LBL[p]}` : `過去 ${MNAME[PM]} 判${LBL[p]}的池內股票`;
  const both = k => po === k && D.track?.both?.[k]?.n ? `今天兩個方法都判${LBL[k]};過去兩方法一致時,<b>${pct(D.track.both[k].pct)}</b> 真的是${LBL[k]}(${D.track.both[k].n} 筆)。` : '';
  const conf = HAS_LEVEL[PM] && P.level ? `,信心 <b>${P.level}</b>` : '';
  const icon = p === 'low' ? '↓' : p === 'high' ? '↑' : '–';
  const sug = !t[PM] ? '今天沒有判斷。' : p === 'low' ? `${MNAME[PM]} 判斷 <b>今天(${md(S.date)})收盤可能是前後 11 天的最低點</b>(分數 ${sfmt(PM, P.score)}${conf})。${hit?.n ? `${hitWord},<b>${pct(hit.pct)}</b> 真的是低點(${hit.n} 筆),其餘大多是普通日子。` : ''}${both('low')}<br><br>
     研究回測的對應規則是 <b>下一個交易日開盤買、第 5 個交易日收盤賣</b>(判低點分數前 3 檔);${btText(PM)}(${esc(PF().pool_label)} ${MNAME[PM]})。
     「低點」只代表 11 天內最低,不代表之後會漲多少。`
    : p === 'high' ? `${MNAME[PM]} 判斷 <b>今天(${md(S.date)})收盤可能是前後 11 天的最高點</b>(分數 ${sfmt(PM, P.score)}${conf})。${hit?.n ? `${hitWord},<b>${pct(hit.pct)}</b> 真的是高點(${hit.n} 筆)。` : ''}${both('high')}<br><br>
     研究沒有回測過「判高點就賣出」的規則,這個判斷只當提醒:短期可能不宜追高。`
    : `${MNAME[PM]} 判斷今天是 <b>非極值</b>(一般日子)。${PM === 'stack' ? `三類機率裡「非極值」最高(${fmt(P.p_none)})。` : '今天收盤若不是近 6 天的最高或最低,就不是候選;是候選但形狀不像過去的真高 / 低點,也會判非極值。'}`;
  const R = (D.research?.classification || []).filter(r => r.year === '2026');
  const rr = mm => R.find(r => r.method === mm) || {};
  const past = (S.signals || []).filter(x => x.main !== 'none' || x.stack !== 'none').slice().reverse().slice(0, 10);
  const cell = (mm, x) => x[mm].pred === 'none' ? '—' : sfmt(mm, x[mm].score) + (HAS_LEVEL[mm] && x[mm].level ? `(信心 ${x[mm].level})` : '');
  const cols = [PM, OM];
  return `<h1>個股查詢</h1>${searchBox()}
  <div class="stack">
  <div class="card"><div class="row"><h2 style="margin:0;font-size:20px">${code} ${esc(S.name)}</h2>${typeTag(S.status)}<div class="sp"></div>
   <div class="right"><span class="px" style="font-size:20px">${fmt(t.close ?? last[4])}</span> ${chg(t.chg_pct)}<div class="lbl">${md(S.date)} 收盤(還原價)</div></div></div></div>
  ${pre}
  ${activeCard(S)}
  ${t[PM] ? `<div class="grid2" style="${dim}">
   <div class="card"><div class="verdict"><div class="vicon" style="background:${p === 'low' ? 'var(--low-bg)' : p === 'high' ? 'var(--high-bg)' : 'var(--mute-bg)'};color:${p === 'low' ? 'var(--low)' : p === 'high' ? 'var(--high)' : 'var(--ink3)'}">${icon}</div>
     <div><div class="lbl">今天的判斷(${MNAME[PM]})</div><div class="vtitle">${p === 'none' ? '非極值・一般日子' : '今天可能是' + LBL[p]}</div>
     ${p !== 'none' ? marks(S.active?.[PM]?.[p], p) : ''}
     ${p !== 'none' ? `<div class="info">分數 ${sfmt(PM, P.score)}${HAS_LEVEL[PM] ? ` ・ 信心 <b>${P.level}</b>` : ''} ・ ${S.status !== 'pool' ? (STATUS[S.status] || ['池外'])[0] + '股票的命中率見上方說明' : HAS_LEVEL[PM] ? lvHit(hit) : allHit(PM, p)}</div>` : ''}
     ${p !== 'none' && p === po ? `<div style="margin-top:4px">${bothTag(p)}</div>` : ''}</div></div>
     <h3 style="margin-top:16px">各類分數</h3>${classBlocks(t)}
     <div class="lbl" style="margin-top:6px">Stacking 是邏輯迴歸機率;主軸分數是 OC-SVM 的 decision_function。兩者不能直接比大小。</div></div>
   <div class="card"><h3>兩方法比較</h3><table class="cmp"><tr><th></th>${cols.map(mm => `<th>${MNAME[mm]}</th>`).join('')}</tr>
     <tr><td>今天判斷</td>${cols.map(mm => `<td><span class="tag ${tagCls(t[mm].pred)}">${LBL[t[mm].pred]}</span></td>`).join('')}</tr>
     <tr><td>分數</td>${cols.map(mm => `<td>${cell(mm, t)}</td>`).join('')}</tr>
     <tr><td>判低點命中率<br><span class="lbl">研究結果 TW100 2026 1–9 月</span></td>${cols.map(mm => `<td>${pct(rr(mm).prec_low)}</td>`).join('')}</tr>
     <tr><td>真低點找到率<br><span class="lbl">研究結果 TW100 2026 1–9 月</span></td>${cols.map(mm => `<td>${pct(rr(mm).rec_low)}</td>`).join('')}</tr>
     <tr><td>這檔判低點對答案<br><span class="lbl">回放 + 實際追蹤</span></td>${cols.map(mm => `<td>${S.low_stats?.[mm]?.n ? `${S.low_stats[mm].hits} / ${S.low_stats[mm].n} 對` : '—'}</td>`).join('')}</tr></table>
     <div class="lbl" style="margin-top:8px">Stacking 判得少;主軸判得多、找到的真低點多。兩者命中率差不多。</div></div>
  </div>` : ''}
  <div class="card" style="${dim}"><div class="row"><h3 style="margin:0">最近 ${innerWidth < 760 ? 30 : 60} 個交易日</h3><div class="sp"></div><span class="lbl">標記 = ${MNAME[PM]}過去的判斷,5 天後對答案</span></div>${kchart(S, PM)}</div>
  <div class="grid2" style="${dim}">
   <div class="card"><h3>說明與建議</h3><div style="font-size:14.5px">${sug}</div>
    <div class="disc" style="margin-top:12px">本頁為研究模型輸出,非投資建議。<a href="#about">免責聲明</a></div></div>
   <div class="card"><h3>這檔過去的判斷</h3>${past.length ? `<div class="tblwrap"><table class="tbl"><tr><th>日期</th>${cols.map(mm => `<th>${MNAME[mm]}</th>`).join('')}<th>結果(${MNAME[PM]})</th><th>t+1 開 → t+5 收</th></tr>
    ${past.map(x => `<tr><td>${md(x.date)}</td>${cols.map(mm => `<td><span class="tag ${tagCls(x[mm])}">${LBL[x[mm]] || '—'}</span></td>`).join('')}
     <td>${x[PM] === 'none' ? '—' : x.truth == null ? '<span class="tag t-wait">待驗證</span>' : x.truth === x[PM] ? '<span class="tag t-ok">對</span>' : `<span class="tag t-bad">錯・實為${LBL[x.truth]}</span>`}</td>
     <td>${x.ret_pct == null ? '—' : sgn(x.ret_pct)}</td></tr>`).join('')}</table></div>` : '<div class="mutebox">最近 60 天沒有判斷紀錄。</div>'}
    <div class="lbl" style="margin-top:6px">報酬已扣成本 ${D.meta.rules.cost_pct}%。判高點的報酬只是參考,研究只回測判低點做多。</div></div>
  </div></div>${disc()}`;
}

/* ---------- 成績追蹤 ---------- */
function pageTrack() {
  const T = trk(TM, TK), dates = D.track.dates || {};
  const series = T.series || [], W = innerWidth < 760 ? 420 : 860, H = innerWidth < 760 ? 240 : 220, top = 14, bot = H - 26;
  let g = '';
  if (series.length > 1) {
    const ymax = Math.max(50, ...series.map(s => s[1])) / 100, y = v => bot - v / ymax * (bot - top), x = i => 40 + i / (series.length - 1) * (W - 50);
    const li = series.findIndex(s => s[2] === 'daily');
    if (li >= 0) g += `<rect x="${x(li)}" y="${top}" width="${x(series.length - 1) - x(li) + 1}" height="${bot - top}" fill="var(--low-bg)" opacity=".7"/><text x="${x(li) + 4}" y="${top + 14}" font-size="11" fill="var(--low)" font-weight="700">實際追蹤</text>`;
    g += `<text x="${li > 0 ? x(li) - 6 : W - 12}" y="${top + 14}" font-size="11" fill="var(--axis)" text-anchor="end">${innerWidth < 760 ? '回放' : '回放(上線前,同一個模型逐日產生)'}</text>`;
    for (let t = 0; t <= ymax + 1e-9; t += .1) g += `<line x1="40" x2="${W - 10}" y1="${y(t)}" y2="${y(t)}" stroke="var(--grid)"/><text x="34" y="${y(t) + 4}" font-size="10" fill="var(--axis)" text-anchor="end">${Math.round(t * 100)}%</text>`;
    const br = (T.base_rate?.pct || 0) / 100;
    g += `<line x1="40" x2="${W - 10}" y1="${y(br)}" y2="${y(br)}" stroke="var(--ink3)" stroke-dasharray="4 3"/><text x="${W - 12}" y="${y(br) - 4}" font-size="10" fill="var(--ink2)" text-anchor="end">隨機猜約 ${pct(T.base_rate?.pct, 0)}</text>`;
    g += `<polyline points="${series.map((s, i) => `${x(i)},${y(s[1] / 100)}`).join(' ')}" fill="none" stroke="${TK === 'low' ? 'var(--low)' : 'var(--high)'}" stroke-width="2"/>`;
    (innerWidth < 760 ? [0, .5, 1] : [0, .25, .5, .75, 1]).forEach(f => { const i = Math.round(f * (series.length - 1)); g += `<text x="${x(i)}" y="${H - 6}" font-size="10" fill="var(--axis)" text-anchor="middle">${md(series[i][0])}</text>`; });
  }
  const R = (D.research?.classification || []).find(r => r.year === '2026' && r.method === TM) || {};
  const k = (lbl, r, extra) => `<div class="card"><div class="lbl">${lbl}</div><div class="kpi">${pct(r?.pct)}</div><div class="info">${r?.n ? `${r.hits} / ${r.n} 檔次` : '尚無資料'}${extra ? ' ・ ' + extra : ''}</div></div>`;
  const lv = T.levels || {}, BH = D.track.both?.[TK];
  return `<div class="row" style="margin-bottom:14px"><div><h1>成績追蹤</h1><p class="sub" style="margin:0">每天的判斷當天就存檔,不會事後修改;5 個交易日後自動對答案。資料 ${dates.first || ''} ~ ${dates.last || ''},已對答案 ${dates.n_graded || 0} 天${dates.live_start ? `,${dates.live_start} 起為實際追蹤` : ',目前都是回放'}。</p></div><div class="sp"></div>
   ${seg(TM, MSEG(), 'TM')} ${seg(TK, [['low', '判低點'], ['high', '判高點']], 'TK')}</div>
  <div class="grid4 k2" style="margin-bottom:16px">
   ${k('近 20 天命中率(前 3 檔)', T.top_20)}${k('近 60 天命中率(前 3 檔)', T.top_60)}
   ${k(`${T.all_ytd?.year || ''} 年命中率(池內全部判斷)`, T.all_ytd, `研究結果 2026 1–9 月 ${pct(TK === 'low' ? R.prec_low : R.prec_high)}`)}
   <div class="card"><div class="lbl">前 3 檔每筆平均報酬(近 60 天)</div><div class="kpi">${sgn(T.top_60?.avg_ret_pct)}</div><div class="info">勝率 ${pct(T.top_60?.win_pct)} ・ t+1 開 → t+5 收,扣成本 ${D.meta.rules.cost_pct}%</div></div>
  </div>
  <div class="card" style="margin-bottom:16px"><div class="row"><h3 style="margin:0">命中率(池內全部判斷,60 天移動)</h3></div>
   ${series.length > 1 ? `<div class="chartwrap"><svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block">${g}</svg></div>` : '<div class="mutebox">對答案的天數還不夠畫圖(至少 20 天)。</div>'}</div>
  <div class="grid2" style="margin-bottom:16px">
   <div class="card"><h3>${HAS_LEVEL[TM] ? '各信心等級的命中率(池內)' : '命中率(池內)'}</h3><table class="tbl lvtable"><tr><th>${HAS_LEVEL[TM] ? '信心' : '判斷'}</th><th>命中率</th><th>對 / 判斷數</th></tr>
    ${HAS_LEVEL[TM] ? ['高', '中', '低'].map(l => `<tr><td>${l}</td><td>${pct(lv[l]?.pct)}</td><td>${lv[l] ? `${lv[l].hits} / ${lv[l].n}` : '—'}</td></tr>`).join('') : ''}
    <tr><td>全部</td><td>${pct(T.all?.pct)}</td><td>${T.all ? `${T.all.hits} / ${T.all.n}` : '—'}</td></tr>
    <tr><td>兩方法一致(Stacking、主軸都判${LBL[TK]})</td><td>${pct(BH?.pct)}</td><td>${BH ? `${BH.hits} / ${BH.n}` : '—'}</td></tr></table>
    <div class="lbl" style="margin-top:6px">${HAS_LEVEL[TM] ? '信心等級 = 訓練期內分數的三等分。' : '主軸不分信心等級:回放期三個等級的命中率幾乎一樣,分等級沒有參考價值。'}「兩方法一致」兩個方法看的是同一批股票日,所以切換方法時數字相同。</div></div>
   <div class="card"><h3>池外與低波動股</h3><table class="tbl lvtable"><tr><th>股票</th><th>命中率</th><th>對 / 判斷數</th></tr>
    <tr><td>池內(參考)</td><td>${pct(T.all?.pct)}</td><td>${T.all ? `${T.all.hits} / ${T.all.n}` : '—'}</td></tr>
    <tr><td>池外</td><td>${pct(T.out_pool?.pct)}</td><td>${T.out_pool ? `${T.out_pool.hits} / ${T.out_pool.n}` : '—'}</td></tr>
    <tr><td>低波動(不適用)</td><td>${pct(T.low_vol?.pct)}</td><td>${T.low_vol ? `${T.low_vol.hits} / ${T.low_vol.n}` : '—'}</td></tr></table>
    <div class="lbl" style="margin-top:6px">低波動股的高低點常常只差一兩檔,命中率高低都沒有參考價值。</div></div></div>
  <div class="card"><h3>每日明細(${TK === 'low' ? '判低點' : '判高點'}前 3 檔)</h3><div class="tblwrap"><table class="tbl"><tr><th>判斷日</th><th>前 3 檔</th><th>結果</th><th>平均報酬</th><th>來源</th></tr>
   ${(T.daily || []).map(r => `<tr><td>${md(r.date)}</td><td>${r.picks.map(p => `<a href="#stock-${p.code}" style="color:inherit">${p.code} ${esc(p.name)}</a>${p.truth == null ? '' : p.truth === TK ? ' <span class="tag t-ok">對</span>' : ' <span class="tag t-bad">錯</span>'}`).join('、')}</td>
    <td>${r.hits == null ? '<span class="tag t-wait">待驗證</span>' : `<span class="tag ${r.hits >= 2 ? 't-ok' : r.hits === 1 ? 't-warn' : 't-bad'}">${r.hits} / ${r.picks.length} 對</span>`}</td>
    <td>${r.avg_ret_pct == null ? '—' : sgn(r.avg_ret_pct)}</td><td><span class="tag ${r.source === 'daily' ? 't-live' : 't-replay'}">${r.source === 'daily' ? '實際' : '回放'}</span></td></tr>`).join('')}</table></div></div>
  ${disc()}`;
}

/* ---------- 研究發現 ---------- */
/* 數字全部來自 findings.json(由 results/ 的結果檔產生,不手抄)。重點:模型適合提醒「哪裡可能是高點、低點」,不適合自動交易。 */
const sg = (x, d = 1) => x == null ? '—' : `${x >= 0 ? '+' : ''}${fmt(x, d)}%`;
function postTable(rows) {
  return `<div class="tblwrap"><table class="tbl"><tr><th>做法</th><th>macro-F1</th><th>判低點<br>每年訊號數</th><th>低點<br>命中率</th><th>低點<br>找到率</th><th>高點<br>命中率</th><th>高點<br>找到率</th><th>只做多前 3 檔回測<br>三年平均(扣成本)</th><th>備註</th></tr>
  ${rows.map(r => `<tr class="${r.future ? 'future' : r.key === 'A0 原始' ? 'base' : ''}"><td>${esc(r.name)}${r.future ? ' <span class="tag t-bad">實際用不了</span>' : ''}</td><td>${pct(r.macro_f1, 2)}</td><td>${fmt(r.n_low, 0)}</td>
   <td>${pct(r.hit_low)}</td><td>${pct(r.rec_low)}</td><td>${pct(r.hit_high)}</td><td>${pct(r.rec_high)}</td><td>${r.bt == null ? '—' : sgn(r.bt)}</td><td class="lbl">${esc(r.future ? '要等整段訊號結束才知道哪天分數最高,用到未來資訊' : r.note)}</td></tr>`).join('')}</table></div>`;
}
function lohiTable(rows) {
  return `<div class="tblwrap"><table class="tbl"><tr><th>做法</th><th>扣成本</th><th>沒扣成本</th><th>筆數</th><th>勝率</th><th>平均持有</th><th>最大回撤</th><th>和等權買進持有差</th></tr>
  ${rows.map(r => `<tr class="${r.future ? 'future' : ''}"><td>${esc(r.name)}${r.future ? ' <span class="tag t-bad">實際用不了</span>' : ''}</td><td>${sgn(r.ret)}</td><td>${sgn(r.gross)}</td><td>${r.n}</td><td>${pct(r.win)}</td><td>${fmt(r.hold, 1)} 天</td><td>${sgn(r.dd)}</td><td>${sg(r.vs, 2)}</td></tr>`).join('')}</table></div>`;
}
function pageFindings() {
  const F = D.findings;
  if (!F) return '<div class="badbox">讀不到研究結果。</div>';
  const C = F.cards[FM], r = C.recall, p = C.precision, f = C.filters, k = C.confirm, lb = F.lohi_base, nm = MNAME[FM];
  const probTxt = f.p7_hit == null ? '' : ` 只留最大機率 ≥ 0.7 / 0.8:命中 ${pct(f.orig_hit)} → ${pct(f.p7_hit)} / ${pct(f.p8_hit)},找到率 ${pct(f.orig_rec)} → ${pct(f.p7_rec)} / ${pct(f.p8_rec)}。`;
  return `<div class="row" style="margin-bottom:6px"><h1 style="margin:0">研究發現</h1><div class="sp"></div><div><div class="lbl" style="margin-bottom:4px">方法</div>${seg(FM, MSEG(), 'FM')}</div></div>
  <p class="sub">這個模型適合<b>提醒你哪裡可能是高點、低點</b>,不適合拿來自動買賣。買不買由你自己決定。
  以下是 ${nm} 的數字(可以切換到另一個方法對照),來自研究結果檔(TW200 168 檔、訓練門檻 0%、2024–2026),沒有重算、沒有手抄。</p>
  <div class="stack">
  <div class="cards">
   <div class="find good"><h3>大方向抓得到</h3><div class="big">${pct(r.low)} <small>真低點當天被提醒</small></div>
    <p>${nm} 對真低點、真高點的找到率是 ${pct(r.low)} / ${pct(r.high)},前後 2 天內算進來是 ${pct(r.low2)} / ${pct(r.high2)}。
    ${F.cards.years.join('、')} 年兩個方法的高點和低點${F.cards.cross === 0 ? '從來沒有判反過' : `判反 ${F.cards.cross} 次`}。</p></div>
   <div class="find bad"><h3>但當天分不出真假</h3><div class="big">${pct(p.low)} <small>判低點裡真的是低點</small></div>
    <p>判低點的命中率不到 3 成(判高點 ${pct(p.high)})。隨便挑一天剛好是低點的機率是 ${pct(p.base_low)},模型好很多,但 10 次還是錯 7 次,錯的大多是普通日子。</p></div>
   <div class="find bad"><h3>分數和機率擋不掉假訊號</h3><div class="big">${pct(f.top50_hit)} <small>只留每天分數前 50% 的命中率</small></div>
    <p>只留分數前 50%:命中 ${pct(f.orig_hit)} → ${pct(f.top50_hit)},找到率卻從 ${pct(f.orig_rec)} 掉到 ${pct(f.top50_rec)};前 10% 只剩 ${pct(f.top10_rec)}。${probTxt}</p></div>
   <div class="find"><h3>等幾天確認能剔除假訊號,但會晚進場</h3><div class="big">${pct(k.k3_hit)} <small>等 3 天沒破底後的命中率</small></div>
    <p>判低點後等 1 天沒破底,命中 ${pct(k.k1_hit)};等 3 天,${pct(k.k3_hit)}。可是買點也晚了,同一批訊號平均每筆少賺 ${fmt(-k.late1, 1)}(晚 1 天)~ ${fmt(-k.late3, 1)} 個百分點(晚 3 天)。
    只做多前 3 檔的回測三年平均:不等 ${sgn(k.bt0)},等 1 / 2 / 3 天 ${sgn(k.bt1)} / ${sgn(k.bt2)} / ${sgn(k.bt3)},沒有變好。</p></div>
  </div>

  <div class="card"><h2>南電(8046)2024:每種做法留下哪些訊號(${nm})</h2>
   <p class="sub">南電 2024 年整年往下跌,是很容易「天天喊低點」的情況。圖上實心 = 判對,空心 = 判錯;點圖可以開原尺寸。</p>
   <div class="figs">${(F.images[FM] || []).map(im => `<figure class="fig"><a href="data/${im.file}" target="_blank" rel="noopener"><img src="data/${im.file}" alt="${esc(im.title)}" loading="lazy"></a>
     <figcaption><b>${esc(im.title)}</b>${im.text.map(t => `<p>${esc(t)}</p>`).join('')}</figcaption></figure>`).join('')}</div></div>

  <div class="card"><h2>減少訊號的做法比較(${nm})</h2>
   <p class="sub">TW200 168 檔、2024–2026 三年平均。命中率 = 判的裡面真的是高 / 低點的比例;找到率 = 真的高 / 低點當天有被判到的比例。</p>
   ${postTable(F.post[FM])}
   <div class="lbl" style="margin-top:6px">「等 k 天確認」的命中率用到判斷日之後 k 天的價格,要等到第 k 天收盤才知道;找到率不變,是因為真低點之後本來就不會破底。回測只算判低點做多。</div></div>

  <div class="card"><h2>Stacking:只留最大機率夠高的訊號</h2>
   <p class="sub">TW200 168 檔、2024–2026 三年平均。判低點那天的最大機率,中位數 ${fmt(F.prob_median['低點'], 3)}(判高點 ${fmt(F.prob_median['高點'], 3)})。主軸沒有機率,沒有這張表。</p>
   <div class="tblwrap"><table class="tbl"><tr><th>門檻</th><th>每年訊號數<br>低 / 高</th><th>命中率<br>低 / 高</th><th>找到率<br>低 / 高</th><th>macro-F1</th></tr>
   ${F.prob.map(x => `<tr><td>${esc(x.name)}</td><td>${fmt(x.n_low, 0)} / ${fmt(x.n_high, 0)}</td><td>${pct(x.hit_low)} / ${pct(x.hit_high)}</td><td>${pct(x.rec_low)} / ${pct(x.rec_high)}</td><td>${pct(x.macro_f1, 2)}</td></tr>`).join('')}</table></div>
   <div class="lbl" style="margin-top:6px">門檻越高,命中率只升一點點,找到率卻大降;≥ 0.9 幾乎沒有訊號。</div></div>

  <div class="card"><h2>${lb.n_stocks} 檔、${lb.year}:低點進場、高點出場(${nm})</h2>
   <p class="sub">最多同時持有 3 檔,訊號隔天開盤成交,持有到判高點隔天開盤賣出,成本 0.585%。對照:${lb.n_stocks} 檔等權買進持有 <b>${sgn(lb.buy_hold, 2)}</b>;
   研究原本的「前 3 檔持有 5 天」Stacking ${sgn(lb.top3['Stacking 邏輯迴歸'], 2)}、主軸 ${sgn(lb.top3['主軸'], 2)}。</p>
   ${lohiTable(F.lohi[FM])}
   <div class="lbl" style="margin-top:6px">「真實標籤」是事先知道答案的上限,「事後最高分」要等整段訊號結束才知道;兩列都用到未來資訊,實際用不了。</div></div>

  <div class="card"><h2>所以網頁怎麼用</h2>
   <ol class="uselist">
    <li><b>判斷當提醒,不當買賣指令。</b>它告訴你「這裡可能是近期低點 / 高點,值得看一下」,買不買由你自己決定。</li>
    <li><b>看「已幾天沒破底 / 沒創高」。</b>今日判斷會把判低點分成剛出現、已 1–2 天、已 3 天以上沒破底。天數越多越可能是真的低點,但也越晚。</li>
    <li><b>機率和分數只當參考。</b>研究顯示只挑機率高或分數高的,命中率只升一點點,卻會漏掉更多真的低點。</li>
    <li><b>5 天後對答案。</b>每天的判斷都會存檔,5 個交易日後在<a href="#track">成績追蹤</a>看對了多少。</li>
   </ol></div>
  <div class="lbl">資料來源:method_kline_peak/results/ 的 ${F.sources.map(esc).join('、')}。</div>
  </div>${disc()}`;
}

/* ---------- 方法與說明 ---------- */
function pageAbout() {
  const bars = [42, 46, 40, 37, 33, 28, 35, 39, 44, 47, 45].map((h, i) => `<i class="${i === 5 ? 't' : i < 5 ? '' : 'f'}" style="height:${h * 2}px"></i>`).join('');
  const ord = m => m === DEF ? 0 : 1;                                       // 預設方法(Stacking)排前面
  const C = (D.research?.classification || []).slice().sort((a, b) => ord(a.method) - ord(b.method) || a.year.localeCompare(b.year));
  const B = (D.research?.backtest || []).slice().sort((a, b) => a.pool.localeCompare(b.pool) || ord(a.method) - ord(b.method));
  const mi = D.meta.model || {};
  return `<h1>方法與說明</h1><p class="sub">本頁的命中率與回測數字是<b>研究結果</b>,直接讀 repo 裡的結果檔(${(D.research?.sources || []).map(esc).join('、')}),沒有重算。</p>
  <div class="stack">
  <div class="card"><h2>「高點」「低點」是什麼意思</h2>
   <div class="grid2"><div><div class="label-demo">${bars}</div><div class="legend"><span>t−5 … t−1</span><span style="color:var(--low);font-weight:700">t(今天)</span><span>t+1 … t+5(要等 5 天)</span></div></div>
   <div style="font-size:14px">看 11 天:今天(第 6 天)加前後各 5 天。<br>・今天收盤是 11 天<b>最低</b> → 低點<br>・今天收盤是 11 天<b>最高</b> → 高點<br>・其他 → 非極值(約 85% 的日子)<br><br>
   模型只看今天和前 5 天的 6 根 K 線,所以收盤後就能判斷;但真正的答案要等 5 個交易日後才知道。</div></div></div>
  <div class="card"><h2>兩個方法</h2><p class="sub" style="margin-bottom:10px">網站預設顯示 ② Stacking;① 主軸保留當對照,各頁都可以切換過去。</p><div class="steps">
   <div class="step"><b>② Stacking(預設)</b>高點、低點各一組 AE + OC-SVM,對每一天打分數;再把兩個分數交給邏輯迴歸,輸出高點 / 低點 / 非極值三類機率,最大的那類就是判斷。不靠規則,判得比較少。</div>
   <div class="step"><b>Stacking 的信心等級</b>判高點 / 低點那天的機率,依訓練期分布切成高 / 中 / 低三等;成績追蹤會列出各等級實際命中多少。</div>
   <div class="step"><b>① 主軸(對照)</b>先用規則挑候選(今天收盤是近 6 天最高 / 最低),再用同樣的 AE + OC-SVM 檢查形狀像不像過去的真高 / 低點。判得多、找到的真高低點多,命中率和 Stacking 差不多。</div></div>
   <div class="lbl" style="margin-top:8px">特徵:6 根 K 線的開高低收 ÷ 今天收盤、量 ÷ 10 日均量,共 29 個數字。目前的模型:${mi.year} 年用,訓練 ${(mi.train || []).join(' ~ ')}(${fmt(mi.n_train, 0)} 筆),股票池 ${esc(poolDesc())},訓練門檻 ${PF().train_min_amp || 0}%,種子 ${mi.seed}。每年 1 月第 6 個交易日後自動重訓。</div></div>
  <div class="card"><h2>歷史命中率(研究結果,TW100 剔除低波動股)</h2><div class="tblwrap"><table class="tbl">
   <tr><th>方法</th><th>年</th><th>macro-F1</th><th>判低點命中</th><th>判高點命中</th><th>真低點找到</th><th>真高點找到</th><th>隨機猜中低點</th></tr>
   ${C.map(r => `<tr><td>${MNAME[r.method]}</td><td>${r.year}${r.year === '2026' ? '(1–9 月)' : ''}</td><td>${pct(r.macro_f1, 2)}</td><td>${pct(r.prec_low)}</td><td>${pct(r.prec_high)}</td><td>${pct(r.rec_low)}</td><td>${pct(r.rec_high)}</td><td>${pct(r.base_low)}</td></tr>`).join('')}</table></div>
   <div class="lbl" style="margin-top:6px">Stacking 判得少,找到的真低點也少;主軸判得多、找到的多,命中率差不多。兩個方法都沒有把高點判成低點(或反過來),錯的都是和非極值混淆。</div></div>
  <div class="card"><h2>回測摘要(研究結果,扣成本 0.585%)</h2>
   <div class="lbl" style="margin-bottom:6px">規則:只做多、判低點分數前 3 檔、每檔 1/3 資金、t+1 開盤買、t+5 收盤賣、每年獨立 100 萬。</div>
   <div class="tblwrap"><table class="tbl"><tr><th>股票池</th><th>方法</th>${[...new Set(B.map(b => b.year))].map(y => `<th>${y}${y === '2026' ? '(1–9 月)' : ''}</th>`).join('')}</tr>
   ${[...new Set(B.map(b => b.pool + '|' + b.method))].map(k => { const [pool, m] = k.split('|'); return `<tr><td>${pool}</td><td>${MNAME[m]}</td>${B.filter(b => b.pool === pool && b.method === m).map(b => `<td>${sgn(b.ret_pct)}</td>`).join('')}</tr>`; }).join('')}</table></div>
   <div class="lbl" style="margin-top:6px">每年起伏很大,多數組合扣成本後是虧的。紅色 = 賺,綠色 = 虧(台股慣例)。</div></div>
  <div class="card"><h2>常見問題</h2><div style="font-size:14px">
   <p><b>判低點就會漲嗎?</b> 不一定。低點只代表 11 天內最低,之後可能只是小反彈。</p>
   <p><b>為什麼盤中查到的是昨天的判斷?</b> 判斷要用收盤價,每天 18:00 左右更新。</p>
   <p><b>為什麼價格和看盤軟體不一樣?</b> 這裡用還原價(把除權息補回去),和訓練時一致。</p>
   <p><b>為什麼有些股票顯示「不適用」?</b> 每日漲跌幅中位數低於 ${D.meta.rules.min_move}% 的股票,高低點常常只差一兩檔,研究時已剔除。</p>
   <p><b>過去的判斷會變嗎?</b> 不會。每天的判斷當天就存檔,之後不重算;除權息後還原價變動也不影響已存的判斷。</p></div></div>
  <div class="badbox" id="disclaimer"><b>免責聲明</b><br>本網站為個人學術研究之模型輸出展示,非證券投資顧問服務,不構成任何買賣建議或推介。
   模型歷史命中率約 3 成,依研究回測規則操作在多數年度扣除成本後為虧損。投資有風險,請自行判斷並承擔損益。本網站不收取任何費用,亦無廣告或任何形式之報酬。</div>
  </div>`;
}

/* ---------- 路由 ---------- */
const NAV = [['today', '今日判斷', 'M3 12h4l3-8 4 16 3-8h4'], ['stock', '個股查詢', 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9 16-4-4'], ['track', '成績追蹤', 'M4 20V10m6 10V4m6 16v-7m4 7H2'], ['findings', '研究發現', 'M9 3h6m-5 0v6L4 19a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2l-6-10V3'], ['about', '方法與說明', 'M12 8h.01M11 12h1v5h1M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z']];
function go(h) { location.hash = h; }
function header() {
  const M = D.meta, c = M.check || {};
  document.getElementById('hmeta').innerHTML = `判斷基準日 <b>${dlabel(M.asof)}收盤</b> ・ 產生於 ${esc((M.created || '').slice(5, 16))}<br>模型:訓練 ${(M.model?.train || []).map(d => d.slice(0, 4)).join('–')} ・ 股票池 ${esc(poolDesc())}`;
  const b = [];
  if (c.stale) b.push(`<div class="badbox"><b>今天的資料還沒更新。</b>畫面是 ${M.asof} 的判斷;資料來源晚到時批次會在稍後補跑。</div>`);
  if ((c.missing_pool || []).length) b.push(`<div class="warnbox">股票池有 ${c.missing_pool.length} 檔沒有 ${M.asof} 的資料(${c.missing_pool.slice(0, 8).join('、')}${c.missing_pool.length > 8 ? '…' : ''}),這幾檔今天沒有判斷。</div>`);
  if (M.source === 'replay') b.push(`<div class="mutebox">目前顯示的是<b>回放資料</b>:上線前用同一個模型逐日產生的判斷。</div>`);
  if (c.online === false && M.source !== 'replay') b.push(`<div class="mutebox">這次批次沒有連網,K 線只到 ${M.asof}。</div>`);
  document.getElementById('banner').innerHTML = b.join('');
}
async function render() {
  // 路由只用英數與連字號(Artifact 的網址只保留單純的 #名稱):#today、#stock、#stock-2330、#track、#findings、#about
  const h = location.hash.slice(1) || 'today', p = h.split('-')[0], arg = h.slice(p.length + 1);
  document.getElementById('topnav').innerHTML = NAV.map(([k, n]) => `<a href="#${k}" class="${p === k ? 'on' : ''}">${n}</a>`).join('');
  document.getElementById('botnav').innerHTML = NAV.map(([k, n, d]) => `<a href="#${k}" class="${p === k ? 'on' : ''}"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"/></svg>${n}</a>`).join('');
  const app = document.getElementById('app');
  try {
    app.innerHTML = p === 'stock' ? (arg ? await pageStock(arg) : pageSearch()) : p === 'track' ? pageTrack() : p === 'findings' ? pageFindings()
      : p === 'about' ? pageAbout() : pageToday();
  } catch (e) { app.innerHTML = `<div class="badbox">畫面產生失敗:${esc(e.message)}</div>`; console.error(e); }
  if (p === 'stock' && arg) Q = '';
}
async function boot() {
  try {
    [D.meta, D.today, D.track, D.research, D.index, D.findings] = await Promise.all(['meta', 'today', 'track', 'research', 'index', 'findings'].map(n => j(`data/${n}.json`)));
    DEF = METHOD = TM = FM = D.meta.default_method || 'stack';
    header();
  } catch (e) {
    document.getElementById('app').innerHTML = `<div class="badbox"><b>還沒有資料。</b>請先執行每日批次:<code>python method_kline_peak/web/run.py daily</code>(${esc(e.message)})</div>`;
    return;
  }
  render();
}
window.addEventListener('hashchange', () => { render(); window.scrollTo(0, 0); });
document.addEventListener('click', e => { if (!e.target.closest('.search')) document.getElementById('ac')?.classList.remove('show'); });
boot();
