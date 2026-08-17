from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_session
from app.deps import current_user
from app.models import (
    BusinessUnit,
    Decision,
    Opportunity,
    OpportunityScore,
    Profile,
    User,
)
from app.schemas import OpportunityDetail, OpportunitySummary, ScoreOut
from app.scoring import (
    clears_bar,
    joint_pitch_note,
    joint_pitch_scores,
    unit_bars,
    viewer_scope,
)

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])

# The prototype's filter pills that are not unit names. Unit filtering is done
# by the viewer's own unit, so these are the cross-cutting ones.
FILTERS: dict[str, object] = {
    "everything": lambda o: True,
    "bid-now": lambda o: o.category == "bid",
    "watch": lambda o: o.category == "watch",
    "partnership": lambda o: o.category == "partnership",
    "bd-leads": lambda o: o.category == "bd",
    "international": lambda o: o.geography not in ("Nigeria", ""),
}


def _scores_by_opportunity(session: Session) -> dict[str, list[OpportunityScore]]:
    out: dict[str, list[OpportunityScore]] = {}
    for s in session.exec(select(OpportunityScore)).all():
        out.setdefault(s.opportunity_id, []).append(s)
    return out


@router.get("", response_model=list[OpportunitySummary])
def list_opportunities(
    filter: str = Query("everything"),
    business_unit_id: int | None = Query(
        None,
        description=(
            "Narrow to ONE unit. Honoured only for scope 'all' (admin, "
            "director), who otherwise see all five units mixed together with no "
            "way to focus. Ignored for scope 'own_units', where a unit pill "
            "would be redundant — their scoping is already implicit."
        ),
    ),
    include_weak: bool = Query(
        False,
        description=(
            "Include opportunities scoring BELOW the viewing unit's "
            "min_fit_percent. Hidden by default. The escape hatch matters: once "
            "the matching engine scores automatically, the weak rows are how "
            "somebody notices it scoring badly, and a permanent filter makes a "
            "broken engine look like a quiet week."
        ),
    ),
    limit: int | None = Query(None, ge=1, le=200),
    # camelCase spellings of the two parameters above, accepted so the trap
    # stops existing rather than being documented in four places. FastAPI
    # silently ignores an unrecognised query parameter, so ?businessUnitId=2
    # returned 200 with the FULL unfiltered list — a wrong answer that looks
    # right, which is the worst failure mode available. Every response body is
    # camelCase, so reaching for it is the natural mistake, and both agents made
    # it. Hidden from the schema: snake_case remains the documented spelling.
    businessUnitId: int | None = Query(None, include_in_schema=False),  # noqa: N803
    includeWeak: bool | None = Query(None, include_in_schema=False),  # noqa: N803
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Ranked opportunities.

    A user in a business unit sees only what scores for THEIR units — that is
    Michaella's rule. An admin or director sees everything, ranked by best fit
    across any unit, and may narrow with business_unit_id.

    Unit selection sits on its OWN axis, deliberately: `filter` stays a closed
    enum of cross-cutting categories, and the unit is a separate parameter.
    """
    if business_unit_id is None:
        business_unit_id = businessUnitId
    if includeWeak is not None:
        include_weak = include_weak or includeWeak

    key = filter.lower()
    if key not in FILTERS:
        raise HTTPException(400, f"unknown filter '{filter}'")

    if business_unit_id is not None and not session.get(BusinessUnit, business_unit_id):
        raise HTTPException(400, f"unknown business unit {business_unit_id}")

    scores = _scores_by_opportunity(session)
    # The role's SCOPE decides whether we filter at all; the user's units decide
    # to what. A director has scope "all" and is never filtered. A lead may
    # belong to SEVERAL units — one person heads both Takeout Media and TM
    # Foundation — so this is a set, not a single id.
    scoped, unit_ids = viewer_scope(user)

    # Scoped but belonging to nowhere sees nothing. Previously this fell through
    # as "unscoped" and showed them everything.
    if scoped and not unit_ids:
        return []

    # Only someone unscoped can narrow — a lead asking for another unit's list
    # is silently ignored rather than granted, since scope is not theirs to widen.
    if business_unit_id is not None and not scoped:
        unit_ids = [business_unit_id]
        scoped = True

    # Each unit's own bar for what is worth its attention. Only a unit-specific
    # view has a bar at all: an unscoped admin or director sees everything,
    # because they are overseeing rather than being pitched to. An admin who
    # deliberately narrows to one unit DOES get that unit's bar, so they can see
    # what a lead there actually sees.
    #
    # Missing profile means no bar (0), never the model default — a unit whose
    # profile row is absent should show everything rather than silently hide
    # everything on account of configuration that was never set.
    thresholds = unit_bars(session, unit_ids) if scoped and not include_weak else {}

    rows = []
    for opp in session.exec(select(Opportunity)).all():
        if not FILTERS[key](opp):
            continue

        opp_scores = scores.get(opp.id, [])
        mine = [s for s in opp_scores if s.business_unit_id in unit_ids]

        # Scoped: an opportunity none of your units has a score for is not
        # yours to see.
        if scoped and not mine:
            continue

        # Below the bar for every one of your units, so not worth your list.
        # Judged on YOUR OWN score, never the top one — an opportunity scoring
        # 82 for TM Foundation and 35 for Takeout Media is the Foundation's to
        # see and not Takeout's. Comparing against top_fit_percent here would
        # leak it straight back into the list this exists to keep clean.
        #
        # Someone in two units keeps it if EITHER unit clears its own bar,
        # which matches the existing rule that the better of their two fits
        # ranks it.
        if mine and not clears_bar(mine, thresholds):
            continue

        summary = OpportunitySummary.model_validate(opp)
        # Belonging to two units means the better of your two fits ranks it.
        summary.your_fit_percent = max((s.fit_percent for s in mine), default=None)
        summary.top_fit_percent = (
            max(s.fit_percent for s in opp_scores) if opp_scores else None
        )
        rows.append(summary)

    rows.sort(
        key=lambda r: (r.your_fit_percent if scoped else r.top_fit_percent) or 0,
        reverse=True,
    )
    return rows[:limit] if limit else rows


@router.get("/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity(
    opportunity_id: str,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """One opportunity, carrying EVERY unit's score — the detail page shows all
    five so you can see when a joint pitch makes sense."""
    opp = session.get(Opportunity, opportunity_id)
    if not opp:
        raise HTTPException(404, "opportunity not found")

    units = {u.id: u for u in session.exec(select(BusinessUnit)).all()}
    rows = session.exec(
        select(OpportunityScore).where(OpportunityScore.opportunity_id == opportunity_id)
    ).all()

    # Same row rule as the list: an opportunity none of your units scored is not
    # yours to open. Detail previously required only a valid token, so a Design
    # Teem lead whose list and priority actions were both empty could still
    # fetch any opportunity by its slug — and the slugs are guessable.
    #
    # This is NOT the fit threshold. A below-bar row is still openable by URL:
    # the bar is about attention, and this is about entitlement. What changed is
    # that having NO score in any of your units now means 404, matching the list.
    #
    # 404 rather than 403, and the same wording as a genuinely missing row, so
    # the response does not confirm that an id exists.
    scoped, unit_ids = viewer_scope(user)
    if scoped and not any(s.business_unit_id in unit_ids for s in rows):
        raise HTTPException(404, "opportunity not found")

    # model_dump() gives the columns only — validating the ORM object directly
    # would drag in the `scores` relationship, whose rows lack the unit name
    # and initials this schema needs.
    out = OpportunityDetail.model_validate(opp.model_dump())

    # The joint-pitch state is COMPUTED from the same rule /api/priority-actions
    # uses, not read from the stored column. That column defaults to False and
    # nothing has ever written it, so trusting it made this endpoint deny a
    # partnership the radar was announcing two clicks earlier.
    #
    # A stored True still wins, so the matching engine can assert a joint pitch
    # the simple threshold would miss once it exists. Today nothing sets it.
    strong = joint_pitch_scores(list(rows))
    strong_ids = {s.business_unit_id for s in strong}
    note = joint_pitch_note(strong, units)

    out.scores = sorted(
        (
            ScoreOut(
                business_unit_id=s.business_unit_id,
                business_unit_name=units[s.business_unit_id].name,
                initials=units[s.business_unit_id].initials,
                fit_percent=s.fit_percent,
                win_probability=s.win_probability,
                is_joint_pitch_candidate=(
                    s.is_joint_pitch_candidate or s.business_unit_id in strong_ids
                ),
                joint_pitch_note=(
                    s.joint_pitch_note
                    or (note if s.business_unit_id in strong_ids else "")
                ),
            )
            for s in rows
            if s.business_unit_id in units
        ),
        key=lambda s: s.fit_percent,
        reverse=True,
    )

    # NOT `unit_ids = user.unit_ids`, which shadowed the viewer_scope result
    # above with an identical-for-scoped-users, empty-for-admins value. It
    # happened to be harmless, and it sat directly above the decision lookup
    # that now depends on unit_ids meaning what viewer_scope said it means.
    if unit_ids:
        out.your_fit_percent = max(
            (s.fit_percent for s in out.scores if s.business_unit_id in unit_ids),
            default=None,
        )
    out.top_fit_percent = max((s.fit_percent for s in out.scores), default=None)

    # Scoped like /api/decisions, which was scoped in the same commit that left
    # this one open. The reason text is the sensitive half: a Reject requires a
    # reason and those are commercially candid by design, so a TM Foundation
    # lead was reading Takeout Media's justification for walking away — the
    # exact thing _log() was changed to prevent, still reachable one endpoint
    # over on eight seeded opportunities.
    #
    # It was also just wrong on its face. Showing TF "Rejected" for a call
    # Takeout made states that TF rejected it, on TF's own screen.
    #
    # An unattributed decision (no unit) is visible to anyone entitled to the
    # opportunity: it is a company-level call, and entitlement here already
    # follows the opportunity rather than the unit.
    decisions = session.exec(
        select(Decision)
        .where(Decision.opportunity_id == opportunity_id)
        .order_by(Decision.created_at.desc())
    ).all()
    if scoped:
        decisions = [
            d
            for d in decisions
            if d.business_unit_id is None or d.business_unit_id in unit_ids
        ]
    if decisions:
        out.decision = decisions[0].decision
        out.decision_reason = decisions[0].reason
    return out
