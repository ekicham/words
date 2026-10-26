// Dedicated temporary database; never changes the user's learning records.
const assert=require('assert/strict'),fs=require('fs'),os=require('os'),path=require('path');
const {spawn,execFileSync}=require('child_process'),{chromium}=require('playwright');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'word-isle-completed-')),db=path.join(dir,'test.sqlite3'),base='http://127.0.0.1:8771';
 const server=spawn('python3',['app.py','--port','8771','--db',db],{stdio:'ignore'});let browser;
 const snapshot=()=>execFileSync('python3',['-c',`import sqlite3,sys,json
with sqlite3.connect(sys.argv[1]) as db:
 print(json.dumps({t:db.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall() for t in ['books','words','sessions','items','attempts','requests']}))`,db],{encoding:'utf8'});
 try{
  for(let i=0;i<50;i++){try{if((await fetch(base+'/api/bootstrap')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
  browser=await chromium.launch({channel:'chrome',headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000},timezoneId:'Asia/Shanghai'}),errors=[];
  page.setDefaultTimeout(15000);page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>localStorage.setItem('word-isle-preferences',JSON.stringify({province:'浙江省',locationChecked:true,sound:false})));
  await page.goto(base);await page.locator('#publisher').waitFor();
  assert.equal(await page.locator('.stats .stat').count(),4);
  for(const scope of ['completed','today']){
   await page.locator(`[data-action="${scope}"]`).click();await page.locator('.completed-empty').waitFor();
   assert.match(await page.locator('h1').innerText(),/已完成/);
   await page.getByRole('button',{name:'返回首页',exact:true}).click();await page.locator('#publisher').waitFor();
  }
  execFileSync('python3',['-c',`import sys,time
from app import App,mask_word
today=time.localtime();midnight=time.mktime((today.tm_year,today.tm_mon,today.tm_mday,0,0,0,0,0,-1));clock=[midnight-10]
app=App(sys.argv[1],now=lambda:clock[0],seed=False)
pack=dict(id='completed-a',title='学习明细验收·原版',publisher='验收出版社',edition='原版',grade=6,term='上',source_url='https://example.com/book',words=[dict(english=w,meaning=m,unit='Unit 1') for w,m in [('Monday','星期一'),('bookstore','书店'),('science','科学'),('Tuesday','星期二')]])
app.import_book(pack)
app.import_book(dict(pack,id='completed-b',title='学习明细验收·新版',edition='新版',grade=5,term='下',words=[dict(english='monday',meaning='周一',unit='Unit 2')]))
s=app.start(dict(book_id=pack['id'],province='浙江省',learning_order='sequential'))
def act(action,**extra):
 global s
 payload=dict(position=s['position'],request_id=str(s['position'])+action,**extra)
 s=app.act(s['id'],action,payload)['session']
 return payload
def solve():
 word=next(w for w in app.vocabulary(s['book_id']) if w['id']==s['current']['word_id'])
 return act('answer',answer=mask_word(word['english'])[1])
solve();solve();clock[0]=midnight+5;solve();act('skip');act('finish')
clock[0]=time.time();s=app.start(dict(book_id='completed-b',province='江苏省'));solve();payload=solve();app.act(s['id'],'answer',payload)
`,db],{stdio:'pipe'});
  const before=snapshot();
  const all=await (await fetch(base+'/api/completed-words')).json(),today=await (await fetch(base+'/api/completed-words?scope=today')).json();
  assert.equal(all.total,3);assert.equal(today.total,2);
  assert.equal((await fetch(base+'/api/completed-words?scope=invalid')).status,400);
  await page.reload();await page.locator('#publisher').waitFor();
  assert.equal(await page.locator('[data-action="completed"] strong').innerText(),'3个单词');
  assert.equal(await page.locator('[data-action="today"] strong').innerText(),'2个单词');
  await page.locator('[data-action="completed"]').focus();await page.keyboard.press('Enter');
  await page.locator('.completed-table').waitFor();
  assert.deepEqual(await page.locator('.completed-table thead th').allTextContents(),['最近学习日期','单词','音标','中文','所属单元','学习频次','所属学期','所属年级','所属教材','所属地区']);
  assert.equal(await page.locator('.completed-table tbody').count(),3);
  const monday=page.locator('.completed-table tbody').filter({has:page.getByRole('rowheader',{name:'monday',exact:true})});
  assert.equal(await monday.count(),1);assert.equal(await monday.locator('tr').count(),2);
  assert.equal(await monday.locator('.word-frequency').innerText(),'3 次');
  const text=await monday.innerText();for(const value of ['星期一','周一','Unit 1','Unit 2','上册','下册','六年级','五年级','原版','新版','浙江省','江苏省'])assert.ok(text.includes(value),value);
  assert.equal(await monday.locator('.word-phonetic').evaluateAll(nodes=>nodes.every(n=>n.textContent.includes('/'))),true);
  fs.mkdirSync('output/playwright',{recursive:true});await page.screenshot({path:'output/playwright/completed-all-desktop.png',fullPage:true});
  await page.locator('[data-action="today"]').click();await page.getByRole('heading',{name:'今日已完成',exact:true}).waitFor();
  assert.equal(await page.locator('.completed-table tbody').count(),2);
  assert.equal(await page.locator('.completed-table').getByText('bookstore',{exact:true}).count(),0);
  assert.equal(await page.locator('.completed-table tbody').filter({has:page.getByRole('rowheader',{name:'monday',exact:true})}).locator('.word-frequency').innerText(),'2 次');
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:1000});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   const scroll=page.locator('.completed-scroll');await scroll.focus();await page.keyboard.press('End');
   assert.ok(await scroll.evaluate(el=>el.scrollWidth>el.clientWidth));
   await page.screenshot({path:`output/playwright/completed-today-${width}.png`,fullPage:true});
  }
  await page.getByRole('button',{name:'返回首页',exact:true}).click();await page.locator('#publisher').waitFor();
  assert.equal(await page.locator('.stats').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length),2);
  await page.screenshot({path:'output/playwright/completed-home-mobile.png',fullPage:true});
  assert.equal(snapshot(),before,'Read-only detail navigation must not modify saved learning records');
  assert.deepEqual(errors,[]);
  const result={passed:true,at:new Date().toISOString(),checks:['累计和今日去重计数，包含未结束练习','跨午夜按实际提交时间，重复轮次与不同教材同词合并','十列详情及多教材出处，累计/今日频次一致','空状态、键盘进入、范围切换和返回首页','390px四卡两列、表格局部滚动，无页面横溢','浏览明细不修改原有记录'],errors};
  fs.writeFileSync('output/playwright/completed-words.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
 }finally{if(browser)await browser.close();server.kill('SIGTERM');await new Promise(r=>server.once('close',r));fs.rmSync(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1});
