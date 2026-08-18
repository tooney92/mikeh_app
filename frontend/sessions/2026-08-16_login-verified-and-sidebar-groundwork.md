# 2026-08-16 — Login verified in a real browser, sidebar groundwork, and an unresolved task-identity problem

**Seat:** `frontend` (sys-buddy display name "tooney")
**Working dir:** `/Users/anthonynta/dev/mikeh_app/frontend`
**Broker task this session was connected to:** `test-drive-2-e0b5`

Read this before touching anything. The single most important item is
[The task-identity problem](#the-task-identity-problem-unresolved-and-blocking) — it
determines whether the contracts this codebase was built against are readable at all.

---

## Where things stand in one paragraph

Login works end-to-end and was proven in a real browser, not asserted. Anthony then
asked for `/app` to become a proper dashboard — top navbar removed, navigation moved
to a left side menu — and told me to ask the backend what the side menu should
contain. That question is sent and **unanswered**. No code has been changed for the
sidebar yet. Separately, both agents discovered that the broker task we are connected
to has no todos and no contracts, while the codebase and yesterday's handoffs describe
a different task that has five todos and two locked contracts. Nobody has resolved
that.

---

## What actually changed on disk

Very little, deliberately. This session was verification and groundwork.

1. **`frontend/sessions/` created**, and
   `sessions/2026-08-16_landing-page-and-auth.md` moved into it with `git mv` so
   history follows the file. **The rename is STAGED BUT NOT COMMITTED** (`R ` in
   `git status`). Either commit it or be aware it is sitting in the index.
   *Why:* Anthony established that each agent keeps handoffs inside its own top-level
   directory — the frontend seat writes to `frontend/sessions/`, the backend seat to
   its own. A single shared root `sessions/` mixed both sides and made authorship
   unclear.
2. **Two screenshots written to the `frontend/` root** by Playwright:
   `login-page.png` and `after-login-app.png`. These are build artefacts in an
   untracked location — decide whether to gitignore `*.png` at the frontend root or
   move them, because Playwright will keep dropping files there.
3. **No source files were edited.** `AppShell.tsx`, `permissions.ts`, `App.tsx` are all
   untouched.

---

## What was verified, and how

Playwright MCP is available in this session (it is *deferred* — the schemas do not
appear in the upfront tool list until fetched with ToolSearch, which is why an early
claim that it "isn't loaded" was wrong).

**Setup:** `npm run dev` on :5173. Backend was already running on :8000, started by the
other seat. Vite proxies `/api` → `127.0.0.1:8000` (see `vite.config.ts`), so the
browser sees one origin and there is no CORS locally.

**Result — login is genuinely working:**

- `http://localhost:5173/login` renders correctly: brand panel, the five unit chips,
  sign-in card.
- The **Sign in button is correctly disabled while both fields are empty** — the form
  gates on input before it will submit.
- Filled `admin` / password, clicked Sign in → redirected to `/app`.
- App shell renders with the full nav and the identity chip reading
  **"Administrator · All units"**, plus a Sign out button.
- Radar shows its "Not built yet — todo #2" placeholder, as expected.
- **Console is clean apart from a `favicon.ico` 404.** Nothing auth-related. That 404
  is cosmetic and pre-existing.

**What was NOT tested:** the failure path. A bad-credential attempt was never run, so
the error state is unverified. That is the obvious first thing to do next time a
server is up.

**Both servers are now DOWN.** The Vite process I started was killed by something
external, and :8000 went away too. Nothing is listening on either port. I did not
restart them — something stopped them deliberately, so that is Anthony's call.

---

## The task-identity problem (unresolved, and blocking)

This is the thing that will waste someone's day if they miss it.

- The broker task this session is connected to is **`test-drive-2-e0b5`**.
  `get_todos()` returns **`[]`**. `roster()` shows three seats — `backend` (host),
  `frontend` (tooney, me), `guest` (unjoined, invite pending). **No contract exists.**
- The backend seat independently reported the same thing, and added that yesterday's
  handoffs describe task **`test-drive-8b12`** with **five accepted todos and
  contracts locked on #1 and #2**.
- A screenshot Anthony shared corroborates it: the sys-buddy dashboard for
  `test-drive-8b12`, all three seats pre-flight passed, a `Scout-Mate Intelligence
  Rebuild.zip` design bundle uploaded by the guest (Michaella), and a message from me
  acknowledging a brief covering **8 screens** — Radar, Opportunities, Opportunity
  detail, Industry, Organisations, Weekly Briefing, Learning, Profile and Sources.
  On `8b12` the guest had **joined**; on `2-e0b5` the guest seat is still empty.
- The backend's read is that **a token swap moved us onto a different task.**

**Why this matters concretely:** the code in this repo openly references history that
lives on the other task. `App.tsx` placeholder copy says *"These screens are todo #2.
Its contract is being re-versioned — I declined v1 because the Radar's 'priority
actions' list had no endpoint behind it…"*. `permissions.ts` says its codename mapping
was *"Started from the mapping suggested in the todo #1 contract."* **None of those
contracts are readable from `2-e0b5`.** So the codebase is built against agreements we
currently cannot verify.

**Do not propose, sign, or report a status against `2-e0b5` until a human settles
which task is real.** I told the backend the same and explicitly said I would not
build against a contract I cannot read.

---

## The open request: dashboard with a side menu

Anthony's instruction, verbatim in intent: on login it needs to be a proper dashboard,
so the navbar items should not be there — they should be in a side menu. And: ask the
backend for the resources so the side menu contents are right.

### Current structure (what you would be changing)

`src/features/app/AppShell.tsx` renders a **top** `<header className="tm-appbar">`
containing brand, a horizontal `<nav>`, and the user/sign-out actions, with `<Outlet />`
below it. Styles in `src/features/app/app.css`.

Nav items come from `visibleNavItems(user.permissions)` in
`src/features/auth/permissions.ts`. Seven items today, each gated on a codename:

| Label | Route | Permission codename |
|---|---|---|
| Radar | `/app` | `opportunity:read` |
| Opportunities | `/app/opportunities` | `opportunity:read` |
| Industry | `/app/industry` | `industry_signal:read` |
| Organisations | `/app/organisations` | `organisation:read` |
| Briefing | `/app/briefing` | `report:read` |
| Learning | `/app/learning` | `decision:read` |
| Profile & Sources | `/app/profile` | `profile:read` |

### The design constraint to preserve

**Navigation is driven by permission codenames, never by role name.** The existing
comment in `AppShell.tsx` explains why and it is correct: `role === 'director'` rots
the moment the client adds a sixth role in the back office, and she can edit roles
herself. Keep this. A new role must never require a frontend deploy.

Also worth keeping in mind: the frontend deliberately owns the codename→nav mapping
because the API returns a flat permission list and no navigation array. Hiding an item
is *presentation only* — the API enforces every permission server-side regardless.

### What I asked the backend (message id 838, direct to `@backend`) — STILL UNANSWERED

- The authoritative **resource list** with endpoints, so the menu reflects real API
  capability rather than seven sketched screens.
- The **exact permission codename strings** they issue. Mine trace back to a todo #1
  contract on the unreadable task, so they are unverified.
- **Which codenames each seeded role holds** (admin, director, unit lead, others), so
  the menu can be *proven* to collapse for a non-admin rather than assumed to.
- Whether an **admin back-office entry** belongs in the sidebar, given `/admin` and
  `/docs` sit outside `/api` and are therefore not covered by the Vite proxy — and
  whether it is a link out or a screen to render.
- Whether any item wants a **count or badge**, and if so the endpoint and field. I will
  not invent a number.
- Whether the menu should **group or stay flat** — their resource split beats a guess.

**Pick up here:** if the answer has arrived, `ch` / `wm` will surface it. If it has not,
the layout restructure (top bar → left rail) is independent of *which* items land in
it and could proceed, but the item list itself should wait.

---

## Credentials — read this before assuming the dev password is private

The backend seat **pasted the dev login (`admin` + password) directly into the broker
message thread** (message 837), stating Anthony had cleared it. I had explicitly asked
them not to.

**Why it matters:** broker rule 6 — messages are stored in the database and rendered on
the dashboard to every viewer token on the task. A password there cannot be unsent.
Anthony's position was that localhost with dummy seed data makes it a non-event, and
that is a reasonable call for a throwaway instance. **But the value is permanently in
the task record.** If that instance ever stops being disposable, rotate it.

The password is deliberately **not reproduced in this handoff.** Get it from the
broker thread or from Anthony.

Login shape, which is safe to record: `POST /api/auth/login` takes
`{"identifier": "...", "password": "..."}` — identifier accepts username *or* email.
Returns 200 with `tokenType: bearer`, `expiresIn: 43200`.

---

## Known-not-bugs, per the backend

Do not go debugging these; they are seed-data artefacts the backend flagged:

- Design Teem, Ingene Studios and TM Labs return **empty opportunity lists** — the seed
  predates the five-unit model and only carries scores for TM Foundation and Takeout
  Media.
- `emergingTrends` and `competitorMovements` on `/api/radar` are **0**, and no Industry
  or Competitor rows appear in priority actions.
- `yourFitPercent` is **null** for admin or director — they have no unit of their own.
- `winProbability` is **null everywhere**; only the matching engine sets it.

---

## Corrections carried forward

- **My seat is `frontend`, not backend.** This session's opening briefing called me the
  backend agent, which is wrong, and pre-flight kept failing the role question until I
  answered `frontend`. `roster()` is the authority — role is stamped from the MCP token
  and is never declared. If a future briefing disagrees with what pre-flight accepts,
  trust `roster()` and tell Anthony.
- **My pre-flight IS cleared** on `2-e0b5`. The backend's message claimed otherwise;
  that was stale. Roster shows frontend/tooney as `passed`.
- **Playwright MCP is available**, just deferred. Fetch schemas with ToolSearch before
  calling. It drives its own throwaway browser profile — distinct from the
  `claude-in-chrome` tools, which drive Anthony's real Chrome session. For staging
  verification, prefer Playwright: reproducible, and it keeps an agent out of an
  authenticated session.

---

## Where to pick up

1. **Settle the task identity first** — `2-e0b5` or `8b12`. Everything else is built on
   sand until that is answered. This needs a human.
2. **Check for the backend's reply** to message 838 (`ch`). The sidebar item list
   depends on it.
3. **Restart servers when Anthony says so** — `npm run dev` for :5173; :8000 belongs to
   the other seat. Do not restart unprompted; the last pair were stopped deliberately.
4. **Build the side rail** once the resource list lands: convert `tm-appbar` to a left
   rail in `AppShell.tsx` + `app.css`, keep `visibleNavItems()` as the source of items,
   keep codename-driven gating.
5. **Test the login failure path**, which was never exercised.
6. Decide what to do with the stray `*.png` files at the frontend root.
