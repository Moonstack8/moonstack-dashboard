import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { fmt } from '../lib/format'
import { useTheme } from '../lib/theme'

const COLORS = {
  spend: '#3b5bdb',
  impressions: '#0ea5e9',
  clicks: '#10b981',
  ctr: '#f59e0b',
  cpc: '#ec4899',
  cpm: '#8b5cf6',
}

function formatValue(metric, value) {
  if (metric === 'spend' || metric === 'cpc' || metric === 'cpm') return fmt.currency(value)
  if (metric === 'ctr') return `${value.toFixed(2)}%`
  return fmt.number(value)
}

function formatTick(metric, value) {
  if (metric === 'spend' || metric === 'cpc' || metric === 'cpm') {
    if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`
    return `$${value.toFixed(0)}`
  }
  if (metric === 'ctr') return `${value.toFixed(1)}%`
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`
  return value
}

const CustomTooltip = ({ active, payload, label, metric }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-elevated border border-rim-2 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-gray-400 mb-1">{label}</p>
      <div className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full" style={{ background: COLORS[metric] }} />
        <span className="text-ink/70 capitalize">{metric}:</span>
        <span className="text-ink font-medium">{formatValue(metric, payload[0].value)}</span>
      </div>
    </div>
  )
}

export default function SparkChart({ data = [], metric = 'spend' }) {
  const { theme } = useTheme()
  const color = COLORS[metric] ?? '#3b5bdb'
  const gridStroke = theme === 'light' ? '#00000008' : '#ffffff08'

  const formatted = data.map(d => ({
    date: fmt.date(d.date_start),
    value: metric === 'spend' || metric === 'cpc' || metric === 'cpm'
      ? parseFloat(d[metric] || 0)
      : metric === 'ctr'
      ? parseFloat(d[metric] || 0)
      : parseInt(d[metric] || 0),
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={formatted} margin={{ top: 5, right: 10, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={`grad-${metric}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.3} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
        <XAxis
          dataKey="date"
          tick={{ fill: '#6b7280', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fill: '#6b7280', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={48}
          tickFormatter={v => formatTick(metric, v)}
        />
        <Tooltip content={<CustomTooltip metric={metric} />} />
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          fill={`url(#grad-${metric})`}
          dot={false}
          activeDot={{ r: 4, strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
