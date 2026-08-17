from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.deps import current_user, requires
from app.models import Decision, Opportunity, OpportunityScore, User
from app.schemas import DecisionCreate, DecisionOut, LearningStats

router = APIRouter(prefix="/api", tags=["decisions"])

VALID_DECISIONS = {"Pursue", "Partner", "Watch", "Reject"}


def _to_out(
    d: Decision, opp: Opportunity | None, fit: int | None = None
) -> DecisionOut:
    return DecisionOut(
        id=d.id,
        opportunity_id=d.opportunity_id,
        business_unit_id=d.business_unit_id,
        decision=d.decision,
        reason=d.reason,
        created_at=d.created_at,
        opportunity_title=opp.title if opp else None,
        fit_percent=fit,
    )


def _fits(session: Session) -> dict[str, dict[int, int]]:
    """opportunity_id -> {business_unit_id: fit_percent}"""
    out: dict[str, dict[int, int]] = {}
    for s in session.exec(select(OpportunityScore)).all():
        out.setdefault(s.opportunity_id, {})[s.business_unit_id] = s.fit_percent
    return out


def _fit_for(d: Decision, fits: dict[str, dict[int, int]]) -> int | None:
    """The deciding unit's fit, else the best fit on that opportunity."""
    by_unit = fits.get(d.opportunity_id)
    if not by_unit:
        return None
    if d.business_unit_id in by_unit:
        return by_unit[d.business_unit_id]
    return max(by_unit.values())


def _log(session: Session) -> list[DecisionOut]:
    """Every decision, newest first, joined to its opportunity."""
    rows = session.exec(select(Decision).order_by(Decision.created_at.desc())).all()
    opps = {o.id: o for o in session.exec(select(Opportunity)).all()}
    fits = _fits(session)
    return [
        _to_out(d, opps.get(d.opportunity_id), _fit_for(d, fits)) for d in rows
    ]


@router.post("/decisions", response_model=DecisionOut, status_code=201)
def log_decision(
    payload: DecisionCreate,
    session: Session = Depends(get_session),
    _: User = Depends(requires("decision:create")),
):
    if payload.decision not in VALID_DECISIONS:
        raise HTTPException(400, f"decision must be one of {sorted(VALID_DECISIONS)}")
    if payload.decision == "Reject" and not payload.reason:
        raise HTTPException(400, "a Reject decision requires a reason")

    opp = session.get(Opportunity, payload.opportunity_id)
    if not opp:
        raise HTTPException(404, "opportunity not found")

    d = Decision(
        opportunity_id=payload.opportunity_id,
        business_unit_id=payload.business_unit_id,
        decision=payload.decision,
        reason=payload.reason if payload.decision == "Reject" else None,
    )
    session.add(d)
    session.commit()
    session.refresh(d)
    return _to_out(d, opp, _fit_for(d, _fits(session)))


@router.get("/decisions", response_model=list[DecisionOut])
def list_decisions(
    session: Session = Depends(get_session), _: User = Depends(current_user)
):
    return _log(session)


@router.get("/learning", response_model=LearningStats)
def learning(
    session: Session = Depends(get_session), _: User = Depends(current_user)
):
    """Aggregates for the Learning page — computed, never hardcoded."""
    decisions = session.exec(select(Decision)).all()
    opps = {o.id: o for o in session.exec(select(Opportunity)).all()}

    # "Avg fit pursued" means the fit for the unit that made the call, falling
    # back to the best score on that opportunity.
    fits = _fits(session)
    pursued_fits = [
        f
        for d in decisions
        if d.decision == "Pursue" and (f := _fit_for(d, fits)) is not None
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
        avg_pursued_fit_percent=(
            round(sum(pursued_fits) / len(pursued_fits), 1) if pursued_fits else None
        ),
        most_backed_theme=backed_themes.most_common(1)[0][0] if backed_themes else None,
        most_common_rejection=rejections.most_common(1)[0][0] if rejections else None,
        breakdown=dict(Counter(d.decision for d in decisions)),
        log=_log(session),
    )
