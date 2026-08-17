# Session handoff — 2026-08-16 — Task identity, RBAC handover to the frontend

Written from the **backend** seat. This is the SECOND backend handoff dated today —
the earlier one, `2026-08-16_backend-rbac-scoring-and-contracts.md`, is the deep
reference on what the service does and why. **Read that one first if you need the
architecture.** This one covers a short session that built no features and instead
surfaced a blocking problem with the sys-buddy task, handed the frontend the RBAC
data they need, and moved some files around.

Nothing in `app/` was modified this session. `git status` changes under `backend/`
are all from previous sessions.

---

## Start here tomorrow

```sh
cd backend
TM_SECRET_KEY="tmglobal-dev-shared-key-do-not-use-in-prod" \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
curl -s http://127.0.0.1:8000/api/health     # {"status":"ok"}
```

**The server is NOT running as of the end of this session** — it was started mid-session
and then killed externally about forty minutes later. The log shows a clean shutdown, no
traceback, every request 200 beforehand. Nothing is listening on 8000. It was not
restarted because the kill looked deliberate and there was no instruction either way.

Credentials are in the other handoff, `2026-08-16_backend-rbac-scoring-and-contracts.md`.
They were verified working this session (see below). Deliberately not duplicated here.

**Do not delete `backend/data/tm_bi.db`.** It survived this session intact (155 KB). A
missing DB reseeds and prints a NEW random admin password once, which would invalidate
the credential the frontend is currently signing in with.

---

## THE BLOCKING PROBLEM: we are on the wrong sys-buddy task

This is the thing to settle before anyone builds.

The broker this session answers to task **`test-drive-2-e0b5`**, and `get_todos()`
returns an **empty list**. Both of yesterday's handoffs describe task
**`test-drive-8b12`** with five accepted todos and contracts locked on #1 and #2.

| | Handoffs describe (`8b12`) | Live broker (`e0b5`) |
| --- | --- | --- |
| Todos | 5, all accepted by both seats | **0** |
| Contracts | #1 v1 locked, #2 v2 locked | none |
| staging_url | null, "humans haven't set it" | `http://localhost:8000` |
| Seats | frontend / backend / guest | same three |

**This is confirmed from both sides.** The frontend agent independently reported an
empty `get_todos()` and said they have seen a dashboard screenshot of `8b12` showing
all five todos and the locked contracts. So it is not a permissions quirk or a stale
read — the two sessions are pointed at a different task from the one the work was done
under.

**Probable cause.** Anthony re-registered the sys-buddy MCP server at the start of this
session:

```sh
claude-personal mcp remove sys-buddy
claude-personal mcp add --scope local --transport http sys-buddy \
  http://127.0.0.1:8787/mcp --header "Authorization: Bearer sbk_..."
```

Task and role are stamped from that bearer token, never declared. A new token means a
new task. `--scope local` also keys the registration to the exact directory it was run
in — the entry landed under `projects["/Users/anthonynta/dev/mikeh_app"]`, and there is
no entry for `backend/` at all.

**Decision needed from the humans:** restore the `8b12` token, or rebuild the board on
`e0b5`. If rebuilding, **port todo #2's spec deliberately** — v2 exists only because the
frontend declined v1 for three specific reasons (no priority-actions endpoint,
pre-formatted money string, no per-unit filter). Re-proposing from memory loses those
fixes. All three are described in the other handoff.

**Both seats have agreed in writing not to build against a contract neither can read.**
Everything below is groundwork, not work against a signed shape.

---

## What was actually verified, and how

All against the live instance while it was up, not from documentation:

- `GET /api/health` → `{"status":"ok"}`
- `POST /api/auth/login` with `{"identifier":"admin","password":"..."}` → **200**,
  `tokenType: bearer`, `expiresIn: 43200` (12h). The password from the older handoff
  **works** — checked before sending it to the frontend rather than trusting the note.
- `GET /api/auth/me` → returns `id, username, email, fullName, businessUnits` (empty
  array for admin), and `role` as an object carrying `id, name, label, scope, isSystem,
  permissions`. `role.permissions` is the flat codename list.
- **40 permission codenames** confirmed: 9 resources × 4 CRUD, plus `scan:run`,
  `report:send`, `opportunity:export`, `admin:access`.
- Role expansion computed from `app.rbac`: **admin 40, director 29, lead 13, member 8**.
  admin/director scope `all`; lead/member scope `own_units`.
- `openapi.json` → **24 routes** under `/api`.
- `GET /api/priority-actions` → a flat JSON **array**; each row is
  `type, title, description, opportunityId`, `type` ∈ {Opportunity, Partnership}.
- **Only ONE user is seeded: `admin`.** Queried the DB directly. See the gap below.

Not verified: the test suite was not run this session (the other handoff says 56 passing).
No UI was looked at from this seat.

---

## The frontend is rebuilding the app shell, and asked for RBAC

Anthony wants `/app` to become a proper dashboard: top navbar removed, navigation moved
to a left side menu. The frontend owns the codename→nav mapping (the API deliberately
returns **no** navigation array, so adding a screen never needs a backend deploy). They
asked for the authoritative permission data because their current seven items came from
a todo #1 contract on a task neither seat can read.

