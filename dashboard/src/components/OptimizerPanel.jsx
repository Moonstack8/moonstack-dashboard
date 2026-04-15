import { useEffect, useState } from 'react'
import { X, Loader, CheckCircle, Copy, Check, Zap, Sparkles, RefreshCw } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const CACHE_KEY = (adId) => `optimizer_cache_${adId}`

function loadCache(adId) {
  try {
    const raw = localStorage.getItem(CACHE_KEY(adId))
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function saveCache(adId, data) {
  try {
    localStorage.setItem(CACHE_KEY(adId), JSON.stringify({ ...data, cachedAt: new Date().toISOString() }))
  } catch {}
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
      className="p-1 rounded hover:bg-ink/10 transition-colors text-gray-500 hover:text-ink/70"
      title="Copy"
    >
      {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
    </button>
  )
}

function VariationCard({ variation, index }) {
  const colors = ['border-blue-500/30 bg-blue-500/5', 'border-purple-500/30 bg-purple-500/5', 'border-green-500/30 bg-green-500/5']
  const labelColors = ['text-blue-400', 'text-purple-400', 'text-green-400']

  return (
    <div className={`border rounded-xl p-4 ${colors[index % colors.length]}`}>
      <div className="flex items-center justify-between mb-3">
        <span className={`text-xs font-semibold uppercase tracking-wider ${labelColors[index % labelColors.length]}`}>
          {variation.angle}
        </span>
        <span className="text-xs text-gray-500">Variation {index + 1}</span>
      </div>

      <div className="space-y-3">
        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600">Headline</p>
            <CopyButton text={variation.headline} />
          </div>
          <p className="text-sm font-semibold text-ink">{variation.headline}</p>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600">Primary Text</p>
            <CopyButton text={variation.primary_text} />
          </div>
          <p className="text-sm text-ink/70 leading-relaxed">{variation.primary_text}</p>
        </div>

        {variation.description && (
          <div>
            <div className="flex items-center justify-between mb-1">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600">Description</p>
              <CopyButton text={variation.description} />
            </div>
            <p className="text-sm text-gray-400">{variation.description}</p>
          </div>
        )}

        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 mb-1">CTA</p>
            <span className="text-xs bg-ink/10 text-ink/70 px-2 py-0.5 rounded font-medium">
              {variation.cta_type?.replace(/_/g, ' ')}
            </span>
          </div>
        </div>

        {variation.reasoning && (
          <p className="text-xs text-gray-500 italic border-t border-rim pt-2">
            {variation.reasoning}
          </p>
        )}

        {variation.suggested_prompt && (
          <div className="border-t border-rim pt-3 mt-1">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-gray-600">
                <Sparkles size={10} />
                Campaign Brief
              </div>
              <CopyButton text={variation.suggested_prompt} />
            </div>
            <p className="text-xs text-gray-400 leading-relaxed bg-ink/[0.03] rounded-lg px-3 py-2 border border-rim">
              {variation.suggested_prompt}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default function OptimizerPanel({ ad, accountId, onClose }) {
  const cached = loadCache(ad.id)

  const [events, setEvents] = useState(cached ? [{ type: 'text', content: cached.analysisText }] : [])
  const [variations, setVariations] = useState(cached?.variations ?? null)
  const [isRunning, setIsRunning] = useState(!cached)
  const [error, setError] = useState(null)
  const [cachedAt, setCachedAt] = useState(cached?.cachedAt ?? null)
  const [forceRerun, setForceRerun] = useState(false)

  const shouldStream = !cached || forceRerun

  useEffect(() => {
    if (!shouldStream) return

    // Clear stale state on rerun
    setEvents([])
    setVariations(null)
    setError(null)
    setIsRunning(true)
    setCachedAt(null)

    const controller = new AbortController()
    let collectedText = ''
    let collectedVariations = null

    fetch('http://localhost:8000/api/agent/optimize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ad_id: ad.id, account_id: accountId }),
      signal: controller.signal,
    }).then(async res => {
      if (!res.ok) {
        setError(`Server error: ${res.status}`)
        setIsRunning(false)
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'text') {
              collectedText += event.content
              setEvents(prev => [...prev, event])
            } else if (event.type === 'variations') {
              collectedVariations = event.data.variations
              setVariations(collectedVariations)
            } else if (event.type === 'error') {
              setError(event.message)
              setIsRunning(false)
            } else if (event.type === 'done') {
              setIsRunning(false)
              if (collectedVariations) {
                const now = new Date().toISOString()
                saveCache(ad.id, { analysisText: collectedText, variations: collectedVariations })
                setCachedAt(now)
              }
            }
          } catch {}
        }
      }
      setIsRunning(false)
    }).catch(err => {
      if (err.name !== 'AbortError') {
        setError(err.message)
        setIsRunning(false)
      }
    })

    return () => controller.abort()
  }, [ad.id, accountId, forceRerun])

  const analysisText = events.filter(e => e.type === 'text').map(e => e.content).join('')

  return (
    <>
      <div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} />

      <div className="fixed right-0 top-0 h-full w-full max-w-xl bg-surface border-l border-rim-2 z-50 flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-rim shrink-0">
          <div className="flex items-center gap-2">
            <Zap size={16} className="text-yellow-400" />
            <div>
              <h2 className="text-sm font-semibold text-ink">Ad Optimizer</h2>
              <p className="text-xs text-gray-500 truncate max-w-xs">{ad.name}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!isRunning && (
              <button
                onClick={() => setForceRerun(v => !v)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-gray-400 hover:text-ink hover:bg-ink/[0.08] transition-colors"
                title="Re-run optimization"
              >
                <RefreshCw size={12} />
                Re-run
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-ink/10 transition-colors text-gray-400 hover:text-ink"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {/* Status bar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {isRunning ? (
                <>
                  <Loader size={13} className="text-yellow-400 animate-spin shrink-0" />
                  <span className="text-xs text-gray-400">Analyzing ad performance...</span>
                </>
              ) : error ? (
                <span className="text-xs text-red-400">{error}</span>
              ) : (
                <>
                  <CheckCircle size={13} className="text-green-400 shrink-0" />
                  <span className="text-xs text-gray-400">Analysis complete</span>
                </>
              )}
            </div>
            {cachedAt && !isRunning && (
              <span className="text-[10px] text-gray-600">
                cached {new Date(cachedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>

          {/* Analysis text */}
          {analysisText && (
            <div className="bg-elevated border border-rim rounded-xl p-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 mb-3">Analysis</p>
              <div className="prose-analysis text-sm text-ink/80 leading-relaxed">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h3: ({ children }) => <p className="text-xs font-bold text-ink uppercase tracking-wider mt-4 mb-1 first:mt-0">{children}</p>,
                    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                    strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
                    em: ({ children }) => <em className="italic text-ink/60">{children}</em>,
                    ul: ({ children }) => <ul className="list-disc list-inside space-y-0.5 mb-2">{children}</ul>,
                    li: ({ children }) => <li className="text-ink/70">{children}</li>,
                    table: ({ children }) => (
                      <div className="overflow-x-auto my-3">
                        <table className="w-full text-xs border-collapse">{children}</table>
                      </div>
                    ),
                    thead: ({ children }) => <thead>{children}</thead>,
                    th: ({ children }) => <th className="text-left py-1.5 px-2 text-[10px] font-semibold uppercase tracking-wider text-gray-500 border-b border-rim">{children}</th>,
                    td: ({ children }) => <td className="py-1.5 px-2 border-b border-rim text-ink/70">{children}</td>,
                    hr: () => <hr className="border-rim my-3" />,
                  }}
                >
                  {analysisText}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {isRunning && !analysisText && (
            <div className="flex items-center gap-1.5 py-2">
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" style={{ animationDelay: '0.2s' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" style={{ animationDelay: '0.4s' }} />
            </div>
          )}

          {/* Variations */}
          {variations && (
            <div>
              <p className="text-xs font-semibold text-ink mb-3">Improved Variations</p>
              <div className="space-y-3">
                {variations.map((v, i) => (
                  <VariationCard key={i} variation={v} index={i} />
                ))}
              </div>
            </div>
          )}

          {isRunning && analysisText && !variations && (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Loader size={11} className="animate-spin" />
              Generating variations...
            </div>
          )}
        </div>
      </div>
    </>
  )
}
