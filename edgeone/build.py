"""Produce only public assets and the Python cloud function; never copy user data."""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from edgeone.resources import RESOURCES

public = ROOT/'dist/edgeone'
runtime = ROOT/'cloud-functions'
package = runtime/'wordisle_edge'
for folder in (public,package):
    if folder.exists(): shutil.rmtree(folder)
    folder.mkdir(parents=True)
for name in ('phonetics.py','local_assessment.py'):
    (runtime/name).write_bytes((ROOT/name).read_bytes())
for name in ('server.py','storage.py','domain.py','security.py'):
    (package/name).write_bytes((ROOT/'edgeone'/name).read_bytes())
(runtime/'app.py').unlink(missing_ok=True)
(package/'core.py').write_bytes((ROOT/'app.py').read_bytes())
(package/'__init__.py').write_text('')
(package/'resources.py').write_text('import json\nRESOURCES = json.loads('+repr(json.dumps(RESOURCES,ensure_ascii=False))+')\n')
for name in ('index.html','app.js','phonetics.js','style.css','favicon.svg'):
    (public/name).write_bytes((ROOT/'static'/name).read_bytes())
for name in ('login.html','login.js','cloud.js'):
    (public/name).write_bytes((ROOT/'cloudflare/static'/name).read_bytes())
html = (public/'index.html').read_text().replace('本地教材单词练习','在线教材单词练习').replace('本机学习者','已登录学习者')
html = html.replace('<script src="/app.js" defer></script>','<script src="/app.js" defer></script><script src="/cloud.js" defer></script>')
(public/'index.html').write_text(html)
media = public/'media/phonetics'
media.mkdir(parents=True)
for name in ('lesson.mp4','lesson.mp3'):
    (media/name).write_bytes((ROOT/'data/phonetics-media'/name).read_bytes())
ca = ROOT/'edgeone/mysql-ca.pem'
if ca.exists(): (package/'mysql-ca.txt').write_bytes(ca.read_bytes())
print('EdgeOne build:',len(RESOURCES['books']),'books; public assets + Python API; MySQL stores learning records.')

# Enterprise desktop encryption can expose different bytes to Python and Node.
# Verify only generated outputs; CI normally takes the no-change path.
import base64
import hashlib
import subprocess
files = []
for folder in (public, package):
    for path in folder.rglob('*'):
        if path.is_file():
            data = path.read_bytes()
            if data.startswith(b'%TSD-Header'): raise RuntimeError('Encrypted build input: '+str(path))
            files.append([str(path),base64.b64encode(data).decode(),hashlib.sha256(data).hexdigest()])
for name in ('phonetics.py','local_assessment.py'):
    path = runtime/name
    data = path.read_bytes()
    files.append([str(path),base64.b64encode(data).decode(),hashlib.sha256(data).hexdigest()])
subprocess.run(['node','-e', """
const fs=require('fs'),crypto=require('crypto');
for(const [p,b,hash] of JSON.parse(fs.readFileSync(0,'utf8'))){
 const digest=()=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
 if(digest()!==hash)fs.writeFileSync(p,Buffer.from(b,'base64'));
 if(digest()!==hash)throw new Error('Build byte verification failed: '+p);
}
"""],input=json.dumps(files).encode(),check=True)
print('Verified generated asset and runtime bytes:',len(files),'files')
