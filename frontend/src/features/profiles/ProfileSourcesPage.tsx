import { ScanPanel } from './ScanPanel'
import { SourcesSection } from './Sources'
import { UnitProfilesSection } from './UnitProfiles'
import './profiles.css'

/**
 * Profile & sources — the configuration screen behind everything the Radar and
 * the opportunity list show.
 *
 * Three sections, in the order they depend on each other: the five unit
 * profiles that opportunities are scored against, the sources those
 * opportunities are meant to come from, and the sweep that walks the sources.
 *
 * Each section fetches independently, on purpose. The sources list failing
 * must not blank the profiles, and neither must take the sweep panel down with
 * it — one dead panel is much better than a dead page, and this screen is
 * where somebody comes to fix things when something else is broken.
 *
 * The route is gated on `profile:read` in App.tsx. Nothing inside gates the
 * sources list any further: reading it needs a session and nothing more, and
 * gating it on `source:read` would hand a member an empty table for rows the
 * API is happily returning. See the header comment in Sources.tsx.
 */
export function ProfileSourcesPage() {
  return (
    <div className="tm-page tm-prof">
      <div className="tm-page__kicker">
        <span className="tm-page__dash" aria-hidden="true" />
        Profile &amp; sources
      </div>
      <h1 className="tm-page__title">What each unit is looking for</h1>
      <p className="tm-page__lede">
        The five profiles every opportunity is scored against, the sources swept to find them, and
        the sweep itself. Everything here decides what the rest of the app can show you.
      </p>

      <UnitProfilesSection />
      <SourcesSection />
      <ScanPanel />
    </div>
  )
}
