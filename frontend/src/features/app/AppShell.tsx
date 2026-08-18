import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { visibleNavGroups } from '../auth/permissions'
import { useAuth } from '../auth/useAuth'
import './app.css'

export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  // Nav is drawn from the permission codenames, never from the role name —
  // role === 'director' rots the moment the client adds a sixth role in the
  // back office, and she can edit roles herself.
  const groups = visibleNavGroups(user?.permissions ?? [])

  // On a phone the rail is a drawer over the page, so a tap that navigates
  // must also close it — otherwise the destination is hidden behind the menu
  // the user just used.
  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  function handleSignOut() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className={menuOpen ? 'tm-app tm-app--menu-open' : 'tm-app'}>
      <aside className="tm-rail">
        <div className="tm-rail__brand">
          <div className="tm-rail__mark">TM</div>
          <div className="tm-rail__wordmark">TM Global BI</div>
        </div>

        <nav className="tm-rail__nav">
          {groups.map((group) => (
            <div className="tm-rail__group" key={group.label}>
              <div className="tm-rail__grouplabel">{group.label}</div>
              {group.items.map((item) =>
                item.external ? (
                  /*
                    The back office is server-rendered on the API's own origin,
                    so it leaves the SPA entirely — a NavLink would treat the
                    absolute URL as a route and mangle it. New tab, because
                    losing the dashboard to a full page load is not what
                    clicking a sidebar item should do.
                  */
                  <a
                    key={item.to}
                    className="tm-rail__link tm-rail__link--external"
                    href={item.to}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {item.label}
                  </a>
                ) : (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    // "Radar" is the index route, so only it needs an exact match.
                    end={item.to === '/app'}
                    className={({ isActive }) =>
                      isActive ? 'tm-rail__link tm-rail__link--active' : 'tm-rail__link'
                    }
                  >
                    {item.label}
                  </NavLink>
                ),
              )}
            </div>
          ))}
        </nav>

        {/*
          Identity sits at the FOOT of the rail, which is where a standard
          dashboard puts it — and it keeps the top of the rail for navigation
          rather than for the thing you look at once a session.
        */}
        <div className="tm-rail__foot">
          <NavLink className="tm-rail__user" to="/app/account">
            <div className="tm-rail__name">{user?.fullName}</div>
            <div className="tm-rail__role">{describeMembership()}</div>
          </NavLink>
          <button className="tm-rail__signout" type="button" onClick={handleSignOut}>
            Sign out
          </button>
        </div>
      </aside>

      {/*
        Narrow screens only: the rail becomes a drawer, so it needs a control
        to open it and a scrim to dismiss it. Both are display:none at desk
        width, so there is no second navigation to keep in sync.
      */}
      <button
        className="tm-app__menubtn"
        type="button"
        aria-expanded={menuOpen}
        aria-label={menuOpen ? 'Close menu' : 'Open menu'}
        onClick={() => setMenuOpen((open) => !open)}
      >
        {menuOpen ? '✕' : '☰'}
      </button>
      <div
        className="tm-app__scrim"
        aria-hidden="true"
        onClick={() => setMenuOpen(false)}
      />

      <main className="tm-app__main">
        <Outlet />
      </main>
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
