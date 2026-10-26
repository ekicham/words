"""Private OpenPronounce child process. No port, external endpoint or cloud fallback."""
import atexit
import base64
import json
import math
import os
from pathlib import Path
import platform
import queue
import subprocess
import sys
import threading

ENGINE = 'OpenPronounce 0.3.0 本地例词参考评测'
NOTICE = '请读完整例词。本地分数评价整个例词，不是单独音标的准确率；引擎使用美式音素规则，英美切换用于示范，不作口音鉴定。儿童、短词和噪声可能导致误判，请结合回听判断。录音不上传。'


def parse_result(payload, example):
    score = payload.get('score')
    if isinstance(score, bool) or not isinstance(score, (float, int)) or not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError('本地引擎未返回有效分数，本次不计分。')
    diff = payload.get('differences') or {}
    def phones(key):
        values = diff.get(key, [])
        if not isinstance(values, list): return ''
        parts = [phone for value in values[:100] for phone in (value if isinstance(value, list) else [value])]
        return ' '.join(str(value)[:30] for value in parts[:200])
    return dict(score=round(score, 1), raw_score=score, phones=[], request_id='', example=example,
                transcript=str(payload.get('transcribe', ''))[:300], expected_ipa=phones('expected_phones'),
                heard_ipa=phones('heard_phones'))


class LocalAssessment:
    def __init__(self, data_dir):
        self.folder = Path(data_dir).resolve() / 'openpronounce'
        self.lock = threading.Lock()
        self.preparing = False
        self.error = ''
        self.process = None
        self.responses = None
        self.log = None
        atexit.register(self.close)

    def command(self):
        if getattr(sys, 'frozen', False):
            target = Path(sys.executable).parents[3] / 'OpenPronounceEngine.app/Contents/MacOS/OpenPronounceEngine'
            return [str(target)] if target.is_file() else []
        root = Path(__file__).resolve().parent
        python = root / '.build/openpronounce/venv/bin/python'
        return [str(python), str(root / 'scripts/openpronounce_engine.py')] if python.exists() else []

    def status(self):
        supported = platform.system() == 'Darwin' and platform.machine() == 'arm64' and int(platform.mac_ver()[0].split('.')[0]) >= 14
        available = supported and bool(self.command())
        ready = False
        if available:
            try:
                manifest = json.loads((self.folder / 'models-ready.json').read_text())
                ready = manifest['version'] == '0.3.0' and bool(manifest['files']) and all(
                    (self.folder / item['path']).is_file() and (self.folder / item['path']).stat().st_size == item['size']
                    for item in manifest['files'])
            except (OSError, ValueError, KeyError, TypeError): pass
        message = '模型已准备好；录音只在本机评测。' if ready else '首次需下载约 2.4 GB 模型；准备完成后可离线评测。'
        if not available: message = '本地引擎需要 Apple 芯片及 macOS 14 或以上；此设备可继续使用腾讯云。'
        if self.preparing:
            try: message = json.loads((self.folder / 'progress.json').read_text())['message']
            except (OSError, ValueError, KeyError): message = '正在准备本地模型，请保持应用开启…'
        if self.error: message = self.error
        return dict(available=available, ready=ready, busy=self.preparing, message=message)

    def environment(self):
        env = dict(os.environ)
        if not getattr(sys, 'frozen', False):
            framework = Path(__file__).resolve().parent / '.build/macos/frameworks'
            env['DYLD_FRAMEWORK_PATH'] = str(framework)
            env['DYLD_LIBRARY_PATH'] = str(framework / 'Python.framework/Versions/3.13/lib')
        return env

    def prepare(self):
        if not self.status()['available']: raise ValueError(self.status()['message'])
        if self.preparing: return self.status()
        if not self.lock.acquire(blocking=False): raise ValueError('正在评测，请完成后再准备模型。')
        self.close()
        self.preparing, self.error = True, ''
        self.folder.mkdir(parents=True, exist_ok=True)
        def run():
            try:
                with (self.folder / 'engine.log').open('w') as log:
                    subprocess.run(self.command() + ['--data-dir', str(self.folder), '--parent-pid', str(os.getpid()), '--prepare'],
                                   stdout=log, stderr=log, env=self.environment(), timeout=7200, check=True)
            except Exception:
                self.error = '模型准备未完成，请检查网络并重试；已下载文件会保留。诊断日志位于学习数据文件夹 openpronounce/engine.log。'
            finally:
                self.preparing = False
                self.lock.release()
        threading.Thread(target=run, daemon=True).start()
        return self.status()

    def close(self):
        if self.process:
            self.process.terminate()
            try: self.process.wait(timeout=3)
            except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()
            if self.process.stdin: self.process.stdin.close()
            if self.process.stdout: self.process.stdout.close()
            self.process = None
        if self.log: self.log.close(); self.log = None

    def assess(self, variant, audio):
        status = self.status()
        if not status['ready'] or status['busy']: raise ValueError('请先在设置中完成本地模型准备。')
        if not self.lock.acquire(blocking=False): raise ValueError('本地引擎正忙，请稍后重试。')
        try:
            if self.process is None or self.process.poll() is not None:
                self.close()
                self.log = (self.folder / 'engine.log').open('a')
                self.process = subprocess.Popen(self.command() + ['--data-dir', str(self.folder), '--parent-pid', str(os.getpid())],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True, env=self.environment())
                self.responses = queue.Queue()
                process, responses = self.process, self.responses
                def read():
                    for line in process.stdout: responses.put(line)
                    responses.put('')
                threading.Thread(target=read, daemon=True).start()
            self.process.stdin.write(json.dumps(dict(example=variant['example'], audio=base64.b64encode(audio).decode())) + '\n')
            self.process.stdin.flush()
            response = self.responses.get(timeout=180)
            if not response:
                (self.folder / 'models-ready.json').unlink(missing_ok=True)
                raise RuntimeError('local worker exited')
            try: result = json.loads(response)
            except ValueError: raise RuntimeError('invalid worker response') from None
            if result.get('error'): raise ValueError(result['error'])
            return parse_result(result, variant['example'])
        except ValueError: raise
        except Exception:
            self.close()
            raise ValueError('本地评测未完成，请稍后重试。本次未计分，也不会自动转交腾讯云。') from None
        finally: self.lock.release()
