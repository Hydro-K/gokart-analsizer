import { useEffect, useRef, useState } from 'react'
import { api, Job } from '../api'

export function useJobPoller(jobId: number | null, intervalMs = 1500) {
  const [job, setJob] = useState<Job | null>(null)
  const [done, setDone] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!jobId) return
    setDone(false)

    const poll = async () => {
      try {
        const j = await api.get<Job>(`/jobs/${jobId}`)
        setJob(j)
        if (j.status === 'done' || j.status === 'failed') {
          setDone(true)
          if (timerRef.current) clearInterval(timerRef.current)
        }
      } catch { /* ignore */ }
    }

    poll()
    timerRef.current = setInterval(poll, intervalMs)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [jobId, intervalMs])

  return { job, done }
}
