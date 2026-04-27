import { useEffect, useState, FormEvent } from 'react'
import { api } from '../api'

// ── Types ─────────────────────────────────────────────────────────────────────

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

interface MapSettings {
  max_current:       number  // 1–220 A
  accel_rate:        number  // 1–255
  decel_rate:        number  // 1–255
  speed_limit:       number  // 0–100 %
  throttle_deadband: number  // 0–255 ADC
  neutral_braking:   number  // 0–255
}

interface TirePSI {
  fl_cold: number; fl_hot: number
  fr_cold: number; fr_hot: number
  rl_cold: number; rl_hot: number
  rr_cold: number; rr_hot: number
}

interface AlltraxSettings {
  maps:              [MapSettings, MapSettings, MapSettings]
  active_map:        number
  lo_voltage_cutoff: number
  hi_voltage_cutoff: number
  peak_amp_mode:     boolean
  regen_braking:     boolean
  regen_intensity:   number
  throttle_curve:    number[]
  tire_psi:          TirePSI
}

interface Kart { id: number; name: string; settings_json: string; gear_json: string }

// ── Defaults / Presets ────────────────────────────────────────────────────────

const DEFAULT_MAP: MapSettings = {
  max_current: 180, accel_rate: 64, decel_rate: 64,
  speed_limit: 100, throttle_deadband: 10, neutral_braking: 0,
}

const DEFAULT_TIRE: TirePSI = {
  fl_cold: 12, fl_hot: 14, fr_cold: 12, fr_hot: 14,
  rl_cold: 12, rl_hot: 14, rr_cold: 12, rr_hot: 14,
}

