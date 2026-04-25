import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { api, ComplianceResult } from '../api'
import { StatusBadge } from '../components/common/StatusBadge'

interface Rules {
  controller_max_current_a: number
  battery_voltage_max_v: number
  battery_voltage_min_v: number
  speed_limit_kmh: number
  combined_min_weight_kg: number
  rulebook_version: string
}

export default function Compliance() {
  const [params] = useSearchParams()
  const sessionId = params.get('session')

  const [result, setResult] = useState<ComplianceResult | null>(null)
  const [rules, setRules]   = useState<Rules | null>(null)

  useEffect(() => {
    api.get<Rules>('/compliance/rules').then(setRules).catch(() => {})
    if (sessionId) {
      api.get<ComplianceResult>(`/sessions/${sessionId}/compliance`).then(setResult).catch(() => {})
    } else {
      api.get<ComplianceResult>('/compliance/check').then(setResult).catch(() => {})
    }
  }, [sessionId])

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Compliance</h1>
        {result && <StatusBadge status={result.overall} />}
      </div>

      {rules && (
        <div className="bg-surface border border-border rounded-lg p-4 space-y-2">
          <h2 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Active Rules — {rules.rulebook_version}</h2>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div><span className="text-gray-400">Max Current:</span> <span className="text-orange font-bold">{rules.controller_max_current_a}A</span></div>
            <div><span className="text-gray-400">Speed Limit:</span> <span className="text-white">{rules.speed_limit_kmh} km/h</span></div>
            <div><span className="text-gray-400">Battery Max V:</span> <span className="text-white">{rules.battery_voltage_max_v}V</span></div>
            <div><span className="text-gray-400">Min Weight:</span> <span className="text-white">{rules.combined_min_weight_kg} kg</span></div>
          </div>
        </div>
      )}

      {result ? (
        <div className="space-y-2">
          {result.items.map((item, i) => (
            <div key={i} className="flex items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3">
              <StatusBadge status={item.status} />
              <div className="flex-1 min-w-0">
                <div className="text-white text-sm">{item.name}</div>
                <div className="text-xs text-gray-400">{item.detail}</div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-gray-400 text-sm">
          {sessionId ? 'Loading session compliance...' : (
            <>Run a session first, then view compliance from{' '}
            <Link to="/sessions" className="text-accent hover:underline">Sessions</Link>.</>
          )}
        </div>
      )}
    </div>
  )
}
