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

interface AlltraxSettings {
  max_current: number
  accel_rate: number
  decel_rate: number
  speed_limit: number
  lo_voltage_cutoff: number
  hi_voltage_cutoff: number
  throttle_deadband: number
  peak_amp_mode: boolean
  regen_braking: boolean
  regen_intensity: number
  throttle_curve: number[]
}

interface Kart { id: number; name: string; settings_json: string; gear_json: string }

const THROTTLE_PRESETS: Record<string, number[]> = {
  'Linear':     [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
  'Aggressive': [0, 20, 37, 52, 64, 74, 82, 89, 95, 98, 100],
  'Soft S-Curve':[0,  2,  8, 18, 32, 50, 68, 82, 92, 98, 100],
  'Late Apex':  [0,  5, 11, 18, 27, 38, 52, 68, 82, 93, 100],
}

const RULE_PRESETS: Record<string, Partial<Rules>> = {
  'Purdue HSGP 2025-26': {
    controller_max_current_a: 220,
    battery_voltage_nominal_v: 51.2,
    battery_voltage_max_v: 58.4,
    battery_voltage_min_v: 40.0,
    battery_capacity_wh: 3072,
    speed_limit_kmh: 80,
    combined_min_weight_kg: 181.4,
    rulebook_version: 'Purdue HSGP 2025-26',
  },
  'EVGP 2025-26': {
    controller_max_current_a: 220,
    battery_voltage_nominal_v: 51.2,
    battery_voltage_max_v: 58.4,
    battery_voltage_min_v: 40.0,
    battery_capacity_wh: 3072,
    speed_limit_kmh: 80,
    combined_min_weight_kg: 181.4,
    rulebook_version: 'EVGP 2025-26',
  },
}

const DEFAULT_ALLTRAX: AlltraxSettings = {
  max_current: 180,
  accel_rate: 64,
  decel_rate: 64,
  speed_limit: 100,
  lo_voltage_cutoff: 42.0,
  hi_voltage_cutoff: 58.4,
  throttle_deadband: 10,
  peak_amp_mode: true,
  regen_braking: false,
  regen_intensity: 40,
  throttle_curve: [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
}

function parseAlltrax(json: string): AlltraxSettings {
  try { return { ...DEFAULT_ALLTRAX, ...JSON.parse(json || '{}') } }
  catch { return { ...DEFAULT_ALLTRAX } }
}

export default function Settings() {
  const [rules, setRules]   = useState<Rules | null>(null)
  const [ruleForm, setRuleForm] = useState<Partial<Rules>>({})
  const [ruleSaved, setRuleSaved] = useState(false)

  const [karts, setKarts]     = useState<Kart[]>([])
  const [kartId, setKartId]   = useState<number | null>(null)
  const [ax, setAx]           = useState<AlltraxSettings>({ ...DEFAULT_ALLTRAX })
  const [axSaved, setAxSaved] = useState(false)

  const [version, setVersion] = useState('')

  useEffect(() => {
    api.get<Rules>('/compliance/rules').then(r => { setRules(r); setRuleForm(r) }).catch(() => {})
    api.get<Kart[]>('/karts').then(ks => {
      setKarts(ks)
      if (ks.length > 0) { setKartId(ks[0].id); setAx(parseAlltrax(ks[0].settings_json)) }
    }).catch(() => {})
    api.get<any>('/system/status').then(s => setVersion(s.version)).catch(() => {})
  }, [])

  const selectKart = (id: number) => {
    setKartId(id)
    const k = karts.find(k => k.id === id)
    if (k) setAx(parseAlltrax(k.settings_json))
    setAxSaved(false)
  }

  const saveRules = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await api.put('/compliance/rules', ruleForm)
      setRuleSaved(true); setTimeout(() => setRuleSaved(false), 2500)
    } catch (err: any) { alert(err.message) }
  }

  const saveAlltrax = async (e: FormEvent) => {
    e.preventDefault()
    if (!kartId) return
    try {
      await api.put(`/karts/${kartId}`, { settings_json: JSON.stringify(ax) })
      setAxSaved(true); setTimeout(() => setAxSaved(false), 2500)
    } catch (err: any) { alert(err.message) }
  }

  const rf = (k: keyof Rules) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setRuleForm(p => ({ ...p, [k]: e.target.type === 'number' ? parseFloat(e.target.value) : e.target.value }))

  const axf = <K extends keyof AlltraxSettings>(k: K, val: AlltraxSettings[K]) =>
    setAx(p => ({ ...p, [k]: val }))

  if (!rules) return <div className="text-gray-400">Loading...</div>

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      {/* System */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <h2 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">System</h2>
        <div className="text-sm text-gray-300">Version: <span className="font-mono text-white">{version}</span></div>
      </div>

      {/* Competition Rules */}
      <form onSubmit={saveRules} className="bg-surface border border-border rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Competition Rules</h2>
          <div className="flex gap-2">
            {Object.keys(RULE_PRESETS).map(preset => (
              <button key={preset} type="button"
                onClick={() => setRuleForm(p => ({ ...p, ...RULE_PRESETS[preset] }))}
                className="text-xs px-2 py-1 border border-border rounded text-gray-400 hover:border-accent hover:text-accent">
                {preset}
              </button>
            ))}
          </div>
        </div>
        <p className="text-xs text-gray-500">Controller max current is hard-capped at 220 A in analysis regardless of this setting.</p>

        <div className="grid grid-cols-2 gap-3">
          {([
            ['controller_max_current_a', 'Max Controller Current (A)',  'number', '1'],
            ['speed_limit_kmh',          'Speed Limit (km/h)',           'number', '0.1'],
            ['battery_voltage_max_v',    'Battery Voltage Max (V)',      'number', '0.1'],
            ['battery_voltage_min_v',    'Battery Voltage Min (V)',      'number', '0.1'],
            ['battery_voltage_nominal_v','Battery Voltage Nominal (V)',  'number', '0.1'],
            ['battery_capacity_wh',      'Battery Capacity (Wh)',        'number', '1'],
            ['combined_min_weight_kg',   'Min Combined Weight kg (driver+kart)', 'number', '0.1'],
          ] as [keyof Rules, string, string, string][]).map(([key, label, type, step]) => (
            <div key={key}>
              <label className="block text-xs text-gray-400 mb-1">{label}</label>
              <input type={type} step={step} value={ruleForm[key] ?? ''}
                onChange={rf(key)}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            </div>
          ))}
          <div>
            <label className="block text-xs text-gray-400 mb-1">Rulebook Version</label>
            <input value={ruleForm.rulebook_version ?? ''} onChange={rf('rulebook_version')}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button type="submit" className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">Save Rules</button>
          {ruleSaved && <span className="text-green text-sm">Saved!</span>}
        </div>
      </form>

      {/* Alltrax Controller Settings */}
      {karts.length > 0 && (
        <form onSubmit={saveAlltrax} className="bg-surface border border-border rounded-lg p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Alltrax Controller — Per Kart</h2>
            <select value={kartId ?? ''} onChange={e => selectKart(Number(e.target.value))}
              className="bg-bg border border-border rounded px-2 py-1 text-white text-sm focus:outline-none focus:border-accent">
              {karts.map(k => <option key={k.id} value={k.id}>{k.name}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {/* Max Current */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">
                Max Current (A) <span className="text-orange">≤ 220 HSGP limit</span>
              </label>
              <input type="number" min={1} max={220} step={1} value={ax.max_current}
                onChange={e => axf('max_current', Math.min(220, parseInt(e.target.value) || 0))}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            </div>

            {/* Speed Limit % */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Speed Limit (%)</label>
              <input type="number" min={0} max={100} step={1} value={ax.speed_limit}
                onChange={e => axf('speed_limit', parseInt(e.target.value) || 0)}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            </div>

            {/* Accel Rate */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Accel Rate (1–255) — higher = faster ramp</label>
              <div className="flex gap-2 items-center">
                <input type="range" min={1} max={255} value={ax.accel_rate}
                  onChange={e => axf('accel_rate', parseInt(e.target.value))}
                  className="flex-1 accent-[var(--color-accent)]" />
                <span className="text-white font-mono text-sm w-8">{ax.accel_rate}</span>
              </div>
            </div>

            {/* Decel Rate */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Decel / Plug Brake Rate (1–255)</label>
              <div className="flex gap-2 items-center">
                <input type="range" min={1} max={255} value={ax.decel_rate}
                  onChange={e => axf('decel_rate', parseInt(e.target.value))}
                  className="flex-1 accent-[var(--color-accent)]" />
                <span className="text-white font-mono text-sm w-8">{ax.decel_rate}</span>
              </div>
            </div>

            {/* Lo Voltage Cutoff */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Low Voltage Cutoff (V)</label>
              <input type="number" step={0.1} value={ax.lo_voltage_cutoff}
                onChange={e => axf('lo_voltage_cutoff', parseFloat(e.target.value) || 0)}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            </div>

            {/* Hi Voltage Cutoff */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">High Voltage Cutoff (V)</label>
              <input type="number" step={0.1} value={ax.hi_voltage_cutoff}
                onChange={e => axf('hi_voltage_cutoff', parseFloat(e.target.value) || 0)}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            </div>

            {/* Throttle Deadband */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Throttle Deadband (0–255 ADC counts)</label>
              <input type="number" min={0} max={255} step={1} value={ax.throttle_deadband}
                onChange={e => axf('throttle_deadband', parseInt(e.target.value) || 0)}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            </div>

            {/* Regen intensity */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Regen Intensity (%) {!ax.regen_braking && <span className="text-gray-600">(regen off)</span>}</label>
              <div className="flex gap-2 items-center">
                <input type="range" min={0} max={100} value={ax.regen_intensity} disabled={!ax.regen_braking}
                  onChange={e => axf('regen_intensity', parseInt(e.target.value))}
                  className="flex-1 accent-[var(--color-accent)] disabled:opacity-40" />
                <span className="text-white font-mono text-sm w-8">{ax.regen_intensity}</span>
              </div>
            </div>
          </div>

          {/* Toggles */}
          <div className="flex gap-6">
            {([
              ['peak_amp_mode', 'Peak Amp Mode'],
              ['regen_braking', 'Regen Braking'],
            ] as [keyof AlltraxSettings, string][]).map(([k, label]) => (
              <label key={k} className="flex items-center gap-2 cursor-pointer">
                <div
                  onClick={() => axf(k as any, !ax[k])}
                  className={`w-10 h-5 rounded-full transition-colors ${ax[k] ? 'bg-accent' : 'bg-border'} relative`}>
                  <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${ax[k] ? 'translate-x-5' : 'translate-x-0.5'}`} />
                </div>
                <span className="text-sm text-gray-300">{label}</span>
              </label>
            ))}
          </div>

          {/* Throttle Curve */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-gray-400">Throttle Curve — output % at each 10% throttle input</label>
              <div className="flex gap-1">
                {Object.keys(THROTTLE_PRESETS).map(name => (
                  <button key={name} type="button"
                    onClick={() => axf('throttle_curve', [...THROTTLE_PRESETS[name]])}
                    className="text-xs px-2 py-0.5 border border-border rounded text-gray-400 hover:border-accent hover:text-accent">
                    {name}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-11 gap-1">
              {ax.throttle_curve.map((val, i) => (
                <div key={i} className="text-center">
                  <input
                    type="number" min={0} max={100} step={1}
                    value={val}
                    onChange={e => {
                      const curve = [...ax.throttle_curve]
                      curve[i] = Math.min(100, Math.max(0, parseInt(e.target.value) || 0))
                      axf('throttle_curve', curve)
                    }}
                    className="w-full bg-bg border border-border rounded px-1 py-1 text-white text-xs text-center focus:outline-none focus:border-accent"
                  />
                  <div className="text-gray-600 text-xs mt-0.5">{i * 10}%</div>
                </div>
              ))}
            </div>
            {/* Mini bar chart preview */}
            <div className="flex items-end gap-0.5 h-12 mt-2">
              {ax.throttle_curve.map((val, i) => (
                <div key={i} className="flex-1 bg-accent rounded-t opacity-70" style={{ height: `${val}%` }} />
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button type="submit" className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">
              Save Controller Settings
            </button>
            {axSaved && <span className="text-green text-sm">Saved!</span>}
          </div>
        </form>
      )}

      {/* Archive Backend */}
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
