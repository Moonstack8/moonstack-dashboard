import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { fmt, getConversions, getRevenue, deriveStatus } from '../lib/format'
import MetricCard from '../components/MetricCard'
import SparkChart from '../components/SparkChart'
import StatusToggle from '../components/StatusToggle'
import DatePresetPicker from '../components/DatePresetPicker'
import DeleteButton from '../components/DeleteButton'
import OptimizerPanel from '../components/OptimizerPanel'
import LoadingSpinner from '../components/LoadingSpinner'
import { ArrowLeft, Zap, ExternalLink } from 'lucide-react'

const CHART_METRICS = [
  { key: 'spend', label: 'Spend' },
  { key: 'impressions', label: 'Impressions' },
  { key: 'clicks', label: 'Clicks' },
]

export default function AdView() {
  const { adId } = useParams()
  const navigate = useNavigate()
  const [datePreset, setDatePreset] = useState('last_30d')
  const [chartMetric, setChartMetric] = useState('spend')
  const [optimizing, setOptimizing] = useState(false)

  const { data: ad, isLoading } = useQuery({
    queryKey: ['ad', adId],
    queryFn: () => api.getAd(adId),
    staleTime: 30_000,
  })

  const { data: timeseries = [], isLoading: loadingTs } = useQuery({
    queryKey: ['ad-timeseries', adId, datePreset],
    queryFn: () => api.getAdTimeseries(adId, datePreset),
    staleTime: 15_000,
  })

  if (isLoading) return <LoadingSpinner label="Loading ad..." />

  const ins = ad?.insights || {}
  const creative = ad?.creative || {}
  const linkData = creative?.object_story_spec?.link_data || {}

  const headline = linkData.name || ''
  const primaryText = linkData.message || ''
  const description = linkData.description || ''
  const cta = linkData.call_to_action?.type || ''
  const destinationUrl = linkData.link || ''
  const thumbnailUrl = creative.thumbnail_url

  const conversions = getConversions(ins.actions || [])
  const revenue = getRevenue(ins.action_values || [])

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
          <p className="text-xs text-gray-500 mb-1">Ad</p>
          <h1 className="text-xl font-bold text-ink">{ad?.name}</h1>
          <p className="text-xs text-gray-600 mt-0.5">{adId}</p>
        </div>
        <div className="flex items-center gap-2">
          <DatePresetPicker value={datePreset} onChange={setDatePreset} />
          <button
            onClick={() => setOptimizing(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-yellow-400 bg-yellow-400/10 hover:bg-yellow-400/20 transition-colors"
          >
            <Zap size={14} />
            Optimize
          </button>
          <DeleteButton type="ad" id={adId} onDeleted={() => navigate(-1)} />
        </div>
      </div>

      {/* Creative + copy */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* Thumbnail */}
        <div className="bg-elevated border border-rim rounded-xl overflow-hidden flex items-center justify-center min-h-[200px]">
          {thumbnailUrl ? (
            <img src={thumbnailUrl} alt="Ad creative" className="w-full h-full object-cover" />
          ) : (
            <span className="text-gray-600 text-sm">No preview</span>
          )}
        </div>

        {/* Copy details */}
        <div className="lg:col-span-2 bg-elevated border border-rim rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Creative Copy</p>
            <StatusToggle status={deriveStatus(ad)} type="ad" id={adId} />
          </div>

          {headline && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 mb-1">Headline</p>
              <p className="text-sm font-semibold text-ink">{headline}</p>
            </div>
          )}

          {primaryText && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 mb-1">Primary Text</p>
              <p className="text-sm text-ink/70 leading-relaxed">{primaryText}</p>
            </div>
          )}

          {description && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 mb-1">Description</p>
              <p className="text-sm text-gray-400">{description}</p>
            </div>
          )}

          <div className="flex items-center gap-4 pt-1">
            {cta && (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 mb-1">CTA</p>
                <span className="text-xs bg-ink/10 text-ink/70 px-2 py-0.5 rounded font-medium">
                  {cta.replace(/_/g, ' ')}
                </span>
              </div>
            )}
            {destinationUrl && (
              <div className="flex-1 min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 mb-1">Destination</p>
                <a
                  href={destinationUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 truncate transition-colors"
                >
                  <ExternalLink size={10} className="shrink-0" />
                  {destinationUrl}
                </a>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <MetricCard label="Spend" value={fmt.currency(ins.spend)} highlight />
        <MetricCard label="Impressions" value={fmt.number(ins.impressions)} />
        <MetricCard label="Clicks" value={fmt.number(ins.clicks)} />
        <MetricCard label="CTR" value={fmt.pct(ins.ctr)} />
        <MetricCard label="CPC" value={fmt.currency(ins.cpc)} />
        <MetricCard label="CPM" value={fmt.currency(ins.cpm)} />
        <MetricCard label="Reach" value={fmt.number(ins.reach)} />
        <MetricCard label="Frequency" value={parseFloat(ins.frequency || 0).toFixed(2)} />
        {conversions > 0 && <MetricCard label="Conversions" value={fmt.number(conversions)} />}
        {revenue > 0 && <MetricCard label="Revenue" value={fmt.currency(revenue)} highlight />}
      </div>

      {/* Chart */}
      <div className="bg-elevated border border-rim rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-ink">Performance Over Time</h2>
          <div className="flex items-center gap-1 bg-ink/5 rounded-lg p-0.5">
            {CHART_METRICS.map(m => (
              <button
                key={m.key}
                onClick={() => setChartMetric(m.key)}
                className={`text-xs px-3 py-1 rounded-md transition-colors ${
                  chartMetric === m.key
                    ? 'bg-ink/10 text-ink font-medium'
                    : 'text-gray-500 hover:text-ink/70'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
        {loadingTs ? (
          <div className="h-[220px] flex items-center justify-center">
            <LoadingSpinner size="sm" />
          </div>
        ) : timeseries.length === 0 ? (
          <div className="h-[220px] flex items-center justify-center text-gray-600 text-sm">No data for this period</div>
        ) : (
          <SparkChart data={timeseries} metric={chartMetric} />
        )}
      </div>

      {/* Optimizer */}
      {optimizing && (
        <OptimizerPanel
          ad={ad}
          accountId={ad?.account_id}
          onClose={() => setOptimizing(false)}
        />
      )}
    </div>
  )
}
