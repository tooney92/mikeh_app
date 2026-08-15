"""Tables from the design handoff's Data Model section.

String-list fields (approach, credentials, partners, themes) are stored as JSON
columns — SQLite has no array type and these are always read whole.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Opportunity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    category: str  # bid | watch | partnership | bd
    org: str
    title: str
    desc: str = ""

    fit_foundation: int = 0
    fit_takeout: int = 0
    value: str = "unconfirmed"
    deadline: str = "No deadline stated"
    relevance: str = "MEDIUM"  # HIGH | MEDIUM | LOW

    beneficiary: str = ""
    geography: str = ""
    source: str = ""
    source_url: str | None = None

    why_it_matters: str = ""
    why_now: str = ""
    positioning: str = ""
    recommendation: str = ""

    approach: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    credentials: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    partners: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    themes: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=utcnow)


class Organisation(SQLModel, table=True):
    """Tracked client/partner orgs — separate from the two scoring profiles."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    sector: str = ""
    signal: str = ""
    upsell_angle: str = ""
    priority: str = "monitor"  # approach_now | monitor
    last_updated: datetime = Field(default_factory=utcnow)


class Profile(SQLModel, table=True):
    """Exactly two rows: Takeout Media, TM Foundation."""

    id: str = Field(primary_key=True)  # takeout | foundation
    name: str
    positioning: str = ""
    priorities: str = ""
    capabilities: str = ""
    credentials: str = ""
    never_show: str = ""


class Source(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    type: str = "html"  # html | rss | json
    category: str = ""
    scope: str = "both"  # takeout | foundation | both
    url: str
    active: bool = True
    last_status: str | None = None
    last_status_ok: bool | None = None
    last_checked_at: datetime | None = None


class Decision(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    opportunity_id: str = Field(foreign_key="opportunity.id", index=True)
    decision: str  # Pursue | Partner | Watch | Reject
    reason: str | None = None  # only for Reject
    created_at: datetime = Field(default_factory=utcnow)


class IndustrySignal(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sector: str = Field(index=True)
    direction: str = "WATCH"  # UP | WATCH | DOWN
    text: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class WeeklyReport(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    week_of: str  # ISO date of the Monday
    opp_count: int = 0
    source_count: int = 0
    generated_at: datetime = Field(default_factory=utcnow)
    content: dict = Field(default_factory=dict, sa_column=Column(JSON))


class ScanRun(SQLModel, table=True):
    """Status of the crawl/match job the Radar's 'Run scan' button triggers."""

    id: int | None = Field(default=None, primary_key=True)
    status: str = "idle"  # running | complete | failed
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    sources_swept: int = 0
    scored: int = 0
