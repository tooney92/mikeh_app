import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../../lib/api'
import { units } from '../landing/data'
import { useAuth } from './useAuth'
import './auth.css'

export function LoginPage() {
  const { user, loading, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Send people back where they were headed before the redirect to /login.
  const from = (location.state as { from?: string } | null)?.from ?? '/app'

  if (!loading && user) return <Navigate to={from} replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(identifier.trim(), password)
      navigate(from, { replace: true })
    } catch (caught) {
      setError(messageFor(caught))
      setPassword('')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="tm-login">
      <aside className="tm-login__aside">
        <div className="tm-login__brand">
          <div className="tm-login__mark">TM</div>
          <div className="tm-login__wordmark">TM Global BI</div>
        </div>

        <div>
          <div className="tm-login__kicker">
            <span className="tm-login__dash" aria-hidden="true" />
            Internal system
          </div>
          <h1 className="tm-login__headline">
            Where is our next revenue coming from?
          </h1>
          <p className="tm-login__lede">
            One business development radar across all five TM Global units —
            opportunities scored for your unit, client movements worth a call,
            and what the market is doing this week.
          </p>
          <ul className="tm-login__units">
            {units.map((unit) => (
              <li className="tm-login__unit" key={unit.name}>
                {unit.name}
              </li>
            ))}
          </ul>
        </div>

        <div className="tm-login__foot">
          Internal system · Accounts are created by an administrator
        </div>
      </aside>

      <main className="tm-login__main">
        <form className="tm-login__form" onSubmit={handleSubmit} noValidate>
          <h2 className="tm-login__title">Sign in</h2>
          <p className="tm-login__hint">
            Use your username or your work email address.
          </p>

          {error && (
            <div className="tm-alert" role="alert">
              {error}
            </div>
          )}

          <label className="tm-field" htmlFor="tm-identifier">
            <span className="tm-field__label">Username or work email</span>
            <input
              className="tm-field__input"
              id="tm-identifier"
              name="identifier"
              type="text"
              autoComplete="username"
              autoFocus
              value={identifier}
              onChange={(event) => setIdentifier(event.target.value)}
              disabled={submitting}
            />
          </label>

          <label className="tm-field" htmlFor="tm-password">
            <span className="tm-field__label">Password</span>
            <input
              className="tm-field__input"
              id="tm-password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={submitting}
            />
          </label>

          <button
            className="tm-submit"
            type="submit"
            disabled={submitting || !identifier || !password}
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>

          <p className="tm-login__meta">
            There is no sign-up and no password reset email. If you cannot get
            in, ask your administrator to set a new password for you.
          </p>
        </form>
      </main>
    </div>
  )
}

function messageFor(caught: unknown): string {
  if (caught instanceof ApiError) {
    // The contract returns the SAME 401 whether or not the account exists, so
    // accounts cannot be enumerated. Don't undo that with a helpful message.
    if (caught.status === 401) return 'Incorrect login or password.'
    if (caught.status === 403)
      return 'That account has been deactivated. Ask your administrator to reactivate it.'
    return caught.message
  }
  return 'Could not reach the server. Check your connection and try again.'
}
