"""Small account/session primitives shared by the Worker and unit tests."""
import hashlib
import hmac
import re
import secrets
import time

SESSION_SECONDS = 7 * 86400
# Workers production caps native PBKDF2 at 100,000; local workerd does not.
# https://github.com/cloudflare/workerd/issues/1346
PASSWORD_ITERATIONS = 100_000


def valid_account(username, password):
    return (isinstance(username, str) and bool(re.fullmatch(r'[a-z0-9][a-z0-9_-]{2,31}', username))
            and isinstance(password, str) and 12 <= len(password) <= 128)


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), PASSWORD_ITERATIONS).hex()


async def webcrypto_password_hash(password, salt, iterations=PASSWORD_ITERATIONS):
    # Pyodide omits hashlib.pbkdf2_hmac; use native Web Crypto.
    from js import crypto, Uint8Array, Object
    from pyodide.ffi import to_js
    key = await crypto.subtle.importKey('raw', to_js(password.encode()), 'PBKDF2', False, to_js(['deriveBits']))
    bits = await crypto.subtle.deriveBits(to_js({'name':'PBKDF2', 'salt':to_js(bytes.fromhex(salt)),
        'iterations':iterations, 'hash':'SHA-256'}, dict_converter=Object.fromEntries), key, 256)
    return Uint8Array.new(bits).to_bytes().hex()


def encode_password_hash(digest):
    return 'pbkdf2_sha256$%s$%s' % (PASSWORD_ITERATIONS, digest)


def password_parameters(stored):
    # Preserve verification of accounts previously created in local workerd.
    if re.fullmatch(r'[a-f0-9]{64}', stored): return 600_000, stored
    match = re.fullmatch(r'pbkdf2_sha256\$(100000)\$([a-f0-9]{64})', stored)
    if not match: raise ValueError('Unsupported stored password format')
    return int(match[1]), match[2]


def issue_session(uid, secret, now=None):
    expires = int(time.time() if now is None else now) + SESSION_SECONDS
    payload = '%s.%s.%s' % (uid, expires, secrets.token_hex(12))
    return payload + '.' + hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_session(token, secret, now=None):
    if not isinstance(token, str) or not re.fullmatch(r'[a-f0-9]{32}\.\d{1,12}\.[a-f0-9]{24}\.[a-f0-9]{64}', token):
        return None
    uid, expires, nonce, signature = token.split('.')
    now = time.time() if now is None else now
    if not now < int(expires) <= now + SESSION_SECONDS:
        return None
    expected = hmac.new(secret.encode(), (uid+'.'+expires+'.'+nonce).encode(), hashlib.sha256).hexdigest()
    return uid if hmac.compare_digest(signature, expected) else None
