/* K 線高低點判斷:靜態前端。資料全部來自 data/*.json(每日批次產生)。
   判斷方法同 final 分支:規則挑候選 → AE + OC-SVM;每檔只有判斷、規則候選、分數(OC-SVM 分數,只用來排序)。推薦範圍和訓練用的股票相同(台灣 200 剔除低波動股);定位為看盤輔助。
   版面原則:畫面只放數字、圖和 2–6 字的標籤;說明文字放在提示框(data-tip / title)或「展開看更多」裡。 */
const D = {shards: {}};
const LBL = {low: '低點', high: '高點', none: '非極值'};
const STATUS = {pool: ['台灣 200', 't-ok'], out: ['池外', 't-warn'], lowvol: ['低波動', 't-none'], nosup: ['不支援', 't-bad'], nodata: ['資料不足', 't-none'], halted: ['今日無交易', 't-none']};
const MARKET = {TWSE: '上市', OTC: '上櫃', ESB: '興櫃', ETF: 'ETF'};
let TK = 'low', Q = '';

const fmt = (x, d = 2) => x == null || !isFinite(x) ? '—' : Number(x).toLocaleString('zh-TW', {minimumFractionDigits: d, maximumFractionDigits: d});
const pct = (x, d = 1) => x == null ? '—' : fmt(x, d) + '%';
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const WD = '日一二三四五六';
const dlabel = d => { const t = new Date(d + 'T00:00:00'); return `${d}(${WD[t.getDay()]})`; };
const md = d => d ? d.slice(5).replace('-', '/') : '';
const tagCls = k => k === 'low' ? 't-low' : k === 'high' ? 't-high' : 't-none';
const REC = () => D.meta?.profile?.recommend_label || '台灣 200(剔除低波動股)';
const TRAIN = () => `${D.meta?.profile?.pool_label || '台灣 200'}(剔除低波動股)`;
const MOBILE = () => innerWidth < 760;
/* 提示框:滑鼠移上去或點一下(手機)才出現;tip 用在卡片,ttl 用在整列可點的元素(只給桌機 hover) */
const tip = t => t ? ` data-tip="${esc(t)}" tabindex="0"` : '';
const ttl = t => t ? ` title="${esc(t)}"` : '';

async function j(path) { const r = await fetch(path, {cache: 'no-store'}); if (!r.ok) throw new Error(path + ' ' + r.status); return r.json(); }

