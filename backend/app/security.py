"""Password hashing and access tokens.

Passwords are HASHED with Argon2, not encrypted — the difference matters: there
is no key that turns a stored hash back into the original password. Nobody, the
admin included, can read a user's password. Resetting one means setting a new
one, which is what the admin dashboard does.
"""

import hashlib
import hmac
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


def password_fingerprint(hashed_password: str) -> str:
    """A short, non-reversible tag for the CURRENT password hash.

    Stamped into every token as `pwd` and re-checked on every request, so
    changing a password invalidates that user's outstanding tokens.

    Without it, a reset only stops FUTURE logins: the TTL is 12 hours, nothing
    tracks a token version, and the hash is not consulted again after login. So
    resetting the password of a compromised account — the remedy the admin
    dashboard exists to provide — left the attacker's bearer token working for
    up to half a day. Deactivating the user DID take effect immediately, because
    current_user re-reads is_active, which made the asymmetry easy to miss:
    the weaker-looking remedy was the effective one.

    HMAC keyed on the signing secret rather than a bare digest, so the value
    reveals nothing about the hash even if a token is captured, and 16 hex
    characters because this identifies a version rather than authenticating
    anything — the JWT signature already does that.

    No new column, and therefore no migration: the password hash IS the version
    marker, since it necessarily changes when the password does.
    """
    return hmac.new(
        SECRET_KEY.encode(), hashed_password.encode(), hashlib.sha256
    ).hexdigest()[:16]


def create_access_token(
    user_id: int, extra: dict | None = None, hashed_password: str | None = None
) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
        "iat": datetime.now(timezone.utc),
        **(extra or {}),
    }
    if hashed_password is not None:
        payload["pwd"] = password_fingerprint(hashed_password)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Returns the payload, or None if the token is invalid or expired."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
