import { useState } from 'react'
import { Upload, X, ImageIcon } from 'lucide-react'
import StatusBadge from './StatusBadge'
import { fmt } from '../lib/format'

function ImageSlot({ adIndex, adName, onUpload, hash }) {
  const [dragging, setDragging] = useState(false)

  const handleFile = async (file) => {
    if (!file) return
    // Read as base64 data URL for preview, pass raw file to parent
    const reader = new FileReader()
    reader.onload = () => onUpload(adIndex, file, reader.result)
    reader.readAsDataURL(file)
  }

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]) }}
      className={`relative border-2 border-dashed rounded-lg p-4 flex flex-col items-center justify-center gap-2 cursor-pointer transition-colors min-h-[100px] ${
        dragging ? 'border-brand-500 bg-brand-500/10' :
        hash ? 'border-green-500/50 bg-green-500/5' :
        'border-white/10 hover:border-white/20'
      }`}
    >
      <input
        type="file"
        accept="image/*"
        className="absolute inset-0 opacity-0 cursor-pointer"
        onChange={e => handleFile(e.target.files[0])}
      />
      {hash ? (
        <>
          <ImageIcon size={20} className="text-green-400" />
          <p className="text-xs text-green-400 font-medium">Image ready</p>
          <p className="text-[10px] text-gray-600 font-mono truncate max-w-full">{hash}</p>
        </>
      ) : (
        <>
          <Upload size={18} className="text-gray-500" />
          <p className="text-xs text-gray-500 text-center">Drop image or click<br /><span className="text-gray-600">for {adName}</span></p>
        </>
      )}
    </div>
  )
}

export default function CampaignPlanPreview({ plan, pages, onImageUpload, imageHashes, onExecute, isExecuting }) {
  const [selectedPage, setSelectedPage] = useState(pages[0]?.id || '')
  const readyCount = plan.ads.filter((_, i) => imageHashes[String(i)]).length
  const allImagesReady = readyCount > 0

  return (
    <div className="space-y-4">
      {/* Rationale */}
      <div className="bg-brand-500/10 border border-brand-500/20 rounded-xl p-4">
        <p className="text-xs font-semibold text-brand-400 uppercase tracking-wider mb-1">Strategy</p>
        <p className="text-sm text-gray-300">{plan.rationale}</p>
      </div>

      {/* Campaign */}
      <div className="bg-[#1a1d27] border border-white/5 rounded-xl p-4">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Campaign</p>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-white font-medium">{plan.campaign.name}</p>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-xs text-gray-400">{plan.campaign.objective.replace('OUTCOME_', '')}</span>
              <span className="text-xs text-gray-600">·</span>
              <span className="text-xs text-gray-400">{plan.campaign.budget_type}</span>
            </div>
          </div>
          <div className="text-right">
            <p className="text-white font-semibold">{fmt.currency(plan.campaign.daily_budget_usd)}/day</p>
            <StatusBadge status="PAUSED" />
          </div>
        </div>
      </div>

      {/* Ad Sets */}
      <div className="bg-[#1a1d27] border border-white/5 rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 border-b border-white/5">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Ad Sets ({plan.adsets.length})</p>
        </div>
        {plan.adsets.map((adset, i) => (
          <div key={i} className="px-4 py-3 border-b border-white/5 last:border-0">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-white font-medium">{adset.name}</p>
                <div className="flex flex-wrap gap-2 mt-1.5">
                  <span className="text-xs bg-white/5 text-gray-400 px-2 py-0.5 rounded">
                    {adset.optimization_goal.replace(/_/g, ' ')}
                  </span>
                  {adset.targeting?.age_min && (
                    <span className="text-xs bg-white/5 text-gray-400 px-2 py-0.5 rounded">
                      Age {adset.targeting.age_min}–{adset.targeting.age_max}
                    </span>
                  )}
                  {adset.targeting?.geo_locations?.countries && (
                    <span className="text-xs bg-white/5 text-gray-400 px-2 py-0.5 rounded">
                      {adset.targeting.geo_locations.countries.join(', ')}
                    </span>
                  )}
                  {adset.targeting?.interests?.slice(0, 3).map(int => (
                    <span key={int.id} className="text-xs bg-white/5 text-gray-400 px-2 py-0.5 rounded">
                      {int.name}
                    </span>
                  ))}
                </div>
              </div>
              {adset.daily_budget_usd && (
                <p className="text-sm text-white font-semibold">{fmt.currency(adset.daily_budget_usd)}/day</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Ads + Image Upload */}
      <div className="bg-[#1a1d27] border border-white/5 rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 border-b border-white/5">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Ads ({plan.ads.length}) — Upload an image for each</p>
        </div>
        <div className="divide-y divide-white/5">
          {plan.ads.map((ad, i) => (
            <div key={i} className={`p-4 grid grid-cols-[1fr_140px] gap-4 ${!imageHashes[String(i)] ? 'opacity-50' : ''}`}>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <p className="text-sm text-white font-medium">{ad.name}</p>
                  {!imageHashes[String(i)] && (
                    <span className="text-[10px] text-gray-600 bg-white/5 px-1.5 py-0.5 rounded">will skip</span>
                  )}
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-gray-400">
                    <span className="text-gray-600">Headline: </span>
                    {ad.headline}
                  </p>
                  <p className="text-xs text-gray-400">
                    <span className="text-gray-600">Copy: </span>
                    {ad.primary_text}
                  </p>
                  <p className="text-xs text-gray-400">
                    <span className="text-gray-600">CTA: </span>
                    {ad.cta_type.replace(/_/g, ' ')}
                    <span className="text-gray-600 ml-2">→</span>
                    <span className="text-blue-400 ml-1">{ad.destination_url}</span>
                  </p>
                </div>
              </div>
              <ImageSlot
                adIndex={i}
                adName={ad.name}
                onUpload={onImageUpload}
                hash={imageHashes[String(i)]}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Page selector + Launch */}
      <div className="bg-[#1a1d27] border border-white/5 rounded-xl p-4">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Facebook Page</p>
        {pages.length > 0 ? (
          <select
            value={selectedPage}
            onChange={e => setSelectedPage(e.target.value)}
            className="w-full bg-[#13151f] border border-white/10 rounded-lg px-3 py-2 text-sm text-white mb-4"
          >
            {pages.map(p => (
              <option key={p.id} value={p.id}>{p.name} ({p.id})</option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            placeholder="Enter Facebook Page ID"
            value={selectedPage}
            onChange={e => setSelectedPage(e.target.value)}
            className="w-full bg-[#13151f] border border-white/10 rounded-lg px-3 py-2 text-sm text-white mb-4"
          />
        )}

        <button
          onClick={() => onExecute(selectedPage)}
          disabled={!allImagesReady || !selectedPage || isExecuting}
          className={`w-full py-2.5 rounded-lg text-sm font-semibold transition-colors ${
            allImagesReady && selectedPage && !isExecuting
              ? 'bg-brand-500 hover:bg-brand-600 text-white'
              : 'bg-white/5 text-gray-600 cursor-not-allowed'
          }`}
        >
          {isExecuting ? 'Launching...' :
           !allImagesReady ? 'Upload at least one image to launch' :
           `🚀 Launch ${readyCount} of ${plan.ads.length} ad${readyCount !== 1 ? 's' : ''} (PAUSED)`}
        </button>
      </div>
    </div>
  )
}
