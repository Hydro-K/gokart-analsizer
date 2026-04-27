import { useState, useEffect, useRef, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, Driver, Kart, Track } from '../api'
import { JobProgress } from '../components/common/JobProgress'

interface FileEntry {
  file: File
  relativePath: string  // dedup key
  folder: string        // display group name (the AiM session subfolder, e.g. a_0001_CSV)
  displayPath: string   // sent to backend
}

/** Group AiM CSV files by their session subfolder.
 *
 * AiM exports look like:
 *   day_folder / a_0001_CSV / GPS.csv        ← user picks day_folder  (depth 3)
 *   a_0001_CSV / GPS.csv                     ← user picks a_0001_CSV  (depth 2)
 *
 * We group by the last directory component before the filename,
 * so both cases produce folder = "a_0001_CSV".
 */
function groupFiles(selected: FileList): FileEntry[] {
  return Array.from(selected)
    .filter(f => /\.csv$/i.test(f.name))
    .map(f => {
      const rel: string = (f as any).webkitRelativePath || ''
      const parts = rel ? rel.split('/') : []

      let folder: string
      let displayPath: string

      if (parts.length >= 3) {
        // Picked any ancestor folder: always extract session subfolder + filename
        // so displayPath is always "sessionFolder/file.csv" (2 components).
        // Using slice(1) was wrong when the user picks a grandparent — it left
        // intermediate dirs in displayPath and broke backend grouping.
        folder      = parts[parts.length - 2]                     // e.g. a_0001_CSV
        displayPath = folder + '/' + parts[parts.length - 1]      // always session/file.csv
      } else if (parts.length === 2) {
        // Picked session folder directly: [session, file]
        folder      = parts[0]
        displayPath = rel
      } else {
        // Individual file with no path info
        folder      = 'Files'
        displayPath = f.name
      }

      return { file: f, relativePath: displayPath || f.name, folder, displayPath }
    })
    .sort((a, b) => a.relativePath.localeCompare(b.relativePath))
}

