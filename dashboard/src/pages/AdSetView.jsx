import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { fmt, getConversions, getRevenue } from '../lib/format'
import MetricCard from '../components/MetricCard'
import StatusBadge from '../components/StatusBadge'
import DataTable from '../components/DataTable'
import DatePresetPicker from '../components/DatePresetPicker'
import LoadingSpinner from '../components/LoadingSpinner'
import DeleteButton from '../components/DeleteButton'
import { ArrowLeft } from 'lucide-react'

const AD_COLUMNS = [
  {
    key: 'thumbnail',
    label: '',
    render: r => r.creative?.thumbnail_url ? (
      <img src={r.creative.thumbnail_url} alt="" className="w-10 h-10 rounded object-cover bg-gray-800" />
    ) : (
      <div className="w-10 h-10 rounded bg-gray-800 flex items-center justify-center text-gray-600 text-xs">Ad</div>
    ),
  },
  { key: 'name', label: 'Ad', render: r => <span className="font-medium text-white">{r.name}</span> },
  { key: 'status', label: 'Status', render: r => <StatusBadge status={r.effective_status || r.status} /> },
  { key: 'spend', label: 'Spend', align: 'right', render: r => <span className="font-medium">{fmt.currency(r.insights?.spend)}</span> },
  { key: 'impressions', label: 'Impressions', align: 'right', render: r => fmt.number(r.insights?.impressions) },
  { key: 'clicks', label: 'Clicks', align: 'right', render: r => fmt.number(r.insights?.clicks) },
  { key: 'ctr', label: 'CTR', align: 'right', render: r => fmt.pct(r.insights?.ctr) },
  { key: 'cpc', label: 'CPC', align: 'right', render: r => fmt.currency(r.insights?.cpc) },
  { key: 'cpm', label: 'CPM', align: 'right', render: r => fmt.currency(r.insights?.cpm) },
  { key: 'reach', label: 'Reach', align: 'right', render: r => fmt.number(r.insights?.reach) },
  { key: 'frequency', label: 'Freq.', align: 'right', render: r => parseFloat(r.insights?.frequency || 0).toFixed(2) },
  { key: 'delete', label: '', render: (r, onDeleted) => <DeleteButton type="ad" id={r.id} onDeleted={onDeleted} /> },
]

export default function AdSetView() {
  const { adsetId } = useParams()
  const navigate = useNavigate()
  const [datePreset, setDatePreset] = useState('last_7d')
  const queryClient = useQueryClient()

  const { data: ads = [], isLoading } = useQuery({
    queryKey: ['ads', adsetId, datePreset],
    queryFn: () => api.getAds(adsetId, datePreset),
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  const handleAdDeleted = (id) => {
    queryClient.setQueryData(['ads', adsetId, datePreset], prev =>
      (prev || []).filter(a => a.id !== id)
    )
  }

  const totalSpend = ads.reduce((s, a) => s + (parseFloat(a.insights?.spend) || 0), 0)
  const totalImpressions = ads.reduce((s, a) => s + (parseInt(a.insights?.impressions) || 0), 0)
  const totalClicks = ads.reduce((s, a) => s + (parseInt(a.insights?.clicks) || 0), 0)
  const avgCtr = totalImpressions > 0 ? (totalClicks / totalImpressions) * 100 : 0
  const avgCpc = totalClicks > 0 ? totalSpend / totalClicks : 0
  const totalConversions = ads.reduce((s, a) => s + getConversions(a.insights?.actions || []), 0)
  const totalRevenue = ads.reduce((s, a) => s + getRevenue(a.insights?.action_values || []), 0)

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
          <p className="text-xs text-gray-500 mb-1">Ad Set</p>
          <h1 className="text-xl font-bold text-white">{adsetId}</h1>
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
        <MetricCard label="Ads" value={ads.length} />
        {totalConversions > 0 && <MetricCard label="Conversions" value={fmt.number(totalConversions)} />}
        {totalRevenue > 0 && <MetricCard label="Revenue" value={fmt.currency(totalRevenue)} highlight />}
      </div>

      {/* Ads table */}
      <div className="bg-[#1a1d27] border border-white/5 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Ads</h2>
          <span className="text-xs text-gray-500">{ads.length} total</span>
        </div>
        {isLoading ? (
          <LoadingSpinner label="Loading ads..." />
        ) : (
          <DataTable
            columns={AD_COLUMNS}
            data={ads}
            onRowAction={handleAdDeleted}
            emptyMessage="No ads found"
          />
        )}
      </div>
    </div>
  )
}
