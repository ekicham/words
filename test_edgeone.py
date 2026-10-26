"""Integration tests against a disposable MySQL 8 database, never production."""
import json
import os
from pathlib import Path
import secrets
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch


class EdgeOneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from edgeone.server import create_app
        filename = os.environ.get('WORDISLE_TEST_ENV')
        if not filename:
            raise unittest.SkipTest('set WORDISLE_TEST_ENV to a disposable MySQL test environment')
        cls.env = dict(line.split('=', 1) for line in Path(filename).read_text().splitlines() if '=' in line)
        assert cls.env['DB_NAME'].endswith('_test'), 'Tests require a dedicated _test database'
        cls.app = create_app(cls.env)
        cls.app.testing = True

    def setUp(self):
        self.client = self.app.test_client()
        self.username = 'test-' + secrets.token_hex(6)
        self.password = secrets.token_hex(16)
        self.ok('/api/auth/register', dict(username=self.username, password=self.password,
                                         invitation=self.env['REGISTRATION_CODE']))

    def call(self, path, body=None, client=None, origin=None):
        client = client or self.client
        return client.get(path) if body is None else client.post(path, json=body,
            headers={'Origin': origin or self.env['APP_ORIGIN']})

    def ok(self, path, body=None, client=None):
        response = self.call(path, body, client)
        self.assertEqual(response.status_code, 200, (path, response.get_json()))
        return response.get_json()

    def book(self):
        self.ok('/api/import', dict(id='edge-test', title='测试词库', publisher='测试', edition='测试',
            grade=3, term='上', source_url='https://example.com', words=[
                dict(english='Monday', meaning='星期一', unit='Unit 1'),
                dict(english='Tuesday', meaning='星期二', unit='Unit 1')]))

    def test_accounts_isolation_and_learning(self):
        stranger = self.app.test_client()
        self.assertEqual(self.call('/api/bootstrap', client=stranger).status_code, 401)
        self.assertEqual(self.call('/api/auth/login', {}, origin='https://evil.example').status_code, 403)
        self.assertEqual(self.call('/api/auth/login', dict(username=self.username, password='wrong-password-long'), stranger).status_code, 401)
        self.assertEqual(len(self.ok('/api/bootstrap')['books']), 17)
        self.book()
        state = self.ok('/api/start', dict(book_id='edge-test', learning_order='sequential'))
        sid = state['id']
        body = dict(position=0, answer='day', request_id='answer-1')
        self.assertEqual(self.ok('/api/session/'+sid+'/answer', body)['session']['stars'], 10)
        self.assertEqual(self.ok('/api/session/'+sid+'/answer', body)['session']['stars'], 10)
        self.assertEqual(self.ok('/api/completed-words?scope=today')['total'], 1)
        other = self.app.test_client()
        self.ok('/api/auth/register', dict(username='other-'+secrets.token_hex(6), password=self.password,
                invitation=self.env['REGISTRATION_CODE']), other)
        self.assertEqual(len(self.ok('/api/bootstrap', client=other)['books']), 17)
        self.assertEqual(self.call('/api/session/'+sid, client=other).status_code, 400)
        self.ok('/api/session/'+sid+'/finish', dict(position=1, request_id='finish'))
        self.assertEqual(self.ok('/api/session/'+sid+'/report')['first_correct'], 1)
        self.ok('/api/auth/logout', {})
        self.assertEqual(self.call('/api/bootstrap').status_code, 401)
        # A new Flask application/connection must see the same persistent records.
        from edgeone.server import create_app
        restored = create_app(self.env).test_client()
        self.ok('/api/auth/login', dict(username=self.username, password=self.password), restored)
        self.assertEqual(self.ok('/api/bootstrap', client=restored)['summary']['stars'], 10)

    def test_atomic_rollback_and_concurrent_rewards(self):
        self.book()
        state = self.ok('/api/start', dict(book_id='edge-test', learning_order='sequential'))
        sid = state['id']
        # Seed earned stars through domain operations, not by changing balances.
        from app import mask_word
        for i in range(80):
            answer = mask_word('Monday' if i % 2 == 0 else 'Tuesday')[1]
            self.ok('/api/session/'+sid+'/answer', dict(position=i, answer=answer, request_id='a-'+str(i)))
        revision = self.ok('/api/rewards/config')['revision']
        cookie = self.client.get_cookie('wordisle_session').value
        def draw(key):
            c = self.app.test_client()
            c.set_cookie('wordisle_session', cookie)
            r = self.call('/api/rewards/draw', dict(request_id=key, config_revision=revision), c)
            return r.status_code, r.get_json()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(draw, ['one', 'two']))
        self.assertEqual(sorted(r[0] for r in results), [200, 400])
        self.assertEqual(self.ok('/api/rewards')['wallet']['available'], 0)
        winner = next(r[1]['draw']['id'] for r in results if r[0] == 200)
        self.assertEqual(draw(winner)[0], 200)
        from edgeone.domain import EdgeApp
        original = EdgeApp.import_book
        def broken(app, pack):
            original(app, pack)
            raise ValueError('simulated failure after insertion')
        with patch.object(EdgeApp, 'import_book', broken):
            r = self.call('/api/import', dict(id='rollback', title='rollback', publisher='test', edition='test',
                grade=3, term='上', source_url='https://example.com', words=[dict(english='apple', meaning='苹果')]))
            self.assertEqual(r.status_code, 400)
        self.assertNotIn('rollback', [b['id'] for b in self.ok('/api/bootstrap')['books']])

    def test_dictation_and_phonetics(self):
        self.book()
        state = self.ok('/api/start', dict(book_id='edge-test', practice_type='dictation_en',
                                         dictation_mode='manual', learning_order='sequential'))
        sid = state['id']
        self.assertEqual(state['current']['phase'], 'listening')
        self.ok('/api/session/'+sid+'/ready', dict(position=0, request_id='ready'))
        for revision, answer in [(2,'Monday'), (1,'bad')]:
            self.ok('/api/session/'+sid+'/draft', dict(position=0, request_id='draft-'+str(revision), revision=revision, answer=answer))
        self.assertEqual(self.ok('/api/session/'+sid)['current']['draft'], 'Monday')
        self.ok('/api/session/'+sid+'/answer', dict(position=0, answer='Monday', request_id='answer'))
        self.ok('/api/session/'+sid+'/next', dict(position=0, request_id='next'))
        self.ok('/api/session/'+sid+'/finish', dict(position=1, request_id='finish'))
        self.assertEqual(self.ok('/api/session/'+sid+'/report')['dictation_correct'], 1)
        self.assertTrue(self.ok('/api/phonetics')['service']['cloud'])
        self.assertEqual(self.call('/api/phonetics/config', {'secret_key':'not-a-key'}).status_code, 400)
        from test_phonetics import recording
        # Provider mock is patched in the host only; never added to deploy artifacts.
        with patch.dict(self.app.config['WORDISLE_ENV'], TENCENT_SECRET_ID='fake', TENCENT_SECRET_KEY='fake'):
            state = self.ok('/api/phonetics/tests', dict(count=10, accent='uk', consent=True))
            prefix = '/api/phonetics/tests/'+state['id']
            data = dict(position=0, request_id='score', audio=recording())
            with patch('edgeone.server.assess', return_value={'score':88, 'request_id':'test'}) as provider:
                self.assertEqual(self.ok(prefix+'/assess', data)['position'], 1)
                self.assertEqual(self.ok(prefix+'/assess', data)['position'], 1)
                self.assertEqual(provider.call_count, 1)
            self.assertTrue(self.call(prefix+'/audio/0').data.startswith(b'RIFF'))
            self.ok(prefix+'/finish', {})
            self.ok(prefix+'/delete', {})


