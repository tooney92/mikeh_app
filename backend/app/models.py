"""Tables from the design handoff's Data Model section.

String-list fields (approach, credentials, partners, themes) are stored as JSON
columns — SQLite has no array type and these are always read whole.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserBusinessUnit(SQLModel, table=True):
    """A user may belong to MORE THAN ONE unit.

    The client has one person leading both Takeout Media and TM Foundation, so
    a single foreign key on User cannot express membership: they would see one
    unit or all five, and neither is right. Defined first because BusinessUnit
    references it as a link model.
    """

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    business_unit_id: int = Field(foreign_key="businessunit.id", primary_key=True)


class BusinessUnit(SQLModel, table=True):
    """The five SBUs. Seeded from seed/units.json."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    initials: str = ""
    description: str = ""
    services: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    users: list["User"] = Relationship(
        back_populates="business_units", link_model=UserBusinessUnit
    )
    profile: "Profile" = Relationship(back_populates="business_unit")
    scores: list["OpportunityScore"] = Relationship(back_populates="business_unit")

    def __str__(self) -> str:
        # What the admin dropdown shows instead of "BusinessUnit object".
        return self.name


class RolePermission(SQLModel, table=True):
    """Join table — the editable grid of which role may do what."""

    role_id: int = Field(foreign_key="role.id", primary_key=True)
    permission_id: int = Field(foreign_key="permission.id", primary_key=True)


class Permission(SQLModel, table=True):
    """One `resource:action` pair. Generated from app/rbac.py, not hand-written."""

    id: int | None = Field(default=None, primary_key=True)
    resource: str = Field(index=True)
    action: str
    codename: str = Field(unique=True, index=True)  # "opportunity:read"

    roles: list["Role"] = Relationship(
        back_populates="permissions", link_model=RolePermission
    )

    def __str__(self) -> str:
        return self.codename


