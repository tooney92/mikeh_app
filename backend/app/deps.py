"""Auth dependencies — who is calling, and may they."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.db import get_session
from app.models import User
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)
) -> User:
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise CREDENTIALS_ERROR

    user = session.get(User, int(payload["sub"]))
    if not user:
        raise CREDENTIALS_ERROR
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account is deactivated")
    return user


def requires(codename: str) -> Callable[[User], User]:
    """Dependency factory: `Depends(requires("user:update"))`.

    Enforced SERVER-side on purpose. The permissions list handed to the frontend
    decides what to DRAW; it is not a security boundary, because anyone can call
    the endpoint directly.
    """

    def _check(user: User = Depends(current_user)) -> User:
        if not user.can(codename):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"requires permission '{codename}'"
            )
        return user

    return _check
