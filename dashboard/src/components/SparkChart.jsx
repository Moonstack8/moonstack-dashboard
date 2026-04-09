import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { fmt } from '../lib/format'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-[#1e2130] border border-white/10 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-gray-400 mb-1">{label}</p>
      {payload.map(p => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-gray-300 capitalize">{p.name}:</span>
          <span className="text-white font-medium">
            {p.name === 'spend' ? fmt.currency(p.value) : fmt.number(p.value)}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function SparkChart({ data = [], metrics = ['spend', 'impressions', 'clicks'] }) {
  const COLORS = {
    spend: '#3b5bdb',
    impressions: '#0ea5e9',
    clicks: '#10b981',
    ctr: '#f59e0b',
    cpc: '#ec4899',
    cpm: '#8b5cf6',
  }

  const formatted = data.map(d => ({
    ...d,
    date: fmt.date(d.date_start),
    spend: parseFloat(d.spend || 0),
    impressions: parseInt(d.impressions || 0),
    clicks: parseInt(d.clicks || 0),
    ctr: parseFloat(d.ctr || 0),
    cpc: parseFloat(d.cpc || 0),
    cpm: parseFloat(d.cpm || 0),
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={formatted} margin={{ top: 5, right: 10, bottom: 0, left: 0 }}>
        <defs>
          {metrics.map(m => (
            <linearGradient key={m} id={`grad-${m}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={COLORS[m]} stopOpacity={0.3} />
              <stop offset="95%" stopColor={COLORS[m]} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
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
          width={45}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: '11px', color: '#9ca3af', paddingTop: '8px' }}
        />
        {metrics.map(m => (
          <Area
            key={m}
            type="monotone"
            dataKey={m}
            stroke={COLORS[m]}
            strokeWidth={2}
            fill={`url(#grad-${m})`}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  )
}
