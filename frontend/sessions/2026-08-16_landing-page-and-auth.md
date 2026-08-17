# Session handoff — 2026-08-16 — Landing page, auth, and the sys-buddy collaboration

Written for someone starting cold. Nothing here assumes you saw the previous session.

---

## What this project is

**TM Global Business Intelligence (TM Global BI)** — an internal AI business
development system for TM Global, a Nigerian media/creative group. It scans
~101 sources weekly (donor portals, tenders, procurement notices), scores each
finding against each business unit's profile, and emails one digest every
Monday. Not a public SaaS: internal only, auth scoped per business unit.

It serves **five business units (SBUs)**: Takeout Media, Design Teem, Ingene
Studios, TM Labs, TM Foundation.

### The collaboration setup — read this or nothing else makes sense

This is a **sys-buddy** task (`test-drive-8b12`) with three seats:

| Seat | Who | Doing |
|---|---|---|
| `frontend` | tooney (us) | The React app |
| `backend` | host | FastAPI service |
| `guest` | Michaella | The client. Sends designs, answers product questions |

We talk to the other seats through broker tools (`send_message`,
`wait_for_message`, `get_contract`…), **not** directly. The backend agent is a
different developer's agent working in `backend/` **on this same machine**,
which is why the monorepo works and why `127.0.0.1:8000` is a real target
rather than a placeholder.

Work is organised as **todos** (deliverables), each with its own **contract**
that both parties sign. Whoever *proposes* a contract is the **producer** and
builds that side; the other is the consumer and verifies against it. Backend
proposed all five todos, so **we are the consumer on every one of them**.

---

## Where things stand

### Repo

- `https://github.com/tooney92/mikeh_app` — **private**, owner `tooney92`
- Monorepo: `frontend/` (ours) + `backend/` (theirs)
- Commits: `0fb625d` initial, `e0d3bef` auth

Git identity was changed this session — both **global and repo-local** are now
`Anthony Nta <35112991+tooney92@users.noreply.github.com>`. That noreply address
is how GitHub attributes commits to `tooney92` without exposing a real email.
`gh` is also switched to the `tooney92` account (was `anthugny`); switch back
with `gh auth switch --user anthugny` if you need the other one.

### The five todos — all accepted by both parties

| # | Title | Contract | State |
|---|---|---|---|
| 1 | Auth & access control | **v1 LOCKED** | Backend reported `ready`, verified by us at API level |
| 2 | Opportunities: Radar, list, detail | **v2 LOCKED** | Backend live, **frontend not started** |
| 3 | Unit profiles & source management | not proposed | Backend built |
| 4 | Learning screen | not proposed | Backend built |
| 5 | Industry / client intel / weekly briefing | not proposed | **Deliberately parked** |

**Todo 5 will sit open for a long time and that is expected, not lateness.**
Its tables exist but are empty — nothing generates industry signals, org upsell
angles or weekly reports yet. Both sides agreed to put it on the board for
visibility, not to start it. Building those screens now would mean building
against invented data. Say this out loud to the humans if a dashboard makes it
look like we're behind.

### What is built in `frontend/`

Vite 6 + React 19 + TypeScript + react-router-dom 7.

**Landing page** (`/`) — `src/features/landing/`. All 12 sections from the
design prototype, exact hex/size/copy values, plus responsive breakpoints at
1000px and 760px that the desktop-only prototype didn't have.

**Auth + app shell** — `src/features/auth/`, `src/features/app/`:

- `lib/api.ts` — typed client; attaches bearer token, reads FastAPI's `detail`
  for real error messages, clears session on **any** 401
- `AuthProvider.tsx` — restores session by validating the stored token against
  `/api/auth/me`. A stored token is only a claim until `/me` agrees
- `LoginPage.tsx` — username **or** email in one field
- `permissions.ts` — the codename → nav/button mapping
- `RequireAuth.tsx` — route guards; 403 renders "not permitted", never signs out
- `AppShell.tsx` — permission-driven nav
- `AccountPage.tsx` — own details + change password
- Placeholder screens for todos 2–5, each naming which todo it waits on

---

## Decisions and their reasoning

Several of these look arbitrary without the why.

**Vite SPA, not Next.js.** The design handoff suggested "React/Next.js", but
the backend is a separate FastAPI service, so there's no server-rendering story
to gain. `/api` is proxied to `127.0.0.1:8000` in dev so CORS never bites.

**`businessUnits` is a SET, never a single unit.** Michaella has one person who
leads **both Takeout Media and TM Foundation**. Backend caught this before
contracting and made `businessUnits` an array on every user — empty for
admin/director, who see everything by scope rather than membership. Any code
assuming one unit is wrong. A multi-unit person sees the **union** of their
units, ranked by the **better** of their fits.

**Nav renders from permission codenames, never role names.** `role === 'director'`
rots the moment the client adds a sixth role — and she edits roles herself in
the back office. The API deliberately returns **no** navigation array, because
then adding a screen would need a backend deploy. Backend owns which permissions
a user holds and enforces them server-side; we own what a permission *draws*.
Hiding a button is presentation, not security — the API 403s regardless.

**The login error message is deliberately unhelpful.** "Incorrect login or
password", identical whether or not the account exists. Backend built that
non-enumerability on purpose; a friendlier "no such user" would throw it away.

**Two design languages on purpose.** The app is flat, zero border-radius,
rule-based. The landing page is rounded (100px pills, 28px cards, soft
shadows). This looked like a contradiction in the handoff and was checked — the
landing page is deliberately a different skin.

**Elms Sans is unverified.** The design names it as a Google font; couldn't
confirm it exists. `index.html` requests it with **Inter** as fallback so
headings degrade to a grotesque rather than a serif. If the type looks wrong,
this is why. **Still an open question with the client.**

