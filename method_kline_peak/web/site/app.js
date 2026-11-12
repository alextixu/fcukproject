/* K 線高低點判斷:靜態前端。資料全部來自 data/*.json(每日批次產生)。
   只有 Stacking,推薦範圍是台灣 50;定位為參考方向的決策輔助。
   版面原則:畫面只放數字、圖和 2–6 字的標籤;說明文字放在提示框(data-tip / title)或「展開看更多」裡。 */
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
const MOBILE = () => innerWidth < 760;
/* 提示框:滑鼠移上去或點一下(手機)才出現;tip 用在卡片,ttl 用在整列可點的元素(只給桌機 hover) */
const tip = t => t ? ` data-tip="${esc(t)}" tabindex="0"` : '';
const ttl = t => t ? ` title="${esc(t)}"` : '';

async function j(path) { const r = await fetch(path, {cache: 'no-store'}); if (!r.ok) throw new Error(path + ' ' + r.status); return r.json(); }

/* ---------- 共用 ---------- */
function disc() { return `<div class="disc">研究模型輸出,非投資建議。<a href="#about">免責聲明</a></div>`; }
function more(body, label = '展開看更多') { return `<details class="explain"><summary>${label}</summary><div>${body}</div></details>`; }
function trk(kind) { return D.track?.kinds?.[kind] || {}; }
function lvTip(h) { return h && h.n ? `同等級歷史命中 ${pct(h.pct)}(${h.n} 筆${h.n < 20 ? ',筆數少,僅供參考' : ''})` : '同等級尚無對答案紀錄'; }
function stat(label, value, t, color) {
  return `<div class="card stat"${tip(t)}><div class="lbl">${label}</div><div class="kpi"${color ? ` style="color:${color}"` : ''}>${value}</div></div>`;
}
function lv(level) { return level ? `<span class="lv lv-${{高: 'h', 中: 'm', 低: 'l'}[level] || 'l'}">${level}</span>` : ''; }
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
  const m = (a.days > 0 ? `<span class="mark hold">已 ${a.days} 天${HOLDWORD[kind]}</span>` : '') + (a.run > 1 ? `<span class="mark">連續第 ${a.run} 天</span>` : '');
  return m ? `<div class="marks">${m}</div>` : '';
}
const GROUPS = [['new', '剛出現'], ['d12', '1–2 天'], ['d3', '3 天以上']];
function groupHit(kind, g) {
  const c = D.today.confirm_hit?.[kind];
  if (!c) return '';
  const v = g === 'new' ? pct(c.k0) : g === 'd12' ? `${pct(c.k1)}–${pct(c.k2)}` : pct(c.k3);
  const t = g === 'new' ? `研究命中率:剛出現 ${pct(c.k0)}` : g === 'd12' ? `研究命中率:已 1 天 ${pct(c.k1)}、已 2 天 ${pct(c.k2)}`
    : `研究命中率:已 3 天 ${pct(c.k3)}(4–5 天沒有研究數字)`;
  return `<span class="hit"${ttl(`${t}\n${c.source}`)}>命中 ${v}</span>`;
}
function pickRow(s, i, kind) {
  const t = [s.days > 0 ? `訊號日 ${md(s.date)}・已 ${s.days} 天${HOLDWORD[kind]}` : '今天判', `連續第 ${s.run} 天`, `機率 ${fmt(s.score)}・信心 ${s.level || '—'}`, lvTip(s.level_hit)].join('\n');
  const m = (s.days > 0 ? `<span class="mark hold">${s.days} 天</span>` : '') + (s.run > 1 ? `<span class="mark">連續 ${s.run} 天</span>` : '');
  return `<div class="pick" onclick="go('stock-${s.code}')"${ttl(t)}><div class="rank">${i + 1}</div>
  <div class="nm">${s.code}<span>${esc(s.name)}</span>${m ? `<div class="marks">${m}</div>` : ''}</div>
  <div class="spk">${spark(s.spark, MOBILE() ? 60 : 86)}</div>
  <div class="prob">${fmt(s.score)}${lv(s.level)}</div></div>`;
}
function groupBlock(L, kind, g, label) {
  const items = L.filter(s => s.group === g), top = items.slice(0, 3), rest = items.slice(3);
  const name = g === 'new' ? label : `${label}${HOLDWORD[kind]}`;
  return `<div class="grp"><b>${name}</b><span class="cnt">${items.length}</span><span class="sp"></span>${groupHit(kind, g)}</div>
  ${items.length ? top.map((s, i) => pickRow(s, i, kind)).join('') : `<div class="empty">—</div>`}
  ${rest.length ? `<details class="more"><summary>還有 ${rest.length} 檔</summary>
  <table class="minitable"><tr><th>代號</th><th>名稱</th><th>機率</th><th>信心</th><th>連續</th></tr>
  ${rest.map(s => `<tr onclick="go('stock-${s.code}')" style="cursor:pointer"><td>${s.code}</td><td>${esc(s.name)}</td><td>${fmt(s.score)}</td><td>${s.level || '—'}</td><td>${s.run} 天</td></tr>`).join('')}</table></details>` : ''}`;
}
function listCard(kind) {
  const L = D.today.lists[kind] || [], isLow = kind === 'low';
  const t = isLow ? '收盤可能是前後 11 天最低。前幾天判的,只列到今天都還沒跌破那天收盤的;組內依機率排序' : '收盤可能是前後 11 天最高。前幾天判的,只列到今天都還沒漲過那天收盤的;組內依機率排序';
  return `<div class="card"><div class="listhead"${ttl(t)}><span class="dot" style="background:${isLow ? 'var(--low)' : 'var(--high)'}"></span>
  <h2>${isLow ? '判低點' : '判高點'}</h2><span class="cnt">${L.length}</span></div>
  ${GROUPS.map(([g, label]) => groupBlock(L, kind, g, label)).join('')}</div>`;
}
function pageToday() {
  const T = D.today, lo = T.lists.low || [], hi = T.lists.high || [];
  const nNew = L => L.filter(s => s.group === 'new').length;
  const t60 = trk('low').top_60 || {}, base = trk('low').base_rate || {}, all = trk('low').all || {};
  return `<h1 class="pt">今日判斷</h1>
  <div class="summary">
   ${stat('今天判低點', nNew(lo), `另 ${lo.length - nNew(lo)} 檔前 1–5 天判、到今天還沒破底`, 'var(--low)')}
   ${stat('今天判高點', nNew(hi), `另 ${hi.length - nNew(hi)} 檔前 1–5 天判、到今天還沒創高`, 'var(--high)')}
   ${stat('低點命中率', pct(all.pct), `${REC()}全部判低點,${all.hits ?? 0} / ${all.n ?? 0} 筆(回放 + 實際追蹤)\n隨機猜中約 ${pct(base.pct, 0)}`)}
   ${stat('近 60 天前 3 檔', pct(t60.pct), `判低點前 3 檔,${t60.hits ?? 0} / ${t60.n ?? 0} 檔次`)}
  </div>
  <div class="grid2">${listCard('low')}${listCard('high')}</div>
  ${more(`「判低點」10 次大約只有 3 次真的是 11 天內的低點,錯的大多是普通日子。判斷之後幾天都沒破底,真的是低點的比例會變高
  (${esc(T.confirm_hit?.source || '')}),但那幾天的價格本來就是答案的一部分,等越久也越晚。
  這份清單是提醒你「這裡可能是近期的高點 / 低點,值得看一下」,買不買由你自己決定。<a href="#findings">看研究發現</a>`, '怎麼看這份清單')}
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
  <input id="q" placeholder="代號或名稱,例如 2330" aria-label="股票代號或名稱" autocomplete="off" value="${esc(Q)}" oninput="ac(this.value)" onfocus="ac(this.value)" onkeydown="acKey(event)"><div class="ac" id="ac"></div></div>${chips()}`;
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
/* K 線:預設整年塞進畫面寬度;「放大」時每根 K 棒固定寬度、可左右捲動(打開時捲到最新一天)。 */
let ZOOM = 'fit';
function kchart(S) {
  const M = MOBILE(), bars = S.bars || [];
  if (!bars.length) return '<div class="mutebox">沒有 K 線資料</div>';
  const sig = Object.fromEntries((S.signals || []).map(s => [s.date, s]));
  const fitW = M ? 420 : 860, zoomed = ZOOM === 'zoom', W = zoomed ? Math.max(fitW, bars.length * (M ? 9 : 12) + 16) : fitW;
  const H = M ? 320 : 300, VH = 50, pad = 8, top = 22, bot = H - VH - 24;
  const mx = Math.max(...bars.map(b => b[2])) * 1.015, mn = Math.min(...bars.map(b => b[3])) * 0.985, y = v => top + (mx - v) / (mx - mn) * (bot - top);
  const bw = (W - pad * 2) / bars.length, vmax = Math.max(...bars.map(b => b[5])) || 1, tw = Math.max(2.5, Math.min(5, bw * .45)); let g = '';
  for (let k = 0; k < 4; k++) { const v = mn + (mx - mn) * k / 3; g += `<line x1="0" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--grid)"/><text x="2" y="${y(v) - 3}" font-size="10" fill="var(--axis)">${fmt(v, 1)}</text>`; }
  let lastMonth = '';
  bars.forEach((b, i) => {
    const [d, o, h, l, c, v] = b, x = pad + i * bw + bw / 2, col = c >= o ? 'var(--up)' : 'var(--down)';
    if (d.slice(5, 7) !== lastMonth) {
      lastMonth = d.slice(5, 7);
      g += `<line x1="${x - bw / 2}" x2="${x - bw / 2}" y1="${top}" y2="${H - 24}" stroke="var(--grid)"/><text x="${x - bw / 2 + 2}" y="${H - 8}" font-size="10" fill="var(--axis)">${+lastMonth}月</text>`;
    }
    g += `<line x1="${x}" x2="${x}" y1="${y(h)}" y2="${y(l)}" stroke="${col}"/><rect x="${x - bw * .34}" y="${y(Math.max(o, c))}" width="${bw * .68}" height="${Math.max(1, Math.abs(y(o) - y(c)))}" fill="${col}"/>`;
    g += `<rect x="${x - bw * .34}" y="${H - 24 - v / vmax * VH}" width="${bw * .68}" height="${v / vmax * VH}" fill="${col}" opacity=".35"/>`;
    const s = sig[d];
    if (s && s.pred && s.pred !== 'none') {
      const isL = s.pred === 'low', c2 = isL ? 'var(--low)' : 'var(--high)', yy = isL ? y(l) + tw + 6 : y(h) - tw - 6;
      const st = s.truth == null ? 'wait' : s.truth === s.pred ? 'ok' : 'bad';
      const tri = isL ? `M${x - tw},${yy + tw * .8} L${x + tw},${yy + tw * .8} L${x},${yy - tw * .8} Z` : `M${x - tw},${yy - tw * .8} L${x + tw},${yy - tw * .8} L${x},${yy + tw * .8} Z`;
      g += `<path d="${tri}" fill="${st === 'ok' ? c2 : 'var(--card)'}" stroke="${c2}" stroke-width="1.3" ${st === 'wait' ? 'stroke-dasharray="2 1.5"' : ''}><title>${d} 判${LBL[s.pred]}:${st === 'wait' ? '待驗證' : st === 'ok' ? '對' : '錯'}</title></path>`;
    }
    if (i === bars.length - 1) g += `<rect x="${x - bw / 2}" y="${top - 6}" width="${bw}" height="${bot - top + 12}" fill="var(--accent)" opacity=".06"/><text x="${x - bw}" y="${top - 9}" font-size="10" font-weight="700" fill="var(--axis)" text-anchor="end">${md(d)} ▸</text>`;
  });
  const t = `${S.price === 'actual' ? '實際成交價(證交所)' : '還原價(把除權息補回去)'},紅漲綠跌;三角形 = 這天的判斷,5 個交易日後對答案`;
  const svg = `<svg viewBox="0 0 ${W} ${H}" ${zoomed ? `width="${W}" height="${H}"` : 'width="100%"'} style="display:block">${g}</svg>`;
  return `<div class="${zoomed ? 'chartscroll' : 'chartwrap'}"${ttl(t)}>${svg}</div>
  <div class="legend"><span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="var(--low)"/></svg>判低點</span><span><svg width="12" height="10"><path d="M1,1 L11,1 L6,9Z" fill="var(--high)"/></svg>判高點</span>
  <span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="var(--low)"/></svg>對</span><span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="var(--card)" stroke="var(--ink2)" stroke-width="1.4"/></svg>錯</span><span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="var(--card)" stroke="var(--ink2)" stroke-width="1.4" stroke-dasharray="2 1.5"/></svg>待驗證</span></div>`;
}
function bar(label, v, color, txt) {
  return `<div class="cls"><span>${label}</span><div class="bar" style="margin:0;height:8px"><i style="width:${Math.max(0, Math.min(1, v)) * 100}%;background:${color}"></i></div><span class="right">${txt}</span></div>`;
}
function pageSearch() {
  const legend = [[REC(), 't-ok', `${REC()}成分股,每天的推薦清單只看這些`], ['池外', 't-warn', '其他上市普通股,可查,僅供參考'], ['低波動', 't-none', '推薦範圍以外、每日漲跌太小,判斷不適用'], ['不支援', 't-bad', 'ETF、上櫃、興櫃、特別股']];
  return `<h1 class="pt">個股查詢</h1>${searchBox()}
  <div class="legendtags">${legend.map(([a, c, d]) => `<span class="tag ${c}"${tip(d)}>${a}</span>`).join('')}</div>${disc()}`;
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
    const hitTxt = c ? (a.days <= 3 ? pct(c[key]) : `≥3 天 ${pct(c.k3)}`) : '—';
    rows.push(`<tr><td><span class="tag ${tagCls(k)}">判${LBL[k]}</span></td><td>${md(a.date)}</td><td>${fmt(a.score)}</td>
      <td>${a.days === 0 ? '剛出現' : `${a.days} 天${HOLDWORD[k]}`}</td><td>第 ${a.run} 天</td><td>${hitTxt}</td></tr>`);
  }
  if (!rows.length) return '';
  const t = `只列最近 5 個交易日內、到今天都還沒破底(低點)/ 沒創高(高點)的訊號。等越多天,真的是低點的比例越高,但也越晚。\n${D.today.confirm_hit?.source || ''}`;
  return `<div class="card"><h3${ttl(t)}>近 5 天訊號</h3><div class="tblwrap"><table class="tbl"><tr><th>判斷</th><th>訊號日</th><th>機率</th><th>到今天</th><th>連續</th><th>研究命中</th></tr>${rows.join('')}</table></div></div>`;
}
async function pageStock(code) {
  const ix = (D.index || []).find(r => r[0] === code);
  if (!ix) return `<h1 class="pt">個股查詢</h1>${searchBox()}<div class="badbox">查無代號 ${esc(code)}。目前只支援上市普通股。</div>${disc()}`;
  if (ix[2] === 'nosup') return `<h1 class="pt">個股查詢</h1>${searchBox()}<div class="card"><div class="row"><h2 style="margin:0">${code} ${esc(ix[1])}</h2>${typeTag('nosup')}<span class="tag t-none">${MARKET[ix[3]] || ''}</span></div>
    <div class="badbox" style="margin-top:12px"><b>目前不支援</b>・${esc(ix[4])}</div></div>${disc()}`;
  let S; try { S = await loadStock(code); } catch (e) { S = null; }
  if (!S) return `<h1 class="pt">個股查詢</h1>${searchBox()}<div class="badbox">讀不到 ${code} 的資料。</div>${disc()}`;
  const t = S.today, P = t.stack || {}, p = P.pred || 'none';
  let pre = '';
  const outHit = trk('low').out_pool;
  if (S.status === 'out') pre = `<div class="warnbox"${tip(`這檔不在${REC()}推薦範圍,判斷照算,僅供參考。回放期間推薦範圍以外股票的判低點命中率 ${pct(outHit?.pct)}(${outHit?.n || 0} 筆)`)}>
    <b>⚠ 推薦範圍外</b>・僅供參考・池外命中 ${pct(outHit?.pct)}</div>`;
  if (S.status === 'lowvol') pre = `<div class="mutebox"${ttl('這類股票的「11 天最低」常常只差一兩檔,判斷沒有參考價值')}><b>低波動・判斷不適用</b>・漲跌中位數 ${fmt(S.move)}% &lt; ${D.meta.rules.min_move}%
   <details style="margin-top:6px"><summary style="cursor:pointer">看模型輸出</summary><div style="margin-top:6px">今天判${LBL[p]}${P.score != null ? `(機率 ${fmt(P.score)})` : ''}。</div></details></div>`;
  if (S.status === 'halted') pre = `<div class="badbox"${ttl('停牌、處置或資料未更新')}><b>${S.date} 無交易</b>・今天沒有判斷</div>`;
  if (S.status === 'nodata') pre = `<div class="mutebox"><b>資料不足</b>・${(S.bars || []).length ? '至少要 16 個交易日的 K 線' : '還沒有這檔的 K 線'}</div>`;
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
  const RS = '研究結果 TW200 2026 1–9 月';
  const past = (S.signals || []).filter(x => x.pred !== 'none').slice().reverse();
  const Y = S.year || {}, yr = Y.year || S.date.slice(0, 4);
  const pastRow = x => `<tr><td>${md(x.date)}</td><td><span class="tag ${tagCls(x.pred)}">${LBL[x.pred]}</span></td><td>${fmt(x.score)}</td><td>${x.level || '—'}</td>
     <td>${x.truth == null ? '<span class="tag t-wait">待驗證</span>' : x.truth === x.pred ? '<span class="tag t-ok">對</span>' : `<span class="tag t-bad">錯・實為${LBL[x.truth]}</span>`}</td></tr>`;
  const pastTable = rows => `<div class="tblwrap"><table class="tbl"><tr><th>日期</th><th>判斷</th><th>機率</th><th>信心</th><th>結果</th></tr>${rows.map(pastRow).join('')}</table></div>`;
  const yrow = k => { const r = Y[k] || {}, wait = (r.n || 0) - (r.graded || 0);
    return `<tr><td><span class="tag ${tagCls(k)}">判${LBL[k]}</span></td><td>${r.n || 0} 天${wait ? ` <span class="wait"${ttl('還沒滿 5 個交易日,還沒有答案')}>+${wait} 待驗證</span>` : ''}</td><td>${r.graded ? `${r.hits} 天` : '—'}</td><td class="pctc">${pct(r.pct)}</td></tr>`; };
  const pxTip = S.price === 'actual' ? '實際成交價(證交所官方資料)' : '還原價(把除權息補回去);這檔沒有證交所官方資料';
  const tile = (label, v, t) => `<div class="tile"${tip(t)}><div class="lbl">${label}</div><div class="kpi">${v}</div></div>`;
  const vtip = p === 'none' ? '' : `機率 ${fmt(P.score)}・信心 ${P.level}\n${S.status !== 'pool' ? `${(STATUS[S.status] || ['池外'])[0]}股票:命中率見上方` : lvTip(hit)}`;
  return `<h1 class="pt">個股查詢</h1>${searchBox()}
  <div class="stack">
  <div class="card"><div class="row"><h2 style="margin:0;font-size:20px">${code} ${esc(S.name)}</h2>${typeTag(S.status)}<div class="sp"></div>
   <div class="right"${ttl(pxTip)}><span class="px" style="font-size:20px">${fmt(S.close ?? t.close ?? last[4])}</span> ${chg(S.chg_pct ?? t.chg_pct)}
    <div class="asof">${S.close_date ? md(S.close_date) : md(S.date)} 收盤${S.price === 'adj' ? ' <span class="tag t-none">還原價</span>' : ''}</div></div></div></div>
  ${pre}
  ${t.stack ? `<div class="grid2" style="${dim}">
   <div class="card"><div class="verdict"><div class="vicon" style="background:${p === 'low' ? 'var(--low-bg)' : p === 'high' ? 'var(--high-bg)' : 'var(--mute-bg)'};color:${p === 'low' ? 'var(--low)' : p === 'high' ? 'var(--high)' : 'var(--ink3)'}">${icon}</div>
     <div><div class="vtitle">${p === 'none' ? '非極值・一般日子' : '可能是' + LBL[p]}</div>
     ${p !== 'none' ? `<div class="vprob"${tip(vtip)}>${fmt(P.score)}${lv(P.level)}</div>` : ''}
     ${p !== 'none' ? marks(S.active?.[p], p) : ''}</div></div>
     <h3 style="margin-top:16px"${ttl('三類機率加起來是 1,最大的那類就是判斷。研究顯示只挑機率高的,命中率只升一點點,真的轉折點卻會漏掉很多,所以機率只當參考。')}>三類機率</h3>
     ${bar('高點', P.p_high, 'var(--high)', fmt(P.p_high))}${bar('低點', P.p_low, 'var(--low)', fmt(P.p_low))}${bar('非極值', P.p_none, 'var(--ink3)', fmt(P.p_none))}
     ${more(sug, '怎麼解讀')}</div>
   <div class="card"><h3${ttl(`這檔 ${yr} 年每天的判斷,5 個交易日後對答案(回放 + 實際追蹤)`)}>${yr} 成績</h3>
     <table class="tbl ytable"><tr><th></th><th>判斷</th><th>對</th><th>命中率</th></tr>${yrow('low')}${yrow('high')}</table>
     <div class="tiles t3">
     ${tile('研究命中率', pct(R.prec_low), `判低點命中率・${RS}`)}
     ${tile('研究找到率', pct(R.rec_low), `真低點找到率・${RS}`)}
     ${tile('隨機猜中', pct(R.base_low), `隨便挑一天剛好是低點・${RS}`)}</div></div>
  </div>` : ''}
  ${activeCard(S)}
  <div class="card" style="${dim}"><div class="row"><h3 style="margin:0">${(S.bars || [])[0]?.[0]?.slice(0, 4) === yr ? yr + ' 整年' : 'K 線'}</h3><div class="sp"></div>${(S.bars || []).length ? seg(ZOOM, [['fit', '全年'], ['zoom', '放大']], 'ZOOM') : ''}</div>${kchart(S)}</div>
  <div class="card" style="${dim}"><h3>${yr} 的判斷</h3>${past.length ? pastTable(past.slice(0, 10)) + (past.length > 10 ? `<details class="more"><summary>還有 ${past.length - 10} 天</summary>${pastTable(past.slice(10))}</details>` : '') : '<div class="empty">今年沒有判斷</div>'}</div>
  </div>${disc()}`;
}

