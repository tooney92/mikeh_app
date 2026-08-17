from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.db import get_session
from app.deps import current_user
from app.models import (
    IndustrySignal,
    Opportunity,
    OpportunityScore,
    Organisation,
    User,
)
from app.schemas import RadarStats
from app.scoring import clears_bar, unit_bars

router = APIRouter(prefix="/api", tags=["radar"])

# The "$" to "$$$$" bands converted to whole naira. These figures are OUR
# guess, not the client's — see QUESTIONS.md, she has been asked what a small,
# medium, large and very large opportunity is worth to her.
VALUE_BANDS = {
    "$": 25_000_000,
    "$$": 75_000_000,
    "$$$": 200_000_000,
    "$$$$": 500_000_000,
}


@router.get("/radar", response_model=RadarStats)
def radar(
    include_weak: bool = Query(
        False,
        description=(
            "Count opportunities below the viewing unit's min_fit_percent too. "
            "Matches the same parameter on /api/opportunities so the tiles and "
            "the list can be asked the same question."
        ),
    ),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """The stat-strip counts, computed from what THIS USER can see.

    Previously this counted every opportunity in the database regardless of who
    asked — the signed-in user was accepted and then discarded. That was already
    wrong for a lead, and the per-unit fit bar made it visible: the tiles said
    eight worth pursuing while the list underneath showed three. A dashboard
    contradicting the list on the same refresh is worse than either number.

    So the same visibility rules the list uses apply here: your units' rows
    only, and only those clearing your units' bars. An admin or director has no
    unit and is unscoped, so they still see totals across everything.
    """
    unit_ids = user.unit_ids
    scoped = bool(unit_ids)
    bars = unit_bars(session, unit_ids) if scoped and not include_weak else {}

    all_opps = session.exec(select(Opportunity)).all()
    if scoped:
        by_opp: dict[str, list[OpportunityScore]] = {}
        for s in session.exec(select(OpportunityScore)).all():
            by_opp.setdefault(s.opportunity_id, []).append(s)
        opps = []
        for o in all_opps:
            mine = [s for s in by_opp.get(o.id, []) if s.business_unit_id in unit_ids]
            if not mine or not clears_bar(mine, bars):
                continue
            opps.append(o)
    else:
        opps = list(all_opps)

    orgs = session.exec(select(Organisation)).all()
    signals = session.exec(select(IndustrySignal)).all()

    pipeline = sum(VALUE_BANDS.get(o.value, 0) for o in opps)

    return RadarStats(
        opportunities_worth_pursuing=len([o for o in opps if o.relevance == "HIGH"]),
        organisations_worth_approaching=len(
            [o for o in orgs if o.priority == "approach_now"]
        ),
        emerging_trends=len([s for s in signals if s.direction == "UP"]),
        competitor_movements=len([s for s in signals if s.direction == "DOWN"]),
        potential_partnerships=len([o for o in opps if o.category == "partnership"]),
        # A number in whole naira. Formatting it — the ₦ glyph, M vs B,
        # separators — is the frontend's call, so it never round-trips here.
        estimated_pipeline_value=pipeline,
        estimated_pipeline_currency="NGN",
    )
