import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlmodel import Session, select

from app.db import engine, get_session
from app.deps import current_user, requires
from app.models import Opportunity, ScanRun, Source, User
from app.schemas import ScanStatus

router = APIRouter(prefix="/api/scan", tags=["scan"])


def _run_scan(run_id: int) -> None:
    """Placeholder for the real crawl + match job.

    The crawler (fetch each active source, parse postings) and the LLM matching
    engine (score each posting against both profiles) are not built yet — this
    records a real job lifecycle so the Radar's status panel has something true
    to poll. Swap the body for the real work; the status contract stays.
    """
    try:
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
    except Exception:
        # A run that raises must not stay "running" forever. The frontend
        # disables its Run button for ANY status that is not idle or complete,
        # and it polls only from inside the handler that button fires — so a
        # wedged "running" row disables scanning for everybody, permanently,
        # with nothing left able to poll it back to life.
        #
        # Today the body cannot realistically fail; once it is a real crawler
        # hitting eighty-odd websites, failing will be routine. Recording the
        # terminal state is what keeps the status honest either way.
        logging.getLogger(__name__).exception("scan run %s failed", run_id)
        try:
            with Session(engine) as session:
                run = session.get(ScanRun, run_id)
                if run and run.status == "running":
                    run.status = "failed"
                    run.finished_at = datetime.now(timezone.utc)
                    session.add(run)
                    session.commit()
        except Exception:  # pragma: no cover - the database itself is gone
            logging.getLogger(__name__).exception(
                "could not mark scan run %s failed", run_id
            )


def _latest(session: Session) -> ScanRun | None:
    return session.exec(select(ScanRun).order_by(ScanRun.started_at.desc())).first()


@router.post("", response_model=ScanStatus, status_code=202)
def start_scan(
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    _: User = Depends(requires("scan:run")),
):
    run = ScanRun(status="running")
    session.add(run)
    session.commit()
    session.refresh(run)
    background.add_task(_run_scan, run.id)
    return ScanStatus.model_validate(run)


@router.get("/status", response_model=ScanStatus)
def scan_status(
    session: Session = Depends(get_session), _: User = Depends(current_user)
):
    run = _latest(session)
    if not run:
        return ScanStatus(status="idle")
    return ScanStatus.model_validate(run)
