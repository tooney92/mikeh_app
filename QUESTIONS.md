# Questions for Michaella (client)

Running log. Newest open questions at the top of each section. When one is
answered, move it to **Answered** with the date and what changed as a result —
the answers are the record of *why* the build looks the way it does.

Ask in plain language. She is not technical, so a question phrased in terms of
tables or endpoints will get a polite non-answer.

---

## Open — blocking

Nothing is fully blocked right now. The items below shape work that is either
in progress or not yet started.

**1. The thirteen people: names and work email addresses.**
She confirmed the shape: 3 TM Global directors, an SBU leader per unit, one
extra person per unit — plus Takeout Media having 3 people, and one person
leading both Takeout Media and TM Foundation. Accounts cannot be created
without the actual names and emails.
*Blocks:* handing the system to real users. Not blocking any code.

---

## Open — needs an answer before the matching engine is built

**2. Should a weak-fit opportunity still appear on a unit's list?**
Today any score at all makes an opportunity visible to that unit, however low.
`au-commission-gami` scores 82% for TM Foundation and 35% for Takeout Media, so
it currently shows on *both* lists. `global-institute` is 12% for Takeout.
With 8 sample opportunities that is untidy; once the crawler is finding dozens a
week it becomes noise.
Options to put to her: hide below a threshold (e.g. 40%), collapse them into a
"14 low-fit opportunities — show" section, or leave everything visible and let
the ranking do the work.
*Ask her:* "If something is only a weak match for your unit, should it still
appear on your list, or be tucked away?"

**3. Should the "Never show me" box actually suppress things?**
Each unit profile has a *Never show me* field. Takeout Media's already says
"opportunities under roughly NGN 20m" and "highly competitive open tenders with
no differentiation". Nothing acts on it yet. It reads like a filter she expects
to work.
*Ask her:* "The 'Never show me' box — should the system hide anything matching
it completely, or just push it down the list?"

**4. Which Nigerian industry sectors, exactly?**
The brief says weekly insight on "all industries within Nigeria", not only the
ones TM Global works in. The prototype shows five (Creative Economy,
Financial Services, Development & NGO, Public Sector, Tech & Telecoms).
"All" is a very large surface to scan and summarise.
*Ask her:* "Is there a list of the industries you want covered, or should we
start with the five in the design and add more as you see what is useful?"

**5. Who are the competitors?**
The Radar has a "competitor movements" count and the Briefing has a
"competitor movements to watch" section. No competitor has ever been named.
*Ask her:* "Which companies do you consider your competitors? We need names to
watch for."

**6. How should pipeline value be calculated?**
Opportunities carry a value band (`$` to `$$$$`), and the Radar shows an
"estimated pipeline value" in naira. The conversion from band to naira is
currently a guess made by us (25m / 75m / 200m / 500m).
*Ask her:* "When we show an estimated pipeline figure, what rough naira value
would you put on a small, medium, large and very large opportunity?"

---

## Open — smaller, can wait

**7. Should directors be able to reset passwords?**
Currently only she can. If a unit leader is locked out on a Monday morning,
only she can fix it. Asked, not yet answered.

**8. Does she want a "forgot password" email later?**
There is none. A locked-out user asks an administrator. Fine for thirteen
people; worth revisiting if the tool grows.

**9. Which address sends the Monday briefing, and who receives it?**
She has confirmed *one* email containing everything. Not yet confirmed: the
sending address, and whether it goes to all thirteen or a wider list.

**10. The bundle is named "Scout-Mate Intelligence Rebuild" but everything
inside says "TM Global Business Intelligence".**
Almost certainly just an export filename, but worth confirming it is one
product and not two.

---

## Answered

**2026-08-16 — Roles confirmed, with two changes.**
The four levels (Administrator / Director / SBU Leader / Team Member) are right.
Team members should *also* be able to start a scan. A leader can see what their
people have decided.
*Result:* `scan:run` granted to all four roles. Learning screen shows unit-wide
decisions to a lead.

**2026-08-16 — One person leads two units.**
Takeout Media has 3 people because it has 2 SBU leaders, one of whom also leads
TM Foundation.
*Result:* a user's unit membership became a set, not a single field. Someone in
two units sees the union of both units' opportunities, ranked by the better of
their two fits. This changed the shape of `/api/auth/me` before it was
contracted.

**2026-08-16 — She is the only administrator for now.**

**2026-08-16 — The source list serves all five units.**
No per-unit source scoping needed.

**2026-08-16 — Ignore scholarships, jobs and residencies.**
Within the 81 sources, focus on what TM Global can deliver from its services
across the SBUs. *Result:* this becomes a rule in the matching engine rather
than a source-level tag, because one source yields both a tender we want and a
scholarship we do not.

**2026-08-16 — Every opportunity shows scores for all five units.**
*Result:* the detail page returns every unit's score, best first, which is how a
joint pitch becomes visible.

**2026-08-16 — Each unit sees only their own unit's opportunities.**
*Result:* lists are scoped by the viewer's units; detail pages are not.

**2026-08-16 — One Monday email containing everything.**
Not one per unit. It carries opportunity highlights *plus* industry insight
*plus* upsell angles for existing clients — not opportunities alone.
