import React, { useEffect, useState } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'

import { AppShell } from './components/layout/AppShell'
import Login from './pages/Login'
import Wizard from './pages/Wizard'
import Dashboard from './pages/Dashboard'
import Sessions from './pages/Sessions'
import SessionUpload from './pages/SessionUpload'
import SessionDetail from './pages/SessionDetail'
import LapAnalysis from './pages/LapAnalysis'
import Drivers from './pages/Drivers'
import Karts from './pages/Karts'
import Tracks from './pages/Tracks'
import Simulation from './pages/Simulation'
import Compliance from './pages/Compliance'
import StorageDashboard from './pages/StorageDashboard'
import Users from './pages/Users'
import Settings from './pages/Settings'
import { api, SystemStatus } from './api'

function AppRouter() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    api.get<SystemStatus>('/system/status')
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setChecking(false))
  }, [])

  if (checking) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="text-accent font-mono">STRAT-OS loading...</div>
      </div>
    )
  }

  if (status?.first_boot) {
    return (
      <Routes>
        <Route path="*" element={<Wizard />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<AppShell />}>
        <Route path="/"              element={<Dashboard />} />
        <Route path="/sessions"      element={<Sessions />} />
        <Route path="/sessions/:id"  element={<SessionDetail />} />
        <Route path="/upload"        element={<SessionUpload />} />
        <Route path="/laps/:id"      element={<LapAnalysis />} />
        <Route path="/drivers"       element={<Drivers />} />
        <Route path="/karts"         element={<Karts />} />
        <Route path="/tracks"        element={<Tracks />} />
        <Route path="/simulation"    element={<Simulation />} />
        <Route path="/compliance"    element={<Compliance />} />
        <Route path="/storage"       element={<StorageDashboard />} />
        <Route path="/users"         element={<Users />} />
        <Route path="/settings"      element={<Settings />} />
        <Route path="*"              element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppRouter />
    </BrowserRouter>
  </React.StrictMode>
)
