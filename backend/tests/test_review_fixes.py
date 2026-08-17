"""Regressions from the second code review.

Every test here corresponds to one finding that was confirmed live before being
fixed. Several of them cover paths the existing suite could not reach — most
importantly the back office, whose guards were being tested with ORM objects
while the HTML form submits primary-key strings, so a broken guard passed.
"""

import asyncio
import importlib
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ADMIN_PW = "review-admin-pw-1"
STAFF_PW = "review-staff-pw-1"


@pytest.fixture(scope="module")
def client():
    os.environ["TM_ADMIN_USERNAME"] = "admin"
    os.environ["TM_ADMIN_EMAIL"] = "admin@tmglobal.local"
    os.environ["TM_ADMIN_PASSWORD"] = ADMIN_PW

    tmp = Path(tempfile.mkdtemp())
    from app import db

    db.DB_PATH = tmp / "review.db"
    db.engine = db.create_engine(
        f"sqlite:///{db.DB_PATH}", connect_args={"check_same_thread": False}
    )
    for mod in ("app.rbac", "app.seed", "app.routers.scan", "app.admin", "app.main"):
        importlib.reload(importlib.import_module(mod))

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module", autouse=True)
def people(client):
    """Two leads in DIFFERENT units, so cross-unit leakage is observable."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import BusinessUnit, Role, User
    from app.security import hash_password

    with Session(engine) as s:
        roles = {r.name: r.id for r in s.exec(select(Role)).all()}
        units = {u.name: u for u in s.exec(select(BusinessUnit)).all()}
        for name, role, unit in [
            ("tf.lead", "lead", "TM Foundation"),
            ("tm.lead", "lead", "Takeout Media"),
            ("pw.user", "member", "TM Foundation"),
        ]:
            u = User(
                username=name,
                email=f"{name}@tmglobal.local",
                hashed_password=hash_password(STAFF_PW),
                role_id=roles[role],
            )
            u.business_units = [units[unit]]
            s.add(u)
        s.commit()


def tok(client, who, pw=None):
    r = client.post(
        "/api/auth/login",
        json={"identifier": who, "password": pw or (ADMIN_PW if who == "admin" else STAFF_PW)},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


class _FakeRequest:
    """Only `.session` is touched by admin._held_codenames."""

    def __init__(self, token=None):
        self.session = {"token": token} if token else {}


def _admin_session_token(client, who, pw=None):
    r = client.post(
        "/api/auth/login",
        json={"identifier": who, "password": pw or (ADMIN_PW if who == "admin" else STAFF_PW)},
    )
    return r.json()["accessToken"]


# --- finding 1: the last-admin guard could never let the admin role be edited ---


def test_role_guard_reads_codenames_from_primary_key_strings(client):
    """sqladmin's QuerySelectMultipleField.data yields PK STRINGS, not objects.

    The guard built `held` with `str(p)`, so it saw {"1","2",...}, never found
    admin:access, and raised on EVERY edit of the admin role — including a
    label-only change with all 40 permissions still ticked. The old tests passed
    ORM objects, exercising a path the form never takes, so they went green
    against a guard that was refusing everything.
    """
    from sqlmodel import Session, select

    from app.admin import RoleAdmin
    from app.db import engine
    from app.models import Permission, Role

    with Session(engine) as s:
        admin_role = s.exec(select(Role).where(Role.name == "admin")).one()
        all_ids = [str(p.id) for p in s.exec(select(Permission)).all()]
        role_id = admin_role.id

    class _Model:
        id = role_id

    # Keeping every permission, as the form submits it: primary-key strings.
    asyncio.run(
        RoleAdmin().on_model_change(
            {"permissions": all_ids, "label": "Administrator (renamed)"},
            _Model(),
            False,
            _FakeRequest(),
        )
    )


def test_role_guard_still_refuses_an_actual_lockout(client):
    """The fix must not disarm the guard — stripping the critical codenames
    from the only administering role is still refused."""
    from sqlmodel import Session, select

    from app.admin import RoleAdmin
    from app.db import engine
    from app.models import Permission, Role

    with Session(engine) as s:
        admin_role = s.exec(select(Role).where(Role.name == "admin")).one()
        role_id = admin_role.id
        harmless = [
            str(p.id)
            for p in s.exec(select(Permission)).all()
            if p.codename not in ("admin:access", "role:update", "user:update")
        ]

    class _Model:
        id = role_id

    with pytest.raises(ValueError, match="lock everyone out"):
        asyncio.run(
            RoleAdmin().on_model_change(
                {"permissions": harmless}, _Model(), False, _FakeRequest()
            )
        )


def test_codenames_from_form_accepts_both_shapes(client):
    """Objects (programmatic callers) and PK strings (the form) both resolve."""
    from sqlmodel import Session, select

    from app.admin import _codenames_from_form
    from app.db import engine
    from app.models import Permission

    with Session(engine) as s:
        perms = s.exec(select(Permission)).all()[:3]
        ids = [str(p.id) for p in perms]
        names = {p.codename for p in perms}

    assert _codenames_from_form(ids) == names
    assert _codenames_from_form(["nonsense", None]) == set()


# --- finding 4: admin:access alone granted full User and Role CRUD ---


def test_back_office_user_and_role_sections_need_more_than_admin_access(client):
    """rbac.CRITICAL treats admin:access, role:update and user:update as three
    SEPARABLE permissions, but the whole back office was gated on the first
    alone. Granting a lead admin:access therefore handed them CRUD on User and
    Role — including setting the admin's password — where the API path for the
    same act 403s on requires("user:update"). Two enforcement paths disagreeing
    about who may administer.
    """
    from sqlmodel import Session, select

    from app.admin import PermissionAdmin, RoleAdmin, UserAdmin
    from app.db import engine
    from app.models import Permission, Role, User

    admin_req = _FakeRequest(_admin_session_token(client, "admin"))
    assert UserAdmin().is_accessible(admin_req)
    assert RoleAdmin().is_accessible(admin_req)
    assert PermissionAdmin().is_accessible(admin_req)

    # Give the lead role admin:access and nothing else new.
    with Session(engine) as s:
        lead = s.exec(select(Role).where(Role.name == "lead")).one()
        access = s.exec(
            select(Permission).where(Permission.codename == "admin:access")
        ).one()
        lead.permissions.append(access)
        s.add(lead)
        s.commit()
        held = {p.codename for p in lead.permissions}

    assert "admin:access" in held, "the lead can now reach /admin at all"
    assert "user:update" not in held and "role:update" not in held

    lead_req = _FakeRequest(_admin_session_token(client, "tf.lead"))
    assert not UserAdmin().is_accessible(lead_req), (
        "admin:access alone must not grant CRUD over accounts"
    )
    assert not RoleAdmin().is_accessible(lead_req)
    # Hidden from the menu too, not merely blocked on submit.
    assert not UserAdmin().is_visible(lead_req)

    with Session(engine) as s:
        lead = s.exec(select(Role).where(Role.name == "lead")).one()
        lead.permissions = [p for p in lead.permissions if p.codename != "admin:access"]
        s.add(lead)
        s.commit()

    assert not UserAdmin().is_accessible(_FakeRequest()), "no session, no access"
    assert User is not None  # import kept meaningful for readers


# --- finding 2: opportunity detail leaked another unit's rejection reason ---


def test_detail_does_not_leak_another_units_decision(client):
    """/api/decisions was scoped in the same commit that left this open.

    A Reject REQUIRES a reason and those are commercially candid by design, so
    this handed a TM Foundation lead Takeout Media's justification for walking
    away. It was also wrong on its face: the page told TF the opportunity was
    rejected when TF never decided.
    """
    tm = tok(client, "tm.lead")
    tf = tok(client, "tf.lead")

    made = client.post(
        "/api/decisions",
        json={
            "opportunityId": "gam-au",
            "decision": "Reject",
            "reason": "margin too thin for Takeout Media",
        },
        headers=tm,
    )
    assert made.status_code == 201, made.text

    # The deciding unit sees its own call.
    mine = client.get("/api/opportunities/gam-au", headers=tm).json()
    assert mine["decision"] == "Reject"
    assert "margin too thin" in mine["decisionReason"]

    # The other unit sees neither the decision nor the reason.
    theirs = client.get("/api/opportunities/gam-au", headers=tf).json()
    assert theirs["decision"] is None, theirs["decision"]
    assert not theirs["decisionReason"]

    # And the list endpoint still agrees with the detail endpoint.
    assert client.get("/api/decisions", headers=tf).json() == []


def test_an_unattributed_decision_is_visible_to_whoever_owns_the_opportunity(client):
    """finding 6. `business_unit_id in unit_ids` is False for NULL, so a
    director's company-level call vanished from every scoped log — while
    log_decision deliberately ALLOWS an unscoped user to omit the unit. The write
    path and the read path disagreed about what unattributed means. Rows
    predating the column are NULL too, so a real database made each lead's
    Learning page read zero.
    """
    admin = tok(client, "admin")
    tf = tok(client, "tf.lead")

    before = len(client.get("/api/decisions", headers=tf).json())
    made = client.post(
        "/api/decisions",
        json={"opportunityId": "gam-au", "decision": "Pursue"},
        headers=admin,
    )
    assert made.status_code == 201, made.text
    assert made.json()["businessUnitId"] is None, "admin may decide unattributed"

    after = client.get("/api/decisions", headers=tf).json()
    assert len(after) == before + 1, "TF is scored on gam-au, so it is their business"
    assert client.get("/api/learning", headers=tf).json()["decisionsLogged"] == len(after)


def test_decisions_record_who_made_them(client):
    """finding 8. Decision.user_id existed on the model and nothing wrote it, so
    the table whose purpose is recording who decided what could not answer it."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import Decision, User

    made = client.post(
        "/api/decisions",
        json={"opportunityId": "encyclopaedia", "decision": "Watch"},
        headers=tok(client, "tf.lead"),
    )
    assert made.status_code == 201, made.text

    with Session(engine) as s:
        d = s.get(Decision, made.json()["id"])
        assert d.user_id is not None, "attribution must not be NULL"
        assert s.get(User, d.user_id).username == "tf.lead"


