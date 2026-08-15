from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlmodel import Session, select

from app.db import engine, get_session
from app.models import Opportunity, ScanRun, Source
from app.schemas import ScanStatus

router = APIRouter(prefix="/api/scan", tags=["scan"])


def _run_scan(run_id: int) -> None:
    """Placeholder for the real crawl + match job.

    The crawler (fetch each active source, parse postings) and the LLM matching
    engine (score each posting against both profiles) are not built yet — this
    records a real job lifecycle so the Radar's status panel has something true
    to poll. Swap the body for the real work; the status contract stays.
    """
    with Session(engine) as session:
        run = session.get(ScanRun, run_id)
        if not run:
            return
        active = session.exec(
            select(Source).where(Source.active == True)  # noqa: E712
        ).all()
        run.sources_swept = len(active)
        run.scored = len(session.exec(select(Opportunity)).all())
        run.status = "complete"
        run.finished_at = datetime.now(timezone.utc)
        session.add(run)
        session.commit()


def _latest(session: Session) -> ScanRun | None:
    return session.exec(select(ScanRun).order_by(ScanRun.started_at.desc())).first()


@router.post("", response_model=ScanStatus, status_code=202)
def start_scan(
    background: BackgroundTasks, session: Session = Depends(get_session)
):
    run = ScanRun(status="running")
    session.add(run)
    session.commit()
    session.refresh(run)
    background.add_task(_run_scan, run.id)
    return ScanStatus.model_validate(run)


@router.get("/status", response_model=ScanStatus)
def scan_status(session: Session = Depends(get_session)):
    run = _latest(session)
    if not run:
        return ScanStatus(status="idle")
    return ScanStatus.model_validate(run)
