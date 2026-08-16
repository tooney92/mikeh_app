import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './features/app/AppShell'
import { PlaceholderPage } from './features/app/PlaceholderPage'
import { AccountPage } from './features/auth/AccountPage'
import { LoginPage } from './features/auth/LoginPage'
import { PERMISSIONS } from './features/auth/permissions'
import { RequireAuth } from './features/auth/RequireAuth'
import { LandingPage } from './features/landing/LandingPage'

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
        <Route index element={<RadarPlaceholder />} />
        <Route
          path="opportunities"
          element={
            <RequireAuth permission={PERMISSIONS.opportunityRead}>
              <OpportunitiesPlaceholder />
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
        <Route
          path="profile"
          element={
            <RequireAuth permission={PERMISSIONS.profileRead}>
              <ProfilePlaceholder />
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

const AWAITING_2 =
  'These screens are todo #2. Its contract is being re-versioned — I declined v1 because the Radar’s “priority actions” list had no endpoint behind it, the pipeline value arrived pre-formatted, and there was no way for a director to filter to one unit.'

function RadarPlaceholder() {
  return (
    <PlaceholderPage
      kicker="Opportunity Radar"
      title="Your business development radar"
      lede="The weekly sweep, what needs attention, and the pipeline it adds up to."
      waitingOn={AWAITING_2}
    />
  )
}

function OpportunitiesPlaceholder() {
  return (
    <PlaceholderPage
      kicker="Opportunities"
      title="Everything worth pursuing"
      lede="Ranked by fit for your unit. Two units see the same opportunity in a different position."
      waitingOn={AWAITING_2}
    />
  )
}

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

function ProfilePlaceholder() {
  return (
    <PlaceholderPage
      kicker="Profile & sources"
      title="What each unit is looking for"
      lede="Five unit profiles the AI scores against, and the sources swept each week."
      waitingOn="This screen is todo #3. Its API is built; the contract has not been proposed yet, and the five-profile layout still needs a design decision the client has not seen."
    />
  )
}
