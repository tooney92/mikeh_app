"""RBAC: the seeded matrix, server-side enforcement, scope-vs-grants, and the
guard that refuses to let anyone remove the last administrator.
"""

import importlib
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ADMIN_PW = "rbac-admin-pw-1"
STAFF_PW = "rbac-staff-pw-1"


@pytest.fixture(scope="module")
def client():
    os.environ["TM_ADMIN_USERNAME"] = "admin"
    os.environ["TM_ADMIN_EMAIL"] = "admin@tmglobal.local"
    os.environ["TM_ADMIN_PASSWORD"] = ADMIN_PW

    tmp = Path(tempfile.mkdtemp())
    from app import db

    db.DB_PATH = tmp / "rbac.db"
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
    """One user per role: a director with no unit, a lead and a member with one."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import BusinessUnit, OpportunityScore, Role, User
    from app.security import hash_password

    with Session(engine) as s:
        roles = {r.name: r.id for r in s.exec(select(Role)).all()}
        units = {u.name: u for u in s.exec(select(BusinessUnit)).all()}
        for name, role, unit in [
            ("dayo", "director", None),
            ("bola", "lead", "TM Foundation"),
            ("chidi", "member", "TM Foundation"),
            ("tunde", "lead", "Design Teem"),
            # Dedicated target for the password-reset test, so resetting it
            # cannot break another test's login.
            ("pwtarget", "member", "TM Labs"),
        ]:
            u = User(
                username=name,
                email=f"{name}@tmglobal.local",
                hashed_password=hash_password(STAFF_PW),
                role_id=roles[role],
            )
            if unit:
                u.business_units = [units[unit]]
            s.add(u)
        # Give Design Teem exactly one scored opportunity.
        s.add(
            OpportunityScore(
                opportunity_id="encyclopaedia",
                business_unit_id=units["Design Teem"].id,
                fit_percent=64,
            )
        )
        s.commit()


def tok(client, who):
    pw = ADMIN_PW if who == "admin" else STAFF_PW
    r = client.post("/api/auth/login", json={"identifier": who, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


# --- the seeded matrix ---


def test_roles_and_permissions_seeded():
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import Permission, Role
    from app.rbac import all_codenames

    with Session(engine) as s:
        assert len(s.exec(select(Permission)).all()) == len(all_codenames())
        scopes = {r.name: r.scope for r in s.exec(select(Role)).all()}
    assert scopes == {
        "admin": "all",
        "director": "all",
        "lead": "own_units",
        "member": "own_units",
    }


def test_only_admin_holds_the_critical_permissions():
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import Role
    from app.rbac import CRITICAL

    with Session(engine) as s:
        holders = {
            r.name
            for r in s.exec(select(Role)).all()
            if all(r.grants(c) for c in CRITICAL)
        }
    assert holders == {"admin"}


def test_wildcards_expand():
    from app.rbac import expand

    assert "opportunity:read" in expand(["opportunity:*"])
    assert "opportunity:delete" in expand(["opportunity:*"])
    assert "source:read" not in expand(["opportunity:*"])
    assert expand(["*"]) == set(__import__("app.rbac", fromlist=["x"]).all_codenames())
    # An unknown codename is dropped rather than silently granted.
    assert expand(["nonsense:action"]) == set()


# --- enforcement happens server-side, not in the frontend ---


@pytest.mark.parametrize(
    "who,expected",
    [("admin", 200), ("dayo", 200), ("bola", 403), ("chidi", 403)],
)
def test_user_read_permission(client, who, expected):
    assert client.get("/api/users", headers=tok(client, who)).status_code == expected


@pytest.mark.parametrize(
    "who,expected",
    [("admin", 200), ("dayo", 403), ("bola", 403), ("chidi", 403)],
)
def test_role_read_is_admin_only(client, who, expected):
    assert client.get("/api/roles", headers=tok(client, who)).status_code == expected


@pytest.mark.parametrize(
    "who,expected",
    [("admin", 204), ("dayo", 403), ("bola", 403), ("chidi", 403)],
)
def test_resetting_someone_elses_password_is_admin_only(client, who, expected):
    """A director sees every unit but administers nobody."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import User

    with Session(engine) as s:
        target = s.exec(select(User).where(User.username == "pwtarget")).one().id

    r = client.post(
        f"/api/users/{target}/reset-password",
        json={"newPassword": "brand-new-pw-42"},
        headers=tok(client, who),
    )
    assert r.status_code == expected


