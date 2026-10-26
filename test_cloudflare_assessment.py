"""Local workerd assessment mock. Never deploy the generated test config.
First run --prepare after npm run check:deploy, then start:
npx wrangler dev --config wrangler.assessment.test.jsonc --port 8788 --persist-to output/cf-assessment
Then run this script without arguments. Restart the mock server before each run.
"""
import json
from pathlib import Path
import secrets
import sys
import test_cloudflare_http as http
from test_phonetics import recording

if '--prepare' in sys.argv:
    config=json.loads(Path('wrangler.jsonc').read_text())
    config.pop('build', None)  # Preserve the prepared mock instead of rebuilding production modules.
    config.update(name='wordisle-assessment-test', main='.cloudflare/assessment_probe.py',
                  vars={'TENCENT_SECRET_ID':'mock-id','TENCENT_SECRET_KEY':'mock-key'})
    Path('wrangler.assessment.test.jsonc').write_text(json.dumps(config))
    Path('.cloudflare/assessment_probe.py').write_bytes(Path('cloudflare/assessment_probe.py').read_bytes())
    print('Prepared isolated test config. Run cloudflare/prepare_runtime.py, then start the test server.')
else:
    http.BASE='http://127.0.0.1:8788'
    client=http.Client()
    def call(path,body=None):
        status,data,_=client.call(path,body,origin=http.BASE)
        assert status==200,(path,status,data)
        return data
    invite=dict(line.split('=',1) for line in Path('.dev.vars').read_text().splitlines() if '=' in line)['REGISTRATION_CODE']
    call('/api/auth/register',dict(username='score-'+secrets.token_hex(5),password=secrets.token_hex(16),invitation=invite))
    state=call('/api/phonetics/tests',dict(count=10,accent='uk',consent=True))
    prefix='/api/phonetics/tests/'+state['id']
    body=dict(position=0,request_id='first',audio=recording())
    first=call(prefix+'/assess',body)
    assert first['position']==1 and first['mean']==88
    assert call(prefix+'/assess',body)==first
    assert call(prefix+'/audio/0')[:4]==b'RIFF'
    body.update(position=1,request_id='second')
    failed=call(prefix+'/assess',body)
    assert failed['position']==1 and failed['results'][1]['status']=='error'
    assert call(prefix+'/assess',body)==failed
    body['request_id']='retry'
    retried=call(prefix+'/assess',body)
    assert retried['position']==2 and retried['scored']==2
    finished=call(prefix+'/finish',{})
    assert finished['scored']==2
    call(prefix+'/delete',{})
    print('PASS: async assessment success, timeout, retry, duplicate submission, saved WAV, finish and delete.')
