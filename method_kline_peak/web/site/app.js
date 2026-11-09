/* K 線高低點判斷:靜態前端。資料全部來自 data/*.json(每日批次產生)。
   2026-11-09 起只有 Stacking,推薦範圍是台灣 50;定位為參考方向的決策輔助。 */
const D = {shards: {}};
const LBL = {low: '低點', high: '高點', none: '非極值'};
const STATUS = {pool: ['台灣 50', 't-ok'], out: ['池外', 't-warn'], lowvol: ['低波動', 't-none'], nosup: ['不支援', 't-bad'], nodata: ['資料不足', 't-none'], halted: ['今日無交易', 't-none']};
const MARKET = {TWSE: '上市', OTC: '上櫃', ESB: '興櫃', ETF: 'ETF'};
let TK = 'low', Q = '';

const fmt = (x, d = 2) => x == null || !isFinite(x) ? '—' : Number(x).toLocaleString('zh-TW', {minimumFractionDigits: d, maximumFractionDigits: d});
const pct = (x, d = 1) => x == null ? '—' : fmt(x, d) + '%';
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const WD = '日一二三四五六';
const dlabel = d => { const t = new Date(d + 'T00:00:00'); return `${d}(${WD[t.getDay()]})`; };
const md = d => d ? d.slice(5).replace('-', '/') : '';
const tagCls = k => k === 'low' ? 't-low' : k === 'high' ? 't-high' : 't-none';
const REC = () => D.meta?.profile?.recommend_label || '台灣 50';
const TRAIN = () => `${D.meta?.profile?.pool_label || 'TW200'}(剔除低波動股)`;

async function j(path) { const r = await fetch(path, {cache: 'no-store'}); if (!r.ok) throw new Error(path + ' ' + r.status); return r.json(); }

/* ---------- 共用 ---------- */
function disc() {
  return `<div class="disc">本網站為研究模型輸出展示,非證券投資顧問服務,不構成買賣建議。模型命中率約 3 成,判斷只供參考方向,買賣請自行決定。<a href="#about">完整免責聲明</a></div>`;
}
function trk(kind) { return D.track?.kinds?.[kind] || {}; }
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
function groupHit(kind, g) {
  const c = D.today.confirm_hit?.[kind];
  if (!c) return '';
  if (g === 'new') return `研究命中 ${pct(c.k0)}`;
  if (g === 'd12') return `研究命中:1 天 ${pct(c.k1)}、2 天 ${pct(c.k2)}`;
  return `研究命中:3 天 ${pct(c.k3)}(4–5 天沒有研究數字)`;
}
function pickRow(s, i, kind) {
  const old = s.days > 0 ? `訊號日 ${md(s.date)} ・ ` : '';
  return `<div class="pick" onclick="go('stock-${s.code}')"><div class="rank">${i + 1}</div>
  <div><div class="nm">${s.code}<span>${esc(s.name)}</span></div>
  ${marks(s, kind)}
  <div class="info">${old}機率 ${fmt(s.score)} ・ 信心 <b>${s.level || '—'}</b> ・ ${lvHit(s.level_hit)}</div></div>
  <div class="right"><div class="px">${fmt(s.close)}</div>${chg(s.chg_pct)}<div class="hide-m">${spark(s.spark)}</div></div></div>`;
}
function groupBlock(L, kind, g, label) {
  const items = L.filter(s => s.group === g), top = items.slice(0, 3), rest = items.slice(3);
  const name = g === 'new' ? label : `${label}${HOLDWORD[kind]}`;
  return `<div class="grp"><b>${name}</b><span class="lbl">${items.length} 檔</span><span class="sp"></span><span class="hit">${groupHit(kind, g)}</span></div>
  ${items.length ? top.map((s, i) => pickRow(s, i, kind)).join('') : `<div class="lbl" style="padding:8px 0">目前沒有。</div>`}
  ${rest.length ? `<details class="more"><summary>還有 ${rest.length} 檔(機率較低)</summary>
  <table class="minitable"><tr><th>代號</th><th>名稱</th><th>收盤</th><th>機率</th><th>信心</th><th>連續</th></tr>
  ${rest.map(s => `<tr onclick="go('stock-${s.code}')" style="cursor:pointer"><td>${s.code}</td><td>${esc(s.name)}</td><td>${fmt(s.close)}</td><td>${fmt(s.score)}</td><td>${s.level || '—'}</td><td>${s.run} 天</td></tr>`).join('')}</table></details>` : ''}`;
}
function listCard(kind) {
  const L = D.today.lists[kind] || [], isLow = kind === 'low';
  return `<div class="card"><div class="listhead"><span class="dot" style="background:${isLow ? 'var(--low)' : 'var(--high)'}"></span>
  <h2 style="margin:0">${isLow ? '判低點' : '判高點'}</h2><span class="lbl">共 ${L.length} 檔,依「${HOLDWORD[kind]}」天數分組,組內依機率排序</span></div>
  <div class="lbl" style="margin:-4px 0 6px">${isLow ? '收盤可能是前後 11 天最低。前幾天判的,只列到今天都還沒跌破那天收盤的' : '收盤可能是前後 11 天最高。前幾天判的,只列到今天都還沒漲過那天收盤的'}</div>
  ${GROUPS.map(([g, label]) => groupBlock(L, kind, g, label)).join('')}</div>`;
}
function pageToday() {
  const T = D.today, lo = T.lists.low || [], hi = T.lists.high || [];
  const nNew = L => L.filter(s => s.group === 'new').length;
  const t60 = trk('low').top_60 || {}, base = trk('low').base_rate || {}, all = trk('low').all || {};
  return `<div style="margin-bottom:14px"><h1>今日判斷</h1>
  <p class="sub" style="margin:0">${dlabel(T.date)} 收盤後,模型對${REC()}的判斷。答案要再過 5 個交易日收盤才知道。</p></div>
  <div class="summary">
   <div class="card"><div class="lbl">今天判低點</div><div class="kpi" style="color:var(--low)">${nNew(lo)} <small>檔</small></div><div class="info">另 ${lo.length - nNew(lo)} 檔前 1–5 天判、還沒破底</div></div>
   <div class="card"><div class="lbl">今天判高點</div><div class="kpi" style="color:var(--high)">${nNew(hi)} <small>檔</small></div><div class="info">另 ${hi.length - nNew(hi)} 檔前 1–5 天判、還沒創高</div></div>
   <div class="card"><div class="lbl">判低點命中率(${REC()},全部判斷)</div><div class="kpi">${pct(all.pct)} <small>隨機約 ${pct(base.pct, 0)}</small></div><div class="info">${all.n ? `${all.hits} / ${all.n} 筆,回放 + 實際追蹤` : ''}</div></div>
   <div class="card"><div class="lbl">判低點前 3 檔命中率(近 60 天)</div><div class="kpi">${pct(t60.pct)}</div><div class="info">${t60.n ? `${t60.hits} / ${t60.n} 檔次` : ''}</div></div>
  </div>
  <div class="grid2">${listCard('low')}${listCard('high')}</div>
  <div class="note" style="margin-top:16px"><b>怎麼看這份清單</b><br>
  「判低點」10 次大約只有 3 次真的是 11 天內的低點,錯的大多是普通日子。判斷之後幾天都沒破底,真的是低點的比例會變高
  (${esc(T.confirm_hit?.source || '')}),但那幾天的價格本來就是答案的一部分,等越久也越晚。
  這份清單是提醒你「這裡可能是近期的高點 / 低點,值得看一下」,買不買由你自己決定。<a href="#findings">看研究發現</a></div>
  ${disc()}`;
}

