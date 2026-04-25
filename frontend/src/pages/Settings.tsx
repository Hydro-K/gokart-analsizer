import { useEffect, useState, FormEvent } from 'react'
import { api } from '../api'

interface Rules {
  controller_max_current_a: number
  battery_voltage_max_v: number
  battery_voltage_min_v: number
  battery_voltage_nominal_v: number
  battery_capacity_wh: number
  speed_limit_kmh: number
  combined_min_weight_kg: number
  rulebook_version: string
}

export default function Settings() {
  const [rules, setRules] = useState<Rules | null>(null)
  const [form, setForm]   = useState<Partial<Rules>>({})
  const [saved, setSaved] = useState(false)
  const [version, setVersion] = useState<string>('')

  useEffect(() => {
    api.get<Rules>('/compliance/rules').then(r => { setRules(r); setForm(r) }).catch(() => {})
    api.get<any>('/system/status').then(s => setVersion(s.version)).catch(() => {})
  }, [])

  const save = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await api.put('/compliance/rules', form)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err: any) { alert(err.message) }
  }

  const f = (k: keyof Rules) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(prev => ({ ...prev, [k]: e.target.type === 'number' ? parseFloat(e.target.value) : e.target.value }))

  if (!rules) return <div className="text-gray-400">Loading...</div>

  return (
    <div className="space-y-6 max-w-lg">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      <div className="bg-surface border border-border rounded-lg p-4">
        <h2 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">System</h2>
        <div className="text-sm text-gray-300">Version: <span className="font-mono text-white">{version}</span></div>
      </div>

      <form onSubmit={save} className="space-y-4 bg-surface border border-border rounded-lg p-4">
        <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Competition Rules</h2>
        <p className="text-xs text-gray-400">Controller max current is hard-capped at 220A regardless of this setting.</p>

        <div className="grid grid-cols-2 gap-3">
          {([
            ['controller_max_current_a', 'Max Current (A, ≤220)', 'number'],
            ['speed_limit_kmh',          'Speed Limit (km/h)',    'number'],
            ['battery_voltage_max_v',    'Battery Voltage Max (V)','number'],
            ['battery_voltage_min_v',    'Battery Voltage Min (V)','number'],
            ['battery_capacity_wh',      'Battery Capacity (Wh)', 'number'],
            ['combined_min_weight_kg',   'Min Combined Weight (kg)','number'],
          ] as [keyof Rules, string, string][]).map(([key, label, type]) => (
            <div key={key}>
              <label className="block text-xs text-gray-400 mb-1">{label}</label>
              <input
                type={type}
                step="0.1"
                value={form[key] ?? ''}
                onChange={f(key)}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent"
              />
            </div>
          ))}
        </div>

        <div>
          <label className="block text-xs text-gray-400 mb-1">Rulebook Version</label>
          <input
            value={form.rulebook_version ?? ''}
            onChange={f('rulebook_version')}
            className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent"
          />
        </div>

        <div className="flex items-center gap-3">
          <button type="submit" className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">
            Save Rules
          </button>
          {saved && <span className="text-green text-sm">Saved!</span>}
        </div>
      </form>

      <div className="bg-surface border border-border rounded-lg p-4 text-sm text-gray-400 space-y-1">
        <h2 className="text-xs font-bold text-white uppercase tracking-wider mb-2">Archive Backend</h2>
        <p>Set <code className="text-accent">STRATOS_ARCHIVE_BACKEND</code> env var to one of:</p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li><code className="text-white">disabled</code> — no archiving (default)</li>
          <li><code className="text-white">smb</code> — network share (<code>STRATOS_SMB_SHARE=//host/share</code>)</li>
          <li><code className="text-white">rclone_gdrive</code> — Google Drive via rclone (<code>STRATOS_RCLONE_REMOTE=gdrive:path</code>)</li>
        </ul>
      </div>
    </div>
  )
}
