import { Search, Globe, Users, CheckCircle, ChevronDown, ChevronUp, Loader } from 'lucide-react'
import { useState } from 'react'

const TOOL_META = {
  search_interests: { icon: Search, label: 'Searching interests', color: 'text-blue-400' },
  search_geo: { icon: Globe, label: 'Looking up locations', color: 'text-green-400' },
  estimate_audience: { icon: Users, label: 'Estimating audience', color: 'text-purple-400' },
  submit_plan: { icon: CheckCircle, label: 'Submitting plan', color: 'text-brand-400' },
}

function ToolCallRow({ event }) {
  const [open, setOpen] = useState(false)
  const meta = TOOL_META[event.tool] || { icon: Search, label: event.tool, color: 'text-gray-400' }
  const Icon = meta.icon

  return (
    <div className="border border-white/5 rounded-lg overflow-hidden mb-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-white/3 transition-colors"
      >
        <Icon size={13} className={meta.color} />
        <span className={`font-medium ${meta.color}`}>{meta.label}</span>
        <span className="text-gray-600 ml-1 truncate max-w-xs">
          {event.input && JSON.stringify(event.input).slice(0, 60)}...
        </span>
        <span className="ml-auto">
          {open ? <ChevronUp size={12} className="text-gray-600" /> : <ChevronDown size={12} className="text-gray-600" />}
        </span>
      </button>
      {open && (
        <div className="px-3 pb-3 border-t border-white/5">
          <pre className="text-xs text-gray-400 mt-2 overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(event.input, null, 2)}
          </pre>
          {event.result && (
            <>
              <p className="text-xs text-gray-600 mt-2 mb-1">Result:</p>
              <pre className="text-xs text-gray-400 overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(event.result, null, 2)}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default function AgentStream({ events, isRunning }) {
  // Pair tool_call events with their tool_result
  const resultMap = {}
  events.forEach(e => {
    if (e.type === 'tool_result') resultMap[e.tool] = e.result
  })

  const rendered = []
  let skipNext = false

  events.forEach((e, i) => {
    if (skipNext) { skipNext = false; return }
    if (e.type === 'tool_call') {
      rendered.push(
        <ToolCallRow
          key={i}
          event={{ ...e, result: events.find((r, ri) => ri > i && r.type === 'tool_result' && r.tool === e.tool)?.result }}
        />
      )
    } else if (e.type === 'text') {
      rendered.push(
        <p key={i} className="text-sm text-gray-300 leading-relaxed mb-3 whitespace-pre-wrap">
          {e.content}
        </p>
      )
    }
  })

  return (
    <div className="bg-[#1a1d27] border border-white/5 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-4">
        {isRunning ? (
          <Loader size={14} className="text-brand-400 animate-spin" />
        ) : (
          <CheckCircle size={14} className="text-green-400" />
        )}
        <span className="text-sm font-medium text-white">
          {isRunning ? 'Agent is planning...' : 'Planning complete'}
        </span>
      </div>

      <div className="max-h-80 overflow-y-auto space-y-1 pr-1">
        {rendered}
        {isRunning && (
          <div className="flex items-center gap-2 text-xs text-gray-500 mt-2">
            <span className="w-1 h-1 rounded-full bg-brand-400 animate-pulse" />
            <span className="w-1 h-1 rounded-full bg-brand-400 animate-pulse" style={{ animationDelay: '0.2s' }} />
            <span className="w-1 h-1 rounded-full bg-brand-400 animate-pulse" style={{ animationDelay: '0.4s' }} />
          </div>
        )}
      </div>
    </div>
  )
}
