from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import Decision, Opportunity
from app.schemas import OpportunityDetail, OpportunitySummary

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])

# The prototype's filter pills, mapped to a predicate over the row.
FILTERS: dict[str, object] = {
    "everything": lambda o: True,
    "bid-now": lambda o: o.category == "bid",
    "watch": lambda o: o.category == "watch",
    "partnership": lambda o: o.category == "partnership",
    "bd-leads": lambda o: o.category == "bd",
    "foundation": lambda o: o.beneficiary in ("TM Foundation", "Joint"),
    "takeout": lambda o: o.beneficiary in ("Takeout Media", "Joint"),
    "international": lambda o: o.geography not in ("Nigeria", ""),
}


@router.get("", response_model=list[OpportunitySummary])
def list_opportunities(
    filter: str = Query("everything"),
    limit: int | None = Query(None, ge=1, le=200),
    session: Session = Depends(get_session),
):
    key = filter.lower()
    if key not in FILTERS:
        raise HTTPException(400, f"unknown filter '{filter}'")
    rows = session.exec(
        select(Opportunity).order_by(Opportunity.fit_foundation.desc())
    ).all()
    rows = [o for o in rows if FILTERS[key](o)]
    return rows[:limit] if limit else rows


@router.get("/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity(opportunity_id: str, session: Session = Depends(get_session)):
    opp = session.get(Opportunity, opportunity_id)
    if not opp:
        raise HTTPException(404, "opportunity not found")

    latest = session.exec(
        select(Decision)
        .where(Decision.opportunity_id == opportunity_id)
        .order_by(Decision.created_at.desc())
    ).first()

    out = OpportunityDetail.model_validate(opp)
    if latest:
        out.decision = latest.decision
        out.decision_reason = latest.reason
    return out