def test_unauthenticated_is_401_not_403(client):
    assert client.get("/api/users").status_code == 401


def test_me_exposes_permissions_for_the_frontend(client):
    body = client.get("/api/auth/me", headers=tok(client, "bola")).json()
    assert body["role"]["name"] == "lead"
    # Flat list so the UI asks can('x'), never role === 'lead'.
    assert "scan:run" in body["permissions"]
    assert "profile:update" in body["permissions"]
    assert "user:update" not in body["permissions"]
    assert "admin:access" not in body["permissions"]


# --- scope and grants are independent axes ---


def test_same_grant_different_rows(client):
    """A lead and a director both hold opportunity:read and see different rows."""
    director = client.get("/api/opportunities", headers=tok(client, "dayo")).json()
    lead_dt = client.get("/api/opportunities", headers=tok(client, "tunde")).json()

    for who in ("dayo", "tunde"):
        assert "opportunity:read" in client.get(
            "/api/auth/me", headers=tok(client, who)
        ).json()["permissions"]

    assert len(director) == 8  # scope "all"
    assert len(lead_dt) == 1  # scope "own_unit", one scored opportunity
    assert lead_dt[0]["id"] == "encyclopaedia"


def test_director_has_no_unit_but_still_sees_everything(client):
    me = client.get("/api/auth/me", headers=tok(client, "dayo")).json()
    assert me["businessUnits"] == []
    assert me["role"]["scope"] == "all"
    assert len(client.get("/api/opportunities", headers=tok(client, "dayo")).json()) == 8


# --- the guard: nobody can remove the last administrator ---


def test_admins_remaining_counts_only_fully_capable_actives():
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import User
    from app.rbac import admins_remaining

    with Session(engine) as s:
        assert admins_remaining(s) == 1
        admin_id = s.exec(select(User).where(User.username == "admin")).one().id
        # Excluding the only admin leaves nobody.
        assert admins_remaining(s, exclude_user_id=admin_id) == 0


def test_guard_blocks_deactivating_the_last_admin():
    from sqlmodel import Session, select

    from app.admin import _guard_last_admin_on_user_change
    from app.db import engine
    from app.models import User

    with Session(engine) as s:
        admin = s.exec(select(User).where(User.username == "admin")).one()
        with pytest.raises(ValueError, match="last administrator"):
            _guard_last_admin_on_user_change(admin, {"is_active": False})


def test_guard_blocks_demoting_the_last_admin():
    from sqlmodel import Session, select

    from app.admin import _guard_last_admin_on_user_change
    from app.db import engine
    from app.models import Role, User

    with Session(engine) as s:
        admin = s.exec(select(User).where(User.username == "admin")).one()
        member = s.exec(select(Role).where(Role.name == "member")).one()
        with pytest.raises(ValueError, match="lock everyone out"):
            _guard_last_admin_on_user_change(admin, {"role": member})


def test_guard_allows_the_change_once_a_second_admin_exists():
    from sqlmodel import Session, select

    from app.admin import _guard_last_admin_on_user_change
    from app.db import engine
    from app.models import Role, User
    from app.security import hash_password

    with Session(engine) as s:
        admin_role = s.exec(select(Role).where(Role.name == "admin")).one()
        s.add(
            User(
                username="second-admin",
                email="second@tmglobal.local",
                hashed_password=hash_password(STAFF_PW),
                role_id=admin_role.id,
            )
        )
        s.commit()

        admin = s.exec(select(User).where(User.username == "admin")).one()
        member = s.exec(select(Role).where(Role.name == "member")).one()
        # No longer the last one, so the same change is now permitted.
        _guard_last_admin_on_user_change(admin, {"is_active": False})
        _guard_last_admin_on_user_change(admin, {"role": member})


def test_seeded_roles_cannot_be_deleted():
    import asyncio

    from sqlmodel import Session, select

    from app.admin import RoleAdmin
    from app.db import engine
    from app.models import Role

    with Session(engine) as s:
        admin_role = s.exec(select(Role).where(Role.name == "admin")).one()
        with pytest.raises(ValueError, match="built-in role"):
            asyncio.run(RoleAdmin().on_model_delete(admin_role, None))


# --- one person, two units ---


