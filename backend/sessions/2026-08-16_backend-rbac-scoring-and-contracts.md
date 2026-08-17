# Session handoff — 2026-08-16 — Backend: RBAC, per-unit scoring, and contracts 1–2

Written from the **backend** seat, for someone starting cold tomorrow. There is a
companion handoff from the frontend seat, `2026-08-16_landing-page-and-auth.md`;
read both if you want the whole picture. This one covers everything under
`backend/` and the sys-buddy negotiation.

---

## Where to start tomorrow

The server is probably still running in the background on port 8000. Check:

```sh
curl -s http://127.0.0.1:8000/api/health          # {"status":"ok"}
cd backend && uv run pytest -q                     # expect 56 passed
```

If it is not running:

```sh
cd backend
TM_SECRET_KEY="tmglobal-dev-shared-key-do-not-use-in-prod" \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Dev login:** `admin` / `zfSDC8ehrGQhR3ud` at http://127.0.0.1:8000
(local dummy data only). Docs at `/docs`, back office at `/admin`.

**Careful:** if you delete `backend/data/tm_bi.db` the seed runs again and
generates a **new random admin password**, printed to the console once. Either
capture it, or set `TM_ADMIN_PASSWORD` before starting.

---

## The stack, and why

FastAPI + SQLModel + SQLite, managed with `uv`, on Python 3.14.

- **FastAPI** because the eventual crawler and LLM matching engine are Python
  work, and `/docs` gave the frontend a live reference to build against while we
  were still negotiating the contract.
- **SQLite** because the data is small and read-heavy. SQLModel sits on
  SQLAlchemy, so Postgres later is a connection string plus a migration tool.
- **sqladmin at `/admin`** — FastAPI has no Django-admin equivalent, and the
  client needs to create accounts and edit the permission grid herself.

There are **no migrations**. `SQLModel.metadata.create_all` runs on boot. Schema
changes so far have meant deleting `data/tm_bi.db` and reseeding. That is fine
now and will stop being fine the moment there is data anyone cares about —
Alembic is the obvious next step before any real deployment.

---

## What is built

Everything below is running and tested. **56 tests** in `backend/tests/`.

| Area | State |
| --- | --- |
| Auth: JWT, Argon2, login by username **or** email | done |
| RBAC: roles, permissions, editable grid, last-admin guard | done |
| Five business units, one profile each | done |
| Per-unit opportunity scoring | done |
| Multi-unit membership (one person, several units) | done |
| Opportunities list/detail, decisions, learning aggregates | done |
| Priority actions, radar stats, sources CRUD, scan job | done |
| Crawler, matching engine, industry signals, weekly email | **not started** |

---

## The three design decisions that matter most

Understand these and the rest of the code reads easily.

### 1. Fit is a row, not a column

The design bundle had `fitFoundation` and `fitTakeout` as columns on the
opportunity. That works for two organisations. The client then revealed there
are **five business units**, and columns would mean a migration per unit.

So `OpportunityScore` holds one row per `(opportunity, business_unit)` carrying
`fit_percent`, `win_probability`, `is_joint_pitch_candidate`, `joint_pitch_note`.

This is what lets both of the client's rules hold at once:
- a **list** is scoped to your units, ranked by *your* fit;
- a **detail page** shows *every* unit's score, best first — which is how a
  joint pitch becomes visible.

### 2. Grants and scope are separate axes

In `app/rbac.py`:

- **`grants`** — what you may DO, as `resource:action` (Django's convention).
  9 resources × 4 CRUD actions + `scan:run`, `report:send`,
  `opportunity:export`, `admin:access` = **40 permissions**.
- **`scope`** — which ROWS you see: `"all"` or `"own_units"`. **Not a
  permission.** It filters the query.

A lead and a director both hold `opportunity:read` and see different rows. If
visibility had been encoded as `read_own` vs `read_all`, every new resource
would need both variants for every role — that is the combinatorial trap this
avoids, and it is why there is no `read_own` codename anywhere.

### 3. Unit membership is a set

`User` has **no** `business_unit_id`. It has a `business_units` relationship via
the `UserBusinessUnit` link table, because the client has one person leading
**both Takeout Media and TM Foundation**. A single FK could only give them one
unit or (with scope `all`) all five, and neither is right.

Someone in two units sees the **union** of their units' opportunities,
deduplicated, ranked by the **better** of their two fits. There is a test that
pins this: `test_a_lead_of_two_units_sees_the_union`.

`/api/auth/me` therefore returns `businessUnits: [...]`, an array, empty for
admins and directors who see everything by scope rather than membership.

---

## Things that look like bugs and are not

Write these down anywhere you demo, because all four will be noticed.

1. **Three of five units return EMPTY opportunity lists.** `opportunities.json`
   predates the five-unit model and carries scores only for TM Foundation and
   Takeout Media. Design Teem, Ingene Studios and TM Labs have no scores, and
   their profiles seed **empty on purpose** — the matching engine cannot score a
   unit until somebody fills its profile in. Inventing numbers would be worse.
2. **`emergingTrends` and `competitorMovements` on `/api/radar` are 0.** Nothing
   generates `IndustrySignal` rows yet. Same reason no Industry or Competitor
   rows appear in priority actions.
3. **`yourFitPercent` is null for an admin or director.** They have no unit of
   their own. The list row's stat panel has to handle it.
4. **`winProbability` is null everywhere.** Only the engine will set it.

---

## The last-admin guard

`app/rbac.py` defines `CRITICAL = ("admin:access", "role:update", "user:update")`.
Any change that would leave **nobody** holding all three is refused with an
explanatory error: deactivating, deleting or demoting the last admin, or
stripping those permissions from the only role that has them. Built-in roles
cannot be deleted either.

This was tested by actually trying it in the browser — opening the admin role's
permission grid, deselecting all three, submitting. Result was a 400 and the
permissions intact. Worth re-testing the same way if you touch `app/admin.py`,
because the sqladmin hooks are easy to break silently.

**The permission catalogue is authoritative; role assignments are not.**
`sync_rbac()` upserts every codename on each boot (so adding a resource to
`RESOURCES` creates its four permissions automatically) but writes
role→permission mappings **only when a role is new**. That is deliberate: if it
re-asserted them every boot, any edit the client made in `/admin` would be
silently reverted on the next restart.

---

## sys-buddy state — where the collaboration stands

Five todos, all accepted by both seats.

| # | Todo | Contract | State |
| --- | --- | --- | --- |
| 1 | Auth and access control | **v1 LOCKED** | reported **ready**, backend live |
| 2 | Opportunities: radar, list, detail | v2 proposed, **signed by backend** | awaiting frontend signature |
| 3 | Unit profiles and source management | none | backend built, uncontracted |
| 4 | Learning | none | backend built, uncontracted |
| 5 | Industry, client intel, weekly briefing | none | **deliberately parked** |

**Todo 5 is parked on purpose.** Its tables exist and are empty; nothing
populates them. It is on the board for visibility, not to be built against.
Both seats agreed in writing that it will sit open a long time through nobody's
fault, so it does not read as lateness on the dashboard.

**Todo 2 v1 was declined by the frontend**, with three reasons, all correct. All
three are fixed in v2:
1. "This week's priority actions" had no endpoint — now `GET /api/priority-actions`,
   derived from real rows. Emits a `Partnership` row automatically when two or
   more units score ≥60 on the same opportunity.
2. `estimatedPipelineValue` arrived pre-formatted as `"₦2400m"` — now an
   **integer of whole naira** plus `estimatedPipelineCurrency`. Formatting money
   is the frontend's job.
3. No per-unit filter for scope `all` — now an optional `businessUnitId` query
   param. **It can only narrow.** A lead passing another unit's id gets their own
   list back; there is a test for that, because a param that narrows for one role
   and widens for another is how scoping springs a leak.

Also renamed `avgFoundationFitPursued` → `avgPursuedFitPercent` at the
frontend's request: with five units the old name argued with what it computes.

**Division of labour, agreed and written into contract 1:** backend owns which
permissions a user holds and enforces them server-side; frontend owns what a
permission *draws*. The API deliberately returns **no** navigation array,
because then adding a screen would need a backend deploy.

---

## Two mistakes I made, so you do not repeat them

**Pydantic auto-validating ORM relationships.** Twice, a 500 came from
`Model.model_validate(orm_object)` dragging in a relationship whose rows did not
match the schema (`scores`, then `role.permissions`). Fix both times was
`model_validate(obj.model_dump())` — SQLModel's `model_dump()` returns columns
only. If you add a relationship to a model that a response schema also names,
expect this.

**Test-order dependencies.** An admin resetting a password in one test broke a
later test's login. Fixed with a dedicated `pwtarget` user that exists only to be
reset. Also, an early fixture created users with **no role at all** and passed by
accident, because "no role" and "member" both scope to a unit — it proved nothing
until roles were assigned properly.

---

## What is next, in order

1. **Import the client's 81 real sources.** She sent
   `Nigeria_Africa_Opportunity_Platforms.xlsx` (in `~/dev/downloads`). 81 rows,
   all unique HTTPS URLs, clean. **Merge, do not replace** — 11 domains overlap
   with the current 15 seeds but 4 would be lost, including
   `search.worldbank.org`, the only JSON API source. Two things to build in:
   an `is_aggregator` flag (her notes say some entries are discovery platforms,
   not issuers, so the crawler must chase links rather than parse postings), and
   the rule that scholarships, jobs and residencies are ignored.
2. **The crawler**, then **the LLM matching engine**. The engine is the product.
3. Contract todos 3 and 4 whenever the frontend wants them.
4. Industry signals, client tracking, weekly email — todo 5's prerequisites.

**Before any real deployment:** add Alembic, set a real `TM_SECRET_KEY` (without
it a fresh key is generated per boot and every restart logs everyone out), and
tighten CORS beyond `localhost:5173`.

---

## Open questions for the client

`QUESTIONS.md` at the repo root is the running log — answered ones carry the
date and what changed as a result. The two sharpest:

- **Should weak-fit opportunities appear at all?** Any score makes an
  opportunity visible today, however low. Takeout Media currently sees a 12%
  match. With eight sample records that is untidy; with a crawler finding dozens
  weekly it is noise.
- **Should the "Never show me" profile field actually suppress anything?**
  Takeout's already says "opportunities under roughly NGN 20m". Nothing acts on
  it, and it reads like a filter she expects to work.

Also still needed: the **thirteen names and work emails** so real accounts can
be created.
