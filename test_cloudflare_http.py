"""Real workerd integration checks. Run against a local wrangler dev only.
Creates two disposable accounts in the local .wrangler database, never real data.
"""
import http.cookiejar
import json
from pathlib import Path
import secrets
import urllib.request
import urllib.error

BASE = 'http://127.0.0.1:8787'
class Client:
    def __init__(self):
        self.jar=http.cookiejar.CookieJar()
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(self.jar))
    def call(self,path,body=None,origin=BASE,headers=None):
        h={'Origin':origin,**(headers or {})}
        if body is not None:h['Content-Type']='application/json'
        req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers=h)
        try:r=self.opener.open(req,timeout=60)
        except urllib.error.HTTPError as e:r=e
        raw=r.read()
        data=json.loads(raw) if 'application/json' in r.headers.get('Content-Type','') else raw
        return r.status,data,r.headers
    def ok(self,path,body=None):
        status,data,_=self.call(path,body)
        assert status==200,(path,status,data)
        return data

def run():
    invitation=dict(line.split('=',1) for line in Path('.dev.vars').read_text().splitlines() if '=' in line)['REGISTRATION_CODE']
    a,b=Client(),Client()
    assert a.call('/api/bootstrap')[0]==401
    assert a.call('/api/auth/register',{},origin='https://evil.example')[0]==403
    names=['test-'+secrets.token_hex(5) for _ in range(2)]
    password='test-password-'+secrets.token_hex(10)
    for client,name in zip((a,b),names):
        status,data,h=client.call('/api/auth/register',dict(username=name,password=password,invitation=invitation))
        assert status==200,(status,data)
        assert 'HttpOnly' in h['Set-Cookie'] and 'SameSite=Strict' in h['Set-Cookie']
    aa,bb=a.ok('/api/bootstrap'),b.ok('/api/bootstrap')
    assert len(aa['books'])==17 and aa['summary']['stars']==0
    assert aa['cloud'] and not aa['native_voice']
    pack=dict(id='cloud-test',title='云端测试',publisher='测试',edition='测试',grade=3,term='上',source_url='https://example.com',words=[dict(english='apple',meaning='苹果',unit='Unit 1'),dict(english='banana',meaning='香蕉',unit='Unit 1')])
    a.ok('/api/import',pack)
    assert len(a.ok('/api/bootstrap')['books'])==18
    assert len(b.ok('/api/bootstrap')['books'])==17
    assert a.call('/api/import',pack)[0]==400
    s=a.ok('/api/start',dict(book_id='cloud-test',minutes=15,learning_order='sequential'))
    sid=s['id']
    assert b.call('/api/session/'+sid)[0]==400
    assert a.call('/api/start',dict(book_id='cloud-test',minutes=15))[0]==400
    answer=dict(position=0,answer='ple',request_id='answer-one')
    result=a.ok('/api/session/'+sid+'/answer',answer)
    assert result['session']['stars']==10
    assert a.ok('/api/session/'+sid+'/answer',answer)['session']['stars']==10
    assert a.call('/api/session/'+sid+'/answer',{**answer,'answer':'bad'})[0]==400
    assert a.ok('/api/completed-words')['total']==1
    assert b.ok('/api/completed-words')['total']==0
    a.ok('/api/session/'+sid+'/finish',dict(position=1,request_id='finish-one'))
    assert a.ok('/api/session/'+sid+'/report')['first_correct']==1
    speech=a.ok('/api/audio/'+str(s['current']['word_id']))
    assert speech['fallback'] and speech['text']=='apple'
    cfg=a.ok('/api/rewards/config')
    a.ok('/api/rewards/config',dict(prizes=list(reversed(cfg['prizes'])),revision=cfg['revision']))
    assert a.call('/api/rewards/config',dict(prizes=cfg['prizes'],revision=cfg['revision']))[0]==400
    assert a.call('/api/rewards/draw',dict(request_id='no-money',config_revision=a.ok('/api/rewards/config')['revision']))[0]==400
    s=a.ok('/api/start',dict(book_id='cloud-test',minutes=15,learning_order='sequential',practice_type='dictation_en',dictation_mode='manual'))
    sid=s['id']
    assert s['current']['phase']=='listening'
    assert a.call('/api/session/'+sid+'/answer',dict(position=0,answer='apple',request_id='early'))[0]==400
    a.ok('/api/session/'+sid+'/ready',dict(position=0,request_id='ready'))
    for rev,value in [(2,'apple'),(1,'bad')]:
        a.ok('/api/session/'+sid+'/draft',dict(position=0,answer=value,revision=rev,request_id='draft-'+str(rev)))
    assert a.ok('/api/session/'+sid)['current']['draft']=='apple'
    a.ok('/api/session/'+sid+'/answer',dict(position=0,answer='apple',request_id='answer'))
    a.ok('/api/session/'+sid+'/next',dict(position=0,request_id='next'))
    a.ok('/api/session/'+sid+'/finish',dict(position=1,request_id='finish'))
    assert a.ok('/api/session/'+sid+'/report')['dictation_correct']==1
    lesson=a.ok('/api/phonetics')
    assert len(lesson['course'])==48 and lesson['service']['cloud'] and not lesson['service']['local']['available']
    assert a.call('/api/phonetics/config',dict(secret_id='not-a-key',secret_key='not-a-key'))[0]==400
    assert a.call('/api/phonetics/prepare',{})[0]==400
    status,body,h=a.call('/media/phonetics/lesson.mp4',headers={'Range':'bytes=0-31'})
    assert status==206 and len(body)==32,(status,len(body))
    assert not a.ok('/api/bootstrap')['active']
    saved=dict(username=names[0],password=password,summary=a.ok('/api/bootstrap')['summary'])
    Path('.wrangler/cloud-test-restart.json').write_text(json.dumps(saved))
    Path('.wrangler/cloud-test-restart.json').chmod(0o600)
    a.ok('/api/auth/logout',{})
    assert a.call('/api/bootstrap')[0]==401
    a.ok('/api/auth/login',dict(username=names[0],password=password))
    assert a.ok('/api/bootstrap')['summary']==saved['summary']
    print('PASS: authentication, CSRF, two-account isolation, catalog, learning/idempotency, dictation drafts, reports, rewards guards, audio fallback, phonetics, media Range, logout/login.')

def verify_restart():
    artifact=Path('.wrangler/cloud-test-restart.json')
    saved=json.loads(artifact.read_text())
    c=Client()
    c.ok('/api/auth/login',dict(username=saved['username'],password=saved['password']))
    assert c.ok('/api/bootstrap')['summary']==saved['summary']
    artifact.unlink()
    print('PASS: restart preserves account, learning history and summary; temporary test credentials removed.')

if __name__=='__main__':
    import sys
    verify_restart() if '--verify-restart' in sys.argv else run()
