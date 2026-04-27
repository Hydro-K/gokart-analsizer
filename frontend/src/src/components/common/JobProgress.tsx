import { useJobPoller } from '../../hooks/useJobPoller'
import { StatusBadge } from './StatusBadge'

interface Props { jobId: number | null; onDone?: () => void }

export function JobProgress({ jobId, onDone }: Props) {
  const { job, done } = useJobPoller(jobId)

  if (!jobId) return null

  if (done && onDone && job?.status === 'done') {
    setTimeout(onDone, 500)
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-3 flex items-center gap-3">
      {!done && (
        <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm text-white font-mono">
          Job #{jobId} — {job?.type ?? '...'}
        </div>
        {job?.error_msg && (
          <div className="text-xs text-red mt-1 truncate">{job.error_msg}</div>
        )}
      </div>
      {job && <StatusBadge status={job.status} />}
    </div>
  )
}
