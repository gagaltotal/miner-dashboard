"""
Password hashing and session tokens.

Two deliberate choices worth calling out:

1. Password hashing uses Argon2id (via argon2-cffi), the OWASP-recommended
   choice, with per-password random salts and constant-time verification
   handled internally by the library.

2. Session tokens are a minimal, hand-rolled HMAC-SHA256 signed payload
   instead of a JWT. This is intentional: JWT's historical CVEs are almost
   all algorithm-confusion bugs (`alg: none`, RS256/HS256 key confusion,
   etc.) that exist *because* the token format lets the client choose the
   algorithm. Our format has exactly one algorithm, hardcoded, never read
   from attacker-controlled input, so that entire bug class does not apply.
   The whole implementation is ~40 lines and easy to audit end to end,
   which is worth more here than the extra features a JWT library brings.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

from app.config import settings

_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


@dataclass
class TokenPayload:
    subject: str
    issued_at: float
    expires_at: float


def issue_token(subject: str, ttl_seconds: int) -> str:
    now = time.time()
    payload = {"sub": subject, "iat": now, "exp": now + ttl_seconds}
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(settings.secret_key, body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url_encode(signature)}"


def verify_token(token: str) -> TokenPayload | None:
    """Return the decoded payload if `token` is validly signed and unexpired, else None."""
    try:
        body, signature_b64 = token.split(".", 1)
    except ValueError:
        return None

    expected_sig = hmac.new(settings.secret_key, body.encode("ascii"), hashlib.sha256).digest()
    try:
        given_sig = _b64url_decode(signature_b64)
    except Exception:
        return None

    # Constant-time comparison: never let a timing side-channel leak how many
    # signature bytes matched.
    if not hmac.compare_digest(expected_sig, given_sig):
        return None

    try:
        payload = json.loads(_b64url_decode(body))
        subject = str(payload["sub"])
        issued_at = float(payload["iat"])
        expires_at = float(payload["exp"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None

    if time.time() > expires_at:
        return None

    return TokenPayload(subject=subject, issued_at=issued_at, expires_at=expires_at)


def new_csrf_token() -> str:
    import secrets as _secrets

    return _secrets.token_urlsafe(32)