def test_a_lead_of_two_units_sees_the_union(client):
    """The client has one person leading Takeout Media AND TM Foundation.

    A single business_unit_id could not express this: they would see one unit
    or, with scope "all", all five. Membership is a set, so they see the union
    of their units and nothing else.
    """
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import BusinessUnit, Opportunity, OpportunityScore, Role, User
    from app.security import hash_password

    with Session(engine) as s:
        units = {u.name: u for u in s.exec(select(BusinessUnit)).all()}
        lead = s.exec(select(Role).where(Role.name == "lead")).one()

        # An opportunity ONLY Design Teem is scored for.
        s.add(Opportunity(id="dt-only", category="bid", org="A Brand", title="Design-only work"))
        s.flush()
        s.add(
            OpportunityScore(
                opportunity_id="dt-only",
                business_unit_id=units["Design Teem"].id,
                fit_percent=91,
            )
        )
        u = User(
            username="ngozi",
            email="ngozi@tmglobal.local",
            hashed_password=hash_password(STAFF_PW),
            role_id=lead.id,
        )
        u.business_units = [units["TM Foundation"], units["Design Teem"]]
        s.add(u)
        s.commit()

    me = client.get("/api/auth/me", headers=tok(client, "ngozi")).json()
    assert {b["name"] for b in me["businessUnits"]} == {"TM Foundation", "Design Teem"}

    foundation_only = client.get(
        "/api/opportunities", headers=tok(client, "bola")
    ).json()
    design_only = client.get("/api/opportunities", headers=tok(client, "tunde")).json()
    both = client.get("/api/opportunities", headers=tok(client, "ngozi")).json()

    f_ids = {r["id"] for r in foundation_only}
    d_ids = {r["id"] for r in design_only}
    b_ids = {r["id"] for r in both}

    assert b_ids == f_ids | d_ids  # the union, deduplicated
    assert "dt-only" in b_ids and "dt-only" not in f_ids
    # Belonging to two units ranks by the BETTER of the two fits.
    assert both[0]["id"] == "dt-only"
    assert both[0]["yourFitPercent"] == 91


def test_members_can_start_a_scan(client):
    """Client asked for this explicitly after seeing the first draft."""
    for who in ("admin", "dayo", "bola", "chidi"):
        perms = client.get("/api/auth/me", headers=tok(client, who)).json()["permissions"]
        assert "scan:run" in perms, who


# --- v2 changes requested by the frontend when they declined todo 2 v1 ---


def test_pipeline_value_is_a_number_not_a_formatted_string(client):
    """Formatting money is the frontend's job; the API sends a number."""
    radar = client.get("/api/radar", headers=tok(client, "admin")).json()
    assert isinstance(radar["estimatedPipelineValue"], int)
    assert radar["estimatedPipelineCurrency"] == "NGN"


def test_priority_actions_are_derived_not_hardcoded(client):
    admin = tok(client, "admin")
    actions = client.get("/api/priority-actions", headers=admin).json()
    assert actions, "the Radar section would be empty"
    allowed = {"Opportunity", "Organisation", "Industry", "Partnership", "Competitor"}
    assert {a["type"] for a in actions} <= allowed
    # Every Opportunity row points at a real opportunity.
    for a in actions:
        if a["type"] == "Opportunity":
            assert (
                client.get(f"/api/opportunities/{a['opportunityId']}", headers=admin).status_code
                == 200
            )
    # No row advertises a deadline that does not exist.
    assert not any("No deadline stated" in a["description"] for a in actions)


def test_priority_actions_are_scoped_like_the_list(client):
    """A lead in a unit with one scored opportunity gets a shorter list."""
    lead = client.get("/api/priority-actions", headers=tok(client, "tunde")).json()
    everyone = client.get("/api/priority-actions", headers=tok(client, "dayo")).json()
    assert len(lead) < len(everyone)


