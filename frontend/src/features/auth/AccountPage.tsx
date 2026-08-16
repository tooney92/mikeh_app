import { useState, type FormEvent } from 'react'
import { ApiError } from '../../lib/api'
import { useAuth } from './useAuth'
import './auth.css'

/**
 * The signed-in user's own account: who the API says they are, plus changing
 * their own password. Managing OTHER people's accounts is deliberately out of
 * scope — that lives in the backend's own /admin back office.
 */
export function AccountPage() {
  const { user } = useAuth()

  return (
    <main className="tm-page">
      <div className="tm-page__kicker">
        <span className="tm-page__dash" aria-hidden="true" />
        Your account
      </div>

      <div className="tm-account">
        <h1 className="tm-account__title">{user?.fullName}</h1>
        <p className="tm-account__lede">
          What the system knows about you, and what that lets you see.
        </p>

        <div className="tm-account__rows">
          <div className="tm-account__row">
            <div className="tm-account__key">Username</div>
            <div className="tm-account__value">{user?.username}</div>
          </div>
          <div className="tm-account__row">
            <div className="tm-account__key">Work email</div>
            <div className="tm-account__value">{user?.email}</div>
          </div>
          <div className="tm-account__row">
            <div className="tm-account__key">Role</div>
            <div className="tm-account__value">{user?.role.label}</div>
          </div>
          <div className="tm-account__row">
            <div className="tm-account__key">Business units</div>
            <div className="tm-account__value">
              {user && user.businessUnits.length > 0
                ? user.businessUnits.map((unit) => unit.name).join(', ')
                : 'All five units'}
            </div>
          </div>
          <div className="tm-account__row">
            <div className="tm-account__key">Sees</div>
            <div className="tm-account__value">
              {user?.role.scope === 'all'
                ? 'Every unit’s opportunities and decisions'
                : 'Only your own units’ opportunities'}
            </div>
          </div>
        </div>

        <ChangePassword />
      </div>
    </main>
  )
}

function ChangePassword() {
  const { changePassword } = useAuth()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setDone(false)

    // Checked here as well as server-side so the mismatch is caught before a
    // pointless round trip; the API is still the authority on the rest.
    if (newPassword !== confirmPassword) {
      setError('The two new passwords do not match.')
      return
    }
    if (newPassword.length < 8) {
      setError('The new password must be at least 8 characters.')
      return
    }

    setSubmitting(true)
    try {
      await changePassword(currentPassword, newPassword)
      setDone(true)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'Could not reach the server. Try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="tm-account__section">
      <h2 className="tm-login__title">Change your password</h2>
      <p className="tm-login__hint">
        You need your current password. There is no reset email — a locked-out
        account is reset by an administrator.
      </p>

      {error && (
        <div className="tm-alert" role="alert">
          {error}
        </div>
      )}
      {done && (
        <div className="tm-alert tm-alert--ok" role="status">
          Password changed.
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <label className="tm-field" htmlFor="tm-current-password">
          <span className="tm-field__label">Current password</span>
          <input
            className="tm-field__input"
            id="tm-current-password"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            disabled={submitting}
          />
        </label>

        <label className="tm-field" htmlFor="tm-new-password">
          <span className="tm-field__label">New password</span>
          <input
            className="tm-field__input"
            id="tm-new-password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            disabled={submitting}
          />
        </label>

        <label className="tm-field" htmlFor="tm-confirm-password">
          <span className="tm-field__label">Confirm new password</span>
          <input
            className="tm-field__input"
            id="tm-confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            disabled={submitting}
          />
        </label>

        <button
          className="tm-submit"
          type="submit"
          disabled={submitting || !currentPassword || !newPassword}
        >
          {submitting ? 'Saving…' : 'Change password'}
        </button>
      </form>
    </section>
  )
}
