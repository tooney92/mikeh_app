"""RBAC: the declarative matrix, and the seeder that syncs it into the database.

Two SEPARATE axes, deliberately:

  grants  — what you may DO, as `resource:action` (Django's convention).
  scope   — which ROWS you see: "all", or "own_units" meaning the units the
            user belongs to (usually one, but the client has a person leading
            two, so it is a set).

Keeping them apart is the whole design. A director and a lead can hold the very
same `opportunity:read` and still see different rows, because scope filters the
query while the grant authorises the verb. Folding visibility into permissions
(`read_own` vs `read_all`) is what makes these systems combinatorial.
"""

from sqlmodel import Session, select

from app.models import Permission, Role

# Every resource the API exposes. Adding one here adds its four CRUD
# permissions on the next boot — no hand-maintained list.
RESOURCES = [
    "opportunity",
    "source",
    "profile",
    "decision",
    "organisation",
    "industry_signal",
    "report",
    "user",
    "role",
]

ACTIONS = ["create", "read", "update", "delete"]

# Verbs that are not CRUD on a row.
EXTRA = [
    "scan:run",
    "report:send",
    "opportunity:export",
    "admin:access",  # may open the /admin back-office at all
]

# Holding ALL of these is what makes an account able to repair the system.
# The guard below refuses any change that would leave nobody with them.
CRITICAL = ("admin:access", "role:update", "user:update")

SCOPE_ALL = "all"
SCOPE_OWN_UNITS = "own_units"

ROLES: dict[str, dict] = {
    "admin": {
        "label": "Administrator",
        "scope": SCOPE_ALL,
        "grants": ["*"],
    },
    "director": {
        "label": "Director",
        "scope": SCOPE_ALL,
        "grants": [
            "opportunity:*",
            "source:*",
            "profile:*",
            "decision:*",
            "organisation:*",
            "industry_signal:*",
            "report:read",
            "report:send",
            "scan:run",
            "opportunity:export",
            "user:read",
        ],
    },
    "lead": {
        "label": "SBU Lead",
        "scope": SCOPE_OWN_UNITS,
        "grants": [
            "opportunity:read",
            "opportunity:export",
            "decision:*",
            "profile:read",
            "profile:update",
            "source:read",
            "organisation:read",
            "industry_signal:read",
            "report:read",
            "scan:run",
        ],
    },
    "member": {
        "label": "Team Member",
        "scope": SCOPE_OWN_UNITS,
        "grants": [
            "opportunity:read",
            "decision:create",
            "decision:read",
            "profile:read",
            "organisation:read",
            "industry_signal:read",
            "report:read",
            "scan:run",
        ],
    },
}


def all_codenames() -> list[str]:
    return [f"{r}:{a}" for r in RESOURCES for a in ACTIONS] + list(EXTRA)


def expand(grants: list[str]) -> set[str]:
    """`*` = everything, `resource:*` = every action on it, else literal."""
    every = all_codenames()
    out: set[str] = set()
    for g in grants:
        if g == "*":
            return set(every)
        if g.endswith(":*"):
            prefix = g[:-1]  # keep the colon
            out.update(c for c in every if c.startswith(prefix))
        else:
            out.add(g)
    return out & set(every)


def sync_rbac(session: Session) -> dict[str, int]:
    """Idempotent, runs on every boot.

    The permission CATALOGUE is authoritative — new resources appear
    automatically. Role→permission ASSIGNMENTS are written only when a role is
    first created, so edits made in /admin survive the next restart instead of
    being silently reverted.
    """
    existing = {p.codename: p for p in session.exec(select(Permission)).all()}
    added_perms = 0
    for codename in all_codenames():
        if codename in existing:
            continue
        resource, action = codename.split(":", 1)
        perm = Permission(resource=resource, action=action, codename=codename)
        session.add(perm)
        existing[codename] = perm
        added_perms += 1
    session.flush()  # need ids before linking

    added_roles = 0
    for name, spec in ROLES.items():
        role = session.exec(select(Role).where(Role.name == name)).first()
        if role:
            continue  # never overwrite an edited role
        role = Role(name=name, label=spec["label"], scope=spec["scope"], is_system=True)
        role.permissions = [existing[c] for c in sorted(expand(spec["grants"]))]
        session.add(role)
        added_roles += 1

    return {"permissions": added_perms, "roles": added_roles}


def admins_remaining(session: Session, exclude_user_id: int | None = None) -> int:
    """Active users whose role grants every CRITICAL permission."""
    from app.models import User

    count = 0
    for user in session.exec(select(User)).all():
        if not user.is_active or user.id == exclude_user_id or not user.role:
            continue
        held = {p.codename for p in user.role.permissions}
        if all(c in held for c in CRITICAL):
            count += 1
    return count
