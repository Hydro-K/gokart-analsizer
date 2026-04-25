import { useState, useRef, FormEvent, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, Driver, Kart, Track } from '../api'
import { JobProgress } from '../components/common/JobProgress'

export default function SessionUpload() {
  const [drivers, setDrivers] = useState<Driver[]>([])
  const [karts, setKarts]     = useState<Kart[]>([])
  const [tracks, setTracks]   = useState<Track[]>([])
  const [driverId, setDriverId] = useState('')
  const [kartId, setKartId]     = useState('')
  const [trackId, setTrackId]   = useState('')
  const [sessionType, setSessionType] = useState('Practice 1')
  const [file, setFile]         = useState<File | null>(null)
  const [error, setError]       = useState('')
  const [jobId, setJobId]       = useState<number | null>(null)
  const [loading, setLoading]   = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const nav = useNavigate()

  useEffect(() => {
    api.get<Driver[]>('/drivers').then(setDrivers).catch(() => {})
    api.get<Kart[]>('/karts').then(setKarts).catch(() => {})
    api.get<Track[]>('/tracks').then(setTracks).catch(() => {})
  }, [])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!file || !driverId || !kartId || !trackId) {
      setError('All fields are required — driver, kart, track, and CSV file.')
      return
    }
    setError('')
    setLoading(true)
    const form = new FormData()
    form.append('file', file)
    form.append('driver_id', driverId)
    form.append('kart_id', kartId)
    form.append('track_id', trackId)
    form.append('session_type', sessionType)
    try {
      const res = await api.upload<{ job_id: number }>('/sessions/upload', form)
      setJobId(res.job_id)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg space-y-6">
      <h1 className="text-2xl font-bold text-white">Upload Session</h1>

      {!jobId ? (
        <form onSubmit={submit} className="space-y-4">
          {error && <div className="text-red text-sm bg-red bg-opacity-10 border border-red rounded px-3 py-2">{error}</div>}

          <div>
            <label className="block text-xs text-gray-400 mb-1">Driver *</label>
            <select value={driverId} onChange={e => setDriverId(e.target.value)} required
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent">
              <option value="">Select driver...</option>
              {drivers.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Kart *</label>
            <select value={kartId} onChange={e => setKartId(e.target.value)} required
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent">
              <option value="">Select kart...</option>
              {karts.map(k => <option key={k.id} value={k.id}>{k.name}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Track *</label>
            <select value={trackId} onChange={e => setTrackId(e.target.value)} required
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent">
              <option value="">Select track...</option>
              {tracks.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Session Type</label>
            <select value={sessionType} onChange={e => setSessionType(e.target.value)}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent">
              {['Practice 1','Practice 2','Qualifying','Race','Test'].map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">AiM CSV File *</label>
            <div
              onClick={() => fileRef.current?.click()}
              className="border-2 border-dashed border-border rounded-lg px-4 py-6 text-center cursor-pointer hover:border-accent transition-colors"
            >
              {file ? (
                <span className="text-white font-mono text-sm">{file.name}</span>
              ) : (
                <span className="text-gray-400 text-sm">Click to select CSV file</span>
              )}
            </div>
            <input ref={fileRef} type="file" accept=".csv,.CSV" className="hidden"
              onChange={e => setFile(e.target.files?.[0] ?? null)} />
          </div>

          {(drivers.length === 0 || karts.length === 0 || tracks.length === 0) && (
            <div className="text-xs text-gold bg-gold bg-opacity-10 border border-gold rounded px-3 py-2">
              You need at least one driver, kart, and track before uploading.
              Create them in the respective pages first.
            </div>
          )}

          <button type="submit" disabled={loading}
            className="w-full py-2 bg-accent text-bg font-bold rounded hover:opacity-90 disabled:opacity-50">
            {loading ? 'Uploading...' : 'Upload & Analyse'}
          </button>
        </form>
      ) : (
        <div className="space-y-4">
          <p className="text-gray-300 text-sm">Ingestion in progress. This runs analysis, GPS reconstruction, and ML automatically.</p>
          <JobProgress jobId={jobId} onDone={() => nav('/sessions')} />
        </div>
      )}
    </div>
  )
}
