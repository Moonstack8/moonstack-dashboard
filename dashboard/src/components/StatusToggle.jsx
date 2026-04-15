import { useState, useEffect } from 'react'
import { Loader } from 'lucide-react'
import { api } from '../lib/api'
import { statusDot, statusColor } from '../lib/format'

// Only allow toggling ACTIVE ↔ PAUSED. Other statuses (DELETED, WITH_ISSUES, etc.) are read-only.
const TOGGLEABLE = new Set(['ACTIVE', 'PAUSED'])

export default function StatusToggle({ status: initialStatus, type, id, onUpdated }) {
  const [status, setStatus] = useState(initialStatus)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Sync with fresh data from React Query refetches (don't override while a toggle is in flight)
  useEffect(() => {
    if (!loading) setStatus(initialStatus)
  }, [initialStatus])

  const canToggle = TOGGLEABLE.has(status)

  const handleToggle = async (e) => {
    e.stopPropagation()
    if (!canToggle || loading) return
    const next = status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE'
    setLoading(true)
    setError(null)
    try {
      await api.updateStatus(type, id, next)
      setStatus(next)
      onUpdated?.(id, next)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Update failed')
      setTimeout(() => setError(null), 3000)
    } finally {
      setLoading(false)
    }
  }

  const label = status?.replace(/_/g, ' ') ?? 'UNKNOWN'

  if (!canToggle) {
    return (
      <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${statusColor(status)}`}>
        <span className={`w-1.5 h-1.5 rounded-full ${statusDot(status)}`} />
        {label}
      </span>
    )
  }

  return (
    <button
      onClick={handleToggle}
      disabled={loading}
      title={status === 'ACTIVE' ? 'Click to pause' : 'Click to activate'}
      className={`inline-flex items-center gap-1.5 text-xs font-medium rounded px-1.5 py-0.5 -mx-1.5 -my-0.5 transition-colors hover:bg-ink/[0.08] ${statusColor(status)} ${loading ? 'opacity-60' : ''}`}
    >
      {loading ? (
        <Loader size={10} className="animate-spin shrink-0" />
      ) : (
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${statusDot(status)}`} />
      )}
      {error || label}
    </button>
  )
}
