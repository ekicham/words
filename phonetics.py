"""IPA learning and Tencent SOE assessment. Credentials and recordings stay local
until the student explicitly submits a recording to the assessment service.
"""
import base64
import binascii
import datetime
import hashlib
import hmac
import io
import json
import math
import os
from pathlib import Path
import random
import re
import secrets
import tempfile
import urllib.request
import wave

from local_assessment import LocalAssessment, ENGINE as LOCAL_ENGINE, NOTICE as LOCAL_NOTICE

ROOT = Path(__file__).resolve().parent
ENGINE = '腾讯云 SOE 通用英语音素模型'
NOTICE = '所选口音用于示范；评分采用通用英语音素模型，不作英美口音鉴定。分数为服务返回的准确度得分（0–100），不是统计准确率。'


def signed_request(config, payload, timestamp):
    host, service = 'soe.tencentcloudapi.com', 'soe'
    body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode()
    content_type = 'application/json; charset=utf-8'
    canonical = 'POST\n/\n\ncontent-type:%s\nhost:%s\n\ncontent-type;host\n%s' % (
        content_type, host, hashlib.sha256(body).hexdigest())
    date = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime('%Y-%m-%d')
    scope = date + '/' + service + '/tc3_request'
    to_sign = 'TC3-HMAC-SHA256\n%s\n%s\n%s' % (timestamp, scope, hashlib.sha256(canonical.encode()).hexdigest())
    key = ('TC3' + config['secret_key']).encode()
    for value in (date, service, 'tc3_request'):
        key = hmac.new(key, value.encode(), hashlib.sha256).digest()
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    return urllib.request.Request('https://' + host, data=body, headers={
        'Content-Type': content_type, 'Host': host, 'X-TC-Action': 'TransmitOralProcessWithInit',
        'X-TC-Version': '2018-07-24', 'X-TC-Timestamp': str(timestamp),
        'Authorization': 'TC3-HMAC-SHA256 Credential=%s/%s, SignedHeaders=content-type;host, Signature=%s' % (
            config['secret_id'], scope, signature)})


def parse_assessment(payload):
    result = payload.get('Response', {})
    if result.get('Error'):
        # Do not echo remote messages, credentials or recorded speech into logs/UI.
        code = re.sub(r'[^A-Za-z0-9_.]', '', str(result['Error'].get('Code', 'Unknown')))[:100]
        raise ValueError('评测服务拒绝请求（%s）。请检查服务开通、密钥和额度。' % code)
    score = result.get('PronAccuracy')
    if isinstance(score, bool) or not isinstance(score, (float, int)) or not math.isfinite(score) or not (score == -1 or 0 <= score <= 100):
        raise ValueError('评测服务未返回有效分数，请重试；本次不计分。')
    phones = []
    for word in result.get('Words') or []:
        for phone in word.get('PhoneInfos') or []:
            value = phone.get('PronAccuracy')
            phones.append(dict(reference=str(phone.get('ReferencePhone', ''))[:40],
                               detected=str(phone.get('Phone', ''))[:40], match=phone.get('MatchTag'),
                               score=value if isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 100 else None))
    return dict(score=max(0, score), raw_score=score, phones=phones, request_id=str(result.get('RequestId', ''))[:200])


def assess(config, variant, audio, timestamp):
    # ASCII label plus explicit phonemes: the displayed IPA is not an English word.
    ref = {'wordList': [{'word': '-'.join(variant['phones']), 'pron': [variant['phones']]}]}
    payload = dict(ScoreCoeff=1.0, VoiceEncodeType=1, UserVoiceData=base64.b64encode(audio).decode(),
                   IsEnd=1, ServerType=0, VoiceFileType=2, SessionId=secrets.token_hex(16), SeqId=1,
                   RefText=json.dumps(ref), WorkMode=1, EvalMode=0, TextMode=1)
    if config.get('soe_app_id'):
        payload['SoeAppId'] = config['soe_app_id']
    try:
        with urllib.request.urlopen(signed_request(config, payload, int(timestamp)), timeout=35) as response:
            result = json.loads(response.read(2_000_000))
    except Exception:
        raise ValueError('连接评测服务中断，本机未取得分数。服务可能已受理；再次提交可能重新计费，请检查网络后决定是否重试。') from None
    return parse_assessment(result)


def decode_recording(value):
    try:
        if not isinstance(value, str) or len(value) > 400_000:
            raise ValueError()
        data = base64.b64decode(value, validate=True)
        with wave.open(io.BytesIO(data), 'rb') as wav:
            if wav.getparams()[:3] != (1, 2, 16000) or wav.getcomptype() != 'NONE':
                raise ValueError()
            frames = wav.getnframes()
            if not 8000 <= frames <= 128000 or len(wav.readframes(frames)) != frames * 2:
                raise ValueError()
        return data
    except (ValueError, binascii.Error, wave.Error, EOFError):
        raise ValueError('请录制 0.5–8 秒的声音（16 kHz、单声道、16 bit WAV）。') from None


