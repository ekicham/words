// Real UI checks; all changes and spending use an isolated temporary database.
const assert=require('assert/strict'),fs=require('fs'),os=require('os'),path=require('path'),{spawn,execFileSync}=require('child_process'),{chromium}=require('playwright');
(async()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'words-prize-settings-')),db=path.join(dir,'test.sqlite3'),base='http://127.0.0.1:8773';
const server=spawn('python3',['app.py','--port','8773','--db',db],{stdio:'ignore'});let browser;
const get=route=>fetch(base+route).then(r=>r.json());
try{
 for(let i=0;i<60;i++){try{await get('/api/rewards');break;}catch{}await new Promise(r=>setTimeout(r,100));}
 execFileSync('python3',['-c',`import sys
from app import App
app=App(sys.argv[1],seed=False)
app.import_book(dict(id='prize-ui',title='测试',publisher='测试',edition='测试',grade=6,term='上',source_url='https://example.com',words=[dict(english='Monday',meaning='星期一',unit='Unit 1')]))
s=app.start(dict(book_id='prize-ui'))
for i in range(240): app.act(s['id'],'answer',dict(position=i,answer='day',request_id=str(i)))
app.act(s['id'],'finish',dict(position=240,request_id='finish'))
app.draw_reward(dict(request_id='legacy-200',config_revision=app.reward_config()['revision']))
# Simulate a prize won before the price changed. Existing cost must stay 200.
with app.db() as conn: conn.execute("UPDATE rewards SET cost=200 WHERE id='legacy-200'")
`,db]);
 const before=await get('/api/rewards'),old=before.draws[0];assert.equal(before.wallet.spent,200);
 browser=await chromium.launch({channel:'chrome',headless:true});const context=await browser.newContext({viewport:{width:1440,height:1100},reducedMotion:'reduce'});
 await context.addInitScript(()=>{if(!localStorage.getItem('word-isle-preferences'))localStorage.setItem('word-isle-preferences',JSON.stringify({province:'浙江省',locationChecked:true,sound:false}));});
 const page=await context.newPage(),other=await context.newPage(),errors=[];for(const p of [page,other]){p.setDefaultTimeout(15000);p.on('pageerror',e=>errors.push(e.message));await p.goto(base);}
 await other.locator('[data-action="rewards"]').click();await other.locator('#spin-reward').waitFor();assert.match(await other.locator('#spin-reward').innerText(),/800 星/);
 await page.locator('[data-nav="settings"]').click();await page.locator('#prize-settings-form').waitFor();assert.equal(await page.locator('.prize-editor').count(),8);
 await page.locator('#speech-rate').selectOption('0.75');
 const presets=before.presets;
 assert.equal(await page.locator('#prize-settings-form input,#prize-settings-form textarea').count(),0);
 for(const preset of presets){await page.locator('#prize-icon-0').selectOption(preset.icon);assert.equal(await page.locator('#prize-name-0').textContent(),preset.name);assert.equal(await page.locator('#prize-detail-0').textContent(),preset.detail);}
 for(let i=0;i<8;i++)await page.locator('#prize-icon-'+i).selectOption(presets[i+8].icon);
 await page.getByRole('button',{name:'保存奖品设置',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#prize-save-status').textContent.startsWith('已保存'));
 const saved=await get('/api/rewards/config');assert.deepEqual(saved.prizes,presets.slice(8));assert.equal(saved.cost,800);assert.equal((await get('/api/rewards')).wallet.spent,200);
 // A stale wheel must refresh without spending on changed prizes.
 await other.locator('#spin-reward').click();await other.waitForFunction(revision=>document.querySelector('#spin-reward').dataset.revision===revision,saved.revision);assert.equal((await get('/api/rewards')).draws.length,1);
 await other.locator('#spin-reward').click();await other.locator('.prize-ticket').nth(1).waitFor();const after=await get('/api/rewards');assert.equal(after.wallet.spent,1000);assert.equal(after.draws[0].cost,800);assert.ok(saved.prizes.some(p=>p.name===after.draws[0].prize.name));
 const legacy=after.draws.find(d=>d.id==='legacy-200');assert.deepEqual(legacy,old);assert.match(await other.locator('[data-reward-id="legacy-200"]').innerText(),/200 星/);
 await page.reload();await page.locator('[data-nav="settings"]').click();await page.locator('#prize-settings-form').waitFor();assert.equal(await page.locator('#prize-name-0').textContent(),presets[8].name);assert.equal(await page.locator('#speech-rate').inputValue(),'0.75');
 // Stale settings cannot overwrite another window's saved edit.
 const latest=await get('/api/rewards/config');latest.prizes[1]=presets[0];await fetch(base+'/api/rewards/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(latest)});
 await page.locator('#prize-icon-1').selectOption(presets[1].icon);await page.getByRole('button',{name:'保存奖品设置',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#prize-save-status').textContent.includes('其他页面更新'));assert.equal((await get('/api/rewards/config')).prizes[1].name,presets[0].name);assert.equal(await page.locator('#prize-name-1').textContent(),presets[1].name);
 await page.locator('[data-nav="settings"]').click();await page.locator('#prize-settings-form').waitFor();
 fs.mkdirSync('output/playwright',{recursive:true});await page.screenshot({path:'output/playwright/prize-settings-desktop.png',fullPage:true});
 await page.emulateMedia({colorScheme:'dark'});await page.screenshot({path:'output/playwright/prize-settings-dark.png',fullPage:true});await page.emulateMedia({colorScheme:'light'});await page.setViewportSize({width:390,height:844});await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:'output/playwright/prize-settings-mobile.png',fullPage:true});
 await page.getByRole('button',{name:'查看转盘',exact:true}).click();await page.locator('#prize-wheel').waitFor();assert.equal(await page.locator('[data-prize-index="0"] tspan').count(),1);assert.equal(await page.locator('[data-prize-index]').count(),8);await page.locator('.reward-rules summary').click();assert.ok((await page.locator('.reward-rules').innerText()).includes(presets[8].detail));await page.screenshot({path:'output/playwright/prize-settings-wheel.png',fullPage:true});assert.deepEqual(errors,[]);
 const result={passed:true,at:new Date().toISOString(),checks:['设置保存、刷新保留、声音设置保持','16个图标自动填写名称和说明、无需手动输入，八格保存生效','过期转盘不扣星，过期设置不覆盖','新抽奖800星，历史200星奖品及内容不变','桌面/深色/390px布局、无脚本错误'],errors};fs.writeFileSync('output/playwright/prize-settings.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{if(browser)await browser.close();server.kill('SIGTERM');if(server.exitCode===null)await new Promise(r=>server.once('close',r));fs.rmSync(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1});
