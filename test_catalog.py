"""Official catalog completeness and preservation. Run: python3 test_catalog.py."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from app import App, ROOT, mask_word


class OfficialCatalog(unittest.TestCase):
    def test_official_books_keep_existing_learning(self):
        expected = {'1212001301245', '1212001302245', '1212001401255',
                    '1212001402255', '1212001501255', '1212001502255',
                    '1212001502145', '1212001601265'}
        packs = [json.loads(p.read_text()) for p in (ROOT / 'data/books').glob('pep-official-*.json')]
        self.assertEqual({p['id'].removeprefix('pep-official-') for p in packs}, expected)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'words.sqlite3'
            app = App(path, seed=False)
            old = json.loads((ROOT / 'data/books/pep-6-a.json').read_text())
            app.import_book(old)
            session = app.start(dict(book_id=old['id'], minutes=15))
            app.act(session['id'], 'answer', dict(position=0, answer='zzzz', request_id='old-answer'))
            def rows(table):
                with sqlite3.connect(path) as db:
                    return db.execute('SELECT * FROM ' + table + ' ORDER BY rowid').fetchall()
            preserved = {t: rows(t) for t in ['books', 'words', 'sessions', 'items', 'attempts', 'requests']}
            seeded = App(path)
            books = seeded.bootstrap()['books']
            self.assertEqual(len(books), 17)
            self.assertEqual(len({p['publisher'] for p in books}), 3)
            for table, before in preserved.items():
                after = rows(table)
                self.assertEqual(after[:len(before)], before, table + ' changed existing records')
            counts = {t: len(rows(t)) for t in preserved}
            App(path)
            self.assertEqual({t: len(rows(t)) for t in preserved}, counts, 'Restart duplicated records')
            six = next(p for p in packs if p['id'] == 'pep-official-1212001601265')
            self.assertEqual(len(six['words']), 144)
            self.assertEqual(len({w['unit'] for w in six['words']}), 6)
            self.assertIn('gingerbread house', {w['english'] for w in six['words']})
            self.assertIn('Unit 1 Amazing places', {w['unit'] for w in six['words']})
            self.assertEqual(len(old['words']), 147)

    def test_henan_fltrp_source_and_practice(self):
        pack = json.loads((ROOT / 'data/books/fltrp-4-a-2024-henan.json').read_text())
        self.assertEqual(pack['regions'], ['河南省'])
        self.assertEqual((pack['grade'], pack['term']), (4, '上'))
        self.assertIn('2024 审定', pack['edition'])
        groups = {}
        for word in pack['words']:
            groups.setdefault(word['unit'], []).append(word)
        self.assertEqual([len(v) for v in groups.values()], [29, 37, 26, 16, 26, 19, 10, 9])
        self.assertEqual([v[0]['english'] for v in groups.values()],
                         ['sport', 'phew', 'weather', 'season', 'bus', 'wheel', 'Terry Fox', 'take off'])
        words = {w['english']: w for w in pack['words']}
        self.assertEqual(words['fly']['unit'], 'Unit 4 Wonderful seasons')
        self.assertEqual(words['picnic']['unit'], "Unit 5 Let's go!")
        self.assertEqual(words['chug']['meaning'], '（汽车、火车等）突突地缓慢前进')
        self.assertEqual(words['across']['meaning'], '从一边到另一边；穿过，越过')
        self.assertEqual(words["I'm fine."]['page'], '92')
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder) / 'words.sqlite3', seed=False)
            self.assertEqual(app.import_book(pack)['count'], 172)
            for kind in ('hint', 'dictation_en', 'dictation_zh'):
                s = app.start(dict(book_id=pack['id'], province='河南省', minutes=15,
                                   learning_order='sequential', practice_type=kind))
                self.assertEqual(s['total'], 172)
                self.assertEqual(s['province'], '河南省')
                word = app.vocabulary(pack['id'])[0]
                self.assertEqual(app.speech(word['id'], 'en'), 'sport')
                self.assertEqual(app.speech(word['id'], 'zh'), '体育运动')
                if kind != 'hint':
                    app.act(s['id'], 'ready', dict(position=0, request_id='ready'))
                result = app.act(s['id'], 'answer', dict(position=0, request_id='answer',
                    answer=mask_word('sport')[1] if kind == 'hint' else 'sport'))
                if kind == 'hint':
                    self.assertTrue(result['correct'])
                else:
                    self.assertEqual(result['session']['current']['result'], 'correct')
                current = result['session']
                app.act(s['id'], 'finish', dict(position=current['position'], request_id='finish'))

    def test_read_pronunciation_follows_headword_tense(self):
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder) / 'words.sqlite3', seed=False)
            app.import_book(dict(id='pronunciation', title='读音核验', publisher='核验',
                                 edition='核验', grade=6, term='上', source_url='https://example.com',
                                 words=[dict(english='read', meaning='（过去式 read）阅读', unit='Unit 1'),
                                        dict(english='read', meaning='（read 的过去式）读', unit='Unit 2')]))
            words = app.vocabulary('pronunciation')
            self.assertEqual(app.speech(words[0]['id'], 'en'), 'read')
            self.assertEqual(app.speech(words[1]['id'], 'en'), 'red')


if __name__ == '__main__':
    unittest.main(verbosity=2)
