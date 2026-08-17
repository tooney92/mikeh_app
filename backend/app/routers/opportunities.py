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
from app.scoring import clears_bar, joint_pitch_note, joint_pitch_scores, unit_bars

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
    unit_ids = user.unit_ids
    scoped = bool(unit_ids)

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

    unit_ids = user.unit_ids
    if unit_ids:
        out.your_fit_percent = max(
            (s.fit_percent for s in out.scores if s.business_unit_id in unit_ids),
            default=None,
        )
    out.top_fit_percent = max((s.fit_percent for s in out.scores), default=None)

    latest = session.exec(
        select(Decision)
        .where(Decision.opportunity_id == opportunity_id)
        .order_by(Decision.created_at.desc())
    ).first()
    if latest:
        out.decision = latest.decision
        out.decision_reason = latest.reason
    return out
