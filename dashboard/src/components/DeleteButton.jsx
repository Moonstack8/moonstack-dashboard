import { useState } from 'react'
import { Trash2, Loader } from 'lucide-react'
import axios from 'axios'

const BASE_URL = 'http://localhost:8000'

const ENDPOINTS = {
  ad: (id) => `/api/ads/${id}`,
  adset: (id) => `/api/adsets/${id}`,
  campaign: (id) => `/api/campaigns/${id}`,
}

export default function DeleteButton({ type, id, onDeleted }) {
  const [confirming, setConfirming] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleDelete = async (e) => {
    e.stopPropagation()
    if (!confirming) {
      setConfirming(true)
      // Auto-cancel confirm state after 3s
      setTimeout(() => setConfirming(false), 3000)
      return
    }
    setLoading(true)
    try {
      await axios.delete(`${BASE_URL}${ENDPOINTS[type](id)}`)
      onDeleted?.(id)
    } catch (err) {
      alert(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
      setConfirming(false)
    }
  }

  if (loading) {
    return <Loader size={13} className="text-gray-500 animate-spin" />
  }

  return (
    <button
      onClick={handleDelete}
      className={`flex items-center gap-1 text-xs px-2 py-1 rounded transition-colors ${
        confirming
          ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
          : 'text-gray-600 hover:text-red-400 hover:bg-red-500/10'
      }`}
    >
      <Trash2 size={12} />
      {confirming ? 'Confirm?' : ''}
    </button>
  )
}
