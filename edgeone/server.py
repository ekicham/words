"""EdgeOne Python cloud-function API. No process-local learning state."""
import hmac
import os
import re
import secrets
import time
from urllib.parse import urlparse

from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
import pymysql
from phonetics import assess
from .domain import EdgeApp
from .storage import Store, ConfigurationError
from .security import valid_account, password_hash, issue_session, verify_session, SESSION_SECONDS


def dispatch(app, method, path, query, data):
    lesson = app.phonetics_lesson
    if method == 'GET':
        routes = {'/api/bootstrap':app.bootstrap, '/api/mistakes':app.mistakes,
                  '/api/rewards':app.rewards, '/api/rewards/config':app.reward_config,
                  '/api/phonetics':lesson.overview, '/api/phonetics/config':lesson.service}
        if path in routes:
            result = routes[path]()
            if path == '/api/bootstrap': result.update(cloud=True,native_voice=False)
            return result
        if path == '/api/completed-words': return app.completed_words(query.get('scope','all'))
        if path == '/api/words': return app.vocabulary(query.get('book_id',''))
        if path == '/api/location': return {'province':'','message':'请选择所在地区'}
        match = re.fullmatch(r'/api/session/([a-f0-9]{32})(/report)?',path)
        if match:
            position = query.get('position')
            return app.report(match[1]) if match[2] else app.state(match[1],int(position) if position is not None else None)
        match = re.fullmatch(r'/api/audio/(\d+)',path)
        if match:
            lang = 'zh' if query.get('lang') == 'zh' else 'en'
            return {'fallback':True,'text':app.speech(int(match[1]),lang,query.get('dictation')=='1'),
                    'lang':'zh-CN' if lang=='zh' else 'en-US'}
        match = re.fullmatch(r'/api/phonetics/tests/([a-f0-9]{32})(?:/audio/(\d+))?',path)
        if match: return lesson.audio(match[1],int(match[2])) if match[2] else lesson.state(match[1])
    if method == 'POST':
        routes = {'/api/start':app.start, '/api/import':app.import_book,
                  '/api/rewards/draw':app.draw_reward, '/api/rewards/config':app.save_reward_config,
                  '/api/phonetics/tests':lesson.start, '/api/phonetics/config':lesson.configure}
        if path in routes: return routes[path](data)
        if path == '/api/phonetics/prepare': raise ValueError('云端不支持 Mac 本地评测模型。')
        match = re.fullmatch(r'/api/session/([a-f0-9]{32})/(answer|hint|skip|finish|ready|draft|next)',path)
        if match: return app.act(match[1],match[2],data)
        match = re.fullmatch(r'/api/rewards/([A-Za-z0-9_-]{1,100})/redeem',path)
        if match: return app.redeem_reward(match[1])
    raise ValueError('接口不存在')


