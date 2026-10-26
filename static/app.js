'use strict';
const $ = (selector) => document.querySelector(selector);
const main = $('#main');
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const letters = value => value.toLowerCase().replace(/[^a-z]/g, '');
const gradeName = value => ['','一年级','二年级','三年级','四年级','五年级','六年级','七年级','八年级','九年级','高一','高二','高三'][value] || value;
const fmtTime = seconds => `${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
const pct = (a,b) => b ? `${Math.round(100*a/b)}%` : '—';
const date = value => new Date(value*1000).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
const lunarCalendar=new Intl.DateTimeFormat('zh-CN-u-ca-chinese',{dateStyle:'long'});
function renderClock(){
  const now=new Date(),pad=n=>String(n).padStart(2,'0');
  $('#date-label').textContent=`${now.getFullYear()}年 ${now.getMonth()+1}月${now.getDate()}日 星期${'日一二三四五六'[now.getDay()]} ${pad(now.getHours())}时${pad(now.getMinutes())}分${pad(now.getSeconds())}秒`;
  const lunar=Object.fromEntries(lunarCalendar.formatToParts(now).map(part=>[part.type,part.value]));
  const animal='鼠牛虎兔龙蛇马羊猴鸡狗猪'[(Number(lunar.relatedYear)-4)%12];
  $('#lunar-label').textContent=`${lunar.yearName}${animal}年 农历${lunar.month}${lunar.day}`;
}
// Public-domain excerpts; the other language is our own translation.
const dailyQuotes = [
  {"zh":"千里之行，始于足下。","en":"Even the longest journey begins with one step.","author":"老子 · Laozi","work":"《道德经》第六十四章","source":"https://ctext.org/dao-de-jing/zh","translation":"英文为词屿意译"},
  {"zh":"行动起来，让每一个明天都比今天更进一步。","en":"But to act, that each to-morrow find us farther than to-day.","author":"朗费罗 · H. W. Longfellow","work":"A Psalm of Life","source":"https://www.poetryfoundation.org/poems/44644/a-psalm-of-life","translation":"中文为词屿意译"},
  {"zh":"学而时习之，不亦说乎？","en":"Is it not a joy to learn and practise what you have learned?","author":"孔子 · Confucius","work":"《论语·学而》","source":"https://ctext.org/analects/xue-er/zh","translation":"英文为词屿意译"},
  {"zh":"愿意付诸努力，本身就是乐观。","en":"The desire and will to work is optimism itself.","author":"海伦·凯勒 · Helen Keller","work":"Optimism","source":"https://www.gutenberg.org/files/31622/31622-h.htm","translation":"中文为词屿意译"},
  {"zh":"锲而不舍，金石可镂。","en":"Keep carving without giving up, and even metal and stone can be engraved.","author":"荀子 · Xunzi","work":"《荀子·劝学》","source":"https://ctext.org/wiki.pl?chapter=331739&if=en","translation":"英文为词屿意译"},
  {"zh":"希望是一只长着羽毛的鸟。","en":"“Hope” is the thing with feathers.","author":"艾米莉·狄金森 · Emily Dickinson","work":"“Hope” is the thing with feathers","source":"https://www.poetryfoundation.org/poems/42889/hope-is-the-thing-with-feathers-314","translation":"中文为词屿意译"},
  {"zh":"温故而知新，可以为师矣。","en":"Review what you know and discover something new; then you can be a teacher.","author":"孔子 · Confucius","work":"《论语·为政》","source":"https://ctext.org/analects/wei-zheng/zh","translation":"英文为词屿意译"},
  {"zh":"相信自己：每颗心都会与这根坚韧的弦共鸣。","en":"Trust thyself: every heart vibrates to that iron string.","author":"爱默生 · Ralph Waldo Emerson","work":"Self-Reliance","source":"https://www.gutenberg.org/files/16643/16643-h.htm","translation":"中文为词屿意译"},
  {"zh":"不积跬步，无以至千里。","en":"Without taking small steps, you cannot travel a thousand miles.","author":"荀子 · Xunzi","work":"《荀子·劝学》","source":"https://ctext.org/wiki.pl?chapter=331739&if=en","translation":"英文为词屿意译"},
  {"zh":"不断进步，不断追求；学会努力，也学会等待。","en":"Still achieving, still pursuing, learn to labor and to wait.","author":"朗费罗 · H. W. Longfellow","work":"A Psalm of Life","source":"https://www.poetryfoundation.org/poems/44644/a-psalm-of-life","translation":"中文为词屿意译"},
  {"zh":"三人行，必有我师焉。","en":"When three walk together, there is someone I can learn from.","author":"孔子 · Confucius","work":"《论语·述而》","source":"https://ctext.org/analects/shu-er/zh","translation":"英文为词屿意译"},
  {"zh":"每天多做一点小练习，让努力的能力保持活力。","en":"Keep the faculty of effort alive in you by a little gratuitous exercise every day.","author":"威廉·詹姆斯 · William James","work":"Psychology","source":"https://www.gutenberg.org/files/55262/old/55262-h/55262-h.htm","translation":"中文为词屿意译"}
];
function dailyQuoteMarkup(now=new Date()){
  // Local calendar days, not elapsed 24-hour periods: stable across DST and reloads.
  const day=Math.floor(Date.UTC(now.getFullYear(),now.getMonth(),now.getDate())/86400000);
  const q=dailyQuotes[((day%dailyQuotes.length)+dailyQuotes.length)%dailyQuotes.length];
  return `<h1>${esc(q.zh)}</h1><p><span lang="en">${esc(q.en)}</span> <a class="quote-author" href="${esc(q.source)}" target="_blank" rel="noreferrer" title="${esc(q.work+' · '+q.translation)}" aria-label="${esc(q.author+'，查看名言出处')}">—— ${esc(q.author)}</a></p>`;
}
let prefs; try { prefs=window.wordIsleDesktop?.preferences ?? JSON.parse(localStorage.getItem('word-isle-preferences') || '{}'); } catch { prefs={}; }
if (!prefs || typeof prefs !== 'object' || Array.isArray(prefs)) prefs={};
let data, session, route='home', currentReport, busy=false, pending=null, clockAt=0, clockRemaining=0, locationRevision=0;
let sound= prefs.sound !== false, voiceToken=0, player=null, audioDone=null, speechAbort=null, toastTimer;
let rewardBusy=false;
const speechRates=[.75,1,1.25,1.5];
let speechRate=speechRates.includes(prefs.speechRate)?prefs.speechRate:1;
prefs.learningOrder=prefs.learningOrder==='sequential'?'sequential':'random';
const practiceNames={hint:'提示拼写',dictation_en:'英文听写',dictation_zh:'中文听写'};
prefs.practiceType=Object.hasOwn(practiceNames,prefs.practiceType)?prefs.practiceType:'hint';
prefs.dictationMode=prefs.dictationMode==='manual'?'manual':'auto';
prefs.dictationSeconds=Number.isInteger(prefs.dictationSeconds)&&prefs.dictationSeconds>=1&&prefs.dictationSeconds<=300?prefs.dictationSeconds:15;
const isDictation=()=>session?.practice_type&&session.practice_type!=='hint';
const isManualDictation=()=>isDictation()&&session.dictation_mode==='manual';
const dictationLabel=s=>s.dictation_mode==='manual'?'手动模式 · Enter 提交':`自动模式 · 每词 ${s.dictation_seconds} 秒`;
let serverOffset=0,draftRevision=0,dictationAdvanceAt=0,dictationSubmitQueued=false;
function savePrefs(){ try { localStorage.setItem('word-isle-preferences',JSON.stringify(prefs)); } catch {} if(window.wordIsleDesktop)window.webkit.messageHandlers.preferences.postMessage(prefs); }
function toast(message){ $('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,4500); }
async function api(path, body){
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),10000);
  try{
    const response=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,signal:controller.signal});
    const result=await response.json();
    if (!response.ok){ if(response.status===401)location.assign('/login.html');const error=new Error(result.error || '请求未完成');error.status=response.status;throw error; }
    return result;
  }finally{clearTimeout(timeout);}
}
function chooseBook(){ return data.books.find(b=>b.id===prefs.book) || data.books.find(b=>b.id==='pep-6-a') || data.books[0]; }
function recommendedBook(province){
  const current=chooseBook();if(!current)return;
  const matches=b=>b.regions.includes(province)&&b.grade===current.grade&&b.term===current.term;
  return matches(current)?current:data.books.find(b=>matches(b)&&b.publisher===current.publisher)||data.books.find(matches);
}
function header(title){
  const names={phonetics:'音标学习',home:'单词探险',practice:'正在探险',report:'探险报告',mistakes:'错词巩固',history:'学习足迹',library:'我的词库',vocabulary:'教材词表',settings:'设置',completed:'累计已完成',today:'今日已完成',rewards:'亲子幸运转盘'};
  document.body.classList.toggle('practicing',route==='practice');
  $('#breadcrumb').textContent=`我的学习 / ${title || names[route]}`;
  document.querySelectorAll('[data-nav]').forEach(b=>{const selected=b.dataset.nav===route || (['practice','report','completed','today','rewards'].includes(route)&&b.dataset.nav==='home') || (route==='vocabulary'&&b.dataset.nav==='library');b.classList.toggle('selected',selected);if(selected)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  $('#mistake-count').textContent=data.summary.mistakes;
}
function sync(s){ session=s;data.active=s.status==='active'?s:null;clockAt=performance.now();clockRemaining=Math.max(0,s.deadline-s.now);serverOffset=s.now*1000-Date.now();draftRevision=Math.max(s.current?.draft_revision||0,draftRevision); }
async function refresh(){data=await api('/api/bootstrap');header();}
async function navigate(view){
  PhoneticsUI.leave();leaveFocus();stopVoice();route=view;header();
  try{
    await refresh();
    if(view==='phonetics')await PhoneticsUI.mount();
    if(view==='home')renderHome();
    if(view==='history')renderHistory();
    if(view==='library')renderLibrary();
    if(view==='settings')await renderSettings();
    if(view==='mistakes')await renderMistakes();
    if(view==='completed'||view==='today')await renderCompleted(view==='today'?'today':'all');
    if(view==='rewards')await renderRewards();
    window.scrollTo(0,0);
  }catch(error){toast(error.message);}
}
function renderHome(){
  route='home';header();const book=chooseBook();
  if(!book){main.innerHTML='<div class="card empty"><h2>还没有词库</h2><button class="primary" data-action="library">导入第一本教材</button></div>';return;}
  prefs.book=book.id;
  const province=data.provinces.includes(prefs.province)?prefs.province:'浙江省';
  const publishers=[...new Set(data.books.map(b=>b.publisher))];
  const same=data.books.filter(b=>b.publisher===book.publisher);
  const minutes=prefs.minutes || 15;const custom=prefs.customTime || ![15,30,45].includes(minutes);
  const unit=book.units.some(u=>u.unit===prefs.unit)?prefs.unit:'';
  main.innerHTML=`
    <div class="page-heading daily-quote"><div id="daily-quote">${dailyQuoteMarkup()}</div></div>
    <section class="stats" aria-label="学习概况"><button class="stat stat-link" data-action="completed"><span class="stat-icon" aria-hidden="true">✓</span><span><strong>${data.summary.completed_words}<small>个单词</small></strong><span class="stat-label">累计已完成</span></span><span class="stat-arrow" aria-hidden="true">›</span></button><button class="stat stat-link" data-action="today"><span class="stat-icon" aria-hidden="true">◈</span><span><strong>${data.summary.today_words}<small>个单词</small></strong><span class="stat-label">今日已完成</span></span><span class="stat-arrow" aria-hidden="true">›</span></button><button class="stat stat-link" data-action="rewards"><span class="stat-icon" aria-hidden="true">✦</span><span><strong>${data.summary.available_stars??data.summary.stars}<small>颗星星</small></strong><span class="stat-label">亲子转盘 · 可用星星</span></span><span class="stat-arrow" aria-hidden="true">›</span></button><button class="stat stat-link" data-action="mistakes"><span class="stat-icon" aria-hidden="true">↻</span><span><strong>${data.summary.mistakes}<small>个单词</small></strong><span class="stat-label">等待你再试一次</span></span><span class="stat-arrow" aria-hidden="true">›</span></button></section>
    ${data.active?`<div class="banner"><span>你还有一次未结束的探险，已完成 ${data.active.position} 次单词练习。</span><button class="primary" data-action="resume">继续探险</button></div>`:''}
    <div class="home-grid"><section class="card setup-card"><div class="card-title"><h2>准备出发</h2><small>跟着课本，稳稳进步</small></div>
      <div class="step-heading"><b>1</b> 找到你的课本</div><div class="form-grid">
      <div class="field"><label for="province">所在地区</label><select id="province">${data.provinces.map(p=>`<option ${p===province?'selected':''}>${esc(p)}</option>`).join('')}</select></div>
      <div class="field"><label for="publisher">教材出版社</label><select id="publisher">${publishers.map(p=>`<option ${p===book.publisher?'selected':''}>${esc(p)}</option>`).join('')}</select></div>
      <div class="field"><label for="grade">年级</label><select id="grade">${[...new Set(same.map(b=>b.grade))].sort((a,b)=>a-b).map(g=>`<option value="${g}" ${g===book.grade?'selected':''}>${esc(gradeName(g))}</option>`).join('')}</select></div>
      <div class="field"><label for="book">学期 / 教材版本</label><select id="book">${same.filter(b=>b.grade===book.grade).map(b=>`<option value="${esc(b.id)}" ${b.id===book.id?'selected':''}>${esc(b.term)}册${same.filter(x=>x.grade===b.grade&&x.term===b.term).length>1?' · '+esc(b.edition):''}</option>`).join('')}</select></div>
      <div class="field span-two"><label for="unit">练习范围</label><select id="unit"><option value="">整本课本 · ${book.count} 个词条</option>${book.units.map(u=>`<option value="${esc(u.unit)}" ${unit===u.unit?'selected':''}>${esc(u.unit)} · ${u.count} 个词条</option>`).join('')}</select></div></div>
      <div class="step-heading"><b>2</b> 练习方式</div><div class="learning-options practice-options" aria-label="练习方式">${[['hint','看提示补全单词'],['dictation_en','听英文，写完整单词'],['dictation_zh','听中文，写英文单词']].map(([value,note])=>`<button data-practice="${value}" class="${prefs.practiceType===value?'active':''}" aria-pressed="${prefs.practiceType===value}"><strong>${practiceNames[value]}</strong><small>${note}</small></button>`).join('')}</div><p class="practice-note">${prefs.practiceType==='hint'?'显示部分字母、音标和中文，填满后自动检查。':`不显示字母、音标或中文。第一遍读完可输入；${prefs.dictationMode==='manual'?'手动模式，每词不限时，按 Enter 提交并进入下一词。':`自动模式，第二遍结束后限时 ${prefs.dictationSeconds} 秒，写满或到时自动下一词。`} 可在设置中调整。`}</p>
      <div class="step-heading"><b>3</b> 出题顺序</div><div class="learning-options" aria-label="出题顺序">${[['sequential','顺序学习','按单元从头到尾'],['random','随机学习','随机挑选，一轮不重复']].map(([value,title,note])=>`<button data-order="${value}" class="${prefs.learningOrder===value?'active':''}" aria-pressed="${prefs.learningOrder===value}"><strong>${title}</strong><small>${note}</small></button>`).join('')}</div>
      <div class="step-heading"><b>4</b> 给专注留一点时间</div><div class="time-options" aria-label="练习时长">${[15,30,45].map(n=>`<button data-minutes="${n}" class="${!custom&&minutes===n?'active':''}" aria-pressed="${!custom&&minutes===n}">${n} <small>分钟</small></button>`).join('')}<button data-minutes="custom" class="${custom?'active':''}" aria-pressed="${custom}">自定义</button></div>
      ${custom?`<label class="custom-row" for="custom-minutes">练习 <input id="custom-minutes" type="number" min="1" max="180" step="1" value="${esc(minutes)}"> 分钟（1–180）</label>`:''}
      <button class="primary start" data-action="start" ${data.active?'disabled':''}>开始单词探险 <span>→</span></button>
    </section><div class="home-aside"><section class="card journey"><div class="eyebrow">YOUR NEXT ADVENTURE</div><h2>下一站，单词岛</h2><p>一个字母，一步进步。<br>让新单词成为老朋友。</p><div class="book-preview"><small>ENGLISH · WORD ISLE</small><strong>${esc(gradeName(book.grade))}</strong><div class="book-bottom"><span>${esc(book.term)}册 · ${book.count} 个词条<br>${esc(book.edition.slice(0,18))}</span><b>${book.grade}</b></div></div><div class="journey-footer"><span>听音记忆</span><span>拼写闯关</span><span>星星奖励</span></div></section>
    <section class="card tips"><h3>你的探险小贴士</h3><div class="tip"><b>01</b><span>${prefs.practiceType==='hint'?'听英文和中文释义，输入空缺的字母。':'只听所选语言，完整朗读两遍。'}</span></div><div class="tip"><b>02</b><span>${prefs.practiceType==='hint'?'填满自动检查，答对就进入下一词。':(prefs.dictationMode==='manual'?'写完整英文后按 Enter，判分并进入下一词。':`${prefs.dictationSeconds} 秒内写完整英文，写满自动检查并继续。`)}</span></div><div class="tip"><b>03</b><span>首次独立答对得 10 星，连续答对挑战自己的纪录。</span></div></section></div></div>
    `;
}
async function locate(){
  const revision=++locationRevision;prefs.locationChecked=true;savePrefs();
  try{const result=await api('/api/location');if(revision!==locationRevision)return;
    if(result.province){prefs.province=result.province;const recommendation=recommendedBook(result.province);if(recommendation)prefs.book=recommendation.id;savePrefs();}
  }catch{/* Region remains manually selectable if first-run location is unavailable. */}
  if(route==='home')renderHome();
}
async function start(mode='learn',bookId){
  if(busy)return;
  const book=bookId || chooseBook().id;const raw=$('#custom-minutes')?.value;const minutes=raw!==undefined?Number(raw):(prefs.minutes||15);
  if(!Number.isInteger(minutes)||minutes<1||minutes>180){toast('请输入 1–180 分钟的整数');$('#custom-minutes')?.focus();return;}
  busy=true;const button=$('[data-action="start"]');if(button)button.disabled=true;enterFocus();
  try{const s=await api('/api/start',{book_id:book,minutes,province:prefs.province||'浙江省',unit:mode==='learn'?(prefs.unit||''):'',mode,learning_order:prefs.learningOrder,practice_type:prefs.practiceType,dictation_mode:prefs.dictationMode,dictation_seconds:prefs.dictationSeconds});prefs.minutes=minutes;savePrefs();sync(s);pending=null;renderPractice();speakCurrent();}
  catch(error){leaveFocus();toast(error.message);if(button)button.disabled=false;}
  finally{busy=false;}
}
async function resume(){enterFocus();try{sync(await api(`/api/session/${data.active.id}`));pending=null;if(session.status==='active'){renderPractice();await speakCurrent();}else await showReport(session.id);}catch(error){leaveFocus();toast(error.message);}}
async function renderSettings(){
  main.innerHTML=`<div class="page-heading"><h1>设置</h1></div><section class="card settings-card"><div class="setting-row"><label for="setting-sound">朗读声音</label><input id="setting-sound" type="checkbox" role="switch" ${sound?'checked':''}></div><div class="setting-row"><label for="speech-rate">朗读语速</label><select id="speech-rate">${speechRates.map(r=>`<option value="${r}" ${r===speechRate?'selected':''}>${r}×${r<1?' 慢速':r===1?' 正常':r===1.25?' 稍快':' 快速'}</option>`).join('')}</select></div></section><div class="settings-actions">${data.active?'<button class="primary" data-action="resume">继续探险</button>':'<button class="primary" data-action="home">回到首页</button>'}</div>`;
  $('.settings-actions').insertAdjacentHTML('beforebegin',`<section class="card settings-card dictation-settings"><h2>听写设置</h2><p class="practice-note">英文听写、中文听写共用。自动保存，下次开始练习生效。</p><div class="setting-row"><label for="dictation-mode">听写模式</label><select id="dictation-mode"><option value="auto" ${prefs.dictationMode==='auto'?'selected':''}>自动模式</option><option value="manual" ${prefs.dictationMode==='manual'?'selected':''}>手动模式</option></select></div><div class="setting-row" id="dictation-duration-row" ${prefs.dictationMode==='manual'?'hidden':''}><label for="dictation-seconds">每词倒计时</label><div class="duration-control"><input id="dictation-seconds" type="number" min="1" max="300" step="1" required value="${prefs.dictationSeconds}" aria-describedby="dictation-setting-note"><span>秒</span></div></div><p class="practice-note" id="dictation-setting-note">${dictationSettingNote()}</p><p class="practice-note">练习总时长单独设置；总时间到后，完成当前单词再结束。</p></section>`);
  await PhoneticsUI.mountSettings();if(route!=='settings')return;
  const panel=document.createElement('section');panel.className='card prize-settings';panel.innerHTML='<h2>亲子转盘奖品</h2><p>正在读取奖品…</p>';$('.settings-actions').before(panel);
  try{
    const config=await api('/api/rewards/config');if(route!=='settings'||!panel.isConnected)return;
    const prizes=config.prizes.map(p=>config.presets.find(preset=>preset.icon===p.icon)||p);
    panel.innerHTML=`<div class="prize-settings-heading"><div><h2>亲子转盘奖品</h2><p>八种奖品等概率 · 每次 ${config.cost} 星</p></div><button class="secondary" data-action="rewards">查看转盘</button></div>
      <form id="prize-settings-form" data-revision="${esc(config.revision)}"><div class="prize-edit-grid">${prizes.map((p,i)=>`<fieldset class="prize-editor"><legend>奖品 ${i+1}</legend><div class="prize-fields"><label for="prize-icon-${i}">图标<select id="prize-icon-${i}" name="icon-${i}" required>${config.presets.map(preset=>`<option value="${esc(preset.icon)}" data-name="${esc(preset.name)}" data-detail="${esc(preset.detail)}" ${preset.icon===p.icon?'selected':''}>${esc(preset.icon)}</option>`).join('')}</select></label><label for="prize-name-${i}">奖品名称<output id="prize-name-${i}">${esc(p.name)}</output></label><label class="prize-detail-field" for="prize-detail-${i}">活动说明<output id="prize-detail-${i}">${esc(p.detail)}</output></label></div></fieldset>`).join('')}</div>
      <div class="prize-save-row"><button type="submit" class="primary">保存奖品设置</button><span id="prize-save-status" role="status">选择图标自动填写活动，保存后生效。</span></div></form>`;
  }catch(error){if(panel.isConnected)panel.innerHTML=`<h2>亲子转盘奖品</h2><p role="alert">${esc(error.message)}</p><button class="secondary" data-action="settings">重新加载</button>`;}
}
function dictationSettingNote(){return prefs.dictationMode==='manual'?'每词不限时，写满后可修改；按 Enter 提交，判分后自动进入下一词。':'可设置 1–300 秒。第二遍朗读结束后计时；写满或到时自动进入下一词，未写完判错。';}
async function savePrizeSettings(form){
  if(form.dataset.saving)return;
  const prizes=[...form.querySelectorAll('select')].map(select=>({name:select.selectedOptions[0].dataset.name,icon:select.value,detail:select.selectedOptions[0].dataset.detail}));
  form.dataset.saving='true';form.querySelectorAll('fieldset,button').forEach(el=>el.disabled=true);
  const status=form.querySelector('[role="status"]');status.textContent='正在保存…';
  try{const config=await api('/api/rewards/config',{prizes,revision:form.dataset.revision});form.dataset.revision=config.revision;status.textContent='已保存，下次抽奖使用这些奖品。';}
  catch(error){status.textContent=error.message;}
  finally{delete form.dataset.saving;form.querySelectorAll('fieldset,button').forEach(el=>el.disabled=false);}
}
async function moveWord(direction){
  if(busy||pending||!session||session.status!=='active')return;
  if(direction===1&&!session.readonly)return act('skip');
  const position=(session.view_position??session.position)+direction;
  if(position<0||position>session.position)return;
  busy=true;disableAnswer(true);stopVoice();
  try{const s=await api(`/api/session/${session.id}?position=${position}`);if(route!=='practice')return;sync(s);if(s.status==='active'){renderPractice();speakCurrent();}else await showReport(s.id);}
  catch(error){feedback(error.message,'error');disableAnswer(false);}
  finally{busy=false;}
}
function enterFocus(){
  document.body.classList.add('focus-mode');
  if(!document.fullscreenElement&&document.documentElement.requestFullscreen){
    document.documentElement.requestFullscreen().then(()=>{if(!document.body.classList.contains('focus-mode'))document.exitFullscreen().catch(()=>{});}).catch(()=>{});
  }
  updateFullscreenButton();$('#answer')?.focus({preventScroll:true});
}
function leaveFocus(){
  document.body.classList.remove('focus-mode');
  if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});
  updateFullscreenButton();
}
function updateFullscreenButton(){const button=$('[data-action="fullscreen"]');if(button)button.textContent=document.body.classList.contains('focus-mode')?'退出全屏 · Esc':'全屏专注';}
document.addEventListener('fullscreenchange',()=>{if(!document.fullscreenElement)document.body.classList.remove('focus-mode');updateFullscreenButton();$('#answer')?.focus({preventScroll:true});});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('#end-dialog').open&&document.body.classList.contains('focus-mode')){leaveFocus();}});
function renderPractice(){
  if(!session || session.status!=='active')return;
  if(isDictation())return renderDictation();
  route='practice';header();const s=session,c=s.current,view=s.view_position??s.position;
  main.innerHTML=`<div class="practice-top"><div><div class="eyebrow">${s.mode==='review'?'ONE MORE TRY':'FOCUS & GROW'}</div><h2>${esc(s.book.title)}${s.mode==='review'?' · 错词重练':''}</h2><p>${esc(s.book.edition)} · ${s.learning_order==='sequential'?'顺序学习':'随机学习'}</p></div><div class="practice-tools"><button class="secondary" data-action="fullscreen">全屏专注</button><div class="timer" id="timer"><small>剩余时间</small><strong id="time-left">${fmtTime(Math.ceil(clockRemaining))}</strong></div></div></div>
    <div class="progress-head"><span>${s.readonly?'回看':'探险进度'} · 第 ${s.round_number} 轮 · 第 ${s.round_position+1} / ${s.round_total} 词</span><span>累计练习 ${s.position} 次</span></div><div class="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="${s.round_total}" aria-valuenow="${s.round_completed}" aria-label="本轮练习进度"><div class="progress-fill" style="width:${s.round_completed/s.round_total*100}%"></div></div>
    <div class="practice-grid"><section class="card word-card" id="word-card"><div class="word-card-top"><span class="tag">${esc(c.unit)} · 课本 p.${esc(c.page||'—')}</span><button class="audio-button" data-action="replay" ${sound?'':'disabled title="请在设置中开启朗读声音"'}>◖)) 再听一遍</button></div>
    <button class="word-nav previous-word" data-action="previous-word" aria-label="上一个" title="回看上一个，不重复计分" ${view===0?'disabled':''}><span aria-hidden="true">‹</span><b>上一个</b></button><button class="word-nav next-word" data-action="next-word" aria-label="下一个" title="${s.readonly?'查看下一个':'跳过当前词，进入下一个'}"><b>下一个</b><span aria-hidden="true">›</span></button>
    <div class="word" aria-label="${esc(c.masked.replaceAll('_',' 空格 '))}">${[...c.masked].map(ch=>`<span aria-hidden="true" class="letter ${ch==='_'?'':'fixed'} ${ch===' '?'space':''}">${ch==='_'?'':esc(ch)}</span>`).join('')}<input class="word-input" id="answer" form="answer-form" type="text" aria-label="输入缺少的字母" autocomplete="off" autocapitalize="off" spellcheck="false" inputmode="text" maxlength="100" aria-describedby="word-instruction feedback"></div>
    <div class="phonetic" title="${esc(c.phonetic_note||'音标待补充')}"><span lang="en">${esc(c.phonetic||'—')}</span></div><div class="meaning">${esc(c.meaning)}</div>
    <p class="word-instruction sr-only" id="word-instruction">补全 ${c.missing} 个字母，填满自动检查${/[ '\-.…]/.test(c.masked)?'，不用输入空格或标点':''}</p>
    ${c.reveal?`<div class="reveal">参考答案：${esc(c.reveal)}</div>`:''}
    <form class="answer-form" id="answer-form"><div class="feedback" id="feedback" role="status"></div><div class="word-actions" ${s.readonly?'hidden':''}><button class="primary" type="submit" id="check-answer">检查答案 <small>↵</small></button><button class="secondary" type="button" data-action="hint">看提示</button><button class="plain" type="button" data-action="skip">暂时跳过</button></div></form><div class="speech-status sr-only" id="speech-status" role="status"></div></section>
    <aside class="practice-aside"><div class="card streak"><h3>✦ 连续首次答对</h3><strong>${s.streak}<small> 连击</small></strong><p>${s.streak>=5?'状态真不错，保持节奏！':'慢慢来，下一次会更好。'}</p></div><div class="card"><h3>本次收获</h3><strong>${s.stars}<small> 星</small></strong><p>每一个努力都有收获</p></div><div class="card aside-tip"><h3>不用害怕答错</h3><p style="margin-top:10px">答错可以重新输入。看过提示的词会单独记录，下次再独立试一试。</p></div></aside></div>
    <button class="plain end-practice" data-action="end">结束练习并查看报告</button>`;
  window.scrollTo(0,0);$('#answer').disabled=!!s.readonly;if(!s.readonly)$('#answer').focus({preventScroll:true});updateLetters();updateFullscreenButton();
}
function dictationSeconds(){return Math.max(0,Math.ceil((session.current.writing_deadline*1000-Date.now()-serverOffset)/1000));}
function renderDictation(){
  route='practice';header();const s=session,c=s.current,done=c.phase==='result',writing=c.phase==='writing',manual=isManualDictation();
  dictationAdvanceAt=done?Math.min(Date.now()+(c.result==='correct'?650:2000),c.writing_deadline?c.writing_deadline*1000-serverOffset:Infinity):0;
  main.innerHTML=`<div class="practice-top"><div><div class="eyebrow">LISTEN & SPELL</div><h2>${practiceNames[s.practice_type]} · ${esc(s.book.title)}</h2><p>第 ${s.round_number} 轮 · 第 ${s.round_position+1} / ${s.round_total} 词 · ${s.learning_order==='sequential'?'顺序':'随机'}出题</p></div><div class="practice-tools"><button class="secondary" data-action="fullscreen">全屏专注</button><div class="timer"><small>本次剩余</small><strong id="time-left">${fmtTime(Math.ceil(clockRemaining))}</strong></div></div></div>
    <section class="card word-card dictation-card ${done&&c.result==='correct'?'success':''}"><div class="word-card-top"><span class="tag">${practiceNames[s.practice_type]} · ${dictationLabel(s)}</span><button class="audio-button" data-action="replay" ${c.phase!=='listening'?'hidden':''}>◖)) 重新听两遍</button></div>
    <div class="dictation-stage" id="dictation-stage">${done?'本题已交卷':writing?'请写出完整英文单词':'准备听音 · 第一遍结束即可输入'}</div>${manual?'':`<div class="dictation-timer ${writing&&dictationSeconds()<=5?'urgent':''}" id="dictation-timer"><strong id="dictation-left">${done?'✓':writing?dictationSeconds():s.dictation_seconds}</strong><span>${done?'已完成':'秒作答'}</span></div>`}
    <div class="word" aria-label="${c.missing} 个空缺字母">${[...c.masked].map(ch=>`<span aria-hidden="true" class="letter ${ch==='_'?'':'fixed'} ${ch===' '?'space':''}">${ch==='_'?'':esc(ch)}</span>`).join('')}<input class="word-input" id="answer" form="answer-form" type="text" aria-label="输入完整英文单词" autocomplete="off" autocapitalize="off" spellcheck="false" inputmode="text" maxlength="100" aria-describedby="word-instruction feedback" ${writing?'':'readonly'}></div>
    ${done?`<div class="reveal">正确答案：<strong>${esc(c.reveal)}</strong></div><div class="phonetic"><span lang="en">${esc(c.phonetic||'—')}</span></div><div class="meaning">${esc(c.meaning)}</div>`:''}
    <p class="word-instruction" id="word-instruction">${done?(clockRemaining>0?'即将自动进入下一个单词，错词已记录。':'即将自动显示本次听写报告。'):manual?'第一遍读完即可输入，每词不限时；写完按 Enter 提交并进入下一词。':`第一遍读完即可输入，写满自动继续；${s.dictation_seconds} 秒到直接下一词，未写完判错。`}</p>
    <form class="answer-form" id="answer-form"><div class="feedback ${done&&c.result==='correct'?'good':done?'error':''}" id="feedback" role="status">${done?({correct:'答对了！获得 10 颗星星。',wrong:'拼写有误，记住它，下次再试。',timeout:'时间到，未写完按错误记录。'}[c.result]):''}</div><div class="word-actions">${done?`<button type="button" class="primary" data-action="dictation-next" hidden>重试保存</button>`:`<button class="primary" type="submit" id="check-answer" hidden>重试保存</button>`}</div></form><div class="speech-status" id="speech-status" role="status"></div></section>
    <p class="dictation-footer">${manual?'总时间到后，仍可完成当前单词；按 Enter 提交后显示报告。':`总时间到后，仍可完成当前单词的 ${s.dictation_seconds} 秒作答。`}</p><button class="plain end-practice" data-action="end">结束练习并查看报告</button>`;
  const input=$('#answer');input.value=c.draft;input.disabled=done;
  if(!done){input.focus({preventScroll:true});input.setSelectionRange(input.value.length,input.value.length);}
  updateLetters();updateFullscreenButton();
}
function saveDraft(answer){
  const sid=session.id,position=session.position,revision=++draftRevision;
  // Revisions reject out-of-order saves; a stalled draft must never block submission.
  api(`/api/session/${sid}/draft`,{position,answer,revision,request_id:crypto.randomUUID()}).catch(error=>{
    if(session?.id===sid&&session.position===position&&session.current.phase==='writing'&&revision===draftRevision)feedback('草稿暂未保存，请检查连接；提交时会再次尝试保存。','error');
  });
}
function updateLetters(){
  const input=$('#answer');if(!input||!session?.current)return;
  const clean=letters(input.value),start=letters(input.value.slice(0,input.selectionStart)).length,end=letters(input.value.slice(0,input.selectionEnd)).length;
  const blanks=[...main.querySelectorAll('.word .letter:not(.fixed)')];
  blanks.forEach((el,i)=>{el.textContent=clean[i]||'';el.classList.toggle('preview',!!clean[i]);el.classList.toggle('selected-letter',i>=start&&i<end);el.classList.toggle('caret',start===end&&i===Math.min(start,blanks.length-1));el.classList.toggle('caret-end',start>=blanks.length);});
}
document.addEventListener('selectionchange',()=>{if(document.activeElement?.id==='answer')updateLetters();});
function feedback(message,kind=''){const el=$('#feedback');if(el){el.textContent=message;el.className='feedback '+kind;}}
function disableAnswer(disabled){if($('[data-action="end"]'))$('[data-action="end"]').disabled=disabled;main.querySelectorAll('#answer,#answer-form button').forEach(el=>el.disabled=disabled||!!session?.readonly||(isDictation()&&el.id==='check-answer'&&session.current.phase!=='writing'));main.querySelectorAll('.word-nav').forEach(el=>el.disabled=disabled||(el.dataset.action==='previous-word'&&(session.view_position??session.position)===0));}
async function act(action, answer){
  if(busy || !session || session.status!=='active')return;
  if(session.readonly&&action!=='finish')return;
  if(action==='answer'&&!pending&&!isDictation()&&!letters(answer||'')){feedback('请输入缺少的英文字母','error');return;}
  busy=true;disableAnswer(true);
  const operation=pending || {action,body:{position:session.position,answer:answer||'',request_id:crypto.randomUUID()}};
  try{
    const result=await api(`/api/session/${session.id}/${operation.action}`,operation.body);pending=null;sync(result.session);
    if(isDictation()){
      stopVoice();if(route!=='practice')return;
      if(session.status==='active'){renderPractice();if(session.current.phase==='listening')speakCurrent();}else await showReport(session.id);
    }else if(result.correct || operation.action==='skip'){
      stopVoice();const card=$('#word-card');if(card&&result.correct)card.classList.add('success');
      feedback(result.correct?`答对了！ ${result.reveal}${session.streak>=5?' · '+session.streak+' 连击！':''}`:`记住它：${result.reveal}`,result.correct?'good':'');
      await new Promise(resolve=>setTimeout(resolve,650));
      if(route!=='practice')return;
      if(session.status==='active'){renderPractice();speakCurrent();}else await showReport(session.id);
    }else if(session.status!=='active'){await showReport(session.id);}
    else if(operation.action==='hint'){renderPractice();}
    else{const card=$('#word-card');if(card)card.classList.add('incorrect');feedback(`还差一点，第 ${result.attempt} 次未答对。重新试一次吧。`,'error');disableAnswer(false);$('#answer')?.focus();$('#answer')?.select();}
  }catch(error){
    if(!error.status || error.status>=500){pending=operation;feedback('暂未确认保存。点击“重试保存”继续，不会重复计分。','error');const button=$('#check-answer')||$('[data-action="dictation-next"]');if(button){button.hidden=false;button.disabled=false;button.textContent='重试保存';}}
    else if(error.status===400&&error.message.includes('题目已变化')){
      pending=null;sync(await api(`/api/session/${session.id}`));
      if(session.status==='active'){renderPractice();speakCurrent();toast('已同步另一窗口的最新进度');}else await showReport(session.id);
    }else{feedback(error.message,'error');disableAnswer(false);toast(error.message);}
  }finally{busy=false;}
}
function stopVoice(){voiceToken++;dictationSubmitQueued=false;speechAbort?.abort();if(player){player.pause();player=null;}if(audioDone){audioDone();audioDone=null;}window.speechSynthesis?.cancel();}
async function browserVoice(lang,token){
  for(let i=0;i<30&&token===voiceToken;i++){
    const selected=speechSynthesis.getVoices().find(v=>v.lang.toLowerCase().startsWith(lang.slice(0,2).toLowerCase()));
    if(selected)return selected;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
}
async function speakCurrent(){
  stopVoice();const dictation=isDictation();if((!sound&&!dictation)||route!=='practice'||!session?.current||(dictation&&session.current.phase!=='listening'))return;
  const token=voiceToken,wordId=session.current.word_id,sid=session.id,position=session.position;speechAbort=new AbortController();
  try{
    const languages=dictation?Array(2).fill(session.practice_type==='dictation_en'?'en':'zh'):['en','zh'];
    for(const [index,lang] of languages.entries()){
      if(token!==voiceToken)return;
      if(dictation&&index)await new Promise(resolve=>setTimeout(resolve,800));
      if(token!==voiceToken)return;
      const status=dictation?`正在朗读第 ${index+1} / 2 遍…`:(lang==='en'?'正在朗读英文…':'正在朗读中文…');
      if($('#speech-status')){$('#speech-status').classList.toggle('sr-only',!dictation);$('#speech-status').textContent=status;}
      if(dictation&&$('#dictation-stage'))$('#dictation-stage').textContent=status;
      const response=await fetch(`/api/audio/${wordId}?lang=${lang}${dictation?'&dictation=1':''}`,{signal:speechAbort.signal});
      if(!response.ok)throw new Error('语音未能播放，请点击“再听一遍”重试');
      if(response.headers.get('Content-Type').includes('application/json')){
        const voice=await response.json();if(token!==voiceToken)return;
        if(!window.speechSynthesis)throw new Error('当前浏览器没有语音功能，请更换浏览器');
        const selected=await browserVoice(voice.lang,token);if(token!==voiceToken)return;
        if(!selected)throw new Error('未找到'+(lang==='en'?'英文':'中文')+'语音，请在系统中安装对应语音');
        try{await new Promise((resolve,reject)=>{audioDone=resolve;const speech=new SpeechSynthesisUtterance(voice.text);speech.lang=voice.lang;speech.voice=selected;speech.rate=speechRate;speech.onend=resolve;speech.onerror=()=>reject(new Error('朗读未完成，请重播'));speechSynthesis.speak(speech);});}finally{if(token===voiceToken)audioDone=null;}
      }else{
        const blob=await response.blob();if(token!==voiceToken)return;
        const url=URL.createObjectURL(blob);player=new Audio(url);player.playbackRate=speechRate;player.preservesPitch=true;
        try{await new Promise((resolve,reject)=>{audioDone=resolve;player.onended=resolve;player.onerror=()=>reject(new Error('语音播放失败，请重试'));player.play().catch(()=>reject(new Error('点击“再听一遍”启用语音')));});}
        finally{URL.revokeObjectURL(url);if(token===voiceToken)audioDone=null;}
      }
      if(dictation&&index===0&&token===voiceToken&&$('#answer')){
        $('#answer').readOnly=false;$('#answer').focus({preventScroll:true});updateLetters();
        feedback(isManualDictation()?'第一遍已读完，可以输入；写完按 Enter 提交。':'第一遍已读完，可以输入；第二遍结束后开始倒计时。');
      }
    }
    if(token!==voiceToken)return;
    if(dictation){
      const result=await api(`/api/session/${sid}/ready`,{position,request_id:crypto.randomUUID()});
      if(token!==voiceToken||route!=='practice')return;
      const input=$('#answer'),draft=input.value,start=input.selectionStart,end=input.selectionEnd;
      sync(result.session);renderPractice();
      if(session.current?.phase==='writing'){
        $('#answer').value=draft;$('#answer').setSelectionRange(start,end);updateLetters();
        if(dictationSubmitQueued||(!isManualDictation()&&letters(draft).length===session.current.missing)){dictationSubmitQueued=false;act('answer',draft);}
      }
    }else if($('#speech-status'))$('#speech-status').textContent=data.native_voice?'本机中英文合成语音 · 可离线播放':'浏览器中英文合成语音';
  }catch(error){if(token===voiceToken&&error.name!=='AbortError'&&$('#speech-status')){$('#speech-status').textContent=error.message;$('#speech-status').classList.remove('sr-only');}}
}
async function showReport(id){
  leaveFocus();stopVoice();const report=await api(`/api/session/${id}/report`);currentReport=report;route='report';await refresh();header();
  window.scrollTo(0,0);
  const r=report,dictation=r.practice_type!=='hint';const title=r.status==='completed'?'太棒了，本轮全部完成！':r.status==='timeout'?'时间到，收好你的进步！':'今天的努力，已被记住。';
  main.innerHTML=`<section class="card report-hero"><div><div class="eyebrow">YOUR ADVENTURE REPORT</div><h1>${title}</h1><p>${esc(r.book.title)} · ${practiceNames[r.practice_type]}${dictation?' · '+dictationLabel(r):''} · ${Math.floor(r.elapsed/60)} 分 ${r.elapsed%60} 秒 · ${date(r.started)}</p></div><div class="report-award"><strong>✦ ${r.stars}</strong><small>本次获得星星</small></div></section>
    ${dictation?`<div class="report-metrics"><div class="card metric"><strong>${pct(r.dictation_correct,r.practice_completed)}</strong><p>本次听写正确率</p><small>${r.dictation_correct} 次正确 / ${r.practice_completed} 次交卷，含超时</small></div><div class="card metric"><strong>${r.dictation_correct}</strong><p>听写正确</p><small>每词仅交卷一次</small></div><div class="card metric"><strong>${r.dictation_wrong}</strong><p>拼写错误</p><small>不含超时答错</small></div><div class="card metric"><strong>${r.dictation_timeout}</strong><p>超时答错</p><small>${r.dictation_mode==='manual'?'手动模式不计超时':r.dictation_seconds+' 秒内未写完'}</small></div></div>`:`<div class="report-metrics"><div class="card metric"><strong>${pct(r.first_correct,r.attempted)}</strong><p>首轮首次独立正确率</p><small>${r.first_correct} 个首次答对 / ${r.attempted} 个已提交</small></div><div class="card metric"><strong>${pct(r.second_correct,r.first_wrong)}</strong><p>首轮二次纠正率</p><small>${r.second_correct} 个第二次答对 / ${r.first_wrong} 个首次答错</small></div><div class="card metric"><strong>${r.solved}<small style="display:inline;font-size:16px"> / ${r.total}</small></strong><p>成功拼出的单词</p><small>跨轮去重，含提示后答对</small></div><div class="card metric"><strong>${r.best_streak}</strong><p>最高连续首次答对</p><small>${r.best_streak>=5?'获得「连击小能手」徽章 ✦':'下一次，挑战自己的纪录'}</small></div></div>`}
    <section class="card"><div class="word-list-title"><h2>每一步，都看得见</h2><button class="plain" data-action="export-report">导出学习报告 ↓</button></div>${dictation?`<div class="report-breakdown"><span>完成 <b>${r.rounds_completed}</b> 轮</span><span>首轮正确率 <b>${pct(r.first_correct,r.attempted)}</b></span><span>首轮交卷 <b>${r.attempted}</b> 次</span><span>未练习 <b>${r.remaining}</b> 词</span><span>本次交卷 <b>${r.practice_completed}</b> 次</span></div>`:`<div class="report-breakdown"><span>完成 <b>${r.rounds_completed}</b> 轮</span><span>累计练习 <b>${r.practice_completed}</b> 次</span><span>巩固答对 <b>${r.reinforcement_solved}</b> 次</span><span>首轮首次答对 <b>${r.first_correct}</b></span><span>首轮二次答对 <b>${r.second_correct}</b></span><span>首轮提示 <b>${r.hinted}</b></span><span>首轮跳过 <b>${r.skipped}</b></span><span>首轮未完成 <b>${r.remaining}</b></span></div>`}
    <div class="table-wrap"><table><thead><tr><th>轮次</th><th>单词与释义</th><th>输入记录</th><th>学习结果</th></tr></thead><tbody>${r.words.map(w=>`<tr><td>第 ${w.round_number} 轮</td><td><strong>${esc(w.english)}</strong><small>${esc(w.meaning)}</small></td><td>${w.attempts.length?w.attempts.map(a=>`<small>${a.number}. ${esc(a.answer)} ${a.correct?'✓':'×'}${a.hinted?'（已提示）':''}</small>`).join(''):'—'}</td><td>${wordResult(w)}</td></tr>`).join('')}</tbody></table></div>
    ${dictation?`<details><summary>听写统计说明</summary><p>本次听写正确率按全部轮次的交卷次数计算，超时也计一次交卷；首轮正确率单独保留。每词只判分一次；${r.dictation_mode==='manual'?'手动模式无每词倒计时，按 Enter 交卷，空白或拼写不完整记为“拼写错误”。':`${r.dictation_seconds} 秒到时按已保存的输入自动交卷，字母未写完记为“超时答错”，完整但错误记为“拼写错误”。`}大小写、空格和标点不影响判分。听写正确得 10 星；提示拼写的成绩不会改写听写记录。</p></details>`:`<details><summary>统计是怎样计算的？</summary><p>正确率、提示、跳过及未完成仅统计第一轮，后续巩固不会改写首轮结果。累计练习包含答对与跳过，巩固答对按第二轮起的答对次数统计。首轮首次独立正确率 = 未使用提示、第一次就答对的词数 ÷ 有过提交的词数。首轮二次纠正率 = 未使用提示、恰好第二次答对的词数 ÷ 第一次提交错误的词数。两次内独立掌握率为 ${pct(r.first_correct+r.second_correct,r.attempted)}。没有分母时显示“—”。使用提示不计入独立答对；未完成与跳过单独列出。每次填满或按 Enter 检查算一次提交。首次答对得 10 星、第二次 6 星、更多次 4 星、提示后 2 星。星星用于鼓励，不替代正确率。</p></details>`}</section>
    <div class="report-controls"><button class="secondary" data-action="home">回到出发地</button><div class="button-row"><button class="secondary" data-action="review" data-book="${esc(r.book.id)}">再练错词</button><button class="primary" data-action="again" data-book="${esc(r.book.id)}">再来一轮 →</button></div></div>`;
}
function wordResult(w){if(w.result)return `<span class="result-pill ${w.result==='correct'?'':'warn'}">${{correct:'听写正确',wrong:'拼写错误',timeout:'超时答错'}[w.result]}</span>`;if(w.skipped)return '<span class="result-pill neutral">已跳过</span>';if(!w.solved)return `<span class="result-pill neutral">${w.tries?'尚未答对':'未练习'}</span>`;if(w.hinted)return '<span class="result-pill warn">提示后答对</span>';return `<span class="result-pill ${w.tries>1?'warn':''}">${w.tries===1?'首次答对':w.tries===2?'二次答对':w.tries+' 次后答对'}</span>`;}
function renderHistory(){
  const history=data.history;main.innerHTML=`<div class="page-heading"><div><div class="eyebrow">LITTLE STEPS, BIG GROWTH</div><h1>你的学习足迹</h1><p>努力留下的痕迹，都在这里。</p></div><span class="tag">已完成 ${data.summary.sessions} 次练习</span></div>`;
  if(!history.length){main.innerHTML+='<div class="card empty"><span class="empty-icon">▥</span><h2>第一步，从今天开始</h2><p>完成一次练习，就能看到自己的进步。</p><button class="primary" data-action="home">开始第一场探险</button></div>';return;}
  const recent=history.slice(0,8).reverse();const max=Math.max(1,...recent.map(r=>r.solved));
  main.innerHTML+=`<section class="card"><h3>最近 ${recent.length} 次 · 成功拼写词数</h3><div class="history-chart" aria-label="近期完成单词数量">${recent.map(r=>`<div class="chart-column"><span>${r.solved}</span><div class="bar" style="height:${r.solved/max*90}px"></div><small>${new Date(r.started*1000).toLocaleDateString('zh-CN',{month:'numeric',day:'numeric'})}</small></div>`).join('')}</div><div class="table-wrap"><table><thead><tr><th>练习时间 / 教材</th><th>首轮首次正确率</th><th>收获</th><th></th></tr></thead><tbody>${history.map(r=>`<tr><td><strong>${date(r.started)}</strong><small>${esc(r.book.title)} · ${practiceNames[r.practice_type]}${r.mode==='review'?' · 错词重练':''}</small></td><td>${pct(r.first_correct,r.attempted)}</td><td>${r.solved} 词 · ${r.stars} 星</td><td><button class="plain" data-report="${r.id}">看报告 →</button></td></tr>`).join('')}</tbody></table></div></section>`;
}
const samePrize=(a,b)=>['name','icon','detail'].every(key=>a?.[key]===b?.[key]);
function prizeWheel(prizes, index=0){
  const colors=['#e2eeff','#e3f3e9','#fff0dd','#f4e6fa','#def2f5','#fff2cc','#eae6fc','#fbe4ea'];
  return `<div class="wheel-stage"><span class="wheel-pointer" aria-hidden="true">▼</span><svg id="prize-wheel" viewBox="0 0 400 400" role="img" aria-label="八种亲子活动，每种中奖机会相同" style="transform:rotate(${-index*45}deg)"><circle cx="200" cy="200" r="191" fill="none" stroke="#d3e2f4" stroke-width="10"/>${prizes.map((p,i)=>`<g transform="rotate(${i*45} 200 200)" data-prize-index="${i}"><path d="M200 200 L129.59 30 A184 184 0 0 1 270.41 30 Z" fill="${colors[i]}" stroke="white" stroke-width="2"/><text x="200" y="64" text-anchor="middle" font-size="25">${esc(p.icon)}</text><text x="200" y="91" text-anchor="middle" font-size="13" font-weight="600" fill="#263b53"><title>${esc(p.name)}</title>${[Array.from(p.name).slice(0,6).join(''),Array.from(p.name).slice(6).join('')].filter(Boolean).map((line,n)=>`<tspan x="200" dy="${n?16:0}">${esc(line)}</tspan>`).join('')}</text></g>`).join('')}</svg><div class="wheel-hub" aria-hidden="true"><span>✦</span><small>一起的时光</small></div></div>`;
}
async function renderRewards(wonId){
  const r=await api('/api/rewards');if(route!=='rewards')return;
  let pendingId='';try{pendingId=localStorage.getItem('word-isle-pending-draw')||'';}catch{}
  if(pendingId&&r.draws.some(d=>d.id===pendingId)){wonId=pendingId;localStorage.removeItem('word-isle-pending-draw');pendingId='';}
  const prize=r.draws.find(d=>d.id===wonId)||r.draws[0],canDraw=r.wallet.available>=r.cost;
  main.innerHTML=`<div class="page-heading reward-heading"><div><h1>亲子幸运转盘</h1><p>把每一点努力，变成和家人一起的美好时光。</p></div><button class="secondary" data-action="home">返回首页</button></div>
    <div class="reward-layout"><section class="card wheel-card"><span class="tag gold">每次 ${r.cost} 星 · 每次都有惊喜</span>${prizeWheel(r.prizes,prize&&samePrize(r.prizes[prize.prize_index],prize.prize)?prize.prize_index:0)}<button id="spin-reward" data-revision="${esc(r.revision)}" class="primary spin-button" data-action="spin-reward" ${rewardBusy||(!canDraw&&!pendingId)?'disabled':''}>${pendingId?'重试抽奖结果':`${r.cost} 星 · 转一次`}</button><p class="wheel-note" id="wheel-status" role="status">${pendingId?'有一份结果待确认，重试不会重复扣星。':canDraw?'8 种活动等概率，每种 12.5%':'还差 '+(r.cost-r.wallet.available)+' 星，学习后再来吧'}</p></section>
    <aside class="reward-side"><section class="card star-wallet"><span>我的可用星星</span><strong id="available-stars">✦ ${r.wallet.available}</strong><div><span>累计获得 <b>${r.wallet.earned}</b></span><span>已经使用 <b>${r.wallet.spent}</b></span></div></section><section class="card prize-result" id="prize-result" role="status">${prize?`<span class="prize-emoji" aria-hidden="true">${esc(prize.prize.icon)}</span><span class="eyebrow">${wonId?'这次的亲子惊喜':'最近抽到的活动'}</span><h2>${esc(prize.prize.name)}</h2><p>${esc(prize.prize.detail)}</p><span class="tag ${prize.redeemed_at?'':'gold'}">${prize.redeemed_at?'已一起完成':'已存入我的奖品'}</span>`:'<span class="prize-emoji" aria-hidden="true">🎁</span><h2>下一份惊喜，是陪伴</h2><p>和家人约好时间，一起把抽到的活动变成美好的回忆。</p>'}</section></aside></div>
    <section class="reward-history"><div class="word-list-title"><h2>我的奖品 <span class="count-label">${r.draws.filter(d=>!d.redeemed_at).length} 份待使用</span></h2></div>${r.draws.length?`<div class="prize-grid">${r.draws.map(d=>`<article class="card prize-ticket" data-reward-id="${esc(d.id)}"><div class="ticket-heading"><span aria-hidden="true">${esc(d.prize.icon)}</span><div><h3>${esc(d.prize.name)}</h3><small>${date(d.created_at)} · ${d.cost} 星</small></div></div><p>${esc(d.prize.detail)}</p>${d.redeemed_at?`<span class="redeemed">✓ 已一起完成 · ${date(d.redeemed_at)}</span>`:`<button class="secondary" data-redeem="${esc(d.id)}" ${rewardBusy?'disabled':''}>标记已完成</button>`}</article>`).join('')}</div>`:'<div class="card reward-empty">还没有奖品，第一份亲子时光等着你。</div>'}</section>
    <details class="reward-rules"><summary>活动清单与规则</summary><p>每次抽奖消耗 ${r.cost} 星，不影响累计获得的星星。八种活动等概率，每次必得一份活动；可以重复抽到，分别保留。与家人一起完成活动后，在奖品卡上标记已完成。</p><ul>${r.prizes.map(p=>`<li><strong>${esc(p.name)}</strong>：${esc(p.detail)}</li>`).join('')}</ul></details>`;
}
async function spinReward(){
  if(rewardBusy)return;rewardBusy=true;
  const button=$('#spin-reward');if(button)button.disabled=true;
  let wonId;
  try{
    const id=localStorage.getItem('word-isle-pending-draw')||crypto.randomUUID();
    localStorage.setItem('word-isle-pending-draw',id);
    const result=await api('/api/rewards/draw',{request_id:id,config_revision:button.dataset.revision});
    localStorage.removeItem('word-isle-pending-draw');wonId=result.draw.id;
    if(route==='rewards'){
      $('#available-stars').textContent='✦ '+result.wallet.available;
      $('#wheel-status').textContent='正在揭晓这份亲子惊喜…';
      const wheel=$('#prize-wheel'),from=parseFloat(wheel.style.transform.match(/-?[\d.]+/)[0]);
      const to=from+1800+((-result.draw.prize_index*45-from)%360+360)%360;
      if(result.config.revision===button.dataset.revision&&samePrize(result.config.prizes[result.draw.prize_index],result.draw.prize)&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
        const animation=wheel.animate([{transform:`rotate(${from}deg)`},{transform:`rotate(${to}deg)`}],{duration:3800,easing:'cubic-bezier(.15,.8,.18,1)',fill:'forwards'});
        await animation.finished;
      }
    }
  }catch(error){
    if(error.status&&error.status<500)localStorage.removeItem('word-isle-pending-draw');
    toast(error.status?error.message:'暂未确认抽奖结果，重试或重新打开转盘可恢复，不会重复扣星。');
  }finally{
    rewardBusy=false;
    if(route==='rewards')try{await renderRewards(wonId);}catch{if(button?.isConnected){button.disabled=false;button.textContent='重试抽奖结果';}}
  }
}
async function redeemReward(id){
  if(rewardBusy)return;rewardBusy=true;
  try{await api('/api/rewards/'+encodeURIComponent(id)+'/redeem',{});toast('已记下这次美好的亲子时光。');}
  catch(error){toast(error.message);}
  finally{rewardBusy=false;if(route==='rewards')await renderRewards();}
}
async function renderCompleted(scope){
  const result=await api('/api/completed-words?scope='+scope),today=scope==='today';
  if(route!==(today?'today':'completed'))return;
  const title=today?'今日已完成':'累计已完成';
  const learnedAt=value=>new Date(value*1000).toLocaleString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
  main.innerHTML=`<div class="page-heading"><div><h1>${title}</h1><p>${result.total} 个单词 · ${today?'今日':'累计'}成功拼写 ${result.words.reduce((sum,w)=>sum+w.frequency,0)} 次</p></div><button class="secondary" data-action="home">返回首页</button></div><div class="completed-tabs button-row"><button class="${today?'secondary':'primary'}" data-action="completed" aria-pressed="${!today}">累计已完成</button><button class="${today?'primary':'secondary'}" data-action="today" aria-pressed="${today}">今日已完成</button></div>`;
  if(!result.words.length){main.innerHTML+=`<section class="card empty completed-empty"><h2>${today?'今天还没有完成的单词':'还没有完成的单词'}</h2><p>成功拼写后，单词会自动记录在这里。</p><button class="primary" data-action="home">去学习</button></section>`;return;}
  main.innerHTML+=`<section class="card completed-card"><div class="table-wrap completed-scroll" tabindex="0" role="region" aria-label="已完成单词学习明细，可横向滚动"><table class="completed-table"><thead><tr><th>最近学习日期</th><th>单词</th><th>音标</th><th>中文</th><th>所属单元</th><th title="当前范围内成功拼写的次数，重复提交不重复计次">学习频次</th><th>所属学期</th><th>所属年级</th><th>所属教材</th><th>所属地区</th></tr></thead>${result.words.map(w=>`<tbody>${w.sources.map((s,index)=>`<tr><td>${esc(learnedAt(s.completed_at))}</td>${index===0?`<th scope="rowgroup" rowspan="${w.sources.length}">${esc(w.english)}</th>`:''}<td class="word-phonetic" lang="en">${esc(s.phonetic||'—')}</td><td>${esc(s.meaning)}</td><td>${esc(s.unit)}</td>${index===0?`<td class="word-frequency" rowspan="${w.sources.length}">${w.frequency} 次</td>`:''}<td>${esc(s.term)}册</td><td>${esc(gradeName(s.grade))}</td><td>${esc(s.book)}<small>${esc(s.publisher)} · ${esc(s.edition)}</small></td><td>${esc(s.province||'未设置')}</td></tr>`).join('')}</tbody>`).join('')}</table></div><details><summary>统计说明</summary><p>相同英文拼写只计一个单词，忽略大小写和多余空格。学习频次为当前范围内成功拼写的次数，包含提示后答对；答错、跳过和重复提交不增加完成次数。今日按实际答对日期计算，也包含尚未结束的练习。相同单词的不同教材、单元和学习地区分别展示最近完成时间与出处，频次合并显示。</p></details></section>`;
}
async function renderMistakes(bookId){
  const words=await api('/api/mistakes');const books=data.books.filter(b=>words.some(w=>w.book_id===b.id));const selected=bookId||books[0]?.id;const filtered=words.filter(w=>w.book_id===selected);
  main.innerHTML=`<div class="page-heading"><div><div class="eyebrow">TRY AGAIN, GROW AGAIN</div><h1>错词巩固</h1><p>按出错的练习方式再答对一次，就能消除该方式的错词记录。</p></div><span class="tag">${words.length} 个词等待复习</span></div>`;
  if(!words.length){main.innerHTML+='<div class="card empty"><span class="empty-icon">✧</span><h2>暂时没有需要巩固的单词</h2><p>练习中答错、跳过或看提示的词会留在这里。</p><button class="primary" data-action="home">去探索新单词</button></div>';return;}
  main.innerHTML+=`<section class="card"><div class="filter-row"><label for="review-book" class="sr-only">选择复习课本</label><select id="review-book">${books.map(b=>`<option value="${esc(b.id)}" ${b.id===selected?'selected':''}>${esc(b.title)}</option>`).join('')}</select><span class="count-label">${filtered.length} 个词</span><select id="review-practice" aria-label="错词练习方式">${Object.entries(practiceNames).map(([value,title])=>`<option value="${value}" ${value===prefs.practiceType?'selected':''}>${title}</option>`).join('')}</select><button class="primary" data-action="review" data-book="${esc(selected)}">开始错词重练</button></div><div class="table-wrap"><table><thead><tr><th>单词</th><th>中文</th><th>来自 / 待巩固方式</th></tr></thead><tbody>${filtered.map(w=>`<tr><td><strong>${esc(w.english)}</strong></td><td>${esc(w.meaning)}</td><td>${esc(w.unit)}<small>${w.practice_types.split(',').map(t=>practiceNames[t]).join(' · ')}</small></td></tr>`).join('')}</tbody></table></div></section>`;
}
function renderLibrary(){
  main.innerHTML=`<div class="page-heading"><div><div class="eyebrow">YOUR BOOKSHELF</div><h1>我的词库</h1><p>${data.books.length} 册教材 · ${data.books.reduce((n,b)=>n+b.count,0)} 个词条与短语</p></div><span class="tag">${data.cloud?'账号独立保存，跨设备练习':'本机保存，随时练习'}</span></div>
    <section class="upload"><div><h3>把你的课本，也带进词屿</h3><p>可导入其他出版社、年级和学期的 JSON 词库。先下载模板填写，导入前请核对内容和来源。</p></div><div class="button-row"><button class="secondary" data-action="template">下载模板</button><button class="primary" data-action="import">导入词库</button><input type="file" id="import-file" accept=".json,application/json" hidden></div></section>
    <div class="library-grid">${data.books.map(b=>`<article class="card library-card"><div class="book-line"><span class="tag">${esc(b.publisher)}</span><span class="book-number">${b.grade}</span></div><h2>${esc(b.title)}</h2><p>${esc(b.edition)}<br>${b.units.length} 个练习分组 · ${b.count} 个词条</p><div class="button-row"><button class="secondary" data-vocabulary="${esc(b.id)}">查看词表</button><button class="plain" data-choose="${esc(b.id)}">选这本练习 →</button><a href="${esc(b.source_url)}" target="_blank" rel="noreferrer" class="small">教材来源 ↗</a></div><details><summary>版本说明</summary><p>${esc(b.source_note)}</p></details></article>`).join('')}</div>
    <div class="sources-note">内置词库分别保留 ChinaTextbook 存档版与人教社官网版，可在出版社选项中切换。官网同时收录部分旧版，请核对册次与版本说明。其他地区的推荐尚需按学校核实；导入的地区标签由词库提供者填写。</div>`;
}
async function vocabulary(id){const book=data.books.find(b=>b.id===id),words=await api('/api/words?book_id='+encodeURIComponent(id));route='vocabulary';header();main.innerHTML=`<div class="page-heading"><div><h1>${esc(book.title)}</h1><p>${words.length} 个词条 · ${esc(book.edition)}</p></div><button class="secondary" data-action="library">返回词库</button></div><div class="card table-wrap"><table><thead><tr><th>单词</th><th>释义</th><th>单元 / 页码</th></tr></thead><tbody>${words.map(w=>`<tr><td><strong>${esc(w.english)}</strong></td><td>${esc(w.meaning)}</td><td>${esc(w.unit)} · ${esc(w.page)}</td></tr>`).join('')}</tbody></table></div>`;}
function download(name,text,type='application/json'){if(window.wordIsleDesktop){window.webkit.messageHandlers.download.postMessage({name,text});return;}const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function exportReport(){
  const r=currentReport,dictation=r.practice_type!=='hint',quote=x=>`"${String(x).replace(/^[=+@-]/,"'$&").replaceAll('"','""')}"`;
  const rows=[['词屿学习报告',r.book.title,date(r.started)],['练习方式',practiceNames[r.practice_type]],['首轮首次独立正确率',pct(r.first_correct,r.attempted)],
    ...(dictation?[['听写设置',dictationLabel(r)],['本次听写正确率',pct(r.dictation_correct,r.practice_completed)],['听写正确',r.dictation_correct],['拼写错误',r.dictation_wrong],['超时答错',r.dictation_timeout]]:[['首轮二次纠正率',pct(r.second_correct,r.first_wrong)]]),
    ['完成轮数',r.rounds_completed],['累计练习次数',r.practice_completed],['巩固答对次数',r.reinforcement_solved],['轮次','单词','中文','提交次数','使用提示','答对','跳过','听写结果','输入记录'],
    ...r.words.map(w=>[w.round_number,w.english,w.meaning,w.tries,w.hinted?'是':'否',w.solved?'是':'否',w.skipped?'是':'否',({correct:'听写正确',wrong:'拼写错误',timeout:'超时答错'}[w.result]||''),w.attempts.map(a=>`${a.number}:${a.answer}(${a.correct?'对':'错'})`).join(' | ')])];
  download('词屿学习报告-'+r.id.slice(0,6)+'.csv','\ufeff'+rows.map(row=>row.map(quote).join(',')).join('\r\n'),'text/csv;charset=utf-8');
}

document.querySelectorAll('[data-nav]').forEach(button=>button.addEventListener('click',()=>navigate(button.dataset.nav)));
$('.brand').addEventListener('click',event=>{event.preventDefault();navigate('home');});
main.addEventListener('submit',event=>{
  if(event.target.id==='prize-settings-form'){event.preventDefault();savePrizeSettings(event.target);return;}
  if(event.target.id!=='answer-form')return;
  event.preventDefault();const input=$('#answer');
  if(pending)return act('answer',input?.value||'');
  if(isDictation()){
    if(input.readOnly||input.disabled||session.current.phase==='result')return;
    if(session.current.phase==='listening'){
      dictationSubmitQueued=true;input.readOnly=true;feedback('已确认作答，第二遍朗读结束后提交并进入下一词。');return;
    }
  }
  act('answer',input?.value||'');
});
main.addEventListener('input',event=>{
  if(event.target.closest('#prize-settings-form'))$('#prize-save-status').textContent='有未保存的修改，离开前请保存。';
  if(event.target.id==='answer'&&!event.isComposing&&!busy&&!pending){
    const value=event.target.value,clean=letters(value);updateLetters();
    if(isDictation()){
      if(event.target.readOnly||(!isManualDictation()&&session.current.phase==='writing'&&!dictationSeconds()))return;
      if(/[^a-zA-Z '\-.]/.test(value)){feedback('请切换为英文输入法，输入完整英文单词。','error');return;}
      saveDraft(value);
      if(isManualDictation()){feedback(clean.length>session.current.missing?'字母数量超出，请删除多余字母。':'填写后可修改，按 Enter 提交并进入下一词。');return;}
      if(clean.length===session.current.missing){
        if(session.current.phase==='writing')act('answer',value);
        else feedback('已写满，第二遍朗读结束后自动检查。');
      }
      else feedback(clean.length>session.current.missing?'字母数量超出，请删除多余字母。':'继续填写，写满自动检查。');
      return;
    }
    if(/[^a-zA-Z '\-.]/.test(value)){feedback('请切换为英文输入法，只输入缺少的字母','error');return;}
    if(clean.length===session.current.missing)act('answer',value);
    else if(clean.length>session.current.missing)feedback(`只需要补全 ${session.current.missing} 个字母，不用输入已显示的部分。`,'error');
  }
});
main.addEventListener('compositionend',event=>{if(event.target.id==='answer')event.target.dispatchEvent(new Event('input',{bubbles:true}));});
main.addEventListener('change',async event=>{
  const el=event.target,book=chooseBook();
  if(el.closest('#prize-settings-form')&&el.name.startsWith('icon-')){
    const option=el.selectedOptions[0],index=el.name.slice(5);
    $('#prize-name-'+index).value=option.dataset.name;$('#prize-detail-'+index).value=option.dataset.detail;
    $('#prize-save-status').textContent='已按图标填写活动，请保存奖品设置。';
  }
  if(['province','publisher','grade','book','unit'].includes(el.id)){
    if(el.id==='province'){locationRevision++;prefs.province=el.value;const b=recommendedBook(el.value);if(b)prefs.book=b.id;}
    if(el.id==='publisher')prefs.book=(data.books.find(b=>b.publisher===el.value&&b.grade===book.grade&&b.term===book.term)||data.books.find(b=>b.publisher===el.value&&b.grade===book.grade)||data.books.find(b=>b.publisher===el.value)).id;
    if(el.id==='grade')prefs.book=(data.books.find(b=>b.publisher===book.publisher&&b.grade===Number(el.value)&&b.term===book.term)||data.books.find(b=>b.publisher===book.publisher&&b.grade===Number(el.value))).id;
    if(el.id==='book')prefs.book=el.value;
    prefs.unit=el.id==='unit'?el.value:'';savePrefs();renderHome();
  }
  if(el.id==='custom-minutes'){prefs.minutes=Number(el.value);savePrefs();}
  if(el.id==='speech-rate'){speechRate=Number(el.value);prefs.speechRate=speechRate;savePrefs();if(sound)speakCurrent();$('#answer')?.focus({preventScroll:true});}
  if(el.id==='setting-sound'){sound=el.checked;prefs.sound=sound;savePrefs();if(!sound)stopVoice();}
  if(el.id==='dictation-mode'){
    prefs.dictationMode=el.value;savePrefs();$('#dictation-duration-row').hidden=el.value==='manual';
    $('#dictation-seconds').value=prefs.dictationSeconds;$('#dictation-setting-note').textContent=dictationSettingNote();
  }
  if(el.id==='dictation-seconds'){
    if(!el.checkValidity()){el.reportValidity();toast('请输入 1–300 秒的整数；本次无效输入未保存。');return;}
    prefs.dictationSeconds=Number(el.value);savePrefs();
  }
  if(el.id==='review-practice'){prefs.practiceType=el.value;savePrefs();}
  if(el.id==='review-book')renderMistakes(el.value).catch(e=>toast(e.message));
  if(el.id==='import-file'&&el.files[0]){try{const file=el.files[0];if(file.size>2000000)throw new Error('词库文件须小于 2 MB');const result=await api('/api/import',JSON.parse(await file.text()));await refresh();renderLibrary();toast(`已导入 ${result.title}，共 ${result.count} 个词条`);}catch(error){toast('导入失败：'+error.message);el.value='';}}
});
main.addEventListener('click',async event=>{
  if(event.target.closest('.word')&&$('#answer')&&!$('#answer').disabled){
    const input=$('#answer'),blank=event.target.closest('.letter:not(.fixed)'),blanks=[...main.querySelectorAll('.word .letter:not(.fixed)')];
    input.focus({preventScroll:true});if(blank){const index=Math.min(blanks.indexOf(blank),input.value.length);input.setSelectionRange(index,index);}updateLetters();return;
  }
  const button=event.target.closest('button');if(!button||button.disabled)return;
  try{
    if(button.dataset.practice){prefs.practiceType=button.dataset.practice;savePrefs();renderHome();return;}
    if(button.dataset.order){prefs.learningOrder=button.dataset.order;savePrefs();renderHome();return;}
    if(button.dataset.minutes){prefs.customTime=button.dataset.minutes==='custom';if(!prefs.customTime)prefs.minutes=Number(button.dataset.minutes);savePrefs();renderHome();if(prefs.customTime)$('#custom-minutes')?.focus();return;}
    if(button.dataset.report)return await showReport(button.dataset.report);
    if(button.dataset.vocabulary)return await vocabulary(button.dataset.vocabulary);
    if(button.dataset.redeem)return await redeemReward(button.dataset.redeem);
    if(button.dataset.choose){prefs.book=button.dataset.choose;prefs.unit='';savePrefs();return await navigate('home');}
    const action=button.dataset.action;
    if(['phonetics','home','library','history','mistakes','settings','completed','today','rewards'].includes(action))return await navigate(action);
    if(action==='spin-reward')return await spinReward();
    if(action==='start')return await start();
    if(action==='resume')return await resume();
    if(action==='fullscreen'){if(document.body.classList.contains('focus-mode'))leaveFocus();else enterFocus();return;}
    if(action==='replay')return await speakCurrent();
    if(action==='dictation-next')return await act('next');
    if(action==='previous-word')return await moveWord(-1);
    if(action==='next-word')return await moveWord(1);
    if(action==='hint'||action==='skip')return await act(action);
    if(action==='end')return $('#end-dialog').showModal();
    if(action==='review'){if(route==='report')prefs.practiceType=currentReport.practice_type;return await start('review',button.dataset.book);}
    if(action==='again'){prefs.practiceType=currentReport.practice_type;prefs.book=button.dataset.book;prefs.unit='';savePrefs();return await start();}
    if(action==='export-report')return exportReport();
    if(action==='import')return $('#import-file').click();
    if(action==='template')return download('词屿词库模板.json',JSON.stringify({id:'my-school-grade6-a',title:'我的六年级上册',publisher:'请填写出版社',edition:'请填写课本版次',grade:6,term:'上',source_url:'https://example.com/replace-with-your-source',source_note:'请核对词条和教材来源后导入',regions:['浙江省'],words:[{english:'Monday',meaning:'星期一',unit:'Unit 1',page:'1'},{english:'Tuesday',meaning:'星期二',unit:'Unit 1',page:'2'}]},null,2));
  }catch(error){toast(error.message);}
});
$('#end-dialog').addEventListener('close',()=>{if($('#end-dialog').returnValue==='end')act('finish');});
async function refreshSession(){
  const view=session.view_position,wordId=session.current?.word_id,readonly=session.readonly,phase=session.current?.phase;
  sync(await api(`/api/session/${session.id}${readonly?'?position='+session.view_position:''}`));
  if(session.status!=='active')await showReport(session.id);
  else if(route==='practice'&&(view!==session.view_position||wordId!==session.current.word_id||readonly!==session.readonly||phase!==session.current.phase)){renderPractice();speakCurrent();}
}
setInterval(async()=>{
  if(!session||session.status!=='active')return;
  const left=Math.max(0,Math.ceil(clockRemaining-(performance.now()-clockAt)/1000));
  if($('#time-left'))$('#time-left').textContent=fmtTime(left);
  $('#timer')?.classList.toggle('urgent',left<60);
  if(isDictation()){
    if(session.current.phase==='writing'&&!isManualDictation()){
      const remaining=dictationSeconds();if($('#dictation-left'))$('#dictation-left').textContent=remaining;
      $('#dictation-timer')?.classList.toggle('urgent',remaining<=5);
      if(!remaining&&route==='practice'&&!busy&&!pending)await act('answer',$('#answer')?.value||'');
    }
    if(session.current.phase==='result'&&route==='practice'&&!busy&&!pending&&!$('#end-dialog').open&&Date.now()>=dictationAdvanceAt)await act('next');
    return;
  }
  if(!left&&!busy){busy=true;disableAnswer(true);try{await refreshSession();if(session.status==='active'&&!pending)disableAnswer(false);}catch{feedback('时间已到，正在等待服务确认结算…','error');}finally{busy=false;}}
},300);
document.addEventListener('visibilitychange',async()=>{if(document.visibilityState==='visible'){renderClock();if(route==='home'&&$('#daily-quote'))$('#daily-quote').innerHTML=dailyQuoteMarkup();if(session?.status==='active'&&!busy){try{await refreshSession();}catch{}}}});
renderClock();setInterval(renderClock,1000);
(async()=>{try{await refresh();renderHome();if(!prefs.province&&!prefs.locationChecked)locate();}catch(error){main.innerHTML=`<div class="card empty"><h2>暂时无法连接词屿</h2><p>${esc(error.message)}<br>请确认启动窗口仍在运行，然后刷新页面。</p></div>`;}})();