# --- finding 5: priority-actions ignored the per-unit fit bar ---


def test_priority_actions_respect_the_units_fit_bar(client):
    """The tiles and the list both apply min_fit_percent; this did not. So the
    Radar could ANNOUNCE an opportunity at "45% fit" while the tiles above it
    and the list below it excluded it — the dashboard contradicting the list on
    one screen refresh.
    """
    admin = tok(client, "admin")
    tf = tok(client, "tf.lead")

    profiles = client.get("/api/profiles", headers=admin).json()
    tf_profile = next(p for p in profiles if p["businessUnitName"] == "TM Foundation")

    baseline = client.get("/api/priority-actions", headers=tf).json()
    assert baseline, "TM Foundation should have actions at the default bar"

    try:
        client.put(
            f"/api/profiles/{tf_profile['id']}",
            json={"minFitPercent": 100},
            headers=admin,
        )
        raised = client.get("/api/priority-actions", headers=tf).json()
        opportunity_rows = [a for a in raised if a["type"] in ("Opportunity", "Partnership")]
        assert opportunity_rows == [], (
            "nothing clears a 100% bar, so nothing may be announced as a "
            f"priority action: {opportunity_rows}"
        )
        assert client.get("/api/opportunities", headers=tf).json() == [], (
            "and the list must agree — that consistency is the whole point"
        )
    finally:
        client.put(
            f"/api/profiles/{tf_profile['id']}",
            json={"minFitPercent": tf_profile["minFitPercent"]},
            headers=admin,
        )

    assert client.get("/api/priority-actions", headers=tf).json() == baseline


