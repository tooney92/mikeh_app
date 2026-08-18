import { useEffect, useState } from 'react'
import { ApiError } from '../../lib/api'
import './states.css'

/**
 * Loading, error and empty states, shared by all three todo #2 screens.
 *
 * These exist as their own module because the contract lists SEVEN known-empty
 * realities that are correct behaviour and will each be read as a bug in a
 * demo: two radar tiles permanently zero, winProbability null everywhere,
 * yourFitPercent null for admin and director, decision null on every row,
 * three of five units with no scores at all, bid-now matching nothing, and
 * every account seeing the same 8 rows.
 *
 * A blank panel and a failed fetch look identical unless you make them
 * different, so nothing here ever renders an unexplained void.
 */

/** A deliberate, explained "there is nothing here" — never a bare blank. */
export function EmptyState({ title, explain }: { title: string; explain: string }) {
  return (
    <div className="tm-empty">
      <div className="tm-empty__title">{title}</div>
      <p className="tm-empty__text">{explain}</p>
    </div>
  )
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  // A 401 is not shown here: the api layer already clears the token and the
  // auth provider bounces to /login, so rendering an error would flash a
  // message the user never reads.
  const message =
    error instanceof ApiError
      ? `${error.message} (${error.status})`
      : 'Could not reach the server.'

  return (
    <div className="tm-error">
      <div className="tm-error__title">That didn’t load</div>
      <p className="tm-error__text">{message}</p>
      {retry ? (
        <button className="tm-error__retry" type="button" onClick={retry}>
          Try again
        </button>
      ) : null}
    </div>
  )
}

export function LoadingState({ label }: { label: string }) {
  return (
    <div className="tm-loading" role="status">
      {label}
    </div>
  )
}

/**
 * A value the API can legitimately return as null, rendered as an em dash with
 * the reason on hover rather than a bare blank or a misleading zero.
 *
 * winProbability is null on EVERY score today and yourFitPercent is null for
 * any user with no unit — showing 0% for either would be a lie, and showing
 * nothing at all reads as a rendering fault.
 */
export function NullValue({ reason }: { reason: string }) {
  return (
    <span className="tm-null" title={reason}>
      —
    </span>
  )
}

/** What a fetch is doing right now. Keeps the three screens' logic identical. */
export type Async<T> =
  | { state: 'loading' }
  | { state: 'error'; error: unknown }
  | { state: 'ready'; data: T }

/**
 * Runs a fetch and tracks it. `deps` re-runs it — the list screen passes its
 * filter and unit so changing either refetches.
 *
 * Results are discarded if they arrive after the inputs changed, so a slow
 * response for the previous filter cannot overwrite a fast one for the current
 * filter. Without that guard, clicking two chips quickly can leave the wrong
 * rows on screen under the right chip.
 */
export function useAsync<T>(run: () => Promise<T>, deps: unknown[]): Async<T> & { reload: () => void } {
  const [result, setResult] = useState<Async<T>>({ state: 'loading' })
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    let cancelled = false
    setResult({ state: 'loading' })

    run()
      .then((data) => {
        if (!cancelled) setResult({ state: 'ready', data })
      })
      .catch((error: unknown) => {
        if (!cancelled) setResult({ state: 'error', error })
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  return { ...result, reload: () => setNonce((n) => n + 1) }
}
