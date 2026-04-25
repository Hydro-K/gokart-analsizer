import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, Telemetry } from '../api'
import { MetricCard } from '../components/common/MetricCard'
import { useUIStore } from '../store/uiStore'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

interface SectorData { sector: number; dist_start_m: number; dist_end_m: number; time_s: number; avg_speed_kmh: number }
interface CornerData  { corner_number: number; apex_speed_kmh: number; entry_speed_kmh: number; exit_speed_kmh: number }

function fmt(s: number) {
  const m = Math.floor(s / 60); const sec = (s % 60).toFixed(3).padStart(6, '0')
  return `${m}:${sec}`
}

export default function LapAnalysis() {
  const { id } = useParams<{ id: string }>()
  const [tele, setTele]       = useState<Telemetry | null>(null)
  const [sectors, setSectors] = useState<SectorData[]>([])
  const [corners, setCorners] = useState<CornerData[]>([])
  const [energy, setEnergy]   = useState<number | null>(null)
  const mode = useUIStore(s => s.mode)

  useEffect(() => {
    if (!id) return
    api.get<Telemetry>(`/laps/${id}/telemetry?points=500`).then(setTele).catch(() => {})
    api.get<SectorData[]>(`/laps/${id}/sectors`).then(setSectors).catch(() => {})
    if (mode === 'engineer') {
      api.get<CornerData[]>(`/laps/${id}/corners`).then(setCorners).catch(() => {})
      api.get<{ energy_kwh: number }>(`/laps/${id}/energy`).then(r => setEnergy(r.energy_kwh)).catch(() => {})
    }
  }, [id, mode])

  const chartData = tele
    ? tele.time.map((t, i) => ({ t: +t.toFixed(2), v: +(tele.speed[i] * 3.6).toFixed(1) }))
    : []

  const phaseColor = (phase: string) => {
    if (phase === 'accelerating') return '#00FF88'
    if (phase === 'braking') return '#FF4444'
    if (phase === 'cornering') return '#FFD700'
    return '#4488FF'
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Lap #{id} Analysis</h1>

      {/* Speed trace */}
      <div>
        <h2 className="text-lg font-bold text-white mb-3">Speed Trace</h2>
        <div className="bg-surface border border-border rounded-lg p-4 h-52">
          {chartData.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-400 text-sm">No telemetry data</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid stroke="#1a2a3a" strokeDasharray="3 3" />
                <XAxis dataKey="t" stroke="#666" tick={{ fontSize: 10 }} label={{ value: 'Time (s)', position: 'insideBottom', offset: -2, fill: '#888', fontSize: 10 }} />
                <YAxis stroke="#666" tick={{ fontSize: 10 }} label={{ value: 'km/h', angle: -90, position: 'insideLeft', fill: '#888', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#112233', border: '1px solid #1a2a3a', borderRadius: 4 }} labelStyle={{ color: '#aaa', fontSize: 11 }} itemStyle={{ color: '#00BFFF' }} />
                <Line type="monotone" dataKey="v" stroke="#00BFFF" dot={false} strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Sectors */}
      {sectors.length > 0 && (
        <div>
          <h2 className="text-lg font-bold text-white mb-3">Sector Splits</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {sectors.map(s => (
              <MetricCard key={s.sector} label={`S${s.sector}`} value={s.time_s.toFixed(3)} unit="s"
                tooltip={`${s.dist_start_m.toFixed(0)}–${s.dist_end_m.toFixed(0)}m · avg ${s.avg_speed_kmh.toFixed(1)} km/h`} />
            ))}
          </div>
        </div>
      )}

      {/* Energy */}
      {mode === 'engineer' && energy !== null && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricCard label="Est. Energy" value={energy.toFixed(3)} unit="kWh" />
        </div>
      )}

      {/* Corners table */}
      {mode === 'engineer' && corners.length > 0 && (
        <div>
          <h2 className="text-lg font-bold text-white mb-3">Corner Analysis</h2>
          <div className="rounded-lg border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-surface text-gray-400 text-xs uppercase">
                <tr>
                  <th className="px-4 py-2 text-left">Corner</th>
                  <th className="px-4 py-2 text-right">Entry km/h</th>
                  <th className="px-4 py-2 text-right">Apex km/h</th>
                  <th className="px-4 py-2 text-right">Exit km/h</th>
                </tr>
              </thead>
              <tbody>
                {corners.map(c => (
                  <tr key={c.corner_number} className="border-t border-border">
                    <td className="px-4 py-2 text-white font-mono">{c.corner_number}</td>
                    <td className="px-4 py-2 text-right font-mono">{c.entry_speed_kmh.toFixed(1)}</td>
                    <td className="px-4 py-2 text-right font-mono text-gold">{c.apex_speed_kmh.toFixed(1)}</td>
                    <td className="px-4 py-2 text-right font-mono text-green">{c.exit_speed_kmh.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
