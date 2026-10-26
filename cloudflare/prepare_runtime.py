"""Verify bytes consumed by Node; normalize generated files on encrypted desktops.

Only generated build/vendor directories are touched. Source files are never edited.
"""
import base64
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
files = []
for folder in (root/'.cloudflare', root/'python_modules'):
    for path in folder.rglob('*'):
        if path.is_file():
            data = path.read_bytes()
            if data.startswith(b'%TSD-Header'):
                raise SystemExit('Cannot read normal bytes: '+str(path))
            files.append([str(path), base64.b64encode(data).decode(), hashlib.sha256(data).hexdigest()])
subprocess.run(['node','-e', '''
const fs=require('fs'),crypto=require('crypto');
for(const [p,b,hash] of JSON.parse(fs.readFileSync(0,'utf8'))){
 const digest=()=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
 if(digest()!==hash)fs.writeFileSync(p,Buffer.from(b,'base64'));
 if(digest()!==hash)throw new Error('Build byte verification failed: '+p);
}
'''], input=json.dumps(files).encode(), check=True)
print('Verified runtime and asset bytes:', len(files), 'files')
