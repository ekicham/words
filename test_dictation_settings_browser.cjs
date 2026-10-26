// Real UI and HTTP state, isolated learning data; speech completion is controlled.
const assert=require('assert/strict'),fs=require('fs'),os=require('os'),path=require('path'),{spawn}=require('child_process');
const {chromium}=require('playwright');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'dictation-settings-')),base='http://127.0.0.1:8775',out='output/dictation-settings';
 fs.mkdirSync(out,{recursive:true});
 const server=spawn('python3',['app.py','--port','8775','--db',path.join(dir,'test.sqlite3')],{stdio:'ignore'});let browser;
 try{
  for(let i=0;i<100;i++){try{if((await fetch(base+'/api/bootstrap')).ok)break}catch{}await new Promise(r=>setTimeout(r,100));}
  const post=async(url,body)=>{const r=await fetch(base+url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(r.status,200);return r.json();};
  await post('/api/import',{id:'settings-test',title:'听写设置验收',publisher:'验收',edition:'验收',grade:6,term:'上',source_url:'https://example.com',words:[{english:'paste',meaning:'粘贴'},{english:'post office',meaning:'邮局'}]});
  browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   if(!localStorage.getItem('word-isle-preferences'))localStorage.setItem('word-isle-preferences',JSON.stringify({book:'settings-test',province:'浙江省',sound:false,learningOrder:'sequential'}));
   window.spoken=[];window.SpeechSynthesisUtterance=class{constructor(text){this.text=text;}};
   Object.defineProperty(window,'speechSynthesis',{value:{cancel(){},getVoices(){return [{lang:'en-US'},{lang:'zh-CN'}]},speak(u){window.spoken.push(u.lang);window.endSpeech=()=>u.onend();}}});
  });
  await page.route('**/api/audio/*',r=>r.fulfill({json:{text:'test',lang:r.request().url().includes('lang=zh')?'zh-CN':'en-US'}}));
  const state=async()=> (await (await fetch(base+'/api/bootstrap')).json()).active;
  const settings=async()=>{await page.locator('[data-nav="settings"]').click();await page.locator('#dictation-mode').waitFor();};
  const start=async kind=>{await page.locator('[data-action="home"]').click();await page.locator('[data-practice="'+kind+'"]').click();const n=await page.evaluate(()=>spoken.length);await page.locator('[data-action="start"]').click();await page.waitForFunction(n=>spoken.length===n+1,n);};
  const firstRead=async()=>{const n=await page.evaluate(()=>spoken.length);await page.evaluate(()=>endSpeech());await page.waitForFunction(n=>spoken.length===n+1,n);assert.equal(await page.locator('#answer').evaluate(e=>e.readOnly),false);};
  const secondRead=async()=>{await page.evaluate(()=>endSpeech());await page.waitForFunction(()=>document.querySelector('#dictation-stage')?.textContent==='请写出完整英文单词');};
  const finish=async()=>{await page.locator('[data-action="end"]').click();await page.getByRole('button',{name:'结束并看报告',exact:true}).click();await page.locator('.report-hero').waitFor();};
  await page.goto(base);await settings();
  assert.equal(await page.locator('#dictation-mode').inputValue(),'auto');assert.equal(await page.locator('#dictation-seconds').inputValue(),'15');
  await page.locator('#dictation-seconds').fill('0');await page.locator('#dictation-seconds').dispatchEvent('change');
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('word-isle-preferences')).dictationSeconds??15),15);
  await page.locator('#dictation-seconds').fill('5');await page.locator('#dictation-seconds').dispatchEvent('change');
  await page.locator('#dictation-mode').selectOption('manual');assert.equal(await page.locator('#dictation-duration-row').isVisible(),false);
  await page.reload();await settings();assert.equal(await page.locator('#dictation-mode').inputValue(),'manual');
  await page.screenshot({path:out+'/settings-manual.png',fullPage:true});
  await start('dictation_en');await firstRead();await page.locator('#answer').fill('paste');await secondRead();
  assert.equal(await page.locator('#dictation-timer').count(),0);assert.equal((await state()).current.writing_deadline,null);
  await page.waitForTimeout(16000);assert.equal((await state()).position,0);assert.equal((await state()).current.result,'');
  await page.reload();await page.locator('[data-action="resume"]').click();assert.equal(await page.locator('#answer').inputValue(),'paste');
  assert.equal(await page.locator('#dictation-timer').count(),0);assert.equal(await page.evaluate(()=>spoken.length),0);
  await page.screenshot({path:out+'/manual-english.png',fullPage:true});
  // An active manual session keeps its settings even if next-session preferences change.
  await page.locator('[data-action="fullscreen"]').click();await settings();await page.locator('#dictation-mode').selectOption('auto');
  await page.locator('[data-action="resume"]').click();assert.equal((await state()).dictation_mode,'manual');assert.equal(await page.locator('#dictation-timer').count(),0);
  let failedAnswer=false;await page.route('**/api/session/*/answer',r=>{if(!failedAnswer){failedAnswer=true;return r.fulfill({status:500,json:{error:'test retry'}});}return r.continue();});
  await page.locator('#answer').press('Enter');await page.getByRole('button',{name:'重试保存',exact:true}).waitFor();await page.getByRole('button',{name:'重试保存',exact:true}).click();
  await page.waitForFunction(()=>spoken.length===1);assert.equal((await state()).position,1);
  await firstRead();await secondRead();await page.locator('#answer').press('Enter');await page.waitForFunction(()=>spoken.length===3);
  const manualReport=await (await fetch(base+'/api/session/'+(await state()).id+'/report')).json();
  assert.equal(manualReport.dictation_wrong,1);assert.equal(manualReport.dictation_timeout,0);assert.equal(manualReport.words[0].attempts.length,1);
  await finish();assert.match(await page.locator('.report-hero').innerText(),/手动模式/);assert.equal(await page.locator('#main').innerText().then(t=>t.includes('15 秒')),false);
  await settings();await page.locator('#dictation-mode').selectOption('manual');
  await start('dictation_zh');await firstRead();await page.locator('#answer').fill('paste');
  const before=await page.evaluate(()=>spoken.length);await page.locator('#answer').press('Enter');assert.match(await page.locator('#feedback').innerText(),/第二遍朗读结束后提交/);
  assert.equal((await state()).current.result,'');await page.evaluate(()=>endSpeech());
  await page.waitForFunction(n=>spoken.length===n+1,before);assert.equal((await state()).position,1);assert.deepEqual(await page.evaluate(()=>spoken.slice(-3,-1)),['zh-CN','zh-CN']);
  await finish();await settings();await page.locator('#dictation-mode').selectOption('auto');assert.equal(await page.locator('#dictation-seconds').inputValue(),'5');
  await page.screenshot({path:out+'/settings-auto.png',fullPage:true});
  await start('dictation_zh');await firstRead();await secondRead();
  let s=await state();const deadline=s.current.writing_deadline;assert.ok(deadline-s.now>4&&deadline-s.now<=5);
  await page.screenshot({path:out+'/auto-five-seconds.png',fullPage:true});
  const speechCount=await page.evaluate(()=>spoken.length);await page.waitForFunction(n=>spoken.length===n+1,speechCount,{timeout:8000});
  assert.ok(Date.now()/1000-deadline<1.5);s=await state();assert.equal(s.position,1);
  const timedReport=await (await fetch(base+'/api/session/'+s.id+'/report')).json();assert.equal(timedReport.words[0].result,'timeout');assert.equal(timedReport.words[0].attempts[0].answer,'');
  await finish();await settings();await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:out+'/settings-mobile.png',fullPage:true});assert.deepEqual(errors,[]);
  const evidence={passed:true,checks:['default auto 15; input validation; saved 5 seconds','manual persists across reload and shared languages','manual full answer waits over 15 seconds and survives reload','active session settings immutable','Enter correct and blank submit once then advance; failed save retry','Enter during second playback waits for audio and advances','custom 5-second expiry advances and records blank wrong','manual reports have no 15-second text','390px settings fit'],errors};
  fs.writeFileSync(out+'/browser.json',JSON.stringify(evidence,null,2));console.log(evidence);
 }finally{if(browser)await browser.close();server.kill('SIGTERM');await new Promise(r=>server.once('close',r));fs.rmSync(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1});
