"""Cloudflare entrypoint. Each authenticated account owns one SQLite DO."""
import asyncio
import base64
import hmac
import json
import re
import secrets
import time
from urllib.parse import urlparse, parse_qs

from workers import WorkerEntrypoint, DurableObject, Response
from js import Object, Response as JSResponse, fetch as js_fetch
from pyodide.ffi import to_js
from app import App, province_from_geo
from phonetics import Phonetics, ENGINE, NOTICE, signed_request, parse_assessment
from resources import RESOURCES
from storage import Connection, database
from auth import issue_session, verify_session, valid_account, SESSION_SECONDS, PASSWORD_ITERATIONS
from auth import webcrypto_password_hash as password_hash, encode_password_hash, password_parameters


def js(value): return to_js(value, dict_converter=Object.fromEntries)
def setting(env, name): return str(getattr(env, name, '') or '')
def reply(value, status=200, headers=None):
    return Response.json(value, status=status, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', **(headers or {})})
def cookie(token, secure=True, clear=False):
    return 'wordisle_session=%s; Path=/; HttpOnly; SameSite=Strict; Max-Age=%s%s' % (token, 0 if clear else SESSION_SECONDS, '; Secure' if secure else '')
def token_from(request):
    for part in (request.headers.get('Cookie') or '').split(';'):
        key, _, value = part.strip().partition('=')
        if key == 'wordisle_session': return value
    return ''
def stub(namespace, name): return namespace.get(namespace.idFromName(name))

async def serve_asset(env, request):
    asset = await env.ASSETS.fetch(request)
    range_header = request.headers.get('Range')
    # Assets' local emulator does not implement ranges. Preserve seeking for our
    # two bounded media files without copying video bytes into Python memory.
    if (urlparse(request.url).path in ('/media/phonetics/lesson.mp4','/media/phonetics/lesson.mp3')
            and request.method == 'GET' and asset.status == 200 and range_header):
        blob = await asset.js_object.blob()
        size = blob.size
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header)
        if not match or not any(match.groups()):
            return Response('',status=416,headers={'Content-Range':'bytes */%s'%size})
        start = int(match[1]) if match[1] else max(0,size-int(match[2]))
        end = min(size-1,int(match[2])) if match[1] and match[2] else size-1
        if start > end or start >= size:
            return Response('',status=416,headers={'Content-Range':'bytes */%s'%size})
        return JSResponse.new(blob.slice(start,end+1),js({'status':206,'headers':{
            'Content-Type':asset.headers.get('Content-Type','application/octet-stream'),
            'Content-Length':str(end-start+1),'Content-Range':'bytes %s-%s/%s'%(start,end,size),
            'Accept-Ranges':'bytes','Cache-Control':'private, no-store'}}))
    return asset

async def body_json(request, limit=2_000_000):
    if (request.headers.get('Content-Type') or '').split(';')[0].strip() != 'application/json':
        raise ValueError('只接受 JSON 请求')
    # Enforce actual streamed bytes as well as declared length.
    length = request.headers.get('Content-Length')
    if length and int(length) > limit: raise ValueError('请求过大')
    reader = request.body.getReader()
    chunks, size = [], 0
    while True:
        item = await reader.read()
        if item.done: break
        chunk = bytes(item.value.to_py())
        size += len(chunk)
        if size > limit:
            await reader.cancel()
            raise ValueError('请求过大')
        chunks.append(chunk)
    data = json.loads(b''.join(chunks))
    if not isinstance(data, dict): raise ValueError('请求格式无效')
    return data

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        try:
            return await self.handle(request)
        except Exception:
            return reply({'error':'服务暂时不可用，请稍后重试'}, 503)

    async def handle(self, request):
        parsed = urlparse(request.url)
        path = parsed.path
        secret = setting(self.env, 'AUTH_SECRET')
        if len(secret) < 32:
            return reply({'error': '请管理员在 Cloudflare Secrets 设置至少 32 字符的 AUTH_SECRET。'}, 503)
        if request.method not in ('GET', 'HEAD', 'POST'):
            return reply({'error': '不支持的请求方式'}, 405)
        if request.method == 'POST':
            origin = request.headers.get('Origin')
            if origin != parsed.scheme + '://' + parsed.netloc:
                return reply({'error': '请求来源无效，请从本站页面操作'}, 403)
        secure = parsed.scheme == 'https'
        if path in ('/api/auth/login', '/api/auth/register') and request.method == 'POST':
            return await stub(self.env.ACCOUNTS, 'directory-v1').fetch(request)
        if path == '/api/auth/logout' and request.method == 'POST':
            return reply({'ok': True}, headers={'Set-Cookie': cookie('', secure, clear=True)})
        if path in ('/login','/login.html','/login.js','/style.css','/favicon.svg') and request.method in ('GET','HEAD'):
            return await self.env.ASSETS.fetch(request)
        uid = verify_session(token_from(request), secret)
        if not uid:
            if path.startswith('/api/'):
                return reply({'error': '请先登录'}, 401)
            return Response('', status=302, headers={'Location': '/login.html', 'Cache-Control': 'no-store'})
        if path == '/api/auth/me': return reply({'user_id': uid})
        if path == '/api/location':
            cf = getattr(request, 'cf', None)
            geo = cf.to_py() if cf else {}
            province = province_from_geo({'country_code': geo.get('country'), 'region': geo.get('region')})
            return reply({'province': province, 'message': '请核对推荐地区' if province else '请选择所在地区'})
        if path.startswith('/api/'):
            return await stub(self.env.LEARNERS, uid).fetch(request)
        return await serve_asset(self.env, request)

