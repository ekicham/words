// Actual Chrome media playback + Web Audio capture. Only the cloud response is mocked.
const assert=require('assert/strict'),fs=require('fs'),os=require('os'),path=require('path'),{spawn}=require('child_process');
const {chromium}=require('playwright');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'phonetics-')),out='output/phonetics';fs.mkdirSync(out,{recursive:true});
 const ready=path.join(dir,'ready');
 const server=spawn('python3',['-c',`import sys,json
from pathlib import Path
from app import App,serve
import phonetics
calls=0
def mock_assess(*args):
 global calls
 calls+=1
 if calls==1: raise ValueError('测试注入：云服务暂不可用，本次不计分')
 return dict(score=88.5,raw_score=88.5,phones=[dict(reference='ih',detected='ih',score=88.5,match=0)],request_id='MOCK-CLOUD-NOT-LIVE')
phonetics.assess=mock_assess
server=serve(App(Path(sys.argv[1])/'words.sqlite3'),0)
Path(sys.argv[2]).write_text(str(server.server_port))
server.serve_forever()`,dir,ready],{stdio:'pipe'});let logs='',browser;server.stderr.on('data',b=>logs+=b);
 try{
  for(let i=0;i<100&&!fs.existsSync(ready);i++)await new Promise(r=>setTimeout(r,100));
  assert.ok(fs.existsSync(ready),logs);const base='http://127.0.0.1:'+fs.readFileSync(ready,'utf8');
  const proxy=process.env.https_proxy||process.env.HTTPS_PROXY;
  browser=await chromium.launch({channel:'chrome',headless:true,proxy:proxy?{server:proxy,bypass:'127.0.0.1,localhost'}:undefined,args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
  const context=await browser.newContext({viewport:{width:1440,height:1080}});await context.grantPermissions(['microphone'],{origin:base});
  const page=await context.newPage(),errors=[],played=[];page.on('pageerror',error=>errors.push(error.message));
  page.on('requestfailed',request=>console.log('network',request.url(),request.failure()?.errorText));
  page.on('response',response=>{if(response.url().includes('dictionary.cambridge.org/media/'))played.push({url:response.url(),status:response.status()});});
  await page.addInitScript(()=>localStorage.setItem('word-isle-preferences',JSON.stringify({locationChecked:true})));
  await page.goto(base);await page.locator('[data-nav="phonetics"]').click();await page.locator('.ipa-tile').first().waitFor();
  assert.equal(await page.locator('.ipa-tile').count(),48);assert.equal(await page.locator('[data-ipa="start"]').first().isDisabled(),true);
  assert.equal(await page.locator('nav button').first().getAttribute('data-nav'),'phonetics');
  await page.locator('[data-ipa="sound"][data-id="1"]').click();await page.waitForFunction(()=>document.querySelector('#ipa-audio-status').textContent==='播放完成',{},{timeout:20000}).catch(async error=>{console.log('audio diagnostics',await page.locator('#ipa-audio-status').innerText(),played,errors);await page.screenshot({path:out+'/audio-failure.png',fullPage:true});throw error;});
  await page.locator('[data-ipa="accent"][data-value="us"]').click();await page.locator('[data-ipa="sound"][data-id="1"]').click();
  await page.waitForFunction(()=>document.querySelector('#ipa-audio-status').textContent==='播放完成',{},{timeout:20000});
  assert.ok(played.some(r=>r.url.includes('/uk_phonetic/')));assert.ok(played.some(r=>r.url.includes('/us_phonetic/')));assert.ok(played.every(r=>r.status===200||r.status===206));
  await page.waitForFunction(()=>document.querySelector('video')?.duration>110);await page.locator('video').evaluate(video=>{video.currentTime=60;return video.play();});
  await page.waitForFunction(()=>document.querySelector('video').currentTime>60.2);await page.locator('video').evaluate(video=>video.pause());
  await page.locator('[data-ipa="fullscreen"]').click();
  await page.waitForFunction(()=>document.fullscreenElement?.tagName==='VIDEO');
  assert.ok(await page.locator('video').evaluate(video=>video.currentTime>=60));
  await page.evaluate(()=>document.exitFullscreen());
  await page.waitForFunction(()=>!document.fullscreenElement);
  await page.screenshot({path:out+'/learning-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:out+'/learning-mobile.png',fullPage:true});
  await page.setViewportSize({width:1440,height:1080});await page.locator('[data-nav="settings"]').click();await page.locator('#ipa-service-form').waitFor();
  await page.locator('[name="secret_id"]').fill('AKID-MOCK-TEST');await page.locator('[name="secret_key"]').fill('MOCK-NOT-A-REAL-SECRET');await page.locator('#ipa-service-form [type="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('#ipa-config-status')?.textContent.includes('已保存；'));
  assert.equal(await page.locator('[name="secret_key"]').inputValue(),'');await page.screenshot({path:out+'/service-settings.png',fullPage:true});
  await page.locator('[data-nav="phonetics"]').click();await page.locator('#ipa-consent').check();await page.locator('[data-ipa="start"][data-count="10"]').click();
  await page.locator('[data-ipa="record"]').waitFor();
  const capture=async()=>{await page.locator('[data-ipa="record"]').click();await page.waitForFunction(()=>document.querySelector('#ipa-record-status')?.textContent.startsWith('正在录音'));await page.waitForTimeout(1100);await page.locator('[data-ipa="stop"]').click();await page.waitForFunction(()=>document.querySelector('[data-ipa="submit"]')?.disabled===false);};
  await capture();await page.locator('[data-ipa="listen"]').click();await page.waitForTimeout(300);await page.locator('[data-ipa="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('#ipa-record-status')?.textContent.includes('测试注入'));
  const overview=await (await fetch(base+'/api/phonetics')).json(),id=overview.history[0].id;
  let state=await(await fetch(base+'/api/phonetics/tests/'+id)).json();assert.equal(state.position,0);assert.equal(state.mean,null);
  await page.locator('[data-ipa="submit"]').click();await page.waitForFunction(()=>document.querySelector('.page-heading')?.textContent.includes('第 2 / 10'));
  state=await(await fetch(base+'/api/phonetics/tests/'+id)).json();assert.equal(state.mean,88.5);assert.equal(state.scored,1);
  await page.locator('[data-ipa="skip"]').click();await page.waitForFunction(()=>document.querySelector('.page-heading')?.textContent.includes('第 3 / 10'));
  await page.locator('[data-ipa="finish"]').click();await page.locator('.ipa-report-summary').waitFor();
  assert.match(await page.locator('.ipa-report').first().innerText(),/88.5/);assert.equal(await page.locator('tbody tr').count(),10);
  const [download]=await Promise.all([page.waitForEvent('download'),page.locator('[data-ipa="export"]').click()]);await download.saveAs(out+'/mock-cloud-report.csv');
  await page.screenshot({path:out+'/mock-cloud-report.png',fullPage:true});await page.locator('[data-ipa="saved"]').click();await page.waitForTimeout(300);
  await page.locator('[data-ipa="learn"]').click();await page.locator('[data-ipa="history"]').click();await page.locator('.ipa-report-summary').waitFor();
  assert.match(await page.locator('.ipa-report').first().innerText(),/88.5/);
  // Leaving a recording must close every capture track.
  await page.locator('[data-ipa="learn"]').click();await page.locator('#ipa-consent').check();await page.locator('[data-ipa="start"][data-count="10"]').click();
  await page.evaluate(()=>{const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async opts=>{window.qaStream=await original(opts);return window.qaStream;};});
  await page.locator('[data-ipa="record"]').click();await page.waitForFunction(()=>document.querySelector('#ipa-record-status')?.textContent.startsWith('正在录音'));
  await page.locator('[data-nav="home"]').click();await page.waitForFunction(()=>window.qaStream.getTracks().every(track=>track.readyState==='ended'));
  await page.locator('[data-nav="phonetics"]').click();await page.locator('[data-ipa="delete"]').first().click();await page.locator('[data-ipa="delete"]').first().click();
  await page.waitForFunction(()=>document.querySelectorAll('.ipa-history-row').length===1);
  assert.deepEqual(errors,[]);fs.writeFileSync(out+'/browser.json',JSON.stringify({passed:true,liveCambridgePlayback:played,videoSeek:true,realWebAudioWithFakeDevice:true,liveCloudAssessment:false,mockReportMean:88.5,errors},null,2));console.log('PASS IPA navigation, UK/US actual audio, local video seek, settings, Web Audio PCM, mock-cloud error/retry/report, history/export/delete, mic cleanup, mobile. Live cloud: NOT TESTED.');
 }finally{if(browser)await browser.close();server.kill();await new Promise(resolve=>server.on('close',resolve));fs.rmSync(dir,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exit(1);});