export default function SessionUpload() {
  const [drivers, setDrivers] = useState<Driver[]>([])
  const [karts, setKarts]     = useState<Kart[]>([])
  const [tracks, setTracks]   = useState<Track[]>([])
  const [driverId, setDriverId] = useState('')
  const [kartId, setKartId]     = useState('')
  const [trackId, setTrackId]   = useState('')
  const [sessionType, setSessionType] = useState('Testing')
  const [date, setDate]         = useState(new Date().toISOString().slice(0, 10))
  const [entries, setEntries]   = useState<FileEntry[]>([])
  const [error, setError]       = useState('')
  const [jobId, setJobId]       = useState<number | null>(null)
  const [loading, setLoading]   = useState(false)
  const [pickerKey, setPickerKey] = useState(0)  // bump to reset the <input> after each pick

  const nav = useNavigate()

  useEffect(() => {
    api.get<Driver[]>('/drivers').then(setDrivers).catch(() => {})
    api.get<Kart[]>('/karts').then(setKarts).catch(() => {})
    api.get<Track[]>('/tracks').then(setTracks).catch(() => {})
  }, [])

  const handlePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      const newEntries = groupFiles(files)
      if (newEntries.length > 0) {
        setEntries(prev => {
          const combined = [...prev, ...newEntries]
          const seen = new Set<string>()
          return combined.filter(en => seen.has(en.relativePath) ? false : (seen.add(en.relativePath), true))
        })
      }
    }
    setPickerKey(k => k + 1)  // fresh <input> so same folder can be re-picked
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.files.length > 0) {
      const newEntries = groupFiles(e.dataTransfer.files)
      if (newEntries.length > 0) {
        setEntries(prev => {
          const combined = [...prev, ...newEntries]
          const seen = new Set<string>()
          return combined.filter(en => seen.has(en.relativePath) ? false : (seen.add(en.relativePath), true))
        })
      }
    }
  }

  const removeFolder = (folder: string) =>
    setEntries(prev => prev.filter(e => e.folder !== folder))

  const folders = [...new Set(entries.map(e => e.folder))]

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (entries.length === 0 || !driverId || !kartId || !trackId) {
      setError('Driver, kart, track and at least one CSV folder are required.')
      return
    }
    setError('')
    setLoading(true)
    const form = new FormData()
    const relPaths: string[] = []
    entries.forEach(entry => {
      form.append('files', entry.file)
      relPaths.push(entry.displayPath)
    })
    form.append('driver_id', driverId)
    form.append('kart_id', kartId)
    form.append('track_id', trackId)
    form.append('session_type', sessionType)
    form.append('date', date)
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

  const missingSetup = drivers.length === 0 || karts.length === 0 || tracks.length === 0

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Upload Session</h1>
        <p className="text-xs text-gray-500 mt-1">
          Select your <span className="text-accent font-bold">day export folder</span> — all
          session subfolders inside it are detected automatically.
        </p>
      </div>

      {!jobId ? (
        <form onSubmit={submit} className="space-y-4">
          {error && (
            <div className="text-red text-sm bg-red bg-opacity-10 border border-red rounded px-3 py-2">
              {error}
            </div>
          )}

          {missingSetup && (
            <div className="text-xs text-gold bg-gold bg-opacity-10 border border-gold rounded px-3 py-2">
              You need at least one driver, kart, and track before uploading. Create them first.
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Driver *</label>
              <select value={driverId} onChange={e => setDriverId(e.target.value)} required
                className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm">
                <option value="">Select...</option>
                {drivers.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Kart *</label>
              <select value={kartId} onChange={e => setKartId(e.target.value)} required
                className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm">
                <option value="">Select...</option>
                {karts.map(k => <option key={k.id} value={k.id}>{k.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Track *</label>
              <select value={trackId} onChange={e => setTrackId(e.target.value)} required
                className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm">
                <option value="">Select...</option>
                {tracks.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Session Type</label>
              <select value={sessionType} onChange={e => setSessionType(e.target.value)}
                className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm">
                {['Testing', 'Sprint', 'Race', 'Practice', 'Qualifying'].map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Date</label>
            <input type="date" value={date} onChange={e => setDate(e.target.value)}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent text-sm" />
          </div>

          {/* ── Folder selector ── */}
          <div className="space-y-3">
            <div className="text-xs text-gray-400">
              AiM Export Data *
            </div>

            {/* How-to hint */}
            <div className="bg-surface border border-border rounded-lg px-4 py-3 text-xs text-gray-400 space-y-1">
              <div className="text-white font-bold text-sm mb-1">How to select your data</div>
              <div>
                <span className="text-accent font-bold">Option A (recommended):</span>{' '}
                Click the button below and select the <span className="font-mono text-white">day folder</span> that
                contains all your <span className="font-mono text-white">a_0001_CSV</span>,{' '}
                <span className="font-mono text-white">a_0002_CSV</span> … subfolders.
                All sessions are detected automatically.
              </div>
              <div>
                <span className="text-gray-500">Option B:</span>{' '}
                Select a single <span className="font-mono">a_000X_CSV</span> folder directly.
              </div>
            </div>

            {/* Drop zone + picker */}
            <label
              onDragOver={e => e.preventDefault()}
              onDrop={handleDrop}
              className="block border-2 border-dashed border-accent rounded-lg p-6 text-center
                         hover:bg-accent hover:bg-opacity-5 transition-colors cursor-pointer"
            >
              {entries.length === 0 ? (
                <div className="space-y-1">
                  <div className="text-accent text-3xl">📂</div>
                  <div className="text-accent font-bold text-sm">Click to select folder</div>
                  <div className="text-gray-500 text-xs">or drag &amp; drop your AiM export folder here</div>
                </div>
              ) : (
                <div className="text-accent text-sm font-bold">
                  Click to replace / add more folders
                </div>
              )}
              <input
                key={`picker-${pickerKey}`}
                type="file"
                // @ts-ignore — webkitdirectory is non-standard
                webkitdirectory=""
                directory=""
                multiple
                className="sr-only"
                onChange={handlePick}
              />
            </label>

            {/* Detected session folders */}
            {folders.length > 0 && (
              <div className="space-y-1.5">
                <div className="text-xs text-gray-500 uppercase tracking-wider">
                  Detected session folders ({folders.length})
                </div>
                {folders.map(folder => {
                  const count = entries.filter(e => e.folder === folder).length
                  return (
                    <div key={folder}
                      className="flex items-center justify-between bg-surface border border-border rounded px-3 py-2">
                      <div className="flex items-center gap-2">
                        <span className="text-accent">📁</span>
                        <div>
                          <div className="text-white text-sm font-mono">{folder}</div>
                          <div className="text-gray-500 text-xs">{count} CSV file{count !== 1 ? 's' : ''}</div>
                        </div>
                      </div>
                      <button type="button" onClick={() => removeFolder(folder)}
                        className="text-gray-600 hover:text-red transition-colors text-sm ml-3">
                        ✕
                      </button>
                    </div>
                  )
                })}
                {entries.length > 0 && (
                  <button type="button" onClick={() => setEntries([])}
                    className="text-xs text-gray-600 hover:text-red transition-colors underline">
                    Clear all
                  </button>
                )}
              </div>
            )}
          </div>

          <button type="submit" disabled={loading || entries.length === 0 || missingSetup}
            className="w-full py-3 bg-accent text-bg font-bold rounded hover:opacity-90 disabled:opacity-40 text-sm">
            {loading
              ? 'Uploading...'
              : entries.length > 0
              ? `Upload & Analyse — ${folders.length} session${folders.length !== 1 ? 's' : ''}, ${entries.length} files`
              : 'Select a folder first'}
          </button>
        </form>
      ) : (
        <div className="space-y-4">
          <p className="text-gray-300 text-sm">
            Ingestion in progress — analysing {entries.length} files across{' '}
            {folders.length} session folder{folders.length !== 1 ? 's' : ''}.
            GPS reconstruction, corner detection, and ML run automatically.
          </p>
          <JobProgress jobId={jobId} onDone={() => nav('/sessions')} />
        </div>
      )}
    </div>
  )
}
