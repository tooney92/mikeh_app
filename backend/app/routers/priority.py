"""The Radar's "This week's priority actions" list.

Derived from real rows, never hardcoded — the whole promise of the section is
"this is what changed this week", so a fixed list would be worse than none.

Each action carries a `type`, because the design colours the tag per type:
Opportunity | Organisation | Industry | Partnership | Competitor.
"""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.db import get_session
from app.deps import current_user
from app.models import (
    BusinessUnit,
    IndustrySignal,
    Opportunity,
    OpportunityScore,
    Organisation,
    User,
)
from app.schemas import PriorityAction
from app.scoring import joint_pitch_note, joint_pitch_scores

router = APIRouter(prefix="/api", tags=["radar"])


@router.get("/priority-actions", response_model=list[PriorityAction])
def priority_actions(
    limit: int = Query(8, ge=1, le=30),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Scoped like the opportunity list: a lead sees their units' actions."""
    unit_ids = user.unit_ids
    scoped = bool(unit_ids)

    units = {u.id: u for u in session.exec(select(BusinessUnit)).all()}
    opps = {o.id: o for o in session.exec(select(Opportunity)).all()}

    by_opp: dict[str, list[OpportunityScore]] = {}
    for s in session.exec(select(OpportunityScore)).all():
        by_opp.setdefault(s.opportunity_id, []).append(s)

    actions: list[PriorityAction] = []

    # 1. Opportunities worth acting on — high relevance, best fit first.
    ranked = []
    for opp_id, scores in by_opp.items():
        mine = [s for s in scores if s.business_unit_id in unit_ids]
        if scoped and not mine:
            continue
        opp = opps.get(opp_id)
        if not opp or opp.relevance != "HIGH":
            continue
        best = max((s.fit_percent for s in (mine or scores)), default=0)
        ranked.append((best, opp, scores))
    ranked.sort(key=lambda r: r[0], reverse=True)

    for best, opp, scores in ranked[:4]:
        # Most sample records carry the literal "No deadline stated", so only
        # mention a deadline when there is an actual one to mention.
        has_deadline = opp.deadline and "no deadline" not in opp.deadline.lower()
        lead_in = f"{opp.org} — {best}% fit"
        if has_deadline:
            lead_in += f", closes {opp.deadline}"
        actions.append(
            PriorityAction(
                type="Opportunity",
                title=opp.title,
                description=f"{lead_in}. {opp.recommendation}".strip(),
                opportunity_id=opp.id,
            )
        )

        # 2. Two units scoring well on the same thing is a joint pitch. The rule
        # lives in app.scoring so this and the opportunity DETAIL endpoint
        # cannot disagree about the same opportunity — they used to.
        strong = joint_pitch_scores(scores)
        if strong:
            actions.append(
                PriorityAction(
                    type="Partnership",
                    title=f"Joint pitch: {opp.title}",
                    description=joint_pitch_note(strong, units),
                    opportunity_id=opp.id,
                )
            )

    # 3. Client organisations flagged for approach.
    for org in session.exec(
        select(Organisation).where(Organisation.priority == "approach_now")
    ).all():
        actions.append(
            PriorityAction(
                type="Organisation",
                title=org.name,
                description=org.upsell_angle or org.signal or "Flagged for approach.",
            )
        )

    # 4/5. Industry movement. Empty until the signal generation work exists
    # (todo 5), so these two types simply do not appear yet.
    for sig in session.exec(select(IndustrySignal)).all():
        if sig.direction == "UP":
            actions.append(
                PriorityAction(type="Industry", title=sig.sector, description=sig.text)
            )
        elif sig.direction == "DOWN":
            actions.append(
                PriorityAction(type="Competitor", title=sig.sector, description=sig.text)
            )

    return actions[:limit]
