// End-to-end dictation with controlled speech completion; no personal records touched.
const assert=require('assert/strict'),fs=require('fs'),os=require('os'),path=require('path'),{spawn}=require('child_process');
const {chromium}=require('playwright');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'word-dictation-')),base='http://127.0.0.1:8774';
 const server=spawn('python3',['app.py','--port','8774','--db',path.join(dir,'test.sqlite3')],{stdio:'ignore'});let browser;
 try{
  for(let i=0;i<100;i++){try{if((await fetch(base+'/api/bootstrap')).ok)break}catch{}await new Promise(r=>setTimeout(r,100));}
  const post=async(url,body)=>{const r=await fetch(base+url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(r.status,200);return r.json();};
  await post('/api/import',{id:'dictation-test',title:'听写验收',publisher:'验收',edition:'验收',grade:6,term:'上',source_url:'https://example.com',words:[{english:'paste',meaning:'粘贴',unit:'Unit 1'},{english:'post office',meaning:'邮局',unit:'Unit 1'},{english:'cat',meaning:'猫',unit:'Unit 1'}]});
  browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   if(!localStorage.getItem('word-isle-preferences'))localStorage.setItem('word-isle-preferences',JSON.stringify({book:'dictation-test',province:'浙江省',sound:false,learningOrder:'sequential'}));
   window.spoken=[];window.SpeechSynthesisUtterance=class{constructor(text){this.text=text;}};
   Object.defineProperty(window,'speechSynthesis',{value:{cancel(){},getVoices(){if(!this.loading){this.loading=true;setTimeout(()=>this.ready=true,350);}return this.ready?[{lang:'en-US'},{lang:'zh-CN'}]:[];},speak(u){window.spoken.push({lang:u.lang,text:u.text});window.endSpeech=()=>u.onend();}}});
  });
  await page.route('**/api/audio/*',route=>{requests.push(route.request().url());return route.fulfill({json:{text:route.request().url().includes('lang=zh')?'粘贴':'paste',lang:route.request().url().includes('lang=zh')?'zh-CN':'en-US'}});});
  const state=async()=> (await (await fetch(base+'/api/bootstrap')).json()).active;
  const completeAudio=async(earlyDraft='')=>{
   const n=await page.evaluate(()=>window.spoken.length);
   await page.evaluate(()=>window.endSpeech());
   await page.waitForFunction(n=>window.spoken.length===n+1,n);
   assert.equal((await state()).current.writing_deadline,null,'Second playback has not ended');
   assert.equal(await page.locator('#answer').evaluate(el=>el.readOnly),false,'Typing must unlock after the first read');
   if(earlyDraft){await page.locator('#answer').fill(earlyDraft);assert.equal((await state()).current.result,'');}
   await page.evaluate(()=>window.endSpeech());
   if(earlyDraft==='paste')await page.locator('.reveal').waitFor();
   else await page.waitForFunction(()=>document.querySelector('#dictation-stage')?.textContent==='请写出完整英文单词');
   if(earlyDraft)assert.equal(await page.locator('#answer').inputValue(),earlyDraft,'Second read completion must preserve early input');
  };
  await page.goto(base);await page.locator('[data-practice="dictation_en"]').click();
  fs.mkdirSync('output/dictation',{recursive:true});await page.screenshot({path:'output/dictation/home.png',fullPage:true});
  await page.locator('[data-action="start"]').click();await page.waitForFunction(()=>window.spoken.length===1,null,{timeout:5000});
  assert.equal(await page.locator('.phonetic,.meaning,.reveal').count(),0);
  assert.equal(await page.locator('.letter.fixed').count(),0);
  assert.equal(await page.locator('#answer').evaluate(el=>document.activeElement===el&&el.selectionStart===0),true);
  assert.equal((await state()).current.writing_deadline,null);
  await completeAudio('pa');assert.deepEqual(await page.evaluate(()=>window.spoken.map(x=>x.lang)),['en-US','en-US']);
  let s=await state();assert.ok(s.current.writing_deadline-s.now>14);
  await page.screenshot({path:'output/dictation/english.png',fullPage:true});
  let failedNext=false;
  await page.route('**/api/session/*/next',r=>{if(!failedNext){failedNext=true;return r.fulfill({status:500,json:{error:'test retry'}});}return r.continue();});
  await page.locator('#answer').fill('pas');await page.keyboard.press('Backspace');await page.keyboard.type('ste');
  await page.locator('.reveal').waitFor({timeout:3000});assert.match(await page.locator('#feedback').innerText(),/答对/);
  assert.equal((await state()).current.tries,1);
  assert.equal(await page.locator('[data-action="dictation-next"]').isVisible(),false,'Normal progress must not need a next button');
  await page.screenshot({path:'output/dictation/result.png',fullPage:true});
  await page.getByRole('button',{name:'重试保存',exact:true}).waitFor();
  await page.getByRole('button',{name:'重试保存',exact:true}).click();await page.waitForFunction(()=>window.spoken.length===3);await completeAudio();
  await page.locator('#answer').fill('po');await page.waitForFunction(()=>document.querySelector('#feedback')?.textContent.includes('自动'));
  for(let i=0;i<30&&(await state()).current.draft!=='po';i++)await page.waitForTimeout(50);
  const deadline=(await state()).current.writing_deadline;
  await page.reload();await page.locator('[data-action="resume"]').click();assert.equal(await page.locator('#answer').inputValue(),'po');
  assert.equal((await state()).current.writing_deadline,deadline);assert.equal(await page.evaluate(()=>window.spoken.length),0,'Resuming writing must not replay');
  await page.waitForFunction(()=>window.spoken.length===1,null,{timeout:20000});
  assert.ok(Date.now()/1000-deadline<1.5,'At 15 seconds advance immediately without an answer-review pause');
  const timeoutReport=await (await fetch(base+'/api/session/'+(await state()).id+'/report')).json();
  assert.equal(timeoutReport.words[1].result,'timeout');assert.equal(timeoutReport.words[1].attempts[0].correct,0);
  await completeAudio();
  await page.locator('#answer').fill('dog');await page.locator('.reveal').waitFor();
  await page.locator('[data-action="end"]').click();await page.waitForTimeout(2200);assert.equal((await state()).position,2,'An open end dialog must suspend advancing');
  await page.getByRole('button',{name:'继续练习',exact:true}).click();await page.waitForFunction(()=>window.spoken.length===3);
  await page.locator('[data-action="end"]').click();await page.getByRole('button',{name:'结束并看报告',exact:true}).click();await page.locator('.report-hero').waitFor();
  assert.match(await page.locator('.report-metrics').innerText(),/超时答错/);assert.equal(await page.locator('.report-metrics .metric strong').allTextContents().then(x=>x.join(',')),'33%,1,1,1');
  const download=page.waitForEvent('download');await page.locator('[data-action="export-report"]').click();const file=await download;assert.match(fs.readFileSync(await file.path(),'utf8'),/英文听写/);
  await page.screenshot({path:'output/dictation/report.png',fullPage:true});
  await page.locator('[data-action="home"]').click();await page.locator('[data-practice="dictation_zh"]').click();await page.locator('[data-action="start"]').click();await page.waitForFunction(()=>window.spoken.length===4);
  await page.route('**/api/session/*/draft',()=>{});
  await completeAudio('paste');assert.deepEqual(await page.evaluate(()=>window.spoken.slice(-2).map(x=>x.lang)),['zh-CN','zh-CN']);
  await page.keyboard.press('Escape');await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:'output/dictation/mobile.png',fullPage:true});
  // Full input during the second read automatically submits when it ends, even with a pending autosave.
  assert.match(await page.locator('#feedback').innerText(),/答对/);
  await page.route('**/api/audio/*',r=>r.fulfill({status:500,json:{error:'test audio failure'}}));
  await page.waitForFunction(()=>document.querySelector('#speech-status')?.textContent.includes('未能播放'));
  s=await state();assert.equal(s.current.writing_deadline,null);assert.equal(s.current.tries,0);
  await page.screenshot({path:'output/dictation/audio-error.png',fullPage:true});
  assert.deepEqual(errors,[]);
  const evidence={passed:true,checks:['two completed playbacks of selected language before 15 seconds','no text clues or prefix; focus first blank','full length auto-submits; correct and timeout auto-advance; end dialog suspends advancement; failed next is retryable','saved draft and deadline survive reload','first read unlocks input; second read preserves input and starts timer; full early input auto-submits','real 15-second immediate advance with wrong-answer record','correct/error/timeout report and CSV','Chinese mode','audio failure never starts timer','390px no overflow'],errors};
  fs.writeFileSync('output/dictation/browser.json',JSON.stringify(evidence,null,2));console.log(evidence);
 }finally{if(browser)await browser.close();server.kill('SIGTERM');await new Promise(r=>server.once('close',r));fs.rmSync(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1});
