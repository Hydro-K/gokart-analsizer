import { useEffect, useState, FormEvent } from 'react'
import { api, Session, Lap } from '../api'
import { MetricCard } from '../components/common/MetricCard'
import { JobProgress } from '../components/common/JobProgress'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

interface ModeAResult {
  delta_lap_time_s: number
  predicted_lap_time_s: number
  delta_points: number[]
  energy_delta_kwh: number
}

export default function Simulation() {
  const [sessions, setSessions]   = useState<Session[]>([])
  const [laps, setLaps]           = useState<Lap[]>([])
  const [sessionId, setSessionId] = useState('')
  const [lapId, setLapId]         = useState('')
  const [result, setResult]       = useState<ModeAResult | null>(null)
  const [jobId, setJobId]         = useState<number | null>(null)
  const [error, setError]         = useState('')
  const [loading, setLoading]     = useState(false)

  const [form, setForm] = useState({
    max_current: '200',
    accel_rate: '1.0',
    speed_limit_pct: '100',
    gear_ratio_new: '8.0',
    gear_ratio_old: '8.0',
    mass_new_kg: '115',
    mode: 'a',
    goal: 'lap_time',
    weight_speed: '0.5',
    weight_energy: '0.5',
  })

  useEffect(() => {
    api.get<Session[]>('/sessions').then(setSessions).catch(() => {})
  }, [])

  useEffect(() => {
    if (!sessionId) { setLaps([]); return }
    api.get<Lap[]>(`/sessions/${sessionId}/laps`).then(ls => {
      setLaps(ls.filter(l => l.is_valid))
      setLapId(String(ls.find(l => l.is_valid)?.id ?? ''))
    }).catch(() => {})
  }, [sessionId])

  const f = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(prev => ({ ...prev, [k]: e.target.value }))

  const run = async (e: FormEvent) => {
    e.preventDefault()
    if (!lapId) { setError('Select a lap first'); return }
    setError(''); setResult(null); setJobId(null); setLoading(true)
    try {
      if (form.mode === 'a') {
        const res = await api.post<ModeAResult>('/simulation/mode-a', {
          lap_id: parseInt(lapId),
          max_current: parseInt(form.max_current),
          accel_rate: parseFloat(form.accel_rate),
          speed_limit_pct: parseFloat(form.speed_limit_pct),
          gear_ratio_new: parseFloat(form.gear_ratio_new),
          gear_ratio_old: parseFloat(form.gear_ratio_old),
          mass_new_kg: parseFloat(form.mass_new_kg),
        })
        setResult(res)
      } else {
        const res = await api.post<{ job_id: number }>('/simulation/mode-c', {
          lap_id: parseInt(lapId),
          session_id: parseInt(sessionId),
          goal: form.goal,
          weight_speed: parseFloat(form.weight_speed),
          weight_energy: parseFloat(form.weight_energy),
          max_current: parseInt(form.max_current),
        })
        setJobId(res.job_id)
      }
    } catch (err: any) { setError(err.message) }
    finally { setLoading(false) }
  }

  const deltaData = result?.delta_points.map((d, i) => ({ i, d: +d.toFixed(4) })) ?? []
  const bestTime = laps.find(l => l.id === parseInt(lapId))?.lap_time_s ?? 0

  function fmtTime(s: number) {
    const m = Math.floor(s / 60); const sec = (s % 60).toFixed(3).padStart(6,'0')
    return `${m}:${sec}`
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-white">Simulation</h1>
        <p className="text-gray-400 text-sm mt-1">
          Mode A: fast linear (&lt;100ms). Mode C: physics ODE (async job, 2-5s).
          Max current hard-capped at <span className="text-orange font-bold">220A</span>.
        </p>
      </div>

      <form onSubmit={run} className="space-y-4">
        {error && <div className="text-red text-sm bg-red bg-opacity-10 border border-red rounded px-3 py-2">{error}</div>}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Session</label>
            <select value={sessionId} onChange={e => setSessionId(e.target.value)}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent">
              <option value="">Select session...</option>
              {sessions.map(s => <option key={s.id} value={s.id}>{s.date} — {s.session_type}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Reference Lap</label>
            <select value={lapId} onChange={e => setLapId(e.target.value)}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent">
              <option value="">Select lap...</option>
              {laps.map(l => <option key={l.id} value={l.id}>Lap {l.lap_number} — {fmtTime(l.lap_time_s)}</option>)}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Mode</label>
            <select value={form.mode} onChange={f('mode')}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent">
              <option value="a">Mode A — Fast Linear</option>
              <option value="c">Mode C — Physics ODE</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Max Current (A, ≤220)</label>
            <input type="number" max={220} value={form.max_current} onChange={f('max_current')}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
          </div>
        </div>

        {form.mode === 'a' && (
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Accel Rate ×</label>
              <input type="number" step="0.05" value={form.accel_rate} onChange={f('accel_rate')}
                className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Speed Limit %</label>
              <input type="number" max={100} value={form.speed_limit_pct} onChange={f('speed_limit_pct')}
                className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Gear Ratio (new)</label>
              <input type="number" step="0.1" value={form.gear_ratio_new} onChange={f('gear_ratio_new')}
                className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            </div>
          </div>
        )}

        <button type="submit" disabled={loading}
          className="w-full py-2 bg-accent text-bg font-bold rounded hover:opacity-90 disabled:opacity-50">
          {loading ? 'Running...' : form.mode === 'a' ? 'Run Mode A' : 'Queue Mode C'}
        </button>
      </form>

      {jobId && <JobProgress jobId={jobId} />}

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <MetricCard
              label="Delta"
              value={`${result.delta_lap_time_s >= 0 ? '+' : ''}${result.delta_lap_time_s.toFixed(3)}`}
              unit="s"
              highlight={result.delta_lap_time_s < 0}
            />
            <MetricCard label="Predicted" value={fmtTime(result.predicted_lap_time_s)} />
            <MetricCard label="Energy Δ" value={`${result.energy_delta_kwh >= 0 ? '+' : ''}${result.energy_delta_kwh.toFixed(4)}`} unit="kWh" />
          </div>

          {deltaData.length > 0 && (
            <div>
              <h2 className="text-sm font-bold text-gray-300 mb-2 uppercase tracking-wider">Time Delta</h2>
              <div className="bg-surface border border-border rounded-lg p-3 h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={deltaData}>
                    <CartesianGrid stroke="#1a2a3a" strokeDasharray="3 3" />
                    <XAxis dataKey="i" stroke="#666" tick={{ fontSize: 9 }} />
                    <YAxis stroke="#666" tick={{ fontSize: 9 }} />
                    <Tooltip contentStyle={{ background: '#112233', border: '1px solid #1a2a3a', fontSize: 11 }} />
                    <ReferenceLine y={0} stroke="#666" />
                    <Line type="monotone" dataKey="d" stroke="#FF8800" dot={false} strokeWidth={1.5} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
