"""Wire shapes.

The API speaks camelCase: the design bundle's own JSON (opportunities.json,
profiles.json, sources.json) is camelCase and the frontend is TypeScript, so
this keeps one convention across the boundary. Columns stay snake_case.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class LoginRequest(CamelModel):
    """`identifier` takes either the username or the email — we match whichever."""

    identifier: str
    password: str


class TokenOut(CamelModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RoleOut(CamelModel):
    id: int
    name: str
    label: str
    scope: str  # all | own_unit
    is_system: bool = False
    permissions: list[str] = []


class UnitBrief(CamelModel):
    id: int
    name: str
    initials: str


class UserOut(CamelModel):
    id: int
    username: str
    email: str
    full_name: str
    # A user can belong to more than one unit — the client has a person leading
    # both Takeout Media and TM Foundation. Empty for a director or admin, who
    # see every unit by scope rather than by membership.
    business_units: list[UnitBrief] = []
    role: RoleOut | None = None
    # Flat codename list, so the frontend asks can('source:update') rather than
    # branching on the role's name.
    permissions: list[str] = []
    is_active: bool
    last_login_at: datetime | None = None


class ChangePasswordRequest(CamelModel):
    current_password: str
    new_password: str


class ResetPasswordRequest(CamelModel):
    new_password: str


class BusinessUnitOut(CamelModel):
    id: int
    name: str
    initials: str
    description: str
    services: list[str]


class ScoreOut(CamelModel):
    """One unit's score on one opportunity."""

    business_unit_id: int
    business_unit_name: str
    initials: str
    fit_percent: int
    win_probability: int | None = None
    is_joint_pitch_candidate: bool = False
    joint_pitch_note: str = ""


class OpportunitySummary(CamelModel):
    id: str
    category: str
    org: str
    title: str
    desc: str
    value: str
    deadline: str
    relevance: str
    beneficiary: str
    geography: str
    source: str
    # The viewer's own unit's fit, for the list row's stat panel. Null for an
    # admin, who has no unit of their own.
    your_fit_percent: int | None = None
    top_fit_percent: int | None = None


class OpportunityDetail(OpportunitySummary):
    source_url: str | None
    why_it_matters: str
    why_now: str
    positioning: str
    recommendation: str
    approach: list[str]
    credentials: list[str]
    partners: list[str]
    themes: list[str]
    # All five units' scores — the detail page shows every one.
    scores: list[ScoreOut] = []
    decision: str | None = None
    decision_reason: str | None = None


class OrganisationOut(CamelModel):
    id: int
    name: str
    sector: str
    signal: str
    upsell_angle: str
    priority: str


class ProfileOut(CamelModel):
    id: int
    business_unit_id: int
    business_unit_name: str
    initials: str
    positioning: str
    priorities: str
    capabilities: str
    credentials: str
    never_show: str
    min_fit_percent: int


class ProfileUpdate(CamelModel):
    positioning: str | None = None
    priorities: str | None = None
    capabilities: str | None = None
    credentials: str | None = None
    never_show: str | None = None
    min_fit_percent: int | None = Field(default=None, ge=0, le=100)


class SourceOut(CamelModel):
    id: int
    name: str
    type: str
    category: str
    scope: str
    url: str
    active: bool
    last_status: str | None
    last_status_ok: bool | None
    last_checked_at: datetime | None


class SourceCreate(CamelModel):
    name: str
    url: str
    type: str = "html"
    category: str = ""
    scope: str = "both"


class SourceUpdate(CamelModel):
    active: bool | None = None
    name: str | None = None
    url: str | None = None


class DecisionCreate(CamelModel):
    opportunity_id: str
    decision: str
    reason: str | None = None
    business_unit_id: int | None = None


class DecisionOut(CamelModel):
    id: int
    opportunity_id: str
    business_unit_id: int | None = None
    decision: str
    reason: str | None
    created_at: datetime
    opportunity_title: str | None = None
    fit_percent: int | None = None


class LearningStats(CamelModel):
    decisions_logged: int
    avg_pursued_fit_percent: float | None
    most_backed_theme: str | None
    most_common_rejection: str | None
    breakdown: dict[str, int]
    log: list[DecisionOut]


class PriorityAction(CamelModel):
    """A row in the Radar's "This week's priority actions" list."""

    type: str  # Opportunity | Organisation | Industry | Partnership | Competitor
    title: str
    description: str
    opportunity_id: str | None = None  # set when the row links to one


class RadarStats(CamelModel):
    opportunities_worth_pursuing: int
    organisations_worth_approaching: int
    emerging_trends: int
    competitor_movements: int
    potential_partnerships: int
    # A NUMBER, not a formatted string. Rendering money (naira glyph, M vs B,
    # thousands separators) is a frontend decision and stays there.
    estimated_pipeline_value: int  # whole naira
    estimated_pipeline_currency: str = "NGN"


class ScanStatus(CamelModel):
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    sources_swept: int = 0
    scored: int = 0
