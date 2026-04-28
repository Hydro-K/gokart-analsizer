import { useEffect, useState, FormEvent } from 'react'
import { api, Track } from '../api'
import { TrackCanvas } from '../components/track/TrackCanvas'

export default function Tracks() {
  const [tracks, setTracks]       = useState<Track[]>([])
  const [selected, setSelected]   = useState<Track | null>(null)
  const [trackXY, setTrackXY]     = useState<number[][] | null>(null)
  const [form, setForm]           = useState({ name: '' })
  const [error, setError]         = useState('')

  const load = () => api.get<Track[]>('/tracks').then(setTracks).catch(() => {})
  useEffect(() => { load() }, [])

  const selectTrack = async (t: Track) => {
    setSelected(t)
    setTrackXY(null)
    try {
      const map = await api.get<{ local_xy: number[][] }>(`/tracks/${t.id}/map`)
      setTrackXY(map.local_xy)
    } catch { setTrackXY(null) }
  }

  const create = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    try {
      await api.post('/tracks', form)
      setForm({ name: '' }); load()
    } catch (err: any) { setError(err.message) }
  }

  const [rebuilding, setRebuilding] = useState<number | null>(null)
  const reconstruct = async (t: Track) => {
    setRebuilding(t.id)
    try {
      await api.post(`/tracks/${t.id}/reconstruct`, {})
      await selectTrack(t)
      load()
    } catch (err: any) { alert(err.message) }
    finally { setRebuilding(null) }
  }

  const del = async (id: number) => {
    if (!confirm('Delete track?')) return
    try { await api.delete(`/tracks/${id}`); load() }
    catch (err: any) { alert(err.message) }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Tracks</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-4">
          <form onSubmit={create} className="space-y-3 bg-surface border border-border rounded-lg p-4">
            <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Add Track</h2>
            {error && <div className="text-red text-sm">{error}</div>}
            <input placeholder="Track name" required value={form.name} onChange={e => setForm({ name: e.target.value })}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            <button type="submit" className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">
              Add Track
            </button>
          </form>

          <div className="space-y-2">
            {tracks.map(t => (
              <div key={t.id}
                onClick={() => selectTrack(t)}
                className={`flex items-center gap-3 rounded-lg border px-4 py-3 cursor-pointer transition-colors ${
                  selected?.id === t.id ? 'border-accent bg-accent bg-opacity-5' : 'border-border bg-surface hover:border-accent'
                }`}>
                <div className="flex-1 min-w-0">
                  <div className="text-white font-medium">{t.name}</div>
                  {t.length_m && <div className="text-xs text-gray-400">{(t.length_m * 0.000621371).toFixed(3)} mi</div>}
                </div>
                <button onClick={e => { e.stopPropagation(); reconstruct(t) }}
                  disabled={rebuilding === t.id}
                  className="text-xs text-gray-500 hover:text-accent transition-colors px-2 disabled:opacity-40">
                  {rebuilding === t.id ? '...' : 'Rebuild Map'}
                </button>
                <button onClick={e => { e.stopPropagation(); del(t.id) }}
                  className="text-xs text-gray-500 hover:text-red transition-colors">
                  Delete
                </button>
              </div>
            ))}
            {tracks.length === 0 && <p className="text-gray-400 text-sm">No tracks yet.</p>}
          </div>
        </div>

        <div>
          <h2 className="text-lg font-bold text-white mb-3">Track Map</h2>
          <div className="bg-surface border border-border rounded-lg" style={{ height: 400 }}>
            {trackXY ? (
              <TrackCanvas xy={trackXY} width={400} height={400} />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                {selected ? 'No GPS map available — upload a session with GPS data first.' : 'Select a track to view map.'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
