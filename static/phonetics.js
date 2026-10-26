'use strict';
const PhoneticsUI = (() => {
  let root, overview, accent='uk', selected='1', test=null, audio=null, playbackTimer, recorder=null, take=null, takeURL=null, generation=0, submitting=false;
  const accentName = value => value==='uk'?'英式':'美式';
  const isLocal = value => value?.provider==='openpronounce';
  const providerName = value => isLocal(value)?'OpenPronounce 本地例词':'腾讯云音素';
  const scoreText = value => value==null?'未评分':`${value} 分`;
  const link = (url, label) => `<a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(label)}</a>`;
  const current = () => test.course[test.position];
  function stopAudio(){
    clearTimeout(playbackTimer);
    if(audio){audio.pause();audio.removeAttribute('src');audio.load();audio=null;}
    root?.querySelectorAll('video,audio').forEach(el=>el.pause());
  }
  function clearTake(){take=null;if(takeURL){URL.revokeObjectURL(takeURL);takeURL=null;}}
  function leave(){generation++;stopAudio();if(recorder)recorder.cancel();clearTake();root=null;test=null;submitting=false;}
  async function mount(){
    leave();const token=generation;accent=prefs.phoneticAccent==='us'?'us':'uk';
    main.innerHTML='<div class="loading">正在打开音标学习…</div>';
    overview=await api('/api/phonetics');if(token!==generation||route!=='phonetics')return;
    root=document.createElement('div');root.className='ipa-page';main.replaceChildren(root);
    root.addEventListener('click',click);renderLearn();
  }
  function title(text, detail){return `<div class="page-heading"><div><div class="eyebrow">LISTEN · SPEAK · GROW</div><h1>${text}</h1><p>${detail}</p></div></div>`;}
  function renderLearn(){
    stopAudio();clearTake();test=null;
    const groups=[...new Set(overview.course.map(item=>item.group))];
    root.innerHTML=title('音标学习','听清每一个音，迈出英语发音的第一步。')+`
      <section class="card ipa-course"><div class="ipa-heading"><div><h2>48 组音标 · 点击听一听</h2><p>20 组元音 · 24 个辅音 · 4 组组合音</p></div><div class="ipa-accents" role="group" aria-label="示范口音">${['uk','us'].map(value=>`<button data-ipa="accent" data-value="${value}" aria-pressed="${accent===value}" class="${accent===value?'primary':'secondary'}">${accentName(value)} ${value.toUpperCase()}</button>`).join('')}</div></div>
      <p class="ipa-note">英美音系并非一一对应。下方按常见 48 组教学分类对照；美式 /ɑː/ 可能对应两个英式音。剑桥录音需联网。</p>
      <div class="ipa-board">${groups.map(group=>`<section class="ipa-group"><h3>${group}</h3><div class="ipa-tiles">${overview.course.filter(item=>item.group===group).map(item=>`<button class="ipa-tile ${item.id===selected?'active':''}" data-ipa="sound" data-id="${item.id}" aria-label="${accentName(accent)} /${esc(item[accent].symbol)}/，${item[accent].kind==='example'?'例词示范':'音标发音'}"><strong>/${esc(item[accent].symbol)}/</strong><small>${esc(item[accent].example)}</small>${item[accent].kind==='example'?'<span>例词示范</span>':''}</button>`).join('')}</div></section>`).join('')}</div>
      <div id="ipa-detail" class="ipa-detail" aria-live="polite"></div></section>
      <div class="ipa-bottom"><section class="card ipa-video"><div class="ipa-heading"><div><h2>跟着视频学音标</h2><p>参考歌谣 · ${overview.service.cloud?'在线播放':'可离线播放'} · 约 2 分钟</p></div><button class="secondary" data-ipa="fullscreen">全屏播放 ↗</button></div><video controls playsinline preload="metadata" aria-label="48 个音标学习参考视频" src="/media/phonetics/lesson.mp4"></video><details><summary>只听音频</summary><audio controls preload="none" src="/media/phonetics/lesson.mp3" aria-label="音标学习参考歌谣"></audio></details><p class="ipa-note">全屏时按 Esc 退出，播放进度保留。视频沿用原素材的口音与教学写法，不随上方英美切换。</p></section>
      <section class="card ipa-start"><div class="eyebrow">SPEAK & CHECK</div><h2>试试你的发音</h2><p>听示范，录下自己的声音。${isLocal(overview.service)?'完成后查看例词参考分和识别结果。':'完成后查看每个音的得分和练习建议。'}</p><div class="ipa-service ${overview.service.configured?'':'ipa-unconfigured'}">${providerName(overview.service)} · ${overview.service.configured?'已就绪':'未就绪'}<p>${isLocal(overview.service)?esc(overview.service.local.message):overview.service.configured?'实际连接及额度将在提交录音时检查。':overview.service.cloud?'请联系管理员配置腾讯云评测，再开始自动评分。':'先在设置中填写腾讯云口语评测凭证，再开始自动评分。'}</p></div>
      <p class="ipa-note">${esc(overview.service.notice)}</p><label class="ipa-consent"><input type="checkbox" id="ipa-consent">${isLocal(overview.service)?'我已了解：需要读完整例词，得分仅作练习参考，录音只在本机处理和保存。':overview.service.cloud?'我同意点击“提交评测”时将录音发送至腾讯云。录音及报告保存在我的云端账号，可在测试记录中删除。请由家长协助确认。':'我同意点击“提交评测”时将录音发送至腾讯云。录音及报告保存在本机，可在测试记录中删除。请由家长协助确认。'}</label>
      <div class="button-row"><button class="primary" data-ipa="start" data-count="10" ${overview.service.configured?'':'disabled'}>快速测试 · 10 项</button><button class="secondary" data-ipa="start" data-count="48" ${overview.service.configured?'':'disabled'}>完整测试 · 48 项</button></div><button class="text-button" data-action="settings">配置评测服务 →</button></section></div>
      <section class="card ipa-history"><h2>发音测试记录</h2>${overview.history.length?overview.history.map(row=>`<div class="ipa-history-row"><span>${date(row.created)} · ${accentName(row.accent)} · ${providerName(row)}<small>${row.ended?'已结束':'可继续'} · 已处理 ${row.position} 项</small></span><div class="button-row"><button class="secondary" data-ipa="history" data-id="${row.id}">${row.ended?'查看报告':'继续测试'}</button><button class="text-button" data-ipa="delete" data-id="${row.id}">删除</button></div></div>`).join(''):'<p>还没有测试记录。完成一次测试后，报告会保存在这里。</p>'}</section>
      <p class="ipa-note">发音来源：${link('https://dictionary.cambridge.org/help/phonetics.html','Cambridge Dictionary 英美发音指南')} · 评分说明：${link('https://github.com/Halleck45/OpenPronounce','OpenPronounce 例词参考评测')} · ${link('https://cloud.tencent.com/document/product/884/33698','腾讯云音素评测')}。组合音和缺少独立音频的美式对应音使用例词示范，并单独标注。</p>`;
    root.querySelectorAll('video,audio').forEach(el=>el.addEventListener('play',()=>{if(audio)audio.pause();root.querySelectorAll('video,audio').forEach(other=>{if(other!==el)other.pause();});}));
    detail();
  }
  function detail(){
    const item=overview.course.find(row=>row.id===selected),variant=item[accent];
    root.querySelectorAll('.ipa-tile').forEach(button=>{button.classList.toggle('active',button.dataset.id===selected);button.setAttribute('aria-pressed',String(button.dataset.id===selected));});
    $('#ipa-detail').innerHTML=`<div class="ipa-symbol">/${esc(variant.symbol)}/</div><div><b>${accentName(accent)} · ${variant.kind==='example'?'例词示范':'音标发音'}</b><p>${esc(item.tip)}</p><p class="ipa-note">英式 /${esc(item.uk.symbol)}/ ↔ 美式 /${esc(item.us.symbol)}/ · 例词 ${esc(variant.example)}</p><div class="button-row"><button class="secondary" data-ipa="replay">${variant.kind==='example'?'再听例词':'再听音标'}</button>${variant.kind==='sound'?'<button class="secondary" data-ipa="example">听例词</button>':''}${link(item.source,'录音来源')}</div><p id="ipa-audio-status" role="status"></p></div>`;
  }
  async function play(url){
    stopAudio();const playing=new Audio(url);audio=playing;
    const status=root?.querySelector('#ipa-audio-status');if(status)status.textContent='正在载入录音…';
    playing.onended=()=>{if(status?.isConnected&&audio===playing)status.textContent='播放完成';};
    playing.onerror=()=>{clearTimeout(playbackTimer);if(status?.isConnected&&audio===playing)status.textContent='录音暂不可用，请检查网络，或打开录音来源。';};
    playing.onplaying=()=>clearTimeout(playbackTimer);
    playbackTimer=setTimeout(()=>{if(audio===playing){playing.pause();playing.onerror();}},15000);
    try{await playing.play();if(status?.isConnected&&audio===playing)status.textContent='正在播放…';}catch{playing.onerror();}
  }
  function renderTest(){
    stopAudio();clearTake();
    if(test.ended)return renderReport();
    const item=current(),variant=item[test.accent],result=test.results.find(row=>row.position===test.position);
    root.innerHTML=title('发音练习',`${providerName(test)} · ${accentName(test.accent)}示范 · 第 ${test.position+1} / ${test.course.length} 项`)+`
      <section class="card ipa-test"><div class="ipa-heading"><span class="tag">${esc(item.group)}</span><button class="secondary" data-ipa="finish">结束并生成报告</button></div><progress max="${test.course.length}" value="${test.position}" aria-label="测试进度"></progress><div class="ipa-test-symbol">/${esc(variant.symbol)}/</div><p>${esc(item.tip)}</p>${isLocal(test)?`<h2 class="ipa-example">请读：${esc(variant.example)}</h2>`:''}<div class="button-row"><button class="secondary" data-ipa="demo">${isLocal(test)||variant.kind==='example'?`听例词 ${esc(variant.example)}`:'听标准示范'}</button></div><p id="ipa-audio-status" role="status"></p>
      <p class="ipa-note">${isLocal(test)?'请读上方完整英文例词，不要只读音标。':'只读目标音或组合音，不读音标名称或整个例词。'}点击录音后开始，最长 8 秒；点击停止后可回听，再提交。</p><p id="ipa-record-status" role="status">${result?.status==='error'?esc(result.error):result?.status==='processing'?'上次提交仍在评测，请稍后刷新进度。':'准备好后，点击开始录音。'}</p>
      <div class="button-row"><button class="primary" data-ipa="record" ${result?.status==='processing'?'disabled':''}>开始录音</button><button class="secondary" data-ipa="stop" disabled>停止录音</button><button class="secondary" data-ipa="listen" disabled>回听录音</button><button class="primary" data-ipa="submit" disabled>提交评测</button></div><div class="button-row ipa-test-footer"><button class="text-button" data-ipa="skip">跳过此音（不计分）</button><button class="text-button" data-ipa="refresh">刷新进度</button><button class="text-button" data-ipa="learn">返回学习，稍后继续</button></div>
      <p class="ipa-note">${esc(test.notice)}</p></section>`;
    if(result?.status==='error'){
      const button=document.createElement('button');button.className='secondary';button.dataset.ipa='restore';button.textContent='恢复上次录音并重试';$('#ipa-record-status').after(button);
    }
  }
  function renderReport(){
    const weak=test.results.filter(row=>row.status==='scored'&&row.score<80).map(row=>test.course[row.position][test.accent].symbol);
    root.innerHTML=title(isLocal(test)?'例词发音参考报告':'音标发音测试报告',`${date(test.created)} · ${accentName(test.accent)}示范 · ${test.engine}`)+`
      <section class="card ipa-report"><div class="ipa-report-summary"><div><strong>${test.mean??'—'}</strong><span>${isLocal(test)?'例词平均参考分':'平均准确度得分'} / 100</span></div><div><b>${test.scored} / ${test.course.length}</b><span>有效评分</span></div><div><b>${test.skipped}</b><span>跳过</span></div><div><b>${test.remaining}</b><span>未取得评分</span></div></div><p>${weak.length?'建议优先练习：'+weak.map(value=>'/'+esc(value)+'/').join('、'):test.scored?'继续回听自己的录音，留意口型与气流。':'本次未取得有效评分，请配置服务或重试。'}</p><p class="ipa-note">均分只计算有效评分；跳过、失败及未完成项不计 0 分。低于 80 分列为本应用的练习建议，不是专业合格标准。${esc(test.notice)}</p><div class="button-row"><button class="primary" data-ipa="learn">返回音标学习</button><button class="secondary" data-ipa="export">导出报告 CSV</button></div></section>
      <section class="card ipa-report"><div class="ipa-table-wrap"><table><thead><tr><th>音标</th><th>${isLocal(test)?'例词参考分':'准确度得分'}</th><th>反馈</th><th>录音</th></tr></thead><tbody>${test.course.map((item,position)=>{const result=test.results.find(row=>row.position===position),variant=item[test.accent];return `<tr><td><b>/${esc(variant.symbol)}/</b><small>${isLocal(test)?esc(variant.example):esc(item.group)}</small></td><td>${scoreText(result?.score)}</td><td>${result?.status==='scored'?(isLocal(test)?`识别文本：${esc(result.transcript||'未识别')}<small>预期音素：${esc(result.expected_ipa||'—')}<br>识别音素：${esc(result.heard_ipa||'—')}</small>`:result.raw_score===-1?'服务判定完全不匹配':result.score<80?'建议再听示范，放慢练习':'继续保持，并回听对比')+(result.phones?.length?'<small>'+result.phones.map(p=>`${esc(p.reference)}: ${scoreText(p.score)}`).join(' · ')+'</small>':''):result?.status==='skipped'?'已跳过':esc(result?.error||'未完成')}</td><td>${result&&['scored','error'].includes(result.status)?`<button class="secondary" data-ipa="saved" data-position="${position}">回听</button>`:'—'}</td></tr>`;}).join('')}</tbody></table></div></section>`;
  }
  async function startRecording(){
    if(recorder||submitting)return;
    stopAudio();clearTake();const token=generation,ctxRoot=root;
    $('#ipa-record-status').textContent='正在请求麦克风权限…';setRecordingButtons(true);
    let stream,context,processor,source,gain,timer,interval;
    const chunks=[];
    try{
      stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:false,noiseSuppression:false,autoGainControl:false},video:false});
      if(token!==generation||root!==ctxRoot){stream.getTracks().forEach(track=>track.stop());return;}
      context=new AudioContext();await context.resume();
      if(token!==generation||root!==ctxRoot){stream.getTracks().forEach(track=>track.stop());await context.close();return;}
      source=context.createMediaStreamSource(stream);
      // ponytail: ScriptProcessor supports the app's macOS 12.3 floor; use AudioWorklet if longer/live recordings are added.
      processor=context.createScriptProcessor(4096,1,1);gain=context.createGain();gain.gain.value=0;
      processor.onaudioprocess=event=>chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      source.connect(processor);processor.connect(gain);gain.connect(context.destination);
      const cleanup=()=>{clearTimeout(timer);clearInterval(interval);processor.disconnect();source.disconnect();gain.disconnect();stream.getTracks().forEach(track=>track.stop());context.close();recorder=null;};
      recorder={cancel:cleanup,stop:async()=>{
        const rate=context.sampleRate;cleanup();
        root.querySelectorAll('[data-ipa]').forEach(button=>button.disabled=true);
        $('#ipa-record-status').textContent='正在处理录音…';
        try{
          const length=Math.min(chunks.reduce((n,chunk)=>n+chunk.length,0),rate*8);
          if(length<rate*.5)throw new Error('录音太短，请至少录制半秒。');
          const buffer=new AudioBuffer({length,numberOfChannels:1,sampleRate:rate});let offset=0;
          for(const chunk of chunks){const part=chunk.subarray(0,length-offset);buffer.copyToChannel(part,0,offset);offset+=part.length;if(offset>=length)break;}
          const offline=new OfflineAudioContext(1,Math.min(128000,Math.round(length*16000/rate)),16000),node=offline.createBufferSource();node.buffer=buffer;node.connect(offline.destination);node.start();
          const pcm=(await offline.startRendering()).getChannelData(0);
          if(token!==generation||root!==ctxRoot)return;
          setTake(wav(pcm));$('#ipa-record-status').textContent=`已录制 ${(pcm.length/16000).toFixed(1)} 秒，请回听后提交。`;
        }catch(error){if(token===generation&&root===ctxRoot){setRecordingButtons(false);$('#ipa-record-status').textContent=error.message;}}
      }};
      const began=performance.now();$('#ipa-record-status').textContent='正在录音 · 0.0 / 8 秒';
      interval=setInterval(()=>{if(root===ctxRoot)$('#ipa-record-status').textContent=`正在录音 · ${((performance.now()-began)/1000).toFixed(1)} / 8 秒`;},100);
      timer=setTimeout(()=>recorder?.stop(),8000);
    }catch(error){stream?.getTracks().forEach(track=>track.stop());if(context&&context.state!=='closed')context.close();if(token===generation&&root===ctxRoot){setRecordingButtons(false);$('#ipa-record-status').textContent=error.name==='NotAllowedError'?'麦克风权限未开启，请在系统设置 → 隐私与安全性 → 麦克风中允许词屿，再重试。':'无法打开麦克风，请检查输入设备后重试。';}}
  }
  function setRecordingButtons(active){
    root.querySelectorAll('[data-ipa]').forEach(button=>button.disabled=active&&!['stop'].includes(button.dataset.ipa));
    root.querySelector('[data-ipa="stop"]').disabled=!active;
    for(const action of ['listen','submit'])root.querySelector(`[data-ipa="${action}"]`).disabled=active||!take;
  }
  function wav(samples){
    const buffer=new ArrayBuffer(44+samples.length*2),view=new DataView(buffer),write=(at,text)=>[...text].forEach((char,i)=>view.setUint8(at+i,char.charCodeAt(0)));
    write(0,'RIFF');view.setUint32(4,36+samples.length*2,true);write(8,'WAVEfmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,16000,true);view.setUint32(28,32000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);write(36,'data');view.setUint32(40,samples.length*2,true);
    samples.forEach((value,i)=>view.setInt16(44+i*2,Math.max(-1,Math.min(1,value))*(value<0?32768:32767),true));return buffer;
  }
  function setTake(buffer){clearTake();take={buffer,id:crypto.randomUUID()};takeURL=URL.createObjectURL(new Blob([buffer],{type:'audio/wav'}));setRecordingButtons(false);}
  async function submit(){
    if(!take||submitting)return;
    stopAudio();submitting=true;const token=generation,ctxRoot=root;
    root.querySelectorAll('button').forEach(button=>button.disabled=true);$('#ipa-record-status').textContent=isLocal(test)?'正在本机评测，首次加载模型可能需要较长时间，请稍候…':'正在提交腾讯云评测，请稍候…';
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),isLocal(test)?200000:45000);
    let binary='';new Uint8Array(take.buffer).forEach(byte=>binary+=String.fromCharCode(byte));
    try{
      const response=await fetch(`/api/phonetics/tests/${test.id}/assess`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({position:test.position,request_id:take.id,audio:btoa(binary)}),signal:controller.signal});
      const result=await response.json();if(!response.ok)throw new Error(result.error||'提交未完成');
      if(token!==generation||root!==ctxRoot)return;
      const priorPosition=test.position;test=result;
      if(test.position===priorPosition&&!test.ended){take.id=crypto.randomUUID();$('#ipa-record-status').textContent=test.results.find(row=>row.position===priorPosition)?.error||'正在评测，请稍后刷新进度。';}
      else renderTest();
    }catch(error){if(token===generation&&root===ctxRoot)$('#ipa-record-status').textContent=error.name==='AbortError'?'等待超时，录音仍保留。可刷新进度确认结果，或原样重试。':error.message;}
    finally{clearTimeout(timeout);if(token===generation&&root===ctxRoot){submitting=false;if(test&&!test.ended)setRecordingButtons(false);}}
  }
  async function click(event){
    const button=event.target.closest('[data-ipa]');if(!button||button.disabled)return;
    const action=button.dataset.ipa;
    try{
      if(action==='accent'){accent=button.dataset.value;prefs.phoneticAccent=accent;savePrefs();renderLearn();}
      if(action==='sound'){selected=button.dataset.id;detail();await play(overview.course.find(row=>row.id===selected)[accent].audio);}
      if(['replay','example'].includes(action))await play(overview.course.find(row=>row.id===selected)[accent][action==='example'?'example_audio':'audio']);
      if(action==='start'){
        if(!$('#ipa-consent').checked){toast('请先确认录音评测说明。');$('#ipa-consent').focus();return;}
        button.disabled=true;const target=root;
        const result=await api('/api/phonetics/tests',{accent,count:Number(button.dataset.count),consent:true,provider:overview.service.provider});if(root!==target)return;test=result;renderTest();
      }
      if(action==='history'){const target=root,result=await api(`/api/phonetics/tests/${button.dataset.id}`);if(root!==target)return;test=result;renderTest();}
      if(action==='learn')await mount();
      if(action==='delete'){
        if(button.dataset.confirm!=='yes'){button.dataset.confirm='yes';button.textContent='确认删除录音及报告';return;}
        await api(`/api/phonetics/tests/${button.dataset.id}/delete`,{});await mount();
      }
      if(action==='record')await startRecording();
      if(action==='stop')await recorder?.stop();
      if(action==='listen'&&takeURL)await play(takeURL);
      if(action==='submit')await submit();
      if(action==='demo')await play(current()[test.accent][isLocal(test)?'example_audio':'audio']);
      if(action==='fullscreen'){
        const video=root.querySelector('video');
        if(video.requestFullscreen)await video.requestFullscreen();
        else if(video.webkitEnterFullscreen)video.webkitEnterFullscreen();
        else throw new Error('当前环境不支持视频全屏，请使用窗口全屏。');
        await video.play();
      }
      if(['skip','finish','refresh'].includes(action)){
        button.disabled=true;const target=root;
        const result=await api(`/api/phonetics/tests/${test.id}${action==='refresh'?'':'/'+action}`,action==='refresh'?undefined:{position:test.position});
        if(root!==target)return;test=result;renderTest();
      }
      if(action==='restore'){
        const target=root,response=await fetch(`/api/phonetics/tests/${test.id}/audio/${test.position}`);if(!response.ok)throw new Error('无法恢复录音，请重新录制。');
        const buffer=await response.arrayBuffer();if(root!==target)return;setTake(buffer);$('#ipa-record-status').textContent='已恢复上次录音，可回听后重新提交。';button.remove();
      }
      if(action==='saved')await play(`/api/phonetics/tests/${test.id}/audio/${button.dataset.position}`);
      if(action==='export'){
        const rows=[['词屿音标发音报告',date(test.created),accentName(test.accent)],['评分服务',test.engine],['评分口径',test.notice],['平均得分',test.mean??'未评分'],['有效评分',test.scored,'总项数',test.course.length],['音标','状态',isLocal(test)?'例词参考分':'准确度得分','服务请求编号','例词','识别文本','预期音素','识别音素']];
        test.course.forEach((item,position)=>{const row=test.results.find(r=>r.position===position);rows.push([item[test.accent].symbol,{scored:'已评分',skipped:'跳过',error:'服务失败'}[row?.status]||'未完成',row?.score??'',row?.request_id||'',isLocal(test)?item[test.accent].example:'',row?.transcript||'',row?.expected_ipa||'',row?.heard_ipa||'']);});
        const quote=value=>'"'+String(value).replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';download('词屿音标发音报告.csv','\ufeff'+rows.map(row=>row.map(quote).join(',')).join('\r\n'),'text/csv');
      }
    }catch(error){toast(error.message);if(button.isConnected)button.disabled=false;}
  }
  async function mountSettings(){
    const panel=document.createElement('section');panel.className='card ipa-settings';$('.settings-actions').before(panel);
    let timer;
    const poll=()=>{clearTimeout(timer);timer=setTimeout(async()=>{
      if(!panel.isConnected)return;
      try{
        const service=await api('/api/phonetics/config');if(!panel.isConnected)return;
        panel.querySelector('#ipa-local-status').textContent=service.local.message;
        const button=panel.querySelector('#ipa-prepare');button.disabled=!service.local.available||service.local.busy;
        button.textContent=service.local.busy?'正在准备模型…':service.local.ready?'检查本地模型':'下载并准备模型';
        if(service.local.busy)poll();
      }catch(error){toast(error.message);}
    },2000);};
    const render=service=>{
      if(!panel.isConnected)return;
      if(service.cloud){
        panel.innerHTML=`<h2>音标发音评测</h2><p>腾讯云评测 · ${service.configured?'管理员已配置':'尚未配置'}</p><p class="ipa-note">${esc(service.notice)}</p><p>评测服务由管理员配置。OpenPronounce 本地模型仅在 Mac 本地版提供。</p><button class="secondary" id="ipa-cloud-refresh">刷新状态</button>`;
        panel.querySelector('#ipa-cloud-refresh').addEventListener('click',async()=>{try{render(await api('/api/phonetics/config'));}catch(error){toast(error.message);}});
        return;
      }
      panel.innerHTML=`<h2>音标发音评测</h2><label class="field">评测方式<select id="ipa-provider"><option value="openpronounce" ${isLocal(service)?'selected':''}>OpenPronounce · 本地例词参考评测</option><option value="tencent" ${isLocal(service)?'':'selected'}>腾讯云 · 联网音素评测</option></select></label><p class="ipa-note">更改仅影响新测试；已开始的测试和历史报告保留各自的评测引擎。</p><p class="ipa-note">${esc(service.notice)}</p>
      <div class="ipa-service"><b>OpenPronounce 本地引擎</b><p id="ipa-local-status" role="status">${esc(service.local.message)}</p><p>首次下载约 2.4 GB 模型，请预留 4 GB 空间。下载完成后可离线评分，录音不上传；剑桥示范点读仍需联网。支持 Apple 芯片、macOS 14 及以上。</p><div class="button-row"><button type="button" class="secondary" id="ipa-prepare" ${!service.local.available||service.local.busy?'disabled':''}>${service.local.busy?'正在准备模型…':service.local.ready?'检查本地模型':'下载并准备模型'}</button><button type="button" class="secondary" id="ipa-refresh-service">刷新状态</button></div></div>
      <details ${isLocal(service)?'':'open'}><summary>腾讯云凭证 · ${service.tencent_configured?'已配置并保留':'未配置'}</summary><p>请先在腾讯云开通口语评测。联网评测可能产生费用。凭证仅保存在本机，不会放进安装包或导出报告。</p><form id="ipa-service-form" autocomplete="off"><div class="form-grid"><label class="field">SecretId<input name="secret_id" type="password" required maxlength="200" autocomplete="off" placeholder="填写 SecretId"></label><label class="field">SecretKey<input name="secret_key" type="password" required maxlength="200" autocomplete="new-password" placeholder="填写 SecretKey"></label><label class="field">SoeAppId（可选）<input name="soe_app_id" inputmode="numeric" pattern="[0-9]*" maxlength="30" placeholder="没有创建评测应用可留空"></label></div><div class="button-row"><button class="primary" type="submit">保存评测配置</button><button class="secondary" type="button" id="ipa-clear-service" ${service.tencent_configured?'':'disabled'}>移除本机凭证</button></div></form><p class="ipa-note">${link('https://cloud.tencent.com/product/soe','开通腾讯云口语评测')} · ${link('https://console.cloud.tencent.com/cam/capi','管理访问密钥')}</p></details><p id="ipa-config-status" role="status">已保存的密钥不会回显；保存仅检查格式，首次提交录音时验证服务。</p>`;
      panel.querySelector('#ipa-provider').addEventListener('change',async event=>{event.target.disabled=true;try{render(await api('/api/phonetics/config',{provider:event.target.value}));}catch(error){toast(error.message);event.target.disabled=false;}});
      panel.querySelector('#ipa-refresh-service').addEventListener('click',async()=>{try{render(await api('/api/phonetics/config'));}catch(error){toast(error.message);}});
      panel.querySelector('#ipa-prepare').addEventListener('click',async event=>{event.target.disabled=true;try{await api('/api/phonetics/prepare',{});render(await api('/api/phonetics/config'));}catch(error){if(panel.isConnected){panel.querySelector('#ipa-local-status').textContent=error.message;event.target.disabled=false;}}});
      panel.querySelector('form').addEventListener('submit',async event=>{event.preventDefault();event.stopPropagation();const form=event.target,button=form.querySelector('[type="submit"]');button.disabled=true;try{const saved=await api('/api/phonetics/config',Object.fromEntries(new FormData(form)));if(!panel.isConnected)return;render(saved);panel.querySelector('#ipa-config-status').textContent='已保存；首次提交录音时验证云服务。';}catch(error){if(panel.isConnected)panel.querySelector('#ipa-config-status').textContent=error.message;}finally{button.disabled=false;}});
      panel.querySelector('#ipa-clear-service').addEventListener('click',async()=>{try{render(await api('/api/phonetics/config',{clear:true}));}catch(error){toast(error.message);}});
      if(service.local.busy)poll();
    };
    try{render(await api('/api/phonetics/config'));}catch(error){if(panel.isConnected)panel.textContent=error.message;}
  }
  return {mount,leave,mountSettings};
})();
