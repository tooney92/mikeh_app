/**
 * Codename -> what it DRAWS.
 *
 * This mapping is deliberately frontend-owned: the API returns a flat list of
 * permission codenames and no navigation array, so adding a screen never needs
 * a backend deploy. Backend owns which codenames a user holds and enforces
 * every one server-side — hiding a button here is presentation, not security.
 *
 * Started from the mapping suggested in the todo #1 contract.
 */

export const PERMISSIONS = {
  opportunityRead: 'opportunity:read',
  industrySignalRead: 'industry_signal:read',
  organisationRead: 'organisation:read',
  reportRead: 'report:read',
  decisionRead: 'decision:read',
  decisionCreate: 'decision:create',
  profileRead: 'profile:read',
  profileUpdate: 'profile:update',
  sourceCreate: 'source:create',
  // NOT paired with a `sourceRead`, and that omission is deliberate: the
  // sources LIST is gated on being signed in and never on source:read, which
  // member.foundation does not hold while still being served all 15 rows.
  // Adding the codename here would invite somebody to gate the screen on it.
  sourceUpdate: 'source:update',
  sourceDelete: 'source:delete',
  scanRun: 'scan:run',
  adminAccess: 'admin:access',
} as const

export interface NavItem {
  label: string
  to: string
  /** Rendered only when the user holds this codename. */
  permission: string
  /**
   * True when `to` is an absolute URL leaving the SPA, so the item renders as
   * an anchor rather than a route. Only the admin back office is external.
   */
  external?: boolean
}

/**
 * The server-rendered back office (sqladmin), which the frontend links to and
 * does NOT rebuild — user administration, the permission grid and password
 * RESET all live there, per the ownership boundary in the todo #1 contract.
 *
 * It sits outside /api, so it needs its own Vite proxy entry (see
 * vite.config.ts). With that in place the link is RELATIVE, which is what
 * makes it work for someone reaching the app over a tunnel — pointing at the
 * backend's origin directly would only ever resolve on the dev machine.
 */
// `||`, NOT `??`. Vite resolves a declared-but-blank var to the empty string
// rather than undefined, so `??` would not fall back — and .env.example ships
// VITE_ADMIN_URL= blank on purpose. With `??` anyone copying that file gets
// href="" on the Back office link, which silently reopens the current page in
// a new tab instead of going to the back office.
const ADMIN_URL = import.meta.env.VITE_ADMIN_URL || '/admin'

export const NAV_ITEMS: NavItem[] = [
  { label: 'Radar', to: '/app', permission: PERMISSIONS.opportunityRead },
  { label: 'Opportunities', to: '/app/opportunities', permission: PERMISSIONS.opportunityRead },
  { label: 'Industry', to: '/app/industry', permission: PERMISSIONS.industrySignalRead },
  { label: 'Organisations', to: '/app/organisations', permission: PERMISSIONS.organisationRead },
  { label: 'Briefing', to: '/app/briefing', permission: PERMISSIONS.reportRead },
  { label: 'Learning', to: '/app/learning', permission: PERMISSIONS.decisionRead },
  { label: 'Profile & Sources', to: '/app/profile', permission: PERMISSIONS.profileRead },
]

export interface NavGroup {
  label: string
  items: NavItem[]
}

/**
 * The sidebar's sections, following the grouping the backend suggested on
 * todo #1 (Intelligence / Configuration / Administration). Grouping is the
 * frontend's call — the API returns no navigation array by design.
 *
 * A group is a presentation device only. Membership of a group grants
 * nothing: every item still carries its own codename and is filtered on it,
 * so a group cannot accidentally widen what somebody sees.
 *
 * Administration holds a single LINK OUT to the back office rather than a
 * screen — the contract puts user administration, the permission grid and
 * password reset there, so a frontend user-management page would be a second
 * place to set a password. One place, and it is /admin.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Intelligence',
    items: NAV_ITEMS.filter((item) => item.to !== '/app/profile'),
  },
  {
    label: 'Configuration',
    items: NAV_ITEMS.filter((item) => item.to === '/app/profile'),
  },
  {
    label: 'Administration',
    items: [
      {
        label: 'Back office',
        to: ADMIN_URL,
        permission: PERMISSIONS.adminAccess,
        external: true,
      },
    ],
  },
]

export function can(permissions: string[], codename: string): boolean {
  return permissions.includes(codename)
}

/**
 * Groups with their visible items, dropping any group left with none. That
 * drop is the point: a lead or member should see the section vanish, not sit
 * there as an empty heading advertising what they cannot reach.
 */
export function visibleNavGroups(permissions: string[]): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => can(permissions, item.permission)),
  })).filter((group) => group.items.length > 0)
}
