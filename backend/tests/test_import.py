"""Todo 4: importing the client's 81 opportunity platforms.

Every test here corresponds to a criterion in the locked v6 contract. The ones
that matter most are the merge-key tests: the whole deliverable turns on
reconciling by host-plus-path rather than by domain, and the difference is
invisible until it eats the only JSON source we have.
"""

import importlib
import json
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ADMIN_PW = "import-admin-pw-1"
STAFF_PW = "import-staff-pw-1"

# The six seeds the client also lists, by merge key. Derived in the fixture
# rather than hardcoded, but named here because they are the reconciliation.
SEED_FILE = Path(__file__).resolve().parent.parent / "seed" / "sources.json"


@pytest.fixture(scope="module")
def client():
    os.environ["TM_ADMIN_USERNAME"] = "admin"
    os.environ["TM_ADMIN_EMAIL"] = "admin@tmglobal.local"
    os.environ["TM_ADMIN_PASSWORD"] = ADMIN_PW

    tmp = Path(tempfile.mkdtemp())
    from app import db

    db.DB_PATH = tmp / "import.db"
    db.engine = db.create_engine(
        f"sqlite:///{db.DB_PATH}", connect_args={"check_same_thread": False}
    )
    for mod in ("app.rbac", "app.seed", "app.routers.scan", "app.admin", "app.main"):
        importlib.reload(importlib.import_module(mod))

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def imported(client):
    """The import has ALREADY run — seeding performs it on a database that has
    never seen the client's list. So this asserts that rather than re-running
    it, and re-running here would prove nothing about the first run."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import Source

    with Session(engine) as s:
        rows = s.exec(select(Source)).all()
        return {
            "total": len(rows),
            "created": sum(1 for r in rows if r.type == "unknown"),
            "reconciled": sum(
                1 for r in rows if r.provenance == "client_import" and r.type != "unknown"
            ),
            "client_rows": sum(1 for r in rows if r.provenance == "client_import"),
        }


def tok(client, who="admin"):
    r = client.post(
        "/api/auth/login", json={"identifier": who, "password": ADMIN_PW}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


def sources(client):
    r = client.get("/api/sources", headers=tok(client))
    assert r.status_code == 200, r.text
    return r.json()


# --- the merge key: the thing this deliverable turns on ---


def test_merge_key_is_host_plus_path_not_the_registrable_domain():
    """Key on the domain and search.worldbank.org collapses into
    projects.worldbank.org. The survivor is the client's html row, and the only
    JSON source in the system — the only one a crawler can read without HTML
    parsing — disappears into a record that looks perfectly healthy."""
    from app.importer import merge_key

    ours = merge_key("https://search.worldbank.org/api/v2/procnotices?format=json")
    theirs = merge_key("https://projects.worldbank.org/en/projects-operations/opportunities")
    third = merge_key("https://step.worldbank.org/")
    assert len({ours, theirs, third}) == 3, "three worldbank.org rows, three keys"

    # www. and a trailing slash are the same page by any reading.
    assert merge_key("https://www.devex.com/") == merge_key("http://devex.com")

    # Path is significant: the RSS feed is what a crawler wants, the landing
    # page is not, and a domain-keyed merge would eat the feed and keep the page.
    assert merge_key("https://opportunitydesk.org/feed/") != merge_key(
        "https://opportunitydesk.org/"
    )


def test_the_client_file_matches_what_the_contract_counted():
    """Nine numbers, verified independently by both seats before v6 locked. If
    the spreadsheet is ever re-exported, this fails rather than the import
    quietly producing a different world."""
    from app.importer import load_client_rows, merge_key

    rows = load_client_rows()
    seeds = json.loads(SEED_FILE.read_text())

    assert len(rows) == 81
    assert len({r["url"] for r in rows}) == 81
    assert len({merge_key(r["url"]) for r in rows}) == 81
    assert len(seeds) == 15
    assert len({merge_key(r["url"]) for r in rows} & {merge_key(s["url"]) for s in seeds}) == 6

    # Both columns are 100% populated, which is why clientOpportunityType and
    # clientSectors are never empty on an imported row.
    assert all(r["clientOpportunityType"] for r in rows)
    assert all(r["clientSectors"] for r in rows)
    # And completely unenumerable — 81 distinct strings, so the future exclusion
    # mechanism must match TEXT. No category scheme can be derived from this.
    assert len({r["clientOpportunityType"] for r in rows}) == 81


# --- the merge itself ---


def test_the_import_produces_exactly_90_rows(client, imported):
    """The single number that proves a merge happened. 96 means it failed to
    deduplicate, 81 means it replaced and destroyed the seeds, 77 means it keyed
    on domain rather than URL."""
    assert imported == {"created": 75, "reconciled": 6, "total": 90, "client_rows": 81}
    assert len(sources(client)) == 90


def test_seeding_performs_the_import_once_and_not_on_every_boot(client, imported):
    """Idempotent is not the same as inert. The import CREATES rows, so running
    it on every boot would silently resurrect a source somebody deliberately
    deleted, and they would have no way to make the deletion stick."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import Source
    from app.seed import seed_client_sources

    with Session(engine) as s:
        assert seed_client_sources(s) == 0, "already imported — must be a no-op"

        # A row the import CREATED, not one of the six it reconciled. Deleting a
        # reconciled row and re-importing would rebuild it from her list alone,
        # losing the type we had established — correct behaviour, since the row
        # was deleted and her sheet is all the import has, but a different
        # scenario from the one this test is about.
        victim = s.exec(
            select(Source)
            .where(Source.provenance == "client_import")
            .where(Source.type == "unknown")
        ).first()
        victim_url, victim_name = victim.url, victim.name
        s.delete(victim)
        s.commit()
        assert len(s.exec(select(Source)).all()) == 89

        # A boot must NOT bring it back.
        assert seed_client_sources(s) == 0
        assert len(s.exec(select(Source)).all()) == 89

        # Only an explicit re-import does, which is the documented way back.
        from app.importer import import_client_sources

        assert import_client_sources(s)["created"] == 1
        restored = s.exec(select(Source).where(Source.url == victim_url)).first()
        assert restored is not None and restored.name == victim_name


