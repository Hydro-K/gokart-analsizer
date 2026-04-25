import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, Session } from '../api'

const TYPE_COLOR: Record<string, string> = {
  'Race':       'text-red border-red',
  'Qualifying': 'text-gold border-gold',
  'Practice 1': 'text-accent border-accent',
  'Practice 2': 'text-accent border-accent',
  'Test':       'text-gray-400 border-gray-600',
}

function fmt(s: number) {
  const m = Math.floor(s / 60)
  const sec = (s % 60).toFixed(3).padStart(6, '0')
  return `${m}:${sec}`
}

export default function Sessions() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading]   = useState(true)
  const [deleting, setDeleting] = useState<number | null>(null)
  const nav = useNavigate()

  const load = () => {
    setLoading(true)
    api.get<Session[]>('/sessions')
      .then(setSessions)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const deleteSession = async (e: React.MouseEvent, id: number) => {
    e.preventDefault()
    e.stopPropagation()
    if (!confirm('Delete this session and all its laps? This cannot be undone.')) return
    setDeleting(id)
    try {
      await api.delete(`/sessions/${id}`)
      setSessions(prev => prev.filter(s => s.id !== id))
    } catch (err: any) {
      alert(err.message)
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Sessions</h1>
          <p className="text-xs text-gray-500 mt-0.5">{sessions.length} session{sessions.length !== 1 ? 's' : ''} total</p>
        </div>
        <Link to="/upload"
          className="px-4 py-2 bg-accent text-bg font-bold rounded text-sm hover:opacity-90 transition-opacity">
          + Upload Session
        </Link>
      </div>

      {loading ? (
        <div className="text-gray-400 text-sm">Loading...</div>
      ) : sessions.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface p-8 text-center">
          <p className="text-gray-400 mb-3">No sessions yet.</p>
          <Link to="/upload" className="text-accent hover:underline text-sm">Upload your first AiM CSV →</Link>
        </div>
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface border-b border-border text-xs text-gray-400 uppercase tracking-wider">
                <th className="px-4 py-3 text-left">Date</th>
                <th className="px-4 py-3 text-left">Type</th>
                <th className="px-4 py-3 text-left">Driver</th>
                <th className="px-4 py-3 text-left">Kart</th>
                <th className="px-4 py-3 text-left">Track</th>
                <th className="px-4 py-3 text-right">Laps</th>
                <th className="px-4 py-3 text-right">Best Lap</th>
                <th className="px-4 py-3 text-center w-16"></th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s, i) => (
                <tr key={s.id}
                  onClick={() => nav(`/sessions/${s.id}`)}
                  className={`border-t border-border cursor-pointer hover:bg-surface transition-colors ${i % 2 === 0 ? 'bg-bg' : 'bg-surface bg-opacity-40'}`}>
                  <td className="px-4 py-3 font-mono text-gray-300 text-xs">{s.date}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-mono border rounded px-1.5 py-0.5 ${TYPE_COLOR[s.session_type] ?? 'text-gray-400 border-gray-600'}`}>
                      {s.session_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-white font-medium">{s.driver_name}</td>
                  <td className="px-4 py-3 text-gray-300">{s.kart_name}</td>
                  <td className="px-4 py-3 text-gray-300">{s.track_name}</td>
                  <td className="px-4 py-3 text-right font-mono text-gray-400">{s.lap_count}</td>
                  <td className="px-4 py-3 text-right font-mono">
                    {s.best_lap_s ? (
                      <span className="text-accent font-bold">{fmt(s.best_lap_s)}</span>
                    ) : (
                      <span className="text-gray-600">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={e => deleteSession(e, s.id)}
                      disabled={deleting === s.id}
                      className="text-xs text-gray-600 hover:text-red transition-colors disabled:opacity-30 px-2 py-1 rounded hover:bg-red hover:bg-opacity-10"
                    >
                      {deleting === s.id ? '...' : 'Del'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
