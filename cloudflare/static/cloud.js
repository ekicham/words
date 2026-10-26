'use strict';
const cloudActions=document.createElement('div');cloudActions.className='button-row';
const logout=document.createElement('button');logout.className='secondary';logout.textContent='退出登录';
logout.addEventListener('click',async()=>{logout.disabled=true;try{const r=await fetch('/api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(!r.ok)throw new Error('退出失败，请重试');location.replace('/login.html');}catch(e){toast(e.message);logout.disabled=false;}});
cloudActions.append(logout);document.querySelector('.sidebar-bottom').append(cloudActions);
