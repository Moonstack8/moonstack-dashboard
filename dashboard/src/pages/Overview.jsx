import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { fmt, getConversions, getRevenue } from '../lib/format'
import MetricCard from '../components/MetricCard'
import StatusBadge from '../components/StatusBadge'
import DatePresetPicker from '../components/DatePresetPicker'
import LoadingSpinner from '../components/LoadingSpinner'
import { DollarSign, Eye, MousePointer, TrendingUp, Users, BarChart2 } from 'lucide-react'

function sumInsight(overviews, key) {
  return overviews.reduce((sum, o) => sum + (parseFloat(o.insights?.[key]) || 0), 0)
}

export default function Overview() {
  const [datePreset, setDatePreset] = useState('last_7d')
  const navigate = useNavigate()

  const { data: accounts = [], isLoading: loadingAccounts } = useQuery({
    queryKey: ['accounts'],
    queryFn: api.getAccounts,
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  const overviewQueries = useQuery({
    queryKey: ['all-overviews', datePreset, accounts.map(a => a.id).join(',')],
    queryFn: () =>
      Promise.all(accounts.map(a => api.getAccountOverview(a.id, datePreset))),
    enabled: accounts.length > 0,
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  const overviews = overviewQueries.data || []

  const totalSpend = sumInsight(overviews, 'spend')
  const totalImpressions = sumInsight(overviews, 'impressions')
  const totalClicks = sumInsight(overviews, 'clicks')
  const totalReach = sumInsight(overviews, 'reach')
  const avgCtr = totalImpressions > 0 ? (totalClicks / totalImpressions) * 100 : 0
  const avgCpc = totalClicks > 0 ? totalSpend / totalClicks : 0
  const avgCpm = totalImpressions > 0 ? (totalSpend / totalImpressions) * 1000 : 0
  const totalConversions = overviews.reduce((sum, o) => sum + getConversions(o.insights?.actions || []), 0)
  const totalRevenue = overviews.reduce((sum, o) => sum + getRevenue(o.insights?.action_values || []), 0)
  const roas = totalSpend > 0 ? totalRevenue / totalSpend : 0

  if (loadingAccounts) return <LoadingSpinner label="Loading accounts..." />

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">Overview</h1>
          <p className="text-sm text-gray-500 mt-0.5">{accounts.length} account{accounts.length !== 1 ? 's' : ''} connected</p>
        </div>
        <DatePresetPicker value={datePreset} onChange={setDatePreset} />
      </div>

      {/* Top metrics */}
      {overviewQueries.isLoading ? (
        <LoadingSpinner label="Fetching insights..." />
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <MetricCard label="Total Spend" value={fmt.currency(totalSpend)} icon={DollarSign} highlight />
            <MetricCard label="Impressions" value={fmt.number(totalImpressions)} icon={Eye} />
            <MetricCard label="Clicks" value={fmt.number(totalClicks)} icon={MousePointer} />
            <MetricCard label="Reach" value={fmt.number(totalReach)} icon={Users} />
            <MetricCard label="CTR" value={fmt.pct(avgCtr)} icon={TrendingUp} />
            <MetricCard label="CPC" value={fmt.currency(avgCpc)} />
            <MetricCard label="CPM" value={fmt.currency(avgCpm)} />
            <MetricCard label="ROAS" value={roas > 0 ? `${roas.toFixed(2)}x` : '—'} icon={BarChart2} />
          </div>

          {totalConversions > 0 && (
            <div className="grid grid-cols-2 gap-3 mb-6">
              <MetricCard label="Conversions" value={fmt.number(totalConversions)} />
              <MetricCard label="Revenue" value={fmt.currency(totalRevenue)} highlight />
            </div>
          )}
        </>
      )}

      {/* Per-account breakdown */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Accounts
        </h2>
        <div className="space-y-2">
          {accounts.map((acct, i) => {
            const ov = overviews[i]
            const ins = ov?.insights || {}
            return (
              <div
                key={acct.id}
                onClick={() => navigate(`/accounts/${acct.id}`)}
                className="bg-[#1a1d27] border border-white/5 rounded-xl px-4 py-3 flex items-center justify-between cursor-pointer hover:border-white/10 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-brand-500/20 flex items-center justify-center text-brand-400 text-xs font-bold shrink-0">
                    {acct.name?.[0]?.toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-white truncate">{acct.name}</p>
                    <p className="text-xs text-gray-500">{acct.id} · {acct.currency}</p>
                  </div>
                </div>
                <div className="flex items-center gap-6 shrink-0 ml-4">
                  <div className="text-right hidden sm:block">
                    <p className="text-xs text-gray-500">Spend</p>
                    <p className="text-sm font-semibold text-white">{fmt.currency(ins.spend, acct.currency)}</p>
                  </div>
                  <div className="text-right hidden md:block">
                    <p className="text-xs text-gray-500">Impressions</p>
                    <p className="text-sm font-semibold text-white">{fmt.number(ins.impressions)}</p>
                  </div>
                  <div className="text-right hidden lg:block">
                    <p className="text-xs text-gray-500">CTR</p>
                    <p className="text-sm font-semibold text-white">{fmt.pct(ins.ctr)}</p>
                  </div>
                  <div className="text-right hidden lg:block">
                    <p className="text-xs text-gray-500">CPC</p>
                    <p className="text-sm font-semibold text-white">{fmt.currency(ins.cpc, acct.currency)}</p>
                  </div>
                  <StatusBadge status={acct.account_status === 1 ? 'ACTIVE' : 'PAUSED'} />
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
