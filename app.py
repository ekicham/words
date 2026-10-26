#!/usr/bin/env python3
"""Word Isle — local-only vocabulary practice. Python standard library only."""
import argparse
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import random
import re
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.request
from urllib.parse import urlparse, parse_qs
from phonetics import Phonetics

ROOT = Path(__file__).resolve().parent
DRAW_COST = 800
FAMILY_PRIZES = [
    dict(name='桌游时光', icon='🎲', detail='选一款喜欢的桌游，和家人一起玩 30 分钟。'),
    dict(name='公园散步', icon='🌿', detail='和家人散步 30 分钟，分享今天最开心的一件事。'),
    dict(name='家庭电影', icon='🎬', detail='一起挑一部电影，在家度过温馨的观影时光。'),
    dict(name='一起做点心', icon='🧁', detail='和家人一起做一道小点心，从准备到分享都一起参与。'),
    dict(name='故事接龙', icon='📚', detail='你一句、我一句，和家人一起编一个 20 分钟的故事。'),
    dict(name='亲子手工', icon='🎨', detail='一起画画、折纸或做手工，留下属于你们的小作品。'),
    dict(name='一起运动', icon='🏸', detail='选择散步以外的一项喜欢的运动，和家人玩 30 分钟。'),
    dict(name='家庭音乐会', icon='🎵', detail='轮流选歌，一起唱歌、跳舞，开一场 20 分钟的小音乐会。'),
]
PRIZE_PRESETS = FAMILY_PRIZES + [
    dict(name='亲子惊喜时光', icon='🎁', detail='和家人各写一个想一起做的小游戏，抽一个，享受 30 分钟的惊喜时光。'),
    dict(name='亲子骑行', icon='🚲', detail='和家人选一条安全的路线，一起骑行 30 分钟，沿途寻找有趣的风景。'),
    dict(name='合作拼图', icon='🧩', detail='选一幅喜欢的拼图，和家人合作 30 分钟，一起完成小挑战。'),
    dict(name='家庭小厨房', icon='🍳', detail='和家人一起准备一道家常菜，分工洗菜、摆盘，再一起分享成果。'),
    dict(name='周末野餐', icon='🏕️', detail='和家人准备食物和野餐垫，找个合适的公园，一起享受户外时光。'),
    dict(name='心愿时光', icon='⭐', detail='和家人商量一个想共同完成的小心愿，安排 30 分钟一起行动。'),
    dict(name='暖心聊天', icon='❤️', detail='和家人聊 20 分钟，轮流分享三件开心的事，认真听听彼此的心情。'),
    dict(name='甜蜜分享', icon='🍦', detail='和家人一起准备喜欢的小甜点，边品尝边聊聊今天的趣事。'),
]
PRIZE_ICONS = [prize['icon'] for prize in PRIZE_PRESETS]
PROVINCES = ['北京市', '天津市', '河北省', '山西省', '内蒙古自治区', '辽宁省', '吉林省', '黑龙江省',
             '上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省', '河南省', '湖北省',
             '湖南省', '广东省', '广西壮族自治区', '海南省', '重庆市', '四川省', '贵州省', '云南省',
             '西藏自治区', '陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区',
             '香港特别行政区', '澳门特别行政区', '台湾省']
REGION_NAMES = ['Beijing', 'Tianjin', 'Hebei', 'Shanxi', 'Inner Mongolia', 'Liaoning', 'Jilin', 'Heilongjiang',
                'Shanghai', 'Jiangsu', 'Zhejiang', 'Anhui', 'Fujian', 'Jiangxi', 'Shandong', 'Henan', 'Hubei',
                'Hunan', 'Guangdong', 'Guangxi', 'Hainan', 'Chongqing', 'Sichuan', 'Guizhou', 'Yunnan',
                'Tibet', 'Shaanxi', 'Gansu', 'Qinghai', 'Ningxia', 'Xinjiang', 'Hong Kong', 'Macao', 'Taiwan']


def letters(text):
    return re.sub('[^a-z]', '', text.lower())


