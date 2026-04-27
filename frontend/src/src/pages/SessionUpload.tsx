import { useState, useRef, FormEvent, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, Driver, Kart, Track } from '../api'
import { JobProgress } from '../components/common/JobProgress'

interface FileEntry {
  file: File
  relativePath: string  // webkitRelativePath or just file.name
  folder: string        // top-level folder name, or '' for individual files
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
  const [entries, setEntries]   = useState<FileEntry[]>([])
  const [error, setError]       = useState('')
  const [jobId, setJobId]       = useState<number | null>(null)
  const [loading, setLoading]   = useState(false)
  const fileRef   = useRef<HTMLInputElement>(null)
  const folderRef = useRef<HTMLInputElement>(null)
  const nav = useNavigate()

  useEffect(() => {
    api.get<Driver[]>('/drivers').then(setDrivers).catch(() => {})
    api.get<Kart[]>('/karts').then(setKarts).catch(() => {})
    api.get<Track[]>('/tracks').then(setTracks).catch(() => {})
  }, [])

  // Set webkitdirectory via DOM (React ignores non-standard attributes)
  useEffect(() => {
    const el = folderRef.current
    if (!el) return
    el.setAttribute('webkitdirectory', '')
    el.setAttribute('directory', '')
    el.setAttribute('multiple', '')
  }, [])

  const addFiles = (selected: FileList | null, append = false) => {
    if (!selected) return
    const newEntries: FileEntry[] = Array.from(selected)
      .filter(f => /\.csv$/i.test(f.name))
      .map(f => {
        const rel = (f as any).webkitRelativePath || f.name
        const folder = rel.includes('/') ? rel.split('/')[0] : ''
        return { file: f, relativePath: rel, folder }
      })
      .sort((a, b) => a.relativePath.localeCompare(b.relativePath))

    setEntries(prev => {
      const combined = append ? [...prev, ...newEntries] : newEntries
      // deduplicate by relativePath
      const seen = new Set<string>()
      return combined.filter(e => seen.has(e.relativePath) ? false : (seen.add(e.relativePath), true))
    })
  }

  const removeEntry = (idx: number) => setEntries(e => e.filter((_, i) => i !== idx))

  // Group entries by folder for display
  const folders = [...new Set(entries.map(e => e.folder || '(individual files)'))]

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (entries.length === 0 || !driverId || !kartId || !trackId) {
      setError('All fields are required — driver, kart, track, and at least one CSV file.')
      return
    }
    setError('')
    setLoading(true)
    const form = new FormData()
    const relPaths: string[] = []
    entries.forEach(entry => {
      form.append('files', entry.file)
      relPaths.push(entry.relativePath)
    })
    form.append('driver_id', driverId)
    form.append('kart_id', kartId)
    form.append('track_id', trackId)
    form.append('session_type', sessionType)
    form.append('date', date)
    // Send relative paths so backend can group files by source folder
    form.append('relative_paths', JSON.stringify(relPaths))
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

          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-xs text-gray-400 mb-1">Session Type</label>
              <select value={sessionType} onChange={e => setSessionType(e.target.value)}
                className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent">
                {['Practice 1','Practice 2','Qualifying','Race','Test'].map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-xs text-gray-400 mb-1">Date</label>
              <input type="date" value={date} onChange={e => setDate(e.target.value)}
                className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">
              AiM CSV Files * — select one folder or multiple folders to stitch together
            </label>
            <div
              onDragOver={e => e.preventDefault()}
              onDrop={e => { e.preventDefault(); addFiles(e.dataTransfer.files, true) }}
              className="border-2 border-dashed border-border rounded-lg px-4 py-6 text-center hover:border-accent transition-colors"
            >
              {entries.length === 0 ? (
                <span className="text-gray-400 text-sm">Drag & drop CSV files or AiM session folder(s) here</span>
              ) : (
                <div className="space-y-1">
                  {folders.map(folder => {
                    const count = entries.filter(e => (e.folder || '(individual files)') === folder).length
                    return (
                      <div key={folder} className="text-accent text-sm font-mono">
                        {folder === '(individual files)' ? `${count} file(s)` : `📁 ${folder}  (${count} files)`}
                      </div>
                    )
                  })}
                  {folders.length > 1 && (
                    <div className="text-gold text-xs mt-1">These {folders.length} folders will be stitched into one session</div>
                  )}
                </div>
              )}
            </div>

            <div className="flex gap-2 mt-2">
              <button type="button" onClick={() => { fileRef.current!.value = ''; fileRef.current?.click() }}
                className="flex-1 py-2 text-xs border border-border rounded hover:border-accent hover:text-accent transition-colors">
                Add Files
              </button>
              <button type="button" onClick={() => { folderRef.current!.value = ''; folderRef.current?.click() }}
                className="flex-1 py-2 text-xs border border-border rounded hover:border-accent hover:text-accent transition-colors">
                Add Folder
              </button>
              {entries.length > 0 && (
                <button type="button" onClick={() => setEntries([])}
                  className="px-3 py-2 text-xs border border-border rounded hover:border-red hover:text-red transition-colors">
                  Clear
                </button>
              )}
            </div>

            <input ref={fileRef} type="file" accept=".csv,.CSV" multiple className="hidden"
              onChange={e => addFiles(e.target.files, true)} />
            <input ref={folderRef} type="file" accept=".csv,.CSV" className="hidden"
              onChange={e => addFiles(e.target.files, true)} />

            {entries.length > 0 && (
              <ul className="mt-2 space-y-1 max-h-48 overflow-y-auto">
                {entries.map((entry, i) => (
                  <li key={i} className="flex items-center justify-between bg-surface rounded px-3 py-1 text-xs">
                    <span className="font-mono text-white truncate max-w-xs">{entry.relativePath}</span>
                    <span className="text-gray-500 ml-2 shrink-0">
                      {(entry.file.size / 1024).toFixed(0)} KB
                    </span>
                    <button type="button" onClick={() => removeEntry(i)}
                      className="ml-3 text-gray-500 hover:text-red shrink-0">✕</button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {(drivers.length === 0 || karts.length === 0 || tracks.length === 0) && (
            <div className="text-xs text-gold bg-gold bg-opacity-10 border border-gold rounded px-3 py-2">
              You need at least one driver, kart, and track before uploading.
              Create them in the respective pages first.
            </div>
          )}

          <button type="submit" disabled={loading}
            className="w-full py-2 bg-accent text-bg font-bold rounded hover:opacity-90 disabled:opacity-50">
            {loading ? 'Uploading...' : `Upload & Analyse${entries.length > 0 ? ` (${entries.length} files)` : ''}`}
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
