/* K 線高低點判斷:靜態前端。資料全部來自 data/*.json(每日批次產生)。 */
const D = {};
const LBL = {low: '低點', high: '高點', none: '非極值'};
const MNAME = {main: '① 主軸', stack: '② Stacking'};
const STATUS = {pool: ['池內', 't-ok'], out: ['池外', 't-warn'], lowvol: ['低波動', 't-none'], nosup: ['不支援', 't-bad'], nodata: ['資料不足', 't-none'], halted: ['今日無交易', 't-none']};
const MARKET = {TWSE: '上市', OTC: '上櫃', ESB: '興櫃', ETF: 'ETF'};
let METHOD = 'main', TM = 'main', TK = 'low', Q = '';

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
function researchBT(method, pool = 'TW100 73 檔') {
  return (D.research?.backtest || []).filter(r => r.pool === pool && r.method === method).sort((a, b) => a.year.localeCompare(b.year));
}
function btText(method) {
  const r = researchBT(method);
  return `${r.map(x => x.year + (x.year === '2026' ? '(1–9 月)' : '')).join(' / ')} 扣成本為 <b>${r.map(x => (x.ret_pct >= 0 ? '+' : '') + fmt(x.ret_pct, 1) + '%').join(' / ')}</b>`;
}
function trk(method, kind) { return D.track?.methods?.[method]?.[kind] || {}; }
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
function pickRow(s, i, kind) {
  const color = kind === 'low' ? 'var(--low)' : 'var(--high)';
  return `<div class="pick" onclick="go('stock/${s.code}')"><div class="rank">${i + 1}</div>
  <div><div class="nm">${s.code}<span>${esc(s.name)}</span> ${s.both ? '<span class="tag t-both">兩方法一致</span>' : ''}</div>
  <div class="info">分數 ${fmt(s.score, METHOD === 'main' ? 1 : 2)} ・ 信心 <b>${s.level || '—'}</b> ・ ${lvHit(s.level_hit)}</div></div>
  <div class="right"><div class="px">${fmt(s.close)}</div>${chg(s.chg_pct)}<div class="hide-m">${spark(s.spark)}</div></div></div>`;
}
function listCard(kind) {
  const L = D.today.methods[METHOD][kind] || [], top = L.slice(0, 3), rest = L.slice(3), isLow = kind === 'low';
  return `<div class="card"><div class="listhead"><span class="dot" style="background:${isLow ? 'var(--low)' : 'var(--high)'}"></span>
  <h2 style="margin:0">${isLow ? '判低點' : '判高點'} 前 3 檔</h2><span class="lbl">今天共 ${L.length} 檔,依分數排序</span></div>
  <div class="lbl" style="margin:-4px 0 6px">${isLow ? '今天收盤可能是前後 11 天最低' : '今天收盤可能是前後 11 天最高 ── 只當提醒,研究沒有回測過賣出規則'}</div>
  ${top.length ? top.map((s, i) => pickRow(s, i, kind)).join('') : '<div class="mutebox">今天沒有股票被判為' + LBL[kind] + '。</div>'}
  ${rest.length ? `<details class="more"><summary>還有 ${rest.length} 檔也${isLow ? '判低點' : '判高點'}(分數較低)</summary>
  <table class="minitable"><tr><th>代號</th><th>名稱</th><th>收盤</th><th>分數</th><th>信心</th></tr>
  ${rest.map(s => `<tr onclick="go('stock/${s.code}')" style="cursor:pointer"><td>${s.code}</td><td>${esc(s.name)}</td><td>${fmt(s.close)}</td><td>${fmt(s.score, METHOD === 'main' ? 1 : 2)}</td><td>${s.level || '—'}</td></tr>`).join('')}</table></details>` : ''}</div>`;
}
function pageToday() {
  const T = D.today, lo = T.methods[METHOD].low || [], hi = T.methods[METHOD].high || [];
  const t60 = trk(METHOD, 'low').top_60 || {}, base = trk(METHOD, 'low').base_rate || {};
  return `<div class="row" style="margin-bottom:14px"><div><h1>今日判斷</h1>
  <p class="sub" style="margin:0">${dlabel(T.date)} 收盤後,模型對股票池 ${T.n_pool} 檔的判斷。答案要再過 5 個交易日收盤才知道。</p></div>
  <div class="sp"></div><div><div class="lbl" style="margin-bottom:4px">方法</div>${seg(METHOD, [['main', '① 主軸'], ['stack', '② Stacking']], 'METHOD')}</div></div>
  <div class="summary">
   <div class="card"><div class="lbl">判低點</div><div class="kpi" style="color:var(--low)">${lo.length} <small>檔</small></div></div>
   <div class="card"><div class="lbl">判高點</div><div class="kpi" style="color:var(--high)">${hi.length} <small>檔</small></div></div>
   <div class="card"><div class="lbl">兩方法一致(低 / 高)</div><div class="kpi" style="color:#5a3fc0">${T.both.low} / ${T.both.high} <small>檔</small></div></div>
   <div class="card"><div class="lbl">${MNAME[METHOD]} 判低點前 3 檔命中率(近 60 天)</div><div class="kpi">${pct(t60.pct)} <small>隨機約 ${pct(base.pct, 0)}</small></div></div>
  </div>
  <div class="grid2">${listCard('low')}${listCard('high')}</div>
  <div class="note" style="margin-top:16px"><b>怎麼看這份清單</b><br>
  「判低點」10 次大約只有 3 次真的是低點,錯的大多是普通日子。研究回測的規則是:<b>判低點分數前 3 檔、下一個交易日開盤買、第 5 個交易日收盤賣</b>,
  ${btText(METHOD)}(研究結果,TW100 ${MNAME[METHOD]})。分數只在同一個方法裡比大小。<a href="#about">看完整說明</a></div>
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
  return `<div class="chips">${list.map(([c, n]) => `<span class="chip" onclick="go('stock/${c}')">${c} ${esc(n)}</span>`).join('')}</div>`;
}
function searchBox() {
  return `<div class="search"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#8a929c" stroke-width="2.2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
  <input id="q" placeholder="輸入代號或名稱,例如 2330 或 台積" autocomplete="off" value="${esc(Q)}" oninput="ac(this.value)" onfocus="ac(this.value)" onkeydown="acKey(event)"><div class="ac" id="ac"></div></div>${chips()}`;
}
let ACSEL = 0, ACL = [];
function ac(v) {
  Q = v; const el = document.getElementById('ac'); v = v.trim(); if (!v) { el.classList.remove('show'); return; }
  const idx = D.index || [];
  ACL = idx.filter(r => r[0].startsWith(v)).concat(idx.filter(r => !r[0].startsWith(v) && r[1].includes(v))).slice(0, 8); ACSEL = 0;
  el.innerHTML = ACL.length ? ACL.map((r, i) => `<div class="${i === 0 ? 'sel' : ''}" onmousedown="go('stock/${r[0]}')"><span class="code">${r[0]}</span><span class="sp">${esc(r[1])}</span>${r[2] === 'nosup' ? `<span class="tag t-bad">${MARKET[r[3]] || '不支援'}</span>` : typeTag(r[2])}</div>`).join('')
    : '<div style="color:var(--ink3)">找不到。目前只支援上市普通股</div>';
  el.classList.add('show');
}
function acKey(e) {
  const el = document.getElementById('ac'); if (!ACL.length) return;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { ACSEL = (ACSEL + (e.key === 'ArrowDown' ? 1 : -1) + ACL.length) % ACL.length; [...el.children].forEach((d, i) => d.classList.toggle('sel', i === ACSEL)); e.preventDefault(); }
  if (e.key === 'Enter') go('stock/' + ACL[ACSEL][0]);
}
function kchart(S) {
  const M = innerWidth < 760, bars = S.bars.slice(M ? -30 : -60);
  if (!bars.length) return '<div class="mutebox">沒有 K 線資料</div>';
  const sig = Object.fromEntries((S.signals || []).map(s => [s.date, s]));
  const W = M ? 420 : 860, H = M ? 320 : 300, VH = 50, pad = 8, top = 22, bot = H - VH - 24;
  const mx = Math.max(...bars.map(b => b[2])) * 1.015, mn = Math.min(...bars.map(b => b[3])) * 0.985, y = v => top + (mx - v) / (mx - mn) * (bot - top);
  const bw = (W - pad * 2) / bars.length, vmax = Math.max(...bars.map(b => b[5])) || 1; let g = '';
  for (let k = 0; k < 4; k++) { const v = mn + (mx - mn) * k / 3; g += `<line x1="0" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="#eef0f3"/><text x="2" y="${y(v) - 3}" font-size="10" fill="#8a929c">${fmt(v, 1)}</text>`; }
  bars.forEach((b, i) => {
    const [d, o, h, l, c, v] = b, x = pad + i * bw + bw / 2, col = c >= o ? 'var(--up)' : 'var(--down)';
    g += `<line x1="${x}" x2="${x}" y1="${y(h)}" y2="${y(l)}" stroke="${col}"/><rect x="${x - bw * .34}" y="${y(Math.max(o, c))}" width="${bw * .68}" height="${Math.max(1, Math.abs(y(o) - y(c)))}" fill="${col}"/>`;
    g += `<rect x="${x - bw * .34}" y="${H - 24 - v / vmax * VH}" width="${bw * .68}" height="${v / vmax * VH}" fill="${col}" opacity=".35"/>`;
    const s = sig[d];
    if (s && s.main && s.main !== 'none') {
      const isL = s.main === 'low', c2 = isL ? 'var(--low)' : 'var(--high)', yy = isL ? y(l) + 11 : y(h) - 11;
      const st = s.truth == null ? 'wait' : s.truth === s.main ? 'ok' : 'bad';
      const tri = isL ? `M${x - 5},${yy + 4} L${x + 5},${yy + 4} L${x},${yy - 4} Z` : `M${x - 5},${yy - 4} L${x + 5},${yy - 4} L${x},${yy + 4} Z`;
      g += `<path d="${tri}" fill="${st === 'ok' ? c2 : '#fff'}" stroke="${c2}" stroke-width="1.5" ${st === 'wait' ? 'stroke-dasharray="2 1.5"' : ''}><title>${d} 判${LBL[s.main]}:${st === 'wait' ? '待驗證' : st === 'ok' ? '對' : '錯'}</title></path>`;
      if (st === 'bad') g += `<text x="${x}" y="${isL ? yy + 16 : yy - 8}" font-size="9" fill="var(--bad)" text-anchor="middle">✕</text>`;
    }
    if (i === bars.length - 1) g += `<rect x="${x - bw / 2}" y="${top - 6}" width="${bw}" height="${bot - top + 12}" fill="var(--accent)" opacity=".06"/><text x="${x - bw}" y="${top - 9}" font-size="10" font-weight="700" fill="var(--accent)" text-anchor="end">今天 ▸</text>`;
  });
  const ticks = M ? [0, 10, 20, bars.length - 1] : [0, 15, 30, 45, bars.length - 1];
  ticks.filter(i => i < bars.length).forEach(i => g += `<text x="${pad + i * bw + bw / 2}" y="${H - 8}" font-size="10" fill="#8a929c" text-anchor="middle">${md(bars[i][0])}</text>`);
  return `<div class="chartwrap"><svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block">${g}</svg></div>
  <div class="legend"><span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="var(--low)"/></svg>判低點・對</span><span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="#fff" stroke="var(--low)" stroke-width="1.4"/></svg>判低點・錯(✕)</span>
  <span><svg width="12" height="10"><path d="M1,1 L11,1 L6,9Z" fill="var(--high)"/></svg>判高點・對</span><span><svg width="12" height="10"><path d="M1,1 L11,1 L6,9Z" fill="#fff" stroke="var(--high)" stroke-width="1.4" stroke-dasharray="2 1.5"/></svg>虛線 = 待驗證(未滿 5 天)</span>
  <span>K 線為還原價,紅漲綠跌 ・ 標記為 ① 主軸的判斷</span></div>`;
}
function bar(label, v, color, txt) {
  return `<div class="cls"><span>${label}</span><div class="bar" style="margin:0;height:8px"><i style="width:${Math.max(0, Math.min(1, v)) * 100}%;background:${color}"></i></div><span class="right">${txt}</span></div>`;
}
function classBlocks(t) {
  const m = t.main || {}, s = t.stack || {};
  const ocs = (v, cut) => v == null ? '—' : (v > 0 ? '範圍內 ' : '範圍外 ') + fmt(v, 1);
  return `<div class="grid2" style="gap:14px"><div><div class="lbl">① 主軸:兩個 OC-SVM 的分數</div>
    <div class="cls"><span>高點</span><span style="grid-column:span 2" class="num">${ocs(m.s_high)}</span></div>
    <div class="cls"><span>低點</span><span style="grid-column:span 2" class="num">${ocs(m.s_low)}</span></div>
    <div class="lbl" style="margin-top:4px">只有收盤創近 6 天新高(新低)時才看高點(低點)分數;> 0 才判高點(低點)。</div></div>
    <div><div class="lbl">② Stacking:三類機率</div>
    ${bar('高點', s.p_high, 'var(--high)', fmt(s.p_high))}${bar('低點', s.p_low, 'var(--low)', fmt(s.p_low))}${bar('非極值', s.p_none, '#9aa3ad', fmt(s.p_none))}</div></div>`;
}
function pageSearch() {
  return `<h1>個股查詢</h1><p class="sub">輸入上市股票代號或名稱。池內 ${D.meta.counts.pool} 檔有完整驗證;池外股票會顯示警示;低波動股不適用。</p>${searchBox()}
  <div class="grid4 k2">${[['池內', 't-ok', `${D.meta.counts.pool} 檔,模型訓練用的股票`], ['池外', 't-warn', `${D.meta.counts.out} 檔,可查,但判斷沒有驗證過`], ['低波動', 't-none', `${D.meta.counts.lowvol} 檔,每日漲跌太小,判斷不適用`], ['不支援', 't-bad', 'ETF、上櫃、興櫃、特別股']].map(([a, c, d]) => `<div class="card"><span class="tag ${c}">${a}</span><div class="info" style="margin-top:6px">${d}</div></div>`).join('')}</div>${disc()}`;
}
async function pageStock(code) {
  const ix = (D.index || []).find(r => r[0] === code);
  if (!ix) return `<h1>個股查詢</h1>${searchBox()}<div class="badbox">查無代號 ${esc(code)}。目前只支援上市普通股。</div>${disc()}`;
  if (ix[2] === 'nosup') return `<h1>個股查詢</h1>${searchBox()}<div class="card"><div class="row"><h2 style="margin:0">${code} ${esc(ix[1])}</h2>${typeTag('nosup')}<span class="tag t-none">${MARKET[ix[3]] || ''}</span></div>
    <div class="badbox" style="margin-top:12px"><b>目前不支援這檔。</b>${esc(ix[4])}</div></div>${disc()}`;
  let S; try { S = await j(`data/stocks/${code}.json`); } catch (e) { return `<h1>個股查詢</h1>${searchBox()}<div class="badbox">讀不到 ${code} 的資料。</div>${disc()}`; }
  const t = S.today, m = t.main || {}, s = t.stack || {}, p = m.pred || 'none', ps = s.pred || 'none';
  let pre = '';
  const outHit = trk('main', 'low').out_pool;
  if (S.status === 'out') pre = `<div class="warnbox"><b>⚠ 這檔不在訓練股票池(TW100 剔除低波動股,${D.meta.counts.pool} 檔)。</b>判斷照算,但準不準沒有直接驗證過。參考:回放期間池外股票的判低點命中率 <b>${pct(outHit?.pct)}</b>(${outHit?.n || 0} 筆)。</div>`;
  if (S.status === 'lowvol') pre = `<div class="mutebox"><b>這檔是低波動股,判斷不適用。</b>2020 年起每日漲跌幅中位數 ${fmt(S.move)}%,低於門檻 ${D.meta.rules.min_move}%。這類股票的「11 天最低」常常只差一兩檔,判斷沒有參考價值,研究時已經剔除。
   <details style="margin-top:6px"><summary style="cursor:pointer">仍要看模型輸出</summary><div style="margin-top:6px">主軸:${LBL[p]}${m.score != null ? `(分數 ${fmt(m.score, 1)})` : ''};Stacking:${LBL[ps]}。</div></details></div>`;
  if (S.status === 'halted') pre = `<div class="badbox"><b>這檔 ${S.date} 沒有交易資料</b>(停牌、處置或資料未更新),今天沒有判斷。</div>`;
  if (S.status === 'nodata') pre = `<div class="mutebox"><b>資料不足</b>,至少要 ${16} 個交易日的 K 線才能判斷。</div>`;
  const dim = S.status === 'lowvol' ? 'opacity:.45;filter:grayscale(1)' : '';
  const last = S.bars[S.bars.length - 1] || [];
  const hit = S.status === 'pool' ? trk('main', p).levels?.[m.level] : null;   // 等級命中率只統計池內;池外看上方警示的池外命中率
  const icon = p === 'low' ? '↓' : p === 'high' ? '↑' : '–';
  const sug = !t.main ? '今天沒有判斷。' : p === 'low' ? `模型判斷 <b>今天(${md(S.date)})收盤可能是前後 11 天的最低點</b>,信心 <b>${m.level}</b>(分數 ${fmt(m.score, 1)})。${hit?.n ? `過去同等級的判低點,<b>${pct(hit.pct)}</b> 真的是低點(${hit.n} 筆),其餘大多是普通日子。` : ''}<br><br>
     研究回測的對應規則是 <b>下一個交易日開盤買、第 5 個交易日收盤賣</b>(判低點分數前 3 檔);${btText('main')}(TW100 主軸)。
     「低點」只代表 11 天內最低,不代表之後會漲多少。`
    : p === 'high' ? `模型判斷 <b>今天(${md(S.date)})收盤可能是前後 11 天的最高點</b>,信心 <b>${m.level}</b>(分數 ${fmt(m.score, 1)})。${hit?.n ? `過去同等級的判高點,<b>${pct(hit.pct)}</b> 真的是高點(${hit.n} 筆)。` : ''}<br><br>
     研究沒有回測過「判高點就賣出」的規則,這個判斷只當提醒:短期可能不宜追高。`
    : `模型判斷今天是 <b>非極值</b>(一般日子)。${m.s_high == null ? '' : '今天收盤若不是近 6 天的最高或最低,就不是候選;是候選但形狀不像過去的真高 / 低點,也會判非極值。'}`;
  const R = (D.research?.classification || []).filter(r => r.year === '2026');
  const rr = mm => R.find(r => r.method === mm) || {};
  const past = (S.signals || []).filter(x => x.main !== 'none' || x.stack !== 'none').slice().reverse().slice(0, 10);
  return `<h1>個股查詢</h1>${searchBox()}
  <div class="stack">
  <div class="card"><div class="row"><h2 style="margin:0;font-size:20px">${code} ${esc(S.name)}</h2>${typeTag(S.status)}<div class="sp"></div>
   <div class="right"><span class="px" style="font-size:20px">${fmt(t.close ?? last[4])}</span> ${chg(t.chg_pct)}<div class="lbl">${md(S.date)} 收盤(還原價)</div></div></div></div>
  ${pre}
  ${t.main ? `<div class="grid2" style="${dim}">
   <div class="card"><div class="verdict"><div class="vicon" style="background:${p === 'low' ? 'var(--low-bg)' : p === 'high' ? 'var(--high-bg)' : 'var(--mute-bg)'};color:${p === 'low' ? 'var(--low)' : p === 'high' ? 'var(--high)' : 'var(--ink3)'}">${icon}</div>
     <div><div class="lbl">今天的判斷(① 主軸)</div><div class="vtitle">${p === 'none' ? '非極值・一般日子' : '今天可能是' + LBL[p]}</div>
     ${p !== 'none' ? `<div class="info">信心 <b>${m.level}</b> ・ 分數 ${fmt(m.score, 1)} ・ ${S.status === 'pool' ? lvHit(hit) : (STATUS[S.status] || ['池外'])[0] + '股票沒有分等級的命中率'}</div>` : ''}
     ${p !== 'none' && p === ps ? '<div style="margin-top:4px"><span class="tag t-both">兩方法一致</span></div>' : ''}</div></div>
     <h3 style="margin-top:16px">各類分數</h3>${classBlocks(t)}
     <div class="lbl" style="margin-top:6px">主軸分數是 OC-SVM 的 decision_function;Stacking 是邏輯迴歸機率。兩者不能直接比大小。</div></div>
   <div class="card"><h3>兩方法比較</h3><table class="cmp"><tr><th></th><th>① 主軸</th><th>② Stacking</th></tr>
     <tr><td>今天判斷</td><td><span class="tag ${tagCls(p)}">${LBL[p]}</span></td><td><span class="tag ${tagCls(ps)}">${LBL[ps]}</span></td></tr>
     <tr><td>分數 / 信心</td><td>${p === 'none' ? '—' : fmt(m.score, 1) + ' / ' + m.level}</td><td>${ps === 'none' ? '—' : fmt(s.score) + ' / ' + s.level}</td></tr>
     <tr><td>判低點命中率<br><span class="lbl">研究結果 2026 1–9 月</span></td><td>${pct(rr('main').prec_low)}</td><td>${pct(rr('stack').prec_low)}</td></tr>
     <tr><td>真低點找到率<br><span class="lbl">研究結果 2026 1–9 月</span></td><td>${pct(rr('main').rec_low)}</td><td>${pct(rr('stack').rec_low)}</td></tr>
     <tr><td>這檔判低點對答案<br><span class="lbl">回放 + 實際追蹤</span></td><td>${S.low_stats?.main?.n ? `${S.low_stats.main.hits} / ${S.low_stats.main.n} 對` : '—'}</td><td>${S.low_stats?.stack?.n ? `${S.low_stats.stack.hits} / ${S.low_stats.stack.n} 對` : '—'}</td></tr></table>
     <div class="lbl" style="margin-top:8px">主軸判得多、找到的真低點多;Stacking 判得少。兩者命中率差不多。</div></div>
  </div>` : ''}
  <div class="card" style="${dim}"><div class="row"><h3 style="margin:0">最近 ${innerWidth < 760 ? 30 : 60} 個交易日</h3><div class="sp"></div><span class="lbl">標記 = 主軸過去的判斷,5 天後對答案</span></div>${kchart(S)}</div>
  <div class="grid2" style="${dim}">
   <div class="card"><h3>說明與建議</h3><div style="font-size:14.5px">${sug}</div>
    <div class="disc" style="margin-top:12px">本頁為研究模型輸出,非投資建議。<a href="#about">免責聲明</a></div></div>
   <div class="card"><h3>這檔過去的判斷</h3>${past.length ? `<div class="tblwrap"><table class="tbl"><tr><th>日期</th><th>主軸</th><th>Stacking</th><th>結果(主軸)</th><th>t+1 開 → t+5 收</th></tr>
    ${past.map(x => `<tr><td>${md(x.date)}</td><td><span class="tag ${tagCls(x.main)}">${LBL[x.main] || '—'}</span></td><td><span class="tag ${tagCls(x.stack)}">${LBL[x.stack] || '—'}</span></td>
     <td>${x.main === 'none' ? '—' : x.truth == null ? '<span class="tag t-wait">待驗證</span>' : x.truth === x.main ? '<span class="tag t-ok">對</span>' : `<span class="tag t-bad">錯・實為${LBL[x.truth]}</span>`}</td>
     <td>${x.ret_pct == null ? '—' : sgn(x.ret_pct)}</td></tr>`).join('')}</table></div>` : '<div class="mutebox">最近 60 天沒有判斷紀錄。</div>'}
    <div class="lbl" style="margin-top:6px">報酬已扣成本 ${D.meta.rules.cost_pct}%。判高點的報酬只是參考,研究只回測判低點做多。</div></div>
  </div></div>${disc()}`;
}

/* ---------- 成績追蹤 ---------- */
function pageTrack() {
  const T = trk(TM, TK), dates = D.track.dates || {};
  const series = T.series || [], W = 860, H = 220, top = 14, bot = H - 26;
  let g = '';
  if (series.length > 1) {
    const ymax = Math.max(50, ...series.map(s => s[1])) / 100, y = v => bot - v / ymax * (bot - top), x = i => 40 + i / (series.length - 1) * (W - 50);
    const li = series.findIndex(s => s[2] === 'daily');
    if (li >= 0) g += `<rect x="${x(li)}" y="${top}" width="${x(series.length - 1) - x(li) + 1}" height="${bot - top}" fill="#e8f0fd" opacity=".7"/><text x="${x(li) + 4}" y="${top + 14}" font-size="11" fill="var(--low)" font-weight="700">實際追蹤</text>`;
    g += `<text x="${li > 0 ? x(li) - 6 : W - 12}" y="${top + 14}" font-size="11" fill="#8a929c" text-anchor="end">回放(上線前,同一個模型逐日產生)</text>`;
    for (let t = 0; t <= ymax + 1e-9; t += .1) g += `<line x1="40" x2="${W - 10}" y1="${y(t)}" y2="${y(t)}" stroke="#eef0f3"/><text x="34" y="${y(t) + 4}" font-size="10" fill="#8a929c" text-anchor="end">${Math.round(t * 100)}%</text>`;
    const br = (T.base_rate?.pct || 0) / 100;
    g += `<line x1="40" x2="${W - 10}" y1="${y(br)}" y2="${y(br)}" stroke="#9aa3ad" stroke-dasharray="4 3"/><text x="${W - 12}" y="${y(br) - 4}" font-size="10" fill="#5b6470" text-anchor="end">隨機猜約 ${pct(T.base_rate?.pct, 0)}</text>`;
    g += `<polyline points="${series.map((s, i) => `${x(i)},${y(s[1] / 100)}`).join(' ')}" fill="none" stroke="${TK === 'low' ? 'var(--low)' : 'var(--high)'}" stroke-width="2"/>`;
    [0, .25, .5, .75, 1].forEach(f => { const i = Math.round(f * (series.length - 1)); g += `<text x="${x(i)}" y="${H - 6}" font-size="10" fill="#8a929c" text-anchor="middle">${md(series[i][0])}</text>`; });
  }
  const R = (D.research?.classification || []).find(r => r.year === '2026' && r.method === TM) || {};
  const k = (lbl, r, extra) => `<div class="card"><div class="lbl">${lbl}</div><div class="kpi">${pct(r?.pct)}</div><div class="info">${r?.n ? `${r.hits} / ${r.n} 檔次` : '尚無資料'}${extra ? ' ・ ' + extra : ''}</div></div>`;
  const lv = T.levels || {};
  return `<div class="row" style="margin-bottom:14px"><div><h1>成績追蹤</h1><p class="sub" style="margin:0">每天的判斷當天就存檔,不會事後修改;5 個交易日後自動對答案。資料 ${dates.first || ''} ~ ${dates.last || ''},已對答案 ${dates.n_graded || 0} 天${dates.live_start ? `,${dates.live_start} 起為實際追蹤` : ',目前都是回放'}。</p></div><div class="sp"></div>
   ${seg(TM, [['main', '① 主軸'], ['stack', '② Stacking']], 'TM')} ${seg(TK, [['low', '判低點'], ['high', '判高點']], 'TK')}</div>
  <div class="grid4 k2" style="margin-bottom:16px">
   ${k('近 20 天命中率(前 3 檔)', T.top_20)}${k('近 60 天命中率(前 3 檔)', T.top_60)}
   ${k(`${T.all_ytd?.year || ''} 年命中率(池內全部判斷)`, T.all_ytd, `研究結果 2026 1–9 月 ${pct(TK === 'low' ? R.prec_low : R.prec_high)}`)}
   <div class="card"><div class="lbl">前 3 檔每筆平均報酬(近 60 天)</div><div class="kpi">${sgn(T.top_60?.avg_ret_pct)}</div><div class="info">勝率 ${pct(T.top_60?.win_pct)} ・ t+1 開 → t+5 收,扣成本 ${D.meta.rules.cost_pct}%</div></div>
  </div>
  <div class="card" style="margin-bottom:16px"><div class="row"><h3 style="margin:0">命中率(池內全部判斷,60 天移動)</h3></div>
   ${series.length > 1 ? `<div class="chartwrap"><svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block">${g}</svg></div>` : '<div class="mutebox">對答案的天數還不夠畫圖(至少 20 天)。</div>'}</div>
  <div class="grid2" style="margin-bottom:16px">
   <div class="card"><h3>各信心等級的命中率(池內)</h3><table class="tbl lvtable"><tr><th>信心</th><th>命中率</th><th>對 / 判斷數</th></tr>
    ${['高', '中', '低'].map(l => `<tr><td>${l}</td><td>${pct(lv[l]?.pct)}</td><td>${lv[l] ? `${lv[l].hits} / ${lv[l].n}` : '—'}</td></tr>`).join('')}
    <tr><td>全部</td><td>${pct(T.all?.pct)}</td><td>${T.all ? `${T.all.hits} / ${T.all.n}` : '—'}</td></tr></table>
    <div class="lbl" style="margin-top:6px">信心等級 = 訓練期內分數的三等分。三個等級的命中率如果差不多,代表分數高低對命中率幫助不大。</div></div>
   <div class="card"><h3>池外與低波動股</h3><table class="tbl lvtable"><tr><th>股票</th><th>命中率</th><th>對 / 判斷數</th></tr>
    <tr><td>池內(參考)</td><td>${pct(T.all?.pct)}</td><td>${T.all ? `${T.all.hits} / ${T.all.n}` : '—'}</td></tr>
    <tr><td>池外</td><td>${pct(T.out_pool?.pct)}</td><td>${T.out_pool ? `${T.out_pool.hits} / ${T.out_pool.n}` : '—'}</td></tr>
    <tr><td>低波動(不適用)</td><td>${pct(T.low_vol?.pct)}</td><td>${T.low_vol ? `${T.low_vol.hits} / ${T.low_vol.n}` : '—'}</td></tr></table>
    <div class="lbl" style="margin-top:6px">低波動股的高低點常常只差一兩檔,命中率高低都沒有參考價值。</div></div></div>
  <div class="card"><h3>每日明細(${TK === 'low' ? '判低點' : '判高點'}前 3 檔)</h3><div class="tblwrap"><table class="tbl"><tr><th>判斷日</th><th>前 3 檔</th><th>結果</th><th>平均報酬</th><th>來源</th></tr>
   ${(T.daily || []).map(r => `<tr><td>${md(r.date)}</td><td>${r.picks.map(p => `<a href="#stock/${p.code}" style="color:inherit">${p.code} ${esc(p.name)}</a>${p.truth == null ? '' : p.truth === TK ? ' <span class="tag t-ok">對</span>' : ' <span class="tag t-bad">錯</span>'}`).join('、')}</td>
    <td>${r.hits == null ? '<span class="tag t-wait">待驗證</span>' : `<span class="tag ${r.hits >= 2 ? 't-ok' : r.hits === 1 ? 't-warn' : 't-bad'}">${r.hits} / ${r.picks.length} 對</span>`}</td>
    <td>${r.avg_ret_pct == null ? '—' : sgn(r.avg_ret_pct)}</td><td><span class="tag ${r.source === 'daily' ? 't-live' : 't-replay'}">${r.source === 'daily' ? '實際' : '回放'}</span></td></tr>`).join('')}</table></div></div>
  ${disc()}`;
}

/* ---------- 方法與說明 ---------- */
function pageAbout() {
  const bars = [42, 46, 40, 37, 33, 28, 35, 39, 44, 47, 45].map((h, i) => `<i class="${i === 5 ? 't' : i < 5 ? '' : 'f'}" style="height:${h * 2}px"></i>`).join('');
  const C = (D.research?.classification || []).slice().sort((a, b) => (a.method + a.year).localeCompare(b.method + b.year));
  const B = (D.research?.backtest || []);
  const mi = D.meta.model || {};
  return `<h1>方法與說明</h1><p class="sub">本頁的命中率與回測數字是<b>研究結果</b>,直接讀 repo 裡的結果檔(${(D.research?.sources || []).map(esc).join('、')}),沒有重算。</p>
  <div class="stack">
  <div class="card"><h2>「高點」「低點」是什麼意思</h2>
   <div class="grid2"><div><div class="label-demo">${bars}</div><div class="legend"><span>t−5 … t−1</span><span style="color:var(--low);font-weight:700">t(今天)</span><span>t+1 … t+5(要等 5 天)</span></div></div>
   <div style="font-size:14px">看 11 天:今天(第 6 天)加前後各 5 天。<br>・今天收盤是 11 天<b>最低</b> → 低點<br>・今天收盤是 11 天<b>最高</b> → 高點<br>・其他 → 非極值(約 85% 的日子)<br><br>
   模型只看今天和前 5 天的 6 根 K 線,所以收盤後就能判斷;但真正的答案要等 5 個交易日後才知道。</div></div></div>
  <div class="card"><h2>兩個方法</h2><div class="steps">
   <div class="step"><b>1. 規則挑候選</b>今天收盤是近 6 天最高 → 高點候選;最低 → 低點候選。其他直接判非極值。</div>
   <div class="step"><b>2a. ① 主軸</b>候選點再經過 AE + OC-SVM 檢查,形狀像過去的真高 / 低點才保留。分數 = decision_function。</div>
   <div class="step"><b>2b. ② Stacking</b>不用規則:兩個 AE / OC-SVM 的分數交給邏輯迴歸,輸出三類機率。判得比較少。</div></div>
   <div class="lbl" style="margin-top:8px">特徵:6 根 K 線的開高低收 ÷ 今天收盤、量 ÷ 10 日均量,共 29 個數字。目前的模型:${mi.year} 年用,訓練 ${(mi.train || []).join(' ~ ')}(${fmt(mi.n_train, 0)} 筆),股票池 ${mi.n_pool} 檔,種子 ${mi.seed}。每年 1 月第 6 個交易日後自動重訓。</div></div>
  <div class="card"><h2>歷史命中率(研究結果,TW100 剔除低波動股)</h2><div class="tblwrap"><table class="tbl">
   <tr><th>方法</th><th>年</th><th>macro-F1</th><th>判低點命中</th><th>判高點命中</th><th>真低點找到</th><th>真高點找到</th><th>隨機猜中低點</th></tr>
   ${C.map(r => `<tr><td>${MNAME[r.method]}</td><td>${r.year}${r.year === '2026' ? '(1–9 月)' : ''}</td><td>${pct(r.macro_f1, 2)}</td><td>${pct(r.prec_low)}</td><td>${pct(r.prec_high)}</td><td>${pct(r.rec_low)}</td><td>${pct(r.rec_high)}</td><td>${pct(r.base_low)}</td></tr>`).join('')}</table></div>
   <div class="lbl" style="margin-top:6px">兩個方法都沒有把高點判成低點(或反過來),錯的都是和非極值混淆。</div></div>
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
const NAV = [['today', '今日判斷', 'M3 12h4l3-8 4 16 3-8h4'], ['stock', '個股查詢', 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9 16-4-4'], ['track', '成績追蹤', 'M4 20V10m6 10V4m6 16v-7m4 7H2'], ['about', '方法與說明', 'M12 8h.01M11 12h1v5h1M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z']];
function go(h) { location.hash = h; }
function header() {
  const M = D.meta, c = M.check || {};
  document.getElementById('hmeta').innerHTML = `判斷基準日 <b>${dlabel(M.asof)}收盤</b> ・ 產生於 ${esc((M.created || '').slice(5, 16))}<br>模型:訓練 ${(M.model?.train || []).map(d => d.slice(0, 4)).join('–')} ・ 股票池 ${M.model?.n_pool} 檔`;
  const b = [];
  if (c.stale) b.push(`<div class="badbox"><b>今天的資料還沒更新。</b>畫面是 ${M.asof} 的判斷;資料來源晚到時批次會在稍後補跑。</div>`);
  if ((c.missing_pool || []).length) b.push(`<div class="warnbox">股票池有 ${c.missing_pool.length} 檔沒有 ${M.asof} 的資料(${c.missing_pool.slice(0, 8).join('、')}${c.missing_pool.length > 8 ? '…' : ''}),這幾檔今天沒有判斷。</div>`);
  if (M.source === 'replay') b.push(`<div class="mutebox">目前顯示的是<b>回放資料</b>:上線前用同一個模型逐日產生的判斷。</div>`);
  if (c.online === false && M.source !== 'replay') b.push(`<div class="mutebox">這次批次沒有連網,K 線只到 ${M.asof}。</div>`);
  document.getElementById('banner').innerHTML = b.join('');
}
async function render() {
  const h = location.hash.slice(1) || 'today', [p, arg] = h.split('/');
  document.getElementById('topnav').innerHTML = NAV.map(([k, n]) => `<a href="#${k}" class="${p === k ? 'on' : ''}">${n}</a>`).join('');
  document.getElementById('botnav').innerHTML = NAV.map(([k, n, d]) => `<a href="#${k}" class="${p === k ? 'on' : ''}"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"/></svg>${n}</a>`).join('');
  const app = document.getElementById('app');
  try {
    app.innerHTML = p === 'stock' ? (arg ? await pageStock(arg) : pageSearch()) : p === 'track' ? pageTrack() : p === 'about' ? pageAbout() : pageToday();
  } catch (e) { app.innerHTML = `<div class="badbox">畫面產生失敗:${esc(e.message)}</div>`; console.error(e); }
  if (p === 'stock' && arg) Q = '';
}
async function boot() {
  try {
    [D.meta, D.today, D.track, D.research, D.index] = await Promise.all(['meta', 'today', 'track', 'research', 'index'].map(n => j(`data/${n}.json`)));
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
