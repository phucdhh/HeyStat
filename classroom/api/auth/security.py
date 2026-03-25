"""JWT helpers — stateless access token (15 min) + refresh token (7 days)."""
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
import secrets

import bcrypt
from jose import JWTError, jwt

from config import get_settings

settings = get_settings()

_BCRYPT_ROUNDS = 12


# ─── password ──────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ─── tokens ────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(user_id: str, roles: list[str]) -> str:
    expire = _now() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "roles": roles,
        "exp": expire,
        "iat": _now(),
        "jti": str(uuid.uuid4()),
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(user_id: str) -> str:
    """Opaque random token stored in Redis/DB for validation."""
    return secrets.token_hex(32)


def decode_access_token(token: str) -> dict:
    """Raises JWTError if invalid/expired."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    return payload
