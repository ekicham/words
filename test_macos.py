"""Desktop packaging regression checks; all learning data uses temporary folders."""
import json
import os
import plistlib
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from app import App, ROOT, mask_word, serve


def request(url, body=None, headers=None):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 headers=headers or {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as response:
        data = response.read()
        return json.loads(data) if 'application/json' in response.headers['Content-Type'] else data


class DesktopChecks(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('WORD_ISLE_APP'), 'set WORD_ISLE_APP to verify a release bundle')
    def test_release_bundle_is_portable_and_has_no_learning_data(self):
        bundle = Path(os.environ['WORD_ISLE_APP']).resolve()
        info = plistlib.loads((bundle / 'Contents/Info.plist').read_bytes())
        self.assertEqual(info['LSMinimumSystemVersion'], '12.3')
        self.assertIn('NSMicrophoneUsageDescription', info)
        entitlements = plistlib.loads(subprocess.check_output(
            ['codesign', '-d', '--entitlements', ':-', str(bundle)], stderr=subprocess.DEVNULL))
        self.assertTrue(entitlements['com.apple.security.device.audio-input'])
        self.assertNotIn('com.apple.security.device.camera', entitlements)
        self.assertFalse(list(bundle.rglob('phonetics-service.json')), 'never bundle assessment credentials')
        self.assertFalse(list(bundle.rglob('*.sqlite3*')), 'a release must not contain personal learning data')
        self.assertFalse(any(path.name in ('audio', 'backups') for path in bundle.rglob('*')))
        binaries = []
        for path in bundle.rglob('*'):
            if path.is_file() and not path.is_symlink():
                with path.open('rb') as file:
                    magic = file.read(4)
                if magic in (b'\xca\xfe\xba\xbe', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf'):
                    binaries.append(path)
                    architectures = subprocess.check_output(['lipo', '-archs', str(path)], text=True).split()
                    expected = {'arm64'} if 'OpenPronounceEngine.app' in path.parts else {'arm64', 'x86_64'}
                    self.assertEqual(set(architectures), expected, str(path))
                    links = subprocess.check_output(['otool', '-L', str(path)], text=True)
                    self.assertNotIn('/Library/Frameworks/Python.framework', links)
                    self.assertNotIn('/Users/', '\n'.join(line for line in links.splitlines() if line.startswith('\t')))
        self.assertGreater(len(binaries), 10)
        self.assertTrue(list(bundle.rglob('OpenPronounceEngine')))
        self.assertFalse(list(bundle.rglob('pytorch_model.bin')), 'models are installed separately')
        self.assertTrue(list(bundle.rglob('libssl.3.dylib')))
        self.assertTrue(list(bundle.rglob('libcrypto.3.dylib')))
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(bundle)], check=True)

    def test_dynamic_port_host_validation_and_missing_voice(self):
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder) / 'words.sqlite3')
            server = serve(app, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = 'http://127.0.0.1:%s' % server.server_port
            try:
                self.assertEqual(len(request(url + '/api/bootstrap')['books']), 17)
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    request(url + '/api/bootstrap', headers={'Host': 'example.com'})
                self.assertEqual(rejected.exception.code, 403)
                with patch('app.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'say')):
                    self.assertTrue(request(url + '/api/audio/1')['fallback'])
                self.assertEqual(list((Path(folder) / 'audio').glob('*.wav')), [])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_desktop_lifecycle_and_restart_persistence(self):
        self.assertTrue((ROOT / 'macos/backend.py').is_file(), 'desktop backend is missing')
        command = shlex.split(os.environ['WORD_ISLE_BACKEND']) if os.environ.get('WORD_ISLE_BACKEND') else [
            sys.executable, str(ROOT / 'macos/backend.py')]
        with tempfile.TemporaryDirectory(prefix='word-isle-desktop-') as folder:
            folder = Path(folder)
            ready, db = folder / 'ready.json', folder / 'profile' / 'words.sqlite3'
            def start(parent=os.getpid()):
                ready.unlink(missing_ok=True)
                process = subprocess.Popen(command + ['--db', str(db), '--ready-file', str(ready),
                                            '--parent-pid', str(parent)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.addCleanup(lambda: process.poll() is None and process.kill())
                for _ in range(200):
                    if ready.exists():
                        state = json.loads(ready.read_text())
                        return process, 'http://127.0.0.1:%s' % state['port']
                    if process.poll() is not None:
                        self.fail(process.communicate()[0].decode())
                    time.sleep(.05)
                process.kill()
                self.fail('backend did not publish its port')

            process, url = start()
            bootstrap = request(url + '/api/bootstrap')
            self.assertEqual(len(bootstrap['books']), 17)
            self.assertEqual(sum(b['count'] for b in bootstrap['books']), 2048)
            self.assertIn('词屿', request(url).decode())
            lesson = request(url + '/api/phonetics')
            self.assertEqual(len(lesson['course']), 48)
            self.assertFalse(lesson['service']['configured'])
            self.assertEqual(lesson['history'], [])
            self.assertIn('requestFullscreen', request(url + '/phonetics.js').decode())
            video = request(url + '/media/phonetics/lesson.mp4', headers={'Range': 'bytes=0-31'})
            self.assertEqual(len(video), 32)
            self.assertEqual(video[4:8], b'ftyp')
            session = request(url + '/api/start', dict(book_id='pep-6-a', minutes=15, learning_order='sequential'))
            word = next(w for w in request(url + '/api/words?book_id=pep-6-a') if w['id'] == session['current']['word_id'])
            answer = request(url + '/api/session/' + session['id'] + '/answer',
                             dict(position=session['position'], request_id='desktop-test', answer=mask_word(word['english'])[1]))
            self.assertTrue(answer['correct'])
            for language in ('en', 'zh'):
                audio = request(url + '/api/audio/%s?lang=%s' % (word['id'], language))
                self.assertTrue(isinstance(audio, bytes) and audio.startswith(b'RIFF'), 'actual offline audio must play on build host')
            process.terminate()
            self.assertEqual(process.wait(timeout=10), 0)
            process.communicate()
            self.assertFalse(ready.exists())
            process, url = start()
            self.assertEqual(request(url + '/api/bootstrap')['summary']['completed_words'], 1)
            report = request(url + '/api/session/' + session['id'] + '/report')
            self.assertEqual(report['practice_completed'], 1)
            request(url + '/api/session/' + session['id'] + '/finish', dict(position=1, request_id='finish-hint'))
            for kind, control in [('dictation_en', 'auto'), ('dictation_zh', 'manual')]:
                s = request(url + '/api/start', dict(book_id='pep-6-a', minutes=15,
                            learning_order='sequential', practice_type=kind, dictation_mode=control, dictation_seconds=30))
                self.assertNotIn('meaning', s['current'])
                self.assertNotIn('phonetic', s['current'])
                endpoint = url + '/api/session/' + s['id']
                ready_state = request(endpoint + '/ready', dict(position=0, request_id='audio-ended'))['session']
                self.assertEqual(ready_state['dictation_mode'], control)
                self.assertEqual(ready_state['current']['phase'], 'writing')
                if control == 'auto':
                    self.assertGreater(ready_state['current']['writing_deadline'] - ready_state['now'], 29)
                else:
                    self.assertIsNone(ready_state['current']['writing_deadline'])
                answer = request(endpoint + '/answer', dict(position=0, request_id='dictated', answer=word['english']))
                self.assertEqual(answer['session']['current']['result'], 'correct')
                request(endpoint + '/finish', dict(position=0, request_id='finish-dictation'))
                report = request(endpoint + '/report')
                self.assertEqual((report['practice_type'], report['dictation_correct'], report['stars']), (kind, 1, 10))
            process.terminate()
            self.assertEqual(process.wait(timeout=10), 0)
            process.communicate()
            orphan, _ = start(parent=2147483647)
            self.assertEqual(orphan.wait(timeout=10), 0)
            orphan.communicate()
            self.assertFalse(ready.exists(), 'orphan backend must release its port and readiness file')


if __name__ == '__main__':
    unittest.main()
