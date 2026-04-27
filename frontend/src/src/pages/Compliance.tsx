import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { api } from '../api'

interface ComplianceItem {
  rule_name: string
  rule_section: string
  status: string
  current_value: string
  limit_value: string
  message: string
  actionable: string
}
interface ComplianceResult {
  passed: boolean
  items: ComplianceItem[]
}
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
        {result && <StatusBadge status={result.passed ? 'pass' : 'fail'} />}
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
            <div key={i} className="rounded-lg border border-border bg-surface px-4 py-3 space-y-1">
              <div className="flex items-center gap-3">
                <StatusBadge status={item.status} />
                <span className="text-white text-sm font-medium">{item.rule_name}</span>
                <span className="text-gray-500 text-xs ml-auto">{item.rule_section}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs font-mono pl-1">
                <div><span className="text-gray-400">Measured: </span><span className="text-white">{item.current_value}</span></div>
                <div><span className="text-gray-400">Limit: </span><span className="text-white">{item.limit_value}</span></div>
              </div>
              <p className="text-xs text-gray-400 pl-1">{item.message}</p>
              {item.actionable && item.actionable !== 'No action needed.' && (
                <p className="text-xs text-accent pl-1">→ {item.actionable}</p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-gray-400 text-sm">
          {sessionId ? 'Loading session compliance...' : (
            <>Select a session to check compliance, or pick a kart from{' '}
            <Link to="/sessions" className="text-accent hover:underline">Sessions</Link>.</>
          )}
        </div>
      )}
    </div>
  )
}
