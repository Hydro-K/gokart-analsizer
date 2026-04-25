import { useEffect, useState } from 'react'
import { api } from '../api'
import { MetricCard } from '../components/common/MetricCard'
import { StorageBar } from '../components/common/StorageBar'
import { StatusBadge } from '../components/common/StatusBadge'

interface StorageStats {
  total_gb: number
  used_gb: number
  free_gb: number
  used_pct: number
  status: string
  thresholds: { warn: number; critical: number; emergency: number }
  archive_backend: string
}

export default function StorageDashboard() {
  const [stats, setStats] = useState<StorageStats | null>(null)
  const [cleaning, setCleaning] = useState(false)

  const load = () => api.get<StorageStats>('/storage/stats').then(setStats).catch(() => {})
  useEffect(load, [])

  const cleanup = async () => {
    if (!confirm('Run auto-cleanup? This may archive or delete old raw files.')) return
    setCleaning(true)
    try { await api.post('/storage/cleanup', {}); load() }
    catch (err: any) { alert(err.message) }
    finally { setCleaning(false) }
  }

  if (!stats) return <div className="text-gray-400">Loading storage stats...</div>

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Storage</h1>
        <StatusBadge status={stats.status} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Total" value={stats.total_gb.toFixed(1)} unit="GB" />
        <MetricCard label="Used"  value={stats.used_gb.toFixed(1)}  unit="GB" highlight={stats.used_pct >= stats.thresholds.warn} />
        <MetricCard label="Free"  value={stats.free_gb.toFixed(1)}  unit="GB" />
        <div className="rounded-lg p-3 border border-border bg-surface flex flex-col gap-2">
          <span className="text-xs text-gray-400 uppercase tracking-wider">Usage</span>
          <StorageBar pct={stats.used_pct} status={stats.status} />
        </div>
      </div>

      <div className="bg-surface border border-border rounded-lg p-4 space-y-3">
        <h2 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Thresholds</h2>
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div className="text-center">
            <div className="text-gold font-bold">{stats.thresholds.warn}%</div>
            <div className="text-xs text-gray-400">Warn</div>
          </div>
          <div className="text-center">
            <div className="text-orange font-bold">{stats.thresholds.critical}%</div>
            <div className="text-xs text-gray-400">Archive</div>
          </div>
          <div className="text-center">
            <div className="text-red font-bold">{stats.thresholds.emergency}%</div>
            <div className="text-xs text-gray-400">Emergency</div>
          </div>
        </div>
        <div className="text-xs text-gray-400">
          Archive backend: <span className="text-white font-mono">{stats.archive_backend}</span>
          {' '}— configure in Settings
        </div>
      </div>

      {stats.status !== 'ok' && (
        <div className="bg-orange bg-opacity-10 border border-orange rounded-lg p-4 text-sm text-orange">
          Storage at {stats.used_pct.toFixed(1)}%. Run cleanup to archive old raw CSV files.
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
