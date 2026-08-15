"""Load the design-handoff sample data into SQLite.

Idempotent: skips any table that already has rows, so restarting the app never
duplicates seed records. Run standalone with `python -m app.seed --reset`.
"""

import json
from pathlib import Path

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import Opportunity, Organisation, Profile, Source

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"

# Sector labels for the tracked orgs — the handoff lists the orgs but the
# sector sublabel only appears in the prototype's table, so it is set here.
ORG_SECTORS = {
    "UNDP Nigeria": "Development / Multilateral",
    "World Bank": "Development / Multilateral",
    "Jaiz Bank": "Financial Services",
    "TAJBank": "Financial Services",
    "Standards Organisation of Nigeria (SON)": "Public Sector",
    "Industrial Training Fund (ITF)": "Public Sector",
    "NNPC": "Energy / Public Sector",
    "GIZ": "Development / Multilateral",
    "Federal Ministry of Art, Culture, Tourism and Creative Economy": "Public Sector",
    "National Council for Arts and Culture (NCAC)": "Public Sector",
}


def _read(name: str):
    return json.loads((SEED_DIR / name).read_text())


def seed_opportunities(session: Session) -> int:
    if session.exec(select(Opportunity)).first():
        return 0
    rows = _read("opportunities.json")
    for r in rows:
        session.add(
            Opportunity(
                id=r["id"],
                category=r["category"],
                org=r["org"],
                title=r["title"],
                desc=r.get("desc", ""),
                fit_foundation=r.get("fitFoundation", 0),
                fit_takeout=r.get("fitTakeout", 0),
                value=r.get("value", "unconfirmed"),
                deadline=r.get("deadline", "No deadline stated"),
                relevance=r.get("relevance", "MEDIUM"),
                beneficiary=r.get("beneficiary", ""),
                geography=r.get("geography", ""),
                source=r.get("source", ""),
                recommendation=r.get("recommendation", ""),
                credentials=r.get("credentials", []),
                partners=r.get("partners", []),
                themes=r.get("themes", []),
                approach=r.get("approach", []),
            )
        )
    return len(rows)


def seed_sources(session: Session) -> int:
    if session.exec(select(Source)).first():
        return 0
    rows = _read("sources.json")
    for r in rows:
        session.add(
            Source(
                name=r["name"],
                type=r.get("type", "html"),
                category=r.get("category", ""),
                scope=r.get("scope", "both"),
                url=r["url"],
                active=True,
                last_status=r.get("lastStatus"),
                last_status_ok=r.get("lastStatusOk"),
            )
        )
    return len(rows)


def seed_profiles_and_orgs(session: Session) -> tuple[int, int]:
    data = _read("profiles.json")
    profiles = 0
    if not session.exec(select(Profile)).first():
        for key, pid in (("takeoutMedia", "takeout"), ("tmFoundation", "foundation")):
            p = data[key]
            session.add(
                Profile(
                    id=pid,
                    name=p["name"],
                    positioning=p.get("positioning", ""),
                    priorities=p.get("priorities", ""),
                    capabilities=p.get("capabilities", ""),
                    credentials=p.get("credentials", ""),
                    never_show=p.get("neverShow", ""),
                )
            )
            profiles += 1

    orgs = 0
    if not session.exec(select(Organisation)).first():
        for name in data.get("trackedOrganisations", []):
            session.add(Organisation(name=name, sector=ORG_SECTORS.get(name, "")))
            orgs += 1

    return profiles, orgs


def run() -> dict[str, int]:
    init_db()
    with Session(engine) as session:
        opps = seed_opportunities(session)
        srcs = seed_sources(session)
        profiles, orgs = seed_profiles_and_orgs(session)
        session.commit()
    return {
        "opportunities": opps,
        "sources": srcs,
        "profiles": profiles,
        "organisations": orgs,
    }


if __name__ == "__main__":
    import sys

    from app.db import DB_PATH

    if "--reset" in sys.argv and DB_PATH.exists():
        DB_PATH.unlink()
        print(f"removed {DB_PATH}")
    print(run())