def mask_word(word):
    keep = min(3, max(1, len(letters(word)) // 2))
    count, masked, answer = 0, '', ''
    for char in word:
        if char.isascii() and char.isalpha():
            count += 1
            masked += char if count <= keep else '_'
            if count > keep:
                answer += char.lower()
        else:
            masked += char
    return masked, answer


def province_from_geo(data):
    if data.get('country_code') not in ('CN', 'HK', 'MO', 'TW'):
        return ''
    region = str(data.get('region', '')).strip().lower()
    for english, chinese in zip(REGION_NAMES, PROVINCES):
        if region in (english.lower(), chinese.lower(), chinese[:2]) or region == english.lower() + ' province':
            return chinese
    return ''


def unit_order(word):
    number = re.search(r'\d+', word['unit'])
    return (int(number.group()) if number else 10000, word['unit'], word['id'])


def earned_stars(item):
    if not item['solved']:
        return 0
    return 2 if item['hinted'] else 10 if item['tries'] == 1 else 6 if item['tries'] == 2 else 4


class App:
    def __init__(self, path, now=time.time, seed=True, *, resources=None, day_offset_hours=None, lesson_factory=Phonetics):
        self.path, self.now = Path(path), now
        self.day_offset_hours = day_offset_hours
        self.phonetics = (resources['phonetics'] if resources is not None else
            json.loads((ROOT / 'data' / 'phonetics.json').read_text(encoding='utf-8')))['entries']
        self.textbook_phonetics = resources['textbook_phonetics'] if resources is not None else dict(line.split('\t') for line in
            (ROOT / 'data/sources/official/1212001601265-phonetics.tsv').read_text(encoding='utf-8').splitlines())
        if resources is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS books (id TEXT PRIMARY KEY, metadata TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS words (
                    id INTEGER PRIMARY KEY, book_id TEXT NOT NULL REFERENCES books(id),
                    english TEXT NOT NULL, meaning TEXT NOT NULL, unit TEXT NOT NULL, page TEXT NOT NULL,
                    UNIQUE(book_id, english, unit));
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, book_id TEXT NOT NULL REFERENCES books(id), province TEXT NOT NULL,
                    started REAL NOT NULL, deadline REAL NOT NULL, ended REAL, minutes INTEGER NOT NULL,
                    position INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'active', mode TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
                    position INTEGER NOT NULL, word_id INTEGER NOT NULL REFERENCES words(id),
                    tries INTEGER NOT NULL DEFAULT 0, solved INTEGER NOT NULL DEFAULT 0,
                    hinted INTEGER NOT NULL DEFAULT 0, skipped INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(session_id, position));
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES items(id),
                    number INTEGER NOT NULL, answer TEXT NOT NULL, correct INTEGER NOT NULL,
                    hinted INTEGER NOT NULL, submitted REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS requests (
                    session_id TEXT NOT NULL REFERENCES sessions(id), key TEXT NOT NULL,
                    payload TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(session_id, key));
                CREATE TABLE IF NOT EXISTS rewards (
                    id TEXT PRIMARY KEY, prize_index INTEGER NOT NULL, prize TEXT NOT NULL,
                    cost INTEGER NOT NULL CHECK(cost>0), created_at REAL NOT NULL, redeemed_at REAL);
                CREATE TABLE IF NOT EXISTS reward_config (
                    id INTEGER PRIMARY KEY CHECK(id=1), prizes TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS items_word ON items(word_id, id);
                CREATE INDEX IF NOT EXISTS attempts_item ON attempts(item_id);
            ''')
            if 'learning_order' not in {r['name'] for r in db.execute('PRAGMA table_info(sessions)')}:
                db.execute("ALTER TABLE sessions ADD COLUMN learning_order TEXT NOT NULL DEFAULT 'random'")
            if 'round_number' not in {r['name'] for r in db.execute('PRAGMA table_info(items)')}:
                db.execute('ALTER TABLE items ADD COLUMN round_number INTEGER NOT NULL DEFAULT 1')
            if 'practice_type' not in {r['name'] for r in db.execute('PRAGMA table_info(sessions)')}:
                db.execute("ALTER TABLE sessions ADD COLUMN practice_type TEXT NOT NULL DEFAULT 'hint'")
            columns = {r['name'] for r in db.execute('PRAGMA table_info(sessions)')}
            for name, definition in [('dictation_mode', "TEXT NOT NULL DEFAULT 'auto'"),
                                     ('dictation_seconds', 'INTEGER NOT NULL DEFAULT 15')]:
                if name not in columns:
                    db.execute('ALTER TABLE sessions ADD COLUMN ' + name + ' ' + definition)
            columns = {r['name'] for r in db.execute('PRAGMA table_info(items)')}
            for name, definition in [('writing_deadline', 'REAL'), ('draft', "TEXT NOT NULL DEFAULT ''"),
                                     ('draft_revision', 'INTEGER NOT NULL DEFAULT 0'), ('result', "TEXT NOT NULL DEFAULT ''"),
                                     ('audio_ready', 'INTEGER NOT NULL DEFAULT 0')]:
                if name not in columns:
                    db.execute('ALTER TABLE items ADD COLUMN ' + name + ' ' + definition)
        self.phonetics_lesson = lesson_factory(self, course=resources['course'] if resources is not None else None)
        if seed:
            packs = resources['books'] if resources is not None else (
                json.loads(source.read_text(encoding='utf-8')) for source in sorted((ROOT / 'data' / 'books').glob('*.json')))
            for pack in packs:
                with self.db() as db:
                    exists = db.execute('SELECT 1 FROM books WHERE id=?', (pack['id'],)).fetchone()
                if not exists:
                    self.import_book(pack)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        # ponytail: serialize local transactions; revisit for a multi-user server.
        db.execute('BEGIN IMMEDIATE')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def import_book(self, pack):
        if not isinstance(pack, dict):
            raise ValueError('词库必须是一个 JSON 对象')
        for key in ('id', 'title', 'publisher', 'edition', 'term', 'source_url'):
            if not isinstance(pack.get(key), str) or not pack[key].strip() or len(pack[key]) > 2000:
                raise ValueError('缺少有效字段：' + key)
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', pack['id']):
            raise ValueError('词库 id 只能包含英文字母、数字、下划线和连字符')
        if type(pack.get('grade')) is not int or not 1 <= pack['grade'] <= 12 or pack['term'] not in ('上', '下'):
            raise ValueError('年级须为 1–12，学期须为上或下')
        if urlparse(pack['source_url']).scheme not in ('http', 'https'):
            raise ValueError('来源须为 http 或 https 链接')
        regions = pack.get('regions', [])
        if not isinstance(regions, list) or any(r not in PROVINCES for r in regions):
            raise ValueError('地区名称无效')
        words = pack.get('words')
        if not isinstance(words, list) or not 1 <= len(words) <= 3000:
            raise ValueError('每册须包含 1–3000 个词条')
        clean, seen = [], set()
        for index, word in enumerate(words, 1):
            if not isinstance(word, dict):
                raise ValueError('词条格式错误')
            en, zh = word.get('english', ''), word.get('meaning', '')
            unit, page = word.get('unit', 'Unit 1'), str(word.get('page', ''))
            if not isinstance(en, str) or not re.fullmatch(r"[A-Za-z][A-Za-z '.…\-]{0,78}[A-Za-z.]", en) or len(letters(en)) < 2:
                raise ValueError('第 %s 个词条的英文格式无效' % index)
            if not isinstance(zh, str) or not zh.strip() or len(zh) > 150 or not isinstance(unit, str) or not 1 <= len(unit) <= 60 or len(page) > 20:
                raise ValueError('第 %s 个词条的释义、单元或页码无效' % index)
            key = (en.strip().lower(), unit.strip())
            if key in seen:
                raise ValueError('同一单元出现重复词条：' + en)
            seen.add(key)
            clean.append((pack['id'], en.strip(), zh.strip(), unit.strip(), page))
        meta = {k: pack[k].strip() if isinstance(pack[k], str) else pack[k]
                for k in ('id', 'title', 'publisher', 'edition', 'grade', 'term', 'source_url')}
        meta.update(regions=regions, source_note=str(pack.get('source_note', '用户导入，内容需自行核对'))[:2000])
        with self.db() as db:
            if db.execute('SELECT 1 FROM books WHERE id=?', (pack['id'],)).fetchone():
                raise ValueError('该词库 id 已存在；请使用新的 id，已有记录不会被覆盖')
            db.execute('INSERT INTO books VALUES (?,?)', (pack['id'], json.dumps(meta, ensure_ascii=False)))
            db.executemany('INSERT INTO words(book_id,english,meaning,unit,page) VALUES (?,?,?,?,?)', clean)
        return dict(count=len(clean), title=meta['title'])

    def _session(self, db, sid):
        session = db.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
        if not session:
            raise ValueError('未找到这次练习')
        if session['status'] == 'active' and session['practice_type'] != 'hint':
            item = db.execute('SELECT i.*,w.english FROM items i JOIN words w ON w.id=i.word_id WHERE session_id=? AND position=?',
                              (sid, session['position'])).fetchone()
            if session['dictation_mode'] == 'auto' and item and not item['result'] and item['writing_deadline'] and self.now() >= item['writing_deadline']:
                self._submit_dictation(db, item, item['draft'], expired=True)
        elif session['status'] == 'active' and self.now() >= session['deadline']:
            db.execute("UPDATE sessions SET status='timeout',ended=deadline WHERE id=?", (sid,))
            session = db.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
        return dict(session)

    def _state(self, db, sid, view_position=None):
        session = self._session(db, sid)
        rows = db.execute('SELECT i.*,w.book_id,w.english,w.meaning,w.unit,w.page FROM items i JOIN words w ON w.id=i.word_id WHERE session_id=? ORDER BY position', (sid,)).fetchall()
        meta = json.loads(db.execute('SELECT metadata FROM books WHERE id=?', (session['book_id'],)).fetchone()[0])
        session.update(total=len(rows), scope_total=sum(r['round_number'] == 1 for r in rows), now=self.now(), book=meta, current=None)
        streak, best, stars = 0, 0, 0
        for row in rows:
            if row['position'] >= session['position'] and not row['result']:
                break
            stars += earned_stars(row)
            streak = streak + 1 if row['solved'] and row['tries'] == 1 and not row['hinted'] else 0
            best = max(best, streak)
        session.update(streak=streak, best_streak=best, stars=stars)
        if session['status'] == 'active':
            view_position = session['position'] if view_position is None else view_position
            if type(view_position) is not int or not 0 <= view_position <= session['position']:
                raise ValueError('只能查看已学单词或当前单词')
            session.update(view_position=view_position, readonly=view_position < session['position'])
            row = rows[view_position]
            round_rows = [r for r in rows if r['round_number'] == row['round_number']]
            start = round_rows[0]['position']
            session.update(round_number=row['round_number'], round_position=view_position - start,
                           round_total=len(round_rows), round_completed=min(session['position'] - start, len(round_rows)))
            masked, suffix = mask_word(row['english'])
            meaning = re.sub(r'\b' + re.escape(row['english']) + r'\b', '原词', row['meaning'], flags=re.I)
            session['current'] = dict(word_id=row['word_id'], masked=masked, missing=len(suffix), meaning=meaning,
                                      unit=row['unit'], page=row['page'], tries=row['tries'], hinted=bool(row['hinted']))
            session['current'].update(self.phonetic(row))
            if row['hinted'] or session['readonly']:
                session['current']['reveal'] = row['english']
            if session['practice_type'] != 'hint':
                current = session['current']
                current.update(masked=re.sub('[A-Za-z]', '_', row['english']), missing=len(letters(row['english'])),
                               writing_deadline=row['writing_deadline'], draft=row['draft'],
                               draft_revision=row['draft_revision'], result=row['result'],
                               phase='result' if row['result'] else 'writing' if row['audio_ready'] or row['writing_deadline'] else 'listening')
                if row['result']:
                    current['reveal'] = row['english']
                else:
                    for key in ('meaning', 'phonetic', 'phonetic_note', 'reveal'):
                        current.pop(key, None)
        return session

    def state(self, sid, view_position=None):
        with self.db() as db:
            return self._state(db, sid, view_position)

    def _mistakes(self, db, book_id=None):
        # Success in one practice type cannot clear a different type's outstanding mistake.
        rows = db.execute('''SELECT w.*,i.tries,i.hinted,i.skipped,GROUP_CONCAT(DISTINCT s.practice_type) AS practice_types
            FROM items i JOIN words w ON w.id=i.word_id JOIN sessions s ON s.id=i.session_id
            WHERE i.id IN (SELECT MAX(j.id) FROM items j JOIN sessions t ON t.id=j.session_id
                WHERE j.tries>0 OR j.hinted=1 OR j.skipped=1 GROUP BY j.word_id,t.practice_type)
            AND (i.tries>1 OR i.hinted=1 OR i.skipped=1 OR i.solved=0)
            GROUP BY w.id ORDER BY w.book_id,w.unit,w.english''').fetchall()
        return [dict(r) for r in rows if not book_id or r['book_id'] == book_id]

    def mistakes(self):
        with self.db() as db:
            return self._mistakes(db)

    def start(self, data):
        minutes = data.get('minutes', 15)
        if type(minutes) is not int or not 1 <= minutes <= 180:
            raise ValueError('练习时间须为 1–180 分钟的整数')
        province = data.get('province', '')
        if province and province not in PROVINCES:
            raise ValueError('请选择有效地区')
        mode = data.get('mode', 'learn')
        if mode not in ('learn', 'review'):
            raise ValueError('练习模式无效')
        learning_order = data.get('learning_order', 'random')
        if learning_order not in ('sequential', 'random'):
            raise ValueError('请选择顺序学习或随机学习')
        practice_type = data.get('practice_type', 'hint')
        if practice_type not in ('hint', 'dictation_en', 'dictation_zh'):
            raise ValueError('请选择有效的练习方式')
        dictation_mode, dictation_seconds = data.get('dictation_mode', 'auto'), data.get('dictation_seconds', 15)
        if dictation_mode not in ('auto', 'manual'):
            raise ValueError('请选择自动或手动听写模式')
        if type(dictation_seconds) is not int or not 1 <= dictation_seconds <= 300:
            raise ValueError('每词倒计时须为 1–300 秒的整数')
        with self.db() as db:
            for row in db.execute("SELECT id FROM sessions WHERE status='active'").fetchall():
                if self._session(db, row['id'])['status'] == 'active':
                    raise ValueError('还有未结束的练习，请先继续或结束它')
            book_id = data.get('book_id', '')
            if not db.execute('SELECT 1 FROM books WHERE id=?', (book_id,)).fetchone():
                raise ValueError('该教材尚未收录，请先导入词库')
            if mode == 'review':
                words = self._mistakes(db, book_id)
            else:
                words = [w for w in db.execute('SELECT id,unit FROM words WHERE book_id=? ORDER BY id', (book_id,))
                         if not data.get('unit') or w['unit'] == data['unit']]
            ids = [w['id'] for w in sorted(words, key=unit_order)]
            if not ids:
                raise ValueError('这个范围没有可练习的单词')
            if learning_order == 'random':
                random.SystemRandom().shuffle(ids)
            sid, now = secrets.token_hex(16), self.now()
            db.execute('INSERT INTO sessions(id,book_id,province,started,deadline,minutes,mode,learning_order,practice_type,dictation_mode,dictation_seconds) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       (sid, book_id, province, now, now + minutes * 60, minutes, mode, learning_order, practice_type, dictation_mode, dictation_seconds))
            db.executemany('INSERT INTO items(session_id,position,word_id) VALUES (?,?,?)', [(sid, i, wid) for i, wid in enumerate(ids)])
            return self._state(db, sid)

    def _next_round(self, db, session):
        # New encounters preserve previous answers; only the initial scope can recur.
        rows = db.execute('''SELECT w.*,i.tries,i.solved,i.hinted,i.skipped,i.round_number
            FROM items i JOIN words w ON w.id=i.word_id WHERE session_id=? ORDER BY position''',
            (session['id'],)).fetchall()
        latest = {r['id']: r for r in rows}
        weak = [r for r in latest.values() if r['tries'] > 1 or r['hinted'] or r['skipped'] or not r['solved']]
        ids = [r['id'] for r in sorted(weak or [r for r in rows if r['round_number'] == 1], key=unit_order)]
        if session['learning_order'] == 'random':
            random.SystemRandom().shuffle(ids)
        db.executemany('INSERT INTO items(session_id,position,word_id,round_number) VALUES (?,?,?,?)',
                       [(session['id'], len(rows) + i, wid, rows[-1]['round_number'] + 1) for i, wid in enumerate(ids)])

    def _submit_dictation(self, db, item, answer, expired=False):
        correct = letters(answer) == letters(item['english'])
        result = 'correct' if correct else 'timeout' if expired and len(letters(answer)) < len(letters(item['english'])) else 'wrong'
        submitted = item['writing_deadline'] if expired else self.now()
        db.execute('INSERT INTO attempts(item_id,number,answer,correct,hinted,submitted) VALUES (?,1,?,?,0,?)',
                   (item['id'], answer, int(correct), submitted))
        db.execute('UPDATE items SET tries=1,solved=?,draft=?,result=? WHERE id=?',
                   (int(correct), answer, result, item['id']))

    def act(self, sid, action, data):
        if action not in ('answer', 'hint', 'skip', 'finish', 'ready', 'draft', 'next'):
            raise ValueError('未知操作')
        key = data.get('request_id', '')
        if not isinstance(key, str) or not 1 <= len(key) <= 100:
            raise ValueError('缺少操作编号，请重试')
        payload = json.dumps([action, data], sort_keys=True, ensure_ascii=False)
        with self.db() as db:
            previous = db.execute('SELECT payload,response FROM requests WHERE session_id=? AND key=?', (sid, key)).fetchone()
            if previous:
                if previous['payload'] != payload:
                    raise ValueError('重复操作编号对应不同内容')
                response = json.loads(previous['response'])
                response['session'] = self._state(db, sid)
                return response
            session = self._session(db, sid)
            if session['status'] != 'active':
                return dict(session=self._state(db, sid))
            if type(data.get('position')) is not int or data['position'] != session['position']:
                raise ValueError('题目已变化，请刷新恢复当前进度')
            item = db.execute('SELECT i.*,w.english FROM items i JOIN words w ON i.word_id=w.id WHERE session_id=? AND position=?',
                              (sid, session['position'])).fetchone()
            response, advance = {}, False
            if action == 'finish':
                db.execute("UPDATE sessions SET status='stopped',ended=? WHERE id=?", (self.now(), sid))
            elif session['practice_type'] != 'hint':
                if action not in ('ready', 'draft', 'answer', 'next'):
                    raise ValueError('听写不提供提示或跳过，请交卷后继续')
                if action == 'next':
                    if not item['result']:
                        raise ValueError('请先完成本题听写')
                    if self.now() >= session['deadline']:
                        db.execute("UPDATE sessions SET status='timeout',ended=? WHERE id=?", (self.now(), sid))
                    else:
                        advance = True
                elif not item['result']:
                    if action == 'ready':
                        if not item['audio_ready'] and item['writing_deadline'] is None:
                            deadline = self.now() + session['dictation_seconds'] if session['dictation_mode'] == 'auto' else None
                            db.execute('UPDATE items SET audio_ready=1,writing_deadline=? WHERE id=?', (deadline, item['id']))
                    else:
                        if action == 'answer' and not item['audio_ready'] and item['writing_deadline'] is None:
                            raise ValueError('请先听完两遍朗读')
                        answer = data.get('answer')
                        if not isinstance(answer, str) or len(answer) > 100 or not re.fullmatch(r"[A-Za-z '.\-]*", answer):
                            raise ValueError('请输入英文字母')
                        if action == 'draft':
                            revision = data.get('revision')
                            if type(revision) is not int or not 1 <= revision <= 1000000:
                                raise ValueError('草稿版本无效')
                            db.execute('UPDATE items SET draft=?,draft_revision=? WHERE id=? AND draft_revision<?',
                                       (answer, revision, item['id'], revision))
                        else:
                            self._submit_dictation(db, item, answer)
            elif action in ('ready', 'draft', 'next'):
                raise ValueError('此操作仅用于听写')
            elif action == 'hint':
                db.execute('UPDATE items SET hinted=1 WHERE id=?', (item['id'],))
                response['reveal'] = item['english']
            elif action == 'skip':
                db.execute('UPDATE items SET skipped=1 WHERE id=?', (item['id'],))
                response['reveal'], advance = item['english'], True
            else:
                answer = data.get('answer')
                if not isinstance(answer, str) or len(answer) > 100 or not re.fullmatch(r"[A-Za-z '\-]+", answer) or not letters(answer):
                    raise ValueError('请输入缺少的英文字母')
                correct = letters(answer) == mask_word(item['english'])[1]
                db.execute('INSERT INTO attempts(item_id,number,answer,correct,hinted,submitted) VALUES (?,?,?,?,?,?)',
                           (item['id'], item['tries'] + 1, answer, int(correct), item['hinted'], self.now()))
                db.execute('UPDATE items SET tries=tries+1,solved=? WHERE id=?', (int(correct), item['id']))
                response.update(correct=correct, attempt=item['tries'] + 1)
                if correct:
                    response['reveal'], advance = item['english'], True
            if advance:
                db.execute('UPDATE sessions SET position=position+1 WHERE id=?', (sid,))
                total = db.execute('SELECT COUNT(*) FROM items WHERE session_id=?', (sid,)).fetchone()[0]
                if session['position'] + 1 == total and self._session(db, sid)['status'] == 'active':
                    self._next_round(db, session)
            response['session'] = self._state(db, sid)
            db.execute('INSERT INTO requests VALUES (?,?,?,?)', (sid, key, payload, json.dumps(response, ensure_ascii=False)))
            return response

    def _report(self, db, sid):
        state = self._state(db, sid)
        rows = db.execute('SELECT i.*,w.english,w.meaning,w.unit FROM items i JOIN words w ON w.id=i.word_id WHERE session_id=? ORDER BY position', (sid,)).fetchall()
        first = [r for r in rows if r['round_number'] == 1]
        first_wrong = db.execute('SELECT COUNT(*) FROM attempts a JOIN items i ON i.id=a.item_id WHERE i.session_id=? AND i.round_number=1 AND a.number=1 AND a.correct=0', (sid,)).fetchone()[0]
        result = {k: state[k] for k in ('id', 'status', 'book', 'total', 'started', 'ended', 'minutes', 'stars', 'best_streak', 'mode', 'province', 'practice_type', 'dictation_mode', 'dictation_seconds')}
        round_ends = {r['round_number']: r['position'] for r in rows}
        result.update(total=len(first), attempted=sum(r['tries'] > 0 for r in first), first_wrong=first_wrong,
                      first_correct=sum(bool(r['solved'] and r['tries'] == 1 and not r['hinted']) for r in first),
                      second_correct=sum(bool(r['solved'] and r['tries'] == 2 and not r['hinted']) for r in first),
                      solved=len({r['word_id'] for r in rows if r['solved']}), hinted=sum(r['hinted'] for r in first),
                      skipped=sum(r['skipped'] for r in first), remaining=sum(not r['solved'] and not r['skipped'] for r in first),
                      practice_completed=state['position'], rounds_completed=sum(end < state['position'] for end in round_ends.values()),
                      reinforcement_solved=sum(r['solved'] for r in rows if r['round_number'] > 1),
                      elapsed=max(0, round((state['ended'] or min(self.now(), state['deadline'])) - state['started'])))
        if state['practice_type'] != 'hint':
            result.update(dictation_correct=sum(r['result'] == 'correct' for r in rows),
                          dictation_wrong=sum(r['result'] == 'wrong' for r in rows),
                          dictation_timeout=sum(r['result'] == 'timeout' for r in rows),
                          practice_completed=sum(bool(r['result']) for r in rows),
                          remaining=sum(not r['result'] for r in first),
                          rounds_completed=sum(all(r['result'] for r in rows if r['round_number'] == n) for n in round_ends))
        result['words'] = []
        for r in rows:
            if r['round_number'] > 1 and not (r['tries'] or r['hinted'] or r['skipped']):
                continue
            attempts = [dict(a) for a in db.execute('SELECT number,answer,correct,hinted,submitted FROM attempts WHERE item_id=? ORDER BY number', (r['id'],))]
            result['words'].append(dict(english=r['english'], meaning=r['meaning'], unit=r['unit'], tries=r['tries'], round_number=r['round_number'],
                                        solved=bool(r['solved']), hinted=bool(r['hinted']), skipped=bool(r['skipped']), result=r['result'], attempts=attempts))
        return result

    def report(self, sid):
        with self.db() as db:
            return self._report(db, sid)

    def _completed_words(self, db, scope='all'):
        offset = self.day_offset_hours
        today = time.strftime('%Y-%m-%d', time.localtime(self.now()) if offset is None else time.gmtime(self.now() + offset * 3600))
        modifier = 'localtime' if offset is None else '%+d hours' % offset
        rows = db.execute('''SELECT w.*,s.province,b.metadata,COUNT(DISTINCT i.id) AS frequency,
                MAX(a.submitted) AS completed_at
            FROM attempts a JOIN items i ON i.id=a.item_id JOIN words w ON w.id=i.word_id
            JOIN sessions s ON s.id=i.session_id JOIN books b ON b.id=w.book_id
            WHERE a.correct=1 AND (?='all' OR date(a.submitted,'unixepoch',?)=?)
            GROUP BY w.id,s.province ORDER BY completed_at DESC,w.id,s.province''', (scope, modifier, today))
        words = {}
        for row in rows:
            key = ' '.join(row['english'].casefold().split())
            word = words.setdefault(key, dict(english=row['english'], completed_at=row['completed_at'], frequency=0, sources=[]))
            word['frequency'] += row['frequency']
            book = json.loads(row['metadata'])
            word['sources'].append(dict(word_id=row['id'], completed_at=row['completed_at'],
                phonetic=self.phonetic(row)['phonetic'], meaning=row['meaning'], unit=row['unit'],
                term=book['term'], grade=book['grade'], book=book['title'], publisher=book['publisher'],
                edition=book['edition'], province=row['province']))
        return dict(scope=scope, date=today, total=len(words), words=list(words.values()))

    def completed_words(self, scope='all'):
        if scope not in ('all', 'today'):
            raise ValueError('请选择累计或今日学习记录')
        with self.db() as db:
            return self._completed_words(db, scope)

    def _wallet(self, db):
        earned = sum(earned_stars(r) for r in db.execute('''SELECT i.solved,i.tries,i.hinted FROM items i
            JOIN sessions s ON s.id=i.session_id WHERE (i.position<s.position OR i.result!='') AND i.solved=1'''))
        spent = db.execute('SELECT COALESCE(SUM(cost),0) FROM rewards').fetchone()[0]
        return dict(earned=earned, spent=spent, available=earned-spent)

    def _reward(self, row):
        result = dict(row)
        result['prize'] = json.loads(result['prize'])
        return result

    def _reward_config(self, db):
        row = db.execute('SELECT prizes FROM reward_config WHERE id=1').fetchone()
        prizes = json.loads(row[0]) if row else FAMILY_PRIZES
        revision = hashlib.sha256(json.dumps(dict(prizes=prizes, cost=DRAW_COST), sort_keys=True).encode()).hexdigest()
        return dict(prizes=prizes, revision=revision, icons=PRIZE_ICONS, presets=PRIZE_PRESETS, cost=DRAW_COST)

    def reward_config(self):
        with self.db() as db:
            return self._reward_config(db)

    def save_reward_config(self, data):
        prizes = data.get('prizes')
        if not isinstance(prizes, list) or len(prizes) != 8:
            raise ValueError('请设置完整的八个奖品')
        clean = []
        for index, prize in enumerate(prizes, 1):
            if not isinstance(prize, dict):
                raise ValueError('奖品格式无效')
            item = {}
            for key, limit, label in [('name', 12, '名称'), ('icon', 16, '图标'), ('detail', 120, '活动说明')]:
                value = prize.get(key)
                if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
                    raise ValueError('奖品%s的%s须为1–%s个字' % (index, label, limit))
                item[key] = value.strip()
            if item['icon'] not in PRIZE_ICONS or any(ord(c) < 32 for c in item['name']):
                raise ValueError('请选择提供的图标，名称不能含换行或控制字符')
            clean.append(item)
        with self.db() as db:
            current = self._reward_config(db)
            if data.get('revision') != current['revision']:
                raise ValueError('奖品已在其他页面更新，请重新打开设置后再修改')
            db.execute('INSERT OR REPLACE INTO reward_config(id,prizes) VALUES(1,?)',
                       (json.dumps(clean, ensure_ascii=False),))
            return self._reward_config(db)

    def rewards(self):
        with self.db() as db:
            return dict(wallet=self._wallet(db), **self._reward_config(db),
                        draws=[self._reward(r) for r in db.execute('SELECT * FROM rewards ORDER BY created_at DESC,rowid DESC')])

    def draw_reward(self, data):
        key = data.get('request_id')
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', key):
            raise ValueError('缺少有效抽奖编号，请重试')
        with self.db() as db:
            config = self._reward_config(db)
            row = db.execute('SELECT * FROM rewards WHERE id=?', (key,)).fetchone()
            if not row:
                if data.get('config_revision') != config['revision']:
                    raise ValueError('奖品或星星消耗已更新，本次未扣星。请刷新页面后再抽奖')
                if self._wallet(db)['available'] < DRAW_COST:
                    raise ValueError('星星不足，每次抽奖需要 %s 星' % DRAW_COST)
                index = secrets.randbelow(len(config['prizes']))
                db.execute('INSERT INTO rewards(id,prize_index,prize,cost,created_at) VALUES (?,?,?,?,?)',
                           (key, index, json.dumps(config['prizes'][index], ensure_ascii=False), DRAW_COST, self.now()))
                row = db.execute('SELECT * FROM rewards WHERE id=?', (key,)).fetchone()
            return dict(draw=self._reward(row), wallet=self._wallet(db), config=config)

    def redeem_reward(self, key):
        with self.db() as db:
            if not db.execute('SELECT 1 FROM rewards WHERE id=?', (key,)).fetchone():
                raise ValueError('未找到这份奖品')
            db.execute('UPDATE rewards SET redeemed_at=COALESCE(redeemed_at,?) WHERE id=?', (self.now(), key))
            return self._reward(db.execute('SELECT * FROM rewards WHERE id=?', (key,)).fetchone())

    def bootstrap(self):
        with self.db() as db:
            active = None
            for row in db.execute("SELECT id FROM sessions WHERE status='active'").fetchall():
                if self._session(db, row['id'])['status'] == 'active':
                    active = self._state(db, row['id'])
            books = []
            for row in db.execute('SELECT metadata FROM books ORDER BY id'):
                book = json.loads(row[0])
                units = [dict(r) for r in db.execute('SELECT unit,COUNT(*) AS count FROM words WHERE book_id=? GROUP BY unit ORDER BY unit', (book['id'],))]
                book.update(units=units, count=sum(u['count'] for u in units))
                books.append(book)
            history = []
            for row in db.execute("SELECT id FROM sessions WHERE status!='active' ORDER BY started DESC").fetchall():
                report = self._report(db, row['id'])
                report.pop('words')
                history.append(report)
            wallet = self._wallet(db)
            return dict(books=books, provinces=PROVINCES, active=active, history=history[:100],
                        summary=dict(stars=wallet['earned'], available_stars=wallet['available'], spent_stars=wallet['spent'],
                                     sessions=len(history), mistakes=len(self._mistakes(db)),
                                     completed_words=self._completed_words(db)['total'],
                                     today_words=self._completed_words(db, 'today')['total']),
                        native_voice=bool(shutil.which('say')))

    def vocabulary(self, book_id):
        with self.db() as db:
            return [dict(r) for r in db.execute('SELECT * FROM words WHERE book_id=? ORDER BY unit,id', (book_id,))]

    def phonetic(self, word):
        if 'book_id' in word.keys() and word['book_id'] == 'pep-official-1212001601265':
            ipa = self.textbook_phonetics.get(word['english'])
            if ipa:
                return dict(phonetic=ipa, phonetic_note='教材格式；短语未注部分用英式参考补全，中文地名保留拼音')
        entry = self.phonetics.get(word['english'].lower(), {})
        ipa = entry.get('ipa', '')
        if word['english'].lower() == 'read' and re.search(r'read\s*的过去式', word['meaning']):
            ipa = '/ˈɹɛd/'
        return dict(phonetic=ipa.replace('ɹ', 'r').replace('ɫ', 'l'), phonetic_note=entry.get('note', '音标待补充'))

    def speech(self, word_id, lang, dictation=False):
        with self.db() as db:
            word = db.execute('SELECT english,meaning FROM words WHERE id=?', (word_id,)).fetchone()
            if not word:
                raise ValueError('单词不存在')
            if lang == 'zh':
                return re.sub('[A-Za-z]+', '', word['meaning']) if dictation else word['meaning']
            # The past-tense "read" is pronounced like "red" in the six下 glossary.
            if word['english'] == 'read' and re.search(r'read\s*的过去式', word['meaning']):
                return 'red'
            return word['english']


def serve(app, port):
    audio_lock = threading.Lock()
    cache = app.path.parent / 'audio'
    cache.mkdir(exist_ok=True)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # No IP addresses or student answers in console logs.

        def output(self, value, status=200, mime='application/json; charset=utf-8'):
            body = json.dumps(value, ensure_ascii=False).encode() if not isinstance(value, bytes) else value
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store' if not mime.startswith('audio/') else 'private, max-age=86400')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob: https://dictionary.cambridge.org; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def media(self, source, mime):
            size = source.stat().st_size
            start, end, status = 0, size - 1, 200
            requested = self.headers.get('Range')
            if requested:
                match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested)
                if match and (match[1] or match[2]):
                    if not match[1]:
                        start = max(0, size - int(match[2]))
                    else:
                        start = int(match[1])
                        end = min(end, int(match[2])) if match[2] else end
                if not match or not (match[1] or match[2]) or not 0 <= start <= end < size:
                    self.send_response(416)
                    self.send_header('Content-Range', 'bytes */%s' % size)
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                status = 206
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(end - start + 1))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if status == 206:
                self.send_header('Content-Range', 'bytes %s-%s/%s' % (start, end, size))
            self.end_headers()
            if self.command != 'HEAD':
                with source.open('rb') as file:
                    file.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        block = file.read(min(65536, remaining))
                        if not block:
                            break
                        self.wfile.write(block)
                        remaining -= len(block)

        def do_HEAD(self):
            self.do_GET()

        def valid_host(self):
            host = self.headers.get('Host', '')
            bound_port = self.server.server_port
            return host in ('127.0.0.1:%s' % bound_port, 'localhost:%s' % bound_port)

        def do_GET(self):
            try:
                if not self.valid_host():
                    return self.output({'error': '只允许本机访问'}, 403)
                parsed = urlparse(self.path)
                path = parsed.path
                if path == '/api/phonetics':
                    return self.output(app.phonetics_lesson.overview())
                if path == '/api/phonetics/config':
                    return self.output(app.phonetics_lesson.service())
                match = re.fullmatch(r'/api/phonetics/tests/([a-f0-9]{32})(?:/audio/(\d+))?', path)
                if match:
                    if match[2] is not None:
                        return self.output(app.phonetics_lesson.audio(match[1], int(match[2])), mime='audio/wav')
                    return self.output(app.phonetics_lesson.state(match[1]))
                if path in ('/media/phonetics/lesson.mp4', '/media/phonetics/lesson.mp3'):
                    return self.media(ROOT / 'data/phonetics-media' / Path(path).name,
                                      'video/mp4' if path.endswith('.mp4') else 'audio/mpeg')
                if path == '/api/bootstrap':
                    return self.output(app.bootstrap())
                if path == '/api/rewards':
                    return self.output(app.rewards())
                if path == '/api/rewards/config':
                    return self.output(app.reward_config())
                if path == '/api/location':
                    try:
                        request = urllib.request.Request('https://ipapi.co/json/', headers={'User-Agent': 'WordIsle/1.0'})
                        with urllib.request.urlopen(request, timeout=3) as response:
                            data = json.loads(response.read(100000))
                        province = province_from_geo(data)
                        return self.output(dict(province=province, message='已根据网络位置推荐地区，请核对' if province else '未定位到可用省份，请手动选择'))
                    except Exception:
                        return self.output(dict(province='', message='自动定位暂不可用，请手动选择地区'))
                if path == '/api/mistakes':
                    return self.output(app.mistakes())
                if path == '/api/completed-words':
                    return self.output(app.completed_words(parse_qs(parsed.query).get('scope', ['all'])[0]))
                if path == '/api/words':
                    return self.output(app.vocabulary(parse_qs(parsed.query).get('book_id', [''])[0]))
                match = re.fullmatch(r'/api/session/([a-f0-9]{32})(/report)?', path)
                if match:
                    position = parse_qs(parsed.query).get('position', [None])[0]
                    return self.output(app.report(match[1]) if match[2] else app.state(match[1], int(position) if position is not None else None))
                match = re.fullmatch(r'/api/audio/(\d+)', path)
                if match:
                    lang = 'zh' if parse_qs(parsed.query).get('lang') == ['zh'] else 'en'
                    spoken = app.speech(int(match[1]), lang, parse_qs(parsed.query).get('dictation') == ['1'])
                    if not shutil.which('say'):
                        return self.output(dict(fallback=True, text=spoken, lang='zh-CN' if lang == 'zh' else 'en-US'))
                    target = cache / (hashlib.sha256((lang + ':' + spoken).encode()).hexdigest() + '.wav')
                    with audio_lock:
                        if not target.exists():
                            with tempfile.NamedTemporaryFile(suffix='.wav', dir=cache, delete=False) as file:
                                tmp = Path(file.name)
                            try:
                                subprocess.run(['say', '-v', 'Tingting' if lang == 'zh' else 'Samantha', '-r', '160' if lang == 'zh' else '145',
                                                '--data-format=LEI16@22050', '-o', str(tmp), spoken], check=True, timeout=12,
                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                tmp.replace(target)
                            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
                                return self.output(dict(fallback=True, text=spoken, lang='zh-CN' if lang == 'zh' else 'en-US'))
                            finally:
                                tmp.unlink(missing_ok=True)
                    return self.output(target.read_bytes(), mime='audio/wav')
                static = {'/': 'index.html', '/index.html': 'index.html', '/style.css': 'style.css', '/app.js': 'app.js', '/phonetics.js': 'phonetics.js', '/favicon.svg': 'favicon.svg'}
                if path in static:
                    mime = 'text/css' if path.endswith('.css') else 'text/javascript' if path.endswith('.js') else 'image/svg+xml' if path.endswith('.svg') else 'text/html'
                    return self.output((ROOT / 'static' / static[path]).read_bytes(), mime=mime + '; charset=utf-8')
                self.output({'error': '页面不存在'}, 404)
            except (ValueError, KeyError) as error:
                self.output({'error': str(error)}, 400)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.output({'error': '本地服务暂时无法完成请求，请重试'}, 500)

        def do_POST(self):
            try:
                host = self.headers.get('Host', '')
                if not self.valid_host() or self.headers.get('Origin') not in ('http://' + host, None):
                    return self.output({'error': '请求来源无效'}, 403)
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    return self.output({'error': '只接受 JSON 请求'}, 415)
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 2_000_000:
                    return self.output({'error': '请求大小须小于 2 MB'}, 413)
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError('请求格式无效')
                if self.path == '/api/phonetics/prepare':
                    return self.output(app.phonetics_lesson.local.prepare())
                if self.path == '/api/phonetics/config':
                    return self.output(app.phonetics_lesson.configure(data))
                if self.path == '/api/phonetics/tests':
                    return self.output(app.phonetics_lesson.start(data))
                match = re.fullmatch(r'/api/phonetics/tests/([a-f0-9]{32})/(assess|skip|finish|delete)', self.path)
                if match:
                    return self.output(app.phonetics_lesson.act(match[1], match[2], data))
                if self.path == '/api/start':
                    return self.output(app.start(data))
                if self.path == '/api/import':
                    return self.output(app.import_book(data))
                if self.path == '/api/rewards/draw':
                    return self.output(app.draw_reward(data))
                if self.path == '/api/rewards/config':
                    return self.output(app.save_reward_config(data))
                reward = re.fullmatch(r'/api/rewards/([A-Za-z0-9_-]{1,100})/redeem', self.path)
                if reward:
                    return self.output(app.redeem_reward(reward[1]))
                match = re.fullmatch(r'/api/session/([a-f0-9]{32})/(answer|hint|skip|finish|ready|draft|next)', self.path)
                if match:
                    return self.output(app.act(match[1], match[2], data))
                self.output({'error': '操作不存在'}, 404)
            except (ValueError, KeyError, TypeError) as error:
                self.output({'error': str(error)}, 400)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.output({'error': '保存失败，请保留当前页面后重试'}, 500)
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='词屿 · 本地背单词')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--db', type=Path, default=ROOT / 'data' / 'words.sqlite3')
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    application = App(args.db)
    try:
        server = serve(application, args.port)
    except OSError:
        raise SystemExit('端口已被使用。若词屿已启动，请打开 http://127.0.0.1:%s；否则更换 --port。' % args.port)
    url = 'http://127.0.0.1:%s' % args.port
    print('词屿已启动：' + url + '\n学习记录：' + str(args.db) + '\n关闭此窗口或按 Ctrl+C 停止服务。', flush=True)
    if args.open:
        import webbrowser
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
