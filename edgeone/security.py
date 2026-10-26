"""Native Python password hashing; shared cookie wire format with the cloud UI."""
import hashlib
import hmac
import re
import secrets
import time

SESSION_SECONDS = 7*86400
ITERATIONS = 600_000


def valid_account(username, password):
    return (isinstance(username,str) and bool(re.fullmatch(r'[a-z0-9][a-z0-9_-]{2,31}',username))
            and isinstance(password,str) and 12 <= len(password) <= 128)


def password_hash(password, salt):
    return 'pbkdf2_sha256$600000$'+hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),ITERATIONS).hex()


def issue_session(uid, secret):
    payload = '%s.%s.%s' % (uid,int(time.time())+SESSION_SECONDS,secrets.token_hex(12))
    return payload+'.'+hmac.new(secret.encode(),payload.encode(),hashlib.sha256).hexdigest()


def verify_session(token, secret):
    if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{32}\.\d{1,12}\.[a-f0-9]{24}\.[a-f0-9]{64}',token): return None
    uid,expires,nonce,signature = token.split('.')
    if not time.time() < int(expires) <= time.time()+SESSION_SECONDS: return None
    payload = uid+'.'+expires+'.'+nonce
    expected = hmac.new(secret.encode(),payload.encode(),hashlib.sha256).hexdigest()
    return uid if hmac.compare_digest(signature,expected) else None
