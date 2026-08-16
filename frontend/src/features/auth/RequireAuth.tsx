import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './useAuth'
import type { ReactNode } from 'react'

/**
 * Gate for the signed-in app.
 *
 * `permission` guards a route the same way the nav hides its link — but this
 * is presentation only. Every permission is enforced server-side too, so a
 * hand-typed URL gets a 403 from the API regardless of what we render.
 */
export function RequireAuth({
  children,
  permission,
}: {
  children: ReactNode
  permission?: string
}) {
  const { user, loading, can } = useAuth()
  const location = useLocation()

  // Don't bounce to /login while the stored token is still being checked,
  // or every refresh would flash the login screen.
  if (loading) return <div className="tm-app__loading">Loading…</div>

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (permission && !can(permission)) {
    return <NotPermitted />
  }

  return <>{children}</>
}

function NotPermitted() {
  return (
    <div className="tm-forbidden">
      <div className="tm-forbidden__code">403</div>
      <h1 className="tm-forbidden__title">You don't have access to this</h1>
      <p className="tm-forbidden__lede">
        You're signed in, but your role doesn't include this screen. If you need
        it, ask your administrator to change your permissions.
      </p>
    </div>
  )
}
