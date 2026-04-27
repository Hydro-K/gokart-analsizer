import { useEffect, useRef, useState, useCallback } from 'react'
import { api, Session, Lap, Telemetry, CornerOut, CompareResult } from '../api'
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { fmtLap, fmtMphKmh } from '../utils/units'

// Up to 6 lap colors
const LAP_COLORS = ['#00FF88', '#FF6B35', '#4A9EFF', '#FFD700', '#FF69B4', '#A78BFA']

interface LapEntry {
  session: Session
  lap: Lap
  tele: Telemetry | null
  corners: CornerOut[]
  color: string
}

const CHART_STYLE = {
  grid: '#1c2e3e', axis: '#4a6070',
  tooltip: { background: '#0a1520', border: '1px solid #1c2e3e', borderRadius: 6, fontSize: 12 },
}

function speedToColor(speedMs: number, maxMs: number): string {
  const ratio = Math.min(speedMs / Math.max(maxMs, 0.1), 1)
  const r = Math.round(ratio < 0.5 ? 510 * ratio : 255)
  const g = Math.round(ratio > 0.5 ? 510 * (1 - ratio) : 255)
  return `rgb(${r},${g},50)`
}

export default function Compare() {
  const [sessions, setSessions]   = useState<Session[]>([])
  const [sessionSel, setSessionSel] = useState('')
  const [lapSel, setLapSel]       = useState('')
  const [sessionLaps, setSessionLaps] = useState<Lap[]>([])
  const [entries, setEntries]     = useState<LapEntry[]>([])
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState('')

  // GPS overlay mode
  const [mapMode, setMapMode]     = useState(false)
  const [playing, setPlaying]     = useState(false)
  const [playSpeed, setPlaySpeed] = useState(1)
  const [curTime, setCurTime]     = useState(0)
  const [maxTime, setMaxTime]     = useState(0)
  const mapRef    = useRef<any>(null)
  const markersRef = useRef<any[]>([])
  const rafRef    = useRef<number>(0)
  const startWallRef = useRef<number>(0)
  const startTimeRef = useRef<number>(0)

  useEffect(() => {
    api.get<Session[]>('/sessions').then(setSessions).catch(() => {})
  }, [])

  useEffect(() => {
    if (!sessionSel) { setSessionLaps([]); setLapSel(''); return }
    api.get<Lap[]>(`/sessions/${sessionSel}/laps`).then(laps => {
      const valid = laps.filter(l => l.is_valid)
      setSessionLaps(valid)
      const best = valid.reduce<Lap | null>((b, l) => (!b || l.lap_time_s < b.lap_time_s) ? l : b, null)
      if (best) setLapSel(String(best.id))
    }).catch(() => {})
  }, [sessionSel])

  const addLap = async () => {
    if (!lapSel || !sessionSel) return
    if (entries.length >= 6) { setError('Max 6 laps'); return }
    if (entries.find(e => e.lap.id === +lapSel)) { setError('Lap already added'); return }
    setLoading(true); setError('')
    try {
      const sess = sessions.find(s => s.id === +sessionSel)!
      const lap  = sessionLaps.find(l => l.id === +lapSel)!
      const [tele, corners] = await Promise.all([
        api.get<Telemetry>(`/laps/${lapSel}/telemetry?points=800`),
        api.get<CornerOut[]>(`/laps/${lapSel}/corners`).catch(() => [] as CornerOut[]),
      ])
      const color = LAP_COLORS[entries.length % LAP_COLORS.length]
      setEntries(prev => [...prev, { session: sess, lap, tele, corners, color }])
    } catch (e: any) { setError(e.message) }
    finally { setLoading(false) }
  }

  const removeLap = (lapId: number) => setEntries(prev => prev.filter(e => e.lap.id !== lapId))

  // Build speed overlay data
  const overlayData = (() => {
    if (entries.length < 2) return []
    const ref = entries[0]
    if (!ref.tele) return []
    return ref.tele.time.map((t, ai) => {
      const pt: any = { t: +t.toFixed(2), [ref.lap.id]: +(ref.tele!.speed_ms[ai] * 0.621371 * 3.6).toFixed(1) }
      for (let ei = 1; ei < entries.length; ei++) {
        const other = entries[ei]
        if (!other.tele) continue
        let bi = 0
        while (bi < other.tele.time.length - 2 && other.tele.time[bi + 1] < t) bi++
        const t0 = other.tele.time[bi], t1 = other.tele.time[bi + 1] ?? t0
        const frac = t1 > t0 ? (t - t0) / (t1 - t0) : 0
        const spd = other.tele.speed_ms[bi] + frac * ((other.tele.speed_ms[bi + 1] ?? other.tele.speed_ms[bi]) - other.tele.speed_ms[bi])
        pt[other.lap.id] = +(spd * 0.621371 * 3.6).toFixed(1)
      }
      return pt
    })
  })()

  // Corner comparison
  const cornerOverlay = (() => {
    const maxCorners = Math.max(...entries.map(e => e.corners.length), 0)
    if (maxCorners === 0) return []
    return Array.from({ length: maxCorners }, (_, i) => {
      const pt: any = { name: `C${i + 1}` }
      entries.forEach(e => { pt[e.lap.id] = e.corners[i]?.apex_speed_kmh ? fmtMphKmh(e.corners[i].apex_speed_kmh) : null })
      return pt
    })
  })()

  // GPS map
  const hasGps = entries.some(e => e.tele?.has_gps)

  const initMap = useCallback(async () => {
    if (!hasGps || !mapMode) return
    const L = await import('leaflet') as any
    if (mapRef.current) { mapRef.current.remove(); mapRef.current = null }
    markersRef.current = []

    const gpsEntries = entries.filter(e => e.tele?.has_gps)
    if (gpsEntries.length === 0) return

    const firstTele = gpsEntries[0].tele!
    const lat0 = firstTele.lat!.reduce((s, v) => s + v, 0) / firstTele.lat!.length
    const lon0 = firstTele.lon!.reduce((s, v) => s + v, 0) / firstTele.lon!.length

    const map = L.map('compare-map', { zoomControl: true })
    mapRef.current = map
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { attribution: 'Tiles &copy; Esri', maxZoom: 19 }).addTo(map)
    map.setView([lat0, lon0], 17)

    // Draw each lap's GPS trace in its color
    for (const e of gpsEntries) {
      const lats = e.tele!.lat!; const lons = e.tele!.lon!
      const coords: [number, number][] = lats.map((lt, i) => [lt, lons[i]])
      L.polyline(coords, { color: e.color, weight: 3, opacity: 0.8 }).addTo(map)

      // Start dot
      L.circleMarker([lats[0], lons[0]], { radius: 5, color: e.color, fillColor: e.color, fillOpacity: 1 })
        .bindTooltip(`Lap ${e.lap.lap_number} — ${fmtLap(e.lap.lap_time_s)}`, { permanent: false })
        .addTo(map)
    }

    // Build animated markers
    const mt = Math.max(...gpsEntries.map(e => {
      const t = e.tele!.time
      return t[t.length - 1] - t[0]
    }))
    setMaxTime(mt)
    setCurTime(0)

    markersRef.current = gpsEntries.map(e => {
      const icon = L.divIcon({
        className: '',
        html: `<div style="width:14px;height:14px;border-radius:50%;background:${e.color};border:2px solid #fff;box-shadow:0 0 6px ${e.color};"></div>`,
        iconSize: [14, 14], iconAnchor: [7, 7],
      })
      return { marker: L.marker([e.tele!.lat![0], e.tele!.lon![0]], { icon }).addTo(map), entry: e }
    })
  }, [entries, hasGps, mapMode])

  useEffect(() => {
    if (mapMode) initMap()
    return () => {
      cancelAnimationFrame(rafRef.current)
      if (mapRef.current) { mapRef.current.remove(); mapRef.current = null }
    }
  }, [mapMode, initMap])

  const animate = useCallback(() => {
    const elapsed = (performance.now() - startWallRef.current) / 1000 * playSpeed
    const t = startTimeRef.current + elapsed
    if (t >= maxTime) { setCurTime(maxTime); setPlaying(false); return }
    setCurTime(t)

    for (const { marker, entry } of markersRef.current) {
      const tel = entry.tele!
      const t0 = tel.time[0]
      const target = t0 + t
      let idx = 0
      while (idx < tel.time.length - 2 && tel.time[idx + 1] <= target) idx++
      const p0 = { lat: tel.lat![idx], lon: tel.lon![idx] }
      const p1 = idx + 1 < tel.lat!.length ? { lat: tel.lat![idx + 1], lon: tel.lon![idx + 1] } : p0
      const dur = (tel.time[idx + 1] ?? tel.time[idx]) - tel.time[idx]
      const frac = dur > 0 ? Math.min((target - tel.time[idx]) / dur, 1) : 0
      marker.setLatLng([p0.lat + (p1.lat - p0.lat) * frac, p0.lon + (p1.lon - p0.lon) * frac])
    }
    rafRef.current = requestAnimationFrame(animate)
  }, [maxTime, playSpeed])

  useEffect(() => {
    if (playing) {
      startWallRef.current = performance.now()
      startTimeRef.current = curTime
      rafRef.current = requestAnimationFrame(animate)
    } else { cancelAnimationFrame(rafRef.current) }
    return () => cancelAnimationFrame(rafRef.current)
  }, [playing, animate])

  const togglePlay = () => {
    if (!playing && curTime >= maxTime) { setCurTime(0); startTimeRef.current = 0 }
    setPlaying(p => !p)
  }

  const handleScrub = (e: React.ChangeEvent<HTMLInputElement>) => {
    const t = parseFloat(e.target.value)
    setCurTime(t); startTimeRef.current = t; startWallRef.current = performance.now()
    // Update markers to scrubbed position
    for (const { marker, entry } of markersRef.current) {
      const tel = entry.tele!; const t0 = tel.time[0]; const target = t0 + t
      let idx = 0
      while (idx < tel.time.length - 2 && tel.time[idx + 1] <= target) idx++
      if (tel.lat) marker.setLatLng([tel.lat[idx], tel.lon![idx]])
    }
  }

  return (
    <div className="space-y-5 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Lap Comparison</h1>
        <p className="text-xs text-gray-500 mt-0.5">Overlay up to 6 laps — speed traces, corners, and live GPS replay</p>
      </div>

      {/* Add lap controls */}
      <div className="bg-surface border border-border rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Add Lap</h2>
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[160px]">
            <label className="block text-xs text-gray-400 mb-1">Session</label>
            <select value={sessionSel} onChange={e => setSessionSel(e.target.value)}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-accent">
              <option value="">Select session…</option>
              {sessions.map(s => <option key={s.id} value={s.id}>{s.date} · {s.driver_name} · {s.session_type}</option>)}
            </select>
          </div>
          <div className="flex-1 min-w-[140px]">
            <label className="block text-xs text-gray-400 mb-1">Lap</label>
            <select value={lapSel} onChange={e => setLapSel(e.target.value)} disabled={!sessionLaps.length}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-accent disabled:opacity-50">
              <option value="">Select lap…</option>
              {sessionLaps.map(l => <option key={l.id} value={l.id}>Lap {l.lap_number} — {fmtLap(l.lap_time_s)}</option>)}
            </select>
          </div>
          <button onClick={addLap} disabled={!lapSel || loading || entries.length >= 6}
            className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 disabled:opacity-40 text-sm shrink-0">
            {loading ? '…' : '+ Add Lap'}
          </button>
        </div>
        {error && <div className="text-red text-sm">{error}</div>}
      </div>

      {/* Active laps */}
      {entries.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {entries.map(e => (
            <div key={e.lap.id} className="flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm"
              style={{ borderColor: e.color, background: e.color + '18' }}>
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: e.color }} />
              <span style={{ color: e.color }} className="font-mono">
                Lap {e.lap.lap_number} — {fmtLap(e.lap.lap_time_s)}
              </span>
              <span className="text-gray-400 text-xs">{e.session.driver_name}</span>
              <button onClick={() => removeLap(e.lap.id)} className="text-gray-500 hover:text-red ml-1 text-xs">✕</button>
            </div>
          ))}
        </div>
      )}

      {entries.length >= 2 && (
        <div className="space-y-5">
          {/* Speed overlay chart */}
          <div className="bg-surface border border-border rounded-lg p-4 space-y-2">
            <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Speed Overlay (mph)</h2>
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={overlayData} margin={{ top: 5, right: 10, bottom: 20, left: 10 }}>
                  <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                  <XAxis dataKey="t" stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }}
                    label={{ value: 'Time (s)', position: 'insideBottom', offset: -10, fill: '#6a8090', fontSize: 10 }} />
                  <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} unit=" mph" />
                  <Tooltip contentStyle={CHART_STYLE.tooltip}
                    formatter={(v: any, name: any) => {
                      const e = entries.find(e => String(e.lap.id) === String(name))
                      return [`${v} mph`, e ? `Lap ${e.lap.lap_number} — ${e.session.driver_name}` : name]
                    }} />
                  <Legend wrapperStyle={{ fontSize: 11 }}
                    formatter={(name: any) => {
                      const e = entries.find(e => String(e.lap.id) === String(name))
                      return e ? `Lap ${e.lap.lap_number} (${e.session.driver_name})` : name
                    }} />
                  {entries.map(e => (
                    <Line key={e.lap.id} type="monotone" dataKey={String(e.lap.id)}
                      stroke={e.color} dot={false} strokeWidth={2} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Corner apex comparison */}
          {cornerOverlay.length > 0 && (
            <div className="bg-surface border border-border rounded-lg p-4 space-y-2">
              <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Corner Apex Speed (mph)</h2>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={cornerOverlay} margin={{ top: 5, right: 10, bottom: 5, left: -10 }}>
                    <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="name" stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} />
                    <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} unit=" mph" />
                    <Tooltip contentStyle={CHART_STYLE.tooltip}
                      formatter={(v: any, name: any) => {
                        const e = entries.find(e => String(e.lap.id) === String(name))
                        return [`${(+v).toFixed(1)} mph`, e ? `Lap ${e.lap.lap_number}` : name]
                      }} />
                    <Legend wrapperStyle={{ fontSize: 11 }}
                      formatter={(name: any) => {
                        const e = entries.find(e => String(e.lap.id) === String(name))
                        return e ? `Lap ${e.lap.lap_number} (${e.session.driver_name})` : name
                      }} />
                    {entries.map(e => (
                      <Bar key={e.lap.id} dataKey={String(e.lap.id)} name={String(e.lap.id)}
                        fill={e.color} radius={[2, 2, 0, 0]} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* GPS Map Overlay + Replay */}
          {hasGps && (
            <div className="bg-surface border border-border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">GPS Map Overlay</h2>
                <button onClick={() => setMapMode(m => !m)}
                  className={`px-3 py-1 text-xs rounded border transition-colors ${mapMode ? 'border-accent text-accent' : 'border-border text-gray-400 hover:border-accent hover:text-accent'}`}>
                  {mapMode ? '✕ Close Map' : '🗺 Show GPS Map & Replay'}
                </button>
              </div>

              {mapMode && (
                <>
                  <div id="compare-map" className="w-full rounded overflow-hidden" style={{ height: 420 }} />

                  {/* Replay controls */}
                  {maxTime > 0 && (
                    <div className="space-y-2">
                      <input type="range" min={0} max={maxTime} step={0.1} value={curTime}
                        onChange={handleScrub} className="w-full accent-accent" />
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-xs text-gray-400 font-mono">{fmtLap(curTime)}</span>
                        <div className="flex items-center gap-2">
                          <div className="flex gap-1">
                            {[0.5, 1, 2, 5].map(s => (
                              <button key={s} onClick={() => setPlaySpeed(s)}
                                className={`px-2 py-0.5 text-xs rounded border ${playSpeed === s ? 'border-accent text-accent' : 'border-border text-gray-400'}`}>
                                {s}×
                              </button>
                            ))}
                          </div>
                          <button onClick={togglePlay}
                            className="px-5 py-1 bg-accent text-bg font-bold rounded text-sm hover:opacity-90">
                            {playing ? '⏸ Pause' : curTime >= maxTime ? '↺ Restart' : '▶ Play All'}
                          </button>
                        </div>
                        <span className="text-xs text-gray-400 font-mono">{fmtLap(maxTime)}</span>
                      </div>
                      {/* Live positions legend */}
                      <div className="flex flex-wrap gap-3 pt-1">
                        {entries.filter(e => e.tele?.has_gps).map(e => {
                          const tel = e.tele!; const t0 = tel.time[0]; const target = t0 + curTime
                          let idx = 0
                          while (idx < tel.time.length - 2 && tel.time[idx + 1] <= target) idx++
                          const spd = tel.speed_ms[idx] ?? 0
                          return (
                            <div key={e.lap.id} className="flex items-center gap-1.5 text-xs">
                              <span className="w-2 h-2 rounded-full" style={{ background: e.color }} />
                              <span style={{ color: e.color }}>Lap {e.lap.lap_number}</span>
                              <span className="text-gray-400">{(spd * 2.23694).toFixed(1)} mph</span>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Lap time summary */}
          <div className="bg-surface border border-border rounded-lg p-4 space-y-2">
            <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Lap Time Summary</h2>
            <div className="space-y-2">
              {[...entries].sort((a, b) => a.lap.lap_time_s - b.lap.lap_time_s).map((e, i) => {
                const best = entries.reduce((b, x) => x.lap.lap_time_s < b ? x.lap.lap_time_s : b, Infinity)
                const delta = e.lap.lap_time_s - best
                return (
                  <div key={e.lap.id} className="flex items-center gap-3 p-2 rounded"
                    style={{ background: e.color + '12', borderLeft: `3px solid ${e.color}` }}>
                    <span className="text-gray-400 text-xs w-4">{i + 1}</span>
                    <span className="font-mono font-bold" style={{ color: e.color }}>{fmtLap(e.lap.lap_time_s)}</span>
                    {delta > 0 && <span className="text-red text-xs font-mono">+{delta.toFixed(3)}s</span>}
                    {delta === 0 && <span className="text-accent text-xs">BEST</span>}
                    <span className="text-gray-400 text-xs flex-1 text-right">
                      Lap {e.lap.lap_number} · {e.session.driver_name} · {e.session.date}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {entries.length === 0 && (
        <div className="text-center py-12 text-gray-500 text-sm">
          Add two or more laps above to begin comparison
        </div>
      )}
      {entries.length === 1 && (
        <div className="text-center py-8 text-gray-500 text-sm">
          Add at least one more lap to compare
        </div>
      )}
    </div>
  )
}
