// Real browser recording + actual local model, using a deterministic synthetic microphone WAV.
const assert=require('assert/strict'),fs=require('fs'),os=require('os'),path=require('path'),{spawn}=require('child_process');
const {chromium}=require('playwright');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'wordisle-local-')),out='output/openpronounce',ready=path.join(dir,'ready');
 fs.symlinkSync(path.resolve(out+'/model-profile/openpronounce'),path.join(dir,'openpronounce'));
 const server=spawn('python3',['-c',`import sys,json,random
from pathlib import Path
from app import App,serve
random.sample=lambda data,count:data[:count]
a=App(Path(sys.argv[1])/'words.sqlite3')
a.phonetics_lesson.configure(dict(provider='openpronounce',secret_id='AKID-MOCK-KEEP',secret_key='MOCK-DO-NOT-UPLOAD'))
s=serve(a,0)
Path(sys.argv[2]).write_text(str(s.server_port))
s.serve_forever()`,dir,ready],{stdio:'pipe'});let browser,logs='';server.stderr.on('data',b=>logs+=b);
 try{
  for(let i=0;i<100&&!fs.existsSync(ready);i++)await new Promise(r=>setTimeout(r,100));assert.ok(fs.existsSync(ready),logs);
  const base='http://127.0.0.1:'+fs.readFileSync(ready,'utf8');
  browser=await chromium.launch({channel:'chrome',headless:true,args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--use-file-for-fake-audio-capture='+path.resolve(out+'/father-mic.wav')]});
  const context=await browser.newContext({viewport:{width:1440,height:1080}});await context.grantPermissions(['microphone'],{origin:base});
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.addInitScript(()=>localStorage.setItem('word-isle-preferences',JSON.stringify({locationChecked:true})));
  await page.goto(base);await page.locator('[data-nav="settings"]').click();await page.locator('#ipa-provider').waitFor();
  assert.equal(await page.locator('#ipa-provider').inputValue(),'openpronounce');await page.screenshot({path:out+'/local-settings.png',fullPage:true});
  await page.locator('#ipa-provider').selectOption('tencent');await page.waitForFunction(()=>document.querySelector('#ipa-provider')?.disabled===false);
  const cloud=await(await fetch(base+'/api/phonetics/config')).json();assert.equal(cloud.tencent_configured,true);
  await page.locator('#ipa-provider').selectOption('openpronounce');await page.waitForFunction(()=>document.querySelector('#ipa-provider')?.disabled===false);
  await page.locator('[data-nav="phonetics"]').click();await page.locator('#ipa-consent').check();await page.locator('[data-ipa="start"][data-count="10"]').click();
  await page.locator('.ipa-example').waitFor();assert.match(await page.locator('.ipa-example').innerText(),/father/);
  await page.locator('[data-ipa="record"]').click();await page.waitForFunction(()=>document.querySelector('#ipa-record-status')?.textContent.startsWith('正在录音'));
  await page.waitForTimeout(3500);await page.locator('[data-ipa="stop"]').click();await page.locator('[data-ipa="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('.page-heading')?.textContent.includes('第 2 / 10'),null,{timeout:200000});
  await page.locator('[data-ipa="finish"]').click();await page.locator('.ipa-report-summary').waitFor();
  assert.match(await page.locator('.page-heading').innerText(),/OpenPronounce/);assert.match(await page.locator('tbody tr').first().innerText(),/识别文本/);
  const overview=await(await fetch(base+'/api/phonetics')).json(),report=await(await fetch(base+'/api/phonetics/tests/'+overview.history[0].id)).json();
  assert.equal(report.provider,'openpronounce');assert.equal(report.scored,1);assert.ok(Number.isFinite(report.mean));
  const [download]=await Promise.all([page.waitForEvent('download'),page.locator('[data-ipa="export"]').click()]);await download.saveAs(out+'/local-report.csv');
  assert.match(fs.readFileSync(out+'/local-report.csv','utf8'),/OpenPronounce/);await page.screenshot({path:out+'/local-report.png',fullPage:true});
  await page.locator('[data-nav="settings"]').click();await page.locator('#ipa-provider').selectOption('tencent');await page.waitForFunction(()=>document.querySelector('#ipa-provider')?.disabled===false);
  await page.locator('[data-nav="phonetics"]').click();await page.locator('[data-ipa="history"]').click();await page.locator('.ipa-report-summary').waitFor();assert.match(await page.locator('.page-heading').innerText(),/OpenPronounce/);
  await page.locator('[data-nav="settings"]').click();await page.locator('#ipa-provider').waitFor();await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:out+'/local-settings-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);fs.writeFileSync(out+'/browser-live.json',JSON.stringify({passed:true,realLocalModel:true,syntheticMic:true,score:report.mean,result:report.results[0],cloudSubmitted:false,errors},null,2));console.log('PASS actual OpenPronounce through browser recording, report and CSV; provider retention; mobile. Synthetic mic, no human accuracy validation.');
 }finally{if(browser)await browser.close();server.kill();await new Promise(resolve=>server.on('close',resolve));fs.rmSync(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exit(1)});
