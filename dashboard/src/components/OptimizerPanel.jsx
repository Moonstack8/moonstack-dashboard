import { useEffect, useRef, useState } from 'react'
import { X, Loader, CheckCircle, Copy, Check, Zap } from 'lucide-react'

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <button
      onClick={handleCopy}
      className="p-1 rounded hover:bg-white/10 transition-colors text-gray-500 hover:text-gray-300"
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
          <p className="text-sm font-semibold text-white">{variation.headline}</p>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600">Primary Text</p>
            <CopyButton text={variation.primary_text} />
          </div>
          <p className="text-sm text-gray-300 leading-relaxed">{variation.primary_text}</p>
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
            <span className="text-xs bg-white/10 text-gray-300 px-2 py-0.5 rounded font-medium">
              {variation.cta_type?.replace(/_/g, ' ')}
            </span>
          </div>
        </div>

        {variation.reasoning && (
          <p className="text-xs text-gray-500 italic border-t border-white/5 pt-2">
            {variation.reasoning}
          </p>
        )}
      </div>
    </div>
  )
}

export default function OptimizerPanel({ ad, accountId, onClose }) {
  const [events, setEvents] = useState([])
  const [variations, setVariations] = useState(null)
  const [isRunning, setIsRunning] = useState(true)
  const [error, setError] = useState(null)
  const textRef = useRef('')
  const esRef = useRef(null)

  useEffect(() => {
    const url = new URL('http://localhost:8000/api/agent/optimize')
    // SSE doesn't support POST body natively — use fetch with ReadableStream
    const controller = new AbortController()

    fetch('http://localhost:8000/api/agent/optimize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ad_id: ad.id, account_id: accountId }),
      signal: controller.signal,
    }).then(async res => {
      if (!res.ok) {
        const text = await res.text()
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
        buffer = lines.pop() // keep incomplete line

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'text') {
              setEvents(prev => [...prev, event])
            } else if (event.type === 'variations') {
              setVariations(event.data.variations)
            } else if (event.type === 'error') {
              setError(event.message)
              setIsRunning(false)
            } else if (event.type === 'done') {
              setIsRunning(false)
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
  }, [ad.id, accountId])

  const analysisText = events
    .filter(e => e.type === 'text')
    .map(e => e.content)
    .join('')

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-full max-w-xl bg-[#13151f] border-l border-white/10 z-50 flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/5 shrink-0">
          <div className="flex items-center gap-2">
            <Zap size={16} className="text-yellow-400" />
            <div>
              <h2 className="text-sm font-semibold text-white">Ad Optimizer</h2>
              <p className="text-xs text-gray-500 truncate max-w-xs">{ad.name}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-gray-400 hover:text-white"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {/* Status */}
          <div className="flex items-center gap-2">
            {isRunning ? (
              <>
                <Loader size={13} className="text-yellow-400 animate-spin shrink-0" />
                <span className="text-xs text-gray-400">Analyzing ad performance...</span>
              </>
            ) : error ? (
              <>
                <span className="text-xs text-red-400">{error}</span>
              </>
            ) : (
              <>
                <CheckCircle size={13} className="text-green-400 shrink-0" />
                <span className="text-xs text-gray-400">Analysis complete</span>
              </>
            )}
          </div>

          {/* Analysis text */}
          {analysisText && (
            <div className="bg-[#1a1d27] border border-white/5 rounded-xl p-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 mb-2">Analysis</p>
              <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{analysisText}</p>
            </div>
          )}

          {/* Loading pulse while waiting */}
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
              <p className="text-xs font-semibold text-white mb-3">Improved Variations</p>
              <div className="space-y-3">
                {variations.map((v, i) => (
                  <VariationCard key={i} variation={v} index={i} />
                ))}
              </div>
            </div>
          )}

          {/* Still streaming variations... */}
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