/* ---------- 個股查詢 ---------- */
function typeTag(st) { const [n, c] = STATUS[st] || ['?', 't-none']; return `<span class="tag ${c}">${n}</span>`; }
function chips() {
  const byCode = Object.fromEntries((D.index || []).map(r => [r[0], r]));
  const pick = (pref, st) => byCode[pref]?.[2] === st ? byCode[pref] : (D.index || []).find(r => r[2] === st);
  const list = [['2330', '台積電'], ['8046', '南電']];
  for (const [pref, st] of [['2618', 'out'], ['2801', 'lowvol']]) { const r = pick(pref, st); if (r) list.push([r[0], r[1]]); }
  list.push(['0050', '元大台灣50']);
  return `<div class="chips">${list.map(([c, n]) => `<button type="button" class="chip" onclick="go('stock-${c}')">${c} ${esc(n)}</button>`).join('')}</div>`;
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
function kchart(S) {
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
    if (s && s.pred && s.pred !== 'none') {
      const isL = s.pred === 'low', c2 = isL ? 'var(--low)' : 'var(--high)', yy = isL ? y(l) + 11 : y(h) - 11;
      const st = s.truth == null ? 'wait' : s.truth === s.pred ? 'ok' : 'bad';
      const tri = isL ? `M${x - 5},${yy + 4} L${x + 5},${yy + 4} L${x},${yy - 4} Z` : `M${x - 5},${yy - 4} L${x + 5},${yy - 4} L${x},${yy + 4} Z`;
      g += `<path d="${tri}" fill="${st === 'ok' ? c2 : 'var(--card)'}" stroke="${c2}" stroke-width="1.5" ${st === 'wait' ? 'stroke-dasharray="2 1.5"' : ''}><title>${d} 判${LBL[s.pred]}:${st === 'wait' ? '待驗證' : st === 'ok' ? '對' : '錯'}</title></path>`;
      if (st === 'bad') g += `<text x="${x}" y="${isL ? yy + 16 : yy - 8}" font-size="9" fill="var(--bad)" text-anchor="middle">✕</text>`;
    }
    if (i === bars.length - 1) g += `<rect x="${x - bw / 2}" y="${top - 6}" width="${bw}" height="${bot - top + 12}" fill="var(--accent)" opacity=".06"/><text x="${x - bw}" y="${top - 9}" font-size="10" font-weight="700" fill="var(--axis)" text-anchor="end">今天 ▸</text>`;
  });
  const ticks = M ? [0, 10, 20, bars.length - 1] : [0, 15, 30, 45, bars.length - 1];
  ticks.filter(i => i < bars.length).forEach(i => g += `<text x="${pad + i * bw + bw / 2}" y="${H - 8}" font-size="10" fill="var(--axis)" text-anchor="middle">${md(bars[i][0])}</text>`);
  return `<div class="chartwrap"><svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block">${g}</svg></div>
  <div class="legend"><span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="var(--low)"/></svg>判低點・對</span><span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="var(--card)" stroke="var(--low)" stroke-width="1.4"/></svg>判低點・錯(✕)</span>
  <span><svg width="12" height="10"><path d="M1,1 L11,1 L6,9Z" fill="var(--high)"/></svg>判高點・對</span><span><svg width="12" height="10"><path d="M1,1 L11,1 L6,9Z" fill="var(--card)" stroke="var(--high)" stroke-width="1.4" stroke-dasharray="2 1.5"/></svg>虛線 = 待驗證(未滿 5 天)</span>
  <span>K 線為還原價,紅漲綠跌</span></div>`;
}
function bar(label, v, color, txt) {
  return `<div class="cls"><span>${label}</span><div class="bar" style="margin:0;height:8px"><i style="width:${Math.max(0, Math.min(1, v)) * 100}%;background:${color}"></i></div><span class="right">${txt}</span></div>`;
}
function pageSearch() {
  return `<h1>個股查詢</h1><p class="sub">輸入上市股票代號或名稱。${REC()}是推薦範圍,每天都有判斷;其他股票照算,畫面會提示;推薦範圍以外的低波動股判斷不適用。</p>${searchBox()}
  <div class="grid4 k2">${[[REC(), 't-ok', `${REC()}成分股,每天的推薦清單只看這些`], ['池外', 't-warn', '其他上市普通股,可查,僅供參考'], ['低波動', 't-none', '推薦範圍以外、每日漲跌太小,判斷不適用'], ['不支援', 't-bad', 'ETF、上櫃、興櫃、特別股']].map(([a, c, d]) => `<div class="card"><span class="tag ${c}">${a}</span><div class="info" style="margin-top:6px">${d}</div></div>`).join('')}</div>${disc()}`;
}
/* 個股資料依代號前兩碼分檔(stocks/23.json 內含 2301–2399),讀過的分檔留在記憶體 */
async function loadStock(code) {
  const k = code.slice(0, 2);
  if (!D.shards[k]) D.shards[k] = await j(`data/stocks/${k}.json`);
  return D.shards[k][code];
}
function activeCard(S) {
  const rows = [];
  for (const k of ['low', 'high']) {
    const a = S.active?.[k];
    if (!a) continue;
    const c = D.today.confirm_hit?.[k], key = a.days >= 3 ? 'k3' : 'k' + a.days;
    const hitTxt = c && a.days <= 3 ? `研究命中 ${pct(c[key])}` : c ? `研究只算到 3 天(${pct(c.k3)})` : '';
    rows.push(`<tr><td><span class="tag ${tagCls(k)}">判${LBL[k]}</span></td><td>${md(a.date)}</td><td>${fmt(a.score)}</td>
      <td>${a.days === 0 ? '剛出現' : `已 ${a.days} 天${HOLDWORD[k]}`}</td><td>連續第 ${a.run} 天</td><td>${hitTxt}</td></tr>`);
  }
  if (!rows.length) return '';
  return `<div class="card"><h3>最近的高 / 低點訊號</h3><div class="tblwrap"><table class="tbl"><tr><th>判斷</th><th>訊號日</th><th>機率</th><th>到今天</th><th>連續</th><th>研究數字(TW200)</th></tr>${rows.join('')}</table></div>
   <div class="lbl" style="margin-top:6px">只列最近 5 個交易日內、到今天都還沒破底(低點)/ 沒創高(高點)的訊號。等越多天,真的是低點的比例越高,但也越晚。研究數字:${esc(D.today.confirm_hit?.source || '')}。</div></div>`;
}
async function pageStock(code) {
  const ix = (D.index || []).find(r => r[0] === code);
  if (!ix) return `<h1>個股查詢</h1>${searchBox()}<div class="badbox">查無代號 ${esc(code)}。目前只支援上市普通股。</div>${disc()}`;
  if (ix[2] === 'nosup') return `<h1>個股查詢</h1>${searchBox()}<div class="card"><div class="row"><h2 style="margin:0">${code} ${esc(ix[1])}</h2>${typeTag('nosup')}<span class="tag t-none">${MARKET[ix[3]] || ''}</span></div>
    <div class="badbox" style="margin-top:12px"><b>目前不支援這檔。</b>${esc(ix[4])}</div></div>${disc()}`;
  let S; try { S = await loadStock(code); } catch (e) { S = null; }
  if (!S) return `<h1>個股查詢</h1>${searchBox()}<div class="badbox">讀不到 ${code} 的資料。</div>${disc()}`;
  const t = S.today, P = t.stack || {}, p = P.pred || 'none';
  let pre = '';
  const outHit = trk('low').out_pool;
  if (S.status === 'out') pre = `<div class="warnbox"><b>⚠ 這檔不在${REC()}推薦範圍。</b>判斷照算,僅供參考。回放期間推薦範圍以外股票的判低點命中率 <b>${pct(outHit?.pct)}</b>(${outHit?.n || 0} 筆)。</div>`;
  if (S.status === 'lowvol') pre = `<div class="mutebox"><b>這檔是低波動股,判斷不適用。</b>2020 年起每日漲跌幅中位數 ${fmt(S.move)}%,低於門檻 ${D.meta.rules.min_move}%。這類股票的「11 天最低」常常只差一兩檔,判斷沒有參考價值。
   <details style="margin-top:6px"><summary style="cursor:pointer">仍要看模型輸出</summary><div style="margin-top:6px">今天判${LBL[p]}${P.score != null ? `(機率 ${fmt(P.score)})` : ''}。</div></details></div>`;
  if (S.status === 'halted') pre = `<div class="badbox"><b>這檔 ${S.date} 沒有交易資料</b>(停牌、處置或資料未更新),今天沒有判斷。</div>`;
  if (S.status === 'nodata') pre = `<div class="mutebox"><b>資料不足</b>,至少要 16 個交易日的 K 線才能判斷。</div>`;
  const dim = S.status === 'lowvol' ? 'opacity:.45;filter:grayscale(1)' : '';
  const last = S.bars[S.bars.length - 1] || [];
  const hit = S.status !== 'pool' || p === 'none' ? null : trk(p).levels?.[P.level];
  const icon = p === 'low' ? '↓' : p === 'high' ? '↑' : '–';
  const sug = !t.stack ? '今天沒有判斷。' : p === 'low' ? `模型判斷 <b>今天(${md(S.date)})收盤可能是前後 11 天的最低點</b>(機率 ${fmt(P.score)},信心 <b>${P.level}</b>)。${hit?.n ? `過去同信心等級的判低點,<b>${pct(hit.pct)}</b> 真的是低點(${hit.n} 筆),其餘大多是普通日子。` : ''}<br><br>
     「低點」只代表 11 天內最低,不代表之後會漲多少。可以看接下來幾天有沒有破底:沒破底的天數越多,越可能是真的低點,但也越晚。`
    : p === 'high' ? `模型判斷 <b>今天(${md(S.date)})收盤可能是前後 11 天的最高點</b>(機率 ${fmt(P.score)},信心 <b>${P.level}</b>)。${hit?.n ? `過去同信心等級的判高點,<b>${pct(hit.pct)}</b> 真的是高點(${hit.n} 筆)。` : ''}<br><br>
     這個判斷只當提醒:短期可能不宜追高。`
    : `模型判斷今天是 <b>非極值</b>(一般日子)。三類機率裡「非極值」最高(${fmt(P.p_none)})。`;
  const R = (D.research?.classification || []).find(r => r.year === '2026') || {};
  const past = (S.signals || []).filter(x => x.pred !== 'none').slice().reverse().slice(0, 10);
  return `<h1>個股查詢</h1>${searchBox()}
  <div class="stack">
  <div class="card"><div class="row"><h2 style="margin:0;font-size:20px">${code} ${esc(S.name)}</h2>${typeTag(S.status)}<div class="sp"></div>
   <div class="right"><span class="px" style="font-size:20px">${fmt(t.close ?? last[4])}</span> ${chg(t.chg_pct)}<div class="lbl">${md(S.date)} 收盤(還原價)</div></div></div></div>
  ${pre}
  ${activeCard(S)}
  ${t.stack ? `<div class="grid2" style="${dim}">
   <div class="card"><div class="verdict"><div class="vicon" style="background:${p === 'low' ? 'var(--low-bg)' : p === 'high' ? 'var(--high-bg)' : 'var(--mute-bg)'};color:${p === 'low' ? 'var(--low)' : p === 'high' ? 'var(--high)' : 'var(--ink3)'}">${icon}</div>
     <div><div class="lbl">今天的判斷</div><div class="vtitle">${p === 'none' ? '非極值・一般日子' : '今天可能是' + LBL[p]}</div>
     ${p !== 'none' ? marks(S.active?.[p], p) : ''}
     ${p !== 'none' ? `<div class="info">機率 ${fmt(P.score)} ・ 信心 <b>${P.level}</b> ・ ${S.status !== 'pool' ? (STATUS[S.status] || ['池外'])[0] + '股票的命中率見上方說明' : lvHit(hit)}</div>` : ''}</div></div>
     <h3 style="margin-top:16px">三類機率</h3>
     ${bar('高點', P.p_high, 'var(--high)', fmt(P.p_high))}${bar('低點', P.p_low, 'var(--low)', fmt(P.p_low))}${bar('非極值', P.p_none, 'var(--ink3)', fmt(P.p_none))}
     <div class="lbl" style="margin-top:6px">三類機率加起來是 1,最大的那類就是判斷。研究顯示只挑機率高的,命中率只升一點點,真的轉折點卻會漏掉很多,所以機率只當參考。</div></div>
   <div class="card"><h3>參考數字</h3><table class="cmp">
     <tr><td>這檔判低點對答案<br><span class="lbl">回放 + 實際追蹤</span></td><td>${S.low_stats?.n ? `${S.low_stats.hits} / ${S.low_stats.n} 對(${pct(S.low_stats.pct)})` : '—'}</td></tr>
     <tr><td>判低點命中率<br><span class="lbl">研究結果 TW200 2026 1–9 月</span></td><td>${pct(R.prec_low)}</td></tr>
     <tr><td>真低點找到率<br><span class="lbl">研究結果 TW200 2026 1–9 月</span></td><td>${pct(R.rec_low)}</td></tr>
     <tr><td>隨便挑一天剛好是低點<br><span class="lbl">研究結果 TW200 2026 1–9 月</span></td><td>${pct(R.base_low)}</td></tr></table></div>
  </div>` : ''}
  <div class="card" style="${dim}"><div class="row"><h3 style="margin:0">最近 ${innerWidth < 760 ? 30 : 60} 個交易日</h3><div class="sp"></div><span class="lbl">標記 = 過去的判斷,5 天後對答案</span></div>${kchart(S)}</div>
  <div class="grid2" style="${dim}">
   <div class="card"><h3>說明</h3><div style="font-size:14.5px">${sug}</div>
    <div class="disc" style="margin-top:12px">本頁為研究模型輸出,非投資建議。<a href="#about">免責聲明</a></div></div>
   <div class="card"><h3>這檔過去的判斷</h3>${past.length ? `<div class="tblwrap"><table class="tbl"><tr><th>日期</th><th>判斷</th><th>機率</th><th>信心</th><th>結果</th></tr>
    ${past.map(x => `<tr><td>${md(x.date)}</td><td><span class="tag ${tagCls(x.pred)}">${LBL[x.pred]}</span></td><td>${fmt(x.score)}</td><td>${x.level || '—'}</td>
     <td>${x.truth == null ? '<span class="tag t-wait">待驗證</span>' : x.truth === x.pred ? '<span class="tag t-ok">對</span>' : `<span class="tag t-bad">錯・實為${LBL[x.truth]}</span>`}</td></tr>`).join('')}</table></div>` : '<div class="mutebox">最近 60 天沒有判斷紀錄。</div>'}</div>
  </div></div>${disc()}`;
}

