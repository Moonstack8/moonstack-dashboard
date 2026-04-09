export const fmt = {
  currency: (val, currency = 'USD') => {
    const n = parseFloat(val) || 0
    return new Intl.NumberFormat('en-US', { style: 'currency', currency, minimumFractionDigits: 2 }).format(n)
  },

  number: (val) => {
    const n = parseFloat(val) || 0
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
    return n.toLocaleString()
  },

  pct: (val) => {
    const n = parseFloat(val) || 0
    return `${n.toFixed(2)}%`
  },

  cpc: (val, currency = 'USD') => fmt.currency(val, currency),

  date: (str) => {
    if (!str) return '—'
    return new Date(str).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  },
}

export const statusColor = (status) => {
  switch (status?.toUpperCase()) {
    case 'ACTIVE': return 'text-green-400'
    case 'PAUSED': return 'text-yellow-400'
    case 'ARCHIVED': return 'text-gray-500'
    case 'DELETED': return 'text-red-500'
    case 'IN_PROCESS': return 'text-blue-400'
    case 'WITH_ISSUES': return 'text-red-400'
    default: return 'text-gray-400'
  }
}

export const statusDot = (status) => {
  switch (status?.toUpperCase()) {
    case 'ACTIVE': return 'bg-green-400'
    case 'PAUSED': return 'bg-yellow-400'
    case 'ARCHIVED': return 'bg-gray-500'
    case 'IN_PROCESS': return 'bg-blue-400'
    case 'WITH_ISSUES': return 'bg-red-400'
    default: return 'bg-gray-500'
  }
}

export const getActions = (actions = [], actionType = 'link_click') => {
  const found = actions.find(a => a.action_type === actionType)
  return found ? parseInt(found.value) : 0
}

export const getConversions = (actions = []) => {
  const convTypes = ['purchase', 'lead', 'complete_registration', 'add_to_cart']
  return actions
    .filter(a => convTypes.some(t => a.action_type?.includes(t)))
    .reduce((sum, a) => sum + parseInt(a.value || 0), 0)
}

export const getRevenue = (actionValues = []) => {
  const found = actionValues.find(a => a.action_type === 'purchase')
  return found ? parseFloat(found.value) : 0
}
