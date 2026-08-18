/**
 * Shapes from the LOCKED v4 contract for todo #3. Field names are the
 * contract's, verbatim — the API speaks camelCase throughout.
 *
 * Two things in here read as mistakes and are not:
 *
 * 1. `priorities`, `capabilities`, `credentials` and `neverShow` are STRINGS,
 *    not `string[]`. The API sends "Brand design\nMotion and animation" — one
 *    string with newlines in it — and expects the same back. Anyone "fixing"
 *    these to arrays gets `.map is not a function` on the first render and a
 *    422 on the first save. Use linesOf()/joinLines() in api.ts at the edges.
 *
 * 2. `id` on UnitProfile is the PROFILE id, and `businessUnitId` is the unit
 *    id. They happen to be equal for all five seeded rows today. That is a
 *    coincidence of seeding, not a guarantee — PUT takes the PROFILE id.
 */

export interface UnitProfile {
  /** PROFILE id. This is what PUT /api/profiles/{id} takes. NOT the unit id. */
  id: number
  businessUnitId: number
  businessUnitName: string
  initials: string
  /** Never null. Empty string when unset. */
  positioning: string
  /** NEWLINE-SEPARATED STRING, not an array. See the note at the top. */
  priorities: string
  /** NEWLINE-SEPARATED STRING, not an array. */
  capabilities: string
  /** NEWLINE-SEPARATED STRING, not an array. */
  credentials: string
  /**
   * NEWLINE-SEPARATED STRING, not an array — and NOT an active filter.
   * Nothing in the service consults this field today. It is guidance recorded
   * for a matching engine that does not exist yet. See ProfileCard.
   */
  neverShow: string
  /** Integer, INCLUSIVE 0-100. 40 on every seeded row. -1 and 101 are 422. */
  minFitPercent: number
  /**
   * THE ONLY THING THAT MAY DECIDE WHETHER THE EDIT UI IS OFFERED.
   *
   * True when this caller may PUT this row. It comes from the same server
   * function the PUT itself enforces, so it cannot drift out of step with what
   * the API will actually allow. Deriving the same answer on the client — from
   * `permissions`, from `user.businessUnits`, from the role name — reintroduces
   * a fail-open bug that was deliberately removed from the backend.
   */
  canEdit: boolean
}

/**
 * The PUT body. PARTIAL: every field optional, omitted fields unchanged, so
 * only what actually changed is ever sent.
 *
 * `id`, `businessUnitId`, `businessUnitName`, `initials` and `canEdit` are
 * deliberately absent — they are not writable and sending them is noise.
 */
export type ProfileUpdate = Partial<
  Pick<
    UnitProfile,
    'positioning' | 'priorities' | 'capabilities' | 'credentials' | 'neverShow' | 'minFitPercent'
  >
>

/** The writable profile fields, in the order the editor lays them out. */
export const PROFILE_FIELDS = [
  'positioning',
  'priorities',
  'capabilities',
  'credentials',
  'neverShow',
  'minFitPercent',
] as const satisfies readonly (keyof ProfileUpdate)[]

export type ProfileField = (typeof PROFILE_FIELDS)[number]

/* ------------------------------------------------------------- sources --- */

/**
 * The four types, VALIDATED SERVER-SIDE as of todo #4 v6.
 *
 * It used to be unvalidated — POST with type "pdf" returned 201 and stored it
 * verbatim. Now anything outside this set is a 422 on both POST and PATCH,
 * confirmed live including the near-misses: "pdf", "HTML" and "" are all
 * rejected, so the check is exact-match and case-sensitive.
 *
 * `Source.type` is still typed as a plain string rather than as this union.
 * The 90 rows on the wire today all conform, but the read side describes
 * whatever the server sends, and narrowing it here would turn a future value
 * into a compile error in the one place that should keep rendering.
 */
export const SOURCE_TYPES = ['html', 'rss', 'json', 'unknown'] as const
export type SourceType = (typeof SOURCE_TYPES)[number]

/**
 * `scope` is a takeout | foundation | both vocabulary that PREDATES the
 * five-unit model — Design Teem, Ingene Studios and TM Labs cannot be
 * expressed in it at all. It is rendered as the raw string everywhere and is
 * never mapped onto business units: that mapping does not exist, and inventing
 * one would produce confident nonsense on three fifths of the company.
 *
 * Also unvalidated server-side: POST with scope "design-teem" returns 201.
 */
export const SOURCE_SCOPES = ['takeout', 'foundation', 'both'] as const
export type SourceScope = (typeof SOURCE_SCOPES)[number]

/**
 * Where a source came from. Contracted in todo #4 v6, never null.
 *
 * "seed" is one of the 9 originals with no counterpart in the client's file.
 * "client_import" is one of her 81 — including the 6 that reconciled with an
 * existing seed, because her list is the reason we know she wants them watched.
 */
export type Provenance = 'seed' | 'client_import'