/* ---------- 共用 ---------- */
function disc() { return `<div class="disc">研究模型輸出,非投資建議。<a href="#about">免責聲明</a></div>`; }
function more(body, label = '展開看更多') { return `<details class="explain"><summary>${label}</summary><div>${body}</div></details>`; }
function trk(kind) { return D.track?.kinds?.[kind] || {}; }
const sc = x => fmt(x, 1);
function stat(label, value, t, color) {
  return `<div class="card stat"${tip(t)}><div class="lbl">${label}</div><div class="kpi"${color ? ` style="color:${color}"` : ''}>${value}</div></div>`;
}
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
function pickRow(s, i, kind) {
  const t = [s.days > 0 ? `訊號日 ${md(s.date)}・已 ${s.days} 天${HOLDWORD[kind]}` : '今天判', `連續第 ${s.run} 天`, `分數 ${sc(s.score)}`].join('\n');
  const m = (s.days > 0 ? `<span class="mark hold">${s.days} 天</span>` : '') + (s.run > 1 ? `<span class="mark">連續 ${s.run} 天</span>` : '');
  return `<div class="pick" onclick="go('stock-${s.code}')"${ttl(t)}><div class="rank">${i + 1}</div>
  <div class="nm">${s.code}<span>${esc(s.name)}</span>${m ? `<div class="marks">${m}</div>` : ''}</div>
  <div class="spk">${spark(s.spark, MOBILE() ? 60 : 86)}</div>
  <div class="score">${sc(s.score)}</div></div>`;
}
function groupBlock(L, kind, g, label) {
  const items = L.filter(s => s.group === g), top = items.slice(0, 3), rest = items.slice(3);
  const name = g === 'new' ? label : `${label}${HOLDWORD[kind]}`;
  return `<div class="grp"><b>${name}</b><span class="cnt">${items.length}</span></div>
  ${items.length ? top.map((s, i) => pickRow(s, i, kind)).join('') : `<div class="empty">—</div>`}
  ${rest.length ? `<details class="more"><summary>還有 ${rest.length} 檔</summary>
  <table class="minitable"><tr><th>代號</th><th>名稱</th><th>分數</th><th>連續</th></tr>
  ${rest.map(s => `<tr onclick="go('stock-${s.code}')" style="cursor:pointer"><td>${s.code}</td><td>${esc(s.name)}</td><td>${sc(s.score)}</td><td>${s.run} 天</td></tr>`).join('')}</table></details>` : ''}`;
}
function listCard(kind) {
  const L = D.today.lists[kind] || [], isLow = kind === 'low';
  const t = isLow ? '收盤可能是前後 11 天最低。前幾天判的,只列到今天都還沒跌破那天收盤的;組內依分數排序' : '收盤可能是前後 11 天最高。前幾天判的,只列到今天都還沒漲過那天收盤的;組內依分數排序';
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
  ${more(`「判低點」10 次大約只有 3 次真的是 11 天內的低點,錯的大多是普通日子。判斷之後幾天都沒破底的,越可能是真的低點
  (真的低點後面 5 天一定不會破底),但等越久也越晚。分數是「和過去真的低點 / 高點有多像」,只用來排序。
  這份清單是看盤時的提醒:「這裡可能是近期的高點 / 低點,值得看一下」,買不買由你自己決定。<a href="#findings">看研究發現</a>`, '怎麼看這份清單')}
  ${disc()}`;
}

/* ---------- 個股查詢 ---------- */
function typeTag(st) { const [n, c] = STATUS[st] || ['?', 't-none']; return `<span class="tag ${c}">${n}</span>`; }
function chips() {
  const byCode = Object.fromEntries((D.index || []).map(r => [r[0], r]));
  const pick = (pref, st) => byCode[pref]?.[2] === st ? byCode[pref] : (D.index || []).find(r => r[2] === st);
  const list = [['2454', '聯發科'], ['2330', '台積電'], ['8046', '南電'], ['3374', '精材']];
  for (const [pref, st] of [['2412', 'lowvol']]) { const r = pick(pref, st); if (r) list.push([r[0], r[1]]); }   /* 3374 精材 = 推薦範圍外的例子 */
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
    : '<div style="color:var(--ink3)">找不到這個代號或名稱</div>';
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
  const t = `${S.price === 'actual' ? '實際成交價(未還原)' : '還原價(把除權息補回去)'},紅漲綠跌;三角形 = 這天的判斷,5 個交易日後對答案`;
  const svg = `<svg viewBox="0 0 ${W} ${H}" ${zoomed ? `width="${W}" height="${H}"` : 'width="100%"'} style="display:block">${g}</svg>`;
  return `<div class="${zoomed ? 'chartscroll' : 'chartwrap'}"${ttl(t)}>${svg}</div>
  <div class="legend"><span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="var(--low)"/></svg>判低點</span><span><svg width="12" height="10"><path d="M1,1 L11,1 L6,9Z" fill="var(--high)"/></svg>判高點</span>
  <span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="var(--low)"/></svg>對</span><span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="var(--card)" stroke="var(--ink2)" stroke-width="1.4"/></svg>錯</span><span><svg width="12" height="10"><path d="M1,9 L11,9 L6,1Z" fill="var(--card)" stroke="var(--ink2)" stroke-width="1.4" stroke-dasharray="2 1.5"/></svg>待驗證</span></div>`;
}
function pageSearch() {
  const legend = [[STATUS.pool[0], 't-ok', `${REC()},每天的推薦清單只看這些`], ['池外', 't-warn', '推薦範圍外:其他上市、上櫃股票與 ETF,可查,僅供參考'], ['低波動', 't-none', '台灣 200 剔除的低波動股,和其他每日漲跌太小的股票,判斷不適用'], ['資料不足', 't-none', '興櫃股票、Yahoo 沒有資料或剛上市的股票'], ['不支援', 't-bad', '特別股、存託憑證']];
  return `<h1 class="pt">個股查詢</h1>${searchBox()}
  <div class="legendtags">${legend.map(([a, c, d]) => `<span class="tag ${c}"${tip(d)}>${a}</span>`).join('')}</div>${disc()}`;
}
/* 個股資料依代號前兩碼分檔(stocks/23.json 內含 2301–2399;ETF 用前四碼,例 00878 → stocks/0087.json),讀過的分檔留在記憶體 */
async function loadStock(code) {
  const k = code.startsWith('00') ? code.slice(0, 4) : code.slice(0, 2);
  if (!D.shards[k]) D.shards[k] = await j(`data/stocks/${k}.json`);
  return D.shards[k][code];
}
function activeCard(S) {
  const rows = [];
  for (const k of ['low', 'high']) {
    const a = S.active?.[k];
    if (!a) continue;
    rows.push(`<tr><td><span class="tag ${tagCls(k)}">判${LBL[k]}</span></td><td>${md(a.date)}</td><td>${sc(a.score)}</td>
      <td>${a.days === 0 ? '剛出現' : `${a.days} 天${HOLDWORD[k]}`}</td><td>第 ${a.run} 天</td></tr>`);
  }
  if (!rows.length) return '';
  const t = '只列最近 5 個交易日內、到今天都還沒破底(低點)/ 沒創高(高點)的訊號。真的低點後面 5 天一定不會破底,所以等越多天越可能是真的,但也越晚。';
  return `<div class="card"><h3${ttl(t)}>近 5 天訊號</h3><div class="tblwrap"><table class="tbl"><tr><th>判斷</th><th>訊號日</th><th>分數</th><th>到今天</th><th>連續</th></tr>${rows.join('')}</table></div></div>`;
}
async function pageStock(code) {
  const ix = (D.index || []).find(r => r[0] === code);
  if (!ix) return `<h1 class="pt">個股查詢</h1>${searchBox()}<div class="badbox">查無代號 ${esc(code)}。</div>${disc()}`;
  if (ix[2] === 'nodata' && ix[4]) return `<h1 class="pt">個股查詢</h1>${searchBox()}<div class="card"><div class="row"><h2 style="margin:0">${code} ${esc(ix[1])}</h2>${typeTag('nodata')}<span class="tag t-none">${MARKET[ix[3]] || ''}</span></div>
    <div class="mutebox" style="margin-top:12px"><b>資料不足</b>・${esc(ix[4])}</div></div>${disc()}`;
  if (ix[2] === 'nosup') return `<h1 class="pt">個股查詢</h1>${searchBox()}<div class="card"><div class="row"><h2 style="margin:0">${code} ${esc(ix[1])}</h2>${typeTag('nosup')}<span class="tag t-none">${MARKET[ix[3]] || ''}</span></div>
    <div class="badbox" style="margin-top:12px"><b>目前不支援</b>・${esc(ix[4])}</div></div>${disc()}`;
  let S; try { S = await loadStock(code); } catch (e) { S = null; }
  if (!S) return `<h1 class="pt">個股查詢</h1>${searchBox()}<div class="badbox">讀不到 ${code} 的資料。</div>${disc()}`;
  const t = S.today, P = t.judge || {}, p = P.pred || 'none', cand = P.cand;
  let pre = '';
  const outHit = trk('low').out_pool;
  if (S.status === 'out') pre = `<div class="warnbox"${tip(`這檔不在${REC()}推薦範圍,判斷照算,僅供參考。回放期間推薦範圍以外股票的判低點命中率 ${pct(outHit?.pct)}(${outHit?.n || 0} 筆)`)}>
    <b>⚠ 推薦範圍外</b>・僅供參考・池外命中 ${pct(outHit?.pct)}</div>`;
  if (S.status === 'lowvol') pre = `<div class="mutebox"${ttl('這類股票的「11 天最低」常常只差一兩檔,判斷沒有參考價值')}><b>低波動・判斷不適用</b>・漲跌中位數 ${fmt(S.move)}% &lt; ${D.meta.rules.min_move}%
   <details style="margin-top:6px"><summary style="cursor:pointer">看模型輸出</summary><div style="margin-top:6px">今天判${LBL[p]}${P.score != null ? `(分數 ${sc(P.score)})` : ''}。</div></details></div>`;
  if (S.status === 'halted') pre = `<div class="badbox"${ttl('停牌、處置或資料未更新')}><b>${S.date} 無交易</b>・今天沒有判斷</div>`;
  if (S.status === 'nodata') pre = `<div class="mutebox"><b>資料不足</b>・${(S.bars || []).length ? '至少要 16 個交易日的 K 線' : '還沒有這檔的 K 線'}</div>`;
  const dim = S.status === 'lowvol' ? 'opacity:.45;filter:grayscale(1)' : '';
  const last = S.bars[S.bars.length - 1] || [];
  const icon = p === 'low' ? '↓' : p === 'high' ? '↑' : '–';
  const CW = {low: '收盤是最近 6 天最低', high: '收盤是最近 6 天最高'};
  const sug = !t.judge ? '今天沒有判斷。' : p === 'low' ? `今天(${md(S.date)})收盤是最近 6 天最低,而且和過去真的低點很像(分數 ${sc(P.score)} &gt; 0),所以判 <b>可能是前後 11 天的最低點</b>。<br><br>
     「低點」只代表 11 天內最低,不代表之後會漲多少。判低點 10 次大約只有 3 次是真的;接下來幾天沒破底,越可能是真的,但也越晚。`
    : p === 'high' ? `今天(${md(S.date)})收盤是最近 6 天最高,而且和過去真的高點很像(分數 ${sc(P.score)} &gt; 0),所以判 <b>可能是前後 11 天的最高點</b>。<br><br>
     這個判斷只當提醒:短期可能不宜追高。判高點 10 次大約只有 3 次是真的。`
    : cand ? `今天${CW[cand]},是${LBL[cand]}候選;但和過去真的${LBL[cand]}不夠像(分數 ${sc(P.score)} ≤ 0),所以判 <b>非極值</b>。`
    : '今天收盤不是最近 6 天最高、也不是最低,不是候選,直接判 <b>非極值</b>(一般日子)。';
  const R = (D.research?.classification || []).find(r => r.year === '2026') || {};
  const RS = `研究結果 ${TRAIN()} 2026 1–9 月`;
  const past = (S.signals || []).filter(x => x.pred !== 'none').slice().reverse();
  const Y = S.year || {}, yr = Y.year || S.date.slice(0, 4);
  const pastRow = x => `<tr><td>${md(x.date)}</td><td><span class="tag ${tagCls(x.pred)}">${LBL[x.pred]}</span></td><td>${sc(x.score)}</td>
     <td>${x.truth == null ? '<span class="tag t-wait">待驗證</span>' : x.truth === x.pred ? '<span class="tag t-ok">對</span>' : `<span class="tag t-bad">錯・實為${LBL[x.truth]}</span>`}</td></tr>`;
  const pastTable = rows => `<div class="tblwrap"><table class="tbl"><tr><th>日期</th><th>判斷</th><th>分數</th><th>結果</th></tr>${rows.map(pastRow).join('')}</table></div>`;
  const yrow = k => { const r = Y[k] || {}, wait = (r.n || 0) - (r.graded || 0);
    return `<tr><td><span class="tag ${tagCls(k)}">判${LBL[k]}</span></td><td>${r.n || 0} 天${wait ? ` <span class="wait"${ttl('還沒滿 5 個交易日,還沒有答案')}>+${wait} 待驗證</span>` : ''}</td><td>${r.graded ? `${r.hits} 天` : '—'}</td><td class="pctc">${pct(r.pct)}</td></tr>`; };
  const pxTip = S.price === 'actual' ? '實際成交價(未還原);漲跌幅對參考價' : '還原價(把除權息補回去);這檔抓不到未還原價';
  const tile = (label, v, t) => `<div class="tile"${tip(t)}><div class="lbl">${label}</div><div class="kpi">${v}</div></div>`;
  const vtip = p === 'none' ? '' : [`分數 ${sc(P.score)}(和過去真的${LBL[p]}有多像)`].join('\n');
  const steps = [
    ['規則候選', cand ? `<span class="tag ${tagCls(cand)}">${LBL[cand]}候選</span>` : '<span class="tag t-none">不是候選</span>', cand ? CW[cand] : '收盤不是最近 6 天最高或最低'],
    ['分數', cand ? `<b>${sc(P.score)}</b>` : '—', cand ? (P.score > 0 ? '> 0:像過去真的' + LBL[cand] : '≤ 0:不夠像,改判非極值') : '不是候選,不打分數'],
    ['判斷', `<span class="tag ${tagCls(p)}">${LBL[p]}</span>`, '']];
  return `<h1 class="pt">個股查詢</h1>${searchBox()}
  <div class="vstack">
  <div class="card"><div class="row"><h2 style="margin:0;font-size:20px">${code} ${esc(S.name)}</h2>${typeTag(S.status)}${S.market && S.market !== 'TWSE' ? `<span class="tag t-none">${MARKET[S.market] || ''}</span>` : ''}<div class="sp"></div>
   <div class="right"${ttl(pxTip)}><span class="px" style="font-size:20px">${fmt(S.close ?? t.close ?? last[4])}</span> ${chg(S.chg_pct ?? t.chg_pct)}
    <div class="asof">${S.close_date ? md(S.close_date) : md(S.date)} 收盤${S.price === 'adj' ? ' <span class="tag t-none">還原價</span>' : ''}</div></div></div></div>
  ${pre}
  ${t.judge ? `<div class="grid2" style="${dim}">
   <div class="card"><div class="verdict"><div class="vicon" style="background:${p === 'low' ? 'var(--low-bg)' : p === 'high' ? 'var(--high-bg)' : 'var(--mute-bg)'};color:${p === 'low' ? 'var(--low)' : p === 'high' ? 'var(--high)' : 'var(--ink3)'}">${icon}</div>
     <div><div class="vtitle">${p === 'none' ? '非極值・一般日子' : '可能是' + LBL[p]}</div>
     ${p !== 'none' ? `<div class="vscore"${tip(vtip)}>分數 ${sc(P.score)}</div>` : ''}
     ${p !== 'none' ? marks(S.active?.[p], p) : ''}</div></div>
     <h3 style="margin-top:16px"${ttl('收盤後先用規則挑候選,再看今天的 6 根 K 線像不像過去真的高點 / 低點。分數是 OC-SVM 的分數,越大越像,只用來排序。')}>${md(S.date)} 的判斷</h3>
     <table class="tbl jtable">${steps.map(([a, b, c]) => `<tr><td>${a}</td><td>${b}</td><td class="jn">${c}</td></tr>`).join('')}</table>
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
  const daily = T.daily || [];
  const dailyTable = rows => `<div class="tblwrap"><table class="tbl"><tr><th>判斷日</th><th>前 3 檔</th><th>結果</th><th>來源</th></tr>
   ${rows.map(r => `<tr><td>${md(r.date)}</td><td>${r.picks.map(p => `<a href="#stock-${p.code}" style="color:inherit">${p.code} ${esc(p.name)}</a>${p.truth == null ? '' : p.truth === TK ? ' <span class="tag t-ok">對</span>' : ' <span class="tag t-bad">錯</span>'}`).join('、')}</td>
    <td>${r.hits == null ? '<span class="tag t-wait">待驗證</span>' : `<span class="tag ${r.hits >= 2 ? 't-ok' : r.hits === 1 ? 't-warn' : 't-bad'}">${r.hits} / ${r.picks.length} 對</span>`}</td>
    <td><span class="tag ${r.source === 'daily' ? 't-live' : 't-replay'}">${r.source === 'daily' ? '實際' : '回放'}</span></td></tr>`).join('')}</table></div>`;
  const sub = `${REC()}每天的判斷當天就存檔,不會事後修改;5 個交易日後自動對答案。資料 ${dates.first || ''} ~ ${dates.last || ''},已對答案 ${dates.n_graded || 0} 天${dates.live_start ? `,${dates.live_start} 起為實際追蹤` : ',目前都是回放'}。回放 = 上線前用同一個模型逐日產生。`;
  return `<div class="row pt"><h1${ttl(sub)}>成績追蹤</h1><div class="sp"></div>${seg(TK, [['low', '判低點'], ['high', '判高點']], 'TK')}</div>
  <div class="grid4 k2" style="margin-bottom:16px">
   ${stat('近 20 天・前 3', pct(T.top_20?.pct), `每天分數最高的 3 檔,${n(T.top_20)}`)}${stat('近 60 天・前 3', pct(T.top_60?.pct), `每天分數最高的 3 檔,${n(T.top_60)}`)}
   ${stat(`${T.all_ytd?.year || ''} 全部`, pct(T.all_ytd?.pct), `全部判斷,${n(T.all_ytd)}\n研究結果 ${TRAIN()} 2026 1–9 月 ${pct(TK === 'low' ? R.prec_low : R.prec_high)}`)}
   ${stat('隨機猜中', pct(T.base_rate?.pct), `隨便挑一天剛好是${LBL[TK]}(${REC()}、已對答案的日子)`)}
  </div>
  <div class="card" style="margin-bottom:16px"><h3${ttl(`${REC()}全部判斷的命中率,60 天移動`)}>命中率・60 天移動</h3>
   ${series.length > 1 ? `<div class="chartwrap"><svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block">${g}</svg></div>` : '<div class="mutebox">對答案的天數還不夠畫圖(至少 20 天)。</div>'}</div>
  <div style="margin-bottom:16px">
   <div class="card"><h3${ttl('個股查詢可以查其他上市、上櫃股票與 ETF,判斷照算,這是它們過去的命中率')}>推薦範圍以外</h3><table class="tbl rtable"><tr><th>股票</th><th>命中率</th><th>對 / 判斷</th></tr>
    <tr><td>${REC()}</td><td>${pct(T.all?.pct)}</td><td>${T.all ? `${T.all.hits} / ${T.all.n}` : '—'}</td></tr>
    <tr><td>池外</td><td>${pct(T.out_pool?.pct)}</td><td>${T.out_pool ? `${T.out_pool.hits} / ${T.out_pool.n}` : '—'}</td></tr></table></div></div>
  <div class="card"><h3${ttl('每天判' + LBL[TK] + '裡分數最高的 3 檔')}>每日明細・前 3 檔</h3>${dailyTable(daily.slice(0, 10))}
   ${daily.length > 10 ? `<details class="more"><summary>還有 ${daily.length - 10} 天</summary>${dailyTable(daily.slice(10))}</details>` : ''}</div>
  ${disc()}`;
}

/* ---------- 研究發現 ---------- */
/* final 分支的研究結論:真高低點大多抓得到、高低點不判反、命中率約三成、多判的訊號很多、扣成本後不能當交易訊號。
   數字全部來自 findings.json,由 results/ 的結果檔產生。 */
function pageFindings() {
  const F = D.findings;
  if (!F) return '<div class="badbox">讀不到研究結果。</div>';
  const r = F.recall, p = F.precision, yrs = F.years, span = `${yrs[0]}–${yrs[yrs.length - 1]}`;
  const rng = k => { const v = yrs.map(y => F.by_year[y][k]); return `${pct(Math.min(...v))}–${pct(Math.max(...v))}`; };
  const hits = Math.round(p.low / 10);
  const dots = Array.from({length: 10}, (_, i) => `<i class="${i < hits ? 'on' : ''}"></i>`).join('');
  const T = F.trade || {};
  const uses = [['看盤時的提醒,不是交易訊號', '它告訴你「這裡可能是近期低點 / 高點,值得看一下」,買不買由你自己決定。'],
    ['看「已幾天沒破底 / 沒創高」', '真的低點後面 5 天一定不會破底(高點不會創高),所以天數越多越可能是真的轉折,但也越晚。'],
    ['分數只用來排序', '分數是和過去真的高點 / 低點有多像,不能當成會對的比例。'],
    ['5 天後對答案', '每天的判斷都會存檔,5 個交易日後在<a href="#track">成績追蹤</a>看對了多少。']];
  return `<h1 class="pt">研究發現</h1>
  <div class="vstack">
  <div class="cards">
   <div class="find good"><h3>真高低點大多抓得到</h3><div class="big">${pct(r.low, 0)} <small>低點找到率</small></div>
    ${more(`${span} 三年合計,真低點 / 真高點當天就被判到的比例是 ${pct(r.low)} / ${pct(r.high)};每年 ${rng('rec_low')}(低點)、${rng('rec_high')}(高點)。放寬到前後 2 個交易日是 ${pct(r.low2)} / ${pct(r.high2)}。`)}</div>
   <div class="find good"><h3>高低點不判反</h3><div class="big">${F.cross} <small>次・${span}</small></div>
    ${more('判高點一定是「最近 6 天最高」、判低點一定是「最近 6 天最低」,所以真低點不會被判成高點,真高點也不會被判成低點。')}</div>
   <div class="find bad"><h3>命中率約三成</h3><div class="big">${pct(p.low)} <small>判低點</small></div>
    <div class="dots"${ttl(`10 次約對 ${hits} 次`)}>${dots}</div>
    ${more(`三年合計判低點命中 ${pct(p.low)}、判高點 ${pct(p.high)};每年 ${rng('prec_low')}(低點)、${rng('prec_high')}(高點)。隨便挑一天剛好是低點約 ${pct(p.base_low)}。`)}</div>
   <div class="find bad"><h3>多判的訊號很多</h3><div class="big">${fmt(F.over.low, 1)} 倍 <small>判低點 ÷ 真低點</small></div>
    ${more(`判低點的天數是真低點的 ${fmt(F.over.low, 1)} 倍、判高點是 ${fmt(F.over.high, 1)} 倍。真的大多抓到了,但判出來的約 7 成其實是普通日子。`)}</div>
  </div>
  <div class="card"><h2>看盤輔助,不是交易訊號</h2>
   <div class="mutebox">頻繁進出會被交易成本吃掉:${T.period ? T.period[0].slice(0, 4) + '–' + T.period[1].slice(0, 4) : ''} 試過 ${T.n} 種只做多的進出方式,扣掉成本(來回 ${T.cost_pct}%)後${T.all_loss ? '全部虧損' : '多數虧損'}${T.below_hold ? ',也都輸給買進持有' : ''}。</div></div>
  <div class="card"><h2>怎麼用</h2><div class="acc">${uses.map(([b, t]) => `<details><summary>${b}</summary><p>${t}</p></details>`).join('')}</div></div>
  ${more(`以上是研究結果(${esc(TRAIN())} ${F.n_stocks || ''} 檔、訓練門檻 0%、${span},${fmt(F.n_days, 0)} 個股票日),數字直接讀 method_kline_peak/results/ 的 ${F.sources.map(esc).join('、')}。`, '資料來源')}
  </div>${disc()}`;
}

/* ---------- 方法與說明 ---------- */
function pageAbout() {
  const bars = [42, 46, 40, 37, 33, 28, 35, 39, 44, 47, 45].map((h, i) => `<i class="${i === 5 ? 't' : i < 5 ? '' : 'f'}" style="height:${h * 2}px"></i>`).join('');
  const C = (D.research?.classification || []).slice().sort((a, b) => a.year.localeCompare(b.year));
  const mi = D.meta.model || {};
  const yrs = a => (a || []).map(d => d.slice(0, 4)).filter((v, i, s) => s.indexOf(v) === i).join('–');
  const faq = [['判低點就會漲嗎?', '不一定。低點只代表 11 天內最低,之後可能只是小反彈。'],
    ['分數是什麼?', 'OC-SVM 的分數。大於 0 代表今天的 K 線落在模型學過的真高點(低點)範圍內,才會判高點(低點);越大越像,只用來排序,不能當成會對的比例。'],
    ['為什麼盤中查到的是昨天的判斷?', '判斷要用收盤價,每天 18:00 左右更新。'],
    ['價格和看盤軟體一樣嗎?', '畫面上的收盤、K 線是實際成交價(未還原),漲跌幅和看盤軟體一樣對參考價。模型判斷用的是還原價(把除權息補回去),和訓練時一致。股票分割後,分割前的價格會照比例換算。'],
    ['為什麼有些股票顯示「不適用」?', `每日漲跌幅中位數低於 ${D.meta.rules.min_move}% 的股票(包括台灣 200 裡被剔除的低波動股),高低點常常只差一兩檔,判斷沒有參考價值。`],
    ['過去的判斷會變嗎?', '不會。每天的判斷當天就存檔,之後不重算;除權息後還原價變動也不影響已存的判斷。']];
  return `<h1 class="pt">方法與說明</h1>
  <div class="vstack">
  <div class="card"><h2>高點 / 低點</h2>
   <div class="grid2"><div><div class="label-demo">${bars}</div><div class="legend"><span>t−5 … t−1</span><span style="color:var(--low);font-weight:700">t(今天)</span><span>t+1 … t+5(要等 5 天)</span></div></div>
   <div class="defs"><div><span class="tag t-low">低點</span>今天收盤是 11 天最低</div><div><span class="tag t-high">高點</span>今天收盤是 11 天最高</div><div><span class="tag t-none">非極值</span>其他(約 85% 的日子)</div></div></div>
   ${more('看 11 天:今天(第 6 天)加前後各 5 天。模型只看今天和前 5 天的 6 根 K 線,所以收盤後就能判斷;但真正的答案要等 5 個交易日後才知道。')}</div>
  <div class="card"><h2>判斷三步驟</h2><div class="steps">
   <div class="step"><b>1. 規則挑候選</b><span>最近 6 天最高 / 最低</span></div>
   <div class="step"><b>2. 看 6 根 K 線</b><span>29 個數字</span></div>
   <div class="step"><b>3. 像不像過去的高 / 低點</b><span>AE + OC-SVM・分數 &gt; 0 才判</span></div></div>
   ${more(`<p><b>1.</b> 今天收盤是最近 6 天(今天和前 5 天)最高 → 高點候選;最低 → 低點候選。不是候選的一律判非極值。真的高低點幾乎都在候選裡;判高點一定是高點候選、判低點一定是低點候選,所以高低點不會互相判反。</p>
   <p><b>2.</b> 今天和前 5 天的開高低收(除以今天收盤)和成交量(除以 10 日均量),共 29 個數字。</p>
   <p><b>3.</b> 高點、低點各一組:AE 把 29 個數字壓成 16 個,OC-SVM 只學過去「真的」高點(低點)長什麼樣子。候選落在 OC-SVM 的範圍內(分數 &gt; 0)才判高點(低點),否則改判非極值。分數越大越像,只用來排序。</p>
   <p>訓練:${esc(TRAIN())} ${mi.n_pool || ''} 檔一起訓練一組模型。判哪一年就用前 4 年訓練,${mi.year} 年用 ${yrs(mi.train)},訓練期最後 5 個交易日剔除;標籤門檻 ${D.meta.profile?.train_min_amp || 0}%,種子 ${mi.seed}。每年 1 月第 6 個交易日後自動重訓。</p>
   <p>推薦範圍:和訓練用的股票相同,${esc(REC())} ${mi.n_pool || ''} 檔;今日判斷、成績追蹤只看這些。台灣 200 裡被剔除的低波動股標「不適用」,其他上市、上櫃股票與 ETF 可以查,標「推薦範圍外」。</p>`)}</div>
  <div class="card"><h2${ttl(`研究結果,${TRAIN()}。錯的都是和非極值混淆,高點和低點沒有互相判錯。`)}>歷史命中率</h2><div class="tblwrap"><table class="tbl">
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
  const t = [`判斷基準日 ${M.asof} 收盤`, `產生於 ${(M.created || '').slice(0, 16)}`, `模型 ${M.method || ''}・${TRAIN()} ${M.model?.n_pool || ''} 檔訓練 ${yrs[0] || ''}–${yrs[1] || ''}`, `推薦範圍 ${REC()}`];
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