Sent them (message 839): the `/me` shape, the full 40 codenames, per-role holdings, and
confirmation that **all seven of their nav gates exist** in the real 40 — no typos, which
is the check that matters most since a typo silently hides a nav item forever.

### Three things found that they had not asked about

1. **Only the `admin` account exists.** The `director`, `lead` and `member` roles are
   seeded with correct grants, but no user holds them — so the frontend **cannot** sign
   in as a non-admin and watch the menu collapse. Admin is the least representative
   account for this, because an admin is never filtered. Offered to create four:
   a director, a lead in one unit, a **lead in two units** (the client's real case, and
   the one most likely to break assumptions), and a member. **Awaiting Anthony's go.**
2. **The Sources gate is split.** `lead` and `member` hold `source:read`, but only
   director and admin hold `source:create/update/delete`. The frontend has folded
   Sources into one "Profile and Sources" screen behind `profile:read`, so a lead would
   be shown an editor they cannot use.
3. **`member` holds `scan:run`.** A team member being able to trigger a crawl looks
   unintended. This is a seeding decision in `app/rbac.py`, not a contracted shape, so
   it can change — flagged rather than silently fixed, because it is the frontend's menu
   that would show or hide the control. **Awaiting Anthony's answer.**

Also suggested grouping the sidebar as **Intelligence / Configuration / Administration**,
since the third group vanishes entirely for lead and member and gives them a visible,
testable collapse. Their constraint — nav driven by codenames, never role names — is
correct and worth preserving.

---

## Credentials: a decision that was made, so it does not get re-argued

Anthony instructed that the dev login be sent to the frontend over the broker. Objection
raised once (broker rule 6 — messages are persisted and rendered to every viewer token,
and the `guest` seat is Michaella, the client). He reaffirmed twice. **It was sent, and
that is settled.** The reasoning: localhost instance, dummy seed data, both agents on the
same machine, and the password already sits in plaintext in the repo.

Two things a cold reader should still know:

- The frontend agent independently asked us **not** to paste it, in a message that
  crossed ours in flight. They wanted the file path instead. Their objection was
  reasonable; it was simply overruled by their own human's counterpart.
- The other handoff notes this **already happened once before** and recommended rotating
  the password. That recommendation still stands and has not been acted on. Set
  `TM_ADMIN_PASSWORD` before a reseed if you want a known value.

This approval covers the **local dev credential only**. A production secret, an API key,
or the sys-buddy bearer token is a fresh decision, not an assumed yes.

---

## Housekeeping done this session

- **Session notes moved.** Each agent now keeps handoffs in its own top-level directory.
  `2026-08-16_backend-rbac-scoring-and-contracts.md` → `backend/sessions/`. The frontend
  agent made the mirror move to `frontend/sessions/` at the same time (staged as a git
  rename). The repo-root `sessions/` folder is now **empty and belongs to nobody** — do
  not recreate it.
- **The two agents share a memory directory**, keyed on
  `/Users/anthonynta/dev/mikeh_app`. Discovered when a `MEMORY.md` write was rejected as
  stale because the other session had just written it. It held a memory asserting
  "my sys-buddy seat is frontend" — stored as a project-wide fact, but true only of that
  session. Replaced with one recording that **seat is stamped from the session's MCP
  token** and `roster()` is the authority. Expect write races in that directory.
- Anthony's shorthand (`ccw`, `rccw`, `cfs`, `cfd`/`cds`) was saved to memory, including
  the two traps: `ls` is aliased to **eza** whose `-t` sorts by field not time, so use
  `/bin/ls -t`; and screenshots live in `~/dev/screen shots` (two words, needs quoting)
  while downloads is `~/dev/downloads` (one word).

---

## Roster, as of end of session

| Seat | Name | Joined | Pre-flight |
| --- | --- | --- | --- |
| backend | host | yes | **passed** |
| frontend | tooney | yes | **passed** |
| guest | — | **no** | — |

An earlier read showed frontend as `pending`; they corrected it and a re-read confirms
**passed**. The `guest` seat (Michaella, the client) has still never joined — worth
watching, because an unjoined seat is the thing that silently stalls a task.

---

## Where to pick up, in order

1. **Settle the task identity.** Nothing else is worth doing first. Restore the `8b12`
   token or rebuild the board on `e0b5`, and if rebuilding, port todo #2 v2 deliberately.
2. **Restart the server** if the frontend is working — their Vite proxy on `:5173`
   forwards `/api` to `:8000` and they are actively driving a browser at it.
3. **Answer the two open questions**: create the four scoping test accounts? and is
   `member` holding `scan:run` intended?
4. Then the real backlog from the other handoff, unchanged: import the client's 81
   sources from `Nigeria_Africa_Opportunity_Platforms.xlsx` (**merge, do not replace** —
   4 current seeds would be lost, including the only JSON API source), then the crawler,
   then the LLM matching engine, which is the actual product.
