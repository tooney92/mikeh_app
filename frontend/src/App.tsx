import { Navigate, Route, Routes } from 'react-router-dom'
import { LandingPage } from './features/landing/LandingPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      {/* App routes (radar, opportunities, …) land here once agreed. */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
