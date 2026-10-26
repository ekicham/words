#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export DYLD_FRAMEWORK_PATH="$PWD/.build/macos/frameworks"
export DYLD_LIBRARY_PATH="$PWD/.build/macos/frameworks/Python.framework/Versions/3.13/lib"
PYTHON="$PWD/.build/openpronounce/venv/bin/python"
# Run build_macos.sh once first to provision the pinned CPython build runtime.
if [ ! -x "$PYTHON" ]; then
    .build/macos/venv/bin/python -m venv .build/openpronounce/venv
    "$PYTHON" -m pip install -r macos/openpronounce-requirements.txt
fi
"$PYTHON" - <<'PYCODE'
from pathlib import Path
import hashlib, importlib.metadata, json, os, shutil, tarfile, urllib.request
import certifi
os.environ['SSL_CERT_FILE']=certifi.where()
folder=Path('.build/openpronounce/notices');folder.mkdir(parents=True,exist_ok=True)
source=folder/'espeak-ng-1.52.0.tar.gz'
if not source.exists(): urllib.request.urlretrieve('https://github.com/espeak-ng/espeak-ng/archive/refs/tags/1.52.0.tar.gz',source)
with tarfile.open(source) as archive: (folder/'eSpeak-NG-GPL-3.0.txt').write_bytes(archive.extractfile('espeak-ng-1.52.0/COPYING').read())
for name,version in [('phonemizer','3.4.0')]:
    metadata=json.load(urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json'))
    entry=next(item for item in metadata['urls'] if item['packagetype']=='sdist');target=folder/entry['filename']
    if not target.exists(): urllib.request.urlretrieve(entry['url'],target)
    assert hashlib.sha256(target.read_bytes()).hexdigest()==entry['digests']['sha256']
for dist in importlib.metadata.distributions():
    for path in dist.files or []:
        if any(word in path.name.lower() for word in ('license','copying','notice')) and dist.locate_file(path).is_file():
            target=folder/'licenses'/dist.metadata['Name']/path.name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dist.locate_file(path),target)
for path in ['scripts/openpronounce_engine.py','macos/openpronounce.spec','macos/openpronounce-requirements.txt','scripts/build_openpronounce.sh']:
    shutil.copy2(path,folder/Path(path).name)
(folder/'README.txt').write_text('OpenPronounce helper source is provided under GPL-3.0-or-later for this combined component. Source, build script, pinned dependencies, eSpeak NG 1.52.0 release source and phonemizer source accompany it. OpenPronounce is MIT. Meta model cards state Apache-2.0; models are downloaded separately. No user data is embedded. See data/sources/openpronounce.md in the app content sources.\n')
PYCODE
"$PYTHON" -m PyInstaller --noconfirm --clean --distpath .build/openpronounce/dist --workpath .build/openpronounce/pyinstaller macos/openpronounce.spec
codesign --verify --deep --strict '.build/openpronounce/dist/OpenPronounceEngine.app'
