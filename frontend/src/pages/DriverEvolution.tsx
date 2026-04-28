import { useEffect, useState } from 'react'
import { api } from '../api'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine
} from 'recharts'

interface Driver { id: number; name: string; notes: string; created_at: string }
interface EvoPoint {
  session_id: number
  date: string
  session_type: string
  track_name: string
  lap_count: number
  best_lap_s: number | null
  avg_lap_s: number | null
  std_dev_s: number | null
  cv_pct: number | null
  avg_smoothness: number | null
  avg_throttle_var: number | null
}

const CHART_STYLE = {
  grid: '#1c2e3e', axis: '#4a6070',
  tooltip: { background: '#0a1520', border: '1px solid #1c2e3e', borderRadius: 6, fontSize: 12 },
}

function fmt(s: number | null) {
  if (!s) return '—'
  const m = Math.floor(s / 60)
  const sec = (s % 60).toFixed(3).padStart(6, '0')
  return `${m}:${sec}`
}

const TRACK_COLORS = ['#00BFFF','#00FF88','#FFD700','#FF8C00','#FF4444','#AA88FF']

export default function DriverEvolution() {
  const [drivers, setDrivers] = useState<Driver[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [selectedTrack, setSelectedTrack] = useState<string>('all')
  const [evo, setEvo] = useState<EvoPoint[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.get<Driver[]>('/drivers').then(setDrivers).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setLoading(true)
    api.get<EvoPoint[]>(`/drivers/${selectedId}/evolution`)
      .then(setEvo)
      .catch(() => setEvo([]))
      .finally(() => setLoading(false))
  }, [selectedId])

  const tracks = ['all', ...Array.from(new Set(evo.map(e => e.track_name)))]
  const filtered = selectedTrack === 'all' ? evo : evo.filter(e => e.track_name === selectedTrack)

  // Group by track for multi-line chart
  const trackList = Array.from(new Set(filtered.map(e => e.track_name)))
  const chartData = filtered.map((e, i) => ({
    label: `${e.date.slice(5)} ${e.session_type.slice(0, 4)}`,
    date: e.date,
    best: e.best_lap_s,
    avg: e.avg_lap_s,
    cv: e.cv_pct,
    smooth: e.avg_smoothness,
    track: e.track_name,
    laps: e.lap_count,
    session_id: e.session_id,
  }))

  const overallBest = filtered.reduce<number | null>((b, e) =>
    e.best_lap_s != null ? (b == null || e.best_lap_s < b ? e.best_lap_s : b) : b, null)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4 flex-wrap">
        <h1 className="text-2xl font-bold text-white tracking-tight">Driver Evolution</h1>
        <select value={selectedId ?? ''} onChange={e => setSelectedId(+e.target.value || null)}
          className="bg-surface border border-border rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-accent">
          <option value="">Select driver…</option>
          {drivers.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        {tracks.length > 2 && (
          <select value={selectedTrack} onChange={e => setSelectedTrack(e.target.value)}
            className="bg-surface border border-border rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-accent">
            {tracks.map(t => <option key={t} value={t}>{t === 'all' ? 'All tracks' : t}</option>)}
          </select>
        )}
      </div>

      {!selectedId ? (
        <div className="text-gray-400 text-sm py-12 text-center">Select a driver to view their lap time progression over time.</div>
      ) : loading ? (
        <div className="text-gray-400 text-sm py-12 text-center">Loading...</div>
      ) : filtered.length === 0 ? (
        <div className="text-gray-400 text-sm py-12 text-center">No sessions found for this driver.</div>
      ) : (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="rounded-lg border border-border bg-surface p-3">
              <div className="text-xs text-gray-400 uppercase tracking-wider">Sessions</div>
              <div className="text-2xl font-bold text-white mt-1">{filtered.length}</div>
            </div>
            <div className="rounded-lg border border-border bg-surface p-3">
              <div className="text-xs text-gray-400 uppercase tracking-wider">All-Time Best</div>
              <div className="text-2xl font-bold text-accent font-mono mt-1">{fmt(overallBest)}</div>
            </div>
            <div className="rounded-lg border border-border bg-surface p-3">
              <div className="text-xs text-gray-400 uppercase tracking-wider">Total Laps</div>
              <div className="text-2xl font-bold text-white mt-1">{filtered.reduce((s, e) => s + e.lap_count, 0)}</div>
            </div>
            <div className="rounded-lg border border-border bg-surface p-3">
              <div className="text-xs text-gray-400 uppercase tracking-wider">Avg Consistency</div>
              <div className="text-2xl font-bold text-white mt-1">
                {filtered.filter(e => e.cv_pct != null).length > 0
                  ? (filtered.reduce((s, e) => s + (e.cv_pct ?? 0), 0) / filtered.filter(e => e.cv_pct != null).length).toFixed(1) + '%'
                  : '—'}
              </div>
            </div>
          </div>

          {/* Best lap progression */}
          <div className="bg-surface border border-border rounded-lg p-4">
            <h2 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Best Lap Progression</h2>
            <div style={{ height: 260 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 20, left: 10 }}>
                  <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                  <XAxis dataKey="label" stroke={CHART_STYLE.axis} tick={{ fontSize: 9 }} angle={-30} textAnchor="end" />
                  <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }}
                    tickFormatter={v => fmt(v)} domain={['auto', 'auto']} />
                  <Tooltip contentStyle={CHART_STYLE.tooltip}
                    formatter={(v: any) => [fmt(+v), 'Best Lap']}
                    labelFormatter={(l) => l} />
                  {overallBest && (
                    <ReferenceLine y={overallBest} stroke="#00FF88" strokeDasharray="4 4"
                      label={{ value: 'PB', fill: '#00FF88', fontSize: 10 }} />
                  )}
                  <Line type="monotone" dataKey="best" name="Best Lap" stroke="#00BFFF"
                    strokeWidth={2} dot={{ r: 4, fill: '#00BFFF' }} connectNulls />
                  <Line type="monotone" dataKey="avg" name="Avg Lap" stroke="#6a8090"
                    strokeWidth={1.5} strokeDasharray="4 4" dot={false} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Consistency trend */}
          {filtered.some(e => e.cv_pct != null) && (
            <div className="bg-surface border border-border rounded-lg p-4">
              <h2 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Lap-Time Consistency (CV%) — lower is better</h2>
              <div style={{ height: 180 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 20, left: 10 }}>
                    <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" stroke={CHART_STYLE.axis} tick={{ fontSize: 9 }} angle={-30} textAnchor="end" />
                    <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} unit="%" />
                    <Tooltip contentStyle={CHART_STYLE.tooltip}
                      formatter={(v: any) => [`${(+v).toFixed(2)}%`, 'CV']} />
                    <ReferenceLine y={3} stroke="#00FF88" strokeDasharray="4 4"
                      label={{ value: 'Target 3%', fill: '#00FF88', fontSize: 9 }} />
                    <Line type="monotone" dataKey="cv" name="CV%" stroke="#FFD700"
                      strokeWidth={2} dot={{ r: 3, fill: '#FFD700' }} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Smoothness trend */}
          {filtered.some(e => e.avg_smoothness != null) && (
            <div className="bg-surface border border-border rounded-lg p-4">
              <h2 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Driving Smoothness Score — higher is better</h2>
              <div style={{ height: 180 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 20, left: 10 }}>
                    <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" stroke={CHART_STYLE.axis} tick={{ fontSize: 9 }} angle={-30} textAnchor="end" />
                    <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} domain={[0, 100]} />
                    <Tooltip contentStyle={CHART_STYLE.tooltip}
                      formatter={(v: any) => [`${(+v).toFixed(1)}`, 'Smoothness']} />
                    <Line type="monotone" dataKey="smooth" name="Smoothness"
                      stroke="#00FF88" strokeWidth={2} dot={{ r: 3, fill: '#00FF88' }} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Session table */}
          <div className="rounded-lg border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-surface text-gray-400 text-xs uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3 text-left">Date</th>
                  <th className="px-4 py-3 text-left">Session</th>
                  <th className="px-4 py-3 text-left">Track</th>
                  <th className="px-4 py-3 text-right">Best</th>
                  <th className="px-4 py-3 text-right">Avg</th>
                  <th className="px-4 py-3 text-right">CV%</th>
                  <th className="px-4 py-3 text-right">Laps</th>
                </tr>
              </thead>
              <tbody>
                {[...filtered].reverse().map((e, i) => (
                  <tr key={e.session_id} className="border-t border-border hover:bg-surface transition-colors">
                    <td className="px-4 py-2.5 text-gray-300 font-mono text-xs">{e.date}</td>
                    <td className="px-4 py-2.5 text-gray-300 text-xs">{e.session_type}</td>
                    <td className="px-4 py-2.5 text-gray-400 text-xs">{e.track_name}</td>
                    <td className="px-4 py-2.5 text-right font-mono font-bold text-accent">{fmt(e.best_lap_s)}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-gray-300">{fmt(e.avg_lap_s)}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-xs text-gray-400">
                      {e.cv_pct != null ? `${e.cv_pct.toFixed(1)}%` : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-right text-gray-400 text-xs">{e.lap_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
