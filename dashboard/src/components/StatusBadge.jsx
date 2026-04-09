import { statusDot, statusColor } from '../lib/format'

export default function StatusBadge({ status }) {
  const label = status?.replace(/_/g, ' ') ?? 'UNKNOWN'
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${statusColor(status)}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${statusDot(status)}`} />
      {label}
    </span>
  )
}
