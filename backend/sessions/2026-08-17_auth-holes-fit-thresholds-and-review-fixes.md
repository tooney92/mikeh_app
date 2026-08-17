# Session handoff — 2026-08-17 (overnight) — Backend: auth holes, fit thresholds, review fixes

Written from the **backend** seat. This continues
`2026-08-16_backend-rbac-scoring-and-contracts.md` — read that one first if you
are cold, it covers the stack, the RBAC model and contracts 1–2. This one covers
one long night: closing six access-control holes, shipping the per-unit fit
threshold, and fixing twelve code-review findings.

Companion handoff from the frontend seat lives in `frontend/sessions/`.

---

## Where to start

```sh
curl -s http://127.0.0.1:8000/api/health          # {"status":"ok"}
cd backend && uv run pytest -q                     # expect 101 passed
```

If it is not running — **and note the `--reload`, which is new**:

```sh
cd backend
TM_SECRET_KEY="tmglobal-dev-shared-key-do-not-use-in-prod" \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Anthony runs this in **his own terminal** now, not as an agent background job.
That was a deliberate change and it fixed a whole night of the server dying.
**Do not `kill` port 8000** — you would be killing a process he is watching. With
`--reload` you no longer need to: edit the file and it picks the change up.

Branch: `backend/auth-rbac-and-fit-thresholds`. Two commits on it, `dd9ffed` and
`1cbce30`. The backend tree is clean; anything modified under `frontend/` is the
other seat's and is theirs to commit.

**Dev login:** `admin` / `zfSDC8ehrGQhR3ud`. Test accounts below.

---

## The one paragraph version

The API had no authentication on most of its surface, and where it did have
scoping the scoping was fail-open. Both are now closed and pinned by tests. On
top of that, Michaella asked for a rule — *don't show a unit an opportunity that
scores badly for it* — which turned out to be the feature that finally made
row-level scoping visible on screen. Tests went 56 → **101**.

---

## The six access-control holes, and the one pattern behind three of them

### 1. Most of the API was unauthenticated

`/api/opportunities`, `/api/radar`, `/api/priority-actions`, `/api/profiles`,
`/api/sources`, `/api/decisions`, `/api/learning` all answered anyone with no
token at all. The login endpoint existed and worked; nothing behind it was
actually gated. Every read route now takes `Depends(current_user)`.

### 2. Write routes checked nothing

Having a valid token was enough to PATCH a profile, delete a source or trigger a
scan. The 40 permission codenames existed, were seeded, and were returned in
`/api/auth/me` — and were never once consulted server-side. `requires("...")`
now gates every write.

**The frontend was gating its menu on those codenames the whole time.** So the
UI looked correct and the server was wide open. If you take one thing from this
handoff: a permission that only the client enforces is not a permission.

### 3. `scoped = bool(unit_ids)` — fail open (three files)

The important one. `opportunities.py`, `radar.py` and `priority.py` each decided
"should I filter this query?" by asking whether the user belonged to any units:

```python
scoped = bool(unit_ids)          # WRONG
scoped = not user.sees_all_units # right
```

`user.unit_ids` is empty for **two completely different people**: a director or
admin whose scope is `all`, and a lead or member who happens to have been
created without units. Units are an optional many-to-many on `UserAdmin`, so
`/admin` creates that second person by default — click save without touching the
units box and you have made an account that sees everything.

So a brand-new member fell into the unscoped branch and got the director view.
Radar computed their tiles over the entire database. The guard in
priority-actions never fired.

It now lives once, in `app/scoring.py::viewer_scope`, derived from the ROLE.

> The lesson worth carrying: the bug was in deriving a security decision from
> data that happened to correlate with it. "Has no units" *usually* means admin.
> Ask the question you actually mean.

### 4. Profile writes were unscoped

Any authenticated user could PATCH any unit's profile. Worse after the threshold
shipped — `min_fit_percent` lives on the profile, so a lead could change what
another unit's whole team is allowed to see. Now 403 unless it is your unit.

### 5. Opportunity detail was unscoped

`/api/opportunities/{id}` required only a token. A Design Teem lead whose list
was empty could still fetch any opportunity's full narrative and source URL by
typing its slug — and the slugs are guessable (`gam-au`). Now 404, deliberately
worded identically to a genuinely missing row so the response does not confirm
the id exists.

Note the distinction that survived review: showing **every unit's scores** on an
opportunity you can already see is correct and intended — that is what makes a
joint pitch visible. Fetching an opportunity **none of your units scored** is
not the same thing.

### 6. The back office trusted a stale token

`AdminAuth.authenticate` read `payload["admin"]` out of the JWT. Revoke
someone's admin rights and their existing token kept working for the full 12
hours. It now re-reads the user and checks `is_active` and `can("admin:access")`
against the database.

### Also: decisions

`business_unit_id` came straight off the request body unchecked, so a Foundation
member could log a `Reject` attributed to Takeout Media and poison that unit's
learning history from a screen they cannot see. SQLite does not enforce the
foreign key by default either, so unit `999` wrote straight through and appeared
in the aggregates as a unit nobody can name. Both checked now. `list_decisions`
and `learning` were also unscoped — rejection reasons are commercially candid by
design, and everyone could read everyone's.

---

## The fit threshold (Michaella's rule)

**Her question:** "what if a unit is less than a 40% match — I don't think we
need to inform them."

**What shipped, and the four decisions Anthony made:**

1. **Judge each unit by its OWN score, never the top one.** An opportunity
   scoring 82 for TM Foundation and 35 for Takeout Media is the Foundation's to
   see and not Takeout's. Comparing against `top_fit_percent` would leak it
   straight back into the list the feature exists to keep clean.
2. **Bosses see everything.** Admin and director are overseeing, not being
   pitched to, so no bar applies — *unless* they deliberately narrow to one
   unit, in which case they get that unit's bar and see what a lead there sees.
3. **Hide it, but let her switch it back on.** `include_weak=true`.
4. **Admin sets the benchmark per unit**, rather than 40 being hardcoded.
   `Profile.min_fit_percent`, editable in `/admin` as "Min fit %".

**Why the escape hatch is not optional:** once the matching engine scores
automatically, the weak rows are how somebody notices it scoring *badly*. A
permanent filter makes a broken engine look like a quiet week.

**A missing profile means no bar (0), never the model default.** A unit whose
profile row is absent shows everything rather than silently hiding everything on
account of configuration nobody ever set.

### The side effect that mattered more than the feature

Every seeded opportunity is scored for both seeded units, so before this landed
every account saw the same 8 rows and neither seat could honestly claim
row-level scoping worked. Now `lead.takeout` sees **3** and `member.foundation`
sees **8**, on the same screen at the same moment. Tony has screenshotted it.
That caveat had been in every report for a day and is now retired.

---

## `app/scoring.py` — new, and the reason it exists

`priority.py` and the detail endpoint had **independently implemented the same
joint-pitch rule and disagreed**. The radar announced "Joint pitch: Great African
Museum Initiative"; you clicked through and the detail page said nothing,
because it read a stored `is_joint_pitch_candidate` column that defaults to
False and that **nothing has ever written**. Tony found it and — correctly —
refused to compute it client-side, which would have made three implementations.

The rule now lives in exactly one module: `viewer_scope`, `unit_bars`,
`clears_bar`, `joint_pitch_scores`, `joint_pitch_note`, and
`JOINT_PITCH_FLOOR = 60`.

Detail computes it live but **a stored `True` still wins**, so the matching
engine can later assert a joint pitch the simple threshold would miss. Today
nothing sets it.

---

## Schema changes without migrations — the precedent set

There is still no Alembic. `SQLModel.metadata.create_all` creates missing
**tables** and never adds **columns**, which means adding `min_fit_percent`
would normally mean deleting the database — and both seats plus Michaella had
live sessions against it.

What was done instead, and what to copy:

1. Back up `data/tm_bi.db`.
2. `ALTER TABLE profile ADD COLUMN min_fit_percent INTEGER NOT NULL DEFAULT 40`.
3. Add a **drift check** — `app/db.py::_check_schema_drift()`, called from
   `init_db()`. If a model has a column the table lacks, boot fails loudly
   naming the missing columns and the two recovery paths.

That third step is the point. The failure mode without it is a server that
starts fine and then 500s on one endpoint, which is much harder to read than a
refusal to boot.

**Alembic before any real deployment.** This is a two-seat workaround, not a
practice.

---

## Test accounts — now opt-in, and why that changed

Four accounts exist to prove the permission rules actually hide something (an
admin is the worst possible account for that — it is never filtered):

| Username | Role | Scope | Units |
| --- | --- | --- | --- |
| `director` | director | all | none |
| `lead.takeout` | lead | own_units | Takeout Media |
| `lead.dual` | lead | own_units | Takeout Media + TM Foundation |
| `member.foundation` | member | own_units | TM Foundation |

They were originally seeded **opt-out with the password hardcoded in the repo**,
and `run_seed` runs from the lifespan on every boot. That meant deploying to
staging would silently create a director account, scope `all`, with a password
sitting in the source tree — while the admin account got a generated password
printed once. The tunnel is public.

Now: `seed_test_accounts()` returns `[]` unless `TM_TEST_PASSWORD` is set, with
a 12-character minimum and no default.

```sh
TM_TEST_PASSWORD="<12+ chars>" uv run uvicorn app.main:app --reload
```

**Ordering trap:** it must run *after* `seed_admin_user`, which bails if any
user already exists — autoflush would otherwise show it the test users and it
would skip the admin.

---

## The camelCase parameter, and a contract decision

`?businessUnitId=2` used to return **200 with the full unfiltered list**.
FastAPI silently ignores an unrecognised query parameter, so the wrong answer
looked exactly like the right one. Every response body is camelCase, so reaching
for it is the natural mistake — **both agents made it.**

The endpoint now accepts both spellings, hidden from the schema. snake_case
remains the documented one.

**Contract #2 v5 says camelCase is "silently ignored — verified both ways", so
it is now inaccurate on that point. It is deliberately NOT being fixed.** The
reasoning:

- Todo #2 is **verified** — Tony ran the full browser pass against v5 with
  screenshots. Reopening drops it out of verified and costs him a re-run.
- The contract is now **stricter than the code, not looser**. Anyone who trusts
  it sends snake_case, which works. The original trap produced silent wrong
  answers; this produces right answers either way. Nobody can be misled into a
  broken state.

If #2 is reopened for any other reason, fold this line in then. Do not reopen a
verified deliverable for it alone.

---

## Contract state

| Todo | State |
| --- | --- |
| #1 Auth and access control | **verified** (contract v3) |
| #2 Opportunities: radar, list, detail | **verified** (contract v5) |
| #3 Unit profiles and source management | contract v1 proposed, signed by backend, awaiting frontend |
| #4 Source import: 81 platforms | contract v2 proposed, signed by backend, awaiting frontend |

---

## Open items, roughly by priority

- **#3 v1 and #4 v2 need Tony's signature.** Nothing blocks him; he had not got
  to them.
- **The exclusion mechanism is unbuilt and unplaced.** Anthony's decision: keep
  all 81 sources, exclude at the **opportunity** level after crawling, not at
  import. *"Like cancelling the newspaper because you don't read the jobs page"*
  — Devex carries tenders AND jobs; drop the site and you lose the tenders. He
  wants it **configurable, not hardcoded** — scholarships, jobs and residencies
  are the first three entries, not the whole list.
  This makes todo #4 **simpler** than contracted (a clean import of all 81, no
  exclusion logic). The mechanism probably belongs with the crawler as its own
  deliverable #5 — without a crawler there is nothing to filter.
- **`neverShow` must be reconciled with it.** Takeout Media's profile already
  reads "opportunities under roughly NGN 20m" and suppresses **nothing**. It is
  the same feature one level down: global + category-based vs per-unit +
  value-based. Building the crawler exclusion without looking at `neverShow`
  produces two systems that do the same job and disagree.
- **Alembic**, before anything real is deployed.
- **`Source.scope` still reads `takeout | foundation | both`** — vocabulary from
  the two-unit era, now that there are five. `is_aggregator` and provenance are
  contracted in #4 and not yet on the model.
- **`member` holds `scan:run`** — an ordinary team member can trigger a crawl.
  Probably unintended; it is a seeding decision in `app/rbac.py`, so it is
  changeable, but the frontend draws or hides that control off it.
- **The 401/403 existence oracle in login** is *deliberately* kept and commented.
  A deactivated account answers 403 "account is deactivated" where an unknown one
  answers 401, so the pair reveals which usernames are real. Todo #1's LOCKED
  contract documents that distinction on purpose, so a deactivated user is not
  told their password was wrong. Collapsing it is the more private choice and
  needs a **new contract version**, not a quiet change.
- **`list_profiles` is not read-scoped.** Writes are. Deliberate for now — the
  frontend needs `minFitPercent` to word its below-the-bar empty state, and
  profiles are not commercially sensitive the way rejection reasons are. Revisit
  if that stops being true.
- **`Decision.user_id` exists on the model and is never written.** Attribution is
  permanently NULL.

---

## Two traps that cost real time

**Probing write routes with a deliberately invalid body is not safe.** I assumed
a permission gate rejects before validation. That is true for POST and **false
for PATCH/PUT/DELETE**. `DELETE /api/sources/1` returned 204 and really removed
AfDB DACON; it was restored from `seed/sources.json` with its original id. Read
the route before probing it, or probe against a copy of the database.

**Check what actually happened before narrating why.** I spent a long stretch
describing the server as being killed by something external and mysterious.
A supervisor script that logged each death with its decoded signal proved that
**five of the six kills were my own `kill` commands** to reload code. The log
was worth more than the theory.

---

## For whoever is briefing Michaella

In her language, what changed overnight:

- **Before, anyone who found the web address could read everything** — every
  opportunity, every rejection reason — without signing in. Now you need an
  account, and what you see depends on who you are.
- **The system now respects the "don't bother me with bad matches" rule.** If
  something scores below your unit's bar it stays out of your list, and there is
  a tick box to show them anyway when you want to check.
- **You set that bar yourself**, per unit, in the admin dashboard. It starts at
  40%.
- **The dashboard and the list finally agree.** Before, the summary tiles
  counted the whole company's opportunities even when your list only showed
  yours.
- **Joint pitches show up on the opportunity page**, matching what the dashboard
  says. Previously the dashboard announced a partnership and the page it linked
  to didn't mention it.
