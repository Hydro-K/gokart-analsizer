import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, Session, Driver, Kart, Track } from '../api'

export default function Sessions() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [drivers, setDrivers] = useState<Record<number, Driver>>({})
  const [karts, setKarts]     = useState<Record<number, Kart>>({})
  const [tracks, setTracks]   = useState<Record<number, Track>>({})

  useEffect(() => {
    api.get<Session[]>('/sessions').then(setSessions).catch(() => {})
    api.get<Driver[]>('/drivers').then(ds => setDrivers(Object.fromEntries(ds.map(d => [d.id, d])))).catch(() => {})
    api.get<Kart[]>('/karts').then(ks => setKarts(Object.fromEntries(ks.map(k => [k.id, k])))).catch(() => {})
    api.get<Track[]>('/tracks').then(ts => setTracks(Object.fromEntries(ts.map(t => [t.id, t])))).catch(() => {})
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Sessions</h1>
        <Link to="/upload" className="px-4 py-2 bg-accent text-bg font-bold rounded text-sm hover:opacity-90">
          Upload Session
        </Link>
      </div>

      {sessions.length === 0 ? (
        <p className="text-gray-400">No sessions yet.</p>
      ) : (
        <div className="space-y-2">
          {sessions.map(s => (
            <Link key={s.id} to={`/sessions/${s.id}`}
              className="flex items-center gap-4 rounded-lg border border-border bg-surface px-4 py-3 hover:border-accent transition-colors">
              <div className="flex-1 grid grid-cols-4 gap-2 min-w-0 text-sm">
                <div>
                  <div className="text-xs text-gray-400">Driver</div>
                  <div className="text-white truncate">{drivers[s.driver_id]?.name ?? `#${s.driver_id}`}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-400">Kart</div>
                  <div className="text-white truncate">{karts[s.kart_id]?.name ?? `#${s.kart_id}`}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-400">Track</div>
                  <div className="text-white truncate">{tracks[s.track_id]?.name ?? `#${s.track_id}`}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-400">Date</div>
                  <div className="text-white font-mono">{s.date}</div>
                </div>
              </div>
              <span className="text-xs text-gray-400 shrink-0">{s.session_type}</span>
              <span className="text-accent text-xs">→</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
