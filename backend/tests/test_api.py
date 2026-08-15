"""Smoke tests against a throwaway SQLite file, seeded from the handoff data."""

import importlib
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    tmp = Path(tempfile.mkdtemp())

    from app import db

    db.DB_PATH = tmp / "test.db"
    db.engine = db.create_engine(
        f"sqlite:///{db.DB_PATH}", connect_args={"check_same_thread": False}
    )

    # Rebind the modules that captured `engine` at import time.
    for mod in ("app.seed", "app.routers.scan", "app.main"):
        importlib.reload(importlib.import_module(mod))

    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_seeded_opportunities(client):
    rows = client.get("/api/opportunities").json()
    assert len(rows) == 8
    # Ranked by foundation fit, descending.
    assert [r["fitFoundation"] for r in rows] == sorted(
        (r["fitFoundation"] for r in rows), reverse=True
    )


def test_filters(client):
    assert len(client.get("/api/opportunities?filter=partnership").json()) == 1
    assert client.get("/api/opportunities?filter=nonsense").status_code == 400


def test_detail_and_404(client):
    detail = client.get("/api/opportunities/wipo").json()
    assert detail["org"].startswith("World Intellectual Property")
    assert detail["themes"]
    assert client.get("/api/opportunities/nope").status_code == 404


def test_reject_requires_reason(client):
    bad = client.post(
        "/api/decisions", json={"opportunityId": "wipo", "decision": "Reject"}
    )
    assert bad.status_code == 400


def test_decision_feeds_learning(client):
    client.post("/api/decisions", json={"opportunityId": "gam-au", "decision": "Pursue"})
    stats = client.get("/api/learning").json()
    assert stats["decisionsLogged"] == 1
    assert stats["avgFoundationFitPursued"] == 82.0
    assert stats["mostBackedTheme"] == "Cultural Heritage"
    assert stats["breakdown"] == {"Pursue": 1}


def test_seeded_profiles_and_orgs(client):
    assert {p["id"] for p in client.get("/api/profiles").json()} == {
        "takeout",
        "foundation",
    }
    assert len(client.get("/api/organisations").json()) == 10
    assert len(client.get("/api/sources").json()) == 15
