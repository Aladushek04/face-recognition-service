import { useState } from 'react'
import { Search, Download, Loader2, CheckCircle2, AlertCircle, Calendar, Film } from 'lucide-react'
import { searchStashdb, importStashdbPerformer } from '../lib/api'
import { useUiPreferences } from '../lib/uiPreferences'

interface StashPerformer {
  id: string
  name: string
  disambiguation: string | null
  gender: string
  birth_date: string | null
  scene_count: number
  breast_type: string | null
  image_url: string | null
}

export function StashImportPanel() {
  const { t } = useUiPreferences()
  const [query, setQuery] = useState('')
  const [performers, setPerformers] = useState<StashPerformer[]>([])
  const [count, setCount] = useState(0)

  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Track importing states by performer ID
  const [importingId, setImportingId] = useState<string | null>(null)
  const [importResult, setImportResult] = useState<{
    id: string
    status: 'imported' | 'exists'
    imagesDownloaded: number
    facesIndexed: number
  } | null>(null)

  // Number of reference images to download per performer (individual selection)
  const [imageCounts, setImageCounts] = useState<Record<string, number>>({})

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!query.trim()) return

    setIsLoading(true)
    setError(null)
    setImportResult(null)
    try {
      const data = await searchStashdb(query.trim(), 1, 30)
      setPerformers(data.performers)
      setCount(data.count)

      
      // Initialize image counts
      const counts: Record<string, number> = {}
      data.performers.forEach(p => {
        counts[p.id] = 3 // default to 3 images
      })
      setImageCounts(counts)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search StashDB. Check API key in .env.')
      setPerformers([])
      setCount(0)
    } finally {
      setIsLoading(false)
    }
  }

  const handleImport = async (performerId: string) => {
    setImportingId(performerId)
    setError(null)
    setImportResult(null)
    const imgCount = imageCounts[performerId] ?? 3
    try {
      const res = await importStashdbPerformer(performerId, { imageCount: imgCount })
      setImportResult({
        id: performerId,
        status: res.status,
        imagesDownloaded: res.images_downloaded,
        facesIndexed: res.faces_indexed
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setImportingId(null)
    }
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Download size={24} className="text-primary-700" />
        <h2 className="text-title-large text-on-surface">{t('stashdbTab')}</h2>
      </div>

      {error && (
        <div className="mb-5 flex items-start gap-3 rounded-2xl border border-error-container bg-error-container px-4 py-3 text-sm font-medium text-on-error-container">
          <AlertCircle size={18} className="flex-shrink-0 mt-0.5" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)} className="font-bold underline ml-2">Dismiss</button>
        </div>
      )}

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="flex gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant" size={18} />
          <input
            type="text"
            placeholder={t('stashdbSearchPlaceholder')}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="md-text-field w-full py-2.5 pl-10 pr-4"
          />
        </div>
        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          className="md-state-layer md-filled-button px-6 font-semibold flex items-center gap-2"
        >
          {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
          <span>{isLoading ? t('processing') : t('search')}</span>
        </button>
      </form>

      {/* Grid Results */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 text-on-surface-variant">
          <Loader2 size={40} className="animate-spin text-primary-700 mb-3" />
          <p className="text-sm font-medium">{t('processing')}</p>
        </div>
      ) : performers.length === 0 ? (
        query && (
          <div className="md-tonal-card py-16 text-center text-on-surface-variant">
            <p className="text-on-surface-variant">{t('noActorsSearch')}</p>
          </div>
        )
      ) : (
        <div>
          <p className="text-sm text-on-surface-variant mb-4 font-semibold">
            Found {count} performer{count !== 1 ? 's' : ''} on StashDB
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {performers.map((p) => {
              const initials = p.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
              const isImporting = importingId === p.id
              const isImported = importResult?.id === p.id
              const imgCount = imageCounts[p.id] ?? 3

              return (
                <div key={p.id} className="md-tonal-card flex flex-col justify-between p-4 border border-outline-variant">
                  <div className="flex items-start gap-4">
                    <div className="h-28 w-20 flex-shrink-0 overflow-hidden rounded-2xl bg-surface-container shadow-sm">
                      {p.image_url ? (
                        <img src={p.image_url} alt={p.name} className="h-full w-full object-cover" loading="lazy" />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center font-bold text-lg text-on-surface-variant">
                          {initials}
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="truncate font-bold text-on-surface text-base">{p.name}</h3>
                      {p.disambiguation && (
                        <p className="text-xs text-primary-700 italic truncate mb-1">({p.disambiguation})</p>
                      )}
                      <div className="mt-1.5 space-y-1 text-xs text-on-surface-variant">
                        {p.birth_date && (
                          <p className="flex items-center gap-1.5">
                            <Calendar size={12} />
                            <span>{p.birth_date}</span>
                          </p>
                        )}
                        {p.scene_count > 0 && (
                          <p className="flex items-center gap-1.5">
                            <Film size={12} />
                            <span>{p.scene_count} {t('scenes').toLowerCase()}</span>
                          </p>
                        )}
                        {p.breast_type && (
                          <p className="text-xs">
                            <span className="font-semibold">{t('breastType')}:</span> {p.breast_type.replace('_', ' ').toLowerCase()}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Actions / Status */}
                  <div className="mt-4 pt-3 border-t border-outline-variant">
                    {isImported ? (
                      <div className="flex flex-col gap-1 text-sm font-semibold text-green-700">
                        <div className="flex items-center gap-1.5">
                          <CheckCircle2 size={16} />
                          <span>
                            {importResult.status === 'exists'
                              ? 'Already in Database'
                              : t('importedSuccess')}
                          </span>
                        </div>
                        {importResult.status === 'imported' && (
                          <span className="text-xs text-on-surface-variant font-normal pl-5">
                            {t('imagesDownloaded')}: {importResult.imagesDownloaded} | {t('facesIndexed')}: {importResult.facesIndexed}
                          </span>
                        )}
                      </div>
                    ) : (
                      <div className="flex items-end gap-3">
                        <div className="flex flex-col flex-1">
                          <label className="text-[10px] uppercase font-bold text-on-surface-variant mb-1">
                            {t('imageCountToDownload')}
                          </label>
                          <select
                            value={imgCount}
                            onChange={(e) => setImageCounts({ ...imageCounts, [p.id]: Number(e.target.value) })}
                            disabled={isImporting}
                            className="md-text-field py-1 px-2 text-xs w-full"
                            style={{ minHeight: '36px', height: '36px' }}
                          >
                            <option value="1">1 Photo</option>
                            <option value="3">3 Photos</option>
                            <option value="5">5 Photos</option>
                            <option value="10">10 Photos</option>
                          </select>
                        </div>
                        <button
                          onClick={() => handleImport(p.id)}
                          disabled={isImporting}
                          className="md-state-layer md-filled-button px-4 text-xs font-semibold flex items-center justify-center gap-1.5 disabled:opacity-50"
                          style={{ minHeight: '36px', height: '36px' }}
                        >
                          {isImporting ? (
                            <Loader2 size={14} className="animate-spin" />
                          ) : (
                            <Download size={14} />
                          )}
                          <span>{isImporting ? t('importing') : t('import')}</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
