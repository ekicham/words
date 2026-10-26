// Run after test_cloudflare_http.py, before --verify-restart. Local fixtures only.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=process.cwd(),base='http://127.0.0.1:8787',artifacts=path.join(root,'output/cloudflare');
fs.mkdirSync(artifacts,{recursive:true});
const credentials=JSON.parse(fs.readFileSync(path.join(root,'.wrangler/cloud-test-restart.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.locator('#login-form').waitFor();
  await page.screenshot({path:path.join(artifacts,'login.png'),fullPage:true});
  await page.getByLabel('账号',{exact:true}).fill(credentials.username);
  await page.getByLabel('密码',{exact:true}).fill(credentials.password);
  await page.locator('#submit-login').click();
  await page.getByRole('button',{name:'开始单词探险 →',exact:true}).waitFor();
  await page.screenshot({path:path.join(artifacts,'home.png'),fullPage:true});
  await page.getByRole('button',{name:'设置',exact:true}).click();
  await page.locator('#ipa-cloud-refresh').waitFor();
  assert.equal(await page.locator('input[name="secret_key"]').count(),0);
  assert.equal(await page.locator('#ipa-prepare').count(),0);
  await page.screenshot({path:path.join(artifacts,'settings.png'),fullPage:true});
  await page.getByRole('button',{name:'音标学习',exact:true}).click();
  await page.getByRole('heading',{name:'跟着视频学音标',exact:true}).waitFor();
  assert.match(await page.locator('.ipa-consent').innerText(),/云端账号/);
  await page.evaluate(()=>{const p=JSON.parse(localStorage.getItem('word-isle-preferences')||'{}');p.book='cloud-test';p.sound=false;p.learningOrder='sequential';p.practiceType='hint';localStorage.setItem('word-isle-preferences',JSON.stringify(p));});
  await page.goto(base);await page.getByRole('button',{name:'开始单词探险 →',exact:true}).click();
  await page.locator('#answer').waitFor();
  await page.locator('#answer').fill('ple');
  await page.waitForFunction(()=>document.querySelector('.progress-head')?.textContent.includes('第 2 /'));
  await page.locator('[data-action="end"]').click();
  await page.getByRole('button',{name:'结束并看报告',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#main')?.textContent.includes('首次独立正确率'));
  await page.screenshot({path:path.join(artifacts,'report.png'),fullPage:true});
  // Refresh the expected persistence snapshot after this real UI answer.
  credentials.summary=await page.evaluate(async()=> (await fetch('/api/bootstrap').then(r=>r.json())).summary);
  fs.writeFileSync(path.join(root,'.wrangler/cloud-test-restart.json'),JSON.stringify(credentials),{mode:0o600});
  await page.getByRole('button',{name:'退出登录',exact:true}).click();await page.locator('#login-form').waitFor();
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(artifacts,'login-mobile.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.deepEqual(errors,[]);console.log('PASS: login, home, cloud settings, phonetics disclosure, answer/report, logout, mobile login; no page errors.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
