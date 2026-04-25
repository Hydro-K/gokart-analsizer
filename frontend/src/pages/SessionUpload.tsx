import { useState, useRef, FormEvent, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, Driver, Kart, Track } from '../api'
import { JobProgress } from '../components/common/JobProgress'

interface QueuedSession {
  id: string
  files: File[]
  driverId: string
  kartId: string
  trackId: string
  sessionType: string
  date: string
  jobId?: number
  status: 'pending' | 'uploading' | 'processing' | 'done' | 'error'
  error?: string
}

export default function SessionUpload() {
  const [drivers, setDrivers] = useState<Driver[]>([])
  const [karts, setKarts]     = useState<Kart[]>([])
  const [tracks, setTracks]   = useState<Track[]>([])
  const [driverId, setDriverId] = useState('')
  const [kartId, setKartId]     = useState('')
  const [trackId, setTrackId]   = useState('')
  const [sessionType, setSessionType] = useState('Practice 1')
  const [date, setDate]         = useState(new Date().toISOString().slice(0, 10))
  const [files, setFiles]       = useState<File[]>([])
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [queue, setQueue]       = useState<QueuedSession[]>([])
  const [bulkMode, setBulkMode] = useState(false)
  const [activeJob, setActiveJob] = useState<number | null>(null)

  const fileRef   = useRef<HTMLInputElement>(null)
  const folderRef = useRef<HTMLInputElement>(null)
  const nav = useNavigate()

  useEffect(() => {
    api.get<Driver[]>('/drivers').then(setDrivers).catch(() => {})
    api.get<Kart[]>('/karts').then(setKarts).catch(() => {})
    api.get<Track[]>('/tracks').then(setTracks).catch(() => {})
  }, [])

  // webkitdirectory must be set as a DOM attribute — not supported as a React prop
  useEffect(() => {
    const el = folderRef.current
    if (!el) return
    el.setAttribute('webkitdirectory', '')
    el.setAttribute('directory', '')
    el.setAttribute('multiple', '')
  }, [])

  const handleFiles = (selected: FileList | null) => {
    if (!selected) return
    const csvOnly = Array.from(selected).filter(f => /\.csv$/i.test(f.name))
    if (csvOnly.length === 0) { setError('No CSV files found in the selection.'); return }
    const sorted = csvOnly.sort((a, b) => a.name.localeCompare(b.name))
    setFiles(sorted)
    setError('')
    if (sorted[0].lastModified)
      setDate(new Date(sorted[0].lastModified).toISOString().slice(0, 10))
  }

  const removeFile = (idx: number) => setFiles(f => f.filter((_, i) => i !== idx))

  const submitSingle = async (e: FormEvent) => {
    e.preventDefault()
    if (files.length === 0 || !driverId || !kartId || !trackId) {
      setError('All fields are required — driver, kart, track, and at least one CSV file.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const form = new FormData()
      files.forEach(f => form.append('files', f))
      form.append('driver_id', driverId)
      form.append('kart_id', kartId)
      form.append('track_id', trackId)
      form.append('session_type', sessionType)
      form.append('date', date)
      const res = await api.upload<{ job_id: number }>('/sessions/upload', form)
      setActiveJob(res.job_id)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const addToQueue = () => {
    if (files.length === 0 || !driverId || !kartId || !trackId) {
      setError('Fill all fields and select files before adding to queue.')
      return
    }
    setError('')
    setQueue(prev => [...prev, {
      id: `${Date.now()}-${Math.random()}`,
      files: [...files], driverId, kartId, trackId, sessionType, date, status: 'pending',
    }])
    setFiles([])
    if (fileRef.current)   fileRef.current.value = ''
    if (folderRef.current) folderRef.current.value = ''
  }

  const removeFromQueue = (id: string) => setQueue(prev => prev.filter(q => q.id !== id))

  const runQueue = async () => {
    for (const item of queue.filter(q => q.status === 'pending')) {
      setQueue(prev => prev.map(q => q.id === item.id ? { ...q, status: 'uploading' } : q))
      try {
        const form = new FormData()
        item.files.forEach(f => form.append('files', f))
        form.append('driver_id', item.driverId)
        form.append('kart_id', item.kartId)
        form.append('track_id', item.trackId)
        form.append('session_type', item.sessionType)
        form.append('date', item.date)
        const res = await api.upload<{ job_id: number }>('/sessions/upload', form)
        setQueue(prev => prev.map(q => q.id === item.id ? { ...q, status: 'processing', jobId: res.job_id } : q))
        await pollJobDone(res.job_id)
        setQueue(prev => prev.map(q => q.id === item.id ? { ...q, status: 'done' } : q))
      } catch (err: any) {
        setQueue(prev => prev.map(q => q.id === item.id ? { ...q, status: 'error', error: err.message } : q))
      }
    }
  }

  const pollJobDone = (jobId: number): Promise<void> =>
    new Promise((resolve, reject) => {
      const t = setInterval(async () => {
        try {
          const job = await api.get<{ status: string; error_msg?: string }>(`/jobs/${jobId}`)
          if (job.status === 'done')   { clearInterval(t); resolve() }
          if (job.status === 'failed') { clearInterval(t); reject(new Error(job.error_msg ?? 'Job failed')) }
        } catch { clearInterval(t); reject(new Error('Polling failed')) }
      }, 2500)
    })

  const driverName = (id: string) => drivers.find(d => String(d.id) === id)?.name ?? `#${id}`
  const kartName   = (id: string) => karts.find(k => String(k.id) === id)?.name ?? `#${id}`
  const STATUS_COLOR: Record<string, string> = {
    pending: 'text-gray-400', uploading: 'text-gold', processing: 'text-blue-400',
    done: 'text-green', error: 'text-red',
  }

  if (activeJob) {
    return (
      <div className="max-w-lg space-y-4">
        <h1 className="text-2xl font-bold text-white">Upload Session</h1>
        <p className="text-gray-300 text-sm">Ingestion running — analysis, GPS reconstruction, and ML will complete automatically.</p>
        <JobProgress jobId={activeJob} onDone={() => nav('/sessions')} />
      </div>
    )
  }

  const SelectField = ({ label, value, onChange, options }: {
    label: string; value: string; onChange: (v: string) => void
    options: { id: number; name: string }[]
  }) => (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label} *</label>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="w-full bg-surface border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-accent">
        <option value="">Select {label.toLowerCase()}...</option>
        {options.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select>
    </div>
  )

  return (
    <div className="max-w-2xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Upload Session</h1>
          <p className="text-xs text-gray-500 mt-0.5">One AiM session = one folder with up to 10 CSV channel files</p>
        </div>
        <button onClick={() => setBulkMode(b => !b)}
          className={`text-xs px-3 py-1.5 border rounded transition-colors ${
            bulkMode ? 'border-accent text-accent bg-accent bg-opacity-10' : 'border-border text-gray-400 hover:border-accent'
          }`}>
          {bulkMode ? '✓ Bulk Mode' : '+ Bulk Mode (18+ sessions)'}
        </button>
      </div>

      {bulkMode && (
        <div className="bg-surface border border-accent border-opacity-30 rounded-lg p-3 text-xs text-gray-400 space-y-0.5">
          <p className="text-white font-medium text-sm mb-1">Bulk Upload — queue multiple sessions</p>
          <p>① Select folder → set driver/kart/track → <span className="text-accent font-bold">Add to Queue</span></p>
          <p>② Repeat for each session folder (you have 18)</p>
          <p>③ Click <span className="text-accent font-bold">Run All</span> — they process one by one automatically</p>
        </div>
      )}

      <div className="space-y-3">
        {error && <div className="text-red text-xs bg-red bg-opacity-10 border border-red rounded px-3 py-2">{error}</div>}

        <div className="grid grid-cols-3 gap-3">
          <SelectField label="Driver" value={driverId} onChange={setDriverId} options={drivers} />
          <SelectField label="Kart"   value={kartId}   onChange={setKartId}   options={karts} />
          <SelectField label="Track"  value={trackId}  onChange={setTrackId}  options={tracks} />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Session Type</label>
            <select value={sessionType} onChange={e => setSessionType(e.target.value)}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-accent">
              {['Practice 1','Practice 2','Qualifying','Race','Test'].map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Date</label>
            <input type="date" value={date} onChange={e => setDate(e.target.value)}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-accent" />
          </div>
        </div>

        <div>
          <label className="block text-xs text-gray-400 mb-1">
            AiM CSV Files * <span className="text-gray-600">— all 10 files from one session folder</span>
          </label>
          <div
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); handleFiles(e.dataTransfer.files) }}
            className="border-2 border-dashed border-border rounded-lg px-4 py-6 text-center hover:border-accent transition-colors"
          >
            {files.length === 0 ? (
              <div>
                <p className="text-gray-500 text-sm">Drag & drop session folder here</p>
                <p className="text-gray-600 text-xs mt-1">or use the buttons below</p>
              </div>
            ) : (
              <p className="text-accent text-sm font-mono font-bold">
                {files.length} CSV file{files.length !== 1 ? 's' : ''} ready
              </p>
            )}
          </div>

          <div className="flex gap-2 mt-2">
            <button type="button" onClick={() => fileRef.current?.click()}
              className="flex-1 py-2.5 text-xs border border-border rounded hover:border-accent hover:text-accent transition-colors">
              Browse Files
              <span className="block text-gray-600 text-xs mt-0.5">select individual CSVs</span>
            </button>
            <button type="button" onClick={() => folderRef.current?.click()}
              className="flex-1 py-2.5 text-xs border-2 border-accent text-accent rounded hover:bg-accent hover:bg-opacity-10 transition-colors font-medium">
              Browse Folder
              <span className="block text-gray-400 text-xs mt-0.5 font-normal">picks all CSVs in folder</span>
            </button>
          </div>

          <input ref={fileRef} type="file" accept=".csv,.CSV" multiple className="hidden"
            onChange={e => handleFiles(e.target.files)} />
          {/* folderRef gets webkitdirectory set via useEffect */}
          <input ref={folderRef} type="file" accept=".csv,.CSV" className="hidden"
            onChange={e => handleFiles(e.target.files)} />

          {files.length > 0 && (
            <div className="mt-2 space-y-1 max-h-48 overflow-y-auto border border-border rounded p-1">
              {files.map((f, i) => (
                <div key={i} className="flex items-center gap-2 px-2 py-1 rounded text-xs hover:bg-surface">
                  <span className="font-mono text-white truncate flex-1">{f.name}</span>
                  <span className="text-gray-600 shrink-0">{(f.size / 1024).toFixed(0)} KB</span>
                  <button type="button" onClick={() => removeFile(i)}
                    className="text-gray-600 hover:text-red shrink-0">✕</button>
                </div>
              ))}
            </div>
          )}
        </div>

        {(drivers.length === 0 || karts.length === 0 || tracks.length === 0) && (
          <div className="text-xs text-gold bg-gold bg-opacity-10 border border-gold rounded px-3 py-2">
            Add at least one driver, kart, and track before uploading.
          </div>
        )}

        <div className="flex gap-3">
          {bulkMode ? (
            <button type="button" onClick={addToQueue}
              className="flex-1 py-2.5 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">
              Add to Queue {queue.length > 0 && `(${queue.length} queued)`}
            </button>
          ) : (
            <button type="button" onClick={submitSingle} disabled={loading}
              className="flex-1 py-2.5 bg-accent text-bg font-bold rounded hover:opacity-90 disabled:opacity-50 text-sm">
              {loading ? 'Uploading...' : files.length > 1 ? `Upload & Analyse (${files.length} files)` : 'Upload & Analyse'}
            </button>
          )}
        </div>
      </div>

      {/* Bulk queue panel */}
      {bulkMode && queue.length > 0 && (
        <div className="space-y-3 pt-3 border-t border-border">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">
              Queue — {queue.filter(q => q.status === 'pending').length} pending / {queue.length} total
            </h2>
            <div className="flex gap-2">
              <button onClick={runQueue}
                disabled={!queue.some(q => q.status === 'pending')}
                className="px-4 py-1.5 bg-accent text-bg text-xs font-bold rounded hover:opacity-90 disabled:opacity-50">
                Run All
              </button>
              <button onClick={() => setQueue(q => q.filter(s => s.status !== 'pending'))}
                className="px-3 py-1.5 border border-border text-xs rounded hover:border-red hover:text-red transition-colors">
                Clear Pending
              </button>
            </div>
          </div>
          <div className="space-y-1.5">
            {queue.map(item => (
              <div key={item.id} className="flex items-center gap-3 bg-surface border border-border rounded px-3 py-2 text-xs">
                <span className={`font-bold uppercase shrink-0 w-20 ${STATUS_COLOR[item.status]}`}>
                  {item.status}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="text-white font-medium">{driverName(item.driverId)}</span>
                  <span className="text-gray-600 mx-1">·</span>
                  <span className="text-gray-400">{kartName(item.kartId)}</span>
                  <span className="text-gray-600 mx-1">·</span>
                  <span className="text-gray-400">{item.sessionType}</span>
                  <span className="text-gray-600 mx-1">·</span>
                  <span className="font-mono text-gray-500">{item.date}</span>
                  <span className="text-gray-700 ml-2">({item.files.length} files)</span>
                </div>
                {item.error && <span className="text-red truncate max-w-xs">{item.error}</span>}
                {item.status === 'done'    && <span className="text-green shrink-0">✓</span>}
                {item.status === 'pending' && (
                  <button onClick={() => removeFromQueue(item.id)}
                    className="text-gray-600 hover:text-red shrink-0">✕</button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