/* ---------- 成績追蹤 ---------- */
function pageTrack() {
  const T = trk(TK), dates = D.track.dates || {};
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
  const R = (D.research?.classification || []).find(r => r.year === '2026') || {};
  const k = (lbl, r, extra) => `<div class="card"><div class="lbl">${lbl}</div><div class="kpi">${pct(r?.pct)}</div><div class="info">${r?.n ? `${r.hits} / ${r.n} 檔次` : '尚無資料'}${extra ? ' ・ ' + extra : ''}</div></div>`;
  const lv = T.levels || {};
  return `<div class="row" style="margin-bottom:14px"><div><h1>成績追蹤</h1><p class="sub" style="margin:0">${REC()}每天的判斷當天就存檔,不會事後修改;5 個交易日後自動對答案。資料 ${dates.first || ''} ~ ${dates.last || ''},已對答案 ${dates.n_graded || 0} 天${dates.live_start ? `,${dates.live_start} 起為實際追蹤` : ',目前都是回放'}。</p></div><div class="sp"></div>
   ${seg(TK, [['low', '判低點'], ['high', '判高點']], 'TK')}</div>
  <div class="grid4 k2" style="margin-bottom:16px">
   ${k('近 20 天命中率(前 3 檔)', T.top_20)}${k('近 60 天命中率(前 3 檔)', T.top_60)}
   ${k(`${T.all_ytd?.year || ''} 年命中率(全部判斷)`, T.all_ytd, `研究結果 TW200 2026 1–9 月 ${pct(TK === 'low' ? R.prec_low : R.prec_high)}`)}
   <div class="card"><div class="lbl">隨便挑一天剛好是${LBL[TK]}</div><div class="kpi">${pct(T.base_rate?.pct)}</div><div class="info">${REC()}、已對答案的日子</div></div>
  </div>
  <div class="card" style="margin-bottom:16px"><div class="row"><h3 style="margin:0">命中率(${REC()}全部判斷,60 天移動)</h3></div>
   ${series.length > 1 ? `<div class="chartwrap"><svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block">${g}</svg></div>` : '<div class="mutebox">對答案的天數還不夠畫圖(至少 20 天)。</div>'}</div>
  <div class="grid2" style="margin-bottom:16px">
   <div class="card"><h3>各信心等級的命中率(${REC()})</h3><table class="tbl lvtable"><tr><th>信心</th><th>命中率</th><th>對 / 判斷數</th></tr>
    ${['高', '中', '低'].map(l => `<tr><td>${l}</td><td>${pct(lv[l]?.pct)}</td><td>${lv[l] ? `${lv[l].hits} / ${lv[l].n}` : '—'}</td></tr>`).join('')}
    <tr><td>全部</td><td>${pct(T.all?.pct)}</td><td>${T.all ? `${T.all.hits} / ${T.all.n}` : '—'}</td></tr></table>
    <div class="lbl" style="margin-top:6px">信心等級 = 訓練期內機率的三等分。</div></div>
   <div class="card"><h3>推薦範圍以外</h3><table class="tbl lvtable"><tr><th>股票</th><th>命中率</th><th>對 / 判斷數</th></tr>
    <tr><td>${REC()}(參考)</td><td>${pct(T.all?.pct)}</td><td>${T.all ? `${T.all.hits} / ${T.all.n}` : '—'}</td></tr>
    <tr><td>其他上市股(池外)</td><td>${pct(T.out_pool?.pct)}</td><td>${T.out_pool ? `${T.out_pool.hits} / ${T.out_pool.n}` : '—'}</td></tr></table>
    <div class="lbl" style="margin-top:6px">個股查詢可以查其他上市股,判斷照算,這是它們過去的命中率。</div></div></div>
  <div class="card"><h3>每日明細(${TK === 'low' ? '判低點' : '判高點'}前 3 檔)</h3><div class="tblwrap"><table class="tbl"><tr><th>判斷日</th><th>前 3 檔</th><th>結果</th><th>來源</th></tr>
   ${(T.daily || []).map(r => `<tr><td>${md(r.date)}</td><td>${r.picks.map(p => `<a href="#stock-${p.code}" style="color:inherit">${p.code} ${esc(p.name)}</a>${p.truth == null ? '' : p.truth === TK ? ' <span class="tag t-ok">對</span>' : ' <span class="tag t-bad">錯</span>'}`).join('、')}</td>
    <td>${r.hits == null ? '<span class="tag t-wait">待驗證</span>' : `<span class="tag ${r.hits >= 2 ? 't-ok' : r.hits === 1 ? 't-warn' : 't-bad'}">${r.hits} / ${r.picks.length} 對</span>`}</td>
    <td><span class="tag ${r.source === 'daily' ? 't-live' : 't-replay'}">${r.source === 'daily' ? '實際' : '回放'}</span></td></tr>`).join('')}</table></div></div>
  ${disc()}`;
}

/* ---------- 研究發現 ---------- */
/* 只放方向性結論(找得到轉折區、高低點不判反、命中率約三成 → 定位為決策輔助)。數字全部來自 findings.json,由 results/ 的結果檔產生。 */
function pageFindings() {
  const F = D.findings;
  if (!F) return '<div class="badbox">讀不到研究結果。</div>';
  const r = F.recall, p = F.precision, c = F.confirm;
  return `<h1>研究發現</h1>
  <p class="sub">這個模型適合<b>提醒你哪裡可能是高點、低點</b>,不適合拿來自動買賣。以下是 Stacking 的研究結果(${esc(TRAIN())}、訓練門檻 0%、2024–2026 三年平均),數字直接讀研究結果檔。</p>
  <div class="stack">
  <div class="cards">
   <div class="find good"><h3>找得到轉折區</h3><div class="big">${pct(r.low2)} <small>真低點前後 2 天內有被提醒</small></div>
    <p>真低點、真高點當天就被判到的比例是 ${pct(r.low)} / ${pct(r.high)};放寬到前後 2 個交易日,是 ${pct(r.low2)} / ${pct(r.high2)}。轉折的「區域」大致抓得到。</p></div>
   <div class="find good"><h3>高點和低點不會判反</h3><div class="big">${F.cross} <small>次判反(${F.years.join('、')})</small></div>
    <p>${F.years.join('、')} 年每一天的判斷裡,真低點從沒被判成高點,真高點也從沒被判成低點。錯的都是把普通日子當成高 / 低點,方向不會弄反。</p></div>
   <div class="find bad"><h3>命中率約三成</h3><div class="big">${pct(p.low)} <small>判低點裡真的是低點</small></div>
    <p>判低點的命中率 ${pct(p.low)}、判高點 ${pct(p.high)}。隨便挑一天剛好是低點的機率是 ${pct(p.base_low)},模型好很多,但 10 次還是錯 7 次。</p></div>
   <div class="find"><h3>所以定位為決策輔助</h3><div class="big" style="font-size:20px">提醒,不是指令</div>
    <p>方向抓得到、但單一天的判斷不夠準,適合用來提醒「這附近可能是轉折」,再由你自己看線圖、基本面決定要不要動作。</p></div>
  </div>
  <div class="card"><h2>判斷之後幾天沒破底,命中率會變高</h2>
   <p class="sub">今日判斷把訊號依「已幾天沒破底 / 沒創高」分組,每組附上這張表的研究數字。注意這些數字用到判斷之後那幾天的價格,所以要等到那天才知道,也就越晚。</p>
   <div class="tblwrap"><table class="tbl"><tr><th></th><th>剛出現</th><th>已 1 天</th><th>已 2 天</th><th>已 3 天</th><th>隨機猜中</th></tr>
    ${['low', 'high'].map(k => `<tr><td>判${LBL[k]}(${k === 'low' ? '沒破底' : '沒創高'})</td><td>${pct(c[k].k0)}</td><td>${pct(c[k].k1)}</td><td>${pct(c[k].k2)}</td><td>${pct(c[k].k3)}</td><td>${pct(c[k].base)}</td></tr>`).join('')}</table></div>
   <div class="lbl" style="margin-top:6px">${esc(c.source)}</div></div>
  <div class="card"><h2>所以網頁怎麼用</h2>
   <ol class="uselist">
    <li><b>判斷當提醒,不當買賣指令。</b>它告訴你「這裡可能是近期低點 / 高點,值得看一下」,買不買由你自己決定。</li>
    <li><b>看「已幾天沒破底 / 沒創高」。</b>天數越多越可能是真的轉折,但也越晚。</li>
    <li><b>機率只當參考。</b>研究顯示只挑機率高的,命中率只升一點點,卻會漏掉更多真的轉折點。</li>
    <li><b>5 天後對答案。</b>每天的判斷都會存檔,5 個交易日後在<a href="#track">成績追蹤</a>看對了多少。</li>
   </ol></div>
  <div class="lbl">資料來源:method_kline_peak/results/ 的 ${F.sources.map(esc).join('、')}。</div>
  </div>${disc()}`;
}

/* ---------- 方法與說明 ---------- */
function pageAbout() {
  const bars = [42, 46, 40, 37, 33, 28, 35, 39, 44, 47, 45].map((h, i) => `<i class="${i === 5 ? 't' : i < 5 ? '' : 'f'}" style="height:${h * 2}px"></i>`).join('');
  const C = (D.research?.classification || []).slice().sort((a, b) => a.year.localeCompare(b.year));
  const mi = D.meta.model || {};
  const yrs = a => (a || []).map(d => d.slice(0, 4)).filter((v, i, s) => s.indexOf(v) === i).join('–');
  return `<h1>方法與說明</h1><p class="sub">本頁的命中率是<b>研究結果</b>,直接讀 repo 裡的結果檔(${(D.research?.sources || []).map(esc).join('、')}),沒有重算。</p>
  <div class="stack">
  <div class="card"><h2>「高點」「低點」是什麼意思</h2>
   <div class="grid2"><div><div class="label-demo">${bars}</div><div class="legend"><span>t−5 … t−1</span><span style="color:var(--low);font-weight:700">t(今天)</span><span>t+1 … t+5(要等 5 天)</span></div></div>
   <div style="font-size:14px">看 11 天:今天(第 6 天)加前後各 5 天。<br>・今天收盤是 11 天<b>最低</b> → 低點<br>・今天收盤是 11 天<b>最高</b> → 高點<br>・其他 → 非極值(約 85% 的日子)<br><br>
   模型只看今天和前 5 天的 6 根 K 線,所以收盤後就能判斷;但真正的答案要等 5 個交易日後才知道。</div></div></div>
  <div class="card"><h2>模型怎麼判斷(Stacking)</h2><div class="steps">
   <div class="step"><b>1. 看 6 根 K 線</b>今天和前 5 天的開高低收(除以今天收盤)和成交量(除以 10 日均量),共 29 個數字。</div>
   <div class="step"><b>2. 像不像過去的高 / 低點</b>高點、低點各一組 AE + OC-SVM,學過去真的高點、低點長什麼樣子,對今天各打一個分數。</div>
   <div class="step"><b>3. 換成三類機率</b>邏輯迴歸把兩個分數換成高點 / 低點 / 非極值三類機率,最大的那類就是判斷;機率依訓練期分布分成高 / 中 / 低三種信心。</div></div>
   <div class="lbl" style="margin-top:8px">訓練:${esc(TRAIN())}。${mi.year} 年用的模型以 ${yrs(mi.train)} 訓練:前 3 年(${yrs(mi.train_a)})學兩組分數,最後 1 年(${yrs(mi.train_b)})學邏輯迴歸,中間留 5 個交易日間隔;標籤門檻 ${D.meta.profile?.train_min_amp || 0}%,種子 ${mi.seed}。每年 1 月第 6 個交易日後自動重訓。<br>
   推薦範圍:${REC()}成分股,每天全部給判斷(低波動股也照樣判斷)。</div></div>
  <div class="card"><h2>歷史命中率(研究結果,${esc(TRAIN())},Stacking)</h2><div class="tblwrap"><table class="tbl">
   <tr><th>年</th><th>macro-F1</th><th>判低點命中</th><th>判高點命中</th><th>真低點找到</th><th>真高點找到</th><th>隨機猜中低點</th><th>高低點判反</th></tr>
   ${C.map(r => `<tr><td>${r.year}${r.year === '2026' ? '(1–9 月)' : ''}</td><td>${pct(r.macro_f1, 2)}</td><td>${pct(r.prec_low)}</td><td>${pct(r.prec_high)}</td><td>${pct(r.rec_low)}</td><td>${pct(r.rec_high)}</td><td>${pct(r.base_low)}</td><td>${r.cross} 次</td></tr>`).join('')}</table></div>
   <div class="lbl" style="margin-top:6px">錯的都是和非極值混淆,高點和低點沒有互相判錯。</div></div>
  <div class="card"><h2>常見問題</h2><div style="font-size:14px">
   <p><b>判低點就會漲嗎?</b> 不一定。低點只代表 11 天內最低,之後可能只是小反彈。</p>
   <p><b>為什麼盤中查到的是昨天的判斷?</b> 判斷要用收盤價,每天 18:00 左右更新。</p>
   <p><b>為什麼價格和看盤軟體不一樣?</b> 這裡用還原價(把除權息補回去),和訓練時一致。</p>
   <p><b>為什麼有些股票顯示「不適用」?</b> ${REC()}以外、每日漲跌幅中位數低於 ${D.meta.rules.min_move}% 的股票,高低點常常只差一兩檔,判斷沒有參考價值。</p>
   <p><b>過去的判斷會變嗎?</b> 不會。每天的判斷當天就存檔,之後不重算;除權息後還原價變動也不影響已存的判斷。</p></div></div>
  <div class="badbox" id="disclaimer"><b>免責聲明</b><br>本網站為個人學術研究之模型輸出展示,非證券投資顧問服務,不構成任何買賣建議或推介。
   模型歷史命中率約 3 成,判斷僅供參考方向。投資有風險,請自行判斷並承擔損益。本網站不收取任何費用,亦無廣告或任何形式之報酬。</div>
  </div>`;
}

/* ---------- 路由 ---------- */
const NAV = [['today', '今日判斷', 'M3 12h4l3-8 4 16 3-8h4'], ['stock', '個股查詢', 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9 16-4-4'], ['track', '成績追蹤', 'M4 20V10m6 10V4m6 16v-7m4 7H2'], ['findings', '研究發現', 'M9 3h6m-5 0v6L4 19a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2l-6-10V3'], ['about', '方法與說明', 'M12 8h.01M11 12h1v5h1M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z']];
function go(h) { location.hash = h; }
function header() {
  const M = D.meta, c = M.check || {};
  const yrs = (M.model?.train || []).map(d => d.slice(0, 4));
  document.getElementById('hmeta').innerHTML = `判斷基準日 <b>${dlabel(M.asof)}收盤</b> ・ 產生於 ${esc((M.created || '').slice(5, 16))}<br>模型:Stacking・${esc(M.profile?.pool_label || 'TW200')} 訓練 ${yrs[0] || ''}–${yrs[1] || ''} ・ 推薦範圍 ${REC()}`;
  const b = [];
  if (c.stale) b.push(`<div class="badbox"><b>今天的資料還沒更新。</b>畫面是 ${M.asof} 的判斷;資料來源晚到時批次會在稍後補跑。</div>`);
  if ((c.missing_pool || []).length) b.push(`<div class="warnbox">${REC()}有 ${c.missing_pool.length} 檔沒有 ${M.asof} 的資料(${c.missing_pool.slice(0, 8).join('、')}${c.missing_pool.length > 8 ? '…' : ''}),這幾檔今天沒有判斷。</div>`);
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
