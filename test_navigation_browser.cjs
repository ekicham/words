const assert=require('assert/strict'),fs=require('fs'),os=require('os'),path=require('path'),{spawn}=require('child_process');
const {chromium}=require('playwright');
(async()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'words-navigation-')),base='http://127.0.0.1:8770';
const server=spawn('python3',['app.py','--port','8770','--db',path.join(dir,'test.sqlite3')],{stdio:'ignore'});let browser;
const get=url=>fetch(base+url).then(r=>r.json());
try{for(let i=0;i<60;i++){try{await get('/api/bootstrap');break}catch{}await new Promise(r=>setTimeout(r,100))}
 browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.setDefaultTimeout(15000);page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{if(!localStorage.getItem('word-isle-preferences'))localStorage.setItem('word-isle-preferences',JSON.stringify({book:'pep-official-1212001601265',province:'浙江省',learningOrder:'sequential',sound:false}));});
 await page.goto(base);await page.locator('#publisher').waitFor();
 assert.equal(await page.locator('[data-nav="settings"]').count(),1,'Settings must be present in sidebar');
 fs.mkdirSync('output/playwright',{recursive:true});await page.screenshot({path:'output/playwright/glass-home.png',fullPage:true});
 await page.locator('[data-nav="settings"]').click();await page.locator('#speech-rate').selectOption('0.75');await page.locator('#setting-sound').check();await page.locator('#setting-sound').uncheck();
 await page.reload();await page.locator('[data-nav="settings"]').click();assert.equal(await page.locator('#speech-rate').inputValue(),'0.75');assert.equal(await page.locator('#setting-sound').isChecked(),false);
 fs.mkdirSync('output/playwright',{recursive:true});await page.screenshot({path:'output/playwright/settings.png',fullPage:true});
 await page.emulateMedia({colorScheme:'dark',reducedMotion:'reduce'});await page.screenshot({path:'output/playwright/glass-settings-dark.png',fullPage:true});
 assert.equal(await page.locator('button').first().evaluate(el=>getComputedStyle(el).transitionDuration),'0s');
 const cdp=await page.context().newCDPSession(page);
 await cdp.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-transparency',value:'reduce'},{name:'prefers-contrast',value:'more'}]});
 assert.equal(await page.locator('.sidebar').evaluate(el=>getComputedStyle(el).backdropFilter),'none');
 assert.equal(await page.locator('.sidebar').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(36, 42, 52)');
 await cdp.send('Emulation.setEmulatedMedia',{features:[]});await page.emulateMedia({colorScheme:'light',reducedMotion:'no-preference'});

 await page.locator('[data-nav="home"]').click();await page.locator('[data-action="start"]').click();await page.locator('#answer').waitFor();
 assert.equal(await page.locator('[data-action="previous-word"]').isDisabled(),true);
 assert.equal(await page.locator('#speech-rate').count(),0);assert.equal(await page.locator('[data-action="sound"]').count(),0);
 for(const selector of ['.word-instruction','#speech-status'])assert.equal(await page.locator(selector).evaluate(el=>getComputedStyle(el).clip),'rect(0px, 0px, 0px, 0px)');assert.equal(await page.locator('#feedback').innerText(),'');
 const sid=(await get('/api/bootstrap')).active.id;
 await page.locator('#answer').fill('as');await page.waitForFunction(()=>document.querySelector('.progress-head').textContent.includes('第 2 /'));
 await page.locator('[data-action="next-word"]').click();await page.waitForFunction(()=>document.querySelector('.progress-head').textContent.includes('第 3 /'));
 const before=await get('/api/session/'+sid+'/report');
 await page.locator('[data-action="previous-word"]').click();await page.waitForFunction(()=>document.querySelector('.progress-head').textContent.includes('第 2 /'));
 assert.equal(await page.locator('#answer').isDisabled(),true);assert.match(await page.locator('.reveal').innerText(),/climb/);
 const resync=page.waitForResponse(r=>r.url().includes('/api/session/'+sid)&&!r.url().endsWith('/report'));await page.evaluate(()=>{clockRemaining=0;});await resync;await page.waitForFunction(()=>clockRemaining>0);
 assert.equal(await page.locator('#answer').isDisabled(),true,'Clock resync must preserve read-only review');assert.match(await page.locator('.reveal').innerText(),/climb/);

 await page.locator('[data-action="previous-word"]').click();await page.waitForFunction(()=>document.querySelector('.progress-head').textContent.includes('第 1 /'));
 assert.equal(await page.locator('[data-action="previous-word"]').isDisabled(),true);
 await page.locator('[data-action="next-word"]').click();await page.waitForFunction(()=>document.querySelector('.progress-head').textContent.includes('第 2 /'));
 await page.locator('[data-action="next-word"]').click();await page.waitForFunction(()=>document.querySelector('.progress-head').textContent.includes('第 3 /'));
 assert.equal(await page.locator('#answer').isDisabled(),false);
 const after=await get('/api/session/'+sid+'/report');for(const k of ['stars','first_correct','attempted','skipped','solved'])assert.equal(after[k],before[k],k);
 await page.locator('[data-action="hint"]').click();await page.locator('.reveal').waitFor();
 const style=await page.evaluate(()=>{const a=getComputedStyle(document.querySelector('.meaning')),b=getComputedStyle(document.querySelector('.reveal'));return [a.fontSize,b.fontSize,a.fontWeight,b.fontWeight,a.fontFamily,b.fontFamily]});
 assert.equal(style[0],style[1]);assert.equal(style[2],style[3]);assert.equal(style[4],style[5]);
 // Advance only this temporary session to the two user-reported examples.
 let s=await get('/api/session/'+sid);while(s.position<22){s=(await (await fetch(base+'/api/session/'+sid+'/skip',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({position:s.position,request_id:'setup-'+s.position})})).json()).session;}
 await page.reload();await page.locator('[data-action="resume"]').click();await page.locator('#answer').waitFor();assert.equal(await page.locator('.phonetic span').innerText(),'/ˈaɪfəl ˈtaʊə(r)/');
 await page.screenshot({path:'output/playwright/navigation-eiffel.png',fullPage:true});
 await page.locator('[data-action="next-word"]').click();await page.waitForFunction(()=>document.querySelector('.progress-head').textContent.includes('第 24 /'));
 await page.locator('[data-action="hint"]').click();await page.locator('.reveal').waitFor();assert.equal(await page.locator('.phonetic span').innerText(),'/ˌterəˈkɒtə ˈwɒriəz/');
 await page.screenshot({path:'output/playwright/navigation-answer.png',fullPage:true});
 await page.emulateMedia({colorScheme:'dark'});await page.waitForFunction(()=>getComputedStyle(document.querySelector('.word-nav')).backgroundColor==='rgba(41, 48, 61, 0.82)');await page.screenshot({path:'output/playwright/glass-practice-dark.png',fullPage:true});await page.emulateMedia({colorScheme:'light'});
 await page.keyboard.press('Escape');await page.setViewportSize({width:390,height:844});await page.locator('[data-action="fullscreen"]').click();
 await page.screenshot({path:'output/playwright/navigation-mobile.png',fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.keyboard.press('Escape');await page.locator('[data-nav="home"]').click();await page.screenshot({path:'output/playwright/glass-home-mobile.png',fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 assert.deepEqual(errors,[]);const evidence={passed:true,at:new Date().toISOString(),checks:['设置菜单及声音/语速持久保存','全屏两侧前后导航、首项禁用','回看不重复计分、当前下一项记跳过','下划线输入回到当前题聚焦','参考答案与中文字号/字重/字体一致','六上教材音标示例','小字移除、桌面及390px布局','Liquid Glass 网页布局、深色模式、减少动态效果、减少透明度及增强对比度'],errors};fs.writeFileSync('output/playwright/navigation-settings.json',JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence,null,2));
}finally{await browser?.close();server.kill('SIGTERM');await new Promise(r=>server.once('close',r));fs.rmSync(dir,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