class SecurityTests(unittest.TestCase):
    def test_cookie_tampering_expiration_and_tenant_identifier(self):
        from edgeone.security import issue_session, verify_session, SESSION_SECONDS
        from edgeone.storage import Connection
        uid, secret = 'a'*32, 's'*40
        token = issue_session(uid,secret)
        self.assertEqual(verify_session(token,secret),uid)
        self.assertIsNone(verify_session('b'+token[1:],secret))
        self.assertIsNone(verify_session(token,'different-secret'))
        import time
        with patch('edgeone.security.time.time',return_value=time.time()+SESSION_SECONDS+1):
            self.assertIsNone(verify_session(token,secret))
        with self.assertRaises(ValueError): Connection(None,'x; DROP TABLE wi_accounts')

    def test_configuration_and_body_boundaries(self):
        from edgeone.server import create_app
        env = dict(AUTH_SECRET='s'*40,APP_ORIGIN='https://words.example.com',REGISTRATION_CODE='i'*20)
        client = create_app(env).test_client()
        headers = {'Origin':env['APP_ORIGIN']}
        response = client.post('/api/auth/register',json=dict(username='example',password='p'*16,invitation='i'*20),headers=headers)
        self.assertEqual(response.status_code,503)
        self.assertIn('DB_HOST',response.get_json()['error'])
        self.assertEqual(client.post('/api/auth/login',json={'oversized':'x'*5000},headers=headers).status_code,413)
        self.assertEqual(client.post('/api/auth/login',data='{',content_type='application/json',headers=headers).status_code,400)
        from edgeone.storage import Store, ConfigurationError
        with self.assertRaises(ConfigurationError):
            with Store(dict(DB_HOST='remote.example',DB_NAME='x',DB_USER='x',DB_PASSWORD='x',DB_TLS='0')).connect(): pass


if __name__ == '__main__': unittest.main()
