import { useEffect, useState, FormEvent } from 'react'
import { api, Driver } from '../api'

export default function Drivers() {
  const [drivers, setDrivers] = useState<Driver[]>([])
  const [styles, setStyles]   = useState<Record<number, { style_label: string; confidence: number }>>({})
  const [name, setName]       = useState('')
  const [notes, setNotes]     = useState('')
  const [error, setError]     = useState('')

  const load = () => {
    api.get<Driver[]>('/drivers').then(ds => {
      setDrivers(ds)
      ds.forEach(d => {
        api.get<{ style_label: string; confidence: number }>(`/drivers/${d.id}/style`)
          .then(s => setStyles(prev => ({ ...prev, [d.id]: s })))
          .catch(() => {})
      })
    }).catch(() => {})
  }

  useEffect(load, [])

  const create = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await api.post('/drivers', { name: name.trim(), notes })
      setName(''); setNotes('')
      load()
    } catch (err: any) { setError(err.message) }
  }

  const del = async (id: number) => {
    if (!confirm('Delete driver? This will fail if they have sessions.')) return
    try { await api.delete(`/drivers/${id}`); load() }
    catch (err: any) { alert(err.message) }
  }

  const STYLE_COLOR: Record<string, string> = {
    aggressive: 'text-red', smooth: 'text-green', balanced: 'text-accent', inconsistent: 'text-gold'
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white">Drivers</h1>

      <form onSubmit={create} className="space-y-3 bg-surface border border-border rounded-lg p-4">
        <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Add Driver</h2>
        {error && <div className="text-red text-sm">{error}</div>}
        <input placeholder="Name" required value={name} onChange={e => setName(e.target.value)}
          className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
        <input placeholder="Notes (optional)" value={notes} onChange={e => setNotes(e.target.value)}
          className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
        <button type="submit" className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">
          Add Driver
        </button>
      </form>

      <div className="space-y-2">
        {drivers.map(d => (
          <div key={d.id} className="flex items-center gap-4 rounded-lg border border-border bg-surface px-4 py-3">
            <div className="flex-1 min-w-0">
              <div className="text-white font-medium">{d.name}</div>
              {d.notes && <div className="text-xs text-gray-400 truncate">{d.notes}</div>}
            </div>
            {styles[d.id] && (
              <div className="text-right">
                <div className={`text-sm font-bold capitalize ${STYLE_COLOR[styles[d.id].style_label] ?? 'text-white'}`}>
                  {styles[d.id].style_label}
                </div>
                <div className="text-xs text-gray-400">{styles[d.id].confidence.toFixed(0)}% conf.</div>
              </div>
            )}
            <button onClick={() => del(d.id)} className="text-xs text-gray-500 hover:text-red transition-colors ml-2">
              Delete
            </button>
          </div>
        ))}
        {drivers.length === 0 && <p className="text-gray-400 text-sm">No drivers yet.</p>}
      </div>
    </div>
  )
}
