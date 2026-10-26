'use strict';
let registering=false;
const form=document.querySelector('#login-form'),status=document.querySelector('#login-status'),submit=document.querySelector('#submit-login'),toggle=document.querySelector('#toggle-mode');
toggle.addEventListener('click',()=>{
  registering=!registering;
  document.querySelector('#invitation-field').hidden=!registering;
  form.elements.invitation.required=registering;
  form.elements.password.autocomplete=registering?'new-password':'current-password';
  submit.textContent=registering?'创建账号并登录':'登录';toggle.textContent=registering?'已有账号，去登录':'创建账号';status.textContent='';
});
form.addEventListener('submit',async event=>{
  event.preventDefault();submit.disabled=toggle.disabled=true;status.textContent='正在验证…';
  try{
    const result=await fetch('/api/auth/'+(registering?'register':'login'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});
    const data=await result.json();if(!result.ok)throw new Error(data.error||'登录失败');
    // Preferences are account-local too, even on a shared browser.
    const identity=await fetch('/api/auth/me').then(r=>r.json());
    try{
    const old=localStorage.getItem('wordisle-cloud-account');
    if(old&&old!==identity.user_id){const prefs=localStorage.getItem('word-isle-preferences');if(prefs)localStorage.setItem('wordisle-prefs-'+old,prefs);}
    if(old!==identity.user_id){const prefs=localStorage.getItem('wordisle-prefs-'+identity.user_id);if(prefs)localStorage.setItem('word-isle-preferences',prefs);else localStorage.removeItem('word-isle-preferences');}
    localStorage.setItem('wordisle-cloud-account',identity.user_id);
    }catch{}
    location.replace('/');
  }catch(error){status.textContent=error.message;}finally{submit.disabled=toggle.disabled=false;}
});
