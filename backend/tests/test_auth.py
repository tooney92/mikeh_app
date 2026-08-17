"""Auth tests: login, identity, permissions, password changes."""

import importlib
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ADMIN_PW = "test-admin-pw-123"
STAFF_PW = "staff-pw-12345"


@pytest.fixture(scope="module")
def client(monkeypatch_module):
    tmp = Path(tempfile.mkdtemp())

    from app import db

    db.DB_PATH = tmp / "auth.db"
    db.engine = db.create_engine(
        f"sqlite:///{db.DB_PATH}", connect_args={"check_same_thread": False}
    )

    for mod in ("app.seed", "app.routers.scan", "app.admin", "app.main"):
        importlib.reload(importlib.import_module(mod))

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def monkeypatch_module():
    """Module-scoped env so the seeded admin has a password we know."""
    import os

    os.environ["TM_ADMIN_USERNAME"] = "admin"
    os.environ["TM_ADMIN_EMAIL"] = "admin@tmglobal.local"
    os.environ["TM_ADMIN_PASSWORD"] = ADMIN_PW
    yield


@pytest.fixture(scope="module")
def staff(client):
    """A non-admin user in Design Teem, created directly like the admin UI does."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import BusinessUnit, User
    from app.security import hash_password

    from app.models import Role

    with Session(engine) as s:
        unit = s.exec(select(BusinessUnit).where(BusinessUnit.name == "Design Teem")).one()
        role = s.exec(select(Role).where(Role.name == "member")).one()
        user = User(
            username="tunde",
            email="tunde@tmglobal.local",
            hashed_password=hash_password(STAFF_PW),
            full_name="Tunde A",
            role_id=role.id,
        )
        user.business_units = [unit]
        s.add(user)
        s.commit()
        s.refresh(user)
        return user.id


def token(client, identifier, password):
    r = client.post(
        "/api/auth/login", json={"identifier": identifier, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["accessToken"]


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_five_business_units_seeded(client):
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import BusinessUnit

    with Session(engine) as s:
        names = {u.name for u in s.exec(select(BusinessUnit)).all()}
    assert names == {
        "Takeout Media",
        "Design Teem",
        "Ingene Studios",
        "TM Labs",
        "TM Foundation",
    }


def test_login_with_username_or_email(client):
    assert token(client, "admin", ADMIN_PW)
    assert token(client, "admin@tmglobal.local", ADMIN_PW)


def test_bad_credentials_do_not_reveal_whether_user_exists(client):
    real = client.post(
        "/api/auth/login", json={"identifier": "admin", "password": "wrong"}
    )
    ghost = client.post(
        "/api/auth/login", json={"identifier": "ghost", "password": "wrong"}
    )
    assert real.status_code == ghost.status_code == 401
    assert real.json()["detail"] == ghost.json()["detail"]


def test_me_requires_a_valid_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=auth("garbage.token")).status_code == 401


def test_me_reports_unit(client, staff):
    body = client.get("/api/auth/me", headers=auth(token(client, "tunde", STAFF_PW))).json()
    assert body["username"] == "tunde"
    assert [u["name"] for u in body["businessUnits"]] == ["Design Teem"]
    assert body["role"]["name"] == "member"
    assert body["role"]["scope"] == "own_units"
    assert "admin:access" not in body["permissions"]


def test_password_hash_is_never_returned(client, staff):
    body = client.get("/api/auth/me", headers=auth(token(client, "tunde", STAFF_PW))).json()
    assert not any("password" in k.lower() for k in body)


def test_admin_only_routes_reject_staff(client, staff):
    staff_tok = auth(token(client, "tunde", STAFF_PW))
    assert client.get("/api/users", headers=staff_tok).status_code == 403
    assert (
        client.post(
            "/api/users/1/reset-password",
            json={"newPassword": "hijacked12345"},
            headers=staff_tok,
        ).status_code
        == 403
    )
    assert client.get("/api/users", headers=auth(token(client, "admin", ADMIN_PW))).status_code == 200


def test_change_password_requires_the_current_one(client, staff):
    tok = auth(token(client, "tunde", STAFF_PW))
    bad = client.post(
        "/api/auth/change-password",
        json={"currentPassword": "nope", "newPassword": "brandnewpw123"},
        headers=tok,
    )
    assert bad.status_code == 400


def test_short_passwords_rejected(client, staff):
    tok = auth(token(client, "tunde", STAFF_PW))
    r = client.post(
        "/api/auth/change-password",
        json={"currentPassword": STAFF_PW, "newPassword": "short"},
        headers=tok,
    )
    assert r.status_code == 400


def test_admin_reset_lets_the_user_log_in_again(client, staff):
    new_pw = "reset-by-admin-1"
    r = client.post(
        f"/api/users/{staff}/reset-password",
        json={"newPassword": new_pw},
        headers=auth(token(client, "admin", ADMIN_PW)),
    )
    assert r.status_code == 204
    assert token(client, "tunde", new_pw)
    # The password the admin replaced no longer works.
    assert (
        client.post(
            "/api/auth/login", json={"identifier": "tunde", "password": STAFF_PW}
        ).status_code
        == 401
    )


def test_deactivating_a_user_kills_their_live_token(client, staff):
    from sqlmodel import Session

    from app.db import engine
    from app.models import User

    tok = auth(token(client, "tunde", "reset-by-admin-1"))
    assert client.get("/api/auth/me", headers=tok).status_code == 200

    with Session(engine) as s:
        u = s.get(User, staff)
        u.is_active = False
        s.add(u)
        s.commit()

    # Already-issued token stops working immediately — no waiting for expiry.
    assert client.get("/api/auth/me", headers=tok).status_code == 403
    assert (
        client.post(
            "/api/auth/login",
            json={"identifier": "tunde", "password": "reset-by-admin-1"},
        ).status_code
        == 403
    )


def test_admin_dashboard_is_gated(client):
    r = client.get("/admin/user/list", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "/admin/login" in r.headers["location"]


# --- per-unit scoping: "each unit should only see opportunities for their unit" ---


def _staff_in(client, username, unit_name, extra_score=None, role="member"):
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import BusinessUnit, OpportunityScore, Role, User
    from app.security import hash_password

    with Session(engine) as s:
        unit = s.exec(select(BusinessUnit).where(BusinessUnit.name == unit_name)).one()
        role_row = s.exec(select(Role).where(Role.name == role)).one()
        if not s.exec(select(User).where(User.username == username)).first():
            u = User(
                username=username,
                email=f"{username}@tmglobal.local",
                hashed_password=hash_password(STAFF_PW),
                role_id=role_row.id,
            )
            u.business_units = [unit]
            s.add(u)
        if extra_score:
            s.add(
                OpportunityScore(
                    opportunity_id=extra_score,
                    business_unit_id=unit.id,
                    fit_percent=64,
                )
            )
        s.commit()
    return unit_name


def test_a_unit_sees_only_its_own_opportunities(client):
    """Design Teem has one scored opportunity, so it sees exactly one."""
    _staff_in(client, "dtuser", "Design Teem", extra_score="encyclopaedia")
    tok = auth(token(client, "dtuser", STAFF_PW))

    rows = client.get("/api/opportunities", headers=tok).json()
    assert len(rows) == 1
    assert rows[0]["id"] == "encyclopaedia"
    assert rows[0]["yourFitPercent"] == 64


def test_each_unit_ranks_by_its_own_fit(client):
    """The same list, ordered differently for two units — that is the point.

    Asks for include_weak so both units return all eight. Ranking is what this
    test is about, and the per-unit fit threshold (which hides Takeout Media's
    12% and 15% matches) would otherwise leave nothing to compare orderings
    with. The threshold has its own tests below.
    """
    _staff_in(client, "tfuser", "TM Foundation")
    _staff_in(client, "tmuser", "Takeout Media")

    foundation = client.get(
        "/api/opportunities?include_weak=true",
        headers=auth(token(client, "tfuser", STAFF_PW)),
    ).json()
    takeout = client.get(
        "/api/opportunities?include_weak=true",
        headers=auth(token(client, "tmuser", STAFF_PW)),
    ).json()

    assert len(foundation) == len(takeout) == 8
    for rows in (foundation, takeout):
        fits = [r["yourFitPercent"] for r in rows]
        assert fits == sorted(fits, reverse=True)

    # Same eight opportunities, ordered differently — each unit ranks by its
    # own fit. (They happen to share a top pick: gam-au leads both lists.)
    assert {r["id"] for r in foundation} == {r["id"] for r in takeout}
    assert [r["id"] for r in foundation] != [r["id"] for r in takeout]
    # And the same opportunity carries a different fit for each unit.
    assert foundation[0]["yourFitPercent"] != takeout[0]["yourFitPercent"]


def _set_bar(client, unit_name, percent):
    """Set one unit's min_fit_percent directly, as an admin would in /admin."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import BusinessUnit, Profile

    with Session(engine) as s:
        unit = s.exec(select(BusinessUnit).where(BusinessUnit.name == unit_name)).one()
        profile = s.exec(
            select(Profile).where(Profile.business_unit_id == unit.id)
        ).one()
        profile.min_fit_percent = percent
        s.add(profile)
        s.commit()


