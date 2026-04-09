import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { fmt, getConversions, getRevenue } from '../lib/format'
import MetricCard from '../components/MetricCard'
import SparkChart from '../components/SparkChart'
import StatusBadge from '../components/StatusBadge'
import DataTable from '../components/DataTable'
import DatePresetPicker from '../components/DatePresetPicker'
import LoadingSpinner from '../components/LoadingSpinner'
import { DollarSign, Eye, MousePointer, TrendingUp, ChevronRight } from 'lucide-react'

const CHART_METRICS = ['spend', 'impressions', 'clicks']

const CAMPAIGN_COLUMNS = [
  { key: 'name', label: 'Campaign' },
  { key: 'status', label: 'Status', render: r => <StatusBadge status={r.effective_status || r.status} /> },
  { key: 'objective', label: 'Objective', render: r => <span className="text-xs text-gray-400">{r.objective?.replace(/_/g, ' ')}</span> },
  { key: 'spend', label: 'Spend', align: 'right', render: r => <span className="font-medium">{fmt.currency(r.insights?.spend)}</span> },
  { key: 'impressions', label: 'Impressions', align: 'right', render: r => fmt.number(r.insights?.impressions) },
  { key: 'clicks', label: 'Clicks', align: 'right', render: r => fmt.number(r.insights?.clicks) },
  { key: 'ctr', label: 'CTR', align: 'right', render: r => fmt.pct(r.insights?.ctr) },
  { key: 'cpc', label: 'CPC', align: 'right', render: r => fmt.currency(r.insights?.cpc) },
  { key: 'cpm', label: 'CPM', align: 'right', render: r => fmt.currency(r.insights?.cpm) },
  { key: 'budget', label: 'Budget', align: 'right', render: r => {
    const b = r.daily_budget || r.lifetime_budget
    return b ? fmt.currency(parseInt(b) / 100) : <span className="text-gray-600">CBO</span>
  }},
  { key: 'arrow', label: '', render: () => <ChevronRight size={14} className="text-gray-600" /> },
]

export default function AccountView() {
  const { accountId } = useParams()
  const navigate = useNavigate()
  const [datePreset, setDatePreset] = useState('last_7d')
  const [chartMetrics, setChartMetrics] = useState(CHART_METRICS)

  const { data: overview, isLoading: loadingOv } = useQuery({
    queryKey: ['account-overview', accountId, datePreset],
    queryFn: () => api.getAccountOverview(accountId, datePreset),
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  const { data: timeseries = [], isLoading: loadingTs } = useQuery({
    queryKey: ['account-timeseries', accountId, datePreset],
    queryFn: () => api.getAccountTimeseries(accountId, datePreset),
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  const { data: campaigns = [], isLoading: loadingCampaigns } = useQuery({
    queryKey: ['campaigns', accountId, datePreset],
    queryFn: () => api.getCampaigns(accountId, datePreset),
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  const ins = overview?.insights || {}
  const info = overview?.info || {}

  const conversions = getConversions(ins.actions || [])
  const revenue = getRevenue(ins.action_values || [])
  const roas = parseFloat(ins.spend) > 0 ? revenue / parseFloat(ins.spend) : 0

  if (loadingOv) return <LoadingSpinner label="Loading account..." />

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-xs text-gray-500 mb-1">Account</p>
          <h1 className="text-xl font-bold text-white">{info.name || accountId}</h1>
          <p className="text-xs text-gray-600 mt-0.5">{accountId} · {info.currency} · {info.timezone_name}</p>
        </div>
        <DatePresetPicker value={datePreset} onChange={setDatePreset} />
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <MetricCard label="Spend" value={fmt.currency(ins.spend, info.currency)} icon={DollarSign} highlight />
        <MetricCard label="Impressions" value={fmt.number(ins.impressions)} icon={Eye} />
        <MetricCard label="Clicks" value={fmt.number(ins.clicks)} icon={MousePointer} />
        <MetricCard label="Reach" value={fmt.number(ins.reach)} />
        <MetricCard label="CTR" value={fmt.pct(ins.ctr)} icon={TrendingUp} />
        <MetricCard label="CPC" value={fmt.currency(ins.cpc, info.currency)} />
        <MetricCard label="CPM" value={fmt.currency(ins.cpm, info.currency)} />
        <MetricCard label="Frequency" value={parseFloat(ins.frequency || 0).toFixed(2)} />
        {conversions > 0 && <MetricCard label="Conversions" value={fmt.number(conversions)} />}
        {revenue > 0 && <MetricCard label="Revenue" value={fmt.currency(revenue, info.currency)} highlight />}
        {roas > 0 && <MetricCard label="ROAS" value={`${roas.toFixed(2)}x`} />}
        {info.amount_spent && (
          <MetricCard
            label="Total Spent (All Time)"
            value={fmt.currency(parseInt(info.amount_spent) / 100, info.currency)}
          />
        )}
      </div>

      {/* Chart */}
      <div className="bg-[#1a1d27] border border-white/5 rounded-xl p-4 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-white">Performance Over Time</h2>
          <div className="flex items-center gap-2">
            {CHART_METRICS.map(m => (
              <button
                key={m}
                onClick={() =>
                  setChartMetrics(prev =>
                    prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m]
                  )
                }
                className={`text-xs px-2 py-1 rounded-md border transition-colors ${
                  chartMetrics.includes(m)
                    ? 'border-brand-500/50 bg-brand-500/10 text-brand-400'
                    : 'border-white/10 text-gray-600'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
        {loadingTs ? (
          <div className="h-[220px] flex items-center justify-center">
            <LoadingSpinner size="sm" />
          </div>
        ) : timeseries.length === 0 ? (
          <div className="h-[220px] flex items-center justify-center text-gray-600 text-sm">
            No time series data
          </div>
        ) : (
          <SparkChart data={timeseries} metrics={chartMetrics.length ? chartMetrics : ['spend']} />
        )}
      </div>

      {/* Campaigns */}
      <div className="bg-[#1a1d27] border border-white/5 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Campaigns</h2>
          <span className="text-xs text-gray-500">{campaigns.length} total</span>
        </div>
        {loadingCampaigns ? (
          <LoadingSpinner label="Loading campaigns..." />
        ) : (
          <DataTable
            columns={CAMPAIGN_COLUMNS}
            data={campaigns}
            onRowClick={row => navigate(`/campaigns/${row.id}`)}
            emptyMessage="No campaigns found"
          />
        )}
      </div>
    </div>
  )
}