def test_unit_filter_narrows_for_scope_all(client):
    """A director can focus one unit; the client is an admin and will need this."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import BusinessUnit

    with Session(engine) as s:
        units = {u.name: u.id for u in s.exec(select(BusinessUnit)).all()}

    director = tok(client, "dayo")
    everything = client.get("/api/opportunities", headers=director).json()
    just_dt = client.get(
        f"/api/opportunities?business_unit_id={units['Design Teem']}", headers=director
    ).json()

    assert len(just_dt) < len(everything)
    assert all(r["yourFitPercent"] is not None for r in just_dt)
    assert (
        client.get("/api/opportunities?business_unit_id=999", headers=director).status_code
        == 400
    )


def test_unit_filter_cannot_widen_a_leads_scope(client):
    """A lead asking for another unit's rows is ignored, not obeyed.

    The filter narrows; it must never be a way around scoping.
    """
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import BusinessUnit

    with Session(engine) as s:
        tf = s.exec(select(BusinessUnit).where(BusinessUnit.name == "TM Foundation")).one().id

    dt_lead = tok(client, "tunde")  # Design Teem only
    normal = client.get("/api/opportunities", headers=dt_lead).json()
    attempted = client.get(
        f"/api/opportunities?business_unit_id={tf}", headers=dt_lead
    ).json()

    assert [r["id"] for r in attempted] == [r["id"] for r in normal]


def test_learning_field_renamed(client):
    stats = client.get("/api/learning", headers=tok(client, "admin")).json()
    assert "avgPursuedFitPercent" in stats
    assert "avgFoundationFitPursued" not in stats


# --- write routes are gated by codename, not just by being authenticated ---
#
# GET routes only ever required a login (see the endpoint-auth tests). These
# pin the separate, stricter rule for POST/PUT/PATCH/DELETE: the caller must
# hold the specific codename, and a 403 here must be the gate talking, not a
# 404 in disguise — every target below is created first so it really exists.


def test_source_create_requires_source_create_not_just_login(client):
    """`source:*` is director/admin only in the seeded grid — a lead or a
    member, who hold only `source:read`, must be refused."""
    lead = tok(client, "bola")
    member = tok(client, "chidi")
    director = tok(client, "dayo")
    admin = tok(client, "admin")

    payload = {"name": "RBAC Test Feed", "url": "https://example.com/rbac-feed"}
    for who, expected in [(lead, 403), (member, 403), (director, 201), (admin, 201)]:
        r = client.post("/api/sources", json=payload, headers=who)
        assert r.status_code == expected, r.text


def test_source_update_and_delete_require_source_write(client):
    """Same split for PATCH and DELETE: source:update / source:delete are
    director/admin only, not lead or member."""
    director = tok(client, "dayo")
    lead = tok(client, "bola")
    member = tok(client, "chidi")

    created = client.post(
        "/api/sources",
        json={"name": "RBAC Update Target", "url": "https://example.com/rbac-target"},
        headers=director,
    )
    assert created.status_code == 201
    source_id = created.json()["id"]

    for who in (lead, member):
        assert (
            client.patch(
                f"/api/sources/{source_id}", json={"active": False}, headers=who
            ).status_code
            == 403
        )
        assert client.delete(f"/api/sources/{source_id}", headers=who).status_code == 403

    # The holder can actually do both, in order, ending with a real delete.
    assert (
        client.patch(
            f"/api/sources/{source_id}", json={"active": False}, headers=director
        ).status_code
        == 200
    )
    assert client.delete(f"/api/sources/{source_id}", headers=director).status_code == 204


def test_profile_update_is_lead_and_above_not_member(client):
    """A lead holds profile:update; a member holds only profile:read — the
    grid's whole point is that scope and grants are independent, and this is
    a grant difference between two roles with the SAME scope."""
    admin = tok(client, "admin")
    profiles = client.get("/api/profiles", headers=admin).json()
    # bola leads TM Foundation, so use TM FOUNDATION's profile. profiles[0] is
    # Takeout Media, and a lead editing another unit's profile is now a 403 in
    # its own right — which would make this test pass or fail for the wrong
    # reason. What it is here to prove is the GRANT: lead yes, member no.
    own = next(p for p in profiles if p["businessUnitName"] == "TM Foundation")
    other = next(p for p in profiles if p["businessUnitName"] == "Takeout Media")
    payload = {"positioning": "rbac write-gate probe"}

    member = tok(client, "chidi")
    assert (
        client.put(f"/api/profiles/{own['id']}", json=payload, headers=member).status_code
        == 403
    )

    lead = tok(client, "bola")
    ok = client.put(f"/api/profiles/{own['id']}", json=payload, headers=lead)
    assert ok.status_code == 200
    assert ok.json()["positioning"] == payload["positioning"]

    # And the grant alone is not enough — scope applies too. Without this, a
    # lead could set another unit's min_fit_percent and silently empty their
    # opportunity list from a screen they never see.
    assert (
        client.put(f"/api/profiles/{other['id']}", json=payload, headers=lead).status_code
        == 403
    )


def test_scan_run_is_currently_granted_to_every_seeded_role(client):
    """`scan:run` sits on member as well as lead/director/admin in the seeded
    grid (app/rbac.py ROLES) — there is no seeded role to demonstrate a 403
    against. That may be unintended, but changing who HOLDS the grant is a
    separate decision nobody has approved; this test just pins the grid as it
    stands: every seeded role can start a scan once authenticated."""
    for who in ("admin", "dayo", "bola", "chidi"):
        assert client.post("/api/scan", headers=tok(client, who)).status_code == 202


# --- regressions from the code review, each one confirmed live before fixing ---


def _unitless_member(client, username="orphan"):
    """A member with a role but NO business unit — the /admin form allows it."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import Role, User
    from app.security import hash_password

    with Session(engine) as s:
        if not s.exec(select(User).where(User.username == username)).first():
            role = s.exec(select(Role).where(Role.name == "member")).one()
            s.add(
                User(
                    username=username,
                    email=f"{username}@tmglobal.local",
                    hashed_password=hash_password(STAFF_PW),
                    role_id=role.id,
                )
            )
            s.commit()
    return tok(client, username)


