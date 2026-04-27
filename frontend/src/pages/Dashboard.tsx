import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, SystemStatus, Session, Driver } from '../api'
import { StorageBar } from '../components/common/StorageBar'
import { StatusBadge } from '../components/common/StatusBadge'
import { useUIStore } from '../store/uiStore'

function fmt(s: number) {
  const m = Math.floor(s / 60)
  const sec = (s % 60).toFixed(3).padStart(6, '0')
  return `${m}:${sec}`
}

const TYPE_DOT: Record<string, string> = {
  Race: 'bg-red', Qualifying: 'bg-gold', 'Practice 1': 'bg-accent', 'Practice 2': 'bg-accent', Test: 'bg-gray-500'
}

interface Benchmark { track_id: number; driver_id: number; kart_id: number; best_ever_s: number; best_session_s: number; theoretical_best_s: number; track_name?: string; driver_name?: string; kart_name?: string }

export default function Dashboard() {
  const [status, setStatus]         = useState<SystemStatus | null>(null)
  const [recentSessions, setRecent] = useState<Session[]>([])
  const [drivers, setDrivers]       = useState<Driver[]>([])
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([])
  const [pendingJobs, setPending]   = useState(0)
  const mode = useUIStore(s => s.mode)

  useEffect(() => {
    api.get<SystemStatus>('/system/status').then(s => { setStatus(s); setPending(s.stats.pending_jobs) }).catch(() => {})
    api.get<Session[]>('/sessions').then(all => setRecent(all.slice(0, 6))).catch(() => {})
    api.get<Driver[]>('/drivers').then(setDrivers).catch(() => {})
    if (mode === 'engineer') {
      api.get<Benchmark[]>('/benchmarks').catch(() => []).then(b => setBenchmarks(Array.isArray(b) ? b.slice(0, 5) : []))
    }
  }, [mode])

  return (
    <div className="space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">STRAT-OS</h1>
          <p className="text-xs text-gray-500 mt-0.5">EV Kart Race Engineering Platform</p>
        </div>
        {status && (
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-600 font-mono">v{status.version}</span>
            <StatusBadge status={status.storage.status} />
            {pendingJobs > 0 && (
              <span className="text-xs bg-gold bg-opacity-20 text-gold border border-gold border-opacity-40 rounded px-2 py-0.5 font-mono animate-pulse">
                {pendingJobs} job{pendingJobs !== 1 ? 's' : ''} running
              </span>
            )}
          </div>
        )}
      </div>

      {/* Stat grid */}
      {status && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Sessions" value={status.stats.sessions} to="/sessions" />
          <StatCard label="Drivers"  value={status.stats.drivers}  to="/drivers" />
          <div className="rounded-lg border border-border bg-surface p-4 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400 uppercase tracking-wider">Storage</span>
              <StatusBadge status={status.storage.status} />
            </div>
            <StorageBar pct={status.storage.used_pct} status={status.storage.status} />
            <span className="text-xs text-gray-600 font-mono">{status.storage.used_pct.toFixed(1)}% used</span>
          </div>
          <div className="rounded-lg border border-border bg-surface p-4 flex flex-col justify-between">
            <span className="text-xs text-gray-400 uppercase tracking-wider">Quick Actions</span>
            <div className="flex flex-col gap-1 mt-2">
              <Link to="/upload" className="text-xs text-accent hover:underline">+ Upload session</Link>
              {mode === 'engineer' && <Link to="/compare" className="text-xs text-gray-400 hover:text-white">Compare laps →</Link>}
              <Link to="/compliance" className="text-xs text-gray-400 hover:text-white">Compliance →</Link>
            </div>
          </div>
        </div>
      )}

      {/* Main grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Recent sessions */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Recent Sessions</h2>
            <Link to="/sessions" className="text-xs text-accent hover:underline">View all →</Link>
          </div>
          {recentSessions.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-6 text-center">
              <p className="text-gray-500 text-sm">No sessions yet.</p>
              <Link to="/upload" className="text-accent text-sm hover:underline mt-1 block">Upload your first AiM CSV →</Link>
            </div>
          ) : (
            <div className="space-y-1.5">
              {recentSessions.map(s => (
                <Link key={s.id} to={`/sessions/${s.id}`}
                  className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2.5 hover:border-accent transition-colors">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${TYPE_DOT[s.session_type] ?? 'bg-gray-500'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white truncate">
                      {s.driver_name}
                      <span className="text-gray-500 text-xs ml-2">{s.kart_name}</span>
                    </div>
                    <div className="text-xs text-gray-500 font-mono">{s.date} · {s.session_type}</div>
                  </div>
                  <div className="text-right shrink-0">
                    {s.best_lap_s ? (
                      <div className="text-accent font-mono text-xs font-bold">{fmt(s.best_lap_s)}</div>
                    ) : (
                      <div className="text-gray-600 text-xs">—</div>
                    )}
                    <div className="text-gray-600 text-xs">{s.lap_count} laps</div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Driver roster + ML */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Driver Roster</h2>
            <Link to="/drivers" className="text-xs text-accent hover:underline">Manage →</Link>
          </div>
          {drivers.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-6 text-center">
              <p className="text-gray-500 text-sm">No drivers yet.</p>
              <Link to="/drivers" className="text-accent text-sm hover:underline mt-1 block">Add a driver →</Link>
            </div>
          ) : (
            <div className="space-y-1.5">
              {drivers.map(d => (
                <DriverCard key={d.id} driver={d} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Engineer-only benchmarks */}
      {mode === 'engineer' && benchmarks.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">All-Time Benchmarks</h2>
          <div className="rounded-lg border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-surface text-xs text-gray-400 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3 text-left">Driver</th>
                  <th className="px-4 py-3 text-left">Kart</th>
                  <th className="px-4 py-3 text-right">Best Ever</th>
                  <th className="px-4 py-3 text-right">Theoretical Best</th>
                </tr>
              </thead>
              <tbody>
                {benchmarks.map((b, i) => (
                  <tr key={i} className="border-t border-border hover:bg-surface transition-colors">
                    <td className="px-4 py-2.5 text-white">{b.driver_name ?? `Driver #${b.driver_id}`}</td>
                    <td className="px-4 py-2.5 text-gray-400">{b.kart_name ?? `Kart #${b.kart_id}`}</td>
                    <td className="px-4 py-2.5 text-right font-mono font-bold text-accent">{b.best_ever_s ? fmt(b.best_ever_s) : '—'}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-gold">{b.theoretical_best_s ? fmt(b.theoretical_best_s) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Day Report generator */}
      <div className="rounded-lg border border-border bg-surface p-4 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Day Report</h2>
          <p className="text-xs text-gray-500 mt-0.5">Generate a full PDF analysis — lap times, energy, tire pressures, ML suggestions.</p>
        </div>
        <DayReportDownload />
      </div>

      {mode === 'beginner' && (
        <div className="rounded-lg border border-border bg-surface p-4 text-sm text-gray-400 flex items-start gap-3">
          <span className="text-accent text-lg shrink-0">ℹ</span>
          <div>
            <span className="text-white font-bold">Beginner mode active.</span> Advanced charts, simulation, and telemetry panels are hidden.
            Switch to <span className="text-accent">Engineer mode</span> in the sidebar to unlock everything.
          </div>
        </div>
      )}
    </div>
  )
}

function DayReportDownload() {
  const today = new Date().toISOString().slice(0, 10)
  const [date, setDate] = useState(today)
  return (
    <div className="flex items-center gap-2">
      <input type="date" value={date} onChange={e => setDate(e.target.value)}
        className="bg-bg border border-border rounded px-2 py-1.5 text-white text-sm focus:outline-none focus:border-accent" />
      <a href={`/api/reports/day/${date}`} target="_blank" rel="noreferrer"
        className="px-4 py-1.5 bg-accent text-bg text-sm font-bold rounded hover:opacity-90 whitespace-nowrap">
        Download PDF
      </a>
    </div>
  )
}

function StatCard({ label, value, to }: { label: string; value: number | string; to?: string }) {
  const inner = (
    <div className="rounded-lg border border-border bg-surface p-4 flex flex-col gap-1 hover:border-accent transition-colors">
      <span className="text-xs text-gray-400 uppercase tracking-wider">{label}</span>
      <span className="text-3xl font-bold font-mono text-white">{value}</span>
    </div>
  )
  return to ? <Link to={to}>{inner}</Link> : inner
}

function DriverCard({ driver }: { driver: Driver }) {
  const [style, setStyle] = useState<{ style_label: string; confidence: number } | null>(null)
  useEffect(() => {
    api.get<{ style_label: string; confidence: number }>(`/ml/driver/${driver.id}/style`).then(setStyle).catch(() => {})
  }, [driver.id])
  const STYLE_COLOR: Record<string, string> = {
    aggressive: 'text-red', smooth: 'text-green', balanced: 'text-accent', inconsistent: 'text-gold'
  }
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2.5">
      <div className="w-8 h-8 rounded-full bg-accent bg-opacity-20 flex items-center justify-center shrink-0">
        <span className="text-accent text-sm font-bold">{driver.name.charAt(0).toUpperCase()}</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm text-white font-medium truncate">{driver.name}</div>
        {driver.notes && <div className="text-xs text-gray-500 truncate">{driver.notes}</div>}
      </div>
      {style && (
        <span className={`text-xs font-bold capitalize ${STYLE_COLOR[style.style_label] ?? 'text-gray-400'}`}>
          {style.style_label}
        </span>
      )}
      {!style && <span className="text-xs text-gray-600">No data</span>}
    </div>
  )
}
