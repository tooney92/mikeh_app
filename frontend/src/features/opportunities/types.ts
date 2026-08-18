/**
 * Shapes from the LOCKED v4 contract on todo #2. Field names are the
 * contract's, verbatim.
 *
 * Read the notes before changing anything here — several fields are named
 * almost like something they are not.
 */

/** A business unit, from GET /api/business-units. Always all five, never scoped. */
export interface BusinessUnitOption {
  id: number
  name: string
  initials: string
  description: string
  /** Length VARIES by unit — 6 for Takeout Media, 1 for Ingene Studios. */
  services: string[]
}

/**
 * The slice of a unit profile this feature needs: the per-unit fit bar.
 *
 * An opportunity scoring below `minFitPercent` is hidden from that unit's
 * list and radar — judged on the VIEWER'S own fit, never the top fit, so one
 * unit's strong score cannot drag a weak match back into another unit's list.
 * Default is 40 and an admin sets it per unit in the back office.
 *
 * The full profile shape belongs to todo #3; only these fields are read here.
 */
export interface UnitProfileBar {
  id: number
  businessUnitId: number
  businessUnitName: string
  initials: string
  minFitPercent: number
}

export interface RadarSummary {
  opportunitiesWorthPursuing: number
  organisationsWorthApproaching: number
  /** Permanently 0 today — nothing generates IndustrySignal rows. Not a bug. */
  emergingTrends: number
  /** Permanently 0 today, same reason. */
  competitorMovements: number
  potentialPartnerships: number
  /** WHOLE NAIRA as an integer, e.g. 2400000000. NOT a pre-formatted string. */
  estimatedPipelineValue: number
  /** ISO code, currently "NGN". Pair with the integer rather than assuming naira. */
  estimatedPipelineCurrency: string
}

/** The `category` on a row. NOT the same vocabulary as OpportunityFilter. */
export type OpportunityCategory = 'bid' | 'watch' | 'partnership' | 'bd'

export type Relevance = 'HIGH' | 'MEDIUM' | 'LOW'

/**
 * The `filter` query value. A CLOSED enum — an unknown value is a 400, not a
 * silent fallback. Deliberately not derived from OpportunityCategory: the two
 * vocabularies differ, and building chips from row categories yields wrong
 * parameter values. See FILTERS for the mapping.
 */
export type OpportunityFilter =
  | 'everything'
  | 'bid-now'
  | 'watch'
  | 'partnership'
  | 'bd-leads'
  | 'international'

export interface OpportunitySummary {
  /** A SLUG string, e.g. "gam-au". Never an integer — treat as a string in keys and URLs. */
  id: string
  category: OpportunityCategory
  org: string
  title: string
  desc: string
  /**
   * A display BAND, e.g. "$$$$" or "unconfirmed". NOT a number and NOT
   * parseable as money. Distinct from RadarSummary.estimatedPipelineValue,
   * which is a real integer.
   */
  value: string
  /** FREE TEXT, e.g. "No deadline stated". Not a date — do not parse it. */
  deadline: string
  relevance: Relevance
  beneficiary: string
  geography: string
  source: string
  /** The caller's own best fit. NULL for admin and director, who belong to no unit. */
  yourFitPercent: number | null
  /** Best fit across ANY unit — what an admin or director ranks by. */
  topFitPercent: number | null
}

export interface OpportunityScore {
  businessUnitId: number
  businessUnitName: string
  initials: string
  fitPercent: number
  /** NULL EVERYWHERE today — only the matching engine will ever set it. */
  winProbability: number | null
  isJointPitchCandidate: boolean
  jointPitchNote: string | null
}

export interface OpportunityDetail extends OpportunitySummary {
  /**
   * EVERY unit that has a score, sorted best first. Units with no score are
   * ABSENT rather than present with null, so a five-row table cannot be
   * assumed. Returned regardless of the caller's scope — that is the whole
   * joint-pitch mechanism.
   */
  scores: OpportunityScore[]
  sourceUrl: string
  positioning: string
  whyItMatters: string
  whyNow: string
  recommendation: string
  credentials: string[]
  partners: string[]
  themes: string[]
  approach: string[]
  /** Latest logged decision, or null. READ-ONLY here — writing is the Learning deliverable. */
  decision: string | null
  decisionReason: string | null
}

/**
 * Opportunity and Partnership are the only values the contract documents, but
 * the server also emits Organisation rows (from the approach-now loop), and
 * more types are planned once industry-signal data exists. Typed as an open
 * string union so an unrecognised type is a rendering decision rather than a
 * lie the compiler waves through.
 */
export type PriorityActionType = 'Opportunity' | 'Partnership' | (string & {})

export interface PriorityAction {
  type: PriorityActionType
  /** A Partnership row is prefixed "Joint pitch: ". */
  title: string
  description: string
  /**
   * The opportunity slug — NULLABLE. An Organisation row has no opportunity
   * behind it and sends null, so a row cannot be assumed to be linkable.
   * Interpolating this blindly produces /app/opportunities/null, which 404s.
   */
  opportunityId: string | null
}

/**
 * The filter chips, and what each one actually selects on server-side.
 *
 * `bid-now` selects category "bid" and `bd-leads` selects category "bd" — only
 * `watch` and `partnership` are spelled the same on both sides. `international`
 * is not a category at all: it selects on GEOGRAPHY, rows whose geography is
 * neither "Nigeria" nor empty. That last one will behave oddly the moment
 * Nigerian rows exist; the contract flags it rather than redesigning it.
 */
export const FILTERS: { value: OpportunityFilter; label: string }[] = [
  { value: 'everything', label: 'Everything' },
  { value: 'bid-now', label: 'Bid now' },
  { value: 'watch', label: 'Watch' },
  { value: 'partnership', label: 'Partnership' },
  { value: 'bd-leads', label: 'BD leads' },
  { value: 'international', label: 'International' },
]