const DEFAULT_ALLTRAX: AlltraxSettings = {
  maps: [
    { ...DEFAULT_MAP },
    { max_current: 150, accel_rate: 40, decel_rate: 64, speed_limit: 80, throttle_deadband: 10, neutral_braking: 0 },
    { max_current: 100, accel_rate: 20, decel_rate: 128, speed_limit: 60, throttle_deadband: 10, neutral_braking: 0 },
  ],
  active_map: 0,
  lo_voltage_cutoff: 42.0,
  hi_voltage_cutoff: 58.4,
  peak_amp_mode: true,
  regen_braking: false,
  regen_intensity: 40,
  throttle_curve: [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
  tire_psi: { ...DEFAULT_TIRE },
}

const THROTTLE_PRESETS: Record<string, number[]> = {
  'Linear':      [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
  'Aggressive':  [0, 20, 37, 52, 64, 74, 82, 89, 95, 98, 100],
  'Soft S':      [0,  2,  8, 18, 32, 50, 68, 82, 92, 98, 100],
  'Late Apex':   [0,  5, 11, 18, 27, 38, 52, 68, 82, 93, 100],
}

const MAP_LABELS = ['Map 1 — Race', 'Map 2 — Practice', 'Map 3 — Safe']

const RULE_PRESETS: Record<string, Partial<Rules>> = {
  'Purdue HSGP 2025-26': {
    controller_max_current_a: 220, battery_voltage_nominal_v: 51.2,
    battery_voltage_max_v: 58.4,  battery_voltage_min_v: 40.0,
    battery_capacity_wh: 3072,    speed_limit_kmh: 80,
    combined_min_weight_kg: 181.4, rulebook_version: 'Purdue HSGP 2025-26',
  },
  'EVGP 2025-26': {
    controller_max_current_a: 220, battery_voltage_nominal_v: 51.2,
    battery_voltage_max_v: 58.4,  battery_voltage_min_v: 40.0,
    battery_capacity_wh: 3072,    speed_limit_kmh: 80,
    combined_min_weight_kg: 181.4, rulebook_version: 'EVGP 2025-26',
  },
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function parseAlltrax(json: string): AlltraxSettings {
  try {
    const raw = JSON.parse(json || '{}')
    // Migrate old flat structure → new maps structure
    if (!raw.maps) {
      const legacy: MapSettings = {
        max_current:       raw.max_current       ?? DEFAULT_MAP.max_current,
        accel_rate:        raw.accel_rate         ?? DEFAULT_MAP.accel_rate,
        decel_rate:        raw.decel_rate         ?? DEFAULT_MAP.decel_rate,
        speed_limit:       raw.speed_limit        ?? DEFAULT_MAP.speed_limit,
        throttle_deadband: raw.throttle_deadband  ?? DEFAULT_MAP.throttle_deadband,
        neutral_braking:   raw.neutral_braking    ?? DEFAULT_MAP.neutral_braking,
      }
      return {
        ...DEFAULT_ALLTRAX,
        maps: [legacy, { ...DEFAULT_ALLTRAX.maps[1] }, { ...DEFAULT_ALLTRAX.maps[2] }],
        lo_voltage_cutoff: raw.lo_voltage_cutoff ?? DEFAULT_ALLTRAX.lo_voltage_cutoff,
        hi_voltage_cutoff: raw.hi_voltage_cutoff ?? DEFAULT_ALLTRAX.hi_voltage_cutoff,
        peak_amp_mode:     raw.peak_amp_mode     ?? DEFAULT_ALLTRAX.peak_amp_mode,
        regen_braking:     raw.regen_braking     ?? DEFAULT_ALLTRAX.regen_braking,
        regen_intensity:   raw.regen_intensity   ?? DEFAULT_ALLTRAX.regen_intensity,
        throttle_curve:    raw.throttle_curve    ?? DEFAULT_ALLTRAX.throttle_curve,
        tire_psi:          raw.tire_psi          ?? { ...DEFAULT_TIRE },
      }
    }
    return { ...DEFAULT_ALLTRAX, ...raw, tire_psi: { ...DEFAULT_TIRE, ...(raw.tire_psi ?? {}) } }
  } catch { return { ...DEFAULT_ALLTRAX } }
}

// km/h ↔ mph conversions for display (rules stored internally in km/h)
const kmhToMph = (k: number) => +(k * 0.621371).toFixed(1)
const mphToKmh = (m: number) => +(m / 0.621371).toFixed(2)
// kg ↔ lbs conversions for display (rules stored internally in kg)
const kgToLbs  = (k: number) => +(k * 2.20462).toFixed(1)
const lbsToKg  = (l: number) => +(l / 2.20462).toFixed(2)

// ── Sub-components ────────────────────────────────────────────────────────────

function SliderRow({ label, min, max, value, onChange, unit = '' }: {
  label: string; min: number; max: number; value: number
  onChange: (v: number) => void; unit?: string
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs text-gray-400">{label}</label>
        <span className="text-white font-mono text-sm font-bold">{value}{unit}</span>
      </div>
      <input type="range" min={min} max={max} value={value}
        onChange={e => onChange(parseInt(e.target.value))}
        className="w-full accent-[var(--color-accent)]" />
      <div className="flex justify-between text-gray-600 text-xs mt-0.5">
        <span>{min}</span><span>{max}</span>
      </div>
    </div>
  )
}

function Toggle({ label, value, onChange, note }: {
  label: string; value: boolean; onChange: (v: boolean) => void; note?: string
}) {
  return (
    <label className="flex items-center gap-3 cursor-pointer">
      <div onClick={() => onChange(!value)}
        className={`w-10 h-5 rounded-full transition-colors relative shrink-0 ${value ? 'bg-accent' : 'bg-border'}`}>
        <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${value ? 'translate-x-5' : 'translate-x-0.5'}`} />
      </div>
      <div>
        <span className="text-sm text-gray-300">{label}</span>
        {note && <span className="text-xs text-gray-500 ml-2">{note}</span>}
      </div>
    </label>
  )
}

function NumberInput({ label, value, onChange, min, max, step = 1, unit = '' }: {
  label: string; value: number; onChange: (v: number) => void
  min?: number; max?: number; step?: number; unit?: string
}) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}{unit && <span className="ml-1 text-gray-600">({unit})</span>}</label>
      <input type="number" min={min} max={max} step={step} value={value}
        onChange={e => {
          let v = parseFloat(e.target.value) || 0
          if (min !== undefined) v = Math.max(min, v)
          if (max !== undefined) v = Math.min(max, v)
          onChange(v)
        }}
        className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm" />
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function Settings() {
  const [rules, setRules]         = useState<Rules | null>(null)
  const [ruleForm, setRuleForm]   = useState<Partial<Rules>>({})
  const [ruleSaved, setRuleSaved] = useState(false)

  const [karts, setKarts]         = useState<Kart[]>([])
  const [kartId, setKartId]       = useState<number | null>(null)
  const [ax, setAx]               = useState<AlltraxSettings>({ ...DEFAULT_ALLTRAX })
  const [axSaved, setAxSaved]     = useState(false)
  const [activeMap, setActiveMap] = useState(0)

  const [version, setVersion] = useState('')

  // US-unit display state for rules (edit in mph/lbs, save back to km/h/kg)
  const [speedMph,   setSpeedMph]   = useState('')
  const [weightLbs,  setWeightLbs]  = useState('')

  useEffect(() => {
    api.get<Rules>('/compliance/rules').then(r => {
      setRules(r)
      setRuleForm(r)
      setSpeedMph(String(kmhToMph(r.speed_limit_kmh)))
      setWeightLbs(String(kgToLbs(r.combined_min_weight_kg)))
    }).catch(() => {})
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
    const payload = {
      ...ruleForm,
      speed_limit_kmh:      mphToKmh(parseFloat(speedMph) || 0),
      combined_min_weight_kg: lbsToKg(parseFloat(weightLbs) || 0),
    }
    try {
      await api.put('/compliance/rules', payload)
      setRuleSaved(true); setTimeout(() => setRuleSaved(false), 2500)
    } catch (err: any) { alert(err.message) }
  }

  const saveAlltrax = async (e: FormEvent) => {
    e.preventDefault()
    if (!kartId) return
    const payload = { ...ax, active_map: activeMap }
    try {
      await api.put(`/karts/${kartId}`, { settings_json: JSON.stringify(payload) })
      setAxSaved(true); setTimeout(() => setAxSaved(false), 2500)
    } catch (err: any) { alert(err.message) }
  }

  const setMap = (idx: number, patch: Partial<MapSettings>) =>
    setAx(prev => {
      const maps = [...prev.maps] as [MapSettings, MapSettings, MapSettings]
      maps[idx] = { ...maps[idx], ...patch }
      return { ...prev, maps }
    })

  const setPSI = (patch: Partial<TirePSI>) =>
    setAx(prev => ({ ...prev, tire_psi: { ...prev.tire_psi, ...patch } }))

  const rf = (k: keyof Rules) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setRuleForm(p => ({ ...p, [k]: e.target.type === 'number' ? parseFloat(e.target.value) : e.target.value }))

  if (!rules) return <div className="text-gray-400 p-4">Loading...</div>

  const m = ax.maps[activeMap]

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      {/* System */}
      <div className="bg-surface border border-border rounded-lg p-4 flex items-center justify-between">
        <span className="text-xs text-gray-400 uppercase tracking-wider">STRAT-OS Version</span>
        <span className="text-white font-mono font-bold">{version}</span>
      </div>

      {/* ── Competition Rules ──────────────────────────────────────────────── */}
      <form onSubmit={saveRules} className="bg-surface border border-border rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Competition Rules</h2>
          <div className="flex gap-2 flex-wrap">
            {Object.keys(RULE_PRESETS).map(preset => (
              <button key={preset} type="button"
                onClick={() => {
                  const p = RULE_PRESETS[preset]
                  setRuleForm(prev => ({ ...prev, ...p }))
                  if (p.speed_limit_kmh)      setSpeedMph(String(kmhToMph(p.speed_limit_kmh)))
                  if (p.combined_min_weight_kg) setWeightLbs(String(kgToLbs(p.combined_min_weight_kg)))
                }}
                className="text-xs px-2 py-1 border border-border rounded text-gray-400 hover:border-accent hover:text-accent">
                {preset}
              </button>
            ))}
          </div>
        </div>
        <p className="text-xs text-gray-500">Controller max current is hard-capped at 220 A in all analysis regardless of this setting.</p>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Max Controller Current (A)</label>
            <input type="number" step="1" value={ruleForm.controller_max_current_a ?? ''}
              onChange={rf('controller_max_current_a')}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Speed Limit (mph)</label>
            <input type="number" step="0.1" value={speedMph}
              onChange={e => setSpeedMph(e.target.value)}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Battery Voltage Max (V)</label>
            <input type="number" step="0.1" value={ruleForm.battery_voltage_max_v ?? ''}
              onChange={rf('battery_voltage_max_v')}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Battery Voltage Min (V)</label>
            <input type="number" step="0.1" value={ruleForm.battery_voltage_min_v ?? ''}
              onChange={rf('battery_voltage_min_v')}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Battery Voltage Nominal (V)</label>
            <input type="number" step="0.1" value={ruleForm.battery_voltage_nominal_v ?? ''}
              onChange={rf('battery_voltage_nominal_v')}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Battery Capacity (Wh)</label>
            <input type="number" step="1" value={ruleForm.battery_capacity_wh ?? ''}
              onChange={rf('battery_capacity_wh')}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Min Combined Weight (lbs, driver+kart)</label>
            <input type="number" step="0.1" value={weightLbs}
              onChange={e => setWeightLbs(e.target.value)}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Rulebook Version</label>
            <input value={ruleForm.rulebook_version ?? ''} onChange={rf('rulebook_version')}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm" />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button type="submit" className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">Save Rules</button>
          {ruleSaved && <span className="text-green text-sm font-medium">Saved!</span>}
        </div>
      </form>

      {/* ── Alltrax Controller ─────────────────────────────────────────────── */}
      {karts.length > 0 && (
        <form onSubmit={saveAlltrax} className="bg-surface border border-border rounded-lg p-4 space-y-5">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Alltrax SR/SPM Controller</h2>
              <p className="text-xs text-gray-500 mt-0.5">3 programmable maps — match the real Alltrax PC utility</p>
            </div>
            <select value={kartId ?? ''} onChange={e => selectKart(Number(e.target.value))}
              className="bg-bg border border-border rounded px-2 py-1 text-white text-sm focus:outline-none focus:border-accent">
              {karts.map(k => <option key={k.id} value={k.id}>{k.name}</option>)}
            </select>
          </div>

          {/* Map tabs */}
          <div className="flex gap-0 border-b border-border">
            {MAP_LABELS.map((label, i) => (
              <button key={i} type="button" onClick={() => setActiveMap(i)}
                className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                  activeMap === i
                    ? 'border-accent text-accent'
                    : 'border-transparent text-gray-400 hover:text-white'
                }`}>
                {label}
                {ax.active_map === i && (
                  <span className="ml-1.5 text-xs bg-accent text-bg rounded px-1 py-0.5 font-bold">ACTIVE</span>
                )}
              </button>
            ))}
          </div>

          {/* Active map badge control */}
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400">Controller active map:</span>
            {MAP_LABELS.map((label, i) => (
              <button key={i} type="button"
                onClick={() => setAx(prev => ({ ...prev, active_map: i }))}
                className={`text-xs px-3 py-1 rounded border transition-colors ${
                  ax.active_map === i
                    ? 'bg-accent text-bg border-accent font-bold'
                    : 'border-border text-gray-400 hover:border-accent hover:text-accent'
                }`}>
                Map {i + 1}
              </button>
            ))}
          </div>

          {/* ── Per-map parameters ─── */}
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              {/* Max Current */}
              <div className="col-span-2 md:col-span-1">
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-gray-400">
                    Max Current (A) <span className="text-orange font-bold">≤ 220 A HSGP limit</span>
                  </label>
                  <span className="font-mono font-bold text-white text-sm">{m.max_current} A</span>
                </div>
                <input type="range" min={1} max={220} value={m.max_current}
                  onChange={e => setMap(activeMap, { max_current: Math.min(220, parseInt(e.target.value)) })}
                  className="w-full accent-[var(--color-accent)]" />
                <div className="flex justify-between text-gray-600 text-xs mt-0.5"><span>1 A</span><span>220 A</span></div>
                <div className="mt-1">
                  <input type="number" min={1} max={220} value={m.max_current}
                    onChange={e => setMap(activeMap, { max_current: Math.min(220, parseInt(e.target.value) || 1) })}
                    className="w-24 bg-bg border border-border rounded px-2 py-1 text-white focus:outline-none focus:border-accent text-sm text-right" />
                </div>
              </div>

              {/* Speed Limit */}
              <div className="col-span-2 md:col-span-1">
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-gray-400">Speed Limit (%)</label>
                  <span className="font-mono font-bold text-white text-sm">{m.speed_limit}%</span>
                </div>
                <input type="range" min={0} max={100} value={m.speed_limit}
                  onChange={e => setMap(activeMap, { speed_limit: parseInt(e.target.value) })}
                  className="w-full accent-[var(--color-accent)]" />
                <div className="flex justify-between text-gray-600 text-xs mt-0.5"><span>0%</span><span>100%</span></div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <SliderRow label="Accel Rate — higher = faster ramp (1–255)"
                min={1} max={255} value={m.accel_rate}
                onChange={v => setMap(activeMap, { accel_rate: v })} />
              <SliderRow label="Decel / Plug Brake Rate (1–255)"
                min={1} max={255} value={m.decel_rate}
                onChange={v => setMap(activeMap, { decel_rate: v })} />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <SliderRow label="Throttle Deadband — ADC counts before motor engages (0–255)"
                  min={0} max={255} value={m.throttle_deadband}
                  onChange={v => setMap(activeMap, { throttle_deadband: v })} />
              </div>
              <div>
                <SliderRow label="Neutral Braking — holding torque at zero throttle (0–255)"
                  min={0} max={255} value={m.neutral_braking}
                  onChange={v => setMap(activeMap, { neutral_braking: v })} />
              </div>
            </div>

            {/* Map summary card */}
            <div className="bg-bg border border-border rounded p-3 grid grid-cols-3 md:grid-cols-6 gap-3 text-center text-xs">
              {[
                ['Max Current', `${m.max_current} A`],
                ['Speed Limit', `${m.speed_limit}%`],
                ['Accel Rate', String(m.accel_rate)],
                ['Decel Rate', String(m.decel_rate)],
                ['Deadband', String(m.throttle_deadband)],
                ['Neutral Brk', String(m.neutral_braking)],
              ].map(([label, val]) => (
                <div key={label}>
                  <div className="text-gray-500">{label}</div>
                  <div className="text-white font-mono font-bold mt-0.5">{val}</div>
                </div>
              ))}
            </div>
          </div>

          {/* ── Global Settings ─── */}
          <div className="border-t border-border pt-4 space-y-4">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Global Controller Settings</h3>

            <div className="grid grid-cols-2 gap-3">
              <NumberInput label="Low Voltage Cutoff" unit="V" value={ax.lo_voltage_cutoff} step={0.1}
                onChange={v => setAx(p => ({ ...p, lo_voltage_cutoff: v }))} />
              <NumberInput label="High Voltage Cutoff" unit="V" value={ax.hi_voltage_cutoff} step={0.1}
                onChange={v => setAx(p => ({ ...p, hi_voltage_cutoff: v }))} />
            </div>

            <div className="flex flex-wrap gap-6">
              <Toggle label="Peak Amp Mode"
                note="Allows brief current bursts above continuous rating"
                value={ax.peak_amp_mode}
                onChange={v => setAx(p => ({ ...p, peak_amp_mode: v }))} />
              <Toggle label="Regen Braking"
                note="Converts braking energy back to battery"
                value={ax.regen_braking}
                onChange={v => setAx(p => ({ ...p, regen_braking: v }))} />
            </div>

            {ax.regen_braking && (
              <SliderRow label="Regen Intensity (%)"
                min={0} max={100} value={ax.regen_intensity} unit="%"
                onChange={v => setAx(p => ({ ...p, regen_intensity: v }))} />
            )}
          </div>

          {/* ── Throttle Curve ─── */}
          <div className="border-t border-border pt-4 space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Throttle Curve</h3>
              <div className="flex gap-1 flex-wrap">
                {Object.keys(THROTTLE_PRESETS).map(name => (
                  <button key={name} type="button"
                    onClick={() => setAx(p => ({ ...p, throttle_curve: [...THROTTLE_PRESETS[name]] }))}
                    className="text-xs px-2 py-0.5 border border-border rounded text-gray-400 hover:border-accent hover:text-accent">
                    {name}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-xs text-gray-500">Output % at each 10% throttle input. Point 0 = 0% throttle (must be 0), point 10 = full throttle (must be 100).</p>

            <div className="grid grid-cols-11 gap-1">
              {ax.throttle_curve.map((val, i) => (
                <div key={i} className="text-center">
                  <input type="number" min={0} max={100} step={1} value={val}
                    onChange={e => {
                      const curve = [...ax.throttle_curve]
                      curve[i] = Math.min(100, Math.max(0, parseInt(e.target.value) || 0))
                      setAx(p => ({ ...p, throttle_curve: curve }))
                    }}
                    className="w-full bg-bg border border-border rounded px-1 py-1 text-white text-xs text-center focus:outline-none focus:border-accent" />
                  <div className="text-gray-600 text-xs mt-0.5">{i * 10}%</div>
                </div>
              ))}
            </div>
            <div className="flex items-end gap-0.5 h-14 mt-1 bg-bg rounded border border-border px-1 pt-1">
              {ax.throttle_curve.map((val, i) => (
                <div key={i} className="flex-1 rounded-t transition-all" style={{ height: `${val}%`, background: `hsl(${160 - val * 1.2}, 80%, 55%)` }} />
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3 border-t border-border pt-4">
            <button type="submit" className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">
              Save Controller Settings
            </button>
            {axSaved && <span className="text-green text-sm font-medium">Saved!</span>}
          </div>
        </form>
      )}

      {/* ── Tire PSI ──────────────────────────────────────────────────────── */}
      {karts.length > 0 && (
        <div className="bg-surface border border-border rounded-lg p-4 space-y-4">
          <div>
            <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Tire Pressure</h2>
            <p className="text-xs text-gray-500 mt-0.5">Target pressures in PSI. Cold = pre-session (ambient). Hot = target after warmup.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {([
              ['FL', 'Front Left',  'fl'],
              ['FR', 'Front Right', 'fr'],
              ['RL', 'Rear Left',   'rl'],
              ['RR', 'Rear Right',  'rr'],
            ] as [string, string, 'fl'|'fr'|'rl'|'rr'][]).map(([abbr, name, key]) => (
              <div key={key} className="bg-bg border border-border rounded p-3 space-y-3">
                <div className="text-xs font-bold text-gray-300 uppercase tracking-wider">{name} <span className="text-gray-600">({abbr})</span></div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Cold PSI</label>
                    <input type="number" min={0} max={50} step={0.5}
                      value={ax.tire_psi[`${key}_cold` as keyof TirePSI]}
                      onChange={e => setPSI({ [`${key}_cold`]: parseFloat(e.target.value) || 0 } as any)}
                      className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm text-center font-mono" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Hot Target PSI</label>
                    <input type="number" min={0} max={50} step={0.5}
                      value={ax.tire_psi[`${key}_hot` as keyof TirePSI]}
                      onChange={e => setPSI({ [`${key}_hot`]: parseFloat(e.target.value) || 0 } as any)}
                      className="w-full bg-surface border border-border rounded px-3 py-2 text-accent focus:outline-none focus:border-accent text-sm text-center font-mono font-bold" />
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>Rise:</span>
                  <span className={`font-mono font-bold ${
                    (ax.tire_psi[`${key}_hot` as keyof TirePSI] - ax.tire_psi[`${key}_cold` as keyof TirePSI]) > 0
                      ? 'text-green' : 'text-gray-600'
                  }`}>
                    +{(ax.tire_psi[`${key}_hot` as keyof TirePSI] - ax.tire_psi[`${key}_cold` as keyof TirePSI]).toFixed(1)} PSI
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Kart diagram – visual PSI overlay */}
          <div className="bg-bg border border-border rounded p-4">
            <div className="text-xs text-gray-500 mb-3 uppercase tracking-wider">Kart View — Cold / Hot PSI</div>
            <div className="relative mx-auto" style={{ width: 180, height: 240 }}>
              {/* Kart body outline */}
              <div className="absolute inset-x-8 top-12 bottom-12 border-2 border-gray-700 rounded-lg bg-gray-900 bg-opacity-50" />
              <div className="absolute left-1/2 -translate-x-1/2 top-4 text-xs text-gray-600 font-bold">FRONT</div>
              <div className="absolute left-1/2 -translate-x-1/2 bottom-2 text-xs text-gray-600 font-bold">REAR</div>
              {([
                ['FL', 'fl', 'top-8  left-0'],
                ['FR', 'fr', 'top-8  right-0'],
                ['RL', 'rl', 'bottom-8 left-0'],
                ['RR', 'rr', 'bottom-8 right-0'],
              ] as [string, 'fl'|'fr'|'rl'|'rr', string][]).map(([abbr, key, pos]) => (
                <div key={key} className={`absolute ${pos} text-center w-12`}>
                  <div className="text-xs text-gray-400 font-bold">{abbr}</div>
                  <div className="text-xs font-mono text-white">{ax.tire_psi[`${key}_cold` as keyof TirePSI]}</div>
                  <div className="text-xs font-mono text-accent font-bold">{ax.tire_psi[`${key}_hot` as keyof TirePSI]}</div>
                </div>
              ))}
            </div>
            <div className="flex gap-4 justify-center text-xs text-gray-500 mt-2">
              <span><span className="text-white font-mono">12.0</span> = cold</span>
              <span><span className="text-accent font-mono font-bold">14.0</span> = hot target</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button type="button"
              onClick={async () => {
                if (!kartId) return
                const payload = { ...ax, active_map: activeMap }
                try {
                  await api.put(`/karts/${kartId}`, { settings_json: JSON.stringify(payload) })
                  setAxSaved(true); setTimeout(() => setAxSaved(false), 2500)
                } catch (err: any) { alert(err.message) }
              }}
              className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">
              Save Tire Pressures
            </button>
            {axSaved && <span className="text-green text-sm font-medium">Saved!</span>}
          </div>
        </div>
      )}

      {/* ── Archive Backend ────────────────────────────────────────────────── */}
      <div className="bg-surface border border-border rounded-lg p-4 text-sm text-gray-400 space-y-1">
        <h2 className="text-xs font-bold text-white uppercase tracking-wider mb-2">Archive Backend</h2>
        <p>Set <code className="text-accent">STRATOS_ARCHIVE_BACKEND</code> env var to one of:</p>
        <ul className="list-disc list-inside space-y-1 ml-2 text-xs">
          <li><code className="text-white">disabled</code> — no archiving (default)</li>
          <li><code className="text-white">smb</code> — network share (<code>STRATOS_SMB_SHARE=//host/share</code>)</li>
          <li><code className="text-white">rclone_gdrive</code> — Google Drive via rclone (<code>STRATOS_RCLONE_REMOTE=gdrive:path</code>)</li>
        </ul>
      </div>
    </div>
  )
}