# --- finding 7: a password change left outstanding tokens working ---


def test_changing_a_password_invalidates_existing_tokens(client):
    """The TTL is 12 hours and nothing consulted the hash after login, so
    resetting a compromised account's password — the remedy the admin dashboard
    exists to provide — left the attacker's bearer token live for up to half a
    day. Deactivating the user DID work immediately, which made the asymmetry
    easy to miss: the weaker-looking remedy was the effective one.
    """
    stolen = tok(client, "pw.user")
    assert client.get("/api/auth/me", headers=stolen).status_code == 200

    new_pw = "review-staff-pw-2"
    changed = client.post(
        "/api/auth/change-password",
        json={"currentPassword": STAFF_PW, "newPassword": new_pw},
        headers=stolen,
    )
    assert changed.status_code == 204, changed.text

    assert client.get("/api/auth/me", headers=stolen).status_code == 401, (
        "the token issued against the OLD password must stop working at once"
    )
    assert client.get("/api/auth/me", headers=tok(client, "pw.user", new_pw)).status_code == 200


def test_an_admin_reset_invalidates_the_targets_tokens(client):
    """Same guarantee via the admin path, which is the one that matters — it is
    what somebody reaches for when an account is compromised."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import Role, User
    from app.security import hash_password

    with Session(engine) as s:
        role = s.exec(select(Role).where(Role.name == "member")).one()
        s.add(
            User(
                username="reset.target",
                email="reset.target@tmglobal.local",
                hashed_password=hash_password(STAFF_PW),
                role_id=role.id,
            )
        )
        s.commit()
        target_id = s.exec(
            select(User).where(User.username == "reset.target")
        ).one().id

    stolen = tok(client, "reset.target")
    assert client.get("/api/auth/me", headers=stolen).status_code == 200

    reset = client.post(
        f"/api/users/{target_id}/reset-password",
        json={"newPassword": "review-staff-pw-3"},
        headers=tok(client, "admin"),
    )
    assert reset.status_code == 204, reset.text
    assert client.get("/api/auth/me", headers=stolen).status_code == 401


def test_a_token_without_the_pwd_claim_is_refused(client):
    """Tokens minted before this existed carry no `pwd` claim. They are refused
    rather than grandfathered — honouring the old shape would leave in force
    exactly the outstanding tokens this protects against."""
    from app.security import create_access_token

    legacy = create_access_token(1, {"admin": True})  # no hashed_password passed
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {legacy}"})
    assert r.status_code == 401, r.text


def test_the_fingerprint_does_not_expose_the_hash(client):
    """It is an HMAC keyed on the signing secret, so a captured token reveals
    nothing about the stored hash."""
    from app.security import hash_password, password_fingerprint

    hashed = hash_password("some-password")
    fp = password_fingerprint(hashed)
    assert len(fp) == 16
    assert fp not in hashed and hashed[:16] not in fp
    assert password_fingerprint(hashed) == fp, "stable for the same hash"
    assert password_fingerprint(hash_password("some-password")) != fp, (
        "Argon2 salts, so a re-hash of the same password is a different version"
    )


# --- finding 10 (the backend half): a failed scan must not wedge "running" ---


def test_a_failing_scan_run_records_failed_not_running(client, monkeypatch):
    """The frontend disables Run for ANY status that is not idle/complete, and
    polls only from inside the handler that button fires. So a run left
    "running" disables scanning for everybody, permanently, with nothing able to
    poll it back. Today the body cannot realistically fail; once it is a real
    crawler over eighty websites, failing is routine.
    """
    from sqlmodel import Session

    from app.db import engine
    from app.models import ScanRun
    from app.routers import scan

    with Session(engine) as s:
        run = ScanRun(status="running")
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id

    def _boom(*_a, **_k):
        raise RuntimeError("source unreachable")

    # Fail INSIDE the try block, leaving Session itself intact so the recovery
    # path can still reach the database to record the terminal state.
    monkeypatch.setattr(scan, "select", _boom)
    scan._run_scan(run_id)
    monkeypatch.undo()

    with Session(engine) as s:
        assert s.get(ScanRun, run_id).status == "failed"
        assert s.get(ScanRun, run_id).finished_at is not None


def test_a_successful_scan_still_completes(client):
    started = client.post("/api/scan", headers=tok(client, "admin"))
    assert started.status_code == 202, started.text
    status = client.get("/api/scan/status", headers=tok(client, "admin")).json()
    assert status["status"] == "complete", status
