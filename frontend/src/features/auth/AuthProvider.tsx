import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  apiGet,
  apiSend,
  clearToken,
  getToken,
  setToken,
  setUnauthenticatedHandler,
} from '../../lib/api'
import { AuthContext, type AuthState } from './authContext'
import { can } from './permissions'
import type { CurrentUser, LoginResponse } from './types'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [loading, setLoading] = useState(true)

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
  }, [])

  // A 401 from any request means the token is dead — including the contract's
  // case where deactivating an account kills a live token on its next call.
  useEffect(() => {
    setUnauthenticatedHandler(() => setUser(null))
    return () => setUnauthenticatedHandler(null)
  }, [])

  // Restore the session on load: a stored token is only a claim until /me agrees.
  useEffect(() => {
    let cancelled = false

    if (!getToken()) {
      setLoading(false)
      return
    }

    apiGet<CurrentUser>('/api/auth/me')
      .then((me) => {
        if (!cancelled) setUser(me)
      })
      .catch(() => {
        if (!cancelled) {
          clearToken()
          setUser(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (identifier: string, password: string) => {
    const result = await apiSend<LoginResponse>('POST', '/api/auth/login', {
      identifier,
      password,
    })
    setToken(result.accessToken)
    // Fetch the user before resolving, so callers never see a logged-in state
    // without permissions loaded.
    setUser(await apiGet<CurrentUser>('/api/auth/me'))
  }, [])

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      await apiSend<void>('POST', '/api/auth/change-password', {
        currentPassword,
        newPassword,
      })
    },
    [],
  )

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      login,
      logout,
      changePassword,
      can: (codename: string) => can(user?.permissions ?? [], codename),
    }),
    [user, loading, login, logout, changePassword],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
