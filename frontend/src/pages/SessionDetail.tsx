import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api, Session, Lap, ComplianceResult } from '../api'
import { MetricCard } from '../components/common/MetricCard'
import { StatusBadge } from '../components/common/StatusBadge'
import { useUIStore } from '../store/uiStore'

function fmt(s: number) {
  const m = Math.floor(s / 60)
  const sec = (s % 60).toFixed(3).padStart(6, '0')
  return `${m}:${sec}`
}

import { ComplianceResult } from '../api'

export default function SessionDetail() {
  const { id } = useParams<{ id: string }>()
  const [session, setSession] = useState<Session | null>(null)
  const [laps, setLaps] = useState<Lap[]>([])
  const [compliance, setCompliance] = useState<ComplianceResult | null>(null)
  const [recs, setRecs] = useState<string[]>([])
  const mode = useUIStore(s => s.mode)

  useEffect(() => {
    if (!id) return
    api.get<Session>(`/sessions/${id}`).then(setSession).catch(() => {})
    api.get<Lap[]>(`/sessions/${id}/laps`).then(setLaps).catch(() => {})
    api.get<ComplianceResult>(`/sessions/${id}/compliance`).then(setCompliance).catch(() => {})
    api.get<string[]>(`/sessions/${id}/recommendations`).then(setRecs).catch(() => {})
  }, [id])

  const validLaps = laps.filter(l => l.is_valid)
  const bestLap = validLaps.reduce<Lap | null>((b, l) => (!b || l.lap_time_s < b.lap_time_s) ? l : b, null)
  const avgTime = validLaps.length ? validLaps.reduce((s, l) => s + l.lap_time_s, 0) / validLaps.length : 0

  if (!session) return <div className="text-gray-400">Loading...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{session.session_type}</h1>
          <p className="text-gray-400 font-mono text-sm">{session.date}</p>
        </div>
        <div className="flex gap-2">
          <Link to={`/sessions/${id}/laps`}
            className="px-3 py-1.5 border border-border rounded text-sm hover:border-accent transition-colors">
            Lap Analysis
          </Link>
          <a href={`/api/export/session/${id}/report`}
            className="px-3 py-1.5 border border-border rounded text-sm hover:border-accent transition-colors">
            Export
          </a>
        </div>
      </div>

      {/* Lap stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Total Laps" value={laps.length} />
        <MetricCard label="Valid Laps" value={validLaps.length} />
        {bestLap && <MetricCard label="Best Lap" value={fmt(bestLap.lap_time_s)} highlight />}
        {avgTime > 0 && <MetricCard label="Avg Lap" value={fmt(avgTime)} />}
      </div>

      {/* Lap table */}
      <div>
        <h2 className="text-lg font-bold text-white mb-3">Laps</h2>
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface text-gray-400 text-xs uppercase">
              <tr>
                <th className="px-4 py-2 text-left">Lap</th>
                <th className="px-4 py-2 text-right">Time</th>
                <th className="px-4 py-2 text-center">Valid</th>
                <th className="px-4 py-2 text-center">Detail</th>
              </tr>
            </thead>
            <tbody>
              {laps.map(l => (
                <tr key={l.id} className={`border-t border-border ${l.id === bestLap?.id ? 'bg-accent bg-opacity-5' : ''}`}>
                  <td className="px-4 py-2 text-white font-mono">
                    {l.lap_number}
                    {l.id === bestLap?.id && <span className="ml-2 text-gold text-xs">★ best</span>}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-white">{fmt(l.lap_time_s)}</td>
                  <td className="px-4 py-2 text-center">
                    <StatusBadge status={l.is_valid ? 'ok' : 'warn'} />
                  </td>
                  <td className="px-4 py-2 text-center">
                    <Link to={`/laps/${l.id}`} className="text-accent text-xs hover:underline">View →</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Compliance */}
      {compliance && (
        <div>
          <div className="flex items-center gap-3 mb-3">
            <h2 className="text-lg font-bold text-white">Compliance</h2>
            <StatusBadge status={compliance.passed ? 'pass' : 'fail'} />
          </div>
          <div className="space-y-1">
            {compliance.items.map((item, i) => (
              <div key={i} className="flex items-center gap-3 rounded px-3 py-2 bg-surface border border-border text-sm">
                <StatusBadge status={item.status} />
                <span className="text-white">{item.rule_name}</span>
                <span className="text-gray-400 text-xs ml-auto">{item.current_value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {recs.length > 0 && (
        <div>
          <h2 className="text-lg font-bold text-white mb-3">Recommendations</h2>
          <ul className="space-y-2">
            {recs.map((r, i) => (
              <li key={i} className="flex gap-2 text-sm text-gray-300 bg-surface border border-border rounded px-3 py-2">
                <span className="text-accent shrink-0">→</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
