"""Run: python3 test_app.py. Uses a temporary database, never learning data."""
import json
from pathlib import Path
import tempfile
import unittest


class LearningFlow(unittest.TestCase):
    def test_completed_words_deduplicate_and_use_actual_completion_date(self):
        import time
        from app import App, mask_word
        with tempfile.TemporaryDirectory() as directory:
            midnight = time.mktime((2026, 9, 26, 0, 0, 0, 0, 0, -1))
            clock = [midnight - 30]
            app = App(Path(directory) / 'completed.sqlite3', now=lambda: clock[0], seed=False)
            pack = dict(id='first', title='原版教材', publisher='测试社', edition='原版', grade=6,
                term='上', source_url='https://example.com/book', words=[
                    dict(english='Monday', meaning='星期一', unit='Unit 1'),
                    dict(english='science', meaning='科学', unit='Unit 1'),
                    dict(english='Tuesday', meaning='星期二', unit='Unit 1'),
                    dict(english='Monday', meaning='星期一（复习）', unit='Unit 2')])
            app.import_book(pack)
            app.import_book(dict(pack, id='second', title='新版教材', edition='新版', grade=5, term='下',
                                 words=[dict(english='monday', meaning='周一', unit='Unit 3')]))
            self.assertEqual(app.bootstrap()['summary'].get('completed_words'), 0)
            self.assertEqual(app.completed_words()['words'], [])
            with self.assertRaises(ValueError): app.completed_words('invalid')
            requests = []
            s = app.start(dict(book_id='first', learning_order='sequential', province='浙江省'))
            def act(action, **extra):
                nonlocal s
                payload = dict(position=s['position'], request_id=str(len(requests)), **extra)
                requests.append((action, payload))
                s = app.act(s['id'], action, payload)['session']
            def solve():
                word = next(w for w in app.vocabulary(s['book_id']) if w['id'] == s['current']['word_id'])
                act('answer', answer=mask_word(word['english'])[1])
            solve()  # Monday before midnight, active session counts immediately.
            self.assertEqual(app.bootstrap()['summary']['today_words'], 1)
            clock[0] = midnight
            solve()  # science belongs to the new day, though session started yesterday.
            self.assertEqual(app.bootstrap()['summary']['today_words'], 1)
            self.assertEqual(app.completed_words('today')['words'][0]['english'], 'science')
            act('skip')  # Tuesday is not completed.
            act('answer', answer='zzzz'); act('hint'); solve()  # Same spelling, different unit.
            app.act(s['id'], *requests[-1])  # Lost-response replay cannot increase frequency.
            act('skip'); solve()  # Round two: hinted Monday now independently solved.
            self.assertEqual(s['round_number'], 3)
            act('finish')
            clock[0] += 10
            s = app.start(dict(book_id='second', learning_order='sequential', province='江苏省'))
            solve()  # Same word in a new textbook/case/grade/term/province, still active.
            act('answer', answer='zzzz')  # A new failed encounter does not increase completed frequency.
            before = app.report(s['id'])
            all_words = app.completed_words()
            today = app.completed_words('today')
            summary = app.bootstrap()['summary']
            self.assertEqual((all_words['total'], today['total'], summary['completed_words'], summary['today_words']), (2, 2, 2, 2))
            monday = next(w for w in all_words['words'] if w['english'].lower() == 'monday')
            self.assertEqual(monday['frequency'], 4)
            self.assertEqual(len(monday['sources']), 3)
            self.assertEqual(monday['completed_at'], clock[0])
            self.assertEqual({(x['unit'], x['term'], x['grade'], x['book'], x['province']) for x in monday['sources']},
                             {('Unit 1', '上', 6, '原版教材', '浙江省'), ('Unit 2', '上', 6, '原版教材', '浙江省'), ('Unit 3', '下', 5, '新版教材', '江苏省')})
            self.assertTrue(all(x['phonetic'] and x['meaning'] for x in monday['sources']))
            self.assertEqual(next(w for w in today['words'] if w['english'].lower() == 'monday')['frequency'], 3)
            self.assertEqual(app.report(s['id']), before, 'Detail reads must not change learning records')
            clock[0] += 86400
            self.assertEqual(app.completed_words('today')['total'], 0)
            self.assertEqual(app.bootstrap()['summary']['completed_words'], 2)

    def test_focus_rounds_prioritize_mistakes_without_changing_first_pass(self):
        from app import App, mask_word
        for order in ('sequential', 'random'):
            with self.subTest(order=order), tempfile.TemporaryDirectory() as directory:
                clock = [1000.0]
                path = Path(directory) / 'rounds.sqlite3'
                app = App(path, now=lambda: clock[0], seed=False)
                app.import_book(dict(id='rounds', title='循环', publisher='测试', edition='测试', grade=6,
                    term='上', source_url='https://example.com/book', words=[
                        dict(english=w, meaning='释义', unit=unit) for w, unit in
                        [('electricity', 'Unit 10'), ('Monday', 'Unit 1'), ('science', 'Unit 1'), ('bookstore', 'Unit 1')]]))
                words = {w['id']: w for w in app.vocabulary('rounds')}
                s = app.start(dict(book_id='rounds', unit='Unit 1', minutes=1, learning_order=order))
                sid, deadline, seen = s['id'], s['deadline'], []
                def act(action, **extra):
                    nonlocal s
                    payload = dict(position=s['position'], request_id=str(len(requests)), **extra)
                    requests.append((action, payload))
                    s = app.act(sid, action, payload)['session']
                def solve():
                    act('answer', answer=mask_word(words[s['current']['word_id']]['english'])[1])
                requests = []
                for i in range(3):
                    seen.append(s['current']['word_id'])
                    if i == 1: act('answer', answer='zzzz')
                    if i == 2: act('hint')
                    solve()
                self.assertEqual(s['status'], 'active')
                self.assertEqual((s['round_number'], s['round_total'], s['round_position']), (2, 2, 0))
                self.assertEqual(s['deadline'], deadline)
                baseline = app.report(sid)
                self.assertEqual((baseline['total'], baseline['attempted'], baseline['first_correct'], baseline['second_correct']), (3, 3, 1, 1))
                self.assertEqual(app.act(sid, *requests[-1])['session'], s, 'Boundary request must not append twice')
                self.assertEqual(App(path, now=lambda: clock[0], seed=False).state(sid), s)
                weak = []
                for _ in range(2):
                    weak.append(s['current']['word_id'])
                    solve()
                self.assertEqual(set(weak), set(seen[1:]))
                if order == 'sequential': self.assertEqual(weak, seen[1:])
                self.assertEqual((s['round_number'], s['round_total']), (3, 3))
                self.assertEqual(app.mistakes(), [])
                report = app.report(sid)
                for key in ('total', 'attempted', 'first_correct', 'second_correct', 'first_wrong', 'hinted', 'skipped', 'remaining'):
                    self.assertEqual(report[key], baseline[key], key)
                self.assertEqual((report['solved'], report['practice_completed'], report['reinforcement_solved'], report['rounds_completed']), (3, 5, 2, 2))
                self.assertEqual([w['round_number'] for w in report['words']], [1, 1, 1, 2, 2])
                self.assertEqual(app.state(sid, 0)['current']['word_id'], seen[0])
                with self.assertRaises(ValueError): app.act(sid, 'skip', dict(position=2, request_id='stale'))
                repeated = []
                for _ in range(3):
                    repeated.append(s['current']['word_id'])
                    act('skip')
                self.assertEqual(set(repeated), set(seen))
                self.assertEqual(s['round_total'], 3)
                if order == 'sequential': self.assertEqual(repeated, seen)
                clock[0] = deadline
                act('answer', answer='late')
                self.assertEqual(s['status'], 'timeout')
                self.assertEqual(app.report(sid)['elapsed'], 60)
                self.assertEqual(s['total'], 11, 'Timeout must not enqueue more words')
                # Review must keep its initial subset and one-word rounds must also continue.
                review = app.start(dict(book_id='rounds', mode='review', minutes=1))
                self.assertEqual(review['scope_total'], 3)
                app.act(review['id'], 'finish', dict(position=0, request_id='finish'))
                s = app.start(dict(book_id='rounds', unit='Unit 10', minutes=1))
                sid = s['id']; solve()
                self.assertEqual((s['round_number'], s['round_total']), (2, 1))
                clock[0] = s['deadline']
                solve()
                self.assertEqual((s['status'], s['position'], s['total']), ('timeout', 1, 2))

    def test_word_navigation_does_not_change_results(self):
        from app import App, mask_word
        with tempfile.TemporaryDirectory() as directory:
            app = App(Path(directory) / 'test.sqlite3', now=lambda: 1000)
            s = app.start(dict(book_id='pep-official-1212001601265', learning_order='sequential'))
            self.assertEqual(s['current']['phonetic'], '/wəz/')
            words = {w['id']: w for w in app.vocabulary(s['book']['id'])}
            # Full glossary overrides follow the book's common phonemic notation.
            word = next(w for w in words.values() if w['english']=='Terracotta Warriors')
            self.assertEqual(app.phonetic(word)['phonetic'], '/ˌterəˈkɒtə ˈwɒriəz/')
            first = s['current']['word_id']
            app.act(s['id'], 'answer', dict(position=0, answer=mask_word(words[first]['english'])[1], request_id='first'))
            before = app.report(s['id'])
            previous = app.state(s['id'], 0)
            self.assertEqual(previous['position'], 1)
            self.assertEqual(previous['view_position'], 0)
            self.assertTrue(previous['readonly'])
            self.assertEqual(previous['current']['word_id'], first)
            self.assertEqual(previous['current']['reveal'], words[first]['english'])
            self.assertEqual(app.report(s['id']), before)
            current = app.state(s['id'], 1)
            self.assertFalse(current['readonly'])
            self.assertEqual(current['stars'], previous['stars'])
            for position in [-1, 2, True, '0']:
                with self.assertRaises(ValueError): app.state(s['id'], position)
            with self.assertRaises(ValueError):
                app.act(s['id'], 'answer', dict(position=0, answer='was', request_id='do-not-recount'))
            app.act(s['id'], 'skip', dict(position=1, request_id='next'))
            app.state(s['id'], 0)
            self.assertEqual(app.report(s['id'])['attempted'], 1)
            self.assertEqual(app.report(s['id'])['skipped'], 1)

    def test_learning_order_and_offline_phonetics(self):
        from app import App
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.sqlite3'
            app = App(path, seed=False)
            app.import_book(dict(id='order', title='顺序测试', publisher='测试', edition='测试', grade=6,
                term='上', source_url='https://example.com/book', words=[
                    dict(english='electricity', meaning='电', unit='Unit 10'),
                    dict(english='Monday', meaning='星期一', unit='Unit 1'),
                    dict(english='post office', meaning='邮局', unit='Unit 1'),
                    dict(english='read', meaning='（read 的过去式）读', unit='Unit 2')]))
            for bad in ['other', '', None, 1, True]:
                with self.assertRaises(ValueError):
                    app.start(dict(book_id='order', learning_order=bad))
            s = app.start(dict(book_id='order', learning_order='sequential'))
            self.assertEqual(s['learning_order'], 'sequential')
            self.assertTrue(s['current']['phonetic'])
            with app.db() as db:
                actual = [r[0] for r in db.execute('SELECT w.english FROM items i JOIN words w ON w.id=i.word_id WHERE session_id=? ORDER BY position', (s['id'],))]
            self.assertEqual(actual, ['Monday', 'post office', 'read', 'electricity'])
            self.assertEqual(App(path, seed=False).state(s['id'])['current'], s['current'])
            app.act(s['id'], 'skip', dict(position=0, request_id='skip'))
            self.assertEqual(app.state(s['id'])['current']['phonetic_note'], '美式分词参考')
            app.act(s['id'], 'skip', dict(position=1, request_id='skip2'))
            self.assertEqual(app.state(s['id'])['current']['phonetic'], '/ˈrɛd/')
            app.act(s['id'], 'finish', dict(position=2, request_id='finish'))
            s = app.start(dict(book_id='order', learning_order='random'))
            with app.db() as db:
                ids = [r[0] for r in db.execute('SELECT word_id FROM items WHERE session_id=?', (s['id'],))]
            self.assertEqual(len(set(ids)), 4)
            self.assertEqual(s['learning_order'], 'random')
            # Existing sessions created before this feature keep their order and default to random.
            original = app.report(s['id'])
            with app.db() as db:
                db.execute('ALTER TABLE sessions DROP COLUMN learning_order')
                db.execute('ALTER TABLE items DROP COLUMN round_number')
            migrated = App(path, seed=False)
            self.assertEqual(migrated.state(s['id'])['learning_order'], 'random')
            self.assertEqual(migrated.report(s['id']), original)
        with tempfile.TemporaryDirectory() as directory:
            app = App(Path(directory) / 'all.sqlite3')
            expected = {'reading a book': '/ˈridɪŋ/ /ə/ /ˈbʊk/', 'windy': '/ˈwɪndi/',
                        'wind': '/ˈwɪnd/', 'live': '/ˈlɪv/', 'use': '/ˈjuz/', 'reuse': '/riˈjuz/'}
            for english, ipa in expected.items():
                self.assertEqual(app.phonetic(dict(english=english, meaning='教材义项'))['phonetic'], ipa)
            for book in app.bootstrap()['books']:
                for word in app.vocabulary(book['id']):
                    self.assertTrue(app.phonetic(word)['phonetic'], word['english'])

    def test_learning_and_persistence(self):
        self.assertTrue(Path(__file__).with_name('app.py').exists(), 'Learning app is not implemented')
        from app import App, letters, mask_word, province_from_geo
        self.assertEqual(mask_word('Monday'), ('Mon___', 'day'))
        self.assertEqual(mask_word('by'), ('b_', 'y'))
        self.assertEqual(letters('ice officer'), 'iceofficer')
        self.assertEqual(province_from_geo({'country_code': 'CN', 'region': 'Zhejiang'}), '浙江省')
        self.assertEqual(province_from_geo({'country_code': 'US', 'region': 'Zhejiang'}), '')
        with tempfile.TemporaryDirectory() as directory:
            clock = [1000.0]
            app = App(Path(directory) / 'test.sqlite3', now=lambda: clock[0], seed=False)
            pack = dict(id='fixture', title='验收词库', publisher='测试出版社', edition='测试版',
                        grade=6, term='上', source_url='https://example.com/book', regions=['浙江省'],
                        words=[dict(english=w, meaning='释义', unit='Unit 1', page=1)
                               for w in ['Monday', 'science', 'bookstore', 'post office']])
            app.import_book(pack)
            with self.assertRaises(ValueError):
                app.import_book(pack)
            bad = dict(pack, id='invalid', words=[dict(english='<script>', meaning='错误')])
            with self.assertRaises(ValueError):
                app.import_book(bad)
            self.assertEqual(len(app.bootstrap()['books']), 1)
            for bad_minutes in [0, -1, 181, 'abc', True]:
                with self.assertRaises(ValueError):
                    app.start(dict(book_id='fixture', minutes=bad_minutes, province='浙江省'))
            with self.assertRaises(ValueError):
                app.start(dict(book_id='fixture', minutes=15, unit='missing'))
            s = app.start(dict(book_id='fixture', minutes=15, province='浙江省'))
            sid = s['id']
            self.assertNotIn('english', s['current'])
            self.assertNotIn('answer', s['current'])
            self.assertEqual(app.bootstrap()['active']['id'], sid)
            seen = []
            def answer_for(state):
                with app.db() as db:
                    word = db.execute('SELECT english FROM words WHERE id=?', (state['current']['word_id'],)).fetchone()[0]
                return mask_word(word)[1]
            seen.append(s['current']['word_id'])
            first = dict(position=0, answer=answer_for(s), request_id='first-try')
            r = app.act(sid, 'answer', first)
            self.assertTrue(r['correct'])
            self.assertEqual(r['session']['position'], 1)
            self.assertEqual(app.act(sid, 'answer', first), r, 'Retry must not count or advance twice')
            with self.assertRaises(ValueError):
                app.act(sid, 'answer', dict(first, request_id='stale'))
            s = r['session']; seen.append(s['current']['word_id'])
            wrong = app.act(sid, 'answer', dict(position=1, answer='z' * s['current']['missing'], request_id='wrong'))
            self.assertFalse(wrong['correct'])
            r = app.act(sid, 'answer', dict(position=1, answer=answer_for(s), request_id='second'))
            s = r['session']; seen.append(s['current']['word_id'])
            r = app.act(sid, 'hint', dict(position=2, request_id='hint'))
            self.assertIn('reveal', r)
            r = app.act(sid, 'answer', dict(position=2, answer=answer_for(s), request_id='hint-correct'))
            s = r['session']; seen.append(s['current']['word_id'])
            r = app.act(sid, 'skip', dict(position=3, request_id='skip'))
            self.assertEqual(len(set(seen)), 4)
            self.assertEqual(r['session']['status'], 'active')
            self.assertEqual(r['session']['round_total'], 3)
            app.act(sid, 'finish', dict(position=4, request_id='finish'))
            report = app.report(sid)
            self.assertEqual(report['attempted'], 3)
            self.assertEqual(report['first_correct'], 1)
            self.assertEqual(report['second_correct'], 1)
            self.assertEqual(report['first_wrong'], 1)
            self.assertEqual(report['hinted'], 1)
            self.assertEqual(report['skipped'], 1)
            self.assertEqual(report['remaining'], 0)
            self.assertEqual(len(app.mistakes()), 3)
            restored = App(Path(directory) / 'test.sqlite3', now=lambda: clock[0], seed=False)
            self.assertEqual(restored.report(sid), report)
            self.assertEqual(len(restored.bootstrap()['history']), 1)
            review = app.start(dict(book_id='fixture', minutes=1, mode='review'))
            self.assertEqual(review['total'], 3)
            clock[0] += 61
            expired = app.act(review['id'], 'answer', dict(position=0, answer='abc', request_id='late'))
            self.assertEqual(expired['session']['status'], 'timeout')
            self.assertEqual(app.report(review['id'])['attempted'], 0)
            self.assertEqual(app.report(review['id'])['remaining'], 3)
            self.assertEqual(len(app.mistakes()), 3, 'Unseen words must not clear mistakes')
            retry_session = app.start(dict(book_id='fixture', minutes=1, mode='review'))
            retry_payload = dict(position=0, answer='zzzz', request_id='lost-response')
            app.act(retry_session['id'], 'answer', retry_payload)
            clock[0] += 61
            replay = app.act(retry_session['id'], 'answer', retry_payload)
            self.assertEqual(replay['session']['status'], 'timeout', 'Replaying a saved response must use the current deadline')
            self.assertEqual(app.report(retry_session['id'])['attempted'], 1)
            self.assertTrue(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    unittest.main(verbosity=2)
