from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any


_PASSWORD_ITERATIONS = 210_000
_PASSWORD_SALT_BYTES = 16


class TokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_PASSWORD_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PASSWORD_ITERATIONS,
    )
    return "$".join(
        [
            "pbkdf2_sha256",
            str(_PASSWORD_ITERATIONS),
            _b64url_encode(salt),
            _b64url_encode(digest),
        ]
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            _b64url_decode(salt),
            int(iterations),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(_b64url_encode(digest), expected)


def create_access_token(
    *,
    user_id: int,
    secret: str,
    expires_delta: timedelta,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return _sign_token(payload, secret)


def decode_access_token(token: str, *, secret: str) -> dict[str, Any]:
    payload = _decode_signed_token(token, secret)
    if payload.get("typ") != "access":
        raise TokenError("Invalid token type")
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(datetime.now(timezone.utc).timestamp()):
        raise TokenError("Token has expired")
    return payload


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_numeric_code(length: int = 6) -> str:
    upper_bound = 10**length
    return f"{secrets.randbelow(upper_bound):0{length}d}"


def _sign_token(payload: dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = _b64url_json(header)
    payload_part = _b64url_json(payload)
    message = f"{header_part}.{payload_part}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{_b64url_encode(signature)}"


def _decode_signed_token(token: str, secret: str) -> dict[str, Any]:
    try:
        header_part, payload_part, signature_part = token.split(".", 2)
    except ValueError as exc:
        raise TokenError("Malformed token") from exc

    message = f"{header_part}.{payload_part}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    actual = _b64url_decode(signature_part)
    if not hmac.compare_digest(actual, expected):
        raise TokenError("Invalid token signature")

    try:
        payload = json.loads(_b64url_decode(payload_part))
    except json.JSONDecodeError as exc:
        raise TokenError("Malformed token payload") from exc
    if not isinstance(payload, dict):
        raise TokenError("Malformed token payload")
    return payload


def _b64url_json(value: dict[str, Any]) -> str:
    data = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _b64url_encode(data)


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
