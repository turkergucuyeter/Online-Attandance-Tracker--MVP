import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Dict, Any

DEFAULT_ITERATIONS = 310000
HASH_NAME = 'sha256'
SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(HASH_NAME, password.encode('utf-8'), salt, DEFAULT_ITERATIONS)
    return '$'.join([
        HASH_NAME,
        str(DEFAULT_ITERATIONS),
        base64.b64encode(salt).decode('utf-8'),
        base64.b64encode(dk).decode('utf-8')
    ])


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_b64, hash_b64 = stored.split('$')
    except ValueError:
        return False
    if algorithm != HASH_NAME:
        return False
    salt = base64.b64decode(salt_b64)
    expected = base64.b64decode(hash_b64)
    dk = hashlib.pbkdf2_hmac(algorithm, password.encode('utf-8'), salt, int(iterations))
    return hmac.compare_digest(dk, expected)


def encode_jwt(payload: Dict[str, Any], secret: str, expires_in: int = 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = payload.copy()
    payload['exp'] = int(time.time()) + expires_in

    def b64(data: Dict[str, Any]) -> str:
        raw = json.dumps(data, separators=(',', ':'), sort_keys=True).encode('utf-8')
        return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('utf-8')

    segments = [b64(header), b64(payload)]
    signing_input = '.'.join(segments).encode('utf-8')
    signature = hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
    segments.append(base64.urlsafe_b64encode(signature).rstrip(b'=').decode('utf-8'))
    return '.'.join(segments)


def decode_jwt(token: str, secret: str) -> Dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split('.')
    except ValueError:
        raise ValueError('Invalid token')

    def b64decode(data: str) -> Dict[str, Any]:
        padding = '=' * (-len(data) % 4)
        decoded = base64.urlsafe_b64decode(data + padding)
        return json.loads(decoded.decode('utf-8'))

    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    expected_sig = hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
    padding = '=' * (-len(signature_b64) % 4)
    signature = base64.urlsafe_b64decode(signature_b64 + padding)
    if not hmac.compare_digest(expected_sig, signature):
        raise ValueError('Invalid signature')

    payload = b64decode(payload_b64)
    if payload.get('exp') and payload['exp'] < int(time.time()):
        raise ValueError('Token expired')
    return payload