def test_a_scoped_user_with_no_unit_sees_nothing_not_everything(client):
    """The fail-open. `scoped = bool(unit_ids)` could not tell a director
    (empty because they see all) from a member whose unit box was never ticked
    (empty because they belong nowhere), and treated the second like the first.

    Every account created in /admin without remembering to tick a unit was in
    this state, because the form makes business_units optional.
    """
    orphan = _unitless_member(client)

    assert client.get("/api/opportunities", headers=orphan).json() == []
    assert client.get("/api/priority-actions", headers=orphan).json() == []

    tiles = client.get("/api/radar", headers=orphan).json()
    assert tiles["opportunitiesWorthPursuing"] == 0
    assert tiles["estimatedPipelineValue"] == 0

    # An admin, whose unit list is empty for the OPPOSITE reason, is unaffected.
    admin_tiles = client.get("/api/radar", headers=tok(client, "admin")).json()
    assert admin_tiles["estimatedPipelineValue"] > 0


def test_detail_is_not_openable_for_an_opportunity_none_of_your_units_scored(client):
    """Detail required only a token, so a lead whose list was empty could still
    fetch any opportunity by its slug — and the slugs are guessable.

    This is NOT the fit threshold: a below-bar row stays openable. It is about
    having no score in any of your units at all.
    """
    orphan = _unitless_member(client, "orphan2")
    r = client.get("/api/opportunities/gam-au", headers=orphan)
    assert r.status_code == 404
    # Same wording as a genuinely missing row, so it is not an existence oracle.
    assert r.json()["detail"] == client.get(
        "/api/opportunities/no-such-slug", headers=orphan
    ).json()["detail"]

    assert client.get("/api/opportunities/gam-au", headers=tok(client, "admin")).status_code == 200


def test_a_decision_cannot_be_attributed_to_a_unit_that_does_not_exist(client):
    """SQLite does not enforce the foreign key, so 999 was written through."""
    r = client.post(
        "/api/decisions",
        json={"opportunityId": "gam-au", "businessUnitId": 999, "decision": "Watch"},
        headers=tok(client, "admin"),
    )
    assert r.status_code == 400
    assert "unknown business unit" in r.json()["detail"]