def configure_app(app, env=None):
    app.config.update(MAX_CONTENT_LENGTH=2_000_000, WORDISLE_ENV=dict(os.environ if env is None else env))

    @app.after_request
    def private_response(response):
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def error(message, status=400): return jsonify(error=message), status

    @app.route('/', defaults={'path':''}, methods=['GET','POST'])
    @app.route('/<path:path>', methods=['GET','POST'])
    def api(path):
        env = app.config['WORDISLE_ENV']
        secret = env.get('AUTH_SECRET','')
        origin = env.get('APP_ORIGIN','').rstrip('/')
        local = env.get('EDGEONE_LOCAL') == '1'
        parsed = urlparse(origin)
        if len(secret) < 32: return error('请管理员配置至少 32 字符的 AUTH_SECRET',503)
        if not parsed.netloc or parsed.path or (parsed.scheme != 'https' and not
                (local and parsed.scheme == 'http' and parsed.hostname in ('localhost','127.0.0.1'))):
            return error('请管理员配置 APP_ORIGIN 为网站的 HTTPS 域名，例如 https://words.example.com',503)
        if request.method == 'POST' and request.headers.get('Origin') != origin:
            return error('请求来源无效，请从本站页面操作',403)
        # Framework routes receive paths with /api stripped by EdgeOne.
        path = request.path if request.path.startswith('/api/') else '/api'+request.path
        store = Store(env)
        try:
            data = {}
            if request.method == 'POST':
                if not request.is_json: return error('只接受 JSON 请求',415)
                if path.startswith('/api/auth/') and len(request.get_data()) > 4096: return error('请求过大',413)
                data = request.get_json()
                if not isinstance(data,dict): return error('请求格式无效')
            if path in ('/api/auth/register','/api/auth/login') and request.method == 'POST':
                username = data.get('username','')
                username = username.strip().lower() if isinstance(username,str) else ''
                password = data.get('password','')
                if not valid_account(username,password): return error('账号须为 3–32 位字母、数字、下划线或连字符，密码须为 12–128 字符。')
                registering = path.endswith('/register')
                if registering:
                    invite, supplied = env.get('REGISTRATION_CODE',''),data.get('invitation','')
                    if len(invite)<16 or not isinstance(supplied,str) or not hmac.compare_digest(invite.encode(),supplied.encode()):
                        return error('邀请码无效或当前未开放注册',403)
                with store.connect() as connection:
                    if not store.consume_attempt(connection,'account:'+username) or not store.consume_attempt(connection,'global-auth',120,60):
                        return error('尝试过于频繁，请稍后重试',429)
                    if registering:
                        uid, salt = secrets.token_hex(16), secrets.token_hex(16)
                        digest = password_hash(password,salt)
                        try:
                            with connection.cursor() as c:
                                c.execute('INSERT INTO wi_accounts(username,uid,salt,password_hash,created) VALUES(%s,%s,%s,%s,%s)',
                                          (username,uid,salt,digest,time.time()))
                            connection.commit()
                        except pymysql.IntegrityError:
                            connection.rollback()
                            return error('该账号已被使用，请更换账号',409)
                    else:
                        with connection.cursor() as c:
                            c.execute('SELECT uid,salt,password_hash FROM wi_accounts WHERE username=%s',(username,))
                            row = c.fetchone()
                        digest = password_hash(password,row['salt'] if row else '00'*16)
                        if not row or not hmac.compare_digest(digest,row['password_hash']): return error('账号或密码不正确',401)
                        uid = row['uid']
                response = jsonify(ok=True,username=username)
                response.set_cookie('wordisle_session',issue_session(uid,secret),max_age=SESSION_SECONDS,
                                    secure=parsed.scheme == 'https',httponly=True,samesite='Strict',path='/')
                return response
            if path == '/api/auth/logout' and request.method == 'POST':
                response = jsonify(ok=True)
                response.delete_cookie('wordisle_session',path='/',secure=parsed.scheme == 'https',httponly=True,samesite='Strict')
                return response
            uid = verify_session(request.cookies.get('wordisle_session',''),secret)
            if not uid: return error('请先登录',401)
            if path == '/api/auth/me': return jsonify(user_id=uid)
            factory = lambda db: EdgeApp(db,env)
            match = re.fullmatch(r'/api/phonetics/tests/([a-f0-9]{32})/(assess|skip|finish|delete)',path)
            if request.method == 'POST' and match:
                with store.learner(uid,factory) as learner:
                    pending,result = learner.phonetics_lesson.begin_action(match[1],match[2],data)
                    config = learner.phonetics_lesson.config()
                if pending:
                    # Commit the submission and release the account lock before provider I/O.
                    try:
                        if not config['secret_id'] or not config['secret_key']: raise ValueError('管理员尚未配置腾讯云评测。')
                        scored = assess(config,pending['variant'],pending['audio'],time.time())
                        failure = ''
                    except Exception as exception:
                        scored = {}
                        failure = str(exception) if isinstance(exception,ValueError) else '评测连接中断，请重新录音重试；服务可能已经受理，重试可能再次计费。'
                    with store.learner(uid,factory) as learner:
                        result = learner.phonetics_lesson.complete_assessment(pending,scored,failure)
            else:
                with store.learner(uid,factory) as learner:
                    result = dispatch(learner,request.method,path,request.args,data)
            return Response(result,mimetype='audio/wav') if isinstance(result,bytes) else jsonify(result)
        except ConfigurationError as exception:
            return error(str(exception),503)
        except RequestEntityTooLarge:
            return error('请求过大',413)
        except BadRequest:
            return error('JSON 请求格式无效')
        except (ValueError,KeyError,TypeError) as exception:
            return error(str(exception))
        except Exception as exception:
            trace = secrets.token_hex(6)
            # Log correlation + type/code, never credentials, SQL, answers or recordings.
            code = exception.args[0] if exception.args and isinstance(exception.args[0],int) else None
            app.logger.error('wordisle_failure id=%s type=%s code=%s',trace,type(exception).__name__,code)
            return error('服务暂时不可用，请管理员检查数据库连接。错误编号：'+trace,503)
    return app


def create_app(env=None):
    return configure_app(Flask(__name__),env)
