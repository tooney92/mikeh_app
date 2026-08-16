import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { visibleNavItems } from '../auth/permissions'
import { useAuth } from '../auth/useAuth'
import './app.css'

export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  // Nav is drawn from the permission codenames, never from the role name —
  // role === 'director' rots the moment the client adds a sixth role in the
  // back office, and she can edit roles herself.
  const items = visibleNavItems(user?.permissions ?? [])

  function handleSignOut() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="tm-app">
      <header className="tm-appbar">
        <div className="tm-appbar__brand">
          <div className="tm-appbar__mark">TM</div>
          <div className="tm-appbar__wordmark">TM Global BI</div>
        </div>

        <nav className="tm-appbar__nav">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              // "Radar" is the index route, so only it needs an exact match.
              end={item.to === '/app'}
              className={({ isActive }) =>
                isActive
                  ? 'tm-appbar__link tm-appbar__link--active'
                  : 'tm-appbar__link'
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="tm-appbar__actions">
          <NavLink className="tm-appbar__user" to="/app/account">
            <div className="tm-appbar__name">{user?.fullName}</div>
            <div className="tm-appbar__role">{describeMembership()}</div>
          </NavLink>
          <button className="tm-appbar__signout" type="button" onClick={handleSignOut}>
            Sign out
          </button>
        </div>
      </header>

      <Outlet />
    </div>
  )

  /**
   * A user can belong to several units (one person leads both Takeout Media
   * and TM Foundation), or to none at all when their scope is "all".
   */
  function describeMembership(): string {
    if (!user) return ''
    if (user.businessUnits.length === 0) return `${user.role.label} · All units`
    return `${user.role.label} · ${user.businessUnits.map((unit) => unit.initials).join(' + ')}`
  }
}