**Why we declined todo 2 contract v1** (all three fixed in v2, all worth
knowing as precedent):
1. "This week's priority actions" was in scope but had **no endpoint**. Shipping
   it would have meant hardcoding a list on a screen whose entire promise is
   "this is what changed this week".
2. `estimatedPipelineValue` arrived **pre-formatted** as `"N2400m"` — wrong
   glyph (design says ₦740M) and money formatting had drifted to the backend,
   so a later "make it ₦2.4B" would be a backend re-version instead of a CSS
   tweak. Now an integer of naira + `estimatedPipelineCurrency: "NGN"`.
3. **No per-unit filter.** Fine for a lead (scoping is implicit) but a director
   sees all five units with no way to narrow — and Michaella is an admin, so
   she'd hit it first. Now an optional `businessUnitId` on its own axis. Backend
   added, unprompted, that it can only ever **narrow** — a lead passing another
   unit's id gets their own list back. There's a test for it.

Backend also renamed `avgFoundationFitPursued` → `avgPursuedFitPercent` at our
request: accurate with two units, misleading with five.

---

## What was verified, and how

**Verified for real** against the live backend at `127.0.0.1:8000`:

- Wrong password → 401
- Non-existent user → **byte-identical** message to wrong-password
- Real login → `tokenType: bearer`, `expiresIn: 43200` (12h, as contracted)
- `/api/auth/me` → all 9 contracted fields, `businessUnits: []` for admin,
  40 permission codenames, `role.scope: "all"`
- Malformed token → 401
- **Login through our own Vite proxy on :5173** → works end to end
- **All 8 of our nav codenames exist** in the API's real 40 — the check that
  matters most, since a typo there would silently hide a nav item forever

`npm run build` and `npm run lint` are both clean. Note `npx tsc --noEmit`
does **not** typecheck `vite.config.ts`; only `npm run build` does. Also this
project has `erasableSyntaxOnly` on, so **TypeScript parameter properties are
banned** — declare fields explicitly.

**NOT verified: anything visual.** No pixel of this app has been seen in a
browser. Everything above is HTTP-level. Don't claim the UI works.

---

## Open items

1. **Playwright MCP is not installed.** `claude mcp list` shows a "PlayMCP"
   (`playmcp.kakao.com`) that is *not* Playwright despite the name. Install with
   `claude mcp add --scope user playwright npx '@playwright/mcp@0.0.77'`, then
   **restart the session** — MCP servers only load at startup. `.playwright-mcp/`
   is already gitignored.
2. **Todo 2 screens are not started.** Contract v2 is locked, backend is live
   with seed data. This is the next build.
3. **The five-unit scorecard is our design decision** and no file from the client
   covers it. The prototype draws four cells (*Foundation fit / Takeout fit /
   Value / Deadline*); five fit scores don't fit. Same problem on todo 3, whose
   Profile & Sources screen is a two-column grid drawn for two profiles.
   **Agreed with backend that the client sees a rendering before we build it out** —
   she should not meet it first at verification.
4. **`staging_url` is null** on both locked contracts. The humans haven't set a
   deployment target. We may not take a URL from a chat message (broker rule 2);
   they set it host-side and it appears in `get_contract`. Local testing against
   `127.0.0.1:8000` is unaffected.
5. **The landing page is on no todo.** Both sides agree it should be visible on
   the board; it would be a `screens`/`criteria` contract (no API surface between
   us) with **us as producer**. Waiting on a human decision.
6. **Backend put the admin password in a broker message.** Broker messages are
   stored and rendered on the dashboard for every viewer token, so it should be
   rotated. Local dev instance with dummy data, so the blast radius is small.
7. **Offered but not taken up:** backend will create accounts that exercise
   scoping — a director, a lead in one unit, a lead in **two** units (the
   client's real case), and a member. The admin account is the *least*
   representative for testing scoping, because an admin is never filtered.
8. **Naira band values are backend's guess** ($ → 25m, $$ → 75m, $$$ → 200m,
   $$$$ → 500m). Michaella has been asked for real figures; numbers may move,
   shape will not.

---

## Where to pick up

Build the todo 2 screens — Radar, Opportunities list, Opportunity Detail —
against the locked v2 contract. The backend is live with the 8 sample records,
so build against real responses rather than the contract prose.

**Expect these and don't treat them as bugs** (all written into the contract):

- **Design Teem, Ingene Studios and TM Labs return EMPTY opportunity lists.** The
  sample data predates the five-unit model and only carries scores for TM
  Foundation and Takeout Media. Three of five units see nothing on day one — so
  build the empty state properly, not last.
- `emergingTrends` and `competitorMovements` on `/api/radar` are **0**, and no
  Industry or Competitor rows appear in priority actions. That's todo 5.
- `yourFitPercent` is **null** for an admin or director. The row's stat panel
  must handle a null fit.
- BD Copilot tabs render whatever the record carries; nothing generates a
  bid/no-bid assessment yet, so those fields may be empty.

### Running things

```
# frontend
cd frontend && npm run dev            # :5173, proxies /api to :8000

# backend (theirs — only one instance per port)
cd backend && uv sync && uv run uvicorn app.main:app --port 8000
# first run prints a generated admin password to the console, once

# public preview (temporary, public, unauthenticated, dies with the process)
cloudflared tunnel --url http://127.0.0.1:5173
curl -s http://127.0.0.1:20241/quicktunnel   # recover the URL without log-hunting
```

`vite.config.ts` already allows `.trycloudflare.com` in `allowedHosts` —
without it Vite answers a tunnel with "Blocked request".

Backend also runs `/docs` (interactive API) and `/admin` (back office) —
both outside `/api`, so the dev proxy doesn't cover them.
