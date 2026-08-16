/**
 * Shapes from the locked contract on todo #1. Field names are the contract's,
 * verbatim — the API speaks camelCase throughout.
 */

export interface BusinessUnit {
  id: number
  name: string
  initials: string
}

/** "all" sees every unit's rows; "own_units" is filtered to the user's units. */
export type RoleScope = 'all' | 'own_units'

export interface Role {
  id: number
  name: string
  label: string
  scope: RoleScope
  isSystem: boolean
  permissions: string[]
}

export interface CurrentUser {
  id: number
  username: string
  email: string
  fullName: string
  /**
   * MAY hold more than one unit — one person leads both Takeout Media and
   * TM Foundation. Empty for admin/director, who see everything by scope
   * rather than membership. Never assume a single unit.
   */
  businessUnits: BusinessUnit[]
  role: Role
  /** Flat codename list, e.g. ["opportunity:read", "scan:run"]. Render from this. */
  permissions: string[]
  isActive: boolean
  lastLoginAt: string | null
}

export interface LoginResponse {
  accessToken: string
  tokenType: 'bearer'
  expiresIn: number
}
