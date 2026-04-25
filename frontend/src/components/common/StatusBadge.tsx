interface Props { status: string; className?: string }

const COLOR: Record<string, string> = {
  ok: 'bg-green text-bg', pass: 'bg-green text-bg',
  warn: 'bg-gold text-bg', warning: 'bg-gold text-bg', pending: 'bg-gold text-bg',
  critical: 'bg-orange text-bg', fail: 'bg-red text-white', failed: 'bg-red text-white',
  emergency: 'bg-red text-white', done: 'bg-accent text-bg',
  running: 'bg-accent text-bg', verify: 'bg-orange text-bg',
}

export function StatusBadge({ status, className = '' }: Props) {
  const color = COLOR[status.toLowerCase()] ?? 'bg-border text-white'
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold uppercase ${color} ${className}`}>
      {status}
    </span>
  )
}
