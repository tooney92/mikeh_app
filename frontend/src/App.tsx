import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './features/app/AppShell'
import { PlaceholderPage } from './features/app/PlaceholderPage'
import { AccountPage } from './features/auth/AccountPage'
import { LoginPage } from './features/auth/LoginPage'
import { PERMISSIONS } from './features/auth/permissions'
import { RequireAuth } from './features/auth/RequireAuth'
import { LandingPage } from './features/landing/LandingPage'
import { OpportunityDetailPage } from './features/opportunities/OpportunityDetailPage'
import { OpportunityListPage } from './features/opportunities/OpportunityListPage'
import { RadarPage } from './features/opportunities/RadarPage'
import { ProfileSourcesPage } from './features/profiles/ProfileSourcesPage'

/**
 * Routes. The landing page is public; everything under /app needs a session.
 *
 * Route-level `permission` mirrors what the nav hides, so a hand-typed URL
 * lands on a 403 screen instead of a broken one. It is presentation only —
 * the API enforces every permission regardless of what we render.
 */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/app"
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<RadarPage />} />
        <Route
          path="opportunities"
          element={
            <RequireAuth permission={PERMISSIONS.opportunityRead}>
              <OpportunityListPage />
            </RequireAuth>
          }
        />
        {/*
          The id is a SLUG string, not an integer — see the todo #2 contract.
          Gated on the same codename as the list: detail deliberately shows
          every unit's score regardless of the caller's scope, which is the
          joint-pitch mechanism, so it needs no additional permission.
        */}
        <Route
          path="opportunities/:opportunityId"
          element={
            <RequireAuth permission={PERMISSIONS.opportunityRead}>
              <OpportunityDetailPage />
            </RequireAuth>
          }
        />
        <Route
          path="industry"
          element={
            <RequireAuth permission={PERMISSIONS.industrySignalRead}>
              <IndustryPlaceholder />
            </RequireAuth>
          }
        />
        <Route
          path="organisations"
          element={
            <RequireAuth permission={PERMISSIONS.organisationRead}>
              <OrganisationsPlaceholder />
            </RequireAuth>
          }
        />
        <Route
          path="briefing"
          element={
            <RequireAuth permission={PERMISSIONS.reportRead}>
              <BriefingPlaceholder />
            </RequireAuth>
          }
        />
        <Route
          path="learning"
          element={
            <RequireAuth permission={PERMISSIONS.decisionRead}>
              <LearningPlaceholder />
            </RequireAuth>
          }
        />
        {/*
          Gated on profile:read only. The SOURCES half of this screen is
          deliberately NOT gated on source:read — that endpoint never checks
          the codename and serves all 15 rows to a member who holds none of
          them, so gating it would blank a table the API is willingly filling.
          The source WRITE controls are gated inside the screen.
        */}
        <Route
          path="profile"
          element={
            <RequireAuth permission={PERMISSIONS.profileRead}>
              <ProfileSourcesPage />
            </RequireAuth>
          }
        />
        <Route path="account" element={<AccountPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

/* Placeholders until each todo's contract is agreed and built. -------------- */

/*
 * Radar, Opportunities and Opportunity detail are BUILT — todo #2's contract
 * locked at v4 and they render real data now, so their placeholders are gone.
 * Profile & sources is BUILT too, against todo #3's v4 contract.
 * What remains below is genuinely unstarted work.
 */

function IndustryPlaceholder() {
  return (
    <PlaceholderPage
      kicker="Industry intelligence"
      title="What is moving in Nigerian industry"
      lede="Trends, regulation and funding across sectors — including the ones TM Global does not work in yet."
      waitingOn="This screen is todo #5, which is deliberately not started. Nothing generates industry signals yet, so building it now would mean building against invented data."
    />
  )
}

function OrganisationsPlaceholder() {
  return (
    <PlaceholderPage
      kicker="Organisation intelligence"
      title="Who should we be talking to?"
      lede="The ten client organisations we track, what they are doing, and where the upsell is."
      waitingOn="Todo #5. The ten organisations exist in the database, but their signal, upsell angle and priority fields are empty until the news monitoring is built."
    />
  )
}

function BriefingPlaceholder() {
  return (
    <PlaceholderPage
      kicker="Executive weekly briefing"
      title="The ten things you need to know"
      lede="One synthesis across opportunities, clients, industry and competitors — the same content that emails on Monday."
      waitingOn="Todo #5. There is no briefing endpoint yet; weekly report generation is still to be built."
    />
  )
}

function LearningPlaceholder() {
  return (
    <PlaceholderPage
      kicker="Learning"
      title="How your decisions shape the scoring"
      lede="Every Pursue, Partner, Watch and Reject, and what they add up to."
      waitingOn="This screen is todo #4. Its API is built; the contract has not been proposed yet."
    />
  )
}