def test_weak_matches_are_hidden_from_the_unit_they_score_badly_for(client):
    """Takeout Media is shown 12% and 15% matches. It should not be."""
    _staff_in(client, "bartm", "Takeout Media")
    _set_bar(client, "Takeout Media", 40)
    tok = token(client, "bartm", STAFF_PW)

    shown = client.get("/api/opportunities", headers=auth(tok)).json()
    assert [r["yourFitPercent"] for r in shown] == [70, 55, 48]

    # The escape hatch returns the rest — hidden by default, never unreachable.
    everything = client.get(
        "/api/opportunities?include_weak=true", headers=auth(tok)
    ).json()
    assert len(everything) == 8


def test_the_bar_is_your_own_fit_never_the_top_fit(client):
    """The failure this guards against is subtle and silent.

    au-commission-gami scores 82 for TM Foundation and 35 for Takeout Media.
    Comparing against topFitPercent would keep it in Takeout's list on the
    strength of another unit's score — leaking back in the exact row the
    threshold exists to remove.
    """
    _staff_in(client, "ownfit", "Takeout Media")
    _set_bar(client, "Takeout Media", 40)

    shown = client.get(
        "/api/opportunities", headers=auth(token(client, "ownfit", STAFF_PW))
    ).json()
    rows = {r["id"]: r for r in shown}
    assert "au-commission-gami" not in rows
    # Present, and above the bar on the top score alone, which is the trap.
    everything = client.get(
        "/api/opportunities?include_weak=true",
        headers=auth(token(client, "ownfit", STAFF_PW)),
    ).json()
    advisory = {r["id"]: r for r in everything}["au-commission-gami"]
    assert advisory["topFitPercent"] >= 40 and advisory["yourFitPercent"] < 40


