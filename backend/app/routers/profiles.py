from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.deps import current_user, requires
from app.models import BusinessUnit, Organisation, Profile, User
from app.schemas import BusinessUnitOut, OrganisationOut, ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api", tags=["profiles"])


def can_edit_profile(user: User, business_unit_id: int) -> bool:
    """May this user write this profile? BOTH axes, in one place.

    The profile:update GRANT says you may edit profiles at all; SCOPE says
    whose. The PUT ENFORCES exactly this and the list REPORTS it as canEdit, so
    the control the frontend draws and the gate the server applies come from one
    function and cannot drift apart.

    Reporting it matters more than it looks. /api/auth/me carries businessUnits
    and permissions but no scope field, so the only way to tell "unscoped, edits
    everything" from "scoped to nothing" on the client is
    `businessUnits.length === 0` — which is character-for-character the
    fail-open inference just removed from this codebase. A lead created in
    /admin with no unit assigned holds profile:update with an empty set, and
    that inference would draw five editable profiles whose every save 403s.
    Answering the question outright means nobody has to infer it.
    """
    if not user.can("profile:update"):
        return False
    return user.sees_all_units or business_unit_id in user.unit_ids


def _to_out(profile: Profile, unit: BusinessUnit, user: User) -> ProfileOut:
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
        can_edit=can_edit_profile(user, unit.id),
    )


@router.get("/business-units", response_model=list[BusinessUnitOut])
def list_business_units(
    session: Session = Depends(get_session), _: User = Depends(current_user)
):
    return session.exec(select(BusinessUnit).order_by(BusinessUnit.id)).all()


@router.get("/profiles", response_model=list[ProfileOut])
def list_profiles(
    session: Session = Depends(get_session), user: User = Depends(current_user)
):
    """One profile per business unit — five of them.

    READING stays unscoped on purpose: seeing another unit's positioning is how
    a joint pitch gets spotted. Each row carries canEdit so the caller knows
    which of the five they may actually write.
    """
    units = {u.id: u for u in session.exec(select(BusinessUnit)).all()}
    rows = session.exec(select(Profile)).all()
    return [
        _to_out(p, units[p.business_unit_id], user)
        for p in rows
        if p.business_unit_id in units
    ]


@router.put("/profiles/{profile_id}", response_model=ProfileOut)
def update_profile(
    profile_id: int,
    payload: ProfileUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(requires("profile:update")),
):
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(404, "profile not found")

    # The GRANT says you may edit a profile; SCOPE says whose. Both apply, and
    # only the grant was being checked — a lead of TM Foundation could rewrite
    # Takeout Media's positioning and credentials.
    #
    # Since min_fit_percent landed here, that is worse than untidy: setting
    # another unit's bar to 99 silently empties their opportunity list and their
    # radar tiles, from a screen they never see, with no error anywhere.
    #
    # Same predicate the list reports as canEdit. `requires` has already proved
    # the codename, so reaching here can only be the unit reason — which is why
    # the message names that and nothing else. The two 403 causes stay separable
    # by their detail string, since they are different problems for the reader.
    if not can_edit_profile(user, profile.business_unit_id):
        raise HTTPException(403, "that profile belongs to another business unit")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    session.add(profile)
    session.commit()
    session.refresh(profile)

    unit = session.get(BusinessUnit, profile.business_unit_id)
    if not unit:
        # Its business unit was deleted in /admin, orphaning this row. The list
        # endpoint skips such profiles; without this the response builder would
        # dereference None and 500.
        raise HTTPException(404, "that profile's business unit no longer exists")
    return _to_out(profile, unit, user)


@router.get("/organisations", response_model=list[OrganisationOut])
def list_organisations(
    session: Session = Depends(get_session), _: User = Depends(current_user)
):
    return session.exec(select(Organisation).order_by(Organisation.name)).all()
