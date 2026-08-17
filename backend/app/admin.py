"""Admin dashboard at /admin — the Django-admin-shaped piece FastAPI omits.

sqladmin generates list/create/edit/delete over the SQLModel tables, gated by
AdminAuth below: the same User table as the API, admins only.

It talks to the database DIRECTLY, not through the API, so it bypasses
endpoint-level rules — an admin here can write state the endpoints would
reject. That is the point of a back-office tool, and the reason only admins
reach it.
"""

from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlmodel import Session, or_, select
from starlette.requests import Request
from starlette.responses import RedirectResponse
from wtforms import PasswordField

from app.db import engine
from app.models import (
    BusinessUnit,
    Decision,
    IndustrySignal,
    Opportunity,
    OpportunityScore,
    Permission,
    Organisation,
    Profile,
    Role,
    ScanRun,
    Source,
    User,
    WeeklyReport,
)
from app.rbac import CRITICAL, admins_remaining
from app.security import (
    SECRET_KEY,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class AdminAuth(AuthenticationBackend):
    """Gate /admin behind the same User table. Admins only."""

    async def login(self, request: Request) -> bool:
        form = await request.form()
        ident = str(form.get("username", "")).strip()
        password = str(form.get("password", ""))

        with Session(engine) as session:
            user = session.exec(
                select(User).where(
                    or_(User.username == ident, User.email == ident.lower())
                )
            ).first()
            if (
                not user
                or not user.is_active
                or not user.can("admin:access")
                or not verify_password(password, user.hashed_password)
            ):
                return False
            request.session["token"] = create_access_token(user.id, {"admin": True})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool | RedirectResponse:
        token = request.session.get("token")
        payload = decode_access_token(token) if token else None
        if not payload or not payload.get("admin"):
            return RedirectResponse(request.url_for("admin:login"), status_code=302)
        return True


class UserAdmin(ModelView, model=User):
    name_plural = "Users"
    icon = "fa-solid fa-user"
    column_list = [
        User.id,
        User.username,
        User.email,
        User.full_name,
        User.business_units,
        User.role,
        User.is_active,
        User.last_login_at,
    ]
    column_searchable_list = [User.username, User.email]
    # The hash must never be displayed or hand-edited — the Password field below
    # replaces it, and hashes on the way in. `business_unit` (the relationship,
    # not the raw FK) renders as a dropdown of unit names.
    form_columns = [
        User.username,
        User.email,
        User.full_name,
        User.business_units,
        User.role,
        User.is_active,
    ]

    async def scaffold_form(self, rules=None):
        form_class = await super().scaffold_form(rules)
        form_class.password = PasswordField(
            "Password",
            description="Set a new password. Leave blank when editing to keep the "
            "current one. Stored hashed — it can never be read back.",
        )
        return form_class

    async def on_model_change(self, data, model, is_created, request) -> None:
        password = (data.pop("password", "") or "").strip()
        if password:
            data["hashed_password"] = hash_password(password)
        elif is_created:
            raise ValueError("A password is required when creating a user.")

        if not is_created:
            _guard_last_admin_on_user_change(model, data)

    async def on_model_delete(self, model, request) -> None:
        with Session(engine) as session:
            if _is_critical_user(model) and admins_remaining(session, model.id) == 0:
                raise ValueError(
                    "This is the last administrator — deleting them would lock "
                    "everyone out. Give another user an admin role first."
                )


def _is_critical_user(user: User) -> bool:
    """Does this user currently hold every CRITICAL permission?"""
    if not user.is_active or not user.role:
        return False
    held = {p.codename for p in user.role.permissions}
    return all(c in held for c in CRITICAL)


def _guard_last_admin_on_user_change(model: User, data: dict) -> None:
    """Refuse a change that would remove the last account able to administer.

    Two ways to do it by accident: deactivate them, or move them to a role that
    cannot manage users and roles.
    """
    if not _is_critical_user(model):
        return  # they were never the thing keeping the lights on

    with Session(engine) as session:
        if admins_remaining(session, exclude_user_id=model.id) > 0:
            return  # somebody else can still administer — go ahead

        if "is_active" in data and not data["is_active"]:
            raise ValueError(
                "This is the last administrator — deactivating them would lock "
                "everyone out. Give another user an admin role first."
            )

        new_role = data.get("role")
        if "role" in data:
            role_id = getattr(new_role, "id", new_role)
            role = session.get(Role, role_id) if role_id else None
            held = {p.codename for p in role.permissions} if role else set()
            if not all(c in held for c in CRITICAL):
                raise ValueError(
                    "This is the last administrator — that role cannot manage "
                    "users and roles, so the change would lock everyone out."
                )


class RoleAdmin(ModelView, model=Role):
    name_plural = "Roles"
    icon = "fa-solid fa-shield-halved"
    column_list = [Role.id, Role.name, Role.label, Role.scope, Role.is_system]
    # `permissions` is the editable grid; `scope` decides which ROWS the role
    # sees and is not a permission (see app/rbac.py).
    form_columns = [Role.name, Role.label, Role.scope, Role.permissions]

    async def on_model_change(self, data, model, is_created, request) -> None:
        if is_created:
            return
        held = {
            p.codename if hasattr(p, "codename") else str(p)
            for p in (data.get("permissions") or [])
        }
        if all(c in held for c in CRITICAL):
            return  # still an administering role, nothing to protect against

        # This role is losing its admin powers — is anyone else left?
        with Session(engine) as session:
            others = 0
            for user in session.exec(select(User)).all():
                if not user.is_active or not user.role or user.role_id == model.id:
                    continue
                user_held = {p.codename for p in user.role.permissions}
                if all(c in user_held for c in CRITICAL):
                    others += 1

            role_has_users = any(
                u.is_active for u in session.exec(select(User)).all()
                if u.role_id == model.id
            )
            if role_has_users and others == 0:
                missing = sorted(c for c in CRITICAL if c not in held)
                raise ValueError(
                    "Refused: this is the only role that can administer the "
                    f"system, and removing {', '.join(missing)} would lock "
                    "everyone out. Grant another role admin rights first."
                )

    async def on_model_delete(self, model, request) -> None:
        if model.is_system:
            raise ValueError(
                f"'{model.name}' is a built-in role and cannot be deleted. "
                "Edit its permissions instead."
            )


class PermissionAdmin(ModelView, model=Permission):
    name_plural = "Permissions"
    icon = "fa-solid fa-key"
    column_list = [Permission.id, Permission.codename, Permission.resource, Permission.action]
    column_searchable_list = [Permission.codename]
    column_default_sort = (Permission.codename, False)
    # The catalogue is generated from app/rbac.py — editing it by hand would be
    # overwritten on the next boot, so it is read-only here.
    can_create = False
    can_edit = False
    can_delete = False


class BusinessUnitAdmin(ModelView, model=BusinessUnit):
    name_plural = "Business units"
    icon = "fa-solid fa-sitemap"
    column_list = [
        BusinessUnit.id,
        BusinessUnit.initials,
        BusinessUnit.name,
        BusinessUnit.description,
    ]


class OpportunityAdmin(ModelView, model=Opportunity):
    name_plural = "Opportunities"
    icon = "fa-solid fa-bullseye"
    column_list = [
        Opportunity.id,
        Opportunity.title,
        Opportunity.org,
        Opportunity.category,
        Opportunity.relevance,
        Opportunity.value,
        Opportunity.deadline,
    ]
    column_searchable_list = [Opportunity.title, Opportunity.org]
    column_sortable_list = [Opportunity.title, Opportunity.org]


class OrganisationAdmin(ModelView, model=Organisation):
    name_plural = "Organisations"
    icon = "fa-solid fa-building"
    column_list = [
        Organisation.id,
        Organisation.name,
        Organisation.sector,
        Organisation.priority,
        Organisation.last_updated,
    ]
    column_searchable_list = [Organisation.name]


class ProfileAdmin(ModelView, model=Profile):
    name_plural = "Profiles"
    icon = "fa-solid fa-id-card"
    column_list = [
        Profile.id,
        Profile.business_unit,
        Profile.min_fit_percent,
        Profile.positioning,
    ]
    can_create = False  # one per business unit, created with the unit
    can_delete = False
    column_labels = {Profile.min_fit_percent: "Min fit %"}


class OpportunityScoreAdmin(ModelView, model=OpportunityScore):
    name = "Opportunity score"
    name_plural = "Opportunity scores"
    icon = "fa-solid fa-percent"
    column_list = [
        OpportunityScore.id,
        OpportunityScore.opportunity,
        OpportunityScore.business_unit,
        OpportunityScore.fit_percent,
        OpportunityScore.win_probability,
        OpportunityScore.is_joint_pitch_candidate,
        OpportunityScore.scored_at,
    ]
    column_sortable_list = [OpportunityScore.fit_percent]
    column_default_sort = (OpportunityScore.fit_percent, True)


class SourceAdmin(ModelView, model=Source):
    name_plural = "Sources"
    icon = "fa-solid fa-rss"
    column_list = [
        Source.id,
        Source.name,
        Source.type,
        Source.category,
        Source.scope,
        Source.active,
        Source.last_status,
        Source.last_checked_at,
    ]
    column_searchable_list = [Source.name, Source.url]
    column_sortable_list = [Source.name, Source.active]


class DecisionAdmin(ModelView, model=Decision):
    name_plural = "Decisions"
    icon = "fa-solid fa-gavel"
    column_list = [
        Decision.id,
        Decision.opportunity_id,
        Decision.decision,
        Decision.reason,
        Decision.created_at,
    ]
    column_default_sort = (Decision.created_at, True)


class IndustrySignalAdmin(ModelView, model=IndustrySignal):
    name_plural = "Industry signals"
    icon = "fa-solid fa-chart-line"
    column_list = [
        IndustrySignal.id,
        IndustrySignal.sector,
        IndustrySignal.direction,
        IndustrySignal.text,
        IndustrySignal.created_at,
    ]


class WeeklyReportAdmin(ModelView, model=WeeklyReport):
    name_plural = "Weekly reports"
    icon = "fa-solid fa-newspaper"
    column_list = [
        WeeklyReport.id,
        WeeklyReport.week_of,
        WeeklyReport.opp_count,
        WeeklyReport.source_count,
        WeeklyReport.generated_at,
    ]


class ScanRunAdmin(ModelView, model=ScanRun):
    name_plural = "Scan runs"
    icon = "fa-solid fa-magnifying-glass"
    column_list = [
        ScanRun.id,
        ScanRun.status,
        ScanRun.started_at,
        ScanRun.finished_at,
        ScanRun.sources_swept,
        ScanRun.scored,
    ]
    column_default_sort = (ScanRun.started_at, True)
    can_create = False  # jobs are started via POST /api/scan
    can_edit = False


def mount_admin(app: FastAPI) -> Admin:
    admin = Admin(
        app,
        engine,
        title="TM Global BI",
        authentication_backend=AdminAuth(secret_key=SECRET_KEY),
    )
    for view in (
        UserAdmin,
        RoleAdmin,
        PermissionAdmin,
        BusinessUnitAdmin,
        OpportunityAdmin,
        OpportunityScoreAdmin,
        OrganisationAdmin,
        ProfileAdmin,
        SourceAdmin,
        DecisionAdmin,
        IndustrySignalAdmin,
        WeeklyReportAdmin,
        ScanRunAdmin,
    ):
        admin.add_view(view)
    return admin