/**
 * Discovery platform vs publisher. A STRING enum, not a nullable boolean.
 *
 * `isAggregator: true | false | null` was the obvious encoding and is the wrong
 * one: null is FALSY, so `if (source.isAggregator)` renders every unconfirmed
 * row as "not an aggregator" — an invisible wrong `false`, which is the exact
 * thing the three-state design exists to prevent. Naming both real states also
 * removes the elimination step: "issuer" is asserted rather than inferred.
 *
 * Every imported row lands "unconfirmed" — her spreadsheet has no aggregator
 * column, so classifying at import would be inventing data.
 */
export type SourceRole = 'aggregator' | 'issuer' | 'unconfirmed'

export interface Source {
  id: number
  name: string
  /**
   * VALIDATED ENUM as of todo #4 v6: html | rss | json | unknown, 422 on
   * anything else. "unknown" is what all 75 imported rows carry, and it exists
   * rather than defaulting to "html" for the same reason sourceRole is a string
   * enum — "html" is a default that LOOKS LIKE AN ANSWER, and a reader could
   * not tell a source somebody examined from one nobody has ever opened.
   */
  type: string
  /** FREE TEXT, not an enum. "" on the 75 imported rows. OUR vocabulary. */
  category: string
  /** Raw stale-vocabulary string. Never mapped onto units. "both" on all 81. */
  scope: string
  url: string
  active: boolean
  /** Never null. */
  provenance: Provenance
  /** Never null. "unconfirmed" on every row today. */
  sourceRole: SourceRole
  /**
   * Her "Opportunity type" text, VERBATIM — never parsed, never mapped onto
   * `category`, which is OURS. 81 distinct values across 81 rows, so there is
   * no vocabulary in here to enumerate; the future exclusion rule matches TEXT.
   * Non-empty on every client_import row, "" on the 9 seeds.
   */
  clientOpportunityType: string
  /** Her "Applicable sector(s)" text, verbatim. Same rules. */
  clientSectors: string
  /** Human string like "ok — 5 candidates" or "HTTP 403". Null = never checked. */
  lastStatus: string | null
  lastStatusOk: boolean | null
  /**
   * Null on EVERY row, including rows that carry a lastStatus — the sweep
   * records a status without recording when. Never render a blank or a dash
   * for it; say plainly that the time is not recorded.
   */
  lastCheckedAt: string | null
}

/** POST /api/sources body. `name` and `url` required; the rest have defaults. */
export interface SourceCreate {
  name: string
  url: string
  /** Defaults to "html" server-side. Settable ONLY here, never afterwards. */
  type?: string
  /** Defaults to "" server-side. Settable ONLY here, never afterwards. */
  category?: string
  /** Defaults to "both" server-side. Settable ONLY here, never afterwards. */
  scope?: string
}

/**
 * PATCH /api/sources/{id} body — WIDENED in todo #4 v6.
 *
 * It used to accept only name, url and active, so type, category and scope
 * were write-once-at-creation and a wrong one could only be fixed by deleting
 * and recreating the row. That was tolerable at 15 hand-written sources and is
 * not at 90 imported ones.
 *
 * `sourceRole` was the half that made widening non-optional: every row lands
 * "unconfirmed" by design and the screen is contracted to draw that as
 * provisional, so without a way to confirm it we would be rendering 90
 * question marks nobody could ever answer. Same now applies to `type`, where
 * 75 rows land "unknown".
 */
export interface SourcePatch {
  name?: string
  url?: string
  active?: boolean
  /** html | rss | json | unknown. 422 on anything else. */
  type?: string
  category?: string
  scope?: string
  sourceRole?: SourceRole
}

/* ---------------------------------------------------------------- scan --- */

/**
 * Observed live: "idle" before anything has run, "running" in the 202 body,
 * "complete" once finished. Typed open-endedly so an unrecognised status is
 * treated as in-flight rather than crashing the panel.
 */
/**
 * `failed` is NOT in the locked v4 contract, which documents only idle and
 * complete. The backend added it after a review found that a sweep raising
 * mid-run left the status stuck on `running` forever. It is handled here
 * BEFORE it is contracted, deliberately: an unhandled `failed` disables the
 * Run button permanently, which is the exact wedge the backend's fix removes.
 * Raised with them to contract properly; handling it early costs nothing and
 * failing to handle it costs the only control on the panel.
 */
export type ScanStatus = 'idle' | 'running' | 'complete' | 'failed'

/**
 * Statuses a sweep can STOP on. Anything outside this set means still going.
 *
 * Written as the terminal set rather than the running set on purpose: the two
 * unknowns fail in very different directions. An unrecognised status treated as
 * running only ever costs a bounded wait, because polling stops at MAX_POLLS
 * and the button falls back to enabled. Treated as terminal it would let a
 * second sweep start on top of a live one, and every call writes a ScanRun row.
 */
export const SCAN_TERMINAL: readonly string[] = ['idle', 'complete', 'failed']

export interface ScanState {
  status: ScanStatus | string
  /** Naive UTC ISO string, NO trailing Z. See formatStamp() in api.ts. */
  startedAt: string | null
  finishedAt: string | null
  /** Sources RECORDED AS VISITED. Nothing was fetched or parsed. */
  sourcesSwept: number
  /** Existing opportunities scored. NOT newly discovered ones — there are none. */
  scored: number
}