class Accounts(DurableObject):
    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self.db = Connection(ctx.storage.sql)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS accounts(
          username TEXT PRIMARY KEY, uid TEXT UNIQUE NOT NULL, salt TEXT NOT NULL,
          password_hash TEXT NOT NULL, created REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY, start REAL NOT NULL, attempts INTEGER NOT NULL);''')

    def attempt(self, ip):
        now = time.time()
        self.db.execute('DELETE FROM limits WHERE start<?', (now-900,))
        row = self.db.execute('SELECT attempts FROM limits WHERE key=?', (ip,)).fetchone()
        if row and row['attempts'] >= 10: return False
        self.db.execute('INSERT INTO limits VALUES(?,?,1) ON CONFLICT(key) DO UPDATE SET attempts=attempts+1', (ip, now))
        return True

    async def fetch(self, request):
        try:
            if not self.ctx.storage.transactionSync(lambda: self.attempt(request.headers.get('CF-Connecting-IP') or 'local')):
                return reply({'error': '尝试过于频繁，请 15 分钟后重试'}, 429)
            data = await body_json(request, 4096)
            username = data.get('username', '')
            username = username.strip().lower() if isinstance(username, str) else ''
            password = data.get('password', '')
            if not valid_account(username, password):
                return reply({'error': '账号须为 3–32 位小写字母、数字、下划线或连字符；密码须为 12–128 字符。'}, 400)
            registering = urlparse(request.url).path.endswith('/register')
            if registering:
                invitation = setting(self.env, 'REGISTRATION_CODE')
                supplied = data.get('invitation', '')
                if len(invitation) < 16 or not isinstance(supplied, str) or not hmac.compare_digest(invitation.encode(), supplied.encode()):
                    return reply({'error': '邀请码无效或当前未开放注册'}, 403)
                salt, uid = secrets.token_hex(16), secrets.token_hex(16)
                digest = await password_hash(password, salt)
                def create():
                    if self.db.execute('SELECT 1 FROM accounts WHERE username=?', (username,)).fetchone(): return False
                    self.db.execute('INSERT INTO accounts VALUES(?,?,?,?,?)', (username,uid,salt,encode_password_hash(digest),time.time()))
                    return True
                if not self.ctx.storage.transactionSync(create):
                    return reply({'error': '该账号已被使用，请更换账号'}, 409)
            else:
                row = self.db.execute('SELECT * FROM accounts WHERE username=?', (username,)).fetchone()
                iterations, expected = password_parameters(row['password_hash']) if row else (PASSWORD_ITERATIONS, '')
                digest = await password_hash(password, row['salt'] if row else '00'*16, iterations)
                if not row or not hmac.compare_digest(digest, expected):
                    return reply({'error': '账号或密码不正确'}, 401)
                uid = row['uid']
            token = issue_session(uid, setting(self.env,'AUTH_SECRET'))
            return reply({'ok': True, 'username': username}, headers={'Set-Cookie':cookie(token, urlparse(request.url).scheme=='https')})
        except (ValueError, TypeError):
            return reply({'error': '登录请求格式无效'}, 400)

class UnavailableLocal:
    def __init__(self, path): pass
    def status(self): return {'available':False,'ready':False,'busy':False,'message':'云端不运行 Mac 本地模型；可使用腾讯云评测。'}

class CloudPhonetics(Phonetics):
    def __init__(self, app, *, course=None):
        super().__init__(app, course=course, local_factory=UnavailableLocal)
    def config(self):
        env = self.app.env
        return {'provider':'tencent','secret_id':setting(env,'TENCENT_SECRET_ID'),
                'secret_key':setting(env,'TENCENT_SECRET_KEY'),'soe_app_id':setting(env,'TENCENT_SOE_APP_ID')}
    def service(self):
        result = super().service()
        result.update(cloud=True, notice=NOTICE+' 录音和报告保存在你的云端账号中，可从测试记录删除。')
        return result
    def configure(self, data): raise ValueError('云端评测凭据由管理员在 Cloudflare Secrets 中配置。')

class CloudApp(App):
    def __init__(self, storage, env):
        self.connection, self.env = Connection(storage.sql), env
        super().__init__('/unused/words.db', resources=RESOURCES, day_offset_hours=8, lesson_factory=CloudPhonetics)
    def db(self): return database(self.connection)

class Learner(DurableObject):
    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self.app = ctx.storage.transactionSync(lambda: CloudApp(ctx.storage, env))

    def dispatch(self, method, path, query, data):
        app, lesson = self.app, self.app.phonetics_lesson
        if method == 'GET':
            routes = {'/api/bootstrap':app.bootstrap, '/api/mistakes':app.mistakes,
                      '/api/rewards':app.rewards, '/api/rewards/config':app.reward_config,
                      '/api/phonetics':lesson.overview, '/api/phonetics/config':lesson.service}
            if path in routes:
                result = routes[path]()
                if path == '/api/bootstrap': result.update(cloud=True, native_voice=False)
                return result
            if path == '/api/completed-words': return app.completed_words(query.get('scope',['all'])[0])
            if path == '/api/words': return app.vocabulary(query.get('book_id',[''])[0])
            match = re.fullmatch(r'/api/session/([a-f0-9]{32})(/report)?', path)
            if match:
                position = query.get('position',[None])[0]
                return app.report(match[1]) if match[2] else app.state(match[1], int(position) if position is not None else None)
            match = re.fullmatch(r'/api/audio/(\d+)', path)
            if match:
                lang = 'zh' if query.get('lang') == ['zh'] else 'en'
                return {'fallback':True,'text':app.speech(int(match[1]),lang,query.get('dictation')==['1']), 'lang':'zh-CN' if lang=='zh' else 'en-US'}
            match = re.fullmatch(r'/api/phonetics/tests/([a-f0-9]{32})(?:/audio/(\d+))?', path)
            if match: return lesson.audio(match[1],int(match[2])) if match[2] else lesson.state(match[1])
        if method == 'POST':
            routes = {'/api/start':app.start, '/api/import':app.import_book,
                      '/api/rewards/draw':app.draw_reward, '/api/rewards/config':app.save_reward_config,
                      '/api/phonetics/tests':lesson.start, '/api/phonetics/config':lesson.configure}
            if path in routes: return routes[path](data)
            if path == '/api/phonetics/prepare': raise ValueError('云端不支持 Mac 本地评测模型。')
            match = re.fullmatch(r'/api/session/([a-f0-9]{32})/(answer|hint|skip|finish|ready|draft|next)', path)
            if match: return app.act(match[1],match[2],data)
            match = re.fullmatch(r'/api/rewards/([A-Za-z0-9_-]{1,100})/redeem',path)
            if match: return app.redeem_reward(match[1])
        raise ValueError('接口不存在')

    async def fetch(self, request):
        try:
            parsed = urlparse(request.url)
            data = await body_json(request) if request.method == 'POST' else {}
            match = re.fullmatch(r'/api/phonetics/tests/([a-f0-9]{32})/(assess|skip|finish|delete)', parsed.path)
            if request.method == 'POST' and match:
                lesson = self.app.phonetics_lesson
                pending, result = self.ctx.storage.transactionSync(lambda: lesson.begin_action(match[1],match[2],data))
                if pending:
                    # An outbound request must not hold a database transaction.
                    # Keep it alive even if the browser disconnects after submission.
                    task = asyncio.create_task(self.assess_pending(pending))
                    self.ctx.waitUntil(to_js(task))
                    result = await task
            else:
                result = self.ctx.storage.transactionSync(lambda: self.dispatch(request.method, parsed.path, parse_qs(parsed.query),data))
            if isinstance(result, bytes):
                return Response(result, headers={'Content-Type':'audio/wav','Cache-Control':'no-store'})
            return reply(result)
        except (ValueError, KeyError, TypeError) as error:
            return reply({'error':str(error)},400)
        except Exception:
            # Never include credentials, recorded speech, SQL or tracebacks in HTTP responses.
            return reply({'error':'服务暂时无法完成请求，请重试'},500)

    async def assess_pending(self, pending):
        lesson = self.app.phonetics_lesson
        try:
            config = lesson.config()
            if not (config['secret_id'] and config['secret_key']): raise ValueError('管理员尚未配置腾讯云评测。')
            variant = pending['variant']
            payload = dict(ScoreCoeff=1.0, VoiceEncodeType=1, UserVoiceData=base64.b64encode(pending['audio']).decode(),
                IsEnd=1,ServerType=0,VoiceFileType=2,SessionId=secrets.token_hex(16),SeqId=1,
                RefText=json.dumps({'wordList':[{'word':'-'.join(variant['phones']),'pron':[variant['phones']]}]}),
                WorkMode=1,EvalMode=0,TextMode=1)
            if config['soe_app_id']: payload['SoeAppId']=config['soe_app_id']
            signed = signed_request(config,payload,int(time.time()))
            from js import AbortSignal
            response = await js_fetch(signed.full_url, js({'method':'POST','headers':dict(signed.header_items()),
                'body':signed.data.decode(),'signal':AbortSignal.timeout(35000)}))
            if not response.ok: raise ValueError('评测服务返回错误；本次未取得有效分数。')
            result, error = parse_assessment(json.loads(await response.text())), ''
        except Exception as exception:
            result = {}
            error = str(exception) if isinstance(exception,ValueError) else '评测连接中断，本次未取得分数；服务可能已受理，重试可能重新计费。'
        return self.ctx.storage.transactionSync(lambda: lesson.complete_assessment(pending,result,error))
