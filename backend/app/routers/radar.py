from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session
from app.models import IndustrySignal, Opportunity, Organisation
from app.schemas import RadarStats

router = APIRouter(prefix="/api", tags=["radar"])

# The prototype shows pipeline value as ₦ from the "$$$$" value bands.
VALUE_BANDS = {"$": 25, "$$": 75, "$$$": 200, "$$$$": 500}  # NGN millions


@router.get("/radar", response_model=RadarStats)
def radar(session: Session = Depends(get_session)):
    """The six stat-strip counts, computed from what's in the database."""
    opps = session.exec(select(Opportunity)).all()
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
        estimated_pipeline_value=f"₦{pipeline}m",
    )
