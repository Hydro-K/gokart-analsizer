import { useEffect, useState } from 'react'
import { api, Session, Lap, Telemetry, CornerOut, CompareResult } from '../api'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Cell, Legend
} from 'recharts'

function fmt(s: number) {
  const m = Math.floor(s / 60); const sec = (s % 60).toFixed(3).padStart(6, '0')
  return `${m}:${sec}`
}
const CHART_STYLE = { grid: '#1c2e3e', axis: '#4a6070', tooltip: { background: '#0a1520', border: '1px solid #1c2e3e', borderRadius: 6, fontSize: 12 } }
const COLORS = { a: '#00FF88', b: '#FF6B35' }

export default function Compare() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [lapsA, setLapsA]       = useState<Lap[]>([])
  const [lapsB, setLapsB]       = useState<Lap[]>([])
  const [sessionA, setSessionA] = useState('')
  const [sessionB, setSessionB] = useState('')
  const [lapA, setLapA]         = useState('')
  const [lapB, setLapB]         = useState('')
  const [teleA, setTeleA]       = useState<Telemetry | null>(null)
  const [teleB, setTeleB]       = useState<Telemetry | null>(null)
  const [delta, setDelta]       = useState<CompareResult | null>(null)
  const [cornersA, setCornersA] = useState<CornerOut[]>([])
  const [cornersB, setCornersB] = useState<CornerOut[]>([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  useEffect(() => {
    api.get<Session[]>('/sessions').then(setSessions).catch(() => {})
  }, [])

  useEffect(() => {
    if (!sessionA) { setLapsA([]); setLapA(''); return }
    api.get<Lap[]>(`/sessions/${sessionA}/laps`).then(laps => {
      const valid = laps.filter(l => l.is_valid)
      setLapsA(valid)
      const best = valid.reduce<Lap | null>((b, l) => (!b || l.lap_time_s < b.lap_time_s) ? l : b, null)
      if (best) setLapA(String(best.id))
    }).catch(() => {})
  }, [sessionA])

  useEffect(() => {
    if (!sessionB) { setLapsB([]); setLapB(''); return }
    api.get<Lap[]>(`/sessions/${sessionB}/laps`).then(laps => {
      const valid = laps.filter(l => l.is_valid)
      setLapsB(valid)
      const best = valid.reduce<Lap | null>((b, l) => (!b || l.lap_time_s < b.lap_time_s) ? l : b, null)
      if (best) setLapB(String(best.id))
    }).catch(() => {})
  }, [sessionB])

  const runCompare = async () => {
    if (!lapA || !lapB) return
    setLoading(true); setError('')
    try {
      const [ta, tb, d, ca, cb] = await Promise.all([
        api.get<Telemetry>(`/laps/${lapA}/telemetry?points=600`),
        api.get<Telemetry>(`/laps/${lapB}/telemetry?points=600`),
        api.post<CompareResult>('/laps/compare', { lap_ids: [+lapA, +lapB] }),
        api.get<CornerOut[]>(`/laps/${lapA}/corners`).catch(() => [] as CornerOut[]),
        api.get<CornerOut[]>(`/laps/${lapB}/corners`).catch(() => [] as CornerOut[]),
      ])
      setTeleA(ta); setTeleB(tb); setDelta(d)
      setCornersA(ca); setCornersB(cb)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // Normalised overlay: resample both speed traces to same time axis
  const overlayData = (() => {
    if (!teleA || !teleB) return []
    const maxT = Math.min(
      teleA.time[teleA.time.length - 1] ?? 0,
      teleB.time[teleB.time.length - 1] ?? 0
    )
    // interpolate B speed at every A timestamp
    const result: { t: number; a: number; b: number }[] = []
    let bi = 0
    for (let ai = 0; ai < teleA.time.length; ai++) {
      const t = teleA.time[ai]; if (t > maxT) break
      while (bi < teleB.time.length - 2 && teleB.time[bi + 1] < t) bi++
      const t0 = teleB.time[bi], t1 = teleB.time[bi + 1] ?? t0
      const frac = t1 > t0 ? (t - t0) / (t1 - t0) : 0
      const bSpeed = (teleB.speed_ms[bi] + frac * (teleB.speed_ms[bi + 1] - teleB.speed_ms[bi])) * 3.6
      result.push({ t: +t.toFixed(2), a: +(teleA.speed_ms[ai] * 3.6).toFixed(1), b: +bSpeed.toFixed(1) })
    }
    return result
  })()

  const deltaData = delta ? delta.delta_points.map(p => ({
    d: p.distance_m, dt: p.delta_s
  })) : []

  // Corner comparison
  const cornerOverlay = (() => {
    if (!cornersA.length && !cornersB.length) return []
    const len = Math.max(cornersA.length, cornersB.length)
    return Array.from({ length: len }, (_, i) => ({
      name: `C${i + 1}`,
      a_apex: cornersA[i]?.apex_speed_kmh ?? null,
      b_apex: cornersB[i]?.apex_speed_kmh ?? null,
    }))
  })()

  const lapAInfo = lapsA.find(l => l.id === +lapA)
  const lapBInfo = lapsB.find(l => l.id === +lapB)
  const timeDelta = delta ? delta.lap_b_time_s - delta.lap_a_time_s : null
  const sessA = sessions.find(s => s.id === +sessionA)
  const sessB = sessions.find(s => s.id === +sessionB)

  return (
    <div className="space-y-5 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Lap Comparison</h1>
        <p className="text-xs text-gray-500 mt-0.5">Overlay two laps — driver vs driver, setup vs setup, or session vs session</p>
      </div>

      {/* Selector panel */}
      <div className="grid grid-cols-2 gap-4">
        {/* Lap A */}
        <div className="bg-surface border-2 rounded-lg p-4 space-y-3" style={{ borderColor: COLORS.a }}>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full" style={{ background: COLORS.a }} />
            <span className="text-sm font-bold" style={{ color: COLORS.a }}>LAP A (Reference)</span>
          </div>
          <select value={sessionA} onChange={e => setSessionA(e.target.value)}
            className="w-full bg-bg border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-accent">
            <option value="">Select session...</option>
            {sessions.map(s => <option key={s.id} value={s.id}>{s.date} · {s.driver_name} · {s.session_type}</option>)}
          </select>
          {lapsA.length > 0 && (
            <select value={lapA} onChange={e => setLapA(e.target.value)}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-accent">
              {lapsA.map(l => <option key={l.id} value={l.id}>Lap {l.lap_number} — {fmt(l.lap_time_s)}</option>)}
            </select>
          )}
          {lapAInfo && (
            <div className="text-xs font-mono" style={{ color: COLORS.a }}>{fmt(lapAInfo.lap_time_s)} — {sessA?.driver_name ?? ''}</div>
          )}
        </div>

        {/* Lap B */}
        <div className="bg-surface border-2 rounded-lg p-4 space-y-3" style={{ borderColor: COLORS.b }}>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full" style={{ background: COLORS.b }} />
            <span className="text-sm font-bold" style={{ color: COLORS.b }}>LAP B (Comparison)</span>
          </div>
          <select value={sessionB} onChange={e => setSessionB(e.target.value)}
            className="w-full bg-bg border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-accent">
            <option value="">Select session...</option>
            {sessions.map(s => <option key={s.id} value={s.id}>{s.date} · {s.driver_name} · {s.session_type}</option>)}
          </select>
          {lapsB.length > 0 && (
            <select value={lapB} onChange={e => setLapB(e.target.value)}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-accent">
              {lapsB.map(l => <option key={l.id} value={l.id}>Lap {l.lap_number} — {fmt(l.lap_time_s)}</option>)}
            </select>
          )}
          {lapBInfo && (
            <div className="text-xs font-mono" style={{ color: COLORS.b }}>{fmt(lapBInfo.lap_time_s)} — {sessB?.driver_name ?? ''}</div>
          )}
        </div>
      </div>

      {error && <div className="text-red text-sm bg-red bg-opacity-10 border border-red rounded px-3 py-2">{error}</div>}

      <button onClick={runCompare} disabled={!lapA || !lapB || loading}
        className="px-6 py-2.5 bg-accent text-bg font-bold rounded hover:opacity-90 disabled:opacity-40 transition-opacity">
        {loading ? 'Comparing...' : 'Compare Laps'}
      </button>

      {/* Results */}
      {delta && (
        <div className="space-y-5">
          {/* Summary */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-surface border rounded-lg p-4 text-center space-y-1" style={{ borderColor: COLORS.a }}>
              <div className="text-xs text-gray-400">Lap A</div>
              <div className="text-2xl font-bold font-mono" style={{ color: COLORS.a }}>{fmt(delta.lap_a_time_s)}</div>
              <div className="text-xs text-gray-500">{sessA?.driver_name}</div>
            </div>
            <div className={`bg-surface border border-border rounded-lg p-4 text-center space-y-1`}>
              <div className="text-xs text-gray-400">Delta</div>
              <div className={`text-2xl font-bold font-mono ${timeDelta !== null && timeDelta > 0 ? 'text-red' : 'text-green'}`}>
                {timeDelta !== null ? (timeDelta > 0 ? '+' : '') + timeDelta.toFixed(3) + 's' : '—'}
              </div>
              <div className="text-xs text-gray-500">{timeDelta !== null && timeDelta > 0 ? 'B is slower' : 'B is faster'}</div>
            </div>
            <div className="bg-surface border rounded-lg p-4 text-center space-y-1" style={{ borderColor: COLORS.b }}>
              <div className="text-xs text-gray-400">Lap B</div>
              <div className="text-2xl font-bold font-mono" style={{ color: COLORS.b }}>{fmt(delta.lap_b_time_s)}</div>
              <div className="text-xs text-gray-500">{sessB?.driver_name}</div>
            </div>
          </div>

          {/* Speed overlay */}
          <div className="bg-surface border border-border rounded-lg p-4 space-y-2">
            <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Speed Overlay</h2>
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={overlayData} margin={{ top: 5, right: 10, bottom: 20, left: 10 }}>
                  <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                  <XAxis dataKey="t" stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }}
                    label={{ value: 'Time (s)', position: 'insideBottom', offset: -10, fill: '#6a8090', fontSize: 10 }} />
                  <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} unit=" km/h" />
                  <Tooltip contentStyle={CHART_STYLE.tooltip}
                    formatter={(v: any, name: string) => [`${v} km/h`, name === 'a' ? `A: ${sessA?.driver_name}` : `B: ${sessB?.driver_name}`]} />
                  <Legend wrapperStyle={{ fontSize: 11 }}
                    formatter={(v: string) => v === 'a' ? sessA?.driver_name ?? 'Lap A' : sessB?.driver_name ?? 'Lap B'} />
                  <Line type="monotone" dataKey="a" stroke={COLORS.a} dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="b" stroke={COLORS.b} dot={false} strokeWidth={2} strokeDasharray="5 3" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Time delta */}
          <div className="bg-surface border border-border rounded-lg p-4 space-y-2">
            <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">
              Time Delta vs Distance <span className="text-gray-500 font-normal text-xs">(positive = B losing time)</span>
            </h2>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={deltaData} margin={{ top: 5, right: 10, bottom: 20, left: 10 }}>
                  <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                  <XAxis dataKey="d" stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }}
                    label={{ value: 'Distance (m)', position: 'insideBottom', offset: -10, fill: '#6a8090', fontSize: 10 }} />
                  <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} tickFormatter={v => `${v}s`} />
                  <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
                  <Tooltip contentStyle={CHART_STYLE.tooltip}
                    formatter={(v: any) => [`${(+v).toFixed(4)}s`, 'Δ time']}
                    labelFormatter={(d: any) => `${d}m`} />
                  <Area type="monotone" dataKey="dt"
                    stroke="#888"
                    fill="url(#deltaGrad)"
                    dot={false} strokeWidth={1.5} />
                  <defs>
                    <linearGradient id="deltaGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#FF4444" stopOpacity={0.4} />
                      <stop offset="50%" stopColor="#888" stopOpacity={0.1} />
                      <stop offset="100%" stopColor="#00FF88" stopOpacity={0.4} />
                    </linearGradient>
                  </defs>
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Corner apex comparison */}
          {cornerOverlay.length > 0 && (
            <div className="bg-surface border border-border rounded-lg p-4 space-y-2">
              <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Corner Apex Speeds</h2>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={cornerOverlay} margin={{ top: 5, right: 10, bottom: 5, left: -10 }}>
                    <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="name" stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} />
                    <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} unit=" km/h" />
                    <Tooltip contentStyle={CHART_STYLE.tooltip}
                      formatter={(v: any, name: string) => [`${(+v).toFixed(1)} km/h`, name === 'a_apex' ? sessA?.driver_name ?? 'A' : sessB?.driver_name ?? 'B']} />
                    <Legend wrapperStyle={{ fontSize: 11 }}
                      formatter={(v: string) => v === 'a_apex' ? sessA?.driver_name ?? 'Lap A' : sessB?.driver_name ?? 'Lap B'} />
                    <Bar dataKey="a_apex" name="a_apex" fill={COLORS.a} radius={[2,2,0,0]} />
                    <Bar dataKey="b_apex" name="b_apex" fill={COLORS.b} radius={[2,2,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
