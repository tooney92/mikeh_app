"""Smoke tests against a throwaway SQLite file, seeded from the handoff data."""

import importlib
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ADMIN_PW = "smoke-admin-pw-123"


@pytest.fixture(scope="module")
def client():
    os.environ["TM_ADMIN_USERNAME"] = "admin"
    os.environ["TM_ADMIN_EMAIL"] = "admin@tmglobal.local"
    os.environ["TM_ADMIN_PASSWORD"] = ADMIN_PW

    tmp = Path(tempfile.mkdtemp())

    from app import db

    db.DB_PATH = tmp / "test.db"
    db.engine = db.create_engine(
        f"sqlite:///{db.DB_PATH}", connect_args={"check_same_thread": False}
    )

    # Rebind the modules that captured `engine` at import time.
    for mod in ("app.seed", "app.routers.scan", "app.admin", "app.main"):
        importlib.reload(importlib.import_module(mod))

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth(client):
    """Every business-data endpoint requires a token now — log in once as the
    seeded admin and reuse the header everywhere."""
    r = client.post(
        "/api/auth/login", json={"identifier": "admin", "password": ADMIN_PW}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_seeded_opportunities(client, auth):
    rows = client.get("/api/opportunities", headers=auth).json()
    assert len(rows) == 8
    # Admin caller: ranked by the best fit across any unit, descending.
    assert [r["topFitPercent"] for r in rows] == sorted(
        (r["topFitPercent"] for r in rows), reverse=True
    )


def test_filters(client, auth):
    assert len(client.get("/api/opportunities?filter=partnership", headers=auth).json()) == 1
    assert client.get("/api/opportunities?filter=nonsense", headers=auth).status_code == 400


def test_detail_and_404(client, auth):
    detail = client.get("/api/opportunities/wipo", headers=auth).json()
    assert detail["org"].startswith("World Intellectual Property")
    assert detail["themes"]
    assert client.get("/api/opportunities/nope", headers=auth).status_code == 404


def test_reject_requires_reason(client, auth):
    bad = client.post(
        "/api/decisions",
        json={"opportunityId": "wipo", "decision": "Reject"},
        headers=auth,
    )
    assert bad.status_code == 400


def test_decision_feeds_learning(client, auth):
    client.post(
        "/api/decisions",
        json={"opportunityId": "gam-au", "decision": "Pursue"},
        headers=auth,
    )
    stats = client.get("/api/learning", headers=auth).json()
    assert stats["decisionsLogged"] == 1
    assert stats["avgPursuedFitPercent"] == 82.0
    assert stats["mostBackedTheme"] == "Cultural Heritage"
    assert stats["breakdown"] == {"Pursue": 1}


def test_one_profile_per_business_unit(client, auth):
    profiles = client.get("/api/profiles", headers=auth).json()
    assert {p["businessUnitName"] for p in profiles} == {
        "Takeout Media",
        "Design Teem",
        "Ingene Studios",
        "TM Labs",
        "TM Foundation",
    }
    # The three units the sample data says nothing about start EMPTY rather
    # than carrying invented content.
    empty = {p["businessUnitName"] for p in profiles if not p["priorities"]}
    assert empty == {"Design Teem", "Ingene Studios", "TM Labs"}


def test_detail_carries_every_units_score(client, auth):
    detail = client.get("/api/opportunities/gam-au", headers=auth).json()
    scored = {s["businessUnitName"]: s["fitPercent"] for s in detail["scores"]}
    assert scored == {"TM Foundation": 82, "Takeout Media": 70}
    assert detail["topFitPercent"] == 82
    # Scores come back best-first.
    assert [s["fitPercent"] for s in detail["scores"]] == [82, 70]


def test_seeded_orgs_and_sources(client, auth):
    assert len(client.get("/api/organisations", headers=auth).json()) == 10
    assert len(client.get("/api/business-units", headers=auth).json()) == 5

    # 90, not 15: seeding now also merges the client's 81 platforms in on a
    # database that has never seen them. The 15 originals are still all there —
    # that is the point of a merge, and the number this asserts.
    srcs = client.get("/api/sources", headers=auth).json()
    assert len(srcs) == 90
    assert sum(1 for s in srcs if s["provenance"] == "seed") == 9
    assert sum(1 for s in srcs if s["provenance"] == "client_import") == 81
