"""Password hashing and JWT issuance/verification for Phase 8 auth.

Replaces the interim X-User-Id header (see [[tenant-isolation]] guardrail):
`get_current_user_id` in app/api/deps.py now requires a valid Bearer token
minted here instead of trusting a client-supplied user id.
"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

_TOKEN_SUBJECT_CLAIM = "sub"


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash (e.g. a placeholder seeded outside this module) —
        # never treat that as a successful login.
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        _TOKEN_SUBJECT_CLAIM: str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


class InvalidTokenError(Exception):
    pass


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return uuid.UUID(payload[_TOKEN_SUBJECT_CLAIM])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise InvalidTokenError("Invalid or expired token") from exc
