"""MySQL 8 persistence. Tenant identifiers come only from signed account UIDs."""
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import re
from pathlib import Path
import ssl
import time

import pymysql

TABLES = ('books', 'words', 'sessions', 'items', 'attempts', 'requests', 'rewards',
          'reward_config', 'phonetic_tests', 'phonetic_scores')

SCHEMA = {
    'books': 'id VARCHAR(80) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY, metadata LONGTEXT NOT NULL',
    'words': '''id BIGINT PRIMARY KEY AUTO_INCREMENT, book_id VARCHAR(80) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        english VARCHAR(80) NOT NULL, meaning VARCHAR(150) NOT NULL, unit VARCHAR(60) NOT NULL, page VARCHAR(20) NOT NULL,
        UNIQUE(book_id,english,unit), FOREIGN KEY(book_id) REFERENCES {p}books(id)''',
    'sessions': '''id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY, book_id VARCHAR(80) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        province VARCHAR(64) NOT NULL, started DOUBLE NOT NULL, deadline DOUBLE NOT NULL, ended DOUBLE,
        minutes INT NOT NULL, position INT NOT NULL DEFAULT 0, status VARCHAR(16) NOT NULL DEFAULT 'active',
        mode VARCHAR(32) NOT NULL, learning_order VARCHAR(32) NOT NULL DEFAULT 'random',
        practice_type VARCHAR(32) NOT NULL DEFAULT 'hint', dictation_mode VARCHAR(16) NOT NULL DEFAULT 'auto',
        dictation_seconds INT NOT NULL DEFAULT 15, FOREIGN KEY(book_id) REFERENCES {p}books(id)''',
    'items': '''id BIGINT PRIMARY KEY AUTO_INCREMENT, session_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        position INT NOT NULL, word_id BIGINT NOT NULL, tries INT NOT NULL DEFAULT 0,
        solved INT NOT NULL DEFAULT 0, hinted INT NOT NULL DEFAULT 0, skipped INT NOT NULL DEFAULT 0,
        round_number INT NOT NULL DEFAULT 1, writing_deadline DOUBLE, draft TEXT NOT NULL DEFAULT (''),
        draft_revision BIGINT NOT NULL DEFAULT 0, result VARCHAR(32) NOT NULL DEFAULT '', audio_ready INT NOT NULL DEFAULT 0,
        UNIQUE(session_id,position), INDEX items_word(word_id,id),
        FOREIGN KEY(session_id) REFERENCES {p}sessions(id), FOREIGN KEY(word_id) REFERENCES {p}words(id)''',
    'attempts': '''id BIGINT PRIMARY KEY AUTO_INCREMENT, item_id BIGINT NOT NULL, number INT NOT NULL,
        answer TEXT NOT NULL, correct INT NOT NULL, hinted INT NOT NULL, submitted DOUBLE NOT NULL,
        INDEX attempts_item(item_id), FOREIGN KEY(item_id) REFERENCES {p}items(id)''',
    'requests': '''session_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, `key` VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        payload LONGTEXT NOT NULL, response LONGTEXT NOT NULL, PRIMARY KEY(session_id,`key`),
        FOREIGN KEY(session_id) REFERENCES {p}sessions(id)''',
    'rewards': '''id VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY, prize_index INT NOT NULL, prize TEXT NOT NULL,
        cost INT NOT NULL CHECK(cost>0), created_at DOUBLE NOT NULL, redeemed_at DOUBLE,
        _sequence BIGINT NOT NULL AUTO_INCREMENT UNIQUE''',
    'reward_config': 'id INT PRIMARY KEY CHECK(id=1), prizes TEXT NOT NULL',
    'phonetic_tests': '''id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY, accent VARCHAR(8) NOT NULL,
        created DOUBLE NOT NULL, ended DOUBLE, position INT NOT NULL DEFAULT 0, course LONGTEXT NOT NULL,
        provider VARCHAR(32) NOT NULL DEFAULT 'tencent' ''',
    'phonetic_scores': '''test_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, position INT NOT NULL,
        request_id VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, digest VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        status VARCHAR(16) NOT NULL, result LONGTEXT NOT NULL DEFAULT ('{{}}'), error TEXT NOT NULL DEFAULT (''),
        audio MEDIUMBLOB, _updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
        PRIMARY KEY(test_id,position), FOREIGN KEY(test_id) REFERENCES {p}phonetic_tests(id)''',
}


class Row(dict):
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Cursor:
    def __init__(self, rows): self.rows = iter(rows)
    def __iter__(self): return self.rows
    def fetchone(self): return next(self.rows, None)
    def fetchall(self): return list(self.rows)


class Connection:
    def __init__(self, connection, uid):
        if not re.fullmatch(r'[a-f0-9]{32}', uid): raise ValueError('Invalid account identifier')
        self.connection, self.prefix = connection, 'u'+uid+'_'

    def translate(self, query, bindings):
        query = query.replace('INSERT OR REPLACE INTO', 'REPLACE INTO')
        # Match the one SQLite date expression used by the completed-words report.
        expression = "date(a.submitted,'unixepoch',?)"
        if expression in query:
            scope, modifier, day = bindings
            if modifier != '+8 hours': raise ValueError('Unsupported business timezone')
            bindings = (scope, 8*3600, day)
            query = query.replace(expression, 'DATE(FROM_UNIXTIME(a.submitted+?))')
        # SQLite permits non-grouped values here; make that choice explicit in MySQL.
        query = query.replace('i.tries,i.hinted,i.skipped,GROUP_CONCAT',
            'ANY_VALUE(i.tries) AS tries,ANY_VALUE(i.hinted) AS hinted,ANY_VALUE(i.skipped) AS skipped,GROUP_CONCAT')
        parts = re.split(r"('(?:''|[^'])*')", query)
        for index in range(0, len(parts), 2):
            part = re.sub(r'\b('+ '|'.join(TABLES)+r')\b', lambda m: '`'+self.prefix+m[0]+'`', parts[index])
            part = re.sub(r'\bkey\b', '`key`', part)
            parts[index] = re.sub(r'\browid\b', '_sequence', part).replace('?', '%s')
        return ''.join(parts), bindings

    def execute(self, query, bindings=()):
        query, bindings = self.translate(query, bindings)
        with self.connection.cursor() as cursor:
            cursor.execute(query, bindings)
            rows = cursor.fetchall() if cursor.description else []
        def normalize(value):
            return (int(value) if value == value.to_integral_value() else float(value)) if isinstance(value, Decimal) else value
        return Cursor([Row((k, normalize(v)) for k,v in row.items() if not k.startswith('_')) for row in rows])

    def executemany(self, query, rows):
        query, _ = self.translate(query, ())
        with self.connection.cursor() as cursor: cursor.executemany(query, list(rows))


