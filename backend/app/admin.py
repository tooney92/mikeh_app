"""Admin dashboard at /admin — the Django-admin-shaped piece FastAPI omits.

sqladmin generates list/create/edit/delete over the SQLModel tables. It talks to
the database directly, not through the API, so it is a back-office tool: no auth
on it yet (see README), do not expose it on staging as-is.
"""

from fastapi import FastAPI
from sqladmin import Admin, ModelView

from app.db import engine
from app.models import (
    Decision,
    IndustrySignal,
    Opportunity,
    Organisation,
    Profile,
    ScanRun,
    Source,
    WeeklyReport,
)


class OpportunityAdmin(ModelView, model=Opportunity):
    name_plural = "Opportunities"
    icon = "fa-solid fa-bullseye"
    column_list = [
        Opportunity.id,
        Opportunity.title,
        Opportunity.org,
        Opportunity.category,
        Opportunity.fit_foundation,
        Opportunity.fit_takeout,
        Opportunity.relevance,
        Opportunity.deadline,
    ]
    column_searchable_list = [Opportunity.title, Opportunity.org]
    column_sortable_list = [Opportunity.fit_foundation, Opportunity.fit_takeout]
    column_default_sort = (Opportunity.fit_foundation, True)


class OrganisationAdmin(ModelView, model=Organisation):
    name_plural = "Organisations"
    icon = "fa-solid fa-building"
    column_list = [
        Organisation.id,
        Organisation.name,
        Organisation.sector,
        Organisation.priority,
        Organisation.last_updated,
    ]
    column_searchable_list = [Organisation.name]


class ProfileAdmin(ModelView, model=Profile):
    name_plural = "Profiles"
    icon = "fa-solid fa-id-card"
    column_list = [Profile.id, Profile.name]
    can_create = False  # exactly two rows, by design
    can_delete = False


class SourceAdmin(ModelView, model=Source):
    name_plural = "Sources"
    icon = "fa-solid fa-rss"
    column_list = [
        Source.id,
        Source.name,
        Source.type,
        Source.category,
        Source.scope,
        Source.active,
        Source.last_status,
        Source.last_checked_at,
    ]
    column_searchable_list = [Source.name, Source.url]
    column_sortable_list = [Source.name, Source.active]


class DecisionAdmin(ModelView, model=Decision):
    name_plural = "Decisions"
    icon = "fa-solid fa-gavel"
    column_list = [
        Decision.id,
        Decision.opportunity_id,
        Decision.decision,
        Decision.reason,
        Decision.created_at,
    ]
    column_default_sort = (Decision.created_at, True)


class IndustrySignalAdmin(ModelView, model=IndustrySignal):
    name_plural = "Industry signals"
    icon = "fa-solid fa-chart-line"
    column_list = [
        IndustrySignal.id,
        IndustrySignal.sector,
        IndustrySignal.direction,
        IndustrySignal.text,
        IndustrySignal.created_at,
    ]


class WeeklyReportAdmin(ModelView, model=WeeklyReport):
    name_plural = "Weekly reports"
    icon = "fa-solid fa-newspaper"
    column_list = [
        WeeklyReport.id,
        WeeklyReport.week_of,
        WeeklyReport.opp_count,
        WeeklyReport.source_count,
        WeeklyReport.generated_at,
    ]


class ScanRunAdmin(ModelView, model=ScanRun):
    name_plural = "Scan runs"
    icon = "fa-solid fa-magnifying-glass"
    column_list = [
        ScanRun.id,
        ScanRun.status,
        ScanRun.started_at,
        ScanRun.finished_at,
        ScanRun.sources_swept,
        ScanRun.scored,
    ]
    column_default_sort = (ScanRun.started_at, True)
    can_create = False  # jobs are started via POST /api/scan
    can_edit = False


def mount_admin(app: FastAPI) -> Admin:
    admin = Admin(app, engine, title="TM Global BI")
    for view in (
        OpportunityAdmin,
        OrganisationAdmin,
        ProfileAdmin,
        SourceAdmin,
        DecisionAdmin,
        IndustrySignalAdmin,
        WeeklyReportAdmin,
        ScanRunAdmin,
    ):
        admin.add_view(view)
    return admin
