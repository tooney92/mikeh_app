from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.deps import current_user, requires
from app.models import BusinessUnit, Organisation, Profile, User
from app.schemas import BusinessUnitOut, OrganisationOut, ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api", tags=["profiles"])


def _to_out(profile: Profile, unit: BusinessUnit) -> ProfileOut:
    return ProfileOut(
        id=profile.id,
        business_unit_id=unit.id,
        business_unit_name=unit.name,
        initials=unit.initials,
        positioning=profile.positioning,
        priorities=profile.priorities,
        capabilities=profile.capabilities,
        credentials=profile.credentials,
        never_show=profile.never_show,
        min_fit_percent=profile.min_fit_percent,
    )


@router.get("/business-units", response_model=list[BusinessUnitOut])
def list_business_units(
    session: Session = Depends(get_session), _: User = Depends(current_user)
):
    return session.exec(select(BusinessUnit).order_by(BusinessUnit.id)).all()


@router.get("/profiles", response_model=list[ProfileOut])
def list_profiles(
    session: Session = Depends(get_session), _: User = Depends(current_user)
):
    """One profile per business unit — five of them."""
    units = {u.id: u for u in session.exec(select(BusinessUnit)).all()}
    rows = session.exec(select(Profile)).all()
    return [_to_out(p, units[p.business_unit_id]) for p in rows if p.business_unit_id in units]


@router.put("/profiles/{profile_id}", response_model=ProfileOut)
def update_profile(
    profile_id: int,
    payload: ProfileUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(requires("profile:update")),
):
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(404, "profile not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    session.add(profile)
    session.commit()
    session.refresh(profile)

    unit = session.get(BusinessUnit, profile.business_unit_id)
    return _to_out(profile, unit)


@router.get("/organisations", response_model=list[OrganisationOut])
def list_organisations(
    session: Session = Depends(get_session), _: User = Depends(current_user)
):
    return session.exec(select(Organisation).order_by(Organisation.name)).all()
