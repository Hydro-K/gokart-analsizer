import { useEffect, useState } from 'react'
import { api } from '../api'
import { MetricCard } from '../components/common/MetricCard'
import { StorageBar } from '../components/common/StorageBar'
import { StatusBadge } from '../components/common/StatusBadge'

interface StorageStats {
  sd_total_gb: number
  sd_used_gb: number
  sd_pct: number
  hdd_available: boolean
  hdd_total_gb: number | null
  hdd_used_gb: number | null
  threshold_warn: number
  threshold_critical: number
  threshold_emergency: number
  status: string
  sessions_on_sd: number
  sessions_archived: number
}

export default function StorageDashboard() {
  const [stats, setStats] = useState<StorageStats | null>(null)
  const [cleaning, setCleaning] = useState(false)
  const [error, setError] = useState('')

  const load = () => api.get<StorageStats>('/storage/stats').then(setStats).catch(() => setError('Failed to load storage stats'))
  useEffect(() => { load() }, [])

  const cleanup = async () => {
    if (!confirm('Run auto-cleanup? This may archive or delete old raw files.')) return
    setCleaning(true)
    try { await api.post('/storage/cleanup', {}); load() }
    catch (err: any) { alert(err.message) }
    finally { setCleaning(false) }
  }

  if (error) return <div className="text-red text-sm">{error}</div>
  if (!stats) return <div className="text-gray-400">Loading storage stats...</div>

  const freeGb = stats.sd_total_gb - stats.sd_used_gb

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Storage</h1>
        <StatusBadge status={stats.status} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Total" value={stats.sd_total_gb.toFixed(1)} unit="GB" />
        <MetricCard label="Used"  value={stats.sd_used_gb.toFixed(1)}  unit="GB" highlight={stats.sd_pct >= stats.threshold_warn} />
        <MetricCard label="Free"  value={freeGb.toFixed(1)}  unit="GB" />
        <div className="rounded-lg p-3 border border-border bg-surface flex flex-col gap-2">
          <span className="text-xs text-gray-400 uppercase tracking-wider">Usage</span>
          <StorageBar pct={stats.sd_pct} status={stats.status} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="Sessions on SD" value={String(stats.sessions_on_sd)} unit="" />
        <MetricCard label="Archived" value={String(stats.sessions_archived)} unit="" />
      </div>

      <div className="bg-surface border border-border rounded-lg p-4 space-y-3">
        <h2 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Thresholds</h2>
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div className="text-center">
            <div className="text-gold font-bold">{stats.threshold_warn}%</div>
            <div className="text-xs text-gray-400">Warn</div>
          </div>
          <div className="text-center">
            <div className="text-orange font-bold">{stats.threshold_critical}%</div>
            <div className="text-xs text-gray-400">Archive</div>
          </div>
          <div className="text-center">
            <div className="text-red font-bold">{stats.threshold_emergency}%</div>
            <div className="text-xs text-gray-400">Emergency</div>
          </div>
        </div>
      </div>

      {stats.hdd_available && stats.hdd_total_gb != null && (
        <div className="bg-surface border border-border rounded-lg p-4 space-y-2">
          <h2 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Archive Drive</h2>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div><span className="text-gray-400">Total: </span><span className="text-white">{stats.hdd_total_gb.toFixed(1)} GB</span></div>
            <div><span className="text-gray-400">Used: </span><span className="text-white">{stats.hdd_used_gb?.toFixed(1) ?? '?'} GB</span></div>
          </div>
        </div>
      )}

      {stats.status !== 'ok' && (
        <div className="bg-orange bg-opacity-10 border border-orange rounded-lg p-4 text-sm text-orange">
          Storage at {stats.sd_pct.toFixed(1)}%. Run cleanup to archive old raw CSV files.
        </div>
      )}

      <button
        onClick={cleanup}
        disabled={cleaning}
        className="px-4 py-2 border border-border rounded hover:border-orange hover:text-orange transition-colors text-sm disabled:opacity-50"
      >
        {cleaning ? 'Cleaning...' : 'Run Auto-Cleanup'}
      </button>
    </div>
  )
}