class Role(SQLModel, table=True):
    """What you may do (permissions) and which rows you see (scope).

    `scope` is NOT a permission — it filters the query. See app/rbac.py.
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)  # admin | director | lead | member
    label: str = ""
    scope: str = "own_units"  # all | own_units
    is_system: bool = False  # seeded; deleting one would be a bad day

    permissions: list[Permission] = Relationship(
        back_populates="roles", link_model=RolePermission
    )
    users: list["User"] = Relationship(back_populates="role")

    def grants(self, codename: str) -> bool:
        return any(p.codename == codename for p in self.permissions)

    def __str__(self) -> str:
        return self.label or self.name


class User(SQLModel, table=True):
    """A staff login.

    Two independent things decide what they get: their ROLE (what they may do)
    and their BUSINESS UNITS combined with the role's scope (which rows they
    see). A director belongs to no unit and has scope "all"; a lead belongs to
    one or more units and has scope "own_units".
    """

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str  # Argon2 — never the plain password
    full_name: str = ""
    role_id: int | None = Field(default=None, foreign_key="role.id", index=True)
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    last_login_at: datetime | None = None

    business_units: list[BusinessUnit] = Relationship(
        back_populates="users", link_model=UserBusinessUnit
    )
    role: Role | None = Relationship(back_populates="users")

    @property
    def permissions(self) -> set[str]:
        return {p.codename for p in self.role.permissions} if self.role else set()

    def can(self, codename: str) -> bool:
        return codename in self.permissions

    @property
    def sees_all_units(self) -> bool:
        return bool(self.role and self.role.scope == "all")

    @property
    def unit_ids(self) -> list[int]:
        """The units whose rows this user may see. Empty when scope is "all"."""
        return [] if self.sees_all_units else [u.id for u in self.business_units]

    def __str__(self) -> str:
        return self.username


class Opportunity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    category: str  # bid | watch | partnership | bd
    org: str
    title: str
    desc: str = ""

    # Fit lives in OpportunityScore — one row per business unit.
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

    scores: list["OpportunityScore"] = Relationship(
        back_populates="opportunity",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    def __str__(self) -> str:
        return self.title


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
    """One per business unit — what the matching engine scores against."""

    id: int | None = Field(default=None, primary_key=True)
    business_unit_id: int = Field(foreign_key="businessunit.id", unique=True, index=True)
    positioning: str = ""
    priorities: str = ""
    capabilities: str = ""
    credentials: str = ""
    never_show: str = ""

    # Below this fit, an opportunity is not worth this unit's attention and is
    # hidden from its list. Per unit rather than global: Takeout Media is shown
    # 12% and 15% matches today, while every score TM Foundation has is 55+, so
    # one number cannot suit both. An admin sets it in the back office.
    #
    # This filters the LIST only. Opportunity detail still shows every unit's
    # score whatever the threshold, because that is how a joint pitch is
    # spotted — you cannot notice another unit also fits if their score is
    # hidden from you.
    min_fit_percent: int = 40

    business_unit: BusinessUnit | None = Relationship(back_populates="profile")

    def __str__(self) -> str:
        return f"Profile #{self.id}"


class OpportunityScore(SQLModel, table=True):
    """How one opportunity scores for one business unit.

    Replaces the old fit_foundation / fit_takeout columns: with five units and
    joint pitches, fit is a row per unit, not a column per unit.
    """

    id: int | None = Field(default=None, primary_key=True)
    opportunity_id: str = Field(foreign_key="opportunity.id", index=True)
    business_unit_id: int = Field(foreign_key="businessunit.id", index=True)

    fit_percent: int = 0
    win_probability: int | None = None  # percent; None until the engine scores it
    is_joint_pitch_candidate: bool = False
    joint_pitch_note: str = ""

    scored_at: datetime = Field(default_factory=utcnow)

    opportunity: "Opportunity" = Relationship(back_populates="scores")
    business_unit: BusinessUnit | None = Relationship(back_populates="scores")

    __table_args__ = (
        UniqueConstraint(
            "opportunity_id", "business_unit_id", name="uq_score_opportunity_unit"
        ),
    )


class Source(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    # html | rss | json | unknown. "unknown" means nobody has looked, and it
    # exists so an unexamined source cannot masquerade as an examined one — the
    # client's spreadsheet has no column saying how a site publishes, so all 81
    # imported rows land here rather than silently claiming "html".
    type: str = "html"
    category: str = ""
    # takeout | foundation | both. STALE: predates the five-unit model and
    # cannot express Design Teem, Ingene Studios or TM Labs. Imported rows carry
    # "both" as a knowingly temporary placeholder, not as a classification.
    scope: str = "both"
    url: str
    active: bool = True
    last_status: str | None = None
    last_status_ok: bool | None = None
    last_checked_at: datetime | None = None
    # seed | client_import — where this row came from, so the client can see her
    # own list arrived intact and we can tell her rows from ours.
    provenance: str = "seed"
    # aggregator | issuer | unconfirmed. A DISCOVERY PLATFORM lists other
    # people's opportunities; an ISSUER publishes its own, and the crawler has
    # to chase links out of the first rather than parse postings on it. A string
    # enum rather than a nullable boolean because null is falsy: `if
    # (isAggregator)` would render every unconfirmed row as "not an aggregator".
    source_role: str = "unconfirmed"
    # The client's own words from her spreadsheet, preserved verbatim and never
    # parsed. All 81 values are distinct and none is blank, so there is no
    # vocabulary to derive — whoever builds the exclusion rules must match TEXT.
    client_opportunity_type: str = ""
    client_sectors: str = ""


class Decision(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    opportunity_id: str = Field(foreign_key="opportunity.id", index=True)
    # Which unit made the call — the same opportunity can be pursued by one
    # unit and rejected by another.
    business_unit_id: int | None = Field(
        default=None, foreign_key="businessunit.id", index=True
    )
    user_id: int | None = Field(default=None, foreign_key="user.id")
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
