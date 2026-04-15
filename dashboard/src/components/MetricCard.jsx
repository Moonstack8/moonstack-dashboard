export default function MetricCard({ label, value, sub, trend, icon: Icon, highlight }) {
  return (
    <div
      className={`rounded-xl p-4 border transition-colors ${
        highlight
          ? 'bg-brand-500/10 border-brand-500/30'
          : 'bg-elevated border-rim hover:border-rim-2'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">{label}</p>
        {Icon && (
          <div className="w-7 h-7 rounded-lg bg-ink/5 flex items-center justify-center shrink-0">
            <Icon size={14} className="text-gray-400" />
          </div>
        )}
      </div>
      <p className={`text-2xl font-bold mt-2 ${highlight ? 'text-brand-400' : 'text-ink'}`}>
        {value ?? '—'}
      </p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
      {trend !== undefined && (
        <p className={`text-xs mt-1 font-medium ${trend >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {trend >= 0 ? '↑' : '↓'} {Math.abs(trend).toFixed(1)}% vs prev period
        </p>
      )}
    </div>
  )
}
