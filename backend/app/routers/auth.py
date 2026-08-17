from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, or_, select

from app.db import get_session
from app.deps import current_user, requires
from app.models import Permission, Role, User
from app.schemas import (
    ChangePasswordRequest,
    RoleOut,
    UnitBrief,
    LoginRequest,
    ResetPasswordRequest,
    TokenOut,
    UserOut,
)
from app.security import TOKEN_TTL_HOURS, create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api", tags=["auth"])

MIN_PASSWORD_LENGTH = 8


def _to_out(user: User, session: Session) -> UserOut:
    # Columns only — validating the ORM object would drag in the `role`
    # relationship, whose Permission rows are objects where RoleOut wants
    # codename strings.
    out = UserOut.model_validate(user.model_dump())
    out.business_units = [
        UnitBrief(id=u.id, name=u.name, initials=u.initials) for u in user.business_units
    ]
    if user.role:
        codenames = sorted(p.codename for p in user.role.permissions)
        out.role = RoleOut(
            id=user.role.id,
            name=user.role.name,
            label=user.role.label,
            scope=user.role.scope,
            is_system=user.role.is_system,
            permissions=codenames,
        )
        out.permissions = codenames
    return out


def _check_password_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"password must be at least {MIN_PASSWORD_LENGTH} characters",
        )


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    """Accepts either the username or the email in `identifier`."""
    ident = payload.identifier.strip()
    user = session.exec(
        select(User).where(or_(User.username == ident, User.email == ident.lower()))
    ).first()

    # Same message either way — never reveal whether the account exists.
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "incorrect login or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account is deactivated")

    user.last_login_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()

    return TokenOut(
        access_token=create_access_token(
            user.id, {"admin": user.can("admin:access")}
        ),
        expires_in=TOKEN_TTL_HOURS * 3600,
    )


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return _to_out(user, session)


@router.post("/auth/change-password", status_code=204)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Change your own password — requires the current one."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "current password is incorrect")
    _check_password_strength(payload.new_password)

    user.hashed_password = hash_password(payload.new_password)
    session.add(user)
    session.commit()


@router.get("/users", response_model=list[UserOut])
def list_users(
    _: User = Depends(requires("user:read")), session: Session = Depends(get_session)
):
    users = session.exec(select(User).order_by(User.username)).all()
    return [_to_out(u, session) for u in users]


@router.post("/users/{user_id}/reset-password", status_code=204)
def reset_password(
    user_id: int,
    payload: ResetPasswordRequest,
    _: User = Depends(requires("user:update")),
    session: Session = Depends(get_session),
):
    """Admin sets a new password for someone. The old one is never readable."""
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    _check_password_strength(payload.new_password)

    target.hashed_password = hash_password(payload.new_password)
    session.add(target)
    session.commit()


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    _: User = Depends(requires("role:read")), session: Session = Depends(get_session)
):
    """The role catalogue, each with its granted permissions."""
    roles = session.exec(select(Role).order_by(Role.id)).all()
    return [
        RoleOut(
            id=r.id,
            name=r.name,
            label=r.label,
            scope=r.scope,
            is_system=r.is_system,
            permissions=sorted(p.codename for p in r.permissions),
        )
        for r in roles
    ]


@router.get("/permissions", response_model=list[str])
def list_permissions(
    _: User = Depends(requires("role:read")), session: Session = Depends(get_session)
):
    """Every codename that exists — the columns of the admin's permission grid."""
    return sorted(p.codename for p in session.exec(select(Permission)).all())
