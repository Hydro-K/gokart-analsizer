import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { api, Session, Lap, Recommendation } from '../api'
import { MetricCard } from '../components/common/MetricCard'
import { StatusBadge } from '../components/common/StatusBadge'

function fmt(s: number) {
  const m = Math.floor(s / 60)
  const sec = (s % 60).toFixed(3).padStart(6, '0')
  return `${m}:${sec}`
}

function delta(t: number, best: number) {
  const d = t - best
  if (d < 0.001) return null
  return `+${d.toFixed(3)}`
}

const PRIORITY_COLOR = ['text-red', 'text-orange', 'text-gold', 'text-accent', 'text-gray-400']
const CAT_ICON: Record<string, string> = {
  throttle: '⚡', gear: '⚙', braking: '🔴', consistency: '📊', energy: '🔋', default: '→'
}

export default function SessionDetail() {
  const { id } = useParams<{ id: string }>()
  const nav = useNavigate()
  const [session, setSession]     = useState<Session | null>(null)
  const [laps, setLaps]           = useState<Lap[]>([])
  const [recs, setRecs]           = useState<Recommendation[]>([])
  const [compliance, setCompliance] = useState<any>(null)
  const [deleting, setDeleting]   = useState(false)
  const [activeTab, setActiveTab] = useState<'laps'|'recs'|'compliance'>('laps')

  useEffect(() => {
    if (!id) return
    api.get<Session>(`/sessions/${id}`).then(setSession).catch(() => {})
    api.get<Lap[]>(`/sessions/${id}/laps`).then(setLaps).catch(() => {})
    api.get<Recommendation[]>(`/sessions/${id}/recommendations`).then(setRecs).catch(() => {})
    api.get(`/sessions/${id}/compliance`).then(setCompliance).catch(() => {})
  }, [id])

  const validLaps = laps.filter(l => l.is_valid)
  const bestLap   = validLaps.reduce<Lap | null>((b, l) => (!b || l.lap_time_s < b.lap_time_s) ? l : b, null)
  const avgTime   = validLaps.length ? validLaps.reduce((s, l) => s + l.lap_time_s, 0) / validLaps.length : 0
  const stdTime   = validLaps.length > 1
    ? Math.sqrt(validLaps.reduce((s, l) => s + (l.lap_time_s - avgTime) ** 2, 0) / validLaps.length)
    : 0
  const consistency = avgTime > 0 ? Math.max(0, 100 - (stdTime / avgTime * 100)) : 100

  const deleteSession = async () => {
    if (!confirm('Delete this session and all its laps? This cannot be undone.')) return
    setDeleting(true)
    try {
      await api.delete(`/sessions/${id}`)
      nav('/sessions', { replace: true })
    } catch (err: any) {
      alert(err.message)
      setDeleting(false)
    }
  }

  if (!session) return (
    <div className="flex items-center justify-center h-48 text-gray-400 text-sm">Loading session...</div>
  )

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white tracking-tight">{session.session_type}</h1>
            {compliance && (
              <StatusBadge status={compliance.passed ? 'pass' : 'fail'} />
            )}
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-400 font-mono">
            <span>{session.date}</span>
            <span className="text-gray-600">·</span>
            <span>{session.driver_name}</span>
            <span className="text-gray-600">·</span>
            <span>{session.kart_name}</span>
            <span className="text-gray-600">·</span>
            <span>{session.track_name}</span>
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          <Link to={`/compare?session=${id}`}
            className="px-3 py-1.5 border border-border rounded text-xs hover:border-accent transition-colors">
            Compare
          </Link>
          <a href={`/api/export/session/${id}/report`}
            className="px-3 py-1.5 border border-border rounded text-xs hover:border-accent transition-colors">
            Export
          </a>
          <button onClick={deleteSession} disabled={deleting}
            className="px-3 py-1.5 border border-red border-opacity-50 text-red text-xs rounded hover:bg-red hover:bg-opacity-10 transition-colors disabled:opacity-40">
            {deleting ? '...' : 'Delete'}
          </button>
        </div>
      </div>

      {/* Stat row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <MetricCard label="Total Laps"   value={String(laps.length)} unit="" />
        <MetricCard label="Valid Laps"   value={String(validLaps.length)} unit="" />
        {bestLap && <MetricCard label="Best Lap" value={fmt(bestLap.lap_time_s)} unit="" highlight />}
        {avgTime > 0 && <MetricCard label="Avg Lap" value={fmt(avgTime)} unit="" />}
        <MetricCard label="Consistency" value={consistency.toFixed(1)} unit="%" highlight={consistency > 95} />
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-border">
        {(['laps', 'recs', 'compliance'] as const).map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
              activeTab === tab
                ? 'border-accent text-accent'
                : 'border-transparent text-gray-400 hover:text-white'
            }`}>
            {tab === 'recs' ? `Recommendations${recs.length ? ` (${recs.length})` : ''}` : tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Laps tab */}
      {activeTab === 'laps' && (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface text-gray-400 text-xs uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3 text-left">Lap</th>
                <th className="px-4 py-3 text-right">Time</th>
                <th className="px-4 py-3 text-right">Delta</th>
                <th className="px-4 py-3 text-center">Valid</th>
                <th className="px-4 py-3 text-center">Analyse</th>
              </tr>
            </thead>
            <tbody>
              {laps.map(l => {
                const d = bestLap ? delta(l.lap_time_s, bestLap.lap_time_s) : null
                const isBest = l.id === bestLap?.id
                return (
                  <tr key={l.id} className={`border-t border-border ${isBest ? 'bg-accent bg-opacity-5' : 'hover:bg-surface transition-colors'}`}>
                    <td className="px-4 py-2.5 text-white font-mono">
                      {l.lap_number}
                      {isBest && <span className="ml-2 text-gold text-xs font-bold">★ BEST</span>}
                    </td>
                    <td className={`px-4 py-2.5 text-right font-mono font-bold ${isBest ? 'text-accent' : 'text-white'}`}>
                      {fmt(l.lap_time_s)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-xs">
                      {d ? <span className="text-red">{d}</span> : <span className="text-gray-600">—</span>}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <StatusBadge status={l.is_valid ? 'ok' : 'warn'} />
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <Link to={`/laps/${l.id}`} className="text-accent text-xs font-bold hover:underline px-2 py-0.5 border border-accent border-opacity-30 rounded">
                        View →
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Recommendations tab */}
      {activeTab === 'recs' && (
        <div className="space-y-2">
          {recs.length === 0 ? (
            <div className="text-gray-400 text-sm rounded-lg border border-border bg-surface p-6 text-center">
              No recommendations yet. Upload more laps to generate tuning insights.
            </div>
          ) : (
            recs.sort((a, b) => a.priority - b.priority).map((r, i) => (
              <div key={i} className="rounded-lg border border-border bg-surface p-4 space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{CAT_ICON[r.category] ?? CAT_ICON.default}</span>
                  <span className={`text-xs font-bold uppercase tracking-wider ${PRIORITY_COLOR[Math.min(r.priority - 1, 4)]}`}>
                    P{r.priority} · {r.category}
                  </span>
                  <span className="ml-auto text-xs font-mono text-gray-500">{r.setting_key}</span>
                </div>
                <p className="text-sm text-white font-medium">{r.reason}</p>
                <div className="flex items-center gap-4 text-xs font-mono">
                  <span><span className="text-gray-400">Current:</span> <span className="text-orange">{String(r.current_value)}</span></span>
                  <span className="text-gray-600">→</span>
                  <span><span className="text-gray-400">Recommended:</span> <span className="text-accent font-bold">{String(r.recommended_value)}</span></span>
                  {r.delta != null && <span className="text-gray-400">({String(r.delta)})</span>}
                </div>
                {r.predicted_outcome && r.predicted_outcome !== r.reason && (
                  <p className="text-xs text-gray-400 italic">{r.predicted_outcome}</p>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Compliance tab */}
      {activeTab === 'compliance' && compliance && (
        <div className="space-y-2">
          <div className="flex items-center gap-3 mb-3">
            <StatusBadge status={compliance.passed ? 'pass' : 'fail'} />
            <span className="text-sm text-gray-300">
              {compliance.passed ? 'All rules passed' : 'Compliance failures detected'}
            </span>
          </div>
          {compliance.items?.map((item: any, i: number) => (
            <div key={i} className="rounded-lg border border-border bg-surface px-4 py-3 space-y-1">
              <div className="flex items-center gap-3">
                <StatusBadge status={item.status} />
                <span className="text-white text-sm font-medium">{item.rule_name}</span>
                <span className="text-gray-500 text-xs ml-auto font-mono">{item.rule_section}</span>
              </div>
              <div className="flex gap-4 text-xs font-mono text-gray-400 pl-1">
                <span>Measured: <span className="text-white">{item.current_value}</span></span>
                <span>Limit: <span className="text-white">{item.limit_value}</span></span>
              </div>
              {item.actionable && item.actionable !== 'No action needed.' && (
                <p className="text-xs text-accent pl-1">→ {item.actionable}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
