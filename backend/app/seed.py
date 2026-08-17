"""Load the design-handoff sample data into SQLite.

Idempotent: skips any table that already has rows, so restarting the app never
duplicates seed records. Run standalone with `python -m app.seed --reset`.
"""

import json
import os
import secrets
from pathlib import Path

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import (
    BusinessUnit,
    Opportunity,
    OpportunityScore,
    Organisation,
    Profile,
    Role,
    Source,
    User,
)
from app.rbac import sync_rbac
from app.security import hash_password

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
    """Load the sample opportunities and convert their two fit numbers to scores.

    The bundle's opportunities.json predates the five-unit model: every record
    carries only fitFoundation and fitTakeout. So TM Foundation and Takeout
    Media get real seeded scores and the other three units get none — they stay
    empty until the matching engine runs. That is honest rather than inventing
    numbers for units the sample data says nothing about.
    """
    if session.exec(select(Opportunity)).first():
        return 0

    units = {u.name: u.id for u in session.exec(select(BusinessUnit)).all()}
    rows = _read("opportunities.json")
    for r in rows:
        session.add(
            Opportunity(
                id=r["id"],
                category=r["category"],
                org=r["org"],
                title=r["title"],
                desc=r.get("desc", ""),
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

        for unit_name, key in (
            ("TM Foundation", "fitFoundation"),
            ("Takeout Media", "fitTakeout"),
        ):
            if key in r and unit_name in units:
                session.add(
                    OpportunityScore(
                        opportunity_id=r["id"],
                        business_unit_id=units[unit_name],
                        fit_percent=r[key],
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
    """One profile row per business unit — five, not two.

    profiles.json only describes Takeout Media and TM Foundation, so the other
    three units get an EMPTY profile seeded from their units.json description.
    Empty is the correct state: the matching engine cannot score a unit until
    somebody fills its profile in on the Profile & Sources screen.
    """
    data = _read("profiles.json")
    written = {
        "Takeout Media": data.get("takeoutMedia", {}),
        "TM Foundation": data.get("tmFoundation", {}),
    }

    profiles = 0
    if not session.exec(select(Profile)).first():
        for unit in session.exec(select(BusinessUnit)).all():
            p = written.get(unit.name, {})
            session.add(
                Profile(
                    business_unit_id=unit.id,
                    positioning=p.get("positioning", unit.description),
                    priorities=p.get("priorities", ""),
                    capabilities=p.get("capabilities", "\n".join(unit.services)),
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


def seed_business_units(session: Session) -> int:
    """The five SBUs, from the design bundle's units.json."""
    if session.exec(select(BusinessUnit)).first():
        return 0
    rows = _read("units.json")
    for r in rows:
        session.add(
            BusinessUnit(
                name=r["name"],
                initials=r.get("initials", ""),
                description=r.get("description", ""),
                services=r.get("services", []),
            )
        )
    return len(rows)


def seed_admin_user(session: Session) -> str | None:
    """Create the first admin, since there is no signup page.

    Credentials come from TM_ADMIN_EMAIL / TM_ADMIN_PASSWORD. With no password
    set we generate one and return it so the caller can print it ONCE — it is
    hashed on the way in and is not recoverable afterwards.
    """
    if session.exec(select(User)).first():
        return None

    email = os.environ.get("TM_ADMIN_EMAIL", "admin@tmglobal.local").lower()
    password = os.environ.get("TM_ADMIN_PASSWORD")
    generated = None
    if not password:
        password = secrets.token_urlsafe(12)
        generated = password

    admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
    session.add(
        User(
            username=os.environ.get("TM_ADMIN_USERNAME", "admin"),
            email=email,
            hashed_password=hash_password(password),
            full_name="Administrator",
            role_id=admin_role.id if admin_role else None,
        )
    )
    return generated


MIN_TEST_PASSWORD_LENGTH = 12

# Four accounts whose only job is to prove the permission rules actually bite.
# The admin cannot do it: it holds all 40 codenames and belongs to no unit, so
# every menu item renders and every list is unfiltered — testing scope against
# it proves nothing by construction. `lead.dual` is the important one; the
# client really does have a person leading both Takeout Media and TM Foundation,
# and the union-of-units behaviour has no other way to be exercised from the UI.
TEST_ACCOUNTS = (
    {
        "username": "director",
        "email": "director@tmglobal.local",
        "full_name": "Test Director",
        "role": "director",
        "units": (),  # scope "all" — belongs to no unit by design
    },
    {
        "username": "lead.takeout",
        "email": "lead.takeout@tmglobal.local",
        "full_name": "Test Lead — Takeout Media",
        "role": "lead",
        "units": ("Takeout Media",),
    },
    {
        "username": "lead.dual",
        "email": "lead.dual@tmglobal.local",
        "full_name": "Test Lead — Takeout Media and TM Foundation",
        "role": "lead",
        "units": ("Takeout Media", "TM Foundation"),
    },
    {
        "username": "member.foundation",
        "email": "member.foundation@tmglobal.local",
        "full_name": "Test Member — TM Foundation",
        "role": "member",
        "units": ("TM Foundation",),
    },
)


def seed_test_accounts(session: Session) -> list[str]:
    """Create the four scoping accounts. OPT-IN: set TM_TEST_PASSWORD to enable.

    These were opt-OUT, created on every boot with a password hard-coded in this
    file. One of them is a director with scope "all" and grants over every
    opportunity, source, profile, decision and organisation. Since the opt-out
    variable appeared in no documentation, deploying by the README would have
    shipped four logins whose password is readable in the source.

    So enabling them is now a deliberate act: set TM_TEST_PASSWORD and they are
    created with it; leave it unset and they do not exist. There is no default
    password, because a default password IS the vulnerability.

    Idempotent per username, so a rerun adds only what is missing. They share
    one password: they exist to be logged into by whoever is testing, and a
    per-account secret would be ceremony without a benefit.

    Both units chosen here have seeded scores. A lead over Design Teem, Ingene
    Studios or TM Labs would see an empty list and prove nothing about filtering,
    because there is nothing to filter.
    """
    password = os.environ.get("TM_TEST_PASSWORD")
    if not password:
        return []
    if len(password) < MIN_TEST_PASSWORD_LENGTH:
        raise ValueError(
            f"TM_TEST_PASSWORD must be at least {MIN_TEST_PASSWORD_LENGTH} "
            "characters — these accounts hold real grants."
        )
    roles = {r.name: r for r in session.exec(select(Role)).all()}
    units = {u.name: u for u in session.exec(select(BusinessUnit)).all()}

    created: list[str] = []
    for spec in TEST_ACCOUNTS:
        exists = session.exec(
            select(User).where(User.username == spec["username"])
        ).first()
        if exists:
            continue

        role = roles.get(spec["role"])
        user = User(
            username=spec["username"],
            email=spec["email"],
            hashed_password=hash_password(password),
            full_name=spec["full_name"],
            role_id=role.id if role else None,
        )
        user.business_units = [units[n] for n in spec["units"] if n in units]
        session.add(user)
        created.append(spec["username"])

    return created


def run() -> dict[str, int]:
    init_db()
    with Session(engine) as session:
        rbac = sync_rbac(session)
        session.flush()
        units = seed_business_units(session)
        opps = seed_opportunities(session)
        srcs = seed_sources(session)
        profiles, orgs = seed_profiles_and_orgs(session)
        generated_pw = seed_admin_user(session)
        # Strictly after the admin: seed_admin_user bails if ANY user exists,
        # and autoflush would show it these four before they are committed.
        test_users = seed_test_accounts(session)
        session.commit()

    if generated_pw:
        print(
            "\n" + "=" * 62,
            "FIRST-RUN ADMIN ACCOUNT CREATED",
            f"  username: {os.environ.get('TM_ADMIN_USERNAME', 'admin')}",
            f"  password: {generated_pw}",
            "Shown once and never again — save it now, then change it.",
            "Set TM_ADMIN_EMAIL / TM_ADMIN_PASSWORD to choose your own.",
            "=" * 62 + "\n",
            sep="\n",
        )

    return {
        "permissions": rbac["permissions"],
        "roles": rbac["roles"],
        "business_units": units,
        "opportunities": opps,
        "sources": srcs,
        "profiles": profiles,
        "organisations": orgs,
        "test_accounts": len(test_users),
    }


if __name__ == "__main__":
    import sys

    from app.db import DB_PATH

    if "--reset" in sys.argv and DB_PATH.exists():
        DB_PATH.unlink()
        print(f"removed {DB_PATH}")
    print(run())