/* ---------- 成績追蹤 ---------- */
function pageTrack() {
  const T = trk(TK), dates = D.track.dates || {};
  const series = T.series || [], W = MOBILE() ? 420 : 860, H = MOBILE() ? 240 : 220, top = 14, bot = H - 26;
  let g = '';
  if (series.length > 1) {
    const ymax = Math.max(50, ...series.map(s => s[1])) / 100, y = v => bot - v / ymax * (bot - top), x = i => 40 + i / (series.length - 1) * (W - 50);
    const li = series.findIndex(s => s[2] === 'daily');
    if (li >= 0) g += `<rect x="${x(li)}" y="${top}" width="${x(series.length - 1) - x(li) + 1}" height="${bot - top}" fill="var(--low-bg)" opacity=".7"/><text x="${x(li) + 4}" y="${top + 14}" font-size="11" fill="var(--low)" font-weight="700">實際</text>`;
    g += `<text x="${li > 0 ? x(li) - 6 : W - 12}" y="${top + 14}" font-size="11" fill="var(--axis)" text-anchor="end">回放</text>`;
    for (let t = 0; t <= ymax + 1e-9; t += .1) g += `<line x1="40" x2="${W - 10}" y1="${y(t)}" y2="${y(t)}" stroke="var(--grid)"/><text x="34" y="${y(t) + 4}" font-size="10" fill="var(--axis)" text-anchor="end">${Math.round(t * 100)}%</text>`;
    const br = (T.base_rate?.pct || 0) / 100;
    g += `<line x1="40" x2="${W - 10}" y1="${y(br)}" y2="${y(br)}" stroke="var(--ink3)" stroke-dasharray="4 3"/><text x="${W - 12}" y="${y(br) - 4}" font-size="10" fill="var(--ink2)" text-anchor="end">隨機 ${pct(T.base_rate?.pct, 0)}</text>`;
    g += `<polyline points="${series.map((s, i) => `${x(i)},${y(s[1] / 100)}`).join(' ')}" fill="none" stroke="${TK === 'low' ? 'var(--low)' : 'var(--high)'}" stroke-width="2"/>`;
    (MOBILE() ? [0, .5, 1] : [0, .25, .5, .75, 1]).forEach(f => { const i = Math.round(f * (series.length - 1)); g += `<text x="${x(i)}" y="${H - 6}" font-size="10" fill="var(--axis)" text-anchor="middle">${md(series[i][0])}</text>`; });
  }
  const R = (D.research?.classification || []).find(r => r.year === '2026') || {};
  const n = r => r?.n ? `${r.hits} / ${r.n} 檔次` : '尚無資料';
  const lvt = T.levels || {}, daily = T.daily || [];
  const dailyTable = rows => `<div class="tblwrap"><table class="tbl"><tr><th>判斷日</th><th>前 3 檔</th><th>結果</th><th>來源</th></tr>
   ${rows.map(r => `<tr><td>${md(r.date)}</td><td>${r.picks.map(p => `<a href="#stock-${p.code}" style="color:inherit">${p.code} ${esc(p.name)}</a>${p.truth == null ? '' : p.truth === TK ? ' <span class="tag t-ok">對</span>' : ' <span class="tag t-bad">錯</span>'}`).join('、')}</td>
    <td>${r.hits == null ? '<span class="tag t-wait">待驗證</span>' : `<span class="tag ${r.hits >= 2 ? 't-ok' : r.hits === 1 ? 't-warn' : 't-bad'}">${r.hits} / ${r.picks.length} 對</span>`}</td>
    <td><span class="tag ${r.source === 'daily' ? 't-live' : 't-replay'}">${r.source === 'daily' ? '實際' : '回放'}</span></td></tr>`).join('')}</table></div>`;
  const sub = `${REC()}每天的判斷當天就存檔,不會事後修改;5 個交易日後自動對答案。資料 ${dates.first || ''} ~ ${dates.last || ''},已對答案 ${dates.n_graded || 0} 天${dates.live_start ? `,${dates.live_start} 起為實際追蹤` : ',目前都是回放'}。回放 = 上線前用同一個模型逐日產生。`;
  return `<div class="row pt"><h1${ttl(sub)}>成績追蹤</h1><div class="sp"></div>${seg(TK, [['low', '判低點'], ['high', '判高點']], 'TK')}</div>
  <div class="grid4 k2" style="margin-bottom:16px">
   ${stat('近 20 天・前 3', pct(T.top_20?.pct), `前 3 檔,${n(T.top_20)}`)}${stat('近 60 天・前 3', pct(T.top_60?.pct), `前 3 檔,${n(T.top_60)}`)}
   ${stat(`${T.all_ytd?.year || ''} 全部`, pct(T.all_ytd?.pct), `全部判斷,${n(T.all_ytd)}\n研究結果 TW200 2026 1–9 月 ${pct(TK === 'low' ? R.prec_low : R.prec_high)}`)}
   ${stat('隨機猜中', pct(T.base_rate?.pct), `隨便挑一天剛好是${LBL[TK]}(${REC()}、已對答案的日子)`)}
  </div>
  <div class="card" style="margin-bottom:16px"><h3${ttl(`${REC()}全部判斷的命中率,60 天移動`)}>命中率・60 天移動</h3>
   ${series.length > 1 ? `<div class="chartwrap"><svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block">${g}</svg></div>` : '<div class="mutebox">對答案的天數還不夠畫圖(至少 20 天)。</div>'}</div>
  <div class="grid2" style="margin-bottom:16px">
   <div class="card"><h3${ttl('信心等級 = 訓練期內機率的三等分')}>信心等級</h3><table class="tbl lvtable"><tr><th>信心</th><th>命中率</th><th>對 / 判斷</th></tr>
    ${['高', '中', '低'].map(l => `<tr><td>${l}</td><td>${pct(lvt[l]?.pct)}</td><td>${lvt[l] ? `${lvt[l].hits} / ${lvt[l].n}` : '—'}</td></tr>`).join('')}
    <tr><td>全部</td><td>${pct(T.all?.pct)}</td><td>${T.all ? `${T.all.hits} / ${T.all.n}` : '—'}</td></tr></table></div>
   <div class="card"><h3${ttl('個股查詢可以查其他上市股,判斷照算,這是它們過去的命中率')}>推薦範圍以外</h3><table class="tbl lvtable"><tr><th>股票</th><th>命中率</th><th>對 / 判斷</th></tr>
    <tr><td>${REC()}</td><td>${pct(T.all?.pct)}</td><td>${T.all ? `${T.all.hits} / ${T.all.n}` : '—'}</td></tr>
    <tr><td>池外</td><td>${pct(T.out_pool?.pct)}</td><td>${T.out_pool ? `${T.out_pool.hits} / ${T.out_pool.n}` : '—'}</td></tr></table></div></div>
  <div class="card"><h3>每日明細・前 3 檔</h3>${dailyTable(daily.slice(0, 10))}
   ${daily.length > 10 ? `<details class="more"><summary>還有 ${daily.length - 10} 天</summary>${dailyTable(daily.slice(10))}</details>` : ''}</div>
  ${disc()}`;
}

/* ---------- 研究發現 ---------- */
/* 只放方向性結論(找得到轉折區、高低點不判反、命中率約三成 → 定位為決策輔助)。數字全部來自 findings.json,由 results/ 的結果檔產生。 */
function pageFindings() {
  const F = D.findings;
  if (!F) return '<div class="badbox">讀不到研究結果。</div>';
  const r = F.recall, p = F.precision, c = F.confirm;
  const hits = Math.round(p.low / 10);
  const dots = Array.from({length: 10}, (_, i) => `<i class="${i < hits ? 'on' : ''}"></i>`).join('');
  const uses = [['判斷當提醒,不當買賣指令', '它告訴你「這裡可能是近期低點 / 高點,值得看一下」,買不買由你自己決定。'],
    ['看「已幾天沒破底 / 沒創高」', '天數越多越可能是真的轉折,但也越晚。'],
    ['機率只當參考', '研究顯示只挑機率高的,命中率只升一點點,卻會漏掉更多真的轉折點。'],
    ['5 天後對答案', '每天的判斷都會存檔,5 個交易日後在<a href="#track">成績追蹤</a>看對了多少。']];
  return `<h1 class="pt">研究發現</h1>
  <div class="stack">
  <div class="cards">
   <div class="find good"><h3>找得到轉折區</h3><div class="big">${pct(r.low2)} <small>低點 ±2 天</small></div>
    ${more(`真低點、真高點當天就被判到的比例是 ${pct(r.low)} / ${pct(r.high)};放寬到前後 2 個交易日,是 ${pct(r.low2)} / ${pct(r.high2)}。轉折的「區域」大致抓得到。`)}</div>
   <div class="find good"><h3>高低點不判反</h3><div class="big">${F.cross} <small>次・${F.years[0]}–${F.years[F.years.length - 1]}</small></div>
    ${more(`${F.years.join('、')} 年每一天的判斷裡,真低點從沒被判成高點,真高點也從沒被判成低點。錯的都是把普通日子當成高 / 低點,方向不會弄反。`)}</div>
   <div class="find bad"><h3>命中率約三成</h3><div class="big">${pct(p.low)} <small>判低點</small></div>
    <div class="dots"${ttl(`10 次約對 ${hits} 次`)}>${dots}</div>
    ${more(`判低點的命中率 ${pct(p.low)}、判高點 ${pct(p.high)}。隨便挑一天剛好是低點的機率是 ${pct(p.base_low)},模型好很多,但 10 次還是錯 7 次。`)}</div>
   <div class="find"><h3>定位:決策輔助</h3><div class="big" style="font-size:20px">提醒,不是指令</div>
    ${more('方向抓得到、但單一天的判斷不夠準,適合用來提醒「這附近可能是轉折」,再由你自己看線圖、基本面決定要不要動作。')}</div>
  </div>
  <div class="card"><h2>沒破底越久,命中越高</h2>
   <div class="tblwrap"><table class="tbl"><tr><th></th><th>剛出現</th><th>1 天</th><th>2 天</th><th>3 天</th><th>隨機</th></tr>
    ${['low', 'high'].map(k => `<tr><td>判${LBL[k]}</td><td>${pct(c[k].k0)}</td><td>${pct(c[k].k1)}</td><td>${pct(c[k].k2)}</td><td>${pct(c[k].k3)}</td><td>${pct(c[k].base)}</td></tr>`).join('')}</table></div>
   ${more(`天數 = 判斷之後已經幾天沒破底(低點)/ 沒創高(高點)。今日判斷把訊號依這個天數分組,每組附上這張表的研究數字。這些數字用到判斷之後那幾天的價格,所以要等到那天才知道,也就越晚。<br>${esc(c.source)}`)}</div>
  <div class="card"><h2>怎麼用</h2><div class="acc">${uses.map(([b, t]) => `<details><summary>${b}</summary><p>${t}</p></details>`).join('')}</div></div>
  ${more(`這個模型適合<b>提醒你哪裡可能是高點、低點</b>,不適合拿來自動買賣。以上是 Stacking 的研究結果(${esc(TRAIN())}、訓練門檻 0%、${F.years[0]}–${F.years[F.years.length - 1]} 三年平均),數字直接讀研究結果檔:method_kline_peak/results/ 的 ${F.sources.map(esc).join('、')}。`, '資料來源')}
  </div>${disc()}`;
}

/* ---------- 方法與說明 ---------- */
function pageAbout() {
  const bars = [42, 46, 40, 37, 33, 28, 35, 39, 44, 47, 45].map((h, i) => `<i class="${i === 5 ? 't' : i < 5 ? '' : 'f'}" style="height:${h * 2}px"></i>`).join('');
  const C = (D.research?.classification || []).slice().sort((a, b) => a.year.localeCompare(b.year));
  const mi = D.meta.model || {};
  const yrs = a => (a || []).map(d => d.slice(0, 4)).filter((v, i, s) => s.indexOf(v) === i).join('–');
  const faq = [['判低點就會漲嗎?', '不一定。低點只代表 11 天內最低,之後可能只是小反彈。'],
    ['為什麼盤中查到的是昨天的判斷?', '判斷要用收盤價,每天 18:00 左右更新。'],
    ['為什麼價格和看盤軟體不一樣?', '這裡用還原價(把除權息補回去),和訓練時一致。'],
    ['為什麼有些股票顯示「不適用」?', `${REC()}以外、每日漲跌幅中位數低於 ${D.meta.rules.min_move}% 的股票,高低點常常只差一兩檔,判斷沒有參考價值。`],
    ['過去的判斷會變嗎?', '不會。每天的判斷當天就存檔,之後不重算;除權息後還原價變動也不影響已存的判斷。']];
  return `<h1 class="pt">方法與說明</h1>
  <div class="stack">
  <div class="card"><h2>高點 / 低點</h2>
   <div class="grid2"><div><div class="label-demo">${bars}</div><div class="legend"><span>t−5 … t−1</span><span style="color:var(--low);font-weight:700">t(今天)</span><span>t+1 … t+5(要等 5 天)</span></div></div>
   <div class="defs"><div><span class="tag t-low">低點</span>今天收盤是 11 天最低</div><div><span class="tag t-high">高點</span>今天收盤是 11 天最高</div><div><span class="tag t-none">非極值</span>其他(約 85% 的日子)</div></div></div>
   ${more('看 11 天:今天(第 6 天)加前後各 5 天。模型只看今天和前 5 天的 6 根 K 線,所以收盤後就能判斷;但真正的答案要等 5 個交易日後才知道。')}</div>
  <div class="card"><h2>Stacking 三步驟</h2><div class="steps">
   <div class="step"><b>1. 看 6 根 K 線</b><span>29 個數字</span></div>
   <div class="step"><b>2. 像不像過去的高 / 低點</b><span>AE + OC-SVM 打分數</span></div>
   <div class="step"><b>3. 換成三類機率</b><span>邏輯迴歸・高 / 中 / 低信心</span></div></div>
   ${more(`<p><b>1.</b> 今天和前 5 天的開高低收(除以今天收盤)和成交量(除以 10 日均量),共 29 個數字。</p>
   <p><b>2.</b> 高點、低點各一組 AE + OC-SVM,學過去真的高點、低點長什麼樣子,對今天各打一個分數。</p>
   <p><b>3.</b> 邏輯迴歸把兩個分數換成高點 / 低點 / 非極值三類機率,最大的那類就是判斷;機率依訓練期分布分成高 / 中 / 低三種信心。</p>
   <p>訓練:${esc(TRAIN())}。${mi.year} 年用的模型以 ${yrs(mi.train)} 訓練:前 3 年(${yrs(mi.train_a)})學兩組分數,最後 1 年(${yrs(mi.train_b)})學邏輯迴歸,中間留 5 個交易日間隔;標籤門檻 ${D.meta.profile?.train_min_amp || 0}%,種子 ${mi.seed}。每年 1 月第 6 個交易日後自動重訓。</p>
   <p>推薦範圍:${REC()}成分股,每天全部給判斷(低波動股也照樣判斷)。</p>`)}</div>
  <div class="card"><h2${ttl(`研究結果,${TRAIN()},Stacking。錯的都是和非極值混淆,高點和低點沒有互相判錯。`)}>歷史命中率</h2><div class="tblwrap"><table class="tbl">
   <tr><th>年</th><th>macro-F1</th><th>低點命中</th><th>高點命中</th><th>低點找到</th><th>高點找到</th><th>隨機(低點)</th><th>判反</th></tr>
   ${C.map(r => `<tr><td>${r.year}${r.year === '2026' ? '(1–9 月)' : ''}</td><td>${pct(r.macro_f1, 2)}</td><td>${pct(r.prec_low)}</td><td>${pct(r.prec_high)}</td><td>${pct(r.rec_low)}</td><td>${pct(r.rec_high)}</td><td>${pct(r.base_low)}</td><td>${r.cross} 次</td></tr>`).join('')}</table></div></div>
  <div class="card"><h2>常見問題</h2><div class="acc">${faq.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div></div>
  <div class="badbox" id="disclaimer"><b>免責聲明</b><br>本網站為個人學術研究之模型輸出展示,非證券投資顧問服務,不構成任何買賣建議或推介。
   模型歷史命中率約 3 成,判斷僅供參考方向。投資有風險,請自行判斷並承擔損益。本網站不收取任何費用,亦無廣告或任何形式之報酬。</div>
  ${more(`本頁的命中率是研究結果,直接讀 repo 裡的結果檔(${(D.research?.sources || []).map(esc).join('、')}),沒有重算。`, '資料來源')}
  </div>`;
}

/* ---------- 路由 ---------- */
const NAV = [['today', '今日判斷', 'M3 12h4l3-8 4 16 3-8h4'], ['stock', '個股查詢', 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9 16-4-4'], ['track', '成績追蹤', 'M4 20V10m6 10V4m6 16v-7m4 7H2'], ['findings', '研究發現', 'M9 3h6m-5 0v6L4 19a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2l-6-10V3'], ['about', '方法與說明', 'M12 8h.01M11 12h1v5h1M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z']];
function go(h) { location.hash = h; }
function header() {
  const M = D.meta, c = M.check || {};
  const yrs = (M.model?.train || []).map(d => d.slice(0, 4));
  const t = [`判斷基準日 ${M.asof} 收盤`, `產生於 ${(M.created || '').slice(0, 16)}`, `模型 Stacking・${M.profile?.pool_label || 'TW200'} 訓練 ${yrs[0] || ''}–${yrs[1] || ''}`, `推薦範圍 ${REC()}`];
  if (c.online === false && M.source !== 'replay') t.push(`這次批次沒有連網,K 線只到 ${M.asof}`);
  document.getElementById('hmeta').innerHTML = `<span${ttl(t.join('\n'))}>判斷基準日 <b>${dlabel(M.asof)}</b></span>${M.source === 'replay' ? ` <span class="tag t-replay"${ttl('回放:上線前用同一個模型逐日產生的判斷')}>回放</span>` : ''}`;
  const b = [];
  const age = (Date.now() - new Date(`${M.asof}T14:30:00+08:00`).getTime()) / 864e5;
  if (age > 4) b.push(`<div class="warnbox"${ttl('網頁顯示的是判斷基準日收盤後的資料;之後的股價還沒更新')}><b>資料只到 ${dlabel(M.asof)}</b>・不是最新股價</div>`);
  if (c.stale) b.push(`<div class="badbox"${ttl('資料來源晚到時批次會在稍後補跑')}><b>資料還沒更新</b>・顯示 ${M.asof} 的判斷</div>`);
  if ((c.missing_pool || []).length) b.push(`<div class="warnbox"${ttl('這幾檔今天沒有判斷')}><b>${c.missing_pool.length} 檔缺 ${md(M.asof)} 資料</b>・${c.missing_pool.slice(0, 8).join('、')}${c.missing_pool.length > 8 ? '…' : ''}</div>`);
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
  app.querySelectorAll('.chartscroll').forEach(e => { e.scrollLeft = e.scrollWidth; });
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
