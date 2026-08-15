from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Decision, Opportunity
from app.schemas import DecisionCreate, DecisionOut, LearningStats

router = APIRouter(prefix="/api", tags=["decisions"])

VALID_DECISIONS = {"Pursue", "Partner", "Watch", "Reject"}


def _to_out(d: Decision, opp: Opportunity | None) -> DecisionOut:
    return DecisionOut(
        id=d.id,
        opportunity_id=d.opportunity_id,
        decision=d.decision,
        reason=d.reason,
        created_at=d.created_at,
        opportunity_title=opp.title if opp else None,
        fit_foundation=opp.fit_foundation if opp else None,
    )


def _log(session: Session) -> list[DecisionOut]:
    """Every decision, newest first, joined to its opportunity."""
    rows = session.exec(select(Decision).order_by(Decision.created_at.desc())).all()
    opps = {o.id: o for o in session.exec(select(Opportunity)).all()}
    return [_to_out(d, opps.get(d.opportunity_id)) for d in rows]


@router.post("/decisions", response_model=DecisionOut, status_code=201)
def log_decision(payload: DecisionCreate, session: Session = Depends(get_session)):
    if payload.decision not in VALID_DECISIONS:
        raise HTTPException(400, f"decision must be one of {sorted(VALID_DECISIONS)}")
    if payload.decision == "Reject" and not payload.reason:
        raise HTTPException(400, "a Reject decision requires a reason")

    opp = session.get(Opportunity, payload.opportunity_id)
    if not opp:
        raise HTTPException(404, "opportunity not found")

    d = Decision(
        opportunity_id=payload.opportunity_id,
        decision=payload.decision,
        reason=payload.reason if payload.decision == "Reject" else None,
    )
    session.add(d)
    session.commit()
    session.refresh(d)
    return _to_out(d, opp)


@router.get("/decisions", response_model=list[DecisionOut])
def list_decisions(session: Session = Depends(get_session)):
    return _log(session)


@router.get("/learning", response_model=LearningStats)
def learning(session: Session = Depends(get_session)):
    """Aggregates for the Learning page — computed, never hardcoded."""
    decisions = session.exec(select(Decision)).all()
    opps = {o.id: o for o in session.exec(select(Opportunity)).all()}

    pursued_fits = [
        opps[d.opportunity_id].fit_foundation
        for d in decisions
        if d.decision == "Pursue" and d.opportunity_id in opps
    ]
    backed_themes = Counter(
        theme
        for d in decisions
        if d.decision in ("Pursue", "Partner") and d.opportunity_id in opps
        for theme in opps[d.opportunity_id].themes
    )
    rejections = Counter(d.reason for d in decisions if d.decision == "Reject" and d.reason)

    return LearningStats(
        decisions_logged=len(decisions),
        avg_foundation_fit_pursued=(
            round(sum(pursued_fits) / len(pursued_fits), 1) if pursued_fits else None
        ),
        most_backed_theme=backed_themes.most_common(1)[0][0] if backed_themes else None,
        most_common_rejection=rejections.most_common(1)[0][0] if rejections else None,
        breakdown=dict(Counter(d.decision for d in decisions)),
        log=_log(session),
    )
