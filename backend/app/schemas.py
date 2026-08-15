"""Wire shapes.

The API speaks camelCase: the design bundle's own JSON (opportunities.json,
profiles.json, sources.json) is camelCase and the frontend is TypeScript, so
this keeps one convention across the boundary. Columns stay snake_case.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class OpportunitySummary(CamelModel):
    id: str
    category: str
    org: str
    title: str
    desc: str
    fit_foundation: int
    fit_takeout: int
    value: str
    deadline: str
    relevance: str
    beneficiary: str
    geography: str
    source: str


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
    id: str
    name: str
    positioning: str
    priorities: str
    capabilities: str
    credentials: str
    never_show: str


class ProfileUpdate(CamelModel):
    positioning: str | None = None
    priorities: str | None = None
    capabilities: str | None = None
    credentials: str | None = None
    never_show: str | None = None


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


class DecisionOut(CamelModel):
    id: int
    opportunity_id: str
    decision: str
    reason: str | None
    created_at: datetime
    opportunity_title: str | None = None
    fit_foundation: int | None = None


class LearningStats(CamelModel):
    decisions_logged: int
    avg_foundation_fit_pursued: float | None
    most_backed_theme: str | None
    most_common_rejection: str | None
    breakdown: dict[str, int]
    log: list[DecisionOut]


class RadarStats(CamelModel):
    opportunities_worth_pursuing: int
    organisations_worth_approaching: int
    emerging_trends: int
    competitor_movements: int
    potential_partnerships: int
    estimated_pipeline_value: str


class ScanStatus(CamelModel):
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    sources_swept: int = 0
    scored: int = 0
