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
  sourceDelete: 'source:delete',
  scanRun: 'scan:run',
  adminAccess: 'admin:access',
} as const

export interface NavItem {
  label: string
  to: string
  /** Rendered only when the user holds this codename. */
  permission: string
}

export const NAV_ITEMS: NavItem[] = [
  { label: 'Radar', to: '/app', permission: PERMISSIONS.opportunityRead },
  { label: 'Opportunities', to: '/app/opportunities', permission: PERMISSIONS.opportunityRead },
  { label: 'Industry', to: '/app/industry', permission: PERMISSIONS.industrySignalRead },
  { label: 'Organisations', to: '/app/organisations', permission: PERMISSIONS.organisationRead },
  { label: 'Briefing', to: '/app/briefing', permission: PERMISSIONS.reportRead },
  { label: 'Learning', to: '/app/learning', permission: PERMISSIONS.decisionRead },
  { label: 'Profile & Sources', to: '/app/profile', permission: PERMISSIONS.profileRead },
]

export function can(permissions: string[], codename: string): boolean {
  return permissions.includes(codename)
}

export function visibleNavItems(permissions: string[]): NavItem[] {
  return NAV_ITEMS.filter((item) => can(permissions, item.permission))
}