class ConfigurationError(RuntimeError): pass


class Store:
    def __init__(self, env): self.env = env

    @contextmanager
    def connect(self):
        missing = [k for k in ('DB_HOST','DB_NAME','DB_USER','DB_PASSWORD') if not self.env.get(k)]
        if missing: raise ConfigurationError('请管理员配置数据库：'+', '.join(missing))
        tls = self.env.get('DB_TLS', '1') != '0'
        if not tls and self.env['DB_HOST'] not in ('127.0.0.1', 'localhost'):
            raise ConfigurationError('远程数据库必须启用 TLS')
        ca = self.env.get('DB_TLS_CA_FILE') or None
        if ca == 'bundled': ca = str(Path(__file__).with_name('mysql-ca.txt'))
        context = ssl.create_default_context(cafile=ca) if tls else None
        connection = pymysql.connect(host=self.env['DB_HOST'], port=int(self.env.get('DB_PORT','3306')),
            database=self.env['DB_NAME'], user=self.env['DB_USER'], password=self.env['DB_PASSWORD'],
            charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, autocommit=False,
            ssl=context, connect_timeout=8, read_timeout=15, write_timeout=15)
        try:
            with connection.cursor() as c:
                c.execute("SET time_zone='+00:00'")
                c.execute('''CREATE TABLE IF NOT EXISTS wi_accounts(
                    username VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
                    uid CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE, salt CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                    password_hash VARCHAR(160) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, created DOUBLE NOT NULL,
                    initialized INT NOT NULL DEFAULT 0, catalog_revision CHAR(64) NOT NULL DEFAULT '') ENGINE=InnoDB''')
                c.execute('''CREATE TABLE IF NOT EXISTS wi_limits(
                    bucket CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY, started DOUBLE NOT NULL, attempts INT NOT NULL,
                    INDEX limits_started(started)) ENGINE=InnoDB''')
            connection.commit()
            yield connection
        finally:
            connection.close()

    def consume_attempt(self, connection, key, limit=10, window=900):
        now = time.time()
        bucket = hashlib.sha256(key.encode()).hexdigest()
        try:
            connection.begin()
            with connection.cursor() as c:
                c.execute('DELETE FROM wi_limits WHERE started<%s LIMIT 1000', (now-86400,))
                c.execute('INSERT IGNORE INTO wi_limits VALUES(%s,%s,0)', (bucket,now))
                c.execute('SELECT * FROM wi_limits WHERE bucket=%s FOR UPDATE', (bucket,))
                row = c.fetchone()
                count = row['attempts'] if now-row['started'] < window else 0
                if count >= limit:
                    connection.commit()
                    return False
                c.execute('UPDATE wi_limits SET started=%s,attempts=%s WHERE bucket=%s',
                          (row['started'] if count else now, count+1, bucket))
            connection.commit()
            return True
        except Exception:
            connection.rollback()
            raise

    @contextmanager
    def learner(self, uid, factory):
        with self.connect() as connection:
            db = Connection(connection, uid)
            lock = 'wi:'+hashlib.sha256(self.env['DB_NAME'].encode()).hexdigest()[:12]+':'+uid
            with connection.cursor() as c:
                c.execute('SELECT GET_LOCK(%s,5) AS acquired', (lock,))
                if c.fetchone()['acquired'] != 1: raise RuntimeError('Account transaction busy')
                c.execute('SELECT initialized,catalog_revision FROM wi_accounts WHERE uid=%s', (uid,))
                account = c.fetchone()
                if account is None: raise ValueError('账号不存在，请重新登录')
                if account['initialized'] == 0:
                    # DDL commits implicitly in MySQL; create tables before the business transaction.
                    for table, definition in SCHEMA.items():
                        c.execute('CREATE TABLE IF NOT EXISTS `'+db.prefix+table+'` ('+
                            definition.format(p=db.prefix)+') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin')
                    c.execute('UPDATE wi_accounts SET initialized=1 WHERE uid=%s', (uid,))
                    connection.commit()
            try:
                connection.begin()
                app = factory(db)
                if account['catalog_revision'] != app.catalog_revision:
                    app.seed_books()
                    with connection.cursor() as c:
                        c.execute('UPDATE wi_accounts SET catalog_revision=%s WHERE uid=%s', (app.catalog_revision,uid))
                # Do not cancel an assessment merely because another request starts.
                db.execute("UPDATE phonetic_scores SET status='error',error='上次评测中断，请重新录音重试。' "
                           "WHERE status='processing' AND _updated_at<TIMESTAMPADD(SECOND,-180,UTC_TIMESTAMP(6))")
                yield app
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                with connection.cursor() as c: c.execute('SELECT RELEASE_LOCK(%s)', (lock,))
