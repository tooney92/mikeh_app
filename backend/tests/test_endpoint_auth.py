"""Every business-data endpoint must refuse anonymous callers.

Before this, the routers under app/routers/ either had no auth dependency at
all, or used `optional_user` (token scopes the response but is never
required). This file pins down the fix: no token -> 401, valid token -> 200
(or whatever success code the route normally returns), for every endpoint
that was open. `/api/health` is the one deliberate exception — it is the
liveness probe and must keep answering with no token.
"""

import importlib
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ADMIN_PW = "endpoint-auth-admin-pw-1"


@pytest.fixture(scope="module")
def client(monkeypatch_module):
    tmp = Path(tempfile.mkdtemp())

    from app import db

    db.DB_PATH = tmp / "endpoint_auth.db"
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
    import os

    os.environ["TM_ADMIN_USERNAME"] = "admin"
    os.environ["TM_ADMIN_EMAIL"] = "admin@tmglobal.local"
    os.environ["TM_ADMIN_PASSWORD"] = ADMIN_PW
    yield


@pytest.fixture(scope="module")
def auth(client):
    r = client.post(
        "/api/auth/login", json={"identifier": "admin", "password": ADMIN_PW}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


def test_health_stays_open_with_no_token(client):
    """The liveness probe must not start requiring auth."""
    assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/business-units",
        "/api/decisions",
        "/api/learning",
        "/api/opportunities",
        "/api/opportunities/wipo",
        "/api/organisations",
        "/api/priority-actions",
        "/api/profiles",
        "/api/radar",
        "/api/scan/status",
        "/api/sources",
    ],
)
def test_get_endpoints_reject_anonymous_callers(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/api/business-units", 200),
        ("/api/decisions", 200),
        ("/api/learning", 200),
        ("/api/opportunities", 200),
        ("/api/opportunities/wipo", 200),
        ("/api/organisations", 200),
        ("/api/priority-actions", 200),
        ("/api/profiles", 200),
        ("/api/radar", 200),
        ("/api/scan/status", 200),
        ("/api/sources", 200),
    ],
)
def test_get_endpoints_work_with_a_valid_token(client, auth, path, expected):
    assert client.get(path, headers=auth).status_code == expected


def test_post_decisions_requires_auth(client, auth):
    payload = {"opportunityId": "wipo", "decision": "Watch"}
    assert client.post("/api/decisions", json=payload).status_code == 401
    assert client.post("/api/decisions", json=payload, headers=auth).status_code == 201


def test_update_profile_requires_auth(client, auth):
    profiles = client.get("/api/profiles", headers=auth).json()
    profile_id = profiles[0]["id"]
    payload = {"positioning": "unauthenticated attempt should be refused"}

    assert (
        client.put(f"/api/profiles/{profile_id}", json=payload).status_code == 401
    )
    ok = client.put(f"/api/profiles/{profile_id}", json=payload, headers=auth)
    assert ok.status_code == 200
    assert ok.json()["positioning"] == payload["positioning"]


def test_start_scan_requires_auth(client, auth):
    assert client.post("/api/scan").status_code == 401
    assert client.post("/api/scan", headers=auth).status_code == 202


def test_sources_write_routes_require_auth(client, auth):
    payload = {"name": "Anonymous Test Feed", "url": "https://example.com/feed"}

    assert client.post("/api/sources", json=payload).status_code == 401
    created = client.post("/api/sources", json=payload, headers=auth)
    assert created.status_code == 201
    source_id = created.json()["id"]

    patch = {"active": False}
    assert client.patch(f"/api/sources/{source_id}", json=patch).status_code == 401
    assert (
        client.patch(f"/api/sources/{source_id}", json=patch, headers=auth).status_code
        == 200
    )

    assert client.delete(f"/api/sources/{source_id}").status_code == 401
    assert client.delete(f"/api/sources/{source_id}", headers=auth).status_code == 204
