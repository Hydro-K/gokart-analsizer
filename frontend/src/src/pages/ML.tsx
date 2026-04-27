import { useEffect, useState } from 'react'
import { api, Driver } from '../api'
import { MetricCard } from '../components/common/MetricCard'
import { JobProgress } from '../components/common/JobProgress'

interface MLStatus {
  model_exists: boolean
  n_training_samples: number
  last_trained: string | null
}

interface DriverStyle {
  driver_id: number
  style_label: string
  confidence: number
  sessions_analyzed: number
  updated_at: string
}

interface FeatureRow {
  lap_id: number
  driver_id: number
  throttle_variance: number
  braking_intensity: number
  corner_entry_speed_avg: number
  accel_consistency: number
  smoothness_score: number
}

const STYLE_COLOR: Record<string, string> = {
  aggressive: 'text-red',
  smooth: 'text-green',
  balanced: 'text-accent',
  inconsistent: 'text-gold',
}

const STYLE_DESC: Record<string, string> = {
  aggressive: 'High throttle variance, hard braking — fast but hard on hardware',
  smooth: 'Consistent inputs, good corner entry — efficient and predictable',
  balanced: 'Mix of aggression and smoothness — adapts to conditions',
  inconsistent: 'Variable lap times — may benefit from more practice',
}

export default function ML() {
  const [status, setStatus]   = useState<MLStatus | null>(null)
  const [drivers, setDrivers] = useState<Driver[]>([])
  const [styles, setStyles]   = useState<Record<number, DriverStyle>>({})
  const [features, setFeatures] = useState<FeatureRow[]>([])
  const [jobId, setJobId]     = useState<number | null>(null)
  const [training, setTraining] = useState(false)
  const [error, setError]     = useState('')

  const loadAll = async () => {
    try {
      const [s, ds] = await Promise.all([
        api.get<MLStatus>('/ml/status'),
        api.get<Driver[]>('/drivers'),
      ])
      setStatus(s)
      setDrivers(ds)
      const styleMap: Record<number, DriverStyle> = {}
      await Promise.all(ds.map(d =>
        api.get<DriverStyle>(`/ml/driver/${d.id}/style`)
          .then(st => { styleMap[d.id] = st })
          .catch(() => {})
      ))
      setStyles(styleMap)
    } catch (e: any) {
      setError(e.message)
    }
  }

  useEffect(() => { loadAll() }, [])

  const trainNow = async () => {
    setError('')
    setTraining(true)
    try {
      const res = await api.post<{ job_id: number; message: string }>('/ml/train', {})
      setJobId(res.job_id)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setTraining(false)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">ML — Driver Style Analysis</h1>
      </div>

      {error && (
        <div className="text-red text-sm bg-red bg-opacity-10 border border-red rounded px-3 py-2">{error}</div>
      )}

      {/* Status card */}
      {status && (
        <div className="grid grid-cols-3 gap-3">
          <MetricCard
            label="Model"
            value={status.model_exists ? 'Ready' : 'Not trained'}
            unit=""
            highlight={!status.model_exists}
          />
          <MetricCard label="Training laps" value={String(status.n_training_samples)} unit="" />
          <MetricCard
            label="Last trained"
            value={status.last_trained ? new Date(status.last_trained).toLocaleDateString() : 'Never'}
            unit=""
          />
        </div>
      )}

      {/* Train button / progress */}
      <div className="bg-surface border border-border rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Training</h2>
        <p className="text-xs text-gray-400">
          Requires at least 5 laps with extracted features. Training classifies each driver's style
          (aggressive / smooth / balanced / inconsistent) and persists predictions in the database.
        </p>
        {jobId ? (
          <JobProgress jobId={jobId} onDone={() => { setJobId(null); loadAll() }} />
        ) : (
          <button
            onClick={trainNow}
            disabled={training || (status?.n_training_samples ?? 0) < 5}
            className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 disabled:opacity-50 text-sm"
          >
            {training ? 'Queuing...' : 'Train Now'}
          </button>
        )}
        {status && status.n_training_samples < 5 && (
          <p className="text-xs text-gold">
            Need {5 - status.n_training_samples} more laps before training is possible.
            Upload sessions to collect feature data automatically.
          </p>
        )}
      </div>

      {/* Driver style cards */}
      {drivers.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Driver Profiles</h2>
          {drivers.map(d => {
            const style = styles[d.id]
            return (
              <div key={d.id} className="bg-surface border border-border rounded-lg p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-white font-medium">{d.name}</span>
                  {style ? (
                    <div className="text-right">
                      <span className={`text-sm font-bold capitalize ${STYLE_COLOR[style.style_label] ?? 'text-white'}`}>
                        {style.style_label}
                      </span>
                      <span className="text-xs text-gray-400 ml-2">{style.confidence.toFixed(0)}% confidence</span>
                    </div>
                  ) : (
                    <span className="text-xs text-gray-500">No data yet</span>
                  )}
                </div>
                {style && (
                  <>
                    <p className="text-xs text-gray-400">{STYLE_DESC[style.style_label] ?? ''}</p>
                    <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs font-mono pt-1">
                      <FeatureStat label="Sessions analyzed" value={String(style.sessions_analyzed)} />
                      <FeatureStat label="Last updated" value={new Date(style.updated_at).toLocaleDateString()} />
                    </div>
                  </>
                )}
              </div>
            )
          })}
        </div>
      )}

      {drivers.length === 0 && (
        <p className="text-gray-400 text-sm">No drivers found. Add drivers and upload sessions first.</p>
      )}
    </div>
  )
}

function FeatureStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-gray-400 w-36 shrink-0">{label}</span>
      <span className="text-white">{value}</span>
    </div>
  )
}
