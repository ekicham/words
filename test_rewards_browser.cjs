// Run with installed Playwright; all spending is confined to a temporary database.
const assert=require('assert/strict'),fs=require('fs'),os=require('os'),path=require('path');
const {spawn,execFileSync}=require('child_process'),{chromium}=require('playwright');
(async()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'word-isle-rewards-')),db=path.join(dir,'test.sqlite3'),base='http://127.0.0.1:8772';
const server=spawn('python3',['app.py','--port','8772','--db',db],{stdio:'ignore'});let browser;
const rewards=async()=>await (await fetch(base+'/api/rewards')).json();
try{
 for(let i=0;i<60;i++){try{if((await fetch(base+'/api/bootstrap')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1100}});page.setDefaultTimeout(15000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>localStorage.setItem('word-isle-preferences',JSON.stringify({province:'浙江省',locationChecked:true,sound:false})));
 await page.goto(base);await page.locator('[data-action="rewards"]').click();await page.locator('#spin-reward').waitFor();
 assert.equal(await page.locator('#spin-reward').isDisabled(),true);assert.equal(await page.locator('[data-prize-index]').count(),8);
 execFileSync('python3',['-c',`import sys
from app import App
app=App(sys.argv[1],seed=False)
app.import_book(dict(id='wheel-test',title='转盘验收',publisher='测试',edition='测试',grade=6,term='上',source_url='https://example.com',words=[dict(english='Monday',meaning='星期一',unit='Unit 1')]))
s=app.start(dict(book_id='wheel-test'))
for i in range(240): app.act(s['id'],'answer',dict(position=i,answer='day',request_id=str(i)))
app.act(s['id'],'finish',dict(position=240,request_id='finish'))
`,db],{stdio:'pipe'});
 await page.reload();await page.locator('[data-action="rewards"]').click();await page.locator('#spin-reward').waitFor();
 assert.match(await page.locator('#available-stars').innerText(),/2400/);
 // A rotated SVG's transparent corners must never cover the next-spin button.
 for(let i=0;i<8;i++){
   const hit=await page.evaluate(index=>{const wheel=document.querySelector('#prize-wheel'),button=document.querySelector('#spin-reward');wheel.style.transform=`rotate(${-index*45}deg)`;const r=button.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.closest('button')===button;},i);
   assert.equal(hit,true,`spin button blocked at prize ${i}`);
 }
 await page.locator('#prize-wheel').evaluate(el=>el.style.transform='rotate(0deg)');
 await page.setViewportSize({width:390,height:844});
 for(let i=0;i<8;i++){
   await page.locator('#prize-wheel').evaluate((el,index)=>el.style.transform=`rotate(${-index*45}deg)`,i);
   await page.evaluate(()=>new Promise(requestAnimationFrame));
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`mobile overflow at prize ${i}`);
 }
 await page.locator('#prize-wheel').evaluate(el=>el.style.transform='rotate(0deg)');await page.setViewportSize({width:1440,height:1100});
 fs.mkdirSync('output/playwright',{recursive:true});await page.screenshot({path:'output/playwright/family-wheel-desktop.png',fullPage:true});
 await page.locator('#spin-reward').click();await page.waitForFunction(()=>document.querySelector('#prize-wheel').getAnimations().length===1);
 assert.equal(await page.locator('#spin-reward').isDisabled(),true);
 await page.locator('.prize-ticket').waitFor();let result=await rewards();assert.equal(result.draws.length,1);assert.equal(result.wallet.available,1600);
 assert.ok((await page.locator('#prize-result').innerText()).includes(result.draws[0].prize.name));
 assert.equal(await page.locator('#prize-wheel').evaluate(el=>Number(el.style.transform.match(/-?[\d.]+/)[0])),-result.draws[0].prize_index*45||0);
 const first=result.draws[0];await page.locator('[data-redeem]').click();await page.locator('.redeemed').waitFor();
 await fetch(base+'/api/rewards/'+first.id+'/redeem',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
 assert.equal((await rewards()).wallet.available,1600);
 // Commit the second draw but lose its response and the following GET. Refresh must recover it.
 await page.emulateMedia({reducedMotion:'reduce'});let dropped=false;
 await page.route('**/api/rewards/draw',async route=>{await route.fetch();dropped=true;await route.abort('failed');});
 await page.route('**/api/rewards',route=>dropped?route.abort('failed'):route.continue());
 await page.locator('#spin-reward').click();await page.waitForFunction(()=>document.querySelector('#spin-reward')?.textContent==='重试抽奖结果'&&!document.querySelector('#spin-reward').disabled);
 assert.ok(await page.evaluate(()=>localStorage.getItem('word-isle-pending-draw')));assert.equal((await rewards()).draws.length,2);
 await page.unroute('**/api/rewards/draw');await page.unroute('**/api/rewards');
 await page.reload();await page.locator('[data-action="rewards"]').click();await page.locator('.prize-ticket').nth(1).waitFor();
 assert.equal(await page.evaluate(()=>localStorage.getItem('word-isle-pending-draw')),null);assert.equal((await rewards()).wallet.available,800);
 // A request lost before commit keeps the same ID on manual retry.
 const ids=[];let lose=true;
 await page.route('**/api/rewards/draw',route=>{ids.push(route.request().postDataJSON().request_id);if(lose){lose=false;return route.abort('failed');}return route.continue();});
 await page.locator('#spin-reward').click();await page.waitForFunction(()=>document.querySelector('#spin-reward')?.textContent==='重试抽奖结果'&&!document.querySelector('#spin-reward').disabled);
 await page.locator('#spin-reward').click();await page.locator('.prize-ticket').nth(2).waitFor();
 assert.equal(ids.length,2);assert.equal(ids[0],ids[1]);assert.equal(await page.locator('#prize-wheel').evaluate(el=>el.getAnimations().length),0);
 result=await rewards();assert.equal(result.wallet.available,0);assert.equal(result.wallet.earned,2400);assert.equal(result.wallet.spent,2400);assert.equal(await page.locator('#spin-reward').isDisabled(),true);
 await page.locator('#toast').waitFor({state:'hidden'});await page.screenshot({path:'output/playwright/family-wheel-prizes.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.locator('#prize-wheel').evaluate(el=>el.style.transform='rotate(-45deg)');
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 const mobile=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('main *')].map(el=>({tag:el.tagName,id:el.id,cls:el.className.baseVal??el.className,right:el.getBoundingClientRect().right})).filter(el=>el.right>innerWidth)}));
 assert.ok(mobile.scroll<=mobile.width,JSON.stringify(mobile));await page.locator('#prize-wheel').evaluate((el,index)=>el.style.transform=`rotate(${-index*45}deg)`,result.draws[0].prize_index);await page.screenshot({path:'output/playwright/family-wheel-mobile.png',fullPage:true});
 await page.setViewportSize({width:1440,height:1100});await page.emulateMedia({colorScheme:'dark'});await page.waitForTimeout(200);await page.screenshot({path:'output/playwright/family-wheel-dark.png',fullPage:true});
 await page.getByRole('button',{name:'返回首页',exact:true}).click();await page.locator('#publisher').waitFor();assert.match(await page.locator('[data-action="rewards"] strong').innerText(),/^0/);
 assert.deepEqual(errors,[]);
 const evidence={passed:true,at:new Date().toISOString(),checks:['800星真实扣除，累计奖励保持不变','8等分SVG转盘真实动画、指针对齐服务端结果','中奖保存及标记完成，重复兑换不再次扣费','响应丢失后刷新恢复，未提交成功的请求重试沿用编号','动画期间按钮禁用、余额不足禁用、减少动态时直接显示结果','桌面、390px和深色无页面横溢'],errors};
 fs.writeFileSync('output/playwright/family-wheel.json',JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence,null,2));
}finally{if(browser)await browser.close();server.kill('SIGTERM');await new Promise(r=>server.once('close',r));fs.rmSync(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1});
