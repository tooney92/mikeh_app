from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Organisation, Profile
from app.schemas import OrganisationOut, ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api", tags=["profiles"])


@router.get("/profiles", response_model=list[ProfileOut])
def list_profiles(session: Session = Depends(get_session)):
    return session.exec(select(Profile)).all()


@router.put("/profiles/{profile_id}", response_model=ProfileOut)
def update_profile(
    profile_id: str, payload: ProfileUpdate, session: Session = Depends(get_session)
):
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(404, "profile not found — expected 'takeout' or 'foundation'")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.get("/organisations", response_model=list[OrganisationOut])
def list_organisations(session: Session = Depends(get_session)):
    return session.exec(select(Organisation).order_by(Organisation.name)).all()
