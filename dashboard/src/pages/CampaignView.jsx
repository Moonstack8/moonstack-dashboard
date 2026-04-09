import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { fmt, getConversions, getRevenue } from '../lib/format'
import MetricCard from '../components/MetricCard'
import SparkChart from '../components/SparkChart'
import StatusBadge from '../components/StatusBadge'
import DataTable from '../components/DataTable'
import DatePresetPicker from '../components/DatePresetPicker'
import LoadingSpinner from '../components/LoadingSpinner'
import DeleteButton from '../components/DeleteButton'
import { ChevronRight, ArrowLeft } from 'lucide-react'

const ADSET_COLUMNS = [
  { key: 'name', label: 'Ad Set' },
  { key: 'status', label: 'Status', render: r => <StatusBadge status={r.effective_status || r.status} /> },
  { key: 'spend', label: 'Spend', align: 'right', render: r => <span className="font-medium">{fmt.currency(r.insights?.spend)}</span> },
  { key: 'impressions', label: 'Impressions', align: 'right', render: r => fmt.number(r.insights?.impressions) },
  { key: 'clicks', label: 'Clicks', align: 'right', render: r => fmt.number(r.insights?.clicks) },
  { key: 'ctr', label: 'CTR', align: 'right', render: r => fmt.pct(r.insights?.ctr) },
  { key: 'cpc', label: 'CPC', align: 'right', render: r => fmt.currency(r.insights?.cpc) },
  { key: 'cpm', label: 'CPM', align: 'right', render: r => fmt.currency(r.insights?.cpm) },
  { key: 'budget', label: 'Budget', align: 'right', render: r => {
    const b = r.daily_budget || r.lifetime_budget
    return b ? fmt.currency(parseInt(b) / 100) : '—'
  }},
  { key: 'optimization', label: 'Goal', render: r => <span className="text-xs text-gray-400">{r.optimization_goal?.replace(/_/g, ' ')}</span> },
  { key: 'arrow', label: '', render: () => <ChevronRight size={14} className="text-gray-600" /> },
  { key: 'delete', label: '', render: (r, onDeleted) => <DeleteButton type="adset" id={r.id} onDeleted={onDeleted} /> },
]

export default function CampaignView() {
  const { campaignId } = useParams()
  const navigate = useNavigate()
  const [datePreset, setDatePreset] = useState('last_7d')
  const queryClient = useQueryClient()

  const handleAdsetDeleted = (id) => {
    queryClient.setQueryData(['adsets', campaignId, datePreset], prev =>
      (prev || []).filter(a => a.id !== id)
    )
  }

  const { data: timeseries = [], isLoading: loadingTs } = useQuery({
    queryKey: ['campaign-timeseries', campaignId, datePreset],
    queryFn: () => api.getCampaignTimeseries(campaignId, datePreset),
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  const { data: adsets = [], isLoading: loadingAdsets } = useQuery({
    queryKey: ['adsets', campaignId, datePreset],
    queryFn: () => api.getAdSets(campaignId, datePreset),
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  // Aggregate insights from adsets
  const totalSpend = adsets.reduce((s, a) => s + (parseFloat(a.insights?.spend) || 0), 0)
  const totalImpressions = adsets.reduce((s, a) => s + (parseInt(a.insights?.impressions) || 0), 0)
  const totalClicks = adsets.reduce((s, a) => s + (parseInt(a.insights?.clicks) || 0), 0)
  const avgCtr = totalImpressions > 0 ? (totalClicks / totalImpressions) * 100 : 0
  const avgCpc = totalClicks > 0 ? totalSpend / totalClicks : 0
  const avgCpm = totalImpressions > 0 ? (totalSpend / totalImpressions) * 1000 : 0
  const totalConversions = adsets.reduce((s, a) => s + getConversions(a.insights?.actions || []), 0)
  const totalRevenue = adsets.reduce((s, a) => s + getRevenue(a.insights?.action_values || []), 0)

  const firstAdset = adsets[0]
  const campaignName = firstAdset ? `Campaign ${campaignId}` : campaignId

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-white mb-2 transition-colors"
          >
            <ArrowLeft size={12} /> Back
          </button>
          <p className="text-xs text-gray-500 mb-1">Campaign</p>
          <h1 className="text-xl font-bold text-white">{campaignName}</h1>
          <p className="text-xs text-gray-600 mt-0.5">{campaignId}</p>
        </div>
        <DatePresetPicker value={datePreset} onChange={setDatePreset} />
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <MetricCard label="Spend" value={fmt.currency(totalSpend)} highlight />
        <MetricCard label="Impressions" value={fmt.number(totalImpressions)} />
        <MetricCard label="Clicks" value={fmt.number(totalClicks)} />
        <MetricCard label="CTR" value={fmt.pct(avgCtr)} />
        <MetricCard label="CPC" value={fmt.currency(avgCpc)} />
        <MetricCard label="CPM" value={fmt.currency(avgCpm)} />
        {totalConversions > 0 && <MetricCard label="Conversions" value={fmt.number(totalConversions)} />}
        {totalRevenue > 0 && <MetricCard label="Revenue" value={fmt.currency(totalRevenue)} highlight />}
      </div>

      {/* Chart */}
      <div className="bg-[#1a1d27] border border-white/5 rounded-xl p-4 mb-6">
        <h2 className="text-sm font-semibold text-white mb-4">Performance Over Time</h2>
        {loadingTs ? (
          <div className="h-[220px] flex items-center justify-center">
            <LoadingSpinner size="sm" />
          </div>
        ) : timeseries.length === 0 ? (
          <div className="h-[220px] flex items-center justify-center text-gray-600 text-sm">No time series data</div>
        ) : (
          <SparkChart data={timeseries} metrics={['spend', 'impressions', 'clicks']} />
        )}
      </div>

      {/* Ad Sets */}
      <div className="bg-[#1a1d27] border border-white/5 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Ad Sets</h2>
          <span className="text-xs text-gray-500">{adsets.length} total</span>
        </div>
        {loadingAdsets ? (
          <LoadingSpinner label="Loading ad sets..." />
        ) : (
          <DataTable
            columns={ADSET_COLUMNS}
            data={adsets}
            onRowClick={row => navigate(`/adsets/${row.id}`)}
            onRowAction={handleAdsetDeleted}
            emptyMessage="No ad sets found"
          />
        )}
      </div>
    </div>
  )
}