def test_no_two_rows_share_a_merge_key(client, imported):
    from app.importer import merge_key

    rows = sources(client)
    assert len({merge_key(r["url"]) for r in rows}) == len(rows)


def test_all_nine_seeds_without_an_exact_match_survive(client, imported):
    """Naming only four, as earlier contract versions did, points verification
    at the wrong subset — five of these nine were unnamed, and they are the ones
    a domain-keyed merge destroys."""
    nine = {
        "Ford Foundation News",
        "Gates Foundation Newsroom",
        "Google.org Opportunities",
        "World Bank Procurement Notices",
        "African Development Bank Procurement",
        "African Union Opportunities",
        "British Council Nigeria",
        "Opportunity Desk",
        "UNESCO Creative Economy",
    }
    by_name = {r["name"]: r for r in sources(client)}
    assert nine <= set(by_name), f"destroyed: {nine - set(by_name)}"


def test_the_only_json_source_survives_with_type_json(client, imported):
    """The expensive loss. It is the only source a crawler can read without
    HTML parsing, and it has an organisational twin in the spreadsheet, which
    makes it the row most likely to be lost by a keying mistake."""
    rows = sources(client)
    json_rows = [r for r in rows if r["type"] == "json"]
    assert len(json_rows) == 1
    assert "search.worldbank.org" in json_rows[0]["url"]
    assert json_rows[0]["provenance"] == "seed"


def test_every_worldbank_row_survives_separately(client, imported):
    """THREE, not two. The contract named two; the spreadsheet also carries
    step.worldbank.org, so a registrable-domain merge would have collapsed three
    rows into one rather than two into one."""
    wb = [r for r in sources(client) if "worldbank.org" in r["url"]]
    assert len(wb) == 3, [r["url"] for r in wb]
    assert {r["type"] for r in wb} == {"json", "unknown"}


def test_opportunity_desk_keeps_both_rows(client, imported):
    """Correct, not a duplicate: the RSS feed is what a crawler wants and the
    landing page is not."""
    od = [r for r in sources(client) if "opportunitydesk.org" in r["url"]]
    assert len(od) == 2
    assert {r["type"] for r in od} == {"rss", "unknown"}


# --- what the imported rows carry ---


def test_created_rows_assert_nothing_they_cannot_know(client, imported):
    """The spreadsheet has four columns and none says how a site publishes or
    whether it aggregates. So the import claims neither. `type` matters most: it
    decides how the crawler PARSES, and defaulting to "html" would have been 75
    silent assertions about sites nobody has opened."""
    seeds = {s["url"] for s in json.loads(SEED_FILE.read_text())}
    created = [r for r in sources(client) if r["url"] not in seeds]

    assert len(created) == 75
    assert all(r["type"] == "unknown" for r in created)
    assert all(r["sourceRole"] == "unconfirmed" for r in created)
    assert all(r["provenance"] == "client_import" for r in created)
    assert all(r["category"] == "" for r in created)
    # Knowingly temporary: the vocabulary cannot express three of the five units.
    assert all(r["scope"] == "both" for r in created)
    # Her evidence arrives intact on every row.
    assert all(r["clientOpportunityType"] and r["clientSectors"] for r in created)


