import { apiGet } from '../../lib/api'
import type {
  BusinessUnitOption,
  OpportunityDetail,
  OpportunityFilter,
  OpportunitySummary,
  PriorityAction,
  RadarSummary,
  UnitProfileBar,
} from './types'

/**
 * The todo #2 endpoints. Every call here goes through apiGet, which attaches
 * the bearer token — as of the v4 contract EVERY endpoint requires one, and
 * the only unauthenticated route on the whole service is GET /api/health.
 */

/**
 * `includeWeak` maps to the `include_weak` query parameter — snake_case, the
 * same spelling rule as business_unit_id. Built here so no caller spells it.
 */
export function fetchRadar(options?: { includeWeak?: boolean }): Promise<RadarSummary> {
  const query = options?.includeWeak ? '?include_weak=true' : ''
  return apiGet<RadarSummary>(`/api/radar${query}`)
}

/**
 * Unit profiles. Read here for ONE field: minFitPercent, the per-unit bar
 * below which an opportunity is hidden from that unit. It lets the
 * everything-is-below-the-bar empty state say "hidden below 40% for Takeout
 * Media" instead of something vague.
 *
 * The rest of the profile shape belongs to todo #3 and is not consumed here.
 */
export function fetchProfiles(): Promise<UnitProfileBar[]> {
  return apiGet<UnitProfileBar[]>('/api/profiles')
}

export function fetchPriorityActions(): Promise<PriorityAction[]> {
  return apiGet<PriorityAction[]>('/api/priority-actions')
}

export function fetchBusinessUnits(): Promise<BusinessUnitOption[]> {
  return apiGet<BusinessUnitOption[]>('/api/business-units')
}

/**
 * The ranked list. Returns a BARE ARRAY — no items/total/page envelope, and
 * no pagination beyond `limit`, which truncates.
 *
 * The unit parameter is `business_unit_id`, in snake_case, and it is built
 * here so no caller has to remember that.
 *
 * The v5 contract warns that camelCase is silently ignored and returns the
 * full unfiltered list with a 200 — a wrong answer that looks right. Backend
 * has since made the server accept `businessUnitId` and `includeWeak` too,
 * deliberately hidden from the schema, so that trap no longer bites. The
 * contract was left saying the stricter thing on purpose: it points the safe
 * way, since anyone trusting it sends snake_case and snake_case always works.
 *
 * Which is why this still builds snake_case and nothing else — the camelCase
 * alias is undocumented and unversioned, so it is not something to depend on.
 */
export function fetchOpportunities(options?: {
  filter?: OpportunityFilter
  businessUnitId?: number
  /** Include matches below the viewing unit's bar. Wire name: include_weak. */
  includeWeak?: boolean
  limit?: number
}): Promise<OpportunitySummary[]> {
  const params = new URLSearchParams()
  if (options?.filter) params.set('filter', options.filter)
  if (options?.businessUnitId !== undefined) {
    params.set('business_unit_id', String(options.businessUnitId))
  }
  // Only sent when true: the server default is false, and an explicit
  // include_weak=false is the same request with more to go wrong.
  if (options?.includeWeak) params.set('include_weak', 'true')
  if (options?.limit !== undefined) params.set('limit', String(options.limit))

  const query = params.toString()
  return apiGet<OpportunitySummary[]>(
    query ? `/api/opportunities?${query}` : '/api/opportunities',
  )
}

/** `id` is a slug string, so it is encoded rather than interpolated raw. */
export function fetchOpportunity(id: string): Promise<OpportunityDetail> {
  return apiGet<OpportunityDetail>(`/api/opportunities/${encodeURIComponent(id)}`)
}

/**
 * Money formatting is the frontend's job — the API deliberately sends an
 * integer plus an ISO currency code rather than a pre-formatted string, which
 * was one of the three reasons v1 was declined on the previous board.
 *
 * Large naira figures are unreadable in full, so this abbreviates: 2400000000
 * becomes "₦2.4bn". Intl supplies the symbol so a currency change needs no
 * code change here.
 */
export function formatMoney(value: number, currency: string): string {
  const symbol =
    new Intl.NumberFormat('en-NG', { style: 'currency', currency })
      .formatToParts(0)
      .find((part) => part.type === 'currency')?.value ?? ''

  const units: [number, string][] = [
    [1_000_000_000, 'bn'],
    [1_000_000, 'm'],
    [1_000, 'k'],
  ]

  for (const [size, suffix] of units) {
    if (Math.abs(value) >= size) {
      const scaled = value / size
      // One decimal below 100 ("2.4bn"), none above ("240bn") — precision that
      // survives at a glance rather than precision nobody reads.
      const digits = Math.abs(scaled) < 100 ? 1 : 0
      return `${symbol}${scaled.toFixed(digits).replace(/\.0$/, '')}${suffix}`
    }
  }

  return `${symbol}${value.toLocaleString('en-NG')}`
}
