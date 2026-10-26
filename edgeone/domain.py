"""Keep the desktop learning rules; supply MySQL and server-owned assessment settings."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import time
from .core import App
from phonetics import Phonetics, NOTICE
from .resources import RESOURCES


class NoLocalModel:
    def status(self):
        return {'available':False, 'ready':False, 'busy':False, 'message':'云端使用腾讯云评测，不运行 Mac 本地模型。'}


class EdgePhonetics(Phonetics):
    def __init__(self, app):
        self.app, self.course, self.local = app, RESOURCES['course'], NoLocalModel()

    def config(self):
        env = self.app.env
        return dict(provider='tencent', secret_id=env.get('TENCENT_SECRET_ID',''),
                    secret_key=env.get('TENCENT_SECRET_KEY',''), soe_app_id=env.get('TENCENT_SOE_APP_ID',''))

    def service(self):
        result = super().service()
        result.update(cloud=True, notice=NOTICE+' 录音和报告保存在你的云端账号中，可从测试记录删除。')
        return result

    def configure(self, data): raise ValueError('云端评测密钥由管理员在 EdgeOne 环境变量中配置。')


class EdgeApp(App):
    catalog_revision = hashlib.sha256(json.dumps(RESOURCES['books'], sort_keys=True).encode()).hexdigest()

    def __init__(self, connection, env):
        # The MySQL store owns schema migrations and the outer request transaction.
        self.connection, self.env = connection, env
        self.path, self.now, self.day_offset_hours = Path('/unused/words.db'), time.time, 8
        self.phonetics = RESOURCES['phonetics']['entries']
        self.textbook_phonetics = RESOURCES['textbook_phonetics']
        self.phonetics_lesson = EdgePhonetics(self)

    @contextmanager
    def db(self): yield self.connection

    def seed_books(self):
        for book in RESOURCES['books']:
            if not self.connection.execute('SELECT 1 FROM books WHERE id=?', (book['id'],)).fetchone():
                self.import_book(book)
