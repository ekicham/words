// Isolated browser regression for official/archived textbook selection.
const assert=require('assert/strict'),fs=require('fs'),os=require('os'),path=require('path'),{spawn}=require('child_process');
const {chromium}=require('playwright');
(async()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'words-catalog-'));const server=spawn('python3',['app.py','--port','8768','--db',path.join(dir,'test.sqlite3')],{stdio:'ignore'});let browser;
try{for(let i=0;i<50;i++){try{if((await fetch('http://127.0.0.1:8768/api/bootstrap')).ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000},timezoneId:'Asia/Shanghai'});const errors=[];page.setDefaultTimeout(15000);page.on('pageerror',e=>errors.push(e.message));let locations=0;await page.route('**/api/location',r=>{locations++;return r.fulfill({json:{province:'浙江省',message:'验收模拟定位'}})});await page.clock.setFixedTime(new Date('2026-09-25T01:00:00Z'));await page.goto('http://127.0.0.1:8768/');await page.locator('#publisher').waitFor();
await page.waitForFunction(()=>JSON.parse(localStorage.getItem('word-isle-preferences')).province==='浙江省');
assert.equal(await page.locator('#date-label').innerText(),'2026年 9月25日 星期五 09时00分00秒');
assert.equal(await page.locator('#lunar-label').innerText(),'丙午马年 农历八月十五');
await page.clock.setFixedTime(new Date('2026-09-25T01:00:01Z'));
await page.waitForFunction(()=>document.querySelector('#date-label').textContent.endsWith('09时00分01秒'));
for(const [day,expected] of [['2026-02-16','乙巳蛇年 农历腊月廿九'],['2026-02-17','丙午马年 农历正月初一'],['2025-07-25','乙巳蛇年 农历闰六月初一']]){
 await page.clock.setFixedTime(new Date(day+'T04:00:00Z'));
 await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
 assert.equal(await page.locator('#lunar-label').innerText(),expected);
}
await page.clock.setFixedTime(new Date('2026-09-25T01:00:00Z'));
await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
assert.equal(await page.locator('.inline-note,.units,[data-action="locate"]').count(),0);
await page.locator('#daily-quote h1').waitFor();const quote=await page.locator('#daily-quote').innerText();
assert.match(await page.locator('#daily-quote [lang="en"]').innerText(),/[A-Za-z]/);
assert.match(await page.locator('#daily-quote a').getAttribute('href'),/^https:\/\//);
await page.reload();await page.locator('#daily-quote').waitFor();assert.equal(await page.locator('#daily-quote').innerText(),quote);assert.equal(locations,1,'Saved location must not be requested again');
await page.clock.setFixedTime(new Date('2026-09-25T15:59:00Z'));await page.locator('[data-nav="home"]').click();assert.equal(await page.locator('#daily-quote').innerText(),quote,'Same local calendar day');
await page.clock.setFixedTime(new Date('2026-09-25T16:01:00Z'));await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));assert.notEqual(await page.locator('#daily-quote').innerText(),quote,'Local midnight changes the quote even without reloading');

