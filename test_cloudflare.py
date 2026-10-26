import json
import tempfile
import unittest
from pathlib import Path
from app import App, ROOT

class ResourceTests(unittest.TestCase):
    def test_injected_resources_and_china_day(self):
        resources = {
            'phonetics': {'entries': {}}, 'textbook_phonetics': {}, 'course': [],
            'books': [json.loads((ROOT/'data/books/pep-3-a.json').read_text())],
        }
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder)/'test.db', resources=resources, day_offset_hours=8)
            self.assertEqual(len(app.bootstrap()['books']), 1)
            app.now = lambda: 1767198600  # 2025-12-31 16:30 UTC -> Jan 1 China
            self.assertEqual(app.completed_words('today')['date'], '2026-01-01')
            self.assertEqual(app.phonetics_lesson.course, [])

class AssessmentTests(unittest.TestCase):
    def test_two_phase_dedup_and_completion(self):
        from test_phonetics import recording
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder)/'test.db', seed=False)
            lesson = app.phonetics_lesson
            lesson.configure(dict(secret_id='AKIDtest', secret_key='secret-test'))
            test = lesson.start(dict(accent='uk', count=10, consent=True))
            body = dict(position=0, request_id='one', audio=recording())
            pending, result = lesson.begin_action(test['id'], 'assess', body)
            self.assertIsNone(result)
            self.assertTrue(pending['audio'])
            with self.assertRaisesRegex(ValueError, '正在评测'):
                lesson.begin_action(test['id'], 'assess', body)
            state = lesson.complete_assessment(pending, {'score': 90}, '')
            self.assertEqual(state['position'], 1)
            pending, state = lesson.begin_action(test['id'], 'assess', body)
            self.assertIsNone(pending)
            self.assertEqual(state['position'], 1)

class AuthTests(unittest.TestCase):
    def test_signed_sessions_reject_tampering_expiry_and_key_rotation(self):
        from cloudflare.auth import issue_session, verify_session
        token = issue_session('a'*32, 's'*32, now=100)
        self.assertEqual(verify_session(token, 's'*32, now=101), 'a'*32)
        self.assertIsNone(verify_session(token+'x', 's'*32, now=101))
        self.assertIsNone(verify_session(token, 't'*32, now=101))
        self.assertIsNone(verify_session(token, 's'*32, now=100+8*86400))
    def test_password_hash_and_account_validation(self):
        from cloudflare.auth import password_hash, valid_account
        self.assertEqual(password_hash('a strong password', '00'*16), password_hash('a strong password', '00'*16))
        self.assertNotEqual(password_hash('a strong password', '00'*16), password_hash('wrong password', '00'*16))
        self.assertTrue(valid_account('alice-1', 'long password 12'))
        self.assertFalse(valid_account('../alice', 'long password 12'))
        self.assertFalse(valid_account('alice', 'short'))

if __name__ == '__main__': unittest.main()
