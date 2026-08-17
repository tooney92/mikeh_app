# TM Global Business Intelligence — Backend

FastAPI + SQLite (via SQLModel). Serves the data behind the 8 screens in the
design handoff.

## Run

```sh
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

- API docs (Swagger): http://127.0.0.1:8000/docs
- Admin dashboard: http://127.0.0.1:8000/admin

The database is created and seeded on startup — idempotently, so restarting
never duplicates rows.

```sh
uv run python -m app.seed --reset   # wipe and reseed
uv run pytest                       # smoke tests
```

## Layout

```
app/
  main.py      FastAPI app, CORS, router wiring
  admin.py     sqladmin views + login gate, mounted at /admin
  security.py  Argon2 hashing, JWT create/decode
  rbac.py      the permission matrix + its seeder
  deps.py      current_user / optional_user / requires(codename)
  db.py        engine + session dependency (data/tm_bi.db)
  models.py    tables, straight from the handoff's Data Model
  schemas.py   wire shapes (camelCase)
  seed.py      loads seed/*.json
  routers/     auth · radar · opportunities · decisions · profiles · sources · scan
seed/          the four JSON files from the design bundle
```

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | |
| POST | `/api/auth/login` | `{identifier, password}` — identifier is username **or** email |
| GET | `/api/auth/me` | current user + their business unit |
| POST | `/api/auth/change-password` | own password; requires the current one |
| GET | `/api/users` | needs `user:read` |
| POST | `/api/users/{id}/reset-password` | needs `user:update`; no current password needed |
| GET | `/api/roles` | needs `role:read` — role catalogue + granted permissions |
| GET | `/api/permissions` | needs `role:read` — every codename that exists |
| GET | `/api/radar` | the six stat-strip counts |
| GET | `/api/business-units` | the five SBUs |
| GET | `/api/opportunities` | `?filter=` + `?limit=` (use `limit=5` for Top 5) — **scoped to the caller's unit** |
| GET | `/api/opportunities/{id}` | every unit's score + the latest logged decision |
| POST | `/api/decisions` | `{opportunityId, decision, reason?}` |
| GET | `/api/decisions` | newest first |
| GET | `/api/learning` | aggregates, computed over Decision × Opportunity |
| GET | `/api/profiles` | one scoring profile per unit — five |
| PUT | `/api/profiles/{id}` | integer profile id |
| GET | `/api/organisations` | the 10 tracked orgs |
| GET/POST | `/api/sources` | `?active_only=true` on GET |
| PATCH/DELETE | `/api/sources/{id}` | PATCH toggles `active` |
| POST | `/api/scan` | starts a job, 202 |
| GET | `/api/scan/status` | poll for `running` → `complete` |

Filter keys: `everything`, `bid-now`, `watch`, `partnership`, `bd-leads`,
`international`. An unknown key is a 400. There are no per-unit filter keys —
unit filtering is implicit in who is asking.

## Per-unit scoring

Fit is **not** a column on the opportunity. `OpportunityScore` holds one row per
opportunity per business unit, carrying `fit_percent`, `win_probability` and a
joint-pitch flag. That is what makes the client's two rules work at once:

- **A list is scoped to your unit.** `GET /api/opportunities` returns only what
  your unit has a score for, ranked by *your* fit. Two units see the same
  opportunity in a different position. An admin has no unit, so they see
  everything ranked by the best fit across any unit, with `yourFitPercent: null`.
- **A detail page shows all five.** `GET /api/opportunities/{id}` returns every
  unit's score, best first — that is how a joint pitch becomes visible.

Scoping is driven by the bearer token when one is sent. These endpoints are not
gated yet, so an anonymous caller sees everything.

**Seeded scores are deliberately incomplete.** `opportunities.json` predates the
five-unit model and carries only `fitFoundation`/`fitTakeout`, so only TM
Foundation and Takeout Media get seeded scores. Design Teem, Ingene Studios and
TM Labs have none, and their profiles seed empty. Both stay that way until the
matching engine runs — inventing numbers for them would be worse than showing
nothing.

Decisions are `Pursue` / `Partner` / `Watch` / `Reject`; `Reject` requires a
`reason` (400 without one).

**The API speaks camelCase.** The design bundle's own JSON is camelCase and the
frontend is TypeScript, so one convention crosses the boundary; columns stay
snake_case. This is an assumption, not yet an agreed contract.

## Auth

JWT bearer tokens, 12-hour expiry. Log in with **either** username or email;
send the token as `Authorization: Bearer <token>`.

Passwords are **hashed** with Argon2, not encrypted — there is no key that turns
a stored hash back into a password. Nobody, admin included, can read an existing
password; an admin "reset" sets a new one.

Every user has a **role** (what they may do) and usually a **business unit**
(which rows they see, when their role's scope is `own_unit`). See RBAC below.
Deactivating a user (`is_active = false`) kills their live token on the next
request — `current_user` re-reads the row every time rather than trusting the
token's claims.

There is no signup page by design. Admins create accounts in `/admin`.

**Environment variables**

| Variable | Purpose |
| --- | --- |
| `TM_SECRET_KEY` | Signs tokens. **Required in production** — without it a fresh key is generated per boot, so every restart logs everyone out. |
| `TM_ADMIN_EMAIL` / `TM_ADMIN_PASSWORD` / `TM_ADMIN_USERNAME` | The first admin, created on first run only. With no password set, one is generated and printed to the console **once**. |

## RBAC

Roles and permissions are **data**, not constants — Michaella can edit the grid
in `/admin`. The declarative source is `app/rbac.py`.

**Two independent axes.** Folding them together is what makes permission systems
combinatorial, so they are kept apart:

- **`grants`** — what you may DO, as `resource:action` (Django's convention).
  9 resources × 4 CRUD actions, plus `scan:run`, `report:send`,
  `opportunity:export`, `admin:access` = 40 permissions.
- **`scope`** — which ROWS you see: `all` or `own_unit`. Not a permission; it
  filters the query.

A lead and a director both hold `opportunity:read` and see different rows. Had
visibility been encoded as `read_own` vs `read_all`, every future resource would
need both variants for every role.

| role | scope | can |
| --- | --- | --- |
| `admin` | all | everything, including users and roles |
| `director` | all | all data, cannot manage accounts |
| `lead` | own unit | read opportunities, log decisions, edit own unit's profile, run a scan |
| `member` | own unit | read opportunities, log decisions |

**Enforcement is server-side**, via `Depends(requires("user:update"))`. The
permission list returned by `/api/auth/me` decides what the frontend *draws* —
it is not a security boundary, since anyone can call an endpoint directly.

For the frontend: `/api/auth/me` returns the role plus a flat codename list, so
the UI asks `can('source:update')` rather than branching on `role === 'director'`.

**The seeder.** `sync_rbac()` runs on every boot. The permission *catalogue* is
authoritative, so adding a resource to `RESOURCES` creates its four permissions
automatically. Role→permission *assignments* are written only when a role is
first created — otherwise every restart would silently revert edits made in
`/admin`.

**Last-admin guard.** Any change that would leave nobody holding all of
`admin:access`, `role:update`, `user:update` is refused with an explanatory
error: deactivating, deleting or demoting the last admin, or stripping those
permissions from the only role that has them. Built-in roles cannot be deleted,
and the permission catalogue is read-only in `/admin` (it is generated).

## Admin

FastAPI ships no Django-admin equivalent, so `/admin` is [sqladmin][] — CRUD
over all 10 tables, with search, sorting, pagination and CSV/JSON export.
Configured in `app/admin.py`; `Profile` can't be created or deleted (exactly two
rows by design) and `ScanRun` is read-only (jobs start via `POST /api/scan`).

[sqladmin]: https://aminalaee.dev/sqladmin/

**Login required, admins only** — a non-admin with valid credentials is refused.
The user form has a masked `Password` field that hashes on save; the stored hash
is never rendered into the form, and leaving the field blank on an edit keeps
the existing password rather than wiping it.

It still talks to the database **directly**, bypassing endpoint-level rules — an
admin here can write state the API would reject. That is what a back-office tool
is for, and the reason only admins reach it.

## Not built yet

Scaffolded and honest about it, rather than faked:

- **Source crawler.** `POST /api/scan` records a real job lifecycle but does not
  fetch anything — `_run_scan` in `routers/scan.py` is the hook.
- **LLM matching engine.** Fit scores are the seeded values; nothing scores a new
  posting against the profiles yet.
- **Partnership suggestion, org monitoring, weekly report generation.** Tables
  exist (`WeeklyReport`, `IndustrySignal`, `Organisation.signal`/`upsell_angle`);
  nothing populates them, so `/api/radar` reports 0 trends and 0 competitor
  movements, and there is no `/api/briefing` or `/api/industry` endpoint.
- **Decision feedback into scoring.** Decisions persist and drive the Learning
  aggregates, but do not yet influence future fit scores.
- **Auth on the data endpoints.** Login works and a token scopes the response,
  but `/api/opportunities` and friends still answer anonymous callers — gating
  them is a one-line dependency swap (`optional_user` → `current_user`) once
  the frontend sends the header.
- **Source `scope`.** Still the old `takeout|foundation|both` string; needs to
  become which units a source serves.
