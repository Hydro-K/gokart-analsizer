import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, SystemStatus, Session, Driver } from '../api'
import { MetricCard } from '../components/common/MetricCard'
import { StorageBar } from '../components/common/StorageBar'
import { StatusBadge } from '../components/common/StatusBadge'
import { useUIStore } from '../store/uiStore'

function fmtTime(s: number) {
  const m = Math.floor(s / 60)
  const sec = (s % 60).toFixed(3).padStart(6, '0')
  return `${m}:${sec}`
}

export default function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [recentSessions, setRecentSessions] = useState<Session[]>([])
  const [drivers, setDrivers] = useState<Driver[]>([])
  const mode = useUIStore(s => s.mode)

  useEffect(() => {
    api.get<SystemStatus>('/system/status').then(setStatus).catch(() => {})
    api.get<Session[]>('/sessions?limit=5').then(setRecentSessions).catch(() => {})
    api.get<Driver[]>('/drivers').then(setDrivers).catch(() => {})
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        {status && (
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400 font-mono">v{status.version}</span>
            <StatusBadge status={status.storage.status} />
          </div>
        )}
      </div>

      {/* Metrics row */}
      {status && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricCard label="Sessions" value={status.stats.sessions} />
          <MetricCard label="Drivers" value={status.stats.drivers} />
          <MetricCard label="Pending Jobs" value={status.stats.pending_jobs} highlight={status.stats.pending_jobs > 0} />
          <div className="rounded-lg p-3 border border-border bg-surface flex flex-col gap-2">
            <span className="text-xs text-gray-400 uppercase tracking-wider">Storage</span>
            <StorageBar pct={status.storage.used_pct} status={status.storage.status} />
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="flex gap-3 flex-wrap">
        <Link to="/upload" className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">
          Upload Session
        </Link>
        <Link to="/sessions" className="px-4 py-2 border border-border rounded hover:border-accent text-sm transition-colors">
          View Sessions
        </Link>
        {mode === 'engineer' && (
          <Link to="/simulation" className="px-4 py-2 border border-border rounded hover:border-accent text-sm transition-colors">
            Simulation
          </Link>
        )}
        <Link to="/compliance" className="px-4 py-2 border border-border rounded hover:border-accent text-sm transition-colors">
          Compliance
        </Link>
      </div>

      {/* Recent sessions */}
      <div>
        <h2 className="text-lg font-bold text-white mb-3">Recent Sessions</h2>
        {recentSessions.length === 0 ? (
          <p className="text-gray-400 text-sm">No sessions yet. <Link to="/upload" className="text-accent hover:underline">Upload your first CSV.</Link></p>
        ) : (
          <div className="space-y-2">
            {recentSessions.map(s => (
              <Link key={s.id} to={`/sessions/${s.id}`}
                className="flex items-center gap-4 rounded-lg border border-border bg-surface px-4 py-3 hover:border-accent transition-colors">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-white">
                    {drivers.find(d => d.id === s.driver_id)?.name ?? `Driver #${s.driver_id}`}
                    <span className="text-gray-400 ml-2 text-xs">{s.session_type}</span>
                  </div>
                  <div className="text-xs text-gray-400 font-mono">{s.date}</div>
                </div>
                <span className="text-accent text-xs">View →</span>
              </Link>
            ))}
          </div>
        )}
      </div>

      {mode === 'beginner' && (
        <div className="rounded-lg border border-border bg-surface p-4 text-sm text-gray-400">
          <span className="text-accent font-bold">Beginner mode:</span> Complex analysis panels are hidden.
          Toggle Engineer mode in the sidebar to see all charts and tools.
        </div>
      )}
    </div>
  )
}
