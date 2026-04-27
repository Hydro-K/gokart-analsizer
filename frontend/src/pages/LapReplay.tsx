import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api, Lap } from '../api'
import { fmtMph, fmtLap } from '../utils/units'

interface TelemetryPoint {
  t: number
  lat: number
  lon: number
  speed: number   // m/s
  phase: string
}

const PHASE_COLOR: Record<string, string> = {
  accelerating: '#00FF88',
  braking:      '#FF3B3B',
  cornering:    '#FFD700',
  straight:     '#4A9EFF',
}

function speedToColor(speedMs: number, maxMs: number): string {
  const ratio = Math.min(speedMs / Math.max(maxMs, 0.1), 1)
  const r = Math.round(ratio < 0.5 ? 510 * ratio : 255)
  const g = Math.round(ratio > 0.5 ? 510 * (1 - ratio) : 255)
  return `rgb(${r},${g},50)`
}

function fmtRecorded(created_at?: string) {
  if (!created_at) return ''
  try {
    return new Date(created_at).toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return '' }
}

export default function LapReplay() {
  const { lapId: lapIdParam } = useParams<{ lapId: string }>()
  const nav = useNavigate()

  const mapRef    = useRef<any>(null)
  const markerRef = useRef<any>(null)
  const polyRef   = useRef<any[]>([])
  const rafRef    = useRef<number>(0)
  const startWallRef = useRef<number>(0)
  const startIdxRef  = useRef<number>(0)

  const [activeLapId, setActiveLapId] = useState<number>(parseInt(lapIdParam ?? '0'))
  const [sessionLaps, setSessionLaps] = useState<Lap[]>([])
  const [points, setPoints]   = useState<TelemetryPoint[]>([])
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed]     = useState(1)
  const [curIdx, setCurIdx]   = useState(0)
  const [lapTime, setLapTime] = useState(0)
  const [loaded, setLoaded]   = useState(false)
  const [error, setError]     = useState('')
  const [lapInfo, setLapInfo] = useState<Lap | null>(null)
  const [mapStyle, setMapStyle] = useState<'satellite' | 'street'>('satellite')

  // Load lap + fetch sibling laps from same session
  useEffect(() => {
    if (!activeLapId) return
    setLoaded(false); setError(''); setPlaying(false)
    cancelAnimationFrame(rafRef.current)

    Promise.all([
      api.get<any>(`/laps/${activeLapId}/telemetry`),
      api.get<any>(`/laps/${activeLapId}`),
    ]).then(([tel, lap]) => {
      const timeArr  = tel.time  as number[]
      const speedArr = tel.speed_ms as number[]
      const latArr   = tel.lat   as number[] | null
      const lonArr   = tel.lon   as number[] | null
      const phaseArr = tel.phase as string[] | null

      if (!latArr || !lonArr || latArr.length < 10) {
        setError('No GPS data for this lap — replay requires GPS coordinates.')
        return
      }

      const pts: TelemetryPoint[] = timeArr.map((t, i) => ({
        t, lat: latArr[i], lon: lonArr[i],
        speed: speedArr[i],
        phase: phaseArr?.[i] ?? 'straight',
      }))
      setPoints(pts)
      setLapInfo(lap)
      setCurIdx(0)
      setLapTime(0)

      // Load sibling laps if not already loaded
      if (sessionLaps.length === 0) {
        api.get<Lap[]>(`/sessions/${lap.session_id}/laps`)
          .then(laps => setSessionLaps(laps.filter(l => l.is_valid)))
          .catch(() => {})
      }

      setLoaded(true)
    }).catch(e => setError(e.message))
  }, [activeLapId])

  // Initialize / reinitialize Leaflet map when data loads
  useEffect(() => {
    if (!loaded || points.length === 0) return

    // Clean up old map
    if (mapRef.current) {
      mapRef.current.remove()
      mapRef.current = null
      markerRef.current = null
    }

    import('leaflet').then((L: any) => {
      const avgLat = points.reduce((s, p) => s + p.lat, 0) / points.length
      const avgLon = points.reduce((s, p) => s + p.lon, 0) / points.length

      const map = L.map('replay-map', { zoomControl: true, attributionControl: true })
      mapRef.current = map

      const tileLayers = {
        satellite: L.tileLayer(
          'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
          { attribution: 'Tiles &copy; Esri', maxZoom: 19 }
        ),
        street: L.tileLayer(
          'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
          { attribution: '&copy; OpenStreetMap contributors', maxZoom: 19 }
        ),
      }
      tileLayers[mapStyle].addTo(map)
      ;(map as any)._tileLayers = tileLayers

      map.setView([avgLat, avgLon], 17)

      // Draw speed-colored path
      const maxMs = Math.max(...points.map(p => p.speed))
      const segs: any[] = []
      for (let i = 0; i < points.length - 1; i++) {
        const col = speedToColor(points[i].speed, maxMs)
        segs.push(L.polyline(
          [[points[i].lat, points[i].lon], [points[i+1].lat, points[i+1].lon]],
          { color: col, weight: 4, opacity: 0.85 }
        ).addTo(map))
      }
      polyRef.current = segs

      // Kart marker
      const kartIcon = L.divIcon({
        className: '',
        html: `<div style="width:16px;height:16px;border-radius:50%;background:#00FF88;border:3px solid #fff;box-shadow:0 0 8px #00FF88;"></div>`,
        iconSize: [16, 16], iconAnchor: [8, 8],
      })
      markerRef.current = L.marker([points[0].lat, points[0].lon], { icon: kartIcon }).addTo(map)
    })

    return () => {
      cancelAnimationFrame(rafRef.current)
      if (mapRef.current) { mapRef.current.remove(); mapRef.current = null }
    }
  }, [loaded, points])

  // Swap tile layers
  useEffect(() => {
    if (!mapRef.current) return
    const tl = (mapRef.current as any)._tileLayers
    if (!tl) return
    Object.values(tl).forEach((l: any) => mapRef.current.removeLayer(l))
    ;(tl as any)[mapStyle].addTo(mapRef.current)
  }, [mapStyle])

  // Animation loop
  const animate = useCallback(() => {
    if (!mapRef.current || !markerRef.current || points.length === 0) return
    const wallElapsed = (performance.now() - startWallRef.current) / 1000 * speed
    const startT = points[startIdxRef.current].t
    const targetT = startT + wallElapsed
    let idx = startIdxRef.current
    while (idx < points.length - 1 && points[idx + 1].t <= targetT) idx++
    if (idx >= points.length - 1) {
      setCurIdx(points.length - 1)
      setPlaying(false)
      return
    }
    const p0 = points[idx]; const p1 = points[idx + 1]
    const frac = (targetT - p0.t) / Math.max(p1.t - p0.t, 0.001)
    markerRef.current.setLatLng([p0.lat + (p1.lat - p0.lat) * frac, p0.lon + (p1.lon - p0.lon) * frac])
    const col = PHASE_COLOR[p0.phase] ?? '#00FF88'
    const el = markerRef.current.getElement()
    if (el) { const dot = el.querySelector('div'); if (dot) { dot.style.background = col; dot.style.boxShadow = `0 0 10px ${col}` } }
    setCurIdx(idx)
    setLapTime(p0.t - points[0].t)
    rafRef.current = requestAnimationFrame(animate)
  }, [points, speed])

  useEffect(() => {
    if (playing) {
      startWallRef.current = performance.now()
      startIdxRef.current = curIdx
      rafRef.current = requestAnimationFrame(animate)
    } else {
      cancelAnimationFrame(rafRef.current)
    }
    return () => cancelAnimationFrame(rafRef.current)
  }, [playing, animate])

  const togglePlay = () => {
    if (!playing && curIdx >= points.length - 1) {
      setCurIdx(0); startIdxRef.current = 0
      if (markerRef.current && points.length > 0)
        markerRef.current.setLatLng([points[0].lat, points[0].lon])
    }
    setPlaying(p => !p)
  }

  const handleScrub = (e: React.ChangeEvent<HTMLInputElement>) => {
    const idx = parseInt(e.target.value)
    setCurIdx(idx); startIdxRef.current = idx; startWallRef.current = performance.now()
    if (markerRef.current && points[idx]) markerRef.current.setLatLng([points[idx].lat, points[idx].lon])
    setLapTime(points[idx]?.t - (points[0]?.t ?? 0))
  }

  const switchLap = (id: number) => {
    setPlaying(false)
    cancelAnimationFrame(rafRef.current)
    setActiveLapId(id)
  }

  const curPoint = points[curIdx]
  const maxMs = points.length ? Math.max(...points.map(p => p.speed)) : 0

  return (
    <div className="flex flex-col h-screen bg-bg">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-surface border-b border-border shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <button onClick={() => nav(-1)} className="text-gray-400 hover:text-white text-sm shrink-0">← Back</button>
          <h1 className="text-white font-bold truncate">
            Lap Replay{lapInfo ? ` — Lap ${lapInfo.lap_number}` : ''}
            {lapInfo && <span className="text-gray-400 font-normal ml-2">{fmtLap(lapInfo.lap_time_s)}</span>}
          </h1>
          {lapInfo?.created_at && (
            <span className="text-xs text-gray-500 shrink-0">{fmtRecorded(lapInfo.created_at)}</span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {/* Lap switcher */}
          {sessionLaps.length > 1 && (
            <select
              value={activeLapId}
              onChange={e => switchLap(parseInt(e.target.value))}
              className="bg-bg border border-border rounded px-2 py-1 text-white text-xs focus:outline-none focus:border-accent"
            >
              {sessionLaps.map(l => (
                <option key={l.id} value={l.id}>
                  Lap {l.lap_number} — {fmtLap(l.lap_time_s)}
                </option>
              ))}
            </select>
          )}
          <button
            onClick={() => setMapStyle(s => s === 'satellite' ? 'street' : 'satellite')}
            className="text-xs px-2 py-1 border border-border rounded hover:border-accent hover:text-accent transition-colors"
          >
            {mapStyle === 'satellite' ? '🗺 Street' : '🛰 Satellite'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 text-red text-sm">
          {error}
          <Link to={`/laps/${activeLapId}`} className="ml-2 text-accent underline">← Back to analysis</Link>
        </div>
      )}

      {!loaded && !error && (
        <div className="flex-1 flex items-center justify-center text-gray-400">Loading GPS data…</div>
      )}

      {loaded && (
        <div className="flex flex-1 overflow-hidden">
          {/* Map */}
          <div className="flex-1 relative">
            <div id="replay-map" className="w-full h-full" />

            {/* Speed overlay */}
            <div className="absolute top-3 right-3 bg-bg bg-opacity-90 border border-border rounded-lg p-3 min-w-[110px]">
              <div className="text-xs text-gray-400 mb-1">SPEED</div>
              <div className="text-3xl font-bold text-accent font-mono">
                {(curPoint?.speed ?? 0) > 0 ? fmtMph(curPoint.speed).split(' ')[0] : '0.0'}
              </div>
              <div className="text-xs text-gray-400">mph</div>
              <div className="mt-2 h-1.5 bg-border rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all"
                  style={{
                    width: `${maxMs > 0 ? ((curPoint?.speed ?? 0) / maxMs * 100).toFixed(0) : 0}%`,
                    background: speedToColor(curPoint?.speed ?? 0, maxMs),
                  }}
                />
              </div>
            </div>

            {/* Phase badge */}
            {curPoint && (
              <div className="absolute top-3 left-3 px-3 py-1 rounded-full text-xs font-bold border"
                style={{
                  background: (PHASE_COLOR[curPoint.phase] ?? '#4A9EFF') + '22',
                  borderColor: PHASE_COLOR[curPoint.phase] ?? '#4A9EFF',
                  color: PHASE_COLOR[curPoint.phase] ?? '#4A9EFF',
                }}>
                {curPoint.phase.toUpperCase()}
              </div>
            )}

            {/* Legend */}
            <div className="absolute bottom-20 left-3 bg-bg bg-opacity-90 border border-border rounded-lg p-2 text-xs">
              <div className="text-gray-400 mb-1 font-bold">SPEED TRACE</div>
              <div className="flex items-center gap-2">
                <div className="w-8 h-1.5 rounded" style={{ background: 'linear-gradient(to right, rgb(255,50,50), rgb(255,255,50), rgb(50,255,50))' }} />
                <span className="text-gray-400">slow → fast</span>
              </div>
            </div>
          </div>

          {/* Side panel */}
          <div className="w-52 bg-surface border-l border-border flex flex-col p-3 gap-3 shrink-0 overflow-y-auto">
            <div className="bg-bg rounded p-2 text-center">
              <div className="text-xs text-gray-400">LAP TIME</div>
              <div className="text-2xl font-mono font-bold text-white">{fmtLap(lapTime)}</div>
              {lapInfo && <div className="text-xs text-gray-500 mt-0.5">/ {fmtLap(lapInfo.lap_time_s)}</div>}
            </div>

            <div className="space-y-2">
              {[
                { label: 'SPEED', val: fmtMph(curPoint?.speed ?? 0) },
                { label: 'MAX', val: fmtMph(maxMs) },
                { label: 'PHASE', val: curPoint?.phase ?? '—' },
                { label: 'PROGRESS', val: `${points.length > 1 ? (curIdx / (points.length - 1) * 100).toFixed(0) : 0}%` },
              ].map(({ label, val }) => (
                <div key={label} className="flex justify-between text-xs">
                  <span className="text-gray-400">{label}</span>
                  <span className="text-white font-mono">{val}</span>
                </div>
              ))}
            </div>

            {/* Phase legend */}
            <div className="border-t border-border pt-2">
              <div className="text-xs text-gray-400 mb-1.5">PHASES</div>
              {Object.entries(PHASE_COLOR).map(([phase, col]) => (
                <div key={phase} className="flex items-center gap-1.5 mb-1">
                  <div className="w-2 h-2 rounded-full shrink-0" style={{ background: col }} />
                  <span className="text-xs text-gray-300 capitalize">{phase}</span>
                </div>
              ))}
            </div>

            {/* Playback speed */}
            <div className="border-t border-border pt-2">
              <div className="text-xs text-gray-400 mb-1">PLAYBACK SPEED</div>
              <div className="flex gap-1">
                {[0.5, 1, 2, 5].map(s => (
                  <button key={s} onClick={() => setSpeed(s)}
                    className={`flex-1 py-1 text-xs rounded border transition-colors ${speed === s ? 'border-accent text-accent' : 'border-border text-gray-400 hover:border-gray-400'}`}>
                    {s}×
                  </button>
                ))}
              </div>
            </div>

            {/* Lap list */}
            {sessionLaps.length > 1 && (
              <div className="border-t border-border pt-2">
                <div className="text-xs text-gray-400 mb-2">SESSION LAPS</div>
                <div className="space-y-1">
                  {sessionLaps.map(l => (
                    <button
                      key={l.id}
                      onClick={() => switchLap(l.id)}
                      className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${l.id === activeLapId ? 'bg-accent bg-opacity-20 text-accent border border-accent border-opacity-50' : 'text-gray-400 hover:text-white hover:bg-bg'}`}
                    >
                      <div className="font-mono">Lap {l.lap_number} — {fmtLap(l.lap_time_s)}</div>
                      {l.created_at && (
                        <div className="text-gray-600 text-[10px]">{fmtRecorded(l.created_at)}</div>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Controls bar */}
      {loaded && (
        <div className="bg-surface border-t border-border px-4 py-3 flex flex-col gap-2 shrink-0">
          <input
            type="range" min={0} max={points.length - 1} value={curIdx}
            onChange={handleScrub} className="w-full accent-accent"
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400 font-mono">{fmtLap(lapTime)}</span>
            <button onClick={togglePlay}
              className="px-6 py-1.5 bg-accent text-bg font-bold rounded text-sm hover:opacity-90">
              {playing ? '⏸ Pause' : curIdx >= points.length - 1 ? '↺ Restart' : '▶ Play'}
            </button>
            <span className="text-xs text-gray-400 font-mono">
              {lapInfo ? fmtLap(lapInfo.lap_time_s) : ''}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
