import { createContext } from 'react'
import type { CurrentUser } from './types'

export interface AuthState {
  user: CurrentUser | null
  /** True until the stored token has been checked against /api/auth/me. */
  loading: boolean
  login: (identifier: string, password: string) => Promise<void>
  logout: () => void
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>
  can: (codename: string) => boolean
}

/** Kept apart from the provider component so fast refresh keeps working. */
export const AuthContext = createContext<AuthState | null>(null)
