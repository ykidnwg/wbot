"""Cryptographic helpers for OAuth state and social access-token envelopes."""

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def new_oauth_state() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


def hash_oauth_state(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def encrypt_token(token: str, encoded_key: str) -> str:
    key = _decode_key(encoded_key)
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key).encrypt(nonce, token.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_token(envelope: str, encoded_key: str) -> str:
    key = _decode_key(encoded_key)
    payload = base64.urlsafe_b64decode(envelope.encode("ascii"))
    if len(payload) <= 12:
        raise ValueError("Invalid token envelope")
    return AESGCM(key).decrypt(payload[:12], payload[12:], None).decode("utf-8")


def token_key_is_valid(encoded_key: str | None) -> bool:
    if not encoded_key:
        return False
    try:
        _decode_key(encoded_key)
    except ValueError:
        return False
    return True


def _decode_key(encoded_key: str) -> bytes:
    try:
        key = base64.urlsafe_b64decode(encoded_key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValueError("TOKEN_ENCRYPTION_KEY must be URL-safe base64") from exc
    if len(key) != 32:
        raise ValueError("TOKEN_ENCRYPTION_KEY must decode to 32 bytes")
    return key


def oauth_expiry(minutes: int = 10) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