class Phonetics:
    def __init__(self, app):
        self.app = app
        self.course = json.loads((ROOT / 'data/phonetics-course.json').read_text(encoding='utf-8'))
        self.config_path = app.path.parent / 'phonetics-service.json'
        self.local = LocalAssessment(app.path.parent)
        with app.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS phonetic_tests (
                    id TEXT PRIMARY KEY, accent TEXT NOT NULL, created REAL NOT NULL,
                    ended REAL, position INTEGER NOT NULL DEFAULT 0, course TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS phonetic_scores (
                    test_id TEXT NOT NULL REFERENCES phonetic_tests(id), position INTEGER NOT NULL,
                    request_id TEXT NOT NULL, digest TEXT NOT NULL, status TEXT NOT NULL,
                    result TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT '', audio BLOB,
                    PRIMARY KEY(test_id, position));
            ''')
            if 'provider' not in {r[1] for r in db.execute('PRAGMA table_info(phonetic_tests)')}:
                db.execute("ALTER TABLE phonetic_tests ADD COLUMN provider TEXT NOT NULL DEFAULT 'tencent'")
            db.execute("UPDATE phonetic_scores SET status='error', error='上次评测被中断，请重试；本次未计分。' WHERE status='processing'")

    def config(self):
        try:
            return json.loads(self.config_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def service(self):
        config = self.config()
        provider = config.get('provider', 'tencent')
        cloud = bool(config.get('secret_id') and config.get('secret_key'))
        local = self.local.status()
        is_local = provider == 'openpronounce'
        return dict(provider=provider, configured=local['ready'] and not local['busy'] if is_local else cloud,
                    tencent_configured=cloud, local=local,
                    engine=LOCAL_ENGINE if is_local else ENGINE, notice=LOCAL_NOTICE if is_local else NOTICE)

    def configure(self, data):
        config = self.config()
        provider = data.get('provider', config.get('provider', 'tencent'))
        if provider not in ('tencent', 'openpronounce'):
            raise ValueError('请选择 OpenPronounce 或腾讯云。')
        config['provider'] = provider
        if data.get('clear') is True:
            for field in ('secret_id', 'secret_key', 'soe_app_id'): config.pop(field, None)
        elif any(field in data for field in ('secret_id', 'secret_key', 'soe_app_id')):
            for field in ('secret_id', 'secret_key'):
                value = data.get(field)
                if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_+/=-]{4,200}', value):
                    raise ValueError('请完整填写有效的 SecretId 和 SecretKey。')
                config[field] = value
            app_id = data.get('soe_app_id', '')
            if not isinstance(app_id, str) or not re.fullmatch(r'[0-9]{0,30}', app_id):
                raise ValueError('SoeAppId 仅填写数字；未创建应用可留空。')
            config['soe_app_id'] = app_id
        file = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.config_path.parent, delete=False)
        name = Path(file.name)
        try:
            with file:
                os.chmod(name, 0o600)
                json.dump(config, file)
                file.flush()
                os.fsync(file.fileno())
            name.replace(self.config_path)
        finally:
            name.unlink(missing_ok=True)
        return self.service()

    def overview(self):
        with self.app.db() as db:
            tests = [dict(row) for row in db.execute('SELECT id, accent, created, ended, position, provider FROM phonetic_tests ORDER BY created DESC LIMIT 50')]
        return dict(course=self.course, service=self.service(), history=tests)

    def start(self, data):
        if data.get('accent') not in ('uk', 'us') or type(data.get('count')) is not int or data['count'] not in (10, 48):
            raise ValueError('请选择英式或美式，以及 10 项或 48 项测试。')
        service = self.service()
        if data.get('provider', service['provider']) != service['provider']:
            raise ValueError('评测方式已变更，请重新打开音标学习后确认。')
        if data.get('consent') is not True:
            raise ValueError('请先确认录音评测说明。')
        if not service['configured']:
            raise ValueError('请先在设置中完成所选评测服务的配置或模型准备。')
        test_id = secrets.token_hex(16)
        with self.app.db() as db:
            db.execute('INSERT INTO phonetic_tests(id,accent,created,course,provider) VALUES(?,?,?,?,?)',
                       (test_id, data['accent'], self.app.now(), json.dumps(random.sample(self.course, data['count'])), service['provider']))
        return self.state(test_id)

    def state(self, test_id):
        with self.app.db() as db:
            row = db.execute('SELECT * FROM phonetic_tests WHERE id=?', (test_id,)).fetchone()
            if row is None:
                raise ValueError('这份音标测试不存在。')
            state = dict(row)
            state['course'] = json.loads(state['course'])
            state['results'] = []
            for item in db.execute('SELECT position,status,result,error FROM phonetic_scores WHERE test_id=? ORDER BY position', (test_id,)):
                item = dict(item)
                item.update(json.loads(item.pop('result')))
                state['results'].append(item)
        scores = [r['score'] for r in state['results'] if r['status'] == 'scored']
        state.update(scored=len(scores), mean=round(sum(scores) / len(scores), 1) if scores else None,
                     skipped=sum(r['status'] == 'skipped' for r in state['results']), engine=LOCAL_ENGINE if state['provider']=='openpronounce' else ENGINE,
                     notice=LOCAL_NOTICE if state['provider']=='openpronounce' else NOTICE)
        state['remaining'] = len(state['course']) - state['scored'] - state['skipped']
        return state

    def act(self, test_id, action, data):
        if action == 'delete':
            with self.app.db() as db:
                if db.execute("SELECT 1 FROM phonetic_scores WHERE test_id=? AND status='processing'", (test_id,)).fetchone():
                    raise ValueError('正在评测，请等候完成后删除。')
                db.execute('DELETE FROM phonetic_scores WHERE test_id=?', (test_id,))
                db.execute('DELETE FROM phonetic_tests WHERE id=?', (test_id,))
            return dict(deleted=True)
        audio, digest, request_id = None, '', ''
        if action == 'assess':
            audio = decode_recording(data.get('audio'))
            digest = hashlib.sha256(audio).hexdigest()
            request_id = data.get('request_id')
            if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', request_id):
                raise ValueError('提交编号无效，请重新录音。')
            config = self.config()
        with self.app.db() as db:
            test = db.execute('SELECT * FROM phonetic_tests WHERE id=?', (test_id,)).fetchone()
            if test is None:
                raise ValueError('这份音标测试不存在。')
            position = data.get('position')
            existing = db.execute('SELECT * FROM phonetic_scores WHERE test_id=? AND position=?', (test_id, position)).fetchone()
            if action == 'finish':
                if db.execute("SELECT 1 FROM phonetic_scores WHERE test_id=? AND status='processing'", (test_id,)).fetchone():
                    raise ValueError('正在评测，请稍后结束。')
                db.execute('UPDATE phonetic_tests SET ended=COALESCE(ended,?) WHERE id=?', (self.app.now(), test_id))
            elif existing and existing['status'] in ('scored', 'skipped'):
                if action == 'assess' and (existing['request_id'] != request_id or existing['digest'] != digest):
                    raise ValueError('本题已计分，请继续下一题。')
            elif test['ended'] is not None or type(position) is not int or position != test['position']:
                raise ValueError('测试进度已更新，请重新打开本次测试。')
            elif existing and existing['status'] == 'processing':
                raise ValueError('本题正在评测，请稍后刷新进度。')
            elif action == 'skip':
                db.execute("INSERT OR REPLACE INTO phonetic_scores(test_id,position,request_id,digest,status) VALUES(?,?,'','','skipped')", (test_id, position))
                self.advance(db, test)
            elif action == 'assess':
                if existing and existing['request_id'] == request_id:
                    if existing['digest'] != digest:
                        raise ValueError('同一提交编号不可替换录音。')
                    # Return the stored error; an explicit retry must use a new id.
                    audio = None
                else:
                    db.execute("INSERT OR REPLACE INTO phonetic_scores(test_id,position,request_id,digest,status,audio) VALUES(?,?,?,?,'processing',?)", (test_id, position, request_id, digest, audio))
                    variant = json.loads(test['course'])[position][test['accent']]
            else:
                raise ValueError('未知音标操作。')
            if action != 'assess' or (existing and existing['status'] in ('scored', 'skipped')):
                audio = None
        if audio is not None:
            try:
                if test['provider'] == 'openpronounce':
                    result = self.local.assess(variant, audio)
                else:
                    if not (config.get('secret_id') and config.get('secret_key')):
                        raise ValueError('本次测试使用腾讯云，请在设置中恢复腾讯云凭证后重试。')
                    result = assess(config, variant, audio, self.app.now())
                error = ''
            except Exception as exception:
                result = {}
                error = str(exception) if isinstance(exception, ValueError) else '评测暂时失败，请重试；本次不计分。'
            with self.app.db() as db:
                db.execute('UPDATE phonetic_scores SET status=?,result=?,error=? WHERE test_id=? AND position=?',
                           ('error' if error else 'scored', json.dumps(result), error, test_id, position))
                if not error:
                    self.advance(db, test)
        return self.state(test_id)

    def advance(self, db, test):
        position = test['position'] + 1
        db.execute('UPDATE phonetic_tests SET position=?,ended=? WHERE id=?',
                   (position, self.app.now() if position == len(json.loads(test['course'])) else None, test['id']))

    def audio(self, test_id, position):
        with self.app.db() as db:
            row = db.execute('SELECT audio FROM phonetic_scores WHERE test_id=? AND position=?', (test_id, position)).fetchone()
        if not row or not row['audio']:
            raise ValueError('本题没有保存的录音。')
        return bytes(row['audio'])
