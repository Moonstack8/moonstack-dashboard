import { NavLink } from 'react-router-dom'
import { LayoutDashboard, TrendingUp, Users, ChevronRight, Sparkles } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'

export default function Sidebar() {
  const { data: accounts = [] } = useQuery({
    queryKey: ['accounts'],
    queryFn: api.getAccounts,
    staleTime: 60_000,
  })

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-[#13151f] border-r border-white/5 flex flex-col z-40">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-white/5">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-brand-500 flex items-center justify-center">
            <TrendingUp size={14} className="text-white" />
          </div>
          <span className="text-white font-semibold text-sm tracking-wide">AdPilot</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 px-3">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2 rounded-lg text-sm mb-1 transition-colors ${
              isActive
                ? 'bg-brand-500/20 text-brand-400'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`
          }
        >
          <LayoutDashboard size={16} />
          Overview
        </NavLink>

        <NavLink
          to="/builder"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2 rounded-lg text-sm mb-1 transition-colors ${
              isActive
                ? 'bg-brand-500/20 text-brand-400'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`
          }
        >
          <Sparkles size={16} />
          Campaign Builder
        </NavLink>

        {/* Accounts */}
        <div className="mt-4">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-gray-600 px-3 mb-2">
            Accounts
          </p>
          {accounts.length === 0 && (
            <p className="text-xs text-gray-600 px-3">No accounts found</p>
          )}
          {accounts.map(acct => (
            <NavLink
              key={acct.id}
              to={`/accounts/${acct.id}`}
              className={({ isActive }) =>
                `flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm mb-0.5 transition-colors ${
                  isActive
                    ? 'bg-brand-500/20 text-brand-400'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`
              }
            >
              <div className="flex items-center gap-2 min-w-0">
                <Users size={14} className="shrink-0" />
                <span className="truncate text-xs">{acct.name}</span>
              </div>
              <ChevronRight size={12} className="shrink-0 opacity-50" />
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-white/5">
        <p className="text-[10px] text-gray-600">Auto-refresh every 30s</p>
      </div>
    </aside>
  )
}
