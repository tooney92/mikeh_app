"""The joint-pitch rule, in ONE place.

It used to live only inside the priority-actions router, which meant
/api/priority-actions announced "Joint pitch: Great African Museum Initiative"
while /api/opportunities/gam-au reported isJointPitchCandidate false on every
score of that same opportunity. Two units at 82 and 70, both over the floor,
and the screen whose stated purpose is surfacing a joint pitch could not
surface it — the flag was a model column nothing ever wrote.

The frontend found it and declined to derive the state client-side, correctly:
a UI asserting a partnership the API denies is the same class of bug as a
camelCase query parameter that silently returns everything.

So the rule lives here and both callers import it. Two implementations of one
business rule is how they drift; there is now only one.
"""

from sqlmodel import Session, select

from app.models import BusinessUnit, OpportunityScore, Profile

# A unit scoring at least this well is worth naming in a joint-pitch suggestion.
JOINT_PITCH_FLOOR = 60


def viewer_scope(user) -> tuple[bool, list[int]]:
    """(is_scoped, unit_ids) for this viewer. Derived from ROLE, not emptiness.

    This used to be `scoped = bool(user.unit_ids)`, which fails OPEN. unit_ids
    is empty for two completely different people: a director who sees
    everything by scope, and a member whose unit box was never ticked. Deriving
    from emptiness cannot tell them apart, so the second was silently treated
    like the first and shown every unit's opportunities, pipeline value and
    priority actions.

    That was not a rare edge case. The /admin user form makes business_units
    OPTIONAL, so it is the default state of every account created without
    remembering to tick a unit.

    A scoped user with no units now sees NOTHING, which is the honest reading
    of "you see your units' rows" when you belong to no units.
    """
    if user.sees_all_units:
        return False, []
    return True, list(user.unit_ids)


def unit_bars(session: Session, unit_ids: list[int]) -> dict[int, int]:
    """Each unit's min_fit_percent — the bar below which it is not worth showing.

    A unit with no profile row gets NO bar rather than the model default: a
    missing profile should show everything, not silently hide everything on
    account of configuration nobody ever set.
    """
    if not unit_ids:
        return {}
    return {
        p.business_unit_id: p.min_fit_percent
        for p in session.exec(
            select(Profile).where(Profile.business_unit_id.in_(unit_ids))
        ).all()
    }


def clears_bar(mine: list[OpportunityScore], bars: dict[int, int]) -> bool:
    """True when ANY of the viewer's units rates this above its own bar.

    Judged on the viewer's OWN scores, never the opportunity's top score. An
    opportunity at 82 for TM Foundation and 35 for Takeout Media belongs in the
    Foundation's list and not in Takeout's; comparing against the top score
    would put it back in the list this exists to keep clean.

    Union for somebody in two units, matching the existing rule that the better
    of their two fits ranks it.
    """
    if not bars:
        return True
    return any(s.fit_percent >= bars.get(s.business_unit_id, 0) for s in mine)


def joint_pitch_scores(scores: list[OpportunityScore]) -> list[OpportunityScore]:
    """The scores that make this opportunity a joint pitch, or an empty list.

    TWO or more units over the floor. One unit scoring 90 is a good
    opportunity, not a partnership — the whole point is that a second unit
    also fits, which is what nobody would spot from their own list alone.
    """
    strong = [s for s in scores if s.fit_percent >= JOINT_PITCH_FLOOR]
    return strong if len(strong) > 1 else []


def joint_pitch_note(
    strong: list[OpportunityScore], units: dict[int, BusinessUnit]
) -> str:
    """The sentence explaining the suggestion. Empty when it is not one."""
    if not strong:
        return ""
    names = [
        units[s.business_unit_id].name for s in strong if s.business_unit_id in units
    ]
    if len(names) < 2:
        return ""
    listed = f"{', '.join(names[:-1])} and {names[-1]}"
    return (
        f"{listed} both score {JOINT_PITCH_FLOOR}% or better on this — "
        "worth pitching together."
        if len(names) == 2
        else f"{listed} all score {JOINT_PITCH_FLOOR}% or better on this — "
        "worth pitching together."
    )
