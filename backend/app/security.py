"""Password hashing and access tokens.

Passwords are HASHED with Argon2, not encrypted — the difference matters: there
is no key that turns a stored hash back into the original password. Nobody, the
admin included, can read a user's password. Resetting one means setting a new
one, which is what the admin dashboard does.
"""

import logging
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

if not SECRET_KEY_FROM_ENV:  # pragma: no cover - startup diagnostics
    # This flag existed and was referenced nowhere, standing in for a guard that
    # was never wired up. Without the env var each process invents its own key,
    # so every restart signs everyone out — and with more than one worker,
    # requests land on whichever process happens to answer and fail at random.
    logging.getLogger(__name__).warning(
        "TM_SECRET_KEY is not set. A random signing key was generated for this "
        "process: tokens will not survive a restart and will not validate "
        "across workers. Set it before any deployment that matters."
    )


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
