import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { fmt, getConversions, getRevenue, deriveStatus } from '../lib/format'
import MetricCard from '../components/MetricCard'
import DataTable from '../components/DataTable'
import DatePresetPicker from '../components/DatePresetPicker'
import LoadingSpinner from '../components/LoadingSpinner'
import DeleteButton from '../components/DeleteButton'
import OptimizerPanel from '../components/OptimizerPanel'
import StatusToggle from '../components/StatusToggle'
import { ArrowLeft, Zap, ChevronRight } from 'lucide-react'

export default function AdSetView() {
  const { adsetId } = useParams()
  const navigate = useNavigate()
  const [datePreset, setDatePreset] = useState('last_7d')
  const [optimizingAd, setOptimizingAd] = useState(null)
  const queryClient = useQueryClient()

  const { data: adset } = useQuery({
    queryKey: ['adset', adsetId],
    queryFn: () => api.getAdset(adsetId),
    staleTime: 60_000,
  })

  const { data: ads = [], isLoading } = useQuery({
    queryKey: ['ads', adsetId, datePreset],
    queryFn: () => api.getAds(adsetId, datePreset),
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  // If the adset's end_time has passed, all ads are effectively "Completed"
  const adsetCompleted = adset?.end_time && new Date(adset.end_time) < new Date()

  const handleAdDeleted = (id) => {
    queryClient.setQueryData(['ads', adsetId, datePreset], prev =>
      (prev || []).filter(a => a.id !== id)
    )
  }

  const handleAdStatusUpdated = (id, newStatus) => {
    queryClient.setQueryData(['ads', adsetId, datePreset], prev =>
      (prev || []).map(a => a.id === id ? { ...a, status: newStatus, effective_status: newStatus } : a)
    )
  }

  const totalSpend = ads.reduce((s, a) => s + (parseFloat(a.insights?.spend) || 0), 0)
  const totalImpressions = ads.reduce((s, a) => s + (parseInt(a.insights?.impressions) || 0), 0)
  const totalClicks = ads.reduce((s, a) => s + (parseInt(a.insights?.clicks) || 0), 0)
  const avgCtr = totalImpressions > 0 ? (totalClicks / totalImpressions) * 100 : 0
  const avgCpc = totalClicks > 0 ? totalSpend / totalClicks : 0
  const totalConversions = ads.reduce((s, a) => s + getConversions(a.insights?.actions || []), 0)
  const totalRevenue = ads.reduce((s, a) => s + getRevenue(a.insights?.action_values || []), 0)

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
    { key: 'name', label: 'Ad', render: r => <span className="font-medium text-ink">{r.name}</span> },
    { key: 'status', label: 'Status', render: r => {
      const base = deriveStatus(r)
      const s = (base === 'ACTIVE' && adsetCompleted) ? 'COMPLETED' : base
      return <StatusToggle status={s} type="ad" id={r.id} onUpdated={handleAdStatusUpdated} />
    }},
    { key: 'spend', label: 'Spend', align: 'right', render: r => <span className="font-medium">{fmt.currency(r.insights?.spend)}</span> },
    { key: 'impressions', label: 'Impressions', align: 'right', render: r => fmt.number(r.insights?.impressions) },
    { key: 'clicks', label: 'Clicks', align: 'right', render: r => fmt.number(r.insights?.clicks) },
    { key: 'ctr', label: 'CTR', align: 'right', render: r => fmt.pct(r.insights?.ctr) },
    { key: 'cpc', label: 'CPC', align: 'right', render: r => fmt.currency(r.insights?.cpc) },
    { key: 'cpm', label: 'CPM', align: 'right', render: r => fmt.currency(r.insights?.cpm) },
    { key: 'reach', label: 'Reach', align: 'right', render: r => fmt.number(r.insights?.reach) },
    { key: 'frequency', label: 'Freq.', align: 'right', render: r => parseFloat(r.insights?.frequency || 0).toFixed(2) },
    { key: 'arrow', label: '', render: () => <ChevronRight size={14} className="text-gray-600" /> },
    {
      key: 'optimize',
      label: '',
      render: r => (
        <button
          onClick={e => { e.stopPropagation(); setOptimizingAd(r) }}
          className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-yellow-400 hover:bg-yellow-400/10 transition-colors"
          title="Optimize this ad"
        >
          <Zap size={11} />
          Optimize
        </button>
      ),
    },
    { key: 'delete', label: '', render: (r, onDeleted) => <DeleteButton type="ad" id={r.id} onDeleted={onDeleted} /> },
  ]

  // find account_id from first ad (Meta returns it in the ad object)
  const accountId = ads[0]?.account_id || ''

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-ink mb-2 transition-colors"
          >
            <ArrowLeft size={12} /> Back
          </button>
          <p className="text-xs text-gray-500 mb-1">Ad Set</p>
          <h1 className="text-xl font-bold text-ink">{adsetId}</h1>
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
      <div className="bg-elevated border border-rim rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-rim flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">Ads</h2>
          <span className="text-xs text-gray-500">{ads.length} total</span>
        </div>
        {isLoading ? (
          <LoadingSpinner label="Loading ads..." />
        ) : (
          <DataTable
            columns={AD_COLUMNS}
            data={ads}
            onRowClick={row => navigate(`/ads/${row.id}`)}
            onRowAction={handleAdDeleted}
            emptyMessage="No ads found"
          />
        )}
      </div>

      {/* Optimizer slide-over */}
      {optimizingAd && (
        <OptimizerPanel
          ad={optimizingAd}
          accountId={accountId}
          onClose={() => setOptimizingAd(null)}
        />
      )}
    </div>
  )
}
