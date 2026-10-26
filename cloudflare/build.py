"""Whitelist-only build: never copy learning databases, credentials or recordings."""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '.cloudflare'
if OUT.exists(): shutil.rmtree(OUT)
OUT.mkdir()
for name in ('app.py', 'phonetics.py', 'local_assessment.py'):
    shutil.copy2(ROOT/name, OUT/name)
for name in ('worker.py', 'storage.py', 'auth.py'):
    shutil.copy2(ROOT/'cloudflare'/name, OUT/name)
resources = {
    'phonetics': json.loads((ROOT/'data/phonetics.json').read_text()),
    'textbook_phonetics': dict(line.split('\t') for line in (ROOT/'data/sources/official/1212001601265-phonetics.tsv').read_text().splitlines()),
    'course': json.loads((ROOT/'data/phonetics-course.json').read_text()),
    'books': [json.loads(p.read_text()) for p in sorted((ROOT/'data/books').glob('*.json'))],
}
(OUT/'resources.py').write_text('import json\nRESOURCES = json.loads('+repr(json.dumps(resources, ensure_ascii=False))+')\n')
public = OUT/'public'
if public.exists(): shutil.rmtree(public)
public.mkdir()
for name in ('index.html','app.js','phonetics.js','style.css','favicon.svg'):
    shutil.copy2(ROOT/'static'/name, public/name)
for name in ('login.html','login.js','cloud.js'):
    shutil.copy2(ROOT/'cloudflare/static'/name, public/name)
html = (public/'index.html').read_text().replace('本地教材单词练习','在线教材单词练习').replace('本机学习者','已登录学习者')
html = html.replace('<script src="/app.js" defer></script>', '<script src="/app.js" defer></script><script src="/cloud.js" defer></script>')
(public/'index.html').write_text(html)
media = public/'media/phonetics'
media.mkdir(parents=True)
for name in ('lesson.mp4','lesson.mp3'): shutil.copy2(ROOT/'data/phonetics-media'/name, media/name)
print('Cloudflare build: %s books, static assets + Python modules; no personal data.' % len(resources['books']))
