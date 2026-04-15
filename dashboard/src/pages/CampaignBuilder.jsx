import { useState, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import AgentStream from '../components/AgentStream'
import CampaignPlanPreview from '../components/CampaignPlanPreview'
import { Sparkles, RotateCcw, CheckCircle2 } from 'lucide-react'
import axios from 'axios'

const BASE_URL = 'http://localhost:8000'

const EXAMPLE_BRIEFS = [
  'Launch a TOFU traffic campaign for Moonstack (trymoonstack.com), a SaaS tool that helps marketers create better ads with AI. Target startup founders and digital marketers aged 25-45 in the US. Budget $10/day.',
  'Create a lead gen campaign for a local dentist in Miami, FL. Target adults 30-60 in the Miami metro area. Goal is new patient bookings. $20/day budget.',
  'Run a retargeting awareness campaign for an e-commerce sneaker brand. Target men 18-35 in the US who are interested in streetwear and sneakers. $50/day CBO.',
]

export default function CampaignBuilder() {
  const [brief, setBrief] = useState('')
  const [accountId, setAccountId] = useState('')
  const [events, setEvents] = useState([])
  const [plan, setPlan] = useState(null)
  const [isRunning, setIsRunning] = useState(false)
  const [imageFiles, setImageFiles] = useState({})   // adIndex -> File
  const [imagePreviews, setImagePreviews] = useState({})  // adIndex -> dataURL
  const [imageHashes, setImageHashes] = useState({})  // adIndex -> hash
  const [isUploading, setIsUploading] = useState({})
  const [isExecuting, setIsExecuting] = useState(false)
  const [execResult, setExecResult] = useState(null)
  const [error, setError] = useState(null)
  const abortRef = useRef(null)

  const { data: accounts = [] } = useQuery({
    queryKey: ['accounts'],
    queryFn: api.getAccounts,
    staleTime: 60_000,
  })

  const { data: pages = [] } = useQuery({
    queryKey: ['pages', accountId],
    queryFn: () => axios.get(`${BASE_URL}/api/accounts/${accountId}/pages`).then(r => r.data),
    enabled: !!accountId,
    staleTime: 60_000,
  })

  const reset = () => {
    setEvents([])
    setPlan(null)
    setImageFiles({})
    setImagePreviews({})
    setImageHashes({})
    setIsUploading({})
    setExecResult(null)
    setError(null)
  }

  const handleGenerate = async () => {
    if (!brief.trim() || !accountId) return
    reset()
    setIsRunning(true)
    setError(null)

    try {
      const response = await fetch(`${BASE_URL}/api/agent/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brief, account_id: accountId }),
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      abortRef.current = reader

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value)
        const lines = text.split('\n')

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'plan') {
              setPlan(event.data)
            } else if (event.type === 'done') {
              break
            } else if (event.type === 'error') {
              setError(event.message)
            } else {
              setEvents(prev => [...prev, event])
            }
          } catch {}
        }
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setIsRunning(false)
    }
  }

  const handleImageUpload = async (adIndex, file, preview) => {
    setImagePreviews(prev => ({ ...prev, [String(adIndex)]: preview }))
    setImageFiles(prev => ({ ...prev, [String(adIndex)]: file }))
    setIsUploading(prev => ({ ...prev, [String(adIndex)]: true }))

    try {
      // Upload image via the backend
      const formData = new FormData()
      formData.append('file', file)
      formData.append('account_id', accountId)

      const r = await axios.post(`${BASE_URL}/api/upload-image`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setImageHashes(prev => ({ ...prev, [String(adIndex)]: r.data.image_hash }))
    } catch (e) {
      setError(`Image upload failed: ${e.response?.data?.detail || e.message}`)
    } finally {
      setIsUploading(prev => ({ ...prev, [String(adIndex)]: false }))
    }
  }

  const handleExecute = async (pageId) => {
    if (!plan || !pageId) return
    setIsExecuting(true)
    setError(null)
    try {
      const r = await axios.post(`${BASE_URL}/api/agent/execute`, {
        plan,
        account_id: accountId,
        page_id: pageId,
        image_hashes: imageHashes,
      })
      setExecResult(r.data)
    } catch (e) {
      const detail = e.response?.data?.detail
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail) || e.message)
    } finally {
      setIsExecuting(false)
    }
  }

  // Success screen
  if (execResult) {
    return (
      <div className="max-w-lg mx-auto mt-16 text-center">
        <div className="w-14 h-14 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
          <CheckCircle2 size={28} className="text-green-400" />
        </div>
        <h2 className="text-xl font-bold text-ink mb-2">Campaign Launched!</h2>
        <p className="text-sm text-gray-400 mb-6">All objects created and PAUSED. Review in Ads Manager before activating.</p>
        <div className="bg-elevated border border-rim rounded-xl p-4 text-left space-y-2 mb-6">
          <p className="text-xs text-gray-500">Campaign ID: <span className="text-white font-mono">{execResult.campaign_id}</span></p>
          {execResult.adset_ids?.map((id, i) => (
            <p key={id} className="text-xs text-gray-500">Ad Set {i + 1}: <span className="text-white font-mono">{id}</span></p>
          ))}
          {execResult.ad_ids?.map((id, i) => (
            <p key={id} className="text-xs text-gray-500">Ad {i + 1}: <span className="text-white font-mono">{id}</span></p>
          ))}
        </div>
        <div className="space-y-2 text-left">
          {execResult.log?.map((line, i) => (
            <p key={i} className="text-xs text-gray-400 font-mono">{line}</p>
          ))}
        </div>
        <button onClick={reset} className="mt-6 px-4 py-2 bg-brand-500 hover:bg-brand-600 text-ink text-sm rounded-lg transition-colors">
          Build Another
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-ink flex items-center gap-2">
          <Sparkles size={20} className="text-brand-400" />
          Campaign Builder
        </h1>
        <p className="text-sm text-gray-500 mt-1">Describe a client brief — the agent plans the campaign, you review and launch.</p>
      </div>

      {/* Input */}
      {!plan && (
        <div className="bg-elevated border border-rim rounded-xl p-4 mb-4">
          {/* Account selector */}
          <div className="mb-3">
            <label className="text-xs text-gray-500 block mb-1.5">Ad Account</label>
            <select
              value={accountId}
              onChange={e => setAccountId(e.target.value)}
              className="w-full bg-surface border border-rim-2 rounded-lg px-3 py-2 text-sm text-ink"
            >
              <option value="">Select account...</option>
              {accounts.map(a => (
                <option key={a.id} value={a.id}>{a.name} ({a.id})</option>
              ))}
            </select>
          </div>

          {/* Brief */}
          <div className="mb-3">
            <label className="text-xs text-gray-500 block mb-1.5">Client Brief</label>
            <textarea
              value={brief}
              onChange={e => setBrief(e.target.value)}
              placeholder="Describe the client, their product, target audience, budget, and campaign goal..."
              rows={5}
              className="w-full bg-surface border border-rim-2 rounded-lg px-3 py-2.5 text-sm text-ink placeholder-gray-600 resize-none focus:outline-none focus:border-brand-500/50"
            />
          </div>

          {/* Example briefs */}
          <div className="mb-4">
            <p className="text-xs text-gray-600 mb-2">Examples:</p>
            <div className="flex flex-col gap-1.5">
              {EXAMPLE_BRIEFS.map((ex, i) => (
                <button
                  key={i}
                  onClick={() => setBrief(ex)}
                  className="text-left text-xs text-gray-500 hover:text-ink/70 bg-ink/[0.03] hover:bg-ink/5 rounded-lg px-3 py-2 transition-colors line-clamp-2"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleGenerate}
            disabled={!brief.trim() || !accountId || isRunning}
            className={`w-full py-2.5 rounded-lg text-sm font-semibold transition-colors flex items-center justify-center gap-2 ${
              brief.trim() && accountId && !isRunning
                ? 'bg-brand-500 hover:bg-brand-600 text-ink'
                : 'bg-ink/5 text-gray-600 cursor-not-allowed'
            }`}
          >
            <Sparkles size={15} />
            {isRunning ? 'Generating plan...' : 'Generate Campaign Plan'}
          </button>
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 mb-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Agent stream */}
      {events.length > 0 && (
        <div className="mb-4">
          <AgentStream events={events} isRunning={isRunning} />
        </div>
      )}

      {/* Plan preview */}
      {plan && !isRunning && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-ink">Campaign Plan — Review & Launch</h2>
            <button
              onClick={reset}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-ink transition-colors"
            >
              <RotateCcw size={12} /> Start over
            </button>
          </div>
          <CampaignPlanPreview
            plan={plan}
            pages={pages}
            onImageUpload={handleImageUpload}
            imageHashes={imageHashes}
            onExecute={handleExecute}
            isExecuting={isExecuting}
          />
        </div>
      )}
    </div>
  )
}
