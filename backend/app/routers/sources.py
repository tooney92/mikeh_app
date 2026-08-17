from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.deps import current_user, requires
from app.models import Source, User
from app.schemas import SourceCreate, SourceOut, SourceUpdate

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
def list_sources(
    active_only: bool = False,
    session: Session = Depends(get_session),
    _: User = Depends(current_user),
):
    stmt = select(Source).order_by(Source.name)
    if active_only:
        stmt = stmt.where(Source.active == True)  # noqa: E712 — SQL comparison
    return session.exec(stmt).all()


@router.post("", response_model=SourceOut, status_code=201)
def add_source(
    payload: SourceCreate,
    session: Session = Depends(get_session),
    _: User = Depends(requires("source:create")),
):
    src = Source(**payload.model_dump())
    session.add(src)
    session.commit()
    session.refresh(src)
    return src


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(
    source_id: int,
    payload: SourceUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(requires("source:update")),
):
    src = session.get(Source, source_id)
    if not src:
        raise HTTPException(404, "source not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(src, field, value)
    session.add(src)
    session.commit()
    session.refresh(src)
    return src


@router.delete("/{source_id}", status_code=204)
def remove_source(
    source_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(requires("source:delete")),
):
    src = session.get(Source, source_id)
    if not src:
        raise HTTPException(404, "source not found")
    session.delete(src)
    session.commit()
