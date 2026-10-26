"""Build the offline IPA subset: python3 scripts/build_phonetics.py /path/to/en_US.txt"""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1])
dictionary = dict(line.split('\t', 1) for line in source.read_text().splitlines() if '\t' in line)
# Dictionary headwords absent from the upstream US list, checked against Cambridge.
extra = {'maths': '/mæθs/', 'mooncake': '/ˈmuːn.keɪk/', 'schoolbag': '/ˈskuːl.bæɡ/',
         'terracotta': '/ˌter.əˈkɑː.t̬ə/', 'pipa': '/ˌpiːˈpɑː/', 'westray': '/ˈwes.treɪ/'}
dictionary.update(extra)
dictionary['colourful'] = dictionary['colorful']
for acronym in ['BDS', 'PE', 'CPC']:
    dictionary[acronym.lower()] = '/' + ' '.join(dictionary[c.lower()].split(',')[0].strip('/') for c in acronym) + '/'
# Plain "read" is the present/base form; the app selects the past form by meaning.
dictionary['read'] = '/ˈɹid/'
# Select the senses used in these textbook glossaries (not unrelated proper names/nouns).
dictionary.update({'reading': '/ˈɹidɪŋ/', 'windy': '/ˈwɪndi/', 'wind': '/ˈwɪnd/',
                   'live': '/ˈɫɪv/', 'use': '/ˈjuz/', 'reuse': '/ɹiˈjuz/'})
words = sorted({w['english'].lower() for f in (ROOT / 'data/books').glob('*.json') for w in json.loads(f.read_text())['words']})
entries = {}
for word in words:
    if word in dictionary:
        entries[word] = dict(ipa=dictionary[word], note='美式参考')
    else:
        parts = re.findall(r"[a-z]+(?:'[a-z]+)?", word)
        missing = [p for p in parts if p not in dictionary]
        if not missing:
            entries[word] = dict(ipa=' '.join('/ə/' if p == 'a' else dictionary[p].split(',')[0] for p in parts), note='美式分词参考')
# The textbook does not give IPA for these Chinese place names: label pinyin explicitly.
for word, ipa in {
    'mount taishan': dictionary['mount'] + ' Tàishān',
    'jinggangshan revolution museum': 'Jǐnggāngshān ' + dictionary['revolution'] + ' ' + dictionary['museum'],
}.items():
    entries[word] = dict(ipa=ipa, note='分词参考 · 地名为拼音')
entries['turpan'] = dict(ipa='/ˈtuəˈpɑːn/', note='教材音标')
entries['taikonaut'] = dict(ipa='/ˈtaɪkəʊˌnɔːt/', note='英式参考')
assert set(entries) == set(words), sorted(set(words) - set(entries))
result = dict(source='https://github.com/open-dict-data/ipa-dict', dialect='en_US',
              source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), entries=entries)
(ROOT / 'data/phonetics.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print('Offline pronunciation entries:', len(entries))
