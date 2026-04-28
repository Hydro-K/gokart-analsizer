import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAuthStore } from '../store/authStore'

interface KartBasic { id: number; name: string }

export default function Reports() {
  const token = useAuthStore(s => s.token)
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [karts, setKarts] = useState<KartBasic[]>([])
  const [downloading, setDownloading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.get<KartBasic[]>('/karts').then(setKarts).catch(() => {})
  }, [])

  async function downloadPdf(url: string, filename: string, key: string) {
    setDownloading(key)
    setError(null)
    try {
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(`${res.status}: ${text}`)
      }
      const blob = await res.blob()
      const objUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = objUrl
      a.download = filename
      a.click()
      URL.revokeObjectURL(objUrl)
    } catch (e: any) {
      setError(e.message ?? 'Download failed')
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Reports</h1>
        <p className="text-gray-400 text-sm mt-1">Generate and download PDF reports for sessions and kart programming sheets.</p>
      </div>

      {error && (
        <div className="rounded-lg border border-red border-opacity-50 bg-surface px-4 py-3 text-red text-sm">
          {error}
        </div>
      )}

      {/* Day Report */}
      <div className="rounded-lg border border-border bg-surface p-5 space-y-4">
        <h2 className="text-white font-semibold">Race Day Report</h2>
        <p className="text-gray-400 text-xs">
          Multi-page PDF with session overview, lap time chart, tire pressure log, energy usage, and ML-generated recommendations.
        </p>
        <div className="flex items-center gap-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Date</label>
            <input
              type="date"
              value={date}
              onChange={e => setDate(e.target.value)}
              className="bg-bg border border-border rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-accent"
            />
          </div>
          <button
            disabled={!!downloading}
            onClick={() => downloadPdf(
              `/api/reports/day/${date}`,
              `day_report_${date.replace(/-/g, '')}.pdf`,
              'day',
            )}
            className="mt-5 px-4 py-1.5 bg-accent text-bg text-sm font-bold rounded hover:bg-opacity-90 transition-colors disabled:opacity-50"
          >
            {downloading === 'day' ? 'Generating...' : 'Download PDF'}
          </button>
        </div>
      </div>

      {/* Alltrax program sheets */}
      <div className="rounded-lg border border-border bg-surface p-5 space-y-4">
        <h2 className="text-white font-semibold">Alltrax Controller Program Sheets</h2>
        <p className="text-gray-400 text-xs">
          Printable PDF with all Alltrax SR settings, throttle curve, and tire pressure targets for each kart.
        </p>
        {karts.length === 0 ? (
          <p className="text-gray-500 text-sm">No karts found. Add karts first.</p>
        ) : (
          <div className="space-y-2">
            {karts.map(k => (
              <div key={k.id} className="flex items-center justify-between rounded border border-border bg-bg px-4 py-3">
                <span className="text-white text-sm font-medium">{k.name}</span>
                <button
                  disabled={!!downloading}
                  onClick={() => downloadPdf(
                    `/api/reports/alltrax/${k.id}/program-sheet`,
                    `alltrax_${k.name.replace(/\s+/g, '_')}.pdf`,
                    `kart-${k.id}`,
                  )}
                  className="px-3 py-1 border border-accent border-opacity-50 text-accent text-xs rounded hover:bg-accent hover:text-bg transition-colors disabled:opacity-50"
                >
                  {downloading === `kart-${k.id}` ? 'Generating...' : 'Download Program Sheet'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