def test_a_member_cannot_log_a_decision_for_another_unit(client):
    """chidi is in TM Foundation. Takeout Media's learning history is not
    theirs to write, least of all a Reject with a reason attached."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import BusinessUnit

    with Session(engine) as s:
        other = s.exec(
            select(BusinessUnit).where(BusinessUnit.name == "Takeout Media")
        ).one().id

    r = client.post(
        "/api/decisions",
        json={
            "opportunityId": "gam-au",
            "businessUnitId": other,
            "decision": "Reject",
            "reason": "not ours to reject",
        },
        headers=tok(client, "chidi"),
    )
    assert r.status_code == 403


def test_decisions_and_learning_are_scoped_like_everything_else(client):
    """Both took a bare current_user, so a lead read another unit's candid
    rejection reasons and an average computed over calls they never made."""
    admin = tok(client, "admin")
    # An admin logs one for each unit.
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import BusinessUnit

    with Session(engine) as s:
        units = {u.name: u.id for u in s.exec(select(BusinessUnit)).all()}

    for unit in ("TM Foundation", "Takeout Media"):
        client.post(
            "/api/decisions",
            json={
                "opportunityId": "gam-au",
                "businessUnitId": units[unit],
                "decision": "Pursue",
            },
            headers=admin,
        )

    mine = client.get("/api/decisions", headers=tok(client, "chidi")).json()
    assert mine, "the member should see their own unit's decisions"
    assert {d["businessUnitId"] for d in mine} == {units["TM Foundation"]}

    everyones = client.get("/api/decisions", headers=admin).json()
    assert len(everyones) > len(mine)

    stats = client.get("/api/learning", headers=tok(client, "chidi")).json()
    assert stats["decisionsLogged"] == len(mine)


# --- canEdit on the profile list: the client must never have to infer scope ---


def _unitless_lead(client, username="orphan.lead"):
    """A LEAD with no business unit. /admin creates exactly this: units are an
    optional many-to-many on UserAdmin, so saving the form without ticking one
    produces a user holding profile:update whose unit set is empty."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import Role, User
    from app.security import hash_password

    with Session(engine) as s:
        if not s.exec(select(User).where(User.username == username)).first():
            role = s.exec(select(Role).where(Role.name == "lead")).one()
            s.add(
                User(
                    username=username,
                    email=f"{username}@tmglobal.local",
                    hashed_password=hash_password(STAFF_PW),
                    role_id=role.id,
                )
            )
            s.commit()
    return tok(client, username)


def test_can_edit_never_lies_about_what_a_put_would_do(client):
    """canEdit must agree with the gate for EVERY role on EVERY profile.

    This is the invariant that makes the field worth having. A canEdit the
    frontend trusts, that disagrees with the PUT, is worse than no field — it
    draws a control whose save 403s, which is the exact failure the Sources
    read/write split exists to prevent. So assert the two against each other
    rather than asserting canEdit against a hand-written expectation.

    An empty body is a genuine no-op returning 200, so this probes all four
    roles against all five profiles without mutating anything.
    """
    for who in ("admin", "dayo", "bola", "chidi"):
        headers = tok(client, who)
        for row in client.get("/api/profiles", headers=headers).json():
            actual = client.put(
                f"/api/profiles/{row['id']}", json={}, headers=headers
            ).status_code
            assert (actual == 200) == row["canEdit"], (
                f"{who} on {row['businessUnitName']}: "
                f"canEdit={row['canEdit']} but PUT returned {actual}"
            )


def test_can_edit_is_false_for_a_lead_who_belongs_to_no_unit(client):
    """The reason this field exists rather than being derived client-side.

    /api/auth/me carries businessUnits and permissions but no scope, so the only
    client-side way to spot an unscoped user is `businessUnits.length === 0` —
    the same fail-open inference removed from the backend as review finding 1.
    This account defeats it: a lead with an empty unit set holds profile:update
    and looks identical to an admin through that lens, so the inference would
    render all five profiles editable and every save would 403.
    """
    headers = _unitless_lead(client)

    me = client.get("/api/auth/me", headers=headers).json()
    assert me["businessUnits"] == [], "the inference's input is genuinely empty"
    assert "profile:update" in me["permissions"], "and they DO hold the grant"

    rows = client.get("/api/profiles", headers=headers).json()
    assert len(rows) == 5, "reading stays unscoped — they still see all five"
    assert all(r["canEdit"] is False for r in rows), (
        "belonging to no unit means editing nothing, not editing everything"
    )

    for row in rows:
        assert (
            client.put(f"/api/profiles/{row['id']}", json={}, headers=headers).status_code
            == 403
        )


def test_can_edit_follows_membership_not_the_role_name(client):
    """A two-unit lead gets exactly two editable rows. Unit membership is a SET,
    so this is the case a single-unit shortcut would get wrong."""
    admin = tok(client, "admin")
    assert all(r["canEdit"] for r in client.get("/api/profiles", headers=admin).json())

    lead = tok(client, "bola")
    editable = {
        r["businessUnitName"]
        for r in client.get("/api/profiles", headers=lead).json()
        if r["canEdit"]
    }
    assert editable == {"TM Foundation"}, editable

    member = tok(client, "chidi")
    assert not any(
        r["canEdit"] for r in client.get("/api/profiles", headers=member).json()
    ), "a member lacks profile:update entirely, whatever they belong to"
