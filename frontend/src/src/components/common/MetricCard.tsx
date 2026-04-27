interface Props {
  label: string
  value: string | number
  unit?: string
  highlight?: boolean
  tooltip?: string
}

export function MetricCard({ label, value, unit, highlight, tooltip }: Props) {
  return (
    <div
      title={tooltip}
      className={`rounded-lg p-3 border ${highlight ? 'border-accent' : 'border-border'} bg-surface flex flex-col gap-1`}
    >
      <span className="text-xs text-gray-400 uppercase tracking-wider">{label}</span>
      <span className={`text-2xl font-bold font-mono ${highlight ? 'text-accent' : 'text-white'}`}>
        {value}
        {unit && <span className="text-sm text-gray-400 ml-1">{unit}</span>}
      </span>
    </div>
  )
}
