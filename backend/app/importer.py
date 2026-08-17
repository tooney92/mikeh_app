"""Import the client's 81 opportunity platforms, MERGING with what is here.

The one rule that must not be got wrong: merge, do not replace. Nine of the
fifteen seeded sources have no exact counterpart in her spreadsheet, and a
wholesale replace destroys them — including the only JSON source we have.

Contracted in todo 4 v6. The numbers below were verified against the file by
both seats independently before the contract locked:

    81 rows in the sheet, 81 distinct URLs, 73 distinct domains
    15 seeded sources, 11 overlapping DOMAINS, 6 exact URL matches
    90 rows after the merge   (15 + 81 - 6)
    77 rows if keyed on domain instead — the failure this module exists to avoid
"""

import json
from pathlib import Path
from urllib.parse import urlsplit

from sqlmodel import Session, select

from app.models import Source

CLIENT_SOURCES = Path(__file__).resolve().parent.parent / "seed" / "client_sources.json"


def merge_key(url: str) -> str:
    """The contracted merge key: scheme-insensitive HOST plus PATH.

    NOT the registrable domain, and this is the whole point rather than a
    detail. Our search.worldbank.org/api/v2/procnotices and her
    projects.worldbank.org/en/projects-operations/opportunities are the same
    ORGANISATION at different hosts. Key on the domain and they collapse into
    one row; the survivor is her html row, and the only JSON source in the
    system — the only one the crawler can read without HTML parsing —
    disappears into a record that looks perfectly healthy. Nothing errors,
    nothing looks missing.

    Path matters for the same reason downward: opportunitydesk.org/feed and
    opportunitydesk.org are two different pages and we keep BOTH deliberately,
    because the RSS feed is what a crawler wants and the landing page is not.
    Domain keying would eat the feed and leave the page — exactly backwards.

    `www.` is stripped and a trailing slash ignored, because those are the same
    page by any reading. Nothing else is normalised.
    """
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    return f"{host}{parts.path.rstrip('/')}"


def load_client_rows(path: Path = CLIENT_SOURCES) -> list[dict]:
    """Her spreadsheet, converted once to JSON and committed.

    Converted rather than read live so the import has no xlsx dependency at
    runtime and the data is reviewable in git — the same pattern as
    seed/sources.json.
    """
    return json.loads(path.read_text())


def import_client_sources(session: Session, rows: list[dict] | None = None) -> dict:
    """Merge her list into the sources table. Safe to re-run.

    Returns a summary rather than printing, so the caller decides what to say.
    """
    rows = load_client_rows() if rows is None else rows

    existing = {merge_key(s.url): s for s in session.exec(select(Source)).all()}
    created = updated = 0

    for row in rows:
        key = merge_key(row["url"])
        source = existing.get(key)

        if source is None:
            source = Source(
                name=row["name"],
                url=row["url"],
                # NOT "html". Her sheet has four columns and none of them says
                # how a site publishes, so claiming a format here would be
                # inventing data about a site nobody has opened — and `type`
                # decides how the crawler PARSES, so a wrong guess is expensive.
                type="unknown",
                category="",
                # Knowingly temporary. The vocabulary cannot express three of
                # the five units; replacing it is a model question for a human.
                scope="both",
                provenance="client_import",
                # Her sheet has no aggregator column either.
                source_role="unconfirmed",
                client_opportunity_type=row["clientOpportunityType"],
                client_sectors=row["clientSectors"],
            )
            session.add(source)
            existing[key] = source
            created += 1
            continue

        # An existing row she also lists. It reconciles to ONE record, and it
        # becomes hers: her list is the reason we know she wants it watched.
        source.provenance = "client_import"
        source.client_opportunity_type = row["clientOpportunityType"]
        source.client_sectors = row["clientSectors"]

        # A HUMAN'S CLASSIFICATION SURVIVES A RE-IMPORT. Only still-unexamined
        # values may be rewritten, and today the import has nothing better to
        # offer anyway. Without this guard the second run silently undoes
        # somebody's work — and a re-run is exactly the operation people perform
        # casually, expecting it to be a no-op.
        #
        # Deliberately does NOT touch name, url, active or the last_* columns:
        # ours are more specific (opportunitydesk.org/feed over the landing
        # page) and the status columns are observations, not settings.
        updated += 1

    session.commit()
    total = len(session.exec(select(Source)).all())
    return {
        "created": created,
        "reconciled": updated,
        "total": total,
        "client_rows": len(rows),
    }


if __name__ == "__main__":  # pragma: no cover - operator entry point
    # `uv run python -m app.importer` — re-run the merge by hand. Safe: it
    # creates nothing that already exists and never resets a classification
    # somebody has made.
    from app.db import engine

    with Session(engine) as _s:
        print(import_client_sources(_s))
