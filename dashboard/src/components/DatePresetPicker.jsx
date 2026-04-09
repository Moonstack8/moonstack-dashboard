const PRESETS = [
  { label: 'Today', value: 'today' },
  { label: 'Yesterday', value: 'yesterday' },
  { label: '7d', value: 'last_7d' },
  { label: '14d', value: 'last_14d' },
  { label: '30d', value: 'last_30d' },
  { label: '90d', value: 'last_90d' },
]

export default function DatePresetPicker({ value, onChange }) {
  return (
    <div className="flex items-center gap-1 bg-[#1a1d27] rounded-lg p-1 border border-white/5">
      {PRESETS.map(p => (
        <button
          key={p.value}
          onClick={() => onChange(p.value)}
          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
            value === p.value
              ? 'bg-brand-500 text-white'
              : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}
