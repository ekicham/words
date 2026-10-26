"""Portable package checks on the build host; not Windows real-machine validation."""
import ast
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import zipfile

from scripts.build_windows import ROOT, RUNTIME_SHA256, runtime_archive, build_package


class WindowsPackageChecks(unittest.TestCase):
    def test_extracted_package_and_persistence(self):
        with tempfile.TemporaryDirectory(prefix='词屿 Windows 包 ') as folder:
            folder = Path(folder)
            archive = build_package(folder / 'build', folder / 'dist', runtime_archive())
            with zipfile.ZipFile(archive) as bundle:
                self.assertIsNone(bundle.testzip())
                bundle.extractall(folder / '解压 目录')
            root = next((folder / '解压 目录').iterdir())
            names = [str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()]
            for name in names:
                self.assertFalse(any(s in name for s in ('.sqlite3', 'phonetics-service.json', '__pycache__', 'backups/', 'data/audio/', '.build/')))
            self.assertEqual(len(list((root / 'data/books').glob('*.json'))), 17)
            self.assertEqual((root / 'runtime/python38._pth').read_text().splitlines(), ['python38.zip', '.', '..'])
            exe = (root / 'runtime/python.exe').read_bytes()
            pe = struct.unpack_from('<I', exe, 0x3c)[0]
            self.assertEqual(exe[pe:pe+4], b'PE\0\0')
            self.assertEqual(struct.unpack_from('<H', exe, pe+4)[0], 0x8664)
            for script in ('app.py', 'phonetics.py', 'local_assessment.py', 'windows/start.py'):
                ast.parse((root / script).read_text(encoding='utf-8'), feature_version=(3, 8))
            self.assertEqual(hashlib.sha256(runtime_archive().read_bytes()).hexdigest(), RUNTIME_SHA256)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            url = 'http://127.0.0.1:%s' % port
            env = dict(os.environ, LOCALAPPDATA=str(folder / '学生 数据'))
            log_path = folder / 'startup.log'
            def start():
                # Same redirected stdout/stderr as the Windows launcher: no console I/O.
                with log_path.open('ab') as log:
                    process = subprocess.Popen([sys.executable, '-X', 'utf8', str(root / 'windows/start.py'), '--no-browser', '--port', str(port)], env=env, stdout=log, stderr=subprocess.STDOUT)
                for _ in range(100):
                    if process.poll() is not None:
                        process.communicate()
                        self.fail(log_path.read_text(encoding='utf-8'))
                    try:
                        with urllib.request.urlopen(url + '/api/bootstrap', timeout=1) as response:
                            return process, json.load(response)
                    except OSError: time.sleep(.1)
                process.terminate(); process.communicate()
                self.fail('Extracted server did not start')
            def post(path, data):
                request = urllib.request.Request(url + path, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(request) as response: return json.load(response)
            def stop(process):
                process.terminate(); process.communicate(timeout=10)
            process, state = start()
            try:
                self.assertEqual(len(state['books']), 17)
                self.assertEqual(sum(b['count'] for b in state['books']), 2048)
                session = post('/api/start', dict(book_id='fltrp-4-a-2024-henan', minutes=15, province='河南省', mode='learn', learning_order='sequential', practice_type='dictation_en', dictation_mode='manual'))
                post('/api/session/' + session['id'] + '/ready', dict(position=0, request_id='ready'))
                post('/api/session/' + session['id'] + '/draft', dict(position=0, answer='test', revision=1, request_id='draft'))
                duplicate = subprocess.run([sys.executable, '-X', 'utf8', str(root / 'windows/start.py'), '--no-browser', '--port', str(port)], env=env, capture_output=True, timeout=10)
                self.assertEqual(duplicate.returncode, 0)
                self.assertIn('已经运行', duplicate.stdout.decode('utf-8'))
                with urllib.request.urlopen(urllib.request.Request(url + '/media/phonetics/lesson.mp4', headers={'Range': 'bytes=0-31'})) as response:
                    self.assertEqual((response.status, len(response.read())), (206, 32))
            finally: stop(process)
            process, restored = start()
            try:
                self.assertEqual(restored['active']['id'], session['id'])
                self.assertEqual(restored['active']['current']['draft'], 'test')
                self.assertTrue((folder / '学生 数据/WordIsleWeb/words.sqlite3').is_file())
                self.assertFalse(list((root / 'data').glob('*.sqlite3*')))
                self.assertIn('词屿 1.4.1 已启动', log_path.read_text(encoding='utf-8'))
                self.assertIn('学生 数据', log_path.read_text(encoding='utf-8'))
                with log_path.open('ab') as log:
                    conflict = subprocess.run([sys.executable, '-X', 'utf8', str(root / 'windows/start.py'), '--no-browser', '--port', str(port)],
                                              env=dict(env, LOCALAPPDATA=str(folder / '另一个用户')), stdout=log, stderr=subprocess.STDOUT, timeout=10)
                self.assertNotEqual(conflict.returncode, 0)
                self.assertIn('端口 %s 已被其他程序使用' % port, log_path.read_text(encoding='utf-8'))
            finally: stop(process)


if __name__ == '__main__': unittest.main()
