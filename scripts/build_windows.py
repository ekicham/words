#!/usr/bin/env python3
"""Build the Win7 x64 portable ZIP using only the Python standard library."""
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.4.1'
REVISION = 'r2'
NAME = 'WordIsle-%s-Win7-x64-%s' % (VERSION, REVISION)
RUNTIME_URL = 'https://www.python.org/ftp/python/3.8.10/python-3.8.10-embed-amd64.zip'
RUNTIME_SHA256 = 'abbe314e9b41603dde0a823b76f5bbbe17b3de3e5ac4ef06b759da5466711271'


def runtime_archive():
    archive = ROOT / '.build/windows/python-3.8.10-embed-amd64.zip'
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        with urllib.request.urlopen(RUNTIME_URL, timeout=60) as response:
            payload = response.read()
        if hashlib.sha256(payload).hexdigest() != RUNTIME_SHA256:
            raise ValueError('Python runtime checksum mismatch')
        archive.write_bytes(payload)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != RUNTIME_SHA256:
        raise ValueError('Cached Python runtime checksum mismatch: ' + str(archive))
    return archive


def build_package(build_dir, output_dir, archive):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != RUNTIME_SHA256:
        raise ValueError('Python runtime checksum mismatch')
    stage = build_dir / NAME
    if stage.exists(): shutil.rmtree(stage)
    stage.mkdir(parents=True)
    files = [ROOT / p for p in ('app.py', 'phonetics.py', 'local_assessment.py', 'windows/start.py',
                               'static/index.html', 'static/app.js', 'static/style.css', 'static/phonetics.js', 'static/favicon.svg',
                               'data/phonetics.json', 'data/phonetics-course.json',
                               'data/phonetics-media/lesson.mp4', 'data/phonetics-media/lesson.mp3')]
    files += sorted((ROOT / 'data/books').glob('*.json'))
    files += sorted(p for p in (ROOT / 'data/sources').rglob('*') if p.is_file() and p.suffix in ('.json', '.tsv', '.txt', '.md'))
    for source in files:
        target = stage / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    # ASCII entry also works with old ZIP tools that garble Chinese filenames.
    for name in ('Start-WordIsle.bat', '启动词屿.bat'):
        (stage / name).write_bytes((ROOT / '启动词屿.bat').read_text(encoding='utf-8').replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))
    (stage / '使用说明.txt').write_bytes(b'\xef\xbb\xbf' + (ROOT / 'windows/使用说明.txt').read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
    with zipfile.ZipFile(archive) as runtime:
        runtime.extractall(stage / 'runtime')
    (stage / 'runtime/python38._pth').write_text('python38.zip\n.\n..\n', encoding='ascii')
    manifest = dict(version=VERSION, revision=REVISION, target='Windows 7 SP1 x64', runtime_url=RUNTIME_URL, runtime_sha256=RUNTIME_SHA256,
                    files={str(p.relative_to(stage)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(stage.rglob('*')) if p.is_file()})
    (stage / 'build-info.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / ('词屿-%s-Windows7-x64-%s.zip' % (VERSION, REVISION))
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for source in sorted(stage.rglob('*')):
            if source.is_file(): bundle.write(source, source.relative_to(build_dir))
    (output_dir / 'SHA256SUMS.txt').write_text(hashlib.sha256(output.read_bytes()).hexdigest() + '  ' + output.name + '\n', encoding='utf-8')
    return output


if __name__ == '__main__':
    print(build_package(ROOT / '.build/windows/package', ROOT / 'dist/windows', runtime_archive()))
