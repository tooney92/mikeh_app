from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.deps import current_user, requires
from app.models import BusinessUnit, Decision, Opportunity, OpportunityScore, User
from app.schemas import DecisionCreate, DecisionOut, LearningStats
from app.scoring import viewer_scope

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


def _units_by_opportunity(session: Session) -> dict[str, set[int]]:
    """opportunity_id -> the units that have a score on it.

    Which units an unattributed decision is visible to: entitlement follows the
    opportunity, the same rule the detail endpoint uses.
    """
    out: dict[str, set[int]] = {}
    for s in session.exec(select(OpportunityScore)).all():
        out.setdefault(s.opportunity_id, set()).add(s.business_unit_id)
    return out


def visible_decisions(
    session: Session, unit_ids: list[int] | None, newest_first: bool = False
) -> list[Decision]:
    """Which decisions this viewer may read. `unit_ids` None means unscoped.

    ONE definition, used by both /api/decisions and /api/learning. They each had
    their own copy of `d.business_unit_id in unit_ids` and both carried the same
    bug, which is the argument for this function existing rather than for fixing
    it twice.

    An UNATTRIBUTED decision (no unit) belongs to whoever is entitled to the
    OPPORTUNITY, not to nobody. `in unit_ids` is False for NULL, so a director's
    company-level "Pursue" on a TM Foundation opportunity never reached that
    unit's log, breakdown or decisionsLogged — while log_decision deliberately
    ALLOWS an unscoped user to omit the unit. The write path and the read path
    disagreed about what an unattributed decision means.

    Every Decision row predating the business_unit_id column is NULL as well, so
    on any database with history each lead's Learning page read zero.
    """
    stmt = select(Decision)
    if newest_first:
        stmt = stmt.order_by(Decision.created_at.desc())
    rows = list(session.exec(stmt).all())
    if unit_ids is None:
        return rows

    mine = set(unit_ids)
    scored = _units_by_opportunity(session)
    return [
        d
        for d in rows
        if d.business_unit_id in mine
        or (d.business_unit_id is None and scored.get(d.opportunity_id, set()) & mine)
    ]


def _fit_for(d: Decision, fits: dict[str, dict[int, int]]) -> int | None:
    """The deciding unit's fit, else the best fit on that opportunity."""
    by_unit = fits.get(d.opportunity_id)
    if not by_unit:
        return None
    if d.business_unit_id in by_unit:
        return by_unit[d.business_unit_id]
    return max(by_unit.values())


def _log(session: Session, unit_ids: list[int] | None = None) -> list[DecisionOut]:
    """Decisions, newest first, joined to their opportunity.

    `unit_ids` None means unscoped (admin, director). A list means show only
    decisions taken by those units — every other read endpoint here filters by
    unit and these did not, so a TM Foundation lead could read Takeout Media's
    rejection reasons, which are commercially candid by design.
    """
    rows = visible_decisions(session, unit_ids, newest_first=True)
    opps = {o.id: o for o in session.exec(select(Opportunity)).all()}
    fits = _fits(session)
    return [
        _to_out(d, opps.get(d.opportunity_id), _fit_for(d, fits)) for d in rows
    ]


@router.post("/decisions", response_model=DecisionOut, status_code=201)
def log_decision(
    payload: DecisionCreate,
    session: Session = Depends(get_session),
    user: User = Depends(requires("decision:create")),
):
    if payload.decision not in VALID_DECISIONS:
        raise HTTPException(400, f"decision must be one of {sorted(VALID_DECISIONS)}")
    if payload.decision == "Reject" and not payload.reason:
        raise HTTPException(400, "a Reject decision requires a reason")

    opp = session.get(Opportunity, payload.opportunity_id)
    if not opp:
        raise HTTPException(404, "opportunity not found")

    scoped, unit_ids = viewer_scope(user)
    unit_id = payload.business_unit_id

    # Omitting the unit is legal and means "unattributed" — an admin or director
    # deciding on behalf of nobody in particular. But for a SCOPED user it would
    # be a trap: the decision would be written, then filtered out of their own
    # log because it belongs to no unit of theirs. Someone in exactly one unit
    # obviously means that one, so fill it in rather than refusing.
    if unit_id is None and scoped:
        if len(unit_ids) == 1:
            unit_id = unit_ids[0]
        else:
            raise HTTPException(
                400,
                "businessUnitId is required — you belong to more than one unit, "
                "so which one is deciding cannot be inferred",
            )

    if unit_id is not None:
        # The unit must exist. SQLite does not enforce the foreign key by
        # default, so business_unit_id 999 was written straight through and then
        # appeared in the learning aggregates as a unit nobody can name.
        if not session.get(BusinessUnit, unit_id):
            raise HTTPException(400, f"unknown business unit {unit_id}")

        # And it must be YOURS. Otherwise a member of one unit could log a
        # Reject attributed to another, poisoning that unit's learning history
        # from a screen they cannot see.
        if scoped and unit_id not in unit_ids:
            raise HTTPException(
                403, "you cannot log a decision for another business unit"
            )

    # Deciding on an opportunity none of your units scored is the same overreach
    # the detail endpoint now refuses.
    if scoped:
        scored_for = {
            s.business_unit_id
            for s in session.exec(
                select(OpportunityScore).where(
                    OpportunityScore.opportunity_id == payload.opportunity_id
                )
            ).all()
        }
        if not scored_for & set(unit_ids):
            raise HTTPException(404, "opportunity not found")

    d = Decision(
        opportunity_id=payload.opportunity_id,
        business_unit_id=unit_id,
        decision=payload.decision,
        reason=payload.reason if payload.decision == "Reject" else None,
        # The column existed on the model and nothing ever wrote it, so "who
        # made this call" was unanswerable on a table whose whole purpose is
        # recording who decided what. The Learning page's credibility rests on
        # these rows being attributable.
        user_id=user.id,
    )
    session.add(d)
    session.commit()
    session.refresh(d)
    return _to_out(d, opp, _fit_for(d, _fits(session)))


@router.get("/decisions", response_model=list[DecisionOut])
def list_decisions(
    session: Session = Depends(get_session), user: User = Depends(current_user)
):
    scoped, unit_ids = viewer_scope(user)
    return _log(session, unit_ids if scoped else None)


@router.get("/learning", response_model=LearningStats)
def learning(
    session: Session = Depends(get_session), user: User = Depends(current_user)
):
    """Aggregates for the Learning page — computed, never hardcoded.

    Scoped like everything else: avg_pursued_fit_percent computed across all
    units told a lead about calls their colleagues made, which is a different
    statistic from the one the page claims to show.
    """
    scoped, unit_ids = viewer_scope(user)
    decisions = visible_decisions(session, unit_ids if scoped else None)
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
        log=_log(session, unit_ids if scoped else None),
    )
