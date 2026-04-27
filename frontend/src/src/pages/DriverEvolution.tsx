import { useEffect, useState } from 'react'
import { api, Driver } from '../api'
import { fmtLap } from '../utils/units'
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Legend
} from 'recharts'

interface EvolutionPoint {
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

const SESSION_TYPE_COLOR: Record<string, string> = {
  Testing:    '#4488FF',
  Practice:   '#4488FF',
  Sprint:     '#FFD700',
  Qualifying: '#FFD700',
  Race:       '#FF4444',
}

const CHART_STYLE = {
  grid: '#1c2e3e',
  axis: '#4a6070',
  tooltip: { background: '#0a1520', border: '1px solid #1c2e3e', borderRadius: 6, fontSize: 12 },
}

const DRIVER_COLORS = ['#00BFFF','#00FF88','#FFD700','#FF4444','#FF88FF']

export default function DriverEvolution() {
  const [drivers, setDrivers] = useState<Driver[]>([])
  const [selected, setSelected] = useState<number[]>([])
  const [data, setData] = useState<Record<number, EvolutionPoint[]>>({})
  const [loading, setLoading] = useState(false)
  const [activeMetric, setActiveMetric] = useState<'best_lap_s'|'avg_lap_s'|'cv_pct'|'avg_smoothness'>('best_lap_s')

  useEffect(() => {
    api.get<Driver[]>('/drivers').then(d => {
      setDrivers(d)
      if (d.length > 0) setSelected([d[0].id])
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (selected.length === 0) return
    setLoading(true)
    Promise.all(
      selected.map(id =>
        api.get<EvolutionPoint[]>(`/drivers/${id}/evolution`)
          .then(pts => ({ id, pts }))
          .catch(() => ({ id, pts: [] }))
      )
    ).then(results => {
      const next: Record<number, EvolutionPoint[]> = {}
      results.forEach(r => { next[r.id] = r.pts })
      setData(prev => ({ ...prev, ...next }))
    }).finally(() => setLoading(false))
  }, [selected])

  const toggleDriver = (id: number) => {
    setSelected(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  // Build unified chart dataset: one point per session per driver
  // Key by (date + session_type + track) for consistent x-axis
  const allKeys = [...new Set(
    selected.flatMap(id => (data[id] ?? []).map(p => `${p.date}|${p.session_type}|${p.session_id}`))
  )].sort()

  const chartData = allKeys.map(key => {
    const [date, stype, sid] = key.split('|')
    const point: Record<string, any> = {
      label: `${date.slice(5)} ${stype.slice(0,3)}`,
      fullLabel: `${date} · ${stype}`,
      session_id: Number(sid),
    }
    selected.forEach(id => {
      const match = (data[id] ?? []).find(p => `${p.date}|${p.session_type}|${p.session_id}` === key)
      if (match) {
        point[`d${id}_best`]    = match.best_lap_s
        point[`d${id}_avg`]     = match.avg_lap_s
        point[`d${id}_cv`]      = match.cv_pct
        point[`d${id}_smooth`]  = match.avg_smoothness
      }
    })
    return point
  })

  const metricKey = (driverId: number) => {
    switch (activeMetric) {
      case 'best_lap_s':   return `d${driverId}_best`
      case 'avg_lap_s':    return `d${driverId}_avg`
      case 'cv_pct':       return `d${driverId}_cv`
      case 'avg_smoothness': return `d${driverId}_smooth`
    }
  }

  const metricLabel = {
    best_lap_s:    'Best Lap Time',
    avg_lap_s:     'Avg Lap Time',
    cv_pct:        'Consistency (CV%)',
    avg_smoothness:'Smoothness Score',
  }

  const formatYAxis = (v: number) => {
    if (activeMetric === 'best_lap_s' || activeMetric === 'avg_lap_s') return fmtLap(v)
    if (activeMetric === 'cv_pct') return `${v.toFixed(1)}%`
    return v.toFixed(0)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Driver Evolution</h1>
        <p className="text-xs text-gray-500 mt-1">Lap time trends, consistency, and smoothness across all sessions</p>
      </div>

      {/* Driver selector */}
      <div className="flex flex-wrap gap-2">
        {drivers.map((d, i) => {
          const color = DRIVER_COLORS[i % DRIVER_COLORS.length]
          const on = selected.includes(d.id)
          return (
            <button key={d.id} onClick={() => toggleDriver(d.id)}
              className="px-3 py-1.5 rounded-full text-sm font-medium border transition-all"
              style={{
                borderColor: color,
                background: on ? color : 'transparent',
                color: on ? '#0a1520' : color,
              }}>
              {d.name}
            </button>
          )
        })}
      </div>

      {/* Metric selector */}
      <div className="flex gap-2 flex-wrap">
        {(Object.keys(metricLabel) as Array<keyof typeof metricLabel>).map(m => (
          <button key={m} onClick={() => setActiveMetric(m as any)}
            className={`px-3 py-1 text-xs rounded border transition-colors ${
              activeMetric === m
                ? 'bg-accent text-bg border-accent font-bold'
                : 'border-border text-gray-400 hover:border-accent hover:text-white'
            }`}>
            {metricLabel[m]}
          </button>
        ))}
      </div>

      {loading && <div className="text-gray-500 text-sm text-center py-8">Loading evolution data...</div>}

      {/* Main trend chart */}
      {!loading && chartData.length > 0 && (
        <div className="bg-surface border border-border rounded-lg p-4">
          <h2 className="text-xs text-gray-400 uppercase tracking-wider mb-4">{metricLabel[activeMetric]} over Sessions</h2>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 30, left: 20 }}>
                <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                <XAxis dataKey="label" stroke={CHART_STYLE.axis} tick={{ fontSize: 9 }} angle={-35} textAnchor="end" interval={0} />
                <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 9 }} tickFormatter={formatYAxis}
                  label={{ value: metricLabel[activeMetric], angle: -90, position: 'insideLeft', fill: '#6a8090', fontSize: 10, offset: -5 }} />
                <Tooltip
                  contentStyle={CHART_STYLE.tooltip}
                  labelStyle={{ color: '#aaa' }}
                  formatter={(v: any, name: string) => {
                    if (v === null || v === undefined) return ['—', name]
                    if (activeMetric === 'best_lap_s' || activeMetric === 'avg_lap_s') return [fmtLap(v), name]
                    if (activeMetric === 'cv_pct') return [`${(+v).toFixed(2)}%`, name]
                    return [`${(+v).toFixed(1)}`, name]
                  }}
                />
                {selected.map((id, i) => {
                  const driver = drivers.find(d => d.id === id)
                  const color = DRIVER_COLORS[i % DRIVER_COLORS.length]
                  return (
                    <Line key={id}
                      type="monotone"
                      dataKey={metricKey(id)}
                      name={driver?.name ?? `Driver ${id}`}
                      stroke={color}
                      strokeWidth={2}
                      dot={{ r: 3, fill: color, strokeWidth: 0 }}
                      connectNulls
                      isAnimationActive={false}
                    />
                  )
                })}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {!loading && chartData.length === 0 && selected.length > 0 && (
        <div className="text-gray-500 text-sm text-center py-10 bg-surface border border-border rounded-lg">
          No session data found for selected driver(s). Upload sessions first.
        </div>
      )}

      {/* Per-driver session tables */}
      {selected.map((id, di) => {
        const driver = drivers.find(d => d.id === id)
        const pts = data[id] ?? []
        const color = DRIVER_COLORS[di % DRIVER_COLORS.length]
        if (pts.length === 0) return null
        return (
          <div key={id} className="bg-surface border border-border rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-border flex items-center gap-2">
              <span className="w-3 h-3 rounded-full inline-block" style={{ background: color }} />
              <span className="font-bold text-white text-sm">{driver?.name}</span>
              <span className="text-gray-500 text-xs ml-1">{pts.length} sessions</span>
              {pts.length >= 2 && (() => {
                const first = pts[0].best_lap_s
                const last  = pts[pts.length - 1].best_lap_s
                if (!first || !last) return null
                const delta = last - first
                return (
                  <span className={`text-xs font-mono ml-auto ${delta < 0 ? 'text-green' : 'text-red'}`}>
                    {delta < 0 ? '▼' : '▲'} {Math.abs(delta).toFixed(3)}s overall
                  </span>
                )
              })()}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-bg text-gray-500 uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-2 text-left">Date</th>
                    <th className="px-4 py-2 text-left">Type</th>
                    <th className="px-4 py-2 text-left">Track</th>
                    <th className="px-4 py-2 text-right">Laps</th>
                    <th className="px-4 py-2 text-right">Best</th>
                    <th className="px-4 py-2 text-right">Avg</th>
                    <th className="px-4 py-2 text-right">StdDev</th>
                    <th className="px-4 py-2 text-right">CV%</th>
                    <th className="px-4 py-2 text-right">Smooth</th>
                  </tr>
                </thead>
                <tbody>
                  {pts.map((p, idx) => {
                    const prevBest = idx > 0 ? pts[idx - 1].best_lap_s : null
                    const improvement = (prevBest && p.best_lap_s) ? prevBest - p.best_lap_s : null
                    const stColor = SESSION_TYPE_COLOR[p.session_type] ?? '#888'
                    return (
                      <tr key={p.session_id} className="border-t border-border hover:bg-bg transition-colors">
                        <td className="px-4 py-2 font-mono text-gray-300">{p.date}</td>
                        <td className="px-4 py-2">
                          <span className="px-1.5 py-0.5 rounded text-xs font-bold" style={{ color: stColor, borderColor: stColor, border: `1px solid ${stColor}` }}>
                            {p.session_type.slice(0, 4)}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-gray-400">{p.track_name}</td>
                        <td className="px-4 py-2 text-right font-mono text-gray-400">{p.lap_count}</td>
                        <td className="px-4 py-2 text-right font-mono font-bold text-accent">
                          {p.best_lap_s ? fmtLap(p.best_lap_s) : '—'}
                          {improvement !== null && (
                            <span className={`ml-1.5 text-xs ${improvement > 0 ? 'text-green' : 'text-red'}`}>
                              {improvement > 0 ? '▼' : '▲'}{Math.abs(improvement).toFixed(3)}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-right font-mono text-gray-300">{p.avg_lap_s ? fmtLap(p.avg_lap_s) : '—'}</td>
                        <td className="px-4 py-2 text-right font-mono text-gray-400">{p.std_dev_s?.toFixed(3) ?? '—'}</td>
                        <td className={`px-4 py-2 text-right font-mono font-bold ${
                          p.cv_pct === null ? 'text-gray-500' : p.cv_pct < 2 ? 'text-green' : p.cv_pct < 5 ? 'text-gold' : 'text-red'
                        }`}>
                          {p.cv_pct !== null ? `${p.cv_pct.toFixed(2)}%` : '—'}
                        </td>
                        <td className={`px-4 py-2 text-right font-mono ${
                          p.avg_smoothness === null ? 'text-gray-500' : p.avg_smoothness > 75 ? 'text-green' : p.avg_smoothness > 50 ? 'text-gold' : 'text-red'
                        }`}>
                          {p.avg_smoothness?.toFixed(1) ?? '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )
      })}
    </div>
  )
}
