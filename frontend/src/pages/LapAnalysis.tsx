import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { api, Telemetry, EnergyResult, SectorOut, CornerOut, FeatureVector, SmoothnessResult, Lap } from '../api'
import { MetricCard } from '../components/common/MetricCard'
import { mph as toMph, mphKmh } from '../utils/units'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Cell, Legend
} from 'recharts'

function fmt(s: number) {
  const m = Math.floor(s / 60)
  const sec = (s % 60).toFixed(3).padStart(6, '0')
  return `${m}:${sec}`
}

const PHASE_COLOR: Record<string, string> = {
  accelerating: '#00FF88',
  braking:      '#FF4444',
  cornering:    '#FFD700',
  straight:     '#4488FF',
}
const CHART_STYLE = {
  grid: '#1c2e3e',
  axis: '#4a6070',
  tooltip: { background: '#0a1520', border: '1px solid #1c2e3e', borderRadius: 6, fontSize: 12 },
  label: { color: '#6a8090', fontSize: 10 },
}

function PhaseLegend() {
  return (
    <div className="flex gap-4 text-xs">
      {Object.entries(PHASE_COLOR).map(([k, c]) => (
        <span key={k} className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm inline-block" style={{ background: c }} />
          <span className="text-gray-400 capitalize">{k}</span>
        </span>
      ))}
    </div>
  )
}