await page.clock.setFixedTime(new Date('2026-09-25T01:00:00Z'));await page.reload();await page.locator('#publisher').waitFor();
const newPublisher='人民教育出版社 · PEP（官网版）';assert.equal(await page.locator('#publisher option').count(),3);await page.locator('#publisher').selectOption(newPublisher);await page.locator('#grade').selectOption('6');assert.equal(await page.locator('#book').inputValue(),'pep-official-1212001601265');assert.match(await page.locator('#unit').innerText(),/Amazing places/);assert.equal(await page.locator('#book option').count(),1);
await page.locator('#province').selectOption('江苏省');await page.locator('#province').selectOption('浙江省');assert.equal(await page.locator('#publisher').inputValue(),newPublisher,'Manual publisher choice must survive province selection');
await page.locator('#grade').selectOption('5');assert.equal(await page.locator('#book option').count(),3);await page.locator('#book').selectOption('pep-official-1212001502255');assert.match(await page.locator('#unit').innerText(),/Following the rules/);await page.locator('#book').selectOption('pep-official-1212001502145');assert.match(await page.locator('#unit').innerText(),/My day/);
await page.locator('#grade').selectOption('4');await page.locator('#book').selectOption('pep-official-1212001402255');assert.match(await page.locator('#unit').innerText(),/139 个词条/);assert.match(await page.locator('#unit').innerText(),/Numbers 数词/);
await page.locator('#publisher').selectOption('人民教育出版社 · PEP');await page.locator('#grade').selectOption('6');await page.locator('#book').selectOption('pep-6-b');assert.match(await page.locator('#unit').innerText(),/91 个词条/);
await page.locator('#grade').selectOption('4');await page.locator('#book').selectOption('pep-4-a');
await page.locator('#province').selectOption('河南省');assert.equal(await page.locator('#book').inputValue(),'fltrp-4-a-2024-henan');assert.equal(await page.locator('#publisher').inputValue(),'外语教学与研究出版社 · 外研版');assert.equal(await page.locator('#grade').inputValue(),'4');assert.equal(await page.locator('#unit option').count(),9);assert.match(await page.locator('#unit').innerText(),/172 个词条/);assert.match(await page.locator('#unit').innerText(),/I love sports/);
await page.reload();await page.locator('#book').waitFor();assert.equal(await page.locator('#book').inputValue(),'fltrp-4-a-2024-henan');assert.equal(await page.locator('#province').inputValue(),'河南省');fs.mkdirSync('output/playwright',{recursive:true});await page.screenshot({path:'output/playwright/henan-fltrp-home.png',fullPage:true});
await page.locator('[data-nav="library"]').click();await page.locator('[data-vocabulary="fltrp-4-a-2024-henan"]').click();await page.waitForFunction(()=>document.querySelectorAll('tbody tr').length===172);assert.match(await page.locator('tbody tr').first().innerText(),/sport/);assert.match(await page.locator('tbody').innerText(),/on one's own/);await page.screenshot({path:'output/playwright/henan-fltrp-vocabulary.png',fullPage:true});
await page.locator('[data-nav="home"]').click();await page.locator('#province').selectOption('浙江省');assert.equal(await page.locator('#book').inputValue(),'pep-4-a');
await page.locator('#publisher').selectOption(newPublisher);await page.locator('#grade').selectOption('6');await page.locator('#book').selectOption('pep-official-1212001601265');fs.mkdirSync('output/playwright',{recursive:true});await page.screenshot({path:'output/playwright/official-catalog.png',fullPage:true});await page.reload();assert.equal(await page.locator('#publisher').inputValue(),newPublisher);
await page.getByRole('button',{name:'开始单词探险'}).click();await page.locator('#answer').waitFor();assert.match(await page.locator('.practice-top').innerText(),/2024 审定/);await page.locator('[data-action="hint"]').click();await page.locator('.reveal').waitFor();await page.locator('[data-action="skip"]').click();await page.waitForTimeout(900);assert.match(await page.locator('.progress-head').innerText(),/第 2 \/ 144/);await page.screenshot({path:'output/playwright/official-practice.png',fullPage:true});assert.deepEqual(errors,[]);
const firstVisit=await browser.newPage({viewport:{width:390,height:844}});firstVisit.setDefaultTimeout(15000);let failedLocations=0;
await firstVisit.route('**/api/location',r=>{failedLocations++;return r.fulfill({status:503,json:{error:'验收模拟定位不可用'}})});
await firstVisit.goto('http://127.0.0.1:8768/');await firstVisit.waitForFunction(()=>JSON.parse(localStorage.getItem('word-isle-preferences')||'{}').locationChecked===true);
await firstVisit.locator('#province').selectOption('广东省');await firstVisit.reload();await firstVisit.locator('#province').waitFor();assert.equal(failedLocations,1);assert.equal(await firstVisit.locator('#province').inputValue(),'广东省');
await firstVisit.screenshot({path:'output/playwright/daily-quote-mobile.png',fullPage:true});assert.equal(await firstVisit.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.equal(await firstVisit.locator('#date-label').isVisible(),true);assert.equal(await firstVisit.locator('#lunar-label').isVisible(),true);await firstVisit.close();
fs.writeFileSync('output/playwright/daily-quote-home.json',JSON.stringify({passed:true,at:new Date().toISOString(),checks:['地区说明及学习地图移除，单元下拉仍可选择','名言中英双语、作者出处，同日刷新稳定、本地午夜换句','首次自动定位一次并记住；失败仍可手选且刷新不重试','新旧教材选择与练习未受影响','390px 无横向溢出'],errors},null,2));
console.log('PASS: daily bilingual quotes, local midnight rollover, first-run location only, clean home, catalogue and practice');
}finally{if(browser)await browser.close();server.kill('SIGTERM');await new Promise(r=>server.once('close',r));fs.rmSync(dir,{recursive:true,force:true})}})().catch(e=>{console.error(e);process.exitCode=1});
