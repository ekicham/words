// Optional UI acceptance: NODE_PATH=/path/to/installed/node_modules node test_browser.cjs
// Uses an isolated temporary database and Chromium; leaves only screenshots and a result file.
const {chromium}=require('playwright');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const directory=fs.mkdtempSync(path.join(os.tmpdir(),'word-isle-ui-'));
const base='http://127.0.0.1:8767',artifacts=path.join(__dirname,'output/playwright');
fs.mkdirSync(artifacts,{recursive:true});
const server=spawn('python3',['app.py','--port','8767','--db',path.join(directory,'test.sqlite3')],{cwd:__dirname});
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const get=url=>fetch(base+url).then(r=>r.json());
const results=[];
let browser,page,errors=[];
(async()=>{
 try{
  for(let i=0;i<50;i++){try{await get('/api/bootstrap');break;}catch{await pause(100);}}
  browser=await chromium.launch({headless:true,channel:'chrome'});
  const context=await browser.newContext({viewport:{width:1440,height:1080}});
  page=await context.newPage();
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',message=>{if(message.type()==='warning')console.error(message.text());});
  await page.route('**/api/location',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({province:'浙江省',message:'已根据网络位置推荐地区，请核对'})}));
  await page.goto(base);await page.getByRole('button',{name:'开始单词探险 →',exact:true}).waitFor();
  await page.waitForFunction(()=>JSON.parse(localStorage.getItem('word-isle-preferences')||'{}').province==='浙江省');
  assert.equal(await page.locator('#province').inputValue(),'浙江省');
  await page.screenshot({path:path.join(artifacts,'home-desktop.png'),fullPage:true});
  await page.locator('#grade').selectOption('3');assert.equal(await page.locator('#book').inputValue(),'pep-3-a');
  await page.locator('#book').selectOption('pep-3-b');
  await page.locator('#province').selectOption('广东省');assert.equal(await page.locator('#province').inputValue(),'广东省');assert.equal(await page.locator('.inline-note').count(),0);
  results.push('教材年级/上下册切换，模拟浙江定位与手动地区覆盖通过');
  await page.getByRole('button',{name:'我的词库',exact:true}).click();
  const fixture={id:'ui-fixture',title:'浏览器验收课本',publisher:'验收出版社',edition:'仅测试用',grade:6,term:'上',source_url:'https://example.com/test',regions:[],words:['Monday','science','post office','by'].map(english=>({english,meaning:'验收释义',unit:'Unit 1',page:'1'}))};
  const file=path.join(directory,'fixture.json');fs.writeFileSync(file,JSON.stringify(fixture));
  await page.locator('#import-file').setInputFiles(file);
  await page.getByRole('heading',{name:'浏览器验收课本',exact:true}).waitFor();
  const card=page.locator('article').filter({has:page.getByRole('heading',{name:'浏览器验收课本',exact:true})});
  await card.getByRole('button',{name:'选这本练习 →',exact:true}).click();
  await page.getByRole('button',{name:'自定义',exact:true}).click();await page.locator('#custom-minutes').fill('0');
  await page.getByRole('button',{name:'开始单词探险 →',exact:true}).click();assert.match(await page.locator('#toast').innerText(),/1–180/);
  await page.locator('#custom-minutes').fill('1');await page.getByRole('button',{name:'开始单词探险 →',exact:true}).click();
  await page.locator('#answer').waitFor();
  await page.waitForFunction(()=>document.querySelector('#speech-status')?.textContent.includes('本机中英文合成语音'),{},{timeout:20000});
  results.push('通过界面导入新出版社词库、自定义时长校验、原生英文和中文音频播放结束通过');
  const vocabulary=await get('/api/words?book_id=ui-fixture');
  let state=(await get('/api/bootstrap')).active;const sid=state.id,seen=new Set();
  await page.screenshot({path:path.join(artifacts,'practice-desktop.png'),fullPage:true});
  for(let index=0;index<4;index++){
   state=await get('/api/session/'+sid);seen.add(state.current.word_id);
   const full=vocabulary.find(w=>w.id===state.current.word_id).english.toLowerCase().replace(/[^a-z]/g,'');
   const suffix=full.slice(-state.current.missing);
   if(index===1){
    await page.locator('#answer').fill('z'.repeat(suffix.length));
    await page.waitForFunction(()=>document.querySelector('#feedback')?.textContent.includes('未答对'));
    await page.reload();await page.getByRole('button',{name:'继续探险',exact:true}).click();await page.locator('#answer').waitFor();
    state=await get('/api/session/'+sid);assert.equal(state.position,1);assert.equal(state.current.tries,1);
   }
   if(index===2){await page.getByRole('button',{name:'看提示',exact:true}).click();await page.locator('.reveal').waitFor();}
   if(index===3)await page.getByRole('button',{name:'暂时跳过',exact:true}).click();
   else await page.locator('#answer').fill(suffix);
   await page.waitForFunction(async({base,sid,index})=>{const s=await fetch(base+'/api/session/'+sid).then(r=>r.json());return s.position===index+1;},{base,sid,index});
   if(index<3)await page.waitForFunction(index=>document.querySelector('.progress-head')?.textContent.includes('第 '+(index+2)+' /'),index);
  }
  await page.waitForFunction(()=>document.querySelector('.progress-head')?.textContent.includes('第 2 轮'));
  assert.equal((await get('/api/session/'+sid)).status,'active');
  await page.locator('[data-action="end"]').click();await page.getByRole('button',{name:'结束并看报告',exact:true}).click();
  await page.locator('.report-hero').waitFor();
  const report=await get('/api/session/'+sid+'/report');
  assert.equal(seen.size,4);assert.equal(report.attempted,3);assert.equal(report.first_correct,1);assert.equal(report.second_correct,1);assert.equal(report.first_wrong,1);assert.equal(report.hinted,1);assert.equal(report.skipped,1);assert.equal(report.stars,18);
  assert.match(await page.locator('.report-metrics').innerText(),/33%/);assert.match(await page.locator('.report-metrics').innerText(),/100%/);
  await page.screenshot({path:path.join(artifacts,'report-desktop.png'),fullPage:true});
  const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'导出学习报告 ↓',exact:true}).click()]);assert.match(download.suggestedFilename(),/\.csv$/);
  results.push('随机不重复，自动补全跳题，答错重试，刷新恢复，提示与跳过，正确率分母、星星和CSV导出通过');
  await page.getByRole('button',{name:'学习足迹',exact:true}).click();await page.getByRole('button',{name:'看报告 →',exact:true}).waitFor();
  await page.getByRole('button',{name:'错词巩固 3',exact:true}).click();await page.getByRole('button',{name:'开始错词重练',exact:true}).click();
  await page.locator('#answer').waitFor();state=(await get('/api/bootstrap')).active;assert.equal(state.total,3);
  await page.keyboard.press('Escape');await page.locator('[data-nav="settings"]').click();await page.locator('#setting-sound').uncheck();await page.locator('[data-action="resume"]').click();
  await page.waitForFunction(()=>document.querySelector('h1')?.textContent.includes('时间到'),{},{timeout:75000});
  const timed=await get('/api/session/'+state.id+'/report');assert.equal(timed.status,'timeout');assert.equal(timed.remaining,3);assert.equal(timed.attempted,0);assert.equal(timed.elapsed,60);
  results.push('真实60秒倒计时自动结算，未输入不算答错，错词库不被未练习记录清空通过');
  await page.getByRole('button',{name:'回到出发地',exact:true}).click();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(artifacts,'home-mobile.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
  await page.getByRole('button',{name:'开始单词探险 →',exact:true}).click();await page.locator('#answer').waitFor();
  await page.screenshot({path:path.join(artifacts,'practice-mobile.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
  await page.getByRole('button',{name:'结束练习并查看报告',exact:true}).click();
  await page.getByRole('button',{name:'结束并看报告',exact:true}).click();
  await page.getByRole('heading',{name:'今天的努力，已被记住。',exact:true}).waitFor();
  await page.getByRole('button',{name:'再来一轮 →',exact:true}).click();await page.locator('#answer').waitFor();
  const peer=await page.context().newPage();await peer.goto(base);await peer.getByRole('button',{name:'继续探险',exact:true}).click();await peer.locator('#answer').waitFor();
  state=(await get('/api/bootstrap')).active;const multiId=state.id;
  const suffixFor=s=>vocabulary.find(w=>w.id===s.current.word_id).english.toLowerCase().replace(/[^a-z]/g,'').slice(-s.current.missing);
  const oldSuffix=suffixFor(state);
  await page.locator('#answer').fill(oldSuffix);
  await page.waitForFunction(()=>document.querySelector('.progress-head')?.textContent.includes('第 2 /'));
  await peer.locator('#answer').fill(oldSuffix);
  await peer.waitForFunction(()=>document.querySelector('.progress-head')?.textContent.includes('第 2 /'));
  let lost=false;
  await page.route('**/answer',async route=>{const response=await route.fetch();if(!lost){lost=true;await route.abort('failed');}else await route.fulfill({response});});
  state=await get('/api/session/'+multiId);await page.locator('#answer').fill(suffixFor(state));
  await page.getByRole('button',{name:'重试保存',exact:true}).waitFor();
  await page.getByRole('button',{name:'重试保存',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.progress-head')?.textContent.includes('第 3 /'));
  await page.unroute('**/answer');
  const retryReport=await get('/api/session/'+multiId+'/report');assert.equal(retryReport.attempted,2);assert.equal(retryReport.first_correct,2);
  await peer.close();
  results.push('双标签旧题自动同步、服务端已保存但响应丢失后重试不重复计分通过');
  assert.deepEqual(errors,[]);results.push('390px小屏无横向溢出、手动结束、浏览器无未捕获错误通过');
  fs.writeFileSync(path.join(artifacts,'acceptance.json'),JSON.stringify({passed:true,at:new Date().toISOString(),checks:results,errors},null,2));
  console.log(JSON.stringify({passed:true,checks:results},null,2));
 }catch(error){console.error(error);if(page){await page.screenshot({path:path.join(artifacts,'failure.png'),fullPage:true});console.error((await page.locator('main').innerText()).slice(0,2500));console.error(errors);}fs.writeFileSync(path.join(artifacts,'acceptance.json'),JSON.stringify({passed:false,checks:results,error:String(error)},null,2));process.exitCode=1;}
 finally{await browser?.close();server.kill('SIGTERM');await pause(250);fs.rmSync(directory,{recursive:true,force:true});}
})();
