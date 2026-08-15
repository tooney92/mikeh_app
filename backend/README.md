# TM Global Business Intelligence — Backend

FastAPI + SQLite (via SQLModel). Serves the data behind the 8 screens in the
design handoff.

## Run

```sh
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Docs at http://127.0.0.1:8000/docs. The database is created and seeded on
startup — idempotently, so restarting never duplicates rows.

```sh
uv run python -m app.seed --reset   # wipe and reseed
uv run pytest                       # smoke tests
```

## Layout

```
app/
  main.py      FastAPI app, CORS, router wiring
  db.py        engine + session dependency (data/tm_bi.db)
  models.py    tables, straight from the handoff's Data Model
  schemas.py   wire shapes (camelCase)
  seed.py      loads seed/*.json
  routers/     radar · opportunities · decisions · profiles · sources · scan
seed/          the three JSON files from the design bundle
```

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | |
| GET | `/api/radar` | the six stat-strip counts |
| GET | `/api/opportunities` | `?filter=` + `?limit=` (use `limit=5` for Top 5) |
| GET | `/api/opportunities/{id}` | includes the latest logged decision |
| POST | `/api/decisions` | `{opportunityId, decision, reason?}` |
| GET | `/api/decisions` | newest first |
| GET | `/api/learning` | aggregates, computed over Decision × Opportunity |
| GET | `/api/profiles` | the two scoring profiles |
| PUT | `/api/profiles/{id}` | `id` is `takeout` or `foundation` |
| GET | `/api/organisations` | the 10 tracked orgs |
| GET/POST | `/api/sources` | `?active_only=true` on GET |
| PATCH/DELETE | `/api/sources/{id}` | PATCH toggles `active` |
| POST | `/api/scan` | starts a job, 202 |
| GET | `/api/scan/status` | poll for `running` → `complete` |

Filter keys: `everything`, `bid-now`, `watch`, `partnership`, `bd-leads`,
`foundation`, `takeout`, `international`. An unknown key is a 400.

Decisions are `Pursue` / `Partner` / `Watch` / `Reject`; `Reject` requires a
`reason` (400 without one).

**The API speaks camelCase.** The design bundle's own JSON is camelCase and the
frontend is TypeScript, so one convention crosses the boundary; columns stay
snake_case. This is an assumption, not yet an agreed contract.

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
- **Auth / multi-tenancy.** Single tenant, no auth.