def test_the_fifteen_originals_keep_their_examined_types(client, imported):
    """They were findings when somebody wrote the seeds, not defaults. Flattening
    them to "unknown" in the name of honesty would destroy real information."""
    seeds = {s["url"] for s in json.loads(SEED_FILE.read_text())}
    originals = [r for r in sources(client) if r["url"] in seeds]

    assert len(originals) == 15
    counts = {t: sum(1 for r in originals if r["type"] == t) for t in {r["type"] for r in originals}}
    assert counts == {"html": 12, "rss": 2, "json": 1}
    assert all(not r["clientOpportunityType"] for r in originals if r["provenance"] == "seed")


def test_reconciled_rows_become_hers_but_keep_what_we_knew(client, imported):
    """A row she also lists reconciles to ONE record and becomes client_import —
    her list is the reason we know she wants it watched. But our own more
    specific knowledge survives: we do not overwrite a type we established."""
    seeds = {s["url"] for s in json.loads(SEED_FILE.read_text())}
    rows = sources(client)
    reconciled = [r for r in rows if r["url"] in seeds and r["provenance"] == "client_import"]

    assert len(reconciled) == 6
    assert all(r["clientOpportunityType"] for r in reconciled), "gained her text"
    assert all(r["type"] != "unknown" for r in reconciled), "kept our examined type"


def test_provenance_splits_ninety_into_eighty_one_and_nine(client, imported):
    rows = sources(client)
    assert sum(1 for r in rows if r["provenance"] == "client_import") == 81
    assert sum(1 for r in rows if r["provenance"] == "seed") == 9
    assert all(r["provenance"] in ("seed", "client_import") for r in rows)


# --- re-running, which is the operation people perform casually ---


def test_the_import_is_safe_to_rerun(client, imported):
    from sqlmodel import Session

    from app.db import engine
    from app.importer import import_client_sources

    with Session(engine) as s:
        again = import_client_sources(s)
        assert again["created"] == 0
        assert again["total"] == 90
    assert len(sources(client)) == 90


def test_a_rerun_does_not_undo_a_humans_classification(client, imported):
    """The whole three-state design rests on a wrong value being CORRECTABLE. If
    a re-import resets it, the second run silently undoes somebody's work — and
    a re-run is exactly the operation performed casually, expecting a no-op."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.importer import import_client_sources
    from app.models import Source

    with Session(engine) as s:
        row = s.exec(
            select(Source).where(Source.url.like("%projects.worldbank%"))
        ).first()
        row.source_role = "issuer"
        row.type = "html"
        s.add(row)
        s.commit()
        row_id = row.id

        import_client_sources(s)

        after = s.get(Source, row_id)
        assert after.source_role == "issuer", "a human's role classification was reset"
        assert after.type == "html", "a human's format classification was reset"

        # Put it back so later tests see the contracted state.
        after.source_role = "unconfirmed"
        after.type = "unknown"
        s.add(after)
        s.commit()


# --- the widened PATCH, without which "unconfirmed" is permanent ---


def test_patch_can_now_confirm_a_source(client, imported):
    """Every imported row lands "unknown" and "unconfirmed" BY DESIGN. A
    provisional value nobody can confirm is not provisional, it is permanent —
    and the frontend is contracted to draw all 90 as visibly provisional."""
    row = next(r for r in sources(client) if r["type"] == "unknown")
    r = client.patch(
        f"/api/sources/{row['id']}",
        json={"type": "rss", "sourceRole": "aggregator", "category": "aggregators"},
        headers=tok(client),
    )
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "rss"
    assert r.json()["sourceRole"] == "aggregator"
    assert r.json()["category"] == "aggregators"

    restored = client.patch(
        f"/api/sources/{row['id']}",
        json={"type": "unknown", "sourceRole": "unconfirmed", "category": ""},
        headers=tok(client),
    )
    assert restored.status_code == 200


def test_type_is_validated_on_both_write_paths(client, imported):
    """"pdf" used to return 201 and be stored verbatim, and the crawler would
    then decide how to parse a source from an unvalidated string."""
    created = client.post(
        "/api/sources",
        json={"name": "bad type", "url": "https://example.invalid/x", "type": "pdf"},
        headers=tok(client),
    )
    assert created.status_code == 422, created.text

    row = sources(client)[0]
    patched = client.patch(
        f"/api/sources/{row['id']}", json={"type": "pdf"}, headers=tok(client)
    )
    assert patched.status_code == 422, patched.text


def test_source_role_is_validated_too(client, imported):
    row = sources(client)[0]
    r = client.patch(
        f"/api/sources/{row['id']}", json={"sourceRole": "maybe"}, headers=tok(client)
    )
    assert r.status_code == 422, r.text
