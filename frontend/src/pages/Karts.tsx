import { useEffect, useState, FormEvent } from 'react'
import { api, Kart } from '../api'

interface AlltraxSettings {
  max_current: number
  accel_rate: number
  throttle_map: number
  regen_current: number
  speed_limit_pct: number
  boost_enabled: boolean
}

const DEFAULT_ALLTRAX: AlltraxSettings = {
  max_current: 180,
  accel_rate: 64,
  throttle_map: 1,
  regen_current: 0,
  speed_limit_pct: 100,
  boost_enabled: false,
}

interface GearConfig {
  motor_sprocket_teeth: number
  axle_sprocket_teeth: number
}

const DEFAULT_GEAR: GearConfig = {
  motor_sprocket_teeth: 12,
  axle_sprocket_teeth: 60,
}

function parseSettings(json: string | undefined): AlltraxSettings {
  try { return { ...DEFAULT_ALLTRAX, ...JSON.parse(json || '{}') } } catch { return DEFAULT_ALLTRAX }
}

function parseGear(json: string | undefined): GearConfig {
  try { return { ...DEFAULT_GEAR, ...JSON.parse(json || '{}') } } catch { return DEFAULT_GEAR }
}

export default function Karts() {
  const [karts, setKarts]           = useState<Kart[]>([])
  const [selected, setSelected]     = useState<Kart | null>(null)
  const [settings, setSettings]     = useState<AlltraxSettings>(DEFAULT_ALLTRAX)
  const [gear, setGear]             = useState<GearConfig>(DEFAULT_GEAR)
  const [form, setForm]             = useState({ name: '', motor_type: 'DC Series', battery_type: 'LiFePO4', mass_lbs: '253.5' })
  const [error, setError]           = useState('')
  const [settingsMsg, setSettingsMsg] = useState('')

  const load = () => api.get<Kart[]>('/karts').then(setKarts).catch(() => {})
  useEffect(() => { load() }, [])

  const selectKart = (k: Kart) => {
    setSelected(k)
    setSettings(parseSettings(k.settings_json))
    setGear(parseGear(k.gear_json))
    setSettingsMsg('')
  }

  const create = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    try {
      const mass_kg = parseFloat(form.mass_lbs) / 2.20462
      await api.post('/karts', {
        name: form.name, motor_type: form.motor_type,
        battery_type: form.battery_type, mass_kg,
        settings_json: JSON.stringify(DEFAULT_ALLTRAX),
        gear_json: JSON.stringify(DEFAULT_GEAR),
      })
      setForm({ name: '', motor_type: 'DC Series', battery_type: 'LiFePO4', mass_lbs: '253.5' })
      load()
    } catch (err: any) { setError(err.message) }
  }

  const saveSettings = async () => {
    if (!selected) return
    setSettingsMsg('')
    try {
      await api.put(`/karts/${selected.id}`, {
        settings_json: JSON.stringify(settings),
        gear_json: JSON.stringify(gear),
      })
      setSettingsMsg('Saved!')
      load()
    } catch (err: any) { setSettingsMsg(`Error: ${err.message}`) }
  }

  const del = async (id: number) => {
    if (!confirm('Delete kart?')) return
    try { await api.delete(`/karts/${id}`); if (selected?.id === id) setSelected(null); load() }
    catch (err: any) { alert(err.message) }
  }

  const f = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(prev => ({ ...prev, [k]: e.target.value }))

  const sF = (k: keyof AlltraxSettings) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.type === 'checkbox' ? e.target.checked : (e.target.type === 'number' ? parseFloat(e.target.value) : e.target.value)
    setSettings(prev => ({ ...prev, [k]: val }))
  }

  const gF = (k: keyof GearConfig) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setGear(prev => ({ ...prev, [k]: parseInt(e.target.value) }))

  const gearRatio = gear.axle_sprocket_teeth / Math.max(gear.motor_sprocket_teeth, 1)

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Karts</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: list + add form */}
        <div className="space-y-4">
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
              <label className="block text-xs text-gray-400 mb-1">Kart Mass (lbs, without driver)</label>
              <input type="number" step="0.5" value={form.mass_lbs} onChange={f('mass_lbs')}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
              <div className="text-xs text-gray-500 mt-1">{(parseFloat(form.mass_lbs || '0') / 2.20462).toFixed(1)} kg</div>
            </div>
            <button type="submit" className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">
              Add Kart
            </button>
          </form>

          <div className="space-y-2">
            {karts.map(k => (
              <div key={k.id}
                onClick={() => selectKart(k)}
                className={`flex items-center gap-4 rounded-lg border px-4 py-3 cursor-pointer transition-colors ${selected?.id === k.id ? 'border-accent bg-accent bg-opacity-5' : 'border-border bg-surface hover:border-accent'}`}>
                <div className="flex-1 min-w-0">
                  <div className="text-white font-medium">{k.name}</div>
                  <div className="text-xs text-gray-400">{k.motor_type} · {k.battery_type} · {(k.mass_kg * 2.20462).toFixed(0)} lbs</div>
                </div>
                <button onClick={e => { e.stopPropagation(); del(k.id) }}
                  className="text-xs text-gray-500 hover:text-red transition-colors shrink-0">
                  Delete
                </button>
              </div>
            ))}
            {karts.length === 0 && <p className="text-gray-400 text-sm">No karts yet.</p>}
          </div>
        </div>

        {/* Right: Alltrax settings panel */}
        {selected ? (
          <div className="lg:col-span-2 space-y-4">
            <div className="bg-surface border border-border rounded-lg p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">
                  Alltrax SR Controller — {selected.name}
                </h2>
                <div className="flex items-center gap-3">
                  {settingsMsg && (
                    <span className={`text-xs ${settingsMsg.startsWith('Error') ? 'text-red' : 'text-accent'}`}>
                      {settingsMsg}
                    </span>
                  )}
                  <button onClick={saveSettings}
                    className="px-4 py-1.5 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">
                    Save Settings
                  </button>
                </div>
              </div>

              {/* Max Current */}
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold text-gray-300 uppercase tracking-wider">Max Current (A)</label>
                  <span className="text-accent font-mono text-sm font-bold">{settings.max_current}A</span>
                </div>
                <input type="range" min={50} max={220} step={5} value={settings.max_current}
                  onChange={sF('max_current')} className="w-full accent-accent" />
                <div className="flex justify-between text-xs text-gray-500">
                  <span>50A (economy)</span>
                  <span className="text-orange">220A hard limit (EVGP)</span>
                </div>
                <p className="text-xs text-gray-500">Controls peak torque delivery — higher = faster acceleration but more battery draw.</p>
              </div>

              {/* Accel Rate */}
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold text-gray-300 uppercase tracking-wider">Acceleration Rate</label>
                  <span className="text-accent font-mono text-sm font-bold">{settings.accel_rate}</span>
                </div>
                <input type="range" min={1} max={255} step={1} value={settings.accel_rate}
                  onChange={sF('accel_rate')} className="w-full accent-accent" />
                <div className="flex justify-between text-xs text-gray-500">
                  <span>1 (aggressive ramp)</span>
                  <span>255 (soft ramp)</span>
                </div>
                <p className="text-xs text-gray-500">Controls how fast the controller ramps current up from 0. Lower = more aggressive torque hit.</p>
              </div>

              {/* Throttle Map */}
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold text-gray-300 uppercase tracking-wider">Throttle Map</label>
                  <span className="text-accent font-mono text-sm font-bold">Map {settings.throttle_map}</span>
                </div>
                <input type="range" min={1} max={5} step={1} value={settings.throttle_map}
                  onChange={sF('throttle_map')} className="w-full accent-accent" />
                <div className="flex justify-between text-xs text-gray-500">
                  <span>1 (linear)</span>
                  <span>5 (exponential)</span>
                </div>
                <p className="text-xs text-gray-500">Throttle pedal response curve. Map 1 = linear (predictable). Map 5 = top-end biased.</p>
              </div>

              {/* Regen Current */}
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold text-gray-300 uppercase tracking-wider">Regen Braking (A)</label>
                  <span className="text-accent font-mono text-sm font-bold">{settings.regen_current}A</span>
                </div>
                <input type="range" min={0} max={80} step={5} value={settings.regen_current}
                  onChange={sF('regen_current')} className="w-full accent-accent" />
                <div className="flex justify-between text-xs text-gray-500">
                  <span>0 (no regen)</span>
                  <span>80A (strong regen)</span>
                </div>
                <p className="text-xs text-gray-500">Regenerative braking on throttle lift. Higher = more drag / energy recovery.</p>
              </div>

              {/* Speed Limit */}
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold text-gray-300 uppercase tracking-wider">Speed Limit %</label>
                  <span className="text-accent font-mono text-sm font-bold">{settings.speed_limit_pct}%</span>
                </div>
                <input type="range" min={10} max={100} step={5} value={settings.speed_limit_pct}
                  onChange={sF('speed_limit_pct')} className="w-full accent-accent" />
                <div className="flex justify-between text-xs text-gray-500">
                  <span>10% (slow)</span>
                  <span>100% (unlimited)</span>
                </div>
              </div>

              {/* Boost */}
              <div className="flex items-center justify-between py-2 border-t border-border">
                <div>
                  <div className="text-xs font-bold text-gray-300 uppercase tracking-wider">Boost Mode</div>
                  <div className="text-xs text-gray-500">Temporarily exceed max current limit (subject to rules)</div>
                </div>
                <input type="checkbox" checked={settings.boost_enabled}
                  onChange={sF('boost_enabled')}
                  className="w-5 h-5 accent-accent cursor-pointer" />
              </div>
            </div>

            {/* Gear Ratio */}
            <div className="bg-surface border border-border rounded-lg p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Gear Ratio</h2>
                <div className="text-right">
                  <div className="text-accent font-mono font-bold">{gearRatio.toFixed(2)}:1</div>
                  <div className="text-xs text-gray-500">{gear.axle_sprocket_teeth}T ÷ {gear.motor_sprocket_teeth}T</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs text-gray-400">Motor Sprocket (teeth)</label>
                  <input type="number" min={8} max={30} value={gear.motor_sprocket_teeth}
                    onChange={gF('motor_sprocket_teeth')}
                    className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-gray-400">Axle Sprocket (teeth)</label>
                  <input type="number" min={30} max={120} value={gear.axle_sprocket_teeth}
                    onChange={gF('axle_sprocket_teeth')}
                    className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
                </div>
              </div>
              <p className="text-xs text-gray-500">
                Higher ratio = more torque / lower top speed. Typical EVGP range: 5:1 – 9:1.
                Current: <span className="text-white font-mono">{gearRatio.toFixed(2)}:1</span>
              </p>
            </div>
          </div>
        ) : (
          <div className="lg:col-span-2 flex items-center justify-center bg-surface border border-border rounded-lg min-h-[200px]">
            <p className="text-gray-500 text-sm">Select a kart to edit its Alltrax controller settings</p>
          </div>
        )}
      </div>
    </div>
  )
}
