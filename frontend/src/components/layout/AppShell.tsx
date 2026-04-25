import { Outlet, Navigate } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { useAuthStore } from '../../store/authStore'

export function AppShell() {
  const token = useAuthStore(s => s.token)
  if (!token) return <Navigate to="/login" replace />

  return (
    <div className="flex min-h-screen bg-bg text-white">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  )
}
