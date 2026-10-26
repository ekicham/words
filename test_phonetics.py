"""IPA course, real protocol boundary, persistence and media HTTP contracts."""
import base64
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error
import wave

from app import App, ROOT, serve
from phonetics import assess, parse_assessment, signed_request


def recording():
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        wav.writeframes(b'\x01\x00' * 16000)
    return base64.b64encode(output.getvalue()).decode()


class PhoneticsChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = App(Path(self.tmp.name) / 'words.sqlite3', seed=False)
        self.lesson = self.app.phonetics_lesson

    def test_course_and_service_secrets(self):
        course = self.lesson.overview()['course']
        self.assertEqual(len(course), 48)
        for item in course:
            self.assertNotEqual(item['uk']['audio'], item['us']['audio'])
            for accent in ('uk', 'us'):
                self.assertTrue(item[accent]['phones'])
                self.assertTrue(item[accent]['audio'].startswith('https://dictionary.cambridge.org/media/'))
        self.lesson.configure(dict(secret_id='AKIDtest', secret_key='secret-test'))
        self.assertTrue(self.lesson.overview()['service']['configured'])
        self.assertNotIn('secret-test', json.dumps(self.lesson.overview()))
        self.assertEqual(self.lesson.config_path.stat().st_mode & 0o777, 0o600)

    def test_assessment_dedup_failure_restart_report(self):
        with self.assertRaises(ValueError): self.lesson.start(dict(accent='uk', count=10, consent=True))
        self.lesson.configure(dict(secret_id='AKIDtest', secret_key='secret-test'))
        with self.assertRaises(ValueError): self.lesson.start(dict(accent='uk', count=10))
        state = self.lesson.start(dict(accent='us', count=10, consent=True))
        body = dict(position=0, request_id='first', audio=recording())
        with patch('phonetics.assess', side_effect=ValueError('服务不可用')):
            state = self.lesson.act(state['id'], 'assess', body)
        self.assertEqual(state['position'], 0)
        self.assertIsNone(state['mean'])
        self.assertEqual(state['results'][0]['status'], 'error')
        result = dict(score=88.5, raw_score=88.5, phones=[], request_id='cloud-request')
        body['request_id'] = 'retry'
        with patch('phonetics.assess', return_value=result) as cloud:
            state = self.lesson.act(state['id'], 'assess', body)
            again = self.lesson.act(state['id'], 'assess', body)
        self.assertEqual(cloud.call_count, 1)
        self.assertEqual(again['position'], 1)
        self.assertEqual(state['mean'], 88.5)
        state = self.lesson.act(state['id'], 'skip', dict(position=1))
        state = self.lesson.act(state['id'], 'finish', {})
        self.assertEqual((state['scored'], state['skipped'], state['remaining']), (1, 1, 8))
        self.assertEqual(state['mean'], 88.5)
        restored = App(self.app.path, seed=False).phonetics_lesson.state(state['id'])
        self.assertEqual(restored, state)

    def test_config_replace_closes_temporary_file_first(self):
        # Windows cannot replace or delete the still-open temporary file.
        handles = []
        create, replace = tempfile.NamedTemporaryFile, Path.replace
        def temporary(*args, **kwargs):
            handle = create(*args, **kwargs)
            handles.append(handle)
            return handle
        def closed_replace(source, target):
            self.assertTrue(all(handle.closed for handle in handles))
            return replace(source, target)
        with patch('phonetics.tempfile.NamedTemporaryFile', side_effect=temporary), patch.object(Path, 'replace', closed_replace):
            self.lesson.configure(dict(secret_id='AKIDtest', secret_key='secret-test'))
            self.lesson.configure(dict(provider='tencent'))
        self.assertEqual(self.lesson.config()['secret_key'], 'secret-test')

    def test_protocol_scores_and_bad_audio(self):
        parsed = parse_assessment({'Response': {'PronAccuracy': -1, 'RequestId': 'r', 'Words': []}})
        self.assertEqual((parsed['score'], parsed['raw_score']), (0, -1))
        for payload in ({'Response': {'Error': {'Code': 'AuthFailure', 'Message': 'SECRET'}}},
                        {'Response': {}}, {'Response': {'PronAccuracy': 999}}):
            with self.assertRaises(ValueError): parse_assessment(payload)
        req = signed_request({'secret_id': 'AKIDtest', 'secret_key': 'test'}, {'a': 1}, 1600000000)
        self.assertEqual(req.get_header('X-tc-action'), 'TransmitOralProcessWithInit')
        self.assertIn('SignedHeaders=content-type;host', req.get_header('Authorization'))
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return b'{"Response":{"PronAccuracy":92,"Words":[]}}'
        with patch('phonetics.urllib.request.urlopen', return_value=Response()) as remote:
            result = assess({'secret_id': 'AKIDtest', 'secret_key': 'test'}, {'phones': ['ih','r']}, base64.b64decode(recording()), 1600000000)
        sent = json.loads(remote.call_args.args[0].data)
        self.assertEqual(json.loads(sent['RefText']), {'wordList': [{'word':'ih-r','pron':[['ih','r']]}]})
        self.assertEqual([sent[k] for k in ('WorkMode','EvalMode','TextMode','VoiceFileType','VoiceEncodeType')], [1,0,1,2,1])
        self.assertEqual(result['score'],92)
        self.lesson.configure(dict(secret_id='AKIDtest', secret_key='test'))
        state = self.lesson.start(dict(accent='uk', count=10, consent=True))
        with patch('phonetics.assess') as cloud:
            with self.assertRaises(ValueError):
                self.lesson.act(state['id'], 'assess', dict(position=0, request_id='bad', audio='not-wav'))
            cloud.assert_not_called()

    def test_inflight_blocks_duplicate_finish_and_delete(self):
        self.lesson.configure(dict(secret_id='AKIDtest', secret_key='test'))
        state = self.lesson.start(dict(accent='uk',count=48,consent=True))
        entered, release = threading.Event(), threading.Event()
        def pending(*args):
            entered.set()
            release.wait(5)
            return dict(score=90, raw_score=90, phones=[], request_id='cloud')
        body=dict(position=0,request_id='one',audio=recording())
        with patch('phonetics.assess', side_effect=pending) as cloud:
            thread=threading.Thread(target=self.lesson.act,args=(state['id'],'assess',body));thread.start()
            self.assertTrue(entered.wait(5))
            try:
                for action in ('assess','skip','finish','delete'):
                    with self.assertRaises(ValueError): self.lesson.act(state['id'],action,body)
            finally:
                release.set();thread.join()
            self.lesson.act(state['id'],'assess',body)
            self.assertEqual(cloud.call_count,1)
        self.lesson.act(state['id'],'delete',{})
        with self.assertRaises(ValueError): self.lesson.state(state['id'])

    def test_media_range_head_and_origin(self):
        server = serve(self.app, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = 'http://127.0.0.1:%s' % server.server_port
            media = ROOT / 'data/phonetics-media/lesson.mp4'
            with urllib.request.urlopen(urllib.request.Request(url + '/media/phonetics/lesson.mp4', headers={'Range': 'bytes=0-31'})) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.read(), media.read_bytes()[:32])
            with urllib.request.urlopen(urllib.request.Request(url + '/media/phonetics/lesson.mp4', method='HEAD')) as response:
                self.assertEqual(int(response.headers['Content-Length']), media.stat().st_size)
                self.assertEqual(response.read(), b'')
            for path, headers, status in [('/media/phonetics/lesson.mp4', {'Range': 'bytes=999999999-'}, 416),
                                          ('/api/phonetics', {'Host': 'evil.example'}, 403),
                                          ('/media/phonetics/../words.sqlite3', {}, 404)]:
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(urllib.request.Request(url + path, headers=headers))
                self.assertEqual(error.exception.code, status)
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
