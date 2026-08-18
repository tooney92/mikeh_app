import { useEffect, useRef, useState } from 'react'
import { PERMISSIONS, can } from '../auth/permissions'
import { useAuth } from '../auth/useAuth'
import { ErrorState, LoadingState, useAsync } from '../opportunities/States'
import {
  describeScanError,
  fetchScanStatus,
  formatStamp,
  scanFailed,
  scanInFlight,
  startScan,
} from './api'
import type { ScanState } from './types'
import type { WriteFailure } from './api'

/**
 * The sweep control.
 *
 * THE THING THIS PANEL MUST NOT DO IS IMPLY THAT RESULTS ARRIVED. The sweep
 * records that it visited each source and scores what is already in the
 * database. It does NOT fetch a page, parse a page, or create a single new
 * opportunity — the crawler is a later deliverable. A panel that said "scan
 * complete" and left it there would tell the client the system found things
 * for them, which it did not, so the honest sentence is always on screen and
 * not tucked behind a tooltip.
 *
 * Every POST writes a ScanRun row, so nothing here fires automatically: no
 * trigger on mount, no retry, no interval. Only the button starts a run.
 */

/** Poll cadence while a run is genuinely in flight. Runs finish in ~20ms today. */
const POLL_MS = 1200

/**
 * Polls to give up after. GET /api/scan/status is a read and writes nothing,
 * but a run that has not finished in fifteen seconds is not going to be
 * watched into finishing — better to say so and stop than to poll forever.
 */
const MAX_POLLS = 12

export function ScanPanel() {
  const { user } = useAuth()

  /*
    Gated on the codename for correctness, though EVERY seeded role holds
    scan:run today — member included — so no account currently sees this panel
    without the button. If a role is ever created without it, the panel still
    reads as information rather than breaking.
  */
  const canRun = can(user?.permissions ?? [], PERMISSIONS.scanRun)

  // A read, so it is safe on mount. Only the POST is rationed.
  const request = useAsync(() => fetchScanStatus(), [])

  return (
    <section className="tm-prof__section tm-scan" aria-labelledby="tm-prof-scan">
      <div className="tm-prof__sectionhead">
        <h2 className="tm-prof__sectiontitle" id="tm-prof-scan">
          Weekly sweep
        </h2>
      </div>

      {request.state === 'loading' ? <LoadingState label="Checking the last sweep…" /> : null}
      {request.state === 'error' ? <ErrorState error={request.error} retry={request.reload} /> : null}
      {request.state === 'ready' ? <ScanControls loaded={request.data} canRun={canRun} /> : null}
    </section>
  )
}

function ScanControls({ loaded, canRun }: { loaded: ScanState; canRun: boolean }) {
  const [state, setState] = useState(loaded)
  const [running, setRunning] = useState(false)
  const [gaveUp, setGaveUp] = useState(false)
  const [failure, setFailure] = useState<WriteFailure | null>(null)

  // Polling stops the moment this panel goes away, so navigating off mid-run
  // does not leave a loop calling the API into an unmounted component.
  const live = useRef(true)
  useEffect(() => {
    live.current = true
    return () => {
      live.current = false
    }
  }, [])

  async function run() {
    setFailure(null)
    setGaveUp(false)
    setRunning(true)

    try {
      // The 202 carries the freshly started ScanState, so the panel can show
      // "running" without a round trip just to find that out.
      const started = await startScan()
      if (!live.current) return
      setState(started)

      let latest = started
      for (let attempt = 0; attempt < MAX_POLLS && scanInFlight(latest); attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, POLL_MS))
        if (!live.current) return
        latest = await fetchScanStatus()
        if (!live.current) return
        setState(latest)
      }

      // Polling stops here either way — this is the only loop on the screen.
      if (scanInFlight(latest)) setGaveUp(true)
    } catch (error) {
      // NOT describeWriteError(error, 'source') — that speaks in source-table
      // copy, so a failed sweep used to report "A source needs both a name and
      // a URL" on a 422 and "That row is gone" on a 404. Wrong noun entirely.
      if (live.current) setFailure(describeScanError(error))
    } finally {
      if (live.current) setRunning(false)
    }
  }

  const inFlight = running || scanInFlight(state)
  const started = formatStamp(state.startedAt)
  const finished = formatStamp(state.finishedAt)

  return (
    <div className="tm-scan__panel">
      <div className="tm-scan__main">
        <div className="tm-scan__statusline">
          <span className={`tm-scan__dot tm-scan__dot--${inFlight ? 'run' : state.status}`} />
          <span className="tm-scan__status">
            {inFlight
              ? 'Sweep running'
              : state.status === 'idle'
                ? 'No sweep has ever run'
                : /*
                    A failed sweep must NOT read as a finished one. "Last sweep
                    finished" beside a broken run is the same class of lie as a
                    zero tile that might be a failed fetch.
                  */
                  scanFailed(state)
                  ? `Last sweep FAILED ${finished ? `at ${finished}` : '— time not recorded'}`
                  : `Last sweep finished ${finished ?? 'at an unrecorded time'}`}
          </span>
        </div>

        {state.status === 'idle' && !inFlight ? (
          <p className="tm-scan__note">
            Nothing has swept yet. The counts below fill in after the first run.
          </p>
        ) : (
          <dl className="tm-scan__figures">
            <div className="tm-scan__figure">
              <dt>Sources visited</dt>
              <dd>{state.sourcesSwept}</dd>
            </div>
            <div className="tm-scan__figure">
              <dt>Opportunities scored</dt>
              <dd>{state.scored}</dd>
            </div>
            <div className="tm-scan__figure">
              <dt>Started</dt>
              <dd>{started ?? 'not recorded'}</dd>
            </div>
          </dl>
        )}

        {/*
          Always on screen, never conditional on a run having happened. This is
          the sentence that stops "sweep complete" being read as "new
          opportunities have arrived".
        */}
        <p className="tm-scan__truth">
          A sweep <strong>records which sources it visited</strong> and scores what is already in the
          database against the unit profiles. It does not fetch or read a single page, so it produces
          no new opportunities — the crawler that will is a later deliverable. If the Radar looks
          identical afterwards, that is the sweep working exactly as built.
        </p>

        {gaveUp ? (
          <p className="tm-scan__note tm-scan__note--warn">
            The sweep was still running when this screen stopped watching. It has not been cancelled
            — reload the page to see where it got to. Runs normally finish in well under a second, so
            this is worth mentioning to someone.
          </p>
        ) : null}

        {failure ? (
          <p className="tm-scan__note tm-scan__note--warn">
            <strong>{failure.title}.</strong> {failure.message}
          </p>
        ) : null}
      </div>

      <div className="tm-scan__side">
        {canRun ? (
          <>
            <button className="tm-scan__run" type="button" onClick={run} disabled={inFlight}>
              {inFlight ? 'Sweeping…' : 'Run a sweep'}
            </button>
            <p className="tm-scan__runnote">
              Every run is written to the scan history, so it is not something to press idly.
            </p>
          </>
        ) : (
          <p className="tm-scan__runnote">
            Your account cannot start a sweep. Every role currently has this, so if you are seeing
            this message something unusual has been configured.
          </p>
        )}
      </div>
    </div>
  )
}
