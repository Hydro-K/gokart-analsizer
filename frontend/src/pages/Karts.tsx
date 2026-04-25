import { useEffect, useState, FormEvent } from 'react'
import { api, Kart } from '../api'

export default function Karts() {
  const [karts, setKarts] = useState<Kart[]>([])
  const [form, setForm]   = useState({ name: '', motor_type: 'DC Series', battery_type: 'LiFePO4', mass_kg: '115' })
  const [error, setError] = useState('')

  const load = () => api.get<Kart[]>('/karts').then(setKarts).catch(() => {})
  useEffect(load, [])

  const create = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    try {
      await api.post('/karts', { ...form, mass_kg: parseFloat(form.mass_kg) })
      setForm({ name: '', motor_type: 'DC Series', battery_type: 'LiFePO4', mass_kg: '115' })
      load()
    } catch (err: any) { setError(err.message) }
  }

  const del = async (id: number) => {
    if (!confirm('Delete kart?')) return
    try { await api.delete(`/karts/${id}`); load() }
    catch (err: any) { alert(err.message) }
  }

  const f = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(prev => ({ ...prev, [k]: e.target.value }))

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white">Karts</h1>

      <form onSubmit={create} className="space-y-3 bg-surface border border-border rounded-lg p-4">
        <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Add Kart</h2>
        <p className="text-xs text-orange">Max controller current capped at 220A (EVGP rule)</p>
        {error && <div className="text-red text-sm">{error}</div>}
        <input placeholder="Kart name" required value={form.name} onChange={f('name')}
          className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Motor Type</label>
            <select value={form.motor_type} onChange={f('motor_type')}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent">
              <option>DC Series</option><option>DC Permanent Magnet</option><option>BLDC</option><option>AC Induction</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Battery Type</label>
            <select value={form.battery_type} onChange={f('battery_type')}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent">
              <option>LiFePO4</option><option>NMC</option><option>Lead Acid</option>
            </select>
          </div>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Kart Mass (kg, without driver)</label>
          <input type="number" step="0.1" value={form.mass_kg} onChange={f('mass_kg')}
            className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
        </div>
        <button type="submit" className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">
          Add Kart
        </button>
      </form>

      <div className="space-y-2">
        {karts.map(k => (
          <div key={k.id} className="flex items-center gap-4 rounded-lg border border-border bg-surface px-4 py-3">
            <div className="flex-1 min-w-0">
              <div className="text-white font-medium">{k.name}</div>
              <div className="text-xs text-gray-400">{k.motor_type} · {k.battery_type} · {k.mass_kg} kg</div>
            </div>
            <button onClick={() => del(k.id)} className="text-xs text-gray-500 hover:text-red transition-colors">
              Delete
            </button>
          </div>
        ))}
        {karts.length === 0 && <p className="text-gray-400 text-sm">No karts yet.</p>}
      </div>
    </div>
  )
}