def test_the_bar_is_per_unit_not_global(client):
    """One number cannot suit both units, which is why an admin sets each."""
    _staff_in(client, "perunit_tm", "Takeout Media")
    _staff_in(client, "perunit_tf", "TM Foundation")
    _set_bar(client, "Takeout Media", 60)
    _set_bar(client, "TM Foundation", 40)

    takeout = client.get(
        "/api/opportunities", headers=auth(token(client, "perunit_tm", STAFF_PW))
    ).json()
    foundation = client.get(
        "/api/opportunities", headers=auth(token(client, "perunit_tf", STAFF_PW))
    ).json()

    assert all(r["yourFitPercent"] >= 60 for r in takeout)
    assert all(r["yourFitPercent"] >= 40 for r in foundation)
    assert len(foundation) > len(takeout)
    _set_bar(client, "Takeout Media", 40)


def test_an_unscoped_admin_is_never_filtered_by_a_units_bar(client):
    """Directors and admins oversee; they are not being pitched to."""
    _set_bar(client, "Takeout Media", 90)
    rows = client.get("/api/opportunities", headers=auth(token(client, "admin", ADMIN_PW))).json()
    assert len(rows) == 8
    _set_bar(client, "Takeout Media", 40)


def test_admin_narrowing_to_a_unit_sees_that_units_bar(client):
    """So an admin can preview what a lead in that unit actually sees."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import BusinessUnit

    with Session(engine) as s:
        tm = s.exec(
            select(BusinessUnit).where(BusinessUnit.name == "Takeout Media")
        ).one().id

    _set_bar(client, "Takeout Media", 40)
    tok = token(client, "admin", ADMIN_PW)
    narrowed = client.get(
        f"/api/opportunities?business_unit_id={tm}", headers=auth(tok)
    ).json()
    assert len(narrowed) == 3
    weak = client.get(
        f"/api/opportunities?business_unit_id={tm}&include_weak=true",
        headers=auth(tok),
    ).json()
    assert len(weak) == 8


def test_a_lead_of_two_units_keeps_what_clears_either_bar(client):
    """Union, consistent with ranking by the better of their two fits."""
    _staff_in(client, "bothbars", "Takeout Media", role="lead")
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import BusinessUnit, User

    with Session(engine) as s:
        u = s.exec(select(User).where(User.username == "bothbars")).one()
        tf = s.exec(
            select(BusinessUnit).where(BusinessUnit.name == "TM Foundation")
        ).one()
        if tf not in u.business_units:
            u.business_units.append(tf)
            s.add(u)
            s.commit()

    _set_bar(client, "Takeout Media", 90)  # nothing clears this
    _set_bar(client, "TM Foundation", 40)  # everything clears this

    rows = client.get(
        "/api/opportunities", headers=auth(token(client, "bothbars", STAFF_PW))
    ).json()
    # Kept via TM Foundation despite Takeout Media's bar excluding them all.
    assert len(rows) == 8
    _set_bar(client, "Takeout Media", 40)


def test_joint_pitch_agrees_across_endpoints(client):
    """The bug: priority-actions announced a joint pitch that detail denied.

    Two units over 60 on gam-au (82 and 70). priority-actions computed that and
    emitted a Partnership row; the detail endpoint read isJointPitchCandidate
    off a stored column nothing has ever written, so it answered false. The
    screen whose stated purpose is surfacing a joint pitch could not.
    """
    tok = auth(token(client, "admin", ADMIN_PW))

    detail = client.get("/api/opportunities/gam-au", headers=tok).json()
    flagged = [s for s in detail["scores"] if s["isJointPitchCandidate"]]
    assert len(flagged) == 2
    assert all(s["fitPercent"] >= 60 for s in flagged)
    assert all(s["jointPitchNote"] for s in flagged)

    partnerships = [
        a
        for a in client.get("/api/priority-actions", headers=tok).json()
        if a["type"] == "Partnership" and a["opportunityId"] == "gam-au"
    ]
    assert partnerships, "priority-actions must still emit the row it always did"
    # One rule, one wording — the two endpoints cannot drift apart again.
    assert partnerships[0]["description"] == flagged[0]["jointPitchNote"]


def test_one_strong_unit_is_not_a_joint_pitch(client):
    """Guards the opposite failure: a flag that is simply always true.

    au-commission-gami scores 82 for TM Foundation and 35 for Takeout Media.
    One unit fitting well is a good opportunity, not a partnership.
    """
    detail = client.get(
        "/api/opportunities/au-commission-gami",
        headers=auth(token(client, "admin", ADMIN_PW)),
    ).json()
    assert not any(s["isJointPitchCandidate"] for s in detail["scores"])
    assert not any(s["jointPitchNote"] for s in detail["scores"])


def test_radar_counts_what_the_viewer_can_actually_see(client):
    """A dashboard contradicting the list below it is worse than either number.

    Radar used to count every row in the database whoever asked — it took the
    signed-in user and discarded them. A Takeout lead saw tiles describing
    opportunities their own list refused to show.
    """
    _staff_in(client, "radarlead", "Takeout Media")
    _set_bar(client, "Takeout Media", 40)
    tok = auth(token(client, "radarlead", STAFF_PW))

    tiles = client.get("/api/radar", headers=tok).json()
    rows = client.get("/api/opportunities", headers=tok).json()
    assert tiles["opportunitiesWorthPursuing"] <= len(rows)
    assert tiles["estimatedPipelineValue"] > 0

    # Asking both the same question returns the same larger world.
    weak_tiles = client.get("/api/radar?include_weak=true", headers=tok).json()
    weak_rows = client.get("/api/opportunities?include_weak=true", headers=tok).json()
    assert weak_tiles["estimatedPipelineValue"] > tiles["estimatedPipelineValue"]
    assert len(weak_rows) > len(rows)

    # An admin has no unit, so nothing is withheld from their totals.
    admin_tiles = client.get(
        "/api/radar", headers=auth(token(client, "admin", ADMIN_PW))
    ).json()
    assert admin_tiles["estimatedPipelineValue"] >= weak_tiles["estimatedPipelineValue"]


def test_admin_sees_everything_with_no_unit_fit(client):
    rows = client.get(
        "/api/opportunities", headers=auth(token(client, "admin", ADMIN_PW))
    ).json()
    assert len(rows) == 8
    assert all(r["yourFitPercent"] is None for r in rows)
