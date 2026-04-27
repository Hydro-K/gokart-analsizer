interface Props { pct: number; status: string }

const BAR_COLOR: Record<string, string> = {
  ok: 'bg-green', warn: 'bg-gold', critical: 'bg-orange', emergency: 'bg-red',
}

export function StorageBar({ pct, status }: Props) {
  const color = BAR_COLOR[status] ?? 'bg-green'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-border rounded-full overflow-hidden">
        <div className={`h-full ${color} transition-all`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="text-xs font-mono text-gray-400 w-12 text-right">{pct.toFixed(1)}%</span>
    </div>
  )
}
