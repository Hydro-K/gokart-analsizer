import { useEffect, useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

interface Driver { id: number; name: string }
interface Kart   { id: number; name: string }
interface Track  { id: number; name: string }

function parseLapTimes(raw: string): number[] | null {
  const parts = raw.split(/[\n,]+/).map(s => s.trim()).filter(Boolean)
  const result: number[] = []
  for (const p of parts) {
    // Accept M:SS.mmm or raw seconds
    const mmss = p.match(/^(\d+):(\d{2})\.(\d{1,3})$/)
    if (mmss) {
      result.push(parseInt(mmss[1]) * 60 + parseFloat(`${mmss[2]}.${mmss[3].padEnd(3,'0')}`))
      continue
    }
    const s = parseFloat(p)
    if (!isNaN(s) && s > 0) { result.push(s); continue }
    return null
  }
  return result.length > 0 ? result : null
}

export default function QuickEntry() {
  const nav = useNavigate()
  const [drivers, setDrivers] = useState<Driver[]>([])
  const [karts, setKarts]     = useState<Kart[]>([])
  const [tracks, setTracks]   = useState<Track[]>([])
  const [form, setForm] = useState({
    driver_id: '', kart_id: '', track_id: '',
    date: new Date().toISOString().slice(0, 10),
    session_type: 'Practice 1',
    notes: '',
    lap_times_raw: '',
  })
  const [error, setError]     = useState('')
  const [saving, setSaving]   = useState(false)
  const [preview, setPreview] = useState<number[] | null>(null)

  useEffect(() => {
    api.get<Driver[]>('/drivers').then(setDrivers).catch(() => {})
    api.get<Kart[]>('/karts').then(setKarts).catch(() => {})
    api.get<Track[]>('/tracks').then(setTracks).catch(() => {})
  }, [])

  useEffect(() => {
    if (!form.lap_times_raw) { setPreview(null); return }
    setPreview(parseLapTimes(form.lap_times_raw))
  }, [form.lap_times_raw])

  const fmt = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = (s % 60).toFixed(3).padStart(6, '0')
    return `${m}:${sec}`
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    if (!form.driver_id || !form.kart_id || !form.track_id) { setError('Select driver, kart, and track.'); return }
    if (!preview || preview.length === 0) { setError('No valid lap times entered.'); return }
    setSaving(true)
    try {
      const res = await api.post<any>('/sessions/quick', {
        driver_id: +form.driver_id, kart_id: +form.kart_id, track_id: +form.track_id,
        date: form.date, session_type: form.session_type, notes: form.notes,
        lap_times_s: preview,
      })
      nav(`/sessions/${res.session_id}`)
    } catch (err: any) {
      setError(err.message ?? 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const SESSION_TYPES = ['Practice 1','Practice 2','Practice 3','Qualifying','Heat Race','Main Race','Endurance','Test & Tune','Shakedown']

  const sel = 'w-full bg-bg border border-border rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-accent'

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Quick Lap Entry</h1>
        <p className="text-gray-400 text-sm mt-1">Manually enter lap times without uploading a CSV.</p>
      </div>

      {error && <div className="text-red text-sm rounded border border-red border-opacity-40 bg-surface px-4 py-2">{error}</div>}

      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Driver</label>
            <select value={form.driver_id} onChange={e => setForm(f => ({ ...f, driver_id: e.target.value }))} className={sel}>
              <option value="">Select…</option>
              {drivers.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Kart</label>
            <select value={form.kart_id} onChange={e => setForm(f => ({ ...f, kart_id: e.target.value }))} className={sel}>
              <option value="">Select…</option>
              {karts.map(k => <option key={k.id} value={k.id}>{k.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Track</label>
            <select value={form.track_id} onChange={e => setForm(f => ({ ...f, track_id: e.target.value }))} className={sel}>
              <option value="">Select…</option>
              {tracks.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Date</label>
            <input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} className={sel} />
          </div>
          <div className="col-span-2">
            <label className="block text-xs text-gray-400 mb-1">Session Type</label>
            <select value={form.session_type} onChange={e => setForm(f => ({ ...f, session_type: e.target.value }))} className={sel}>
              {SESSION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs text-gray-400 mb-1">
            Lap Times — one per line or comma-separated. Format: <code className="text-accent">1:23.456</code> or <code className="text-accent">83.456</code>
          </label>
          <textarea rows={6} value={form.lap_times_raw}
            onChange={e => setForm(f => ({ ...f, lap_times_raw: e.target.value }))}
            placeholder="1:23.456&#10;1:22.891&#10;1:24.012"
            className="w-full bg-bg border border-border rounded px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-accent resize-none" />
        </div>

        {/* Preview */}
        {preview && preview.length > 0 && (
          <div className="rounded-lg border border-border bg-surface p-3 space-y-1">
            <div className="text-xs text-gray-400 uppercase tracking-wider mb-2">{preview.length} laps parsed</div>
            <div className="flex flex-wrap gap-2">
              {preview.map((t, i) => (
                <span key={i} className="px-2 py-0.5 bg-bg rounded text-xs font-mono text-white border border-border">
                  L{i+1} {fmt(t)}
                </span>
              ))}
            </div>
            <div className="text-xs text-gray-500 pt-1">
              Best: <span className="text-accent font-bold">{fmt(Math.min(...preview))}</span>
              {' · '}Avg: <span className="text-white">{fmt(preview.reduce((a,b)=>a+b,0)/preview.length)}</span>
            </div>
          </div>
        )}
        {form.lap_times_raw && (!preview || preview.length === 0) && (
          <div className="text-red text-xs">Could not parse lap times — use M:SS.mmm or decimal seconds.</div>
        )}

        <div>
          <label className="block text-xs text-gray-400 mb-1">Notes (optional)</label>
          <input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
            className={sel} placeholder="e.g. traffic on lap 3" />
        </div>

        <button type="submit" disabled={saving || !preview || preview.length === 0}
          className="w-full py-2 bg-accent text-bg font-bold rounded hover:opacity-90 disabled:opacity-40 transition-opacity">
          {saving ? 'Saving...' : `Save Session (${preview?.length ?? 0} laps)`}
        </button>
      </form>
    </div>
  )
}