interface TabProps { active: boolean; onClick: () => void; children: React.ReactNode }
function Tab({ active, onClick, children }: TabProps) {
  return (
    <button onClick={onClick}
      className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
        active ? 'border-accent text-accent' : 'border-transparent text-gray-400 hover:text-white'
      }`}>
      {children}
    </button>
  )
}

export default function LapAnalysis() {
  const { id } = useParams<{ id: string }>()
  const nav = useNavigate()
  const [lap, setLap]           = useState<Lap | null>(null)
  const [tele, setTele]         = useState<Telemetry | null>(null)
  const [sectors, setSectors]   = useState<SectorOut[]>([])
  const [corners, setCorners]   = useState<CornerOut[]>([])
  const [energy, setEnergy]     = useState<EnergyResult | null>(null)
  const [smooth, setSmooth]     = useState<SmoothnessResult | null>(null)
  const [feats, setFeats]       = useState<FeatureVector | null>(null)
  const [activeTab, setActiveTab] = useState<'trace'|'gforce'|'corners'|'sectors'|'energy'|'features'>('trace')

  useEffect(() => {
    if (!id) return
    api.get<Lap>(`/laps/${id}`).then(setLap).catch(() => {})
    api.get<Telemetry>(`/laps/${id}/telemetry?points=800`).then(setTele).catch(() => {})
    api.get<SectorOut[]>(`/laps/${id}/sectors?n=5`).then(setSectors).catch(() => {})
    api.get<CornerOut[]>(`/laps/${id}/corners`).then(setCorners).catch(() => {})
    api.get<EnergyResult>(`/laps/${id}/energy`).then(setEnergy).catch(() => {})
    api.get<SmoothnessResult>(`/laps/${id}/smoothness`).then(setSmooth).catch(() => {})
    api.get<FeatureVector>(`/laps/${id}/features`).then(setFeats).catch(() => {})
  }, [id])

  // Build speed trace data with phase color (display in mph)
  const traceData = tele
    ? tele.time.map((t, i) => ({
        t: +t.toFixed(2),
        v: +toMph(tele.speed_ms[i]).toFixed(1),
        phase: tele.phase?.[i] ?? 'straight',
      }))
    : []

  // Phase breakdown percentages
  const phaseCounts = traceData.reduce<Record<string, number>>((acc, d) => {
    acc[d.phase] = (acc[d.phase] ?? 0) + 1
    return acc
  }, {})
  const total = traceData.length || 1
  const phaseBreakdown = Object.entries(phaseCounts).map(([name, count]) => ({
    name, pct: +((count / total) * 100).toFixed(1), fill: PHASE_COLOR[name] ?? '#888'
  }))

  // Sector bar data (convert km/h → mph for display)
  const sectorData = sectors.map(s => ({
    name: `S${s.sector_num}`,
    time: +s.time_s.toFixed(3),
    avg: +mphKmh(s.avg_speed_kmh).toFixed(1),
    min: +mphKmh(s.min_speed_kmh).toFixed(1),
    max: +mphKmh(s.max_speed_kmh).toFixed(1),
  }))

  // Corner data (convert km/h → mph)
  const cornerData = corners.map(c => ({
    name: `C${c.corner_index}`,
    entry: +mphKmh(c.entry_speed_kmh).toFixed(1),
    apex:  +mphKmh(c.apex_speed_kmh).toFixed(1),
    exit:  +mphKmh(c.exit_speed_kmh).toFixed(1),
  }))

  const peakSpeed = tele ? Math.max(...tele.speed_ms.map(s => toMph(s))) : 0

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white tracking-tight">Lap #{id}</h1>
            {lap && (
              <span className={`text-xl font-mono font-bold ${lap.is_valid ? 'text-accent' : 'text-gray-500'}`}>
                {fmt(lap.lap_time_s)}
              </span>
            )}
            {smooth && (
              <span className="text-xs border border-border rounded px-2 py-0.5 text-gray-400">
                Smoothness <span className="text-white font-bold">{smooth.smoothness_score.toFixed(1)}</span>/100
              </span>
            )}
          </div>
          {lap && (
            <div className="text-xs text-gray-500 mt-0.5">
              Lap {lap.lap_number} · {lap.is_valid ? 'Valid' : 'Invalid'}
            </div>
          )}
        </div>
        <div className="flex items-center gap-3">
          {tele?.has_gps && (
            <button onClick={() => nav(`/replay/${id}`)}
              className="px-3 py-1.5 bg-accent text-bg text-xs font-bold rounded hover:opacity-90 flex items-center gap-1.5">
              ▶ Live Replay
            </button>
          )}
          <Link to={`/sessions/${lap?.session_id}`}
            className="text-xs text-gray-400 hover:text-accent transition-colors">
            ← Session
          </Link>
        </div>
      </div>

      {/* Key metrics row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        {lap && <MetricCard label="Lap Time" value={fmt(lap.lap_time_s)} unit="" highlight />}
        <MetricCard label="Peak Speed" value={peakSpeed.toFixed(1)} unit="mph" />
        {energy && <MetricCard label="Energy" value={energy.total_kwh.toFixed(3)} unit="kWh" />}
        {energy && <MetricCard label="Peak Power" value={energy.peak_power_kw.toFixed(1)} unit="kW" />}
        {smooth && <MetricCard label="Smoothness" value={smooth.smoothness_score.toFixed(1)} unit="/100" highlight={smooth.smoothness_score > 75} />}
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-border overflow-x-auto">
        <Tab active={activeTab === 'trace'}    onClick={() => setActiveTab('trace')}>Speed Trace</Tab>
        {(tele?.lateral_acc || tele?.inline_acc) && (
          <Tab active={activeTab === 'gforce'} onClick={() => setActiveTab('gforce')}>G-Forces</Tab>
        )}
        <Tab active={activeTab === 'corners'}  onClick={() => setActiveTab('corners')}>Corners ({corners.length})</Tab>
        <Tab active={activeTab === 'sectors'}  onClick={() => setActiveTab('sectors')}>Sectors</Tab>
        <Tab active={activeTab === 'energy'}   onClick={() => setActiveTab('energy')}>Energy</Tab>
        <Tab active={activeTab === 'features'} onClick={() => setActiveTab('features')}>Features</Tab>
      </div>

      {/* Speed Trace tab */}
      {activeTab === 'trace' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Speed vs Time</h2>
            <PhaseLegend />
          </div>
          <div className="bg-surface border border-border rounded-lg p-4 h-64">
            {traceData.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-500 text-sm">No telemetry data</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={traceData} margin={{ top: 5, right: 10, bottom: 20, left: 10 }}>
                  <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                  <XAxis dataKey="t" stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }}
                    label={{ value: 'Time (s)', position: 'insideBottom', offset: -10, fill: '#6a8090', fontSize: 10 }} />
                  <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }}
                    label={{ value: 'mph', angle: -90, position: 'insideLeft', offset: 10, fill: '#6a8090', fontSize: 10 }} />
                  <Tooltip
                    contentStyle={CHART_STYLE.tooltip}
                    labelStyle={{ color: '#aaa' }}
                    itemStyle={{ color: '#00BFFF' }}
                    formatter={(val: any, _name: any, props: any) => {
                      const color = PHASE_COLOR[props.payload.phase] ?? '#fff'
                      return [<span style={{ color }}>{val} mph</span>, props.payload.phase]
                    }}
                    labelFormatter={(t: any) => `t = ${t}s`}
                  />
                  <Line type="monotone" dataKey="v" stroke="#00BFFF" dot={false} strokeWidth={2}
                    strokeDasharray={undefined} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Phase colour strip */}
          {traceData.length > 0 && (
            <div className="space-y-1">
              <div className="text-xs text-gray-500 uppercase tracking-wider">Phase Strip</div>
              <div className="flex h-4 rounded overflow-hidden">
                {traceData.map((d, i) => (
                  <div key={i} style={{ flex: 1, background: PHASE_COLOR[d.phase] ?? '#333', minWidth: 1 }} />
                ))}
              </div>
            </div>
          )}

          {/* Phase breakdown bar */}
          {phaseBreakdown.length > 0 && (
            <div className="bg-surface border border-border rounded-lg p-4">
              <h3 className="text-xs text-gray-400 uppercase tracking-wider mb-3">Throttle Zone Breakdown</h3>
              <div className="h-36">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={phaseBreakdown} margin={{ top: 5, right: 10, bottom: 5, left: -10 }}>
                    <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="name" stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} />
                    <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} tickFormatter={v => `${v}%`} />
                    <Tooltip
                      contentStyle={CHART_STYLE.tooltip}
                      formatter={(v: any) => [`${v}%`, 'Time']}
                    />
                    <Bar dataKey="pct" radius={[3, 3, 0, 0]}>
                      {phaseBreakdown.map((d, i) => <Cell key={i} fill={d.fill} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3 text-xs text-center font-mono">
                {phaseBreakdown.map(p => (
                  <div key={p.name} className="bg-bg rounded px-2 py-1.5">
                    <div className="text-lg font-bold" style={{ color: p.fill }}>{p.pct}%</div>
                    <div className="text-gray-400 capitalize">{p.name}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* G-Forces tab */}
      {activeTab === 'gforce' && tele && (
        <div className="space-y-4">
          {/* Peak G summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {tele.lateral_acc && (() => {
              const maxLat = Math.max(...tele.lateral_acc.map(Math.abs))
              const maxLatL = Math.max(...tele.lateral_acc.map(v => -v))
              const maxLatR = Math.max(...tele.lateral_acc)
              return <>
                <MetricCard label="Peak Lateral G" value={maxLat.toFixed(2)} unit="G" highlight={maxLat > 1.0} />
                <MetricCard label="Max Left"  value={maxLatL.toFixed(2)} unit="G" />
                <MetricCard label="Max Right" value={maxLatR.toFixed(2)} unit="G" />
              </>
            })()}
            {tele.inline_acc && (() => {
              const maxInl = Math.max(...tele.inline_acc.map(Math.abs))
              return <MetricCard label="Peak Inline G" value={maxInl.toFixed(2)} unit="G" highlight={maxInl > 0.5} />
            })()}
          </div>

          {/* Lateral G trace */}
          {tele.lateral_acc && (
            <div className="bg-surface border border-border rounded-lg p-4 h-52">
              <h3 className="text-xs text-gray-400 uppercase tracking-wider mb-2">Lateral G vs Time</h3>
              <ResponsiveContainer width="100%" height="90%">
                <AreaChart
                  data={tele.time.map((t, i) => ({ t: +t.toFixed(2), g: +(tele.lateral_acc![i]).toFixed(3) }))}
                  margin={{ top: 5, right: 10, bottom: 15, left: 10 }}>
                  <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                  <XAxis dataKey="t" stroke={CHART_STYLE.axis} tick={{ fontSize: 9 }}
                    label={{ value: 'Time (s)', position: 'insideBottom', offset: -10, fill: '#6a8090', fontSize: 9 }} />
                  <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 9 }}
                    label={{ value: 'G', angle: -90, position: 'insideLeft', fill: '#6a8090', fontSize: 9 }} />
                  <ReferenceLine y={0} stroke={CHART_STYLE.axis} strokeDasharray="2 2" />
                  <Tooltip contentStyle={CHART_STYLE.tooltip}
                    formatter={(v: any) => [`${v} G`, 'Lateral']} labelFormatter={(t: any) => `t=${t}s`} />
                  <Area type="monotone" dataKey="g" stroke="#FFD700" fill="#FFD700" fillOpacity={0.15} dot={false} strokeWidth={1.5} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Inline G trace */}
          {tele.inline_acc && (
            <div className="bg-surface border border-border rounded-lg p-4 h-52">
              <h3 className="text-xs text-gray-400 uppercase tracking-wider mb-2">Inline G vs Time <span className="text-gray-600">(+accel / −braking)</span></h3>
              <ResponsiveContainer width="100%" height="90%">
                <AreaChart
                  data={tele.time.map((t, i) => ({ t: +t.toFixed(2), g: +(tele.inline_acc![i]).toFixed(3) }))}
                  margin={{ top: 5, right: 10, bottom: 15, left: 10 }}>
                  <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                  <XAxis dataKey="t" stroke={CHART_STYLE.axis} tick={{ fontSize: 9 }}
                    label={{ value: 'Time (s)', position: 'insideBottom', offset: -10, fill: '#6a8090', fontSize: 9 }} />
                  <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 9 }} />
                  <ReferenceLine y={0} stroke={CHART_STYLE.axis} strokeDasharray="2 2" />
                  <Tooltip contentStyle={CHART_STYLE.tooltip}
                    formatter={(v: any) => [`${v} G`, 'Inline']} labelFormatter={(t: any) => `t=${t}s`} />
                  <Area type="monotone" dataKey="g" stroke="#00BFFF" fill="#00BFFF" fillOpacity={0.15} dot={false} strokeWidth={1.5} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* GG diagram */}
          {tele.lateral_acc && tele.inline_acc && (() => {
            const ggData = tele.lateral_acc.map((lat, i) => ({
              lat: +lat.toFixed(3), inl: +(tele.inline_acc![i]).toFixed(3)
            }))
            const envelope = 1.5
            return (
              <div className="bg-surface border border-border rounded-lg p-4">
                <h3 className="text-xs text-gray-400 uppercase tracking-wider mb-2">
                  GG Diagram <span className="text-gray-600">— lateral vs inline (traction circle)</span>
                </h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={ggData} margin={{ top: 10, right: 10, bottom: 10, left: 10 }}>
                      <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                      <XAxis type="number" dataKey="lat" domain={[-envelope, envelope]}
                        stroke={CHART_STYLE.axis} tick={{ fontSize: 9 }}
                        label={{ value: 'Lateral G', position: 'insideBottom', offset: -5, fill: '#6a8090', fontSize: 9 }} />
                      <YAxis type="number" dataKey="inl" domain={[-envelope, envelope]}
                        stroke={CHART_STYLE.axis} tick={{ fontSize: 9 }}
                        label={{ value: 'Inline G', angle: -90, position: 'insideLeft', fill: '#6a8090', fontSize: 9 }} />
                      <ReferenceLine y={0} stroke={CHART_STYLE.axis} strokeDasharray="2 2" />
                      <ReferenceLine x={0} stroke={CHART_STYLE.axis} strokeDasharray="2 2" />
                      <Tooltip contentStyle={CHART_STYLE.tooltip}
                        formatter={(v: any, name: string) => [`${v} G`, name === 'inl' ? 'Inline' : 'Lateral']} />
                      <Line type="linear" dataKey="inl" stroke="#00FF88" dot={{ r: 1, fill: '#00FF88' }}
                        strokeWidth={0} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  A full traction circle means you're using available grip in all directions.
                  Sparse corners indicate unused grip on corner entry/exit.
                </p>
              </div>
            )
          })()}
        </div>
      )}

      {/* Corners tab */}
      {activeTab === 'corners' && (
        <div className="space-y-4">
          {corners.length === 0 ? (
            <div className="text-gray-400 text-sm text-center py-10">No corners detected in this lap.</div>
          ) : (
            <>
              <div className="bg-surface border border-border rounded-lg p-4 h-64">
                <h3 className="text-xs text-gray-400 uppercase tracking-wider mb-3">Corner Speed Profile</h3>
                <ResponsiveContainer width="100%" height="90%">
                  <BarChart data={cornerData} margin={{ top: 5, right: 10, bottom: 5, left: -10 }}>
                    <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="name" stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} />
                    <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} tickFormatter={v => `${v}`} unit=" mph" />
                    <Tooltip contentStyle={CHART_STYLE.tooltip}
                      formatter={(v: any, name: string) => [`${(+v).toFixed(1)} mph`, name]} />
                    <Legend wrapperStyle={{ fontSize: 11, color: '#888' }} />
                    <Bar dataKey="entry" name="Entry"  fill="#4488FF" radius={[2,2,0,0]} />
                    <Bar dataKey="apex"  name="Apex"   fill="#FFD700" radius={[2,2,0,0]} />
                    <Bar dataKey="exit"  name="Exit"   fill="#00FF88" radius={[2,2,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="rounded-lg border border-border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-surface text-xs text-gray-400 uppercase tracking-wider">
                    <tr>
                      <th className="px-4 py-3 text-left">Corner</th>
                      <th className="px-4 py-3 text-right">Entry mph</th>
                      <th className="px-4 py-3 text-right">Apex mph</th>
                      <th className="px-4 py-3 text-right">Exit mph</th>
                      <th className="px-4 py-3 text-right">Δ Entry→Apex</th>
                      <th className="px-4 py-3 text-right">Entry @ s</th>
                    </tr>
                  </thead>
                  <tbody>
                    {corners.map(c => {
                      const entryMph = mphKmh(c.entry_speed_kmh)
                      const apexMph  = mphKmh(c.apex_speed_kmh)
                      const exitMph  = mphKmh(c.exit_speed_kmh)
                      const drop = entryMph - apexMph
                      return (
                        <tr key={c.corner_index} className="border-t border-border hover:bg-surface transition-colors">
                          <td className="px-4 py-2.5 text-white font-bold font-mono">C{c.corner_index}</td>
                          <td className="px-4 py-2.5 text-right font-mono text-blue-400">{entryMph.toFixed(1)}</td>
                          <td className="px-4 py-2.5 text-right font-mono text-gold font-bold">{apexMph.toFixed(1)}</td>
                          <td className="px-4 py-2.5 text-right font-mono text-green">{exitMph.toFixed(1)}</td>
                          <td className={`px-4 py-2.5 text-right font-mono text-xs ${drop > 12 ? 'text-red' : drop > 6 ? 'text-orange' : 'text-gray-400'}`}>
                            -{drop.toFixed(1)}
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-gray-500 text-xs">{c.entry_time_s.toFixed(2)}s</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* Sectors tab */}
      {activeTab === 'sectors' && (
        <div className="space-y-4">
          {sectors.length === 0 ? (
            <div className="text-gray-400 text-sm text-center py-10">No sector data.</div>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                {sectors.map(s => (
                  <div key={s.sector_num} className="bg-surface border border-border rounded-lg p-3 text-center space-y-1">
                    <div className="text-xs text-gray-400 uppercase tracking-wider">S{s.sector_num}</div>
                    <div className="text-xl font-bold font-mono text-accent">{s.time_s.toFixed(3)}</div>
                    <div className="text-xs text-gray-400">Avg {mphKmh(s.avg_speed_kmh).toFixed(1)} mph</div>
                    <div className="text-xs text-gray-600">{s.dist_start_m.toFixed(0)}–{s.dist_end_m.toFixed(0)} m</div>
                  </div>
                ))}
              </div>
              <div className="bg-surface border border-border rounded-lg p-4 h-56">
                <h3 className="text-xs text-gray-400 uppercase tracking-wider mb-3">Speed Range by Sector</h3>
                <ResponsiveContainer width="100%" height="85%">
                  <BarChart data={sectorData} margin={{ top: 5, right: 10, bottom: 5, left: -10 }}>
                    <CartesianGrid stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="name" stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} />
                    <YAxis stroke={CHART_STYLE.axis} tick={{ fontSize: 10 }} unit=" mph" />
                    <Tooltip contentStyle={CHART_STYLE.tooltip}
                      formatter={(v: any, name: string) => [`${(+v).toFixed(1)} mph`, name]} />
                    <Legend wrapperStyle={{ fontSize: 11, color: '#888' }} />
                    <Bar dataKey="min"  name="Min"  fill="#FF4444" radius={[2,2,0,0]} />
                    <Bar dataKey="avg"  name="Avg"  fill="#00BFFF" radius={[2,2,0,0]} />
                    <Bar dataKey="max"  name="Max"  fill="#00FF88" radius={[2,2,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      )}

      {/* Energy tab */}
      {activeTab === 'energy' && (
        <div className="space-y-4">
          {!energy ? (
            <div className="text-gray-400 text-sm text-center py-10">Energy data not available.</div>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <MetricCard label="Total Used"      value={energy.total_kwh.toFixed(4)}     unit="kWh" highlight />
                <MetricCard label="Net (after regen)" value={energy.net_kwh.toFixed(4)}     unit="kWh" />
                <MetricCard label="Avg Power"       value={energy.avg_power_kw.toFixed(2)}  unit="kW" />
                <MetricCard label="Peak Power"      value={energy.peak_power_kw.toFixed(2)} unit="kW" highlight />
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <MetricCard label="Regen Recovered" value={energy.regen_kwh.toFixed(4)}         unit="kWh" />
                <MetricCard label="Laps/Charge"     value={energy.laps_per_charge.toFixed(1)}   unit="laps" />
                <MetricCard label="Est. Range"      value={energy.estimated_range_km.toFixed(1)} unit="km" />
              </div>
              <div className="bg-surface border border-border rounded-lg p-4 text-sm text-gray-300 space-y-2">
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Analysis</h3>
                <p>
                  At <span className="text-white font-bold">{energy.avg_power_kw.toFixed(1)} kW</span> average
                  draw, your battery will last approximately{' '}
                  <span className="text-accent font-bold">{energy.laps_per_charge.toFixed(1)} laps</span> per charge.
                  Peak demand of <span className="text-orange font-bold">{energy.peak_power_kw.toFixed(1)} kW</span>{' '}
                  — ensure your Alltrax max current setting can sustain this without thermal cutback.
                </p>
                {energy.regen_kwh > 0 && (
                  <p>Regen recovered <span className="text-green font-bold">{energy.regen_kwh.toFixed(4)} kWh</span>,
                    saving {((energy.regen_kwh / energy.total_kwh) * 100).toFixed(1)}% of gross consumption.
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Features tab */}
      {activeTab === 'features' && (
        <div className="space-y-4">
          {!feats ? (
            <div className="text-gray-400 text-sm text-center py-10">Features not computed yet. Features are extracted automatically after session ingestion.</div>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <MetricCard label="Throttle Variance"      value={feats.throttle_variance.toFixed(3)}      unit="" />
                <MetricCard label="Braking Intensity"      value={feats.braking_intensity.toFixed(3)}      unit="" />
                <MetricCard label="Corner Entry Avg"       value={feats.corner_entry_speed_avg.toFixed(1)} unit="m/s" />
                <MetricCard label="Accel Consistency"      value={feats.accel_consistency.toFixed(3)}      unit="" />
                <MetricCard label="Smoothness Score"       value={feats.smoothness_score.toFixed(1)}       unit="" highlight={feats.smoothness_score > 75} />
              </div>
              <div className="bg-surface border border-border rounded-lg p-4 space-y-3">
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">What These Mean</h3>
                <div className="space-y-2 text-sm text-gray-300">
                  <FeatureExplain label="Throttle Variance" value={feats.throttle_variance.toFixed(3)}
                    good={feats.throttle_variance < 0.15}
                    tip={feats.throttle_variance > 0.15
                      ? 'High variance means choppy throttle inputs. Try smoother acceleration on exits — reduces drivetrain stress and improves consistency.'
                      : 'Good throttle smoothness. Consistent inputs are translating into efficient lap times.'} />
                  <FeatureExplain label="Braking Intensity" value={feats.braking_intensity.toFixed(3)}
                    good={feats.braking_intensity > 0.3}
                    tip={feats.braking_intensity < 0.3
                      ? 'Low braking intensity — braking late and hard is fine but check you\'re not over-slowing. Increase decel_rate on Alltrax for better regen.'
                      : 'Strong braking phases. Ensure decel_rate is set high enough to take advantage of regen.'} />
                  <FeatureExplain label="Accel Consistency" value={feats.accel_consistency.toFixed(3)}
                    good={feats.accel_consistency > 0.7}
                    tip={feats.accel_consistency < 0.7
                      ? 'Inconsistent acceleration exits. Consider adjusting throttle curve to a softer initial response to help traction out of corners.'
                      : 'Excellent acceleration consistency — your throttle map is well-matched to this track.'} />
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function FeatureExplain({ label, value, good, tip }: { label: string; value: string; good: boolean; tip: string }) {
  return (
    <div className="flex gap-3 items-start">
      <span className={`shrink-0 text-base ${good ? 'text-green' : 'text-orange'}`}>{good ? '✓' : '!'}</span>
      <div>
        <span className="text-white font-medium">{label}: </span>
        <span className="font-mono text-accent">{value}</span>
        <p className="text-xs text-gray-400 mt-0.5">{tip}</p>
      </div>
    </div>
  )
}
