export default function LoadingSpinner({ size = 'md', label }) {
  const sz = size === 'sm' ? 'w-4 h-4' : size === 'lg' ? 'w-10 h-10' : 'w-6 h-6'
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <div className={`${sz} border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin`} />
      {label && <p className="text-sm text-gray-500">{label}</p>}
    </div>
  )
}

export function InlineSpinner() {
  return (
    <div className="w-3.5 h-3.5 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin inline-block" />
  )
}
