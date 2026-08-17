"""Password hashing and access tokens.

Passwords are HASHED with Argon2, not encrypted — the difference matters: there
is no key that turns a stored hash back into the original password. Nobody, the
admin included, can read a user's password. Resetting one means setting a new
one, which is what the admin dashboard does.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()

ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 12

# A generated fallback keeps dev running without setup, but it rotates on every
# restart (invalidating live tokens) — so production must set the env var.
SECRET_KEY = os.environ.get("TM_SECRET_KEY") or secrets.token_urlsafe(48)
SECRET_KEY_FROM_ENV = "TM_SECRET_KEY" in os.environ


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _hasher.verify(plain, hashed)


def create_access_token(user_id: int, extra: dict | None = None) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
        "iat": datetime.now(timezone.utc),
        **(extra or {}),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Returns the payload, or None if the token is invalid or expired."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
