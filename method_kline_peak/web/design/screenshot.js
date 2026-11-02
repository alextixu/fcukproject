const {chromium}=require('playwright');const path=require('path');
const dir=process.argv[2];const url='file://'+path.join(dir,'mockup.html');
const pages=[['today','today'],['stock/2330','stock_2330'],['stock/2618','stock_outpool_2618'],['stock/2412','stock_lowvol_2412'],['track','track'],['about','about']];
(async()=>{const b=await chromium.launch();const errs=[];
for(const [vw,tag,opt] of [['desktop',1,{width:1280,height:900}],['mobile',2,{width:390,height:844}]]){
  const ctx=await b.newContext({viewport:opt,deviceScaleFactor:tag});const pg=await ctx.newPage();
  pg.on('pageerror',e=>errs.push(e.message));pg.on('console',m=>{if(m.type()==='error')errs.push(m.text())});
  for(const [h,name] of pages){await pg.goto(url+'#'+h);await pg.waitForTimeout(300);
    if(name==='today'){await pg.evaluate(()=>document.querySelector('details.more')?.setAttribute('open',''))}
    await pg.addStyleTag({content:'.bottomnav{position:static!important}'});await pg.screenshot({path:path.join(dir,`shot_${name}_${vw}.png`),fullPage:true});}
  // 自動完成狀態
  await pg.goto(url+'#stock');await pg.fill('#q','23');await pg.waitForTimeout(200);
  await pg.screenshot({path:path.join(dir,`shot_search_autocomplete_${vw}.png`),fullPage:false});
  await ctx.close();}
await b.close();console.log('errors:',errs);})();
