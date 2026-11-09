// 用真資料截圖:node screenshots/shoot.js <網址,例如 http://localhost:8765> <輸出資料夾>
const {chromium} = require('playwright'); const path = require('path');
const base = process.argv[2], dir = process.argv[3];
const pages = [['today', 'today'], ['stock-8046', 'stock_pool_8046'], ['stock-2618', 'stock_outpool_2618'], ['track', 'track'], ['findings', 'findings'], ['about', 'about']];
(async () => {
  const b = await chromium.launch(); const errs = [];
  for (const [vw, scale, opt, scheme] of [['desktop', 1, {width: 1280, height: 900}, 'light'], ['mobile', 2, {width: 390, height: 844}, 'light']]) {
    const ctx = await b.newContext({viewport: opt, deviceScaleFactor: scale, colorScheme: scheme}); const pg = await ctx.newPage();
    pg.on('pageerror', e => errs.push(e.message)); pg.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    for (const [h, name] of (scheme === 'dark' ? pages.filter(p => ['today', 'findings'].includes(p[1])) : pages)) {
      await pg.goto(`${base}/#${h}`); await pg.waitForSelector('main h1'); await pg.waitForTimeout(300);
      if (name === 'today') await pg.evaluate(() => document.querySelector('details.more')?.setAttribute('open', ''));
      await pg.addStyleTag({content: '.bottomnav{position:static!important}'});
      await pg.screenshot({path: path.join(dir, `${name}_${vw}.png`), fullPage: true});
    }
    if (scheme === 'dark') { await ctx.close(); continue; }
    await pg.goto(`${base}/#stock`); await pg.waitForSelector('#q'); await pg.fill('#q', '台'); await pg.waitForTimeout(200);
    await pg.screenshot({path: path.join(dir, `search_autocomplete_${vw}.png`)});
    await ctx.close();
  }
  await b.close(); console.log('errors:', errs);
})();
