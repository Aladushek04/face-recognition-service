import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import {
  Film,
  Search,
  RefreshCw,
  Play,
  Trash2,
  Clock,
  HardDrive,
  Users,
  X,
  AlertCircle,
  ExternalLink,
  ChevronRight,
  ChevronDown,
  Sliders,
  RotateCw,
  LayoutGrid,
  List,
  Download,
  CheckCircle2,
} from 'lucide-react'
import {
  getVideos,
  getVideo,
  scanVideos,
  processVideo,
  deleteVideo,
  getActors,
  processUnprocessedVideos,
  renameVideo,
  searchStashdbCandidates,
  linkStashdb,
  linkStashdbByUrl,
  addActorToVideo,
  removeActorFromVideo,
  resolveMediaUrl,
} from '../lib/api'
import { useUiPreferences } from '../lib/useUiPreferences'
import type { Video, Actor } from '../types'

export function VideosPanel() {
  const { language, t } = useUiPreferences()
  const labels = videosLabels(language)

  const [videos, setVideos] = useState<Video[]>([])
  const [actorsList, setActorsList] = useState<Actor[]>([])
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null)
  
  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [actorFilter, setActorFilter] = useState<string>('all')
  const [durationFilter, setDurationFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState<string>('filename')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')

  // Loading states
  const [isLoading, setIsLoading] = useState(true)
  const [isBatchProcessing, setIsBatchProcessing] = useState(false)
  const [isScanning, setIsScanning] = useState(false)
  const [processingIds, setProcessingIds] = useState<Set<number>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [scanMessage, setScanMessage] = useState<string | null>(null)

  // Expand states for modal actors list
  const [expandedActorId, setExpandedActorId] = useState<number | null>(null)

  const loadVideos = useCallback(async (showLoading = true) => {
    if (showLoading) setIsLoading(true)
    try {
      setError(null)
      const data = await getVideos({
        search: searchQuery || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        actorId: actorFilter !== 'all' ? Number(actorFilter) : undefined,
      })
      setVideos(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load videos')
    } finally {
      if (showLoading) setIsLoading(false)
    }
  }, [searchQuery, statusFilter, actorFilter])

  const loadActorsList = useCallback(async () => {
    try {
      const data = await getActors(1, 100)
      setActorsList(data.actors)
    } catch (err) {
      console.error('Failed to load actors list', err)
    }
  }, [])

  const processedVideos = useMemo(() => {
    let result = [...videos]

    if (durationFilter === 'short') {
      result = result.filter((v) => v.duration !== null && v.duration < 120)
    } else if (durationFilter === 'medium') {
      result = result.filter((v) => v.duration !== null && v.duration >= 120 && v.duration <= 1800)
    } else if (durationFilter === 'long') {
      result = result.filter((v) => v.duration !== null && v.duration > 1800)
    }

    result.sort((a, b) => {
      let comparison = 0
      if (sortBy === 'filename') {
        comparison = a.filename.localeCompare(b.filename)
      } else if (sortBy === 'size') {
        comparison = (a.size_bytes || 0) - (b.size_bytes || 0)
      } else if (sortBy === 'duration') {
        comparison = (a.duration || 0) - (b.duration || 0)
      } else if (sortBy === 'created') {
        comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      }
      return sortOrder === 'asc' ? comparison : -comparison
    })

    return result
  }, [videos, durationFilter, sortBy, sortOrder])

  const resultsTransitionKey = useMemo(
    () => [
      viewMode,
      searchQuery,
      statusFilter,
      actorFilter,
      durationFilter,
      sortBy,
      sortOrder,
      processedVideos.length,
      isLoading ? 'loading' : 'ready',
    ].join(':'),
    [viewMode, searchQuery, statusFilter, actorFilter, durationFilter, sortBy, sortOrder, processedVideos.length, isLoading]
  )

  useEffect(() => {
    loadVideos(true)
  }, [loadVideos])

  useEffect(() => {
    loadActorsList()
  }, [loadActorsList])

  // Polling for processing videos
  useEffect(() => {
    const hasProcessing = videos.some((v) => v.status === 'processing')
    if (!hasProcessing) return

    const timer = setInterval(() => {
      loadVideos(false)
    }, 3000)

    return () => clearInterval(timer)
  }, [videos, loadVideos])

  // Poll current selected video if it's processing to update metadata in modal
  useEffect(() => {
    if (!selectedVideo || selectedVideo.status !== 'processing') return

    const timer = setInterval(async () => {
      try {
        const updated = await getVideo(selectedVideo.id)
        setSelectedVideo(updated)
        if (updated.status === 'completed' || updated.status === 'failed') {
          loadVideos(false)
        }
      } catch (err) {
        console.error('Failed to update selected video status', err)
      }
    }, 3000)

    return () => clearInterval(timer)
  }, [selectedVideo, loadVideos])

  const handleScan = async () => {
    setIsScanning(true)
    setError(null)
    setScanMessage(null)
    try {
      const res = await scanVideos()
      setScanMessage(labels.scannedMessage(res.scanned, res.added))
      loadVideos(false)
      setTimeout(() => setScanMessage(null), 6000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scanning failed')
    } finally {
      setIsScanning(false)
    }
  }

  const handleBatchProcess = async () => {
    setIsBatchProcessing(true)
    setError(null)
    try {
      const res = await processUnprocessedVideos()
      setScanMessage(
        language === 'ru'
          ? `Запущен пакетный анализ: ${res.count} видео добавлено в очередь.`
          : `Started batch processing: ${res.count} videos added to queue.`
      )
      loadVideos(false)
      setTimeout(() => setScanMessage(null), 6000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Batch processing failed to start')
    } finally {
      setIsBatchProcessing(false)
    }
  }

  const handleProcess = async (id: number) => {
    setProcessingIds((prev) => {
      const next = new Set(prev)
      next.add(id)
      return next
    })
    try {
      await processVideo(id)
      setVideos((prev) =>
        prev.map((v) => (v.id === id ? { ...v, status: 'processing' } : v))
      )
      setSelectedVideo((prev) =>
        prev && prev.id === id ? { ...prev, status: 'processing', progress: 0, detections: [], actors: [] } : prev
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Processing start failed')
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm(labels.confirmDelete)) return
    try {
      await deleteVideo(id)
      setVideos((prev) => prev.filter((v) => v.id !== id))
      if (selectedVideo?.id === id) setSelectedVideo(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete video record')
    }
  }

  const openVideoDetails = async (video: Video) => {
    try {
      setError(null)
      const details = await getVideo(video.id)
      setSelectedVideo(details)
      setExpandedActorId(details.actors && details.actors.length > 0 ? details.actors[0].id : null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load video details')
      setSelectedVideo(video)
    }
  }

  const refreshSelectedVideo = async () => {
    if (!selectedVideo) return
    try {
      const details = await getVideo(selectedVideo.id)
      setSelectedVideo(details)
      loadVideos(false)
    } catch (err) {
      console.error('Failed to refresh selected video details', err)
    }
  }

  return (
    <div>
      {/* Top Title Bar */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Film size={24} className="text-primary-700" />
          <h2 className="text-title-large text-on-surface">{labels.title}</h2>
          <span className="rounded-chip bg-surface-container px-2.5 py-0.5 text-sm font-semibold text-on-surface-variant">
            {videos.length}
          </span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleScan}
            disabled={isScanning}
            className="md-state-layer md-tonal-button flex items-center gap-2 px-4 py-2 font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw size={18} className={isScanning ? 'animate-spin' : ''} />
            {labels.scanFolder}
          </button>
          {videos.some((v) => v.status === 'unprocessed' || v.status === 'failed') && (
            <button
              onClick={handleBatchProcess}
              disabled={isBatchProcessing}
              className="md-state-layer md-filled-button flex items-center gap-2 px-4 py-2 font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isBatchProcessing ? (
                <RefreshCw size={18} className="animate-spin" />
              ) : (
                <Users size={18} />
              )}
              {language === 'ru' ? 'Анализировать новые' : 'Analyze new'}
            </button>
          )}
        </div>
      </div>

      {/* Floating notifications */}
      {(error || scanMessage) && (
        <div className="pointer-events-none fixed inset-x-4 top-20 z-50 flex justify-center" aria-live="polite">
          {error ? (
            <div className="md-glass pointer-events-auto flex w-full max-w-2xl items-start justify-between gap-3 rounded-[28px] border-error/30 bg-error-container/80 px-4 py-3 text-sm font-semibold text-on-error-container shadow-xl shadow-black/20 fade-in">
              <span className="flex min-w-0 items-center gap-2">
                <AlertCircle size={16} className="flex-shrink-0" />
                <span className="break-words">{error}</span>
              </span>
              <button
                onClick={() => setError(null)}
                className="md-state-layer rounded-xl p-1 text-on-error-container hover:bg-surface/40"
                aria-label={t('cancel')}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </div>
          ) : (
            <div className="md-glass pointer-events-auto flex w-full max-w-2xl items-center gap-2 rounded-[28px] border-success/30 bg-success-container/80 px-4 py-3 text-sm font-semibold text-on-success-container shadow-xl shadow-black/20 fade-in">
              <span className="flex h-2.5 w-2.5 flex-shrink-0 rounded-full bg-success shadow-[0_0_0_5px_color-mix(in_srgb,var(--md-sys-color-success)_18%,transparent)]" />
              <span className="min-w-0 break-words">{scanMessage}</span>
            </div>
          )}
        </div>
      )}

      {/* Active processing list / progress queue */}
      {videos.filter((v) => v.status === 'processing').length > 0 && (
        <div className="mb-6 md-tonal-card p-4 space-y-3">
          <div className="flex items-center gap-2 text-primary-700 font-bold text-sm uppercase tracking-wider">
            <RefreshCw size={16} className="animate-spin" />
            <span>{language === 'ru' ? 'Очередь обработки' : 'Processing Queue'}</span>
          </div>
          <div className="space-y-3">
            {videos
              .filter((v) => v.status === 'processing')
              .map((video, index) => {
                const progress = video.progress ?? 0
                const isActive = progress > 0 || index === 0

                return (
                  <div
                    key={video.id}
                    className={`rounded-xl border px-3 py-2 transition-colors ${
                      isActive
                        ? 'border-primary/30 bg-primary-container/20'
                        : 'border-outline-variant/30 bg-surface-container-low/40'
                    }`}
                  >
                    <div className="mb-1.5 flex items-center justify-between gap-3 text-xs font-semibold text-on-surface">
                      <span className="min-w-0 truncate font-bold">{video.filename}</span>
                      <span className="flex flex-shrink-0 items-center gap-2">
                        <span className={`rounded-chip px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wider ${
                          isActive
                            ? 'bg-primary-container text-primary-700'
                            : 'bg-surface-container-highest text-on-surface-variant'
                        }`}>
                          {isActive ? (language === 'ru' ? 'Идет' : 'Active') : (language === 'ru' ? 'В очереди' : 'Queued')}
                        </span>
                        <span className="min-w-[34px] text-right font-extrabold text-primary-700">{progress}%</span>
                      </span>
                    </div>
                    <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-surface-container-high">
                      {progress > 0 ? (
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-primary-500 via-primary-600 to-primary-500 shadow-[0_0_14px_color-mix(in_srgb,var(--md-sys-color-primary)_35%,transparent)] transition-all duration-500 ease-out"
                          style={{ width: `${progress}%` }}
                        />
                      ) : isActive ? (
                        <div className="absolute inset-y-0 left-0 w-1/3 animate-pulse rounded-full bg-gradient-to-r from-transparent via-primary-500 to-transparent" />
                      ) : (
                        <div className="h-full w-1 rounded-full bg-outline-variant/50" />
                      )}
                    </div>
                  </div>
                )
              })}
          </div>
        </div>
      )}

      {/* Filters Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant" size={18} />
          <input
            type="text"
            placeholder={labels.searchVideos}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="md-text-field w-full py-2 pl-10 pr-4 text-sm"
          />
        </div>

        <div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="md-text-field w-full px-3 py-2 text-sm"
          >
            <option value="all">{labels.filterStatus}: {labels.all}</option>
            <option value="unprocessed">{labels.unprocessed}</option>
            <option value="processing">{labels.processing}</option>
            <option value="completed">{labels.completed}</option>
            <option value="failed">{labels.failed}</option>
          </select>
        </div>

        <div>
          <select
            value={actorFilter}
            onChange={(e) => setActorFilter(e.target.value)}
            className="md-text-field w-full px-3 py-2 text-sm"
          >
            <option value="all">{labels.filterActor}: {labels.all}</option>
            {actorsList.map((actor) => (
              <option key={actor.id} value={actor.id}>
                {actor.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Advanced Filters & View Toggle */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-6 items-center">
        <div>
          <select
            value={durationFilter}
            onChange={(e) => setDurationFilter(e.target.value)}
            className="md-text-field w-full px-3 py-2 text-sm"
          >
            <option value="all">{language === 'ru' ? 'Длительность: Все' : 'Duration: All'}</option>
            <option value="short">{language === 'ru' ? 'Короткие (< 2 мин)' : 'Short (< 2m)'}</option>
            <option value="medium">{language === 'ru' ? 'Средние (2 - 30 мин)' : 'Medium (2-30m)'}</option>
            <option value="long">{language === 'ru' ? 'Длинные (> 30 мин)' : 'Long (> 30m)'}</option>
          </select>
        </div>

        <div>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="md-text-field w-full px-3 py-2 text-sm"
          >
            <option value="filename">{language === 'ru' ? 'Сортировка: По имени' : 'Sort by: Name'}</option>
            <option value="size">{language === 'ru' ? 'Сортировка: По размеру' : 'Sort by: Size'}</option>
            <option value="duration">{language === 'ru' ? 'Сортировка: По длительности' : 'Sort by: Duration'}</option>
            <option value="created">{language === 'ru' ? 'Сортировка: По дате добавления' : 'Sort by: Date Added'}</option>
          </select>
        </div>

        <div>
          <select
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as 'asc' | 'desc')}
            className="md-text-field w-full px-3 py-2 text-sm"
          >
            <option value="asc">{language === 'ru' ? 'Порядок: По возрастанию' : 'Order: Ascending'}</option>
            <option value="desc">{language === 'ru' ? 'Порядок: По убыванию' : 'Order: Descending'}</option>
          </select>
        </div>

        <div className="flex justify-end gap-1.5">
          <button
            onClick={() => setViewMode('grid')}
            className={`p-2 rounded-xl border flex items-center justify-center transition-all ${
              viewMode === 'grid'
                ? 'bg-primary-container border-primary text-primary-700'
                : 'bg-surface border-outline-variant text-on-surface-variant hover:bg-surface-container'
            }`}
            title={language === 'ru' ? 'Сетка' : 'Grid'}
          >
            <LayoutGrid size={18} />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`p-2 rounded-xl border flex items-center justify-center transition-all ${
              viewMode === 'list'
                ? 'bg-primary-container border-primary text-primary-700'
                : 'bg-surface border-outline-variant text-on-surface-variant hover:bg-surface-container'
            }`}
            title={language === 'ru' ? 'Список' : 'List'}
          >
            <List size={18} />
          </button>
        </div>
      </div>

      {/* Loading state */}
      <div key={resultsTransitionKey} className="md-results-transition">
      {isLoading ? (
        <div className="py-20 flex justify-center items-center">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary-500 border-t-transparent" />
        </div>
      ) : processedVideos.length === 0 ? (
        <div className="md-tonal-card py-16 text-center">
          <Film size={48} className="mx-auto mb-3 text-on-surface-variant" />
          <p className="text-on-surface-variant px-4 max-w-md mx-auto">
            {searchQuery || statusFilter !== 'all' || actorFilter !== 'all' || durationFilter !== 'all'
              ? (language === 'ru' ? 'С заданными фильтрами видео не найдены.' : 'No videos found with the active filters.')
              : labels.noVideos}
          </p>
        </div>
      ) : viewMode === 'list' ? (
        <div className="md-tonal-card overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-outline-variant bg-surface-container-low text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                <th className="p-4 w-20">{language === 'ru' ? 'Превью' : 'Preview'}</th>
                <th className="p-4">{language === 'ru' ? 'Имя файла' : 'Filename'}</th>
                <th className="p-4">{labels.duration}</th>
                <th className="p-4">{labels.size}</th>
                <th className="p-4">{labels.filterStatus}</th>
                <th className="p-4">{labels.detectedActors}</th>
                <th className="p-4 text-right">{language === 'ru' ? 'Действия' : 'Actions'}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/30 text-on-surface font-medium">
              {processedVideos.map((video, index) => {
                const isProcessing = video.status === 'processing' || processingIds.has(video.id)
                let statusBadge = ''
                let statusText = ''
                if (video.status === 'completed') {
                  statusBadge = 'bg-success-container text-on-success-container'
                  statusText = labels.completed
                } else if (video.status === 'failed') {
                  statusBadge = 'bg-error-container text-on-error-container'
                  statusText = labels.failed
                } else if (video.status === 'processing') {
                  statusBadge = 'bg-primary-container text-on-primary-container animate-pulse'
                  statusText = labels.processing
                } else {
                  statusBadge = 'bg-surface-container-highest text-on-surface-variant'
                  statusText = labels.unprocessed
                }
                return (
                  <tr
                    key={video.id}
                    className="md-list-row-enter hover:bg-surface-container-low/50 transition-colors"
                    style={{ animationDelay: `${Math.min(index, 14) * 18}ms` }}
                  >
                    <td className="p-4">
                      <div className="w-16 h-10 rounded-lg bg-surface-container-high overflow-hidden border border-outline-variant flex items-center justify-center relative">
                        {video.status === 'processing' ? (
                          <div className="flex flex-col items-center justify-center gap-0.5 text-primary-700">
                            <RefreshCw size={12} className="animate-spin" />
                            <span className="text-[8px] font-bold">{video.progress ?? 0}%</span>
                          </div>
                        ) : (
                          <>
                            <img
                              src={videoThumbnailSrc(video)}
                              alt={video.filename}
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                e.currentTarget.style.display = 'none';
                                const fallback = e.currentTarget.nextElementSibling;
                                if (fallback) fallback.classList.remove('hidden');
                              }}
                            />
                            <div className="thumb-fallback hidden absolute inset-0 flex items-center justify-center text-on-surface-variant/40 bg-surface-container-high/50">
                              <Film size={16} />
                            </div>
                          </>
                        )}
                      </div>
                    </td>
                    <td className="p-4 max-w-xs truncate">
                      <div className="font-bold text-on-surface text-sm" title={video.filename}>{video.filename}</div>
                      <div className="text-[10px] text-on-surface-variant/80 truncate font-semibold">{video.filepath}</div>
                    </td>
                    <td className="p-4 font-semibold text-xs whitespace-nowrap">{formatDuration(video.duration)}</td>
                    <td className="p-4 font-semibold text-xs whitespace-nowrap">{formatSize(video.size_bytes)}</td>
                    <td className="p-4">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-chip uppercase tracking-wider ${statusBadge}`}>
                        {statusText}
                      </span>
                    </td>
                    <td className="p-4">
                      <div className="flex flex-wrap gap-1 max-w-xs">
                        {video.actors && video.actors.length > 0 ? (
                          video.actors.map((act) => (
                            <span key={act.id} className="rounded-chip bg-primary-container/40 px-2 py-0.5 text-[9px] font-semibold text-primary-700">
                              {act.name}
                            </span>
                          ))
                        ) : (
                          <span className="text-[10px] text-on-surface-variant/50 font-normal">-</span>
                        )}
                      </div>
                    </td>
                    <td className="p-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => openVideoDetails(video)}
                          className="md-state-layer md-filled-button h-8 px-3 text-xs font-semibold flex items-center gap-1"
                        >
                          <Play size={12} />
                          <span>{labels.play}</span>
                        </button>
                        {(video.status === 'unprocessed' || video.status === 'failed' || video.status === 'completed') && (
                          <button
                            onClick={() => handleProcess(video.id)}
                            disabled={isProcessing}
                            className="md-state-layer md-tonal-button h-8 px-3 text-xs font-semibold flex items-center gap-1"
                          >
                            {isProcessing ? <RefreshCw size={12} className="animate-spin" /> : <Users size={12} />}
                            <span>{video.status === 'completed' ? labels.reanalyze : labels.analyze}</span>
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(video.id)}
                          className="md-state-layer p-1.5 text-on-surface-variant hover:bg-error-container hover:text-error rounded-xl transition-colors h-8 w-8 flex items-center justify-center"
                          title={labels.delete}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {processedVideos.map((video, index) => (
            <div
              key={video.id}
              className="md-card-enter h-full"
              style={{ animationDelay: `${Math.min(index, 14) * 24}ms` }}
            >
              <VideoCard
                video={video}
                onOpen={() => openVideoDetails(video)}
                onProcess={() => handleProcess(video.id)}
                onDelete={() => handleDelete(video.id)}
                isStartingProcess={processingIds.has(video.id)}
                labels={labels}
              />
            </div>
          ))}
        </div>
      )}
      </div>

      {/* Detail Modal with Player */}
      {selectedVideo && (
        <VideoPlayerModal
          video={selectedVideo}
          onClose={() => setSelectedVideo(null)}
          onProcess={() => handleProcess(selectedVideo.id)}
          onDelete={() => handleDelete(selectedVideo.id)}
          expandedActorId={expandedActorId}
          setExpandedActorId={setExpandedActorId}
          labels={labels}
          onRefreshVideo={refreshSelectedVideo}
          actorsList={actorsList}
        />
      )}
    </div>
  )
}

function VideoCard({
  video,
  onOpen,
  onProcess,
  onDelete,
  isStartingProcess,
  labels,
}: {
  video: Video
  onOpen: () => void
  onProcess: () => void
  onDelete: () => void
  isStartingProcess: boolean
  labels: any
}) {
  const isProcessing = video.status === 'processing' || isStartingProcess
  const formattedSize = formatSize(video.size_bytes)
  const formattedDuration = formatDuration(video.duration)

  // Decide status pill color
  let statusBadge = ''
  let statusText = ''
  if (video.status === 'completed') {
    statusBadge = 'bg-success-container text-on-success-container'
    statusText = labels.completed
  } else if (video.status === 'failed') {
    statusBadge = 'bg-error-container text-on-error-container'
    statusText = labels.failed
  } else if (video.status === 'processing') {
    statusBadge = 'bg-primary-container text-on-primary-container animate-pulse'
    statusText = labels.processing
  } else {
    statusBadge = 'bg-surface-container-highest text-on-surface-variant'
    statusText = labels.unprocessed
  }

  return (
    <div className="md-tonal-card flex h-full min-h-[430px] flex-col p-4 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-short ease-standard group">
      <div className="flex min-h-0 flex-1 flex-col">
        {/* Thumbnail Preview */}
        <div className="relative aspect-video rounded-xl bg-surface-container-lowest overflow-hidden border border-outline-variant mb-3 flex items-center justify-center group-hover:shadow-md transition-all">
          {video.status === 'processing' ? (
            <div className="flex flex-col items-center justify-center gap-2 text-primary-700">
              <RefreshCw size={24} className="animate-spin" />
              <span className="text-[10px] font-bold uppercase tracking-wider">{video.progress ?? 0}%</span>
            </div>
          ) : (
            <>
              <img
                src={videoThumbnailSrc(video)}
                alt={video.filename}
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                  const fallback = e.currentTarget.nextElementSibling;
                  if (fallback) {
                    fallback.classList.remove('hidden');
                  }
                }}
              />
              <div className="thumb-fallback hidden absolute inset-0 flex items-center justify-center text-on-surface-variant/40 bg-surface-container-high/50">
                <Film size={32} />
              </div>
            </>
          )}
          {video.status === 'completed' && (
            <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity cursor-pointer" onClick={onOpen}>
              <div className="bg-surface/80 p-2.5 rounded-full shadow-md text-primary-700">
                <Play size={20} fill="currentColor" />
              </div>
            </div>
          )}
        </div>

        <div className="mb-2 flex min-h-[44px] items-start justify-between gap-3">
          <h3 className="line-clamp-2 flex-1 break-words text-sm font-bold leading-5 text-on-surface" title={video.filename}>
            {video.filename}
          </h3>
          <span className={`flex-shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-chip uppercase tracking-wider ${statusBadge}`}>
            {statusText}
          </span>
        </div>

        <div className="mt-2 min-h-[48px] space-y-1.5 text-xs text-on-surface-variant font-medium">
          <p className="flex items-center gap-1.5 truncate text-[11px] font-semibold text-on-surface-variant/70">
            <HardDrive size={12} />
            {video.filepath}
          </p>
          <div className="flex items-center gap-4 text-xs font-semibold">
            <span className="flex items-center gap-1">
              <Clock size={12} />
              {formattedDuration}
            </span>
            <span>
              {formattedSize}
            </span>
          </div>
        </div>

        <div className="mt-3 min-h-[62px]">
          {video.actors && video.actors.length > 0 ? (
            <>
            <p className="text-[10px] font-bold text-on-surface-variant/80 uppercase tracking-wider mb-1.5">
              {labels.detectedActors} ({video.actors.length}):
            </p>
            <div className="flex flex-wrap gap-1">
              {video.actors.slice(0, 3).map((actor) => (
                <span key={actor.id} className="rounded-chip bg-primary-container/50 px-2 py-0.5 text-[10px] font-semibold text-primary-700">
                  {actor.name}
                </span>
              ))}
              {video.actors.length > 3 && (
                <span className="rounded-chip bg-surface-container px-2 py-0.5 text-[10px] font-semibold text-on-surface-variant">
                  +{video.actors.length - 3}
                </span>
              )}
            </div>
            </>
          ) : (
            <div className="h-full" aria-hidden="true" />
          )}
        </div>
      </div>

      {/* Actions row */}
      <div className="mt-auto flex gap-2 border-t border-outline-variant/30 pt-3">
        <button
          onClick={onOpen}
          className="md-state-layer md-filled-button flex-1 py-1.5 text-xs font-semibold flex items-center justify-center gap-1.5 h-9"
        >
          <Play size={14} />
          {labels.play}
        </button>

        {(video.status === 'unprocessed' || video.status === 'failed' || video.status === 'completed') && (
          <button
            onClick={onProcess}
            disabled={isProcessing}
            className="md-state-layer md-tonal-button flex-1 py-1.5 text-xs font-semibold flex items-center justify-center gap-1.5 h-9"
          >
            {isProcessing ? (
              <RefreshCw size={14} className="animate-spin" />
            ) : (
              <Users size={14} />
            )}
            {video.status === 'completed' ? labels.reanalyze : labels.analyze}
          </button>
        )}

        <button
          onClick={onDelete}
          className="md-state-layer rounded-xl p-2 text-on-surface-variant hover:bg-error-container hover:text-error transition-colors flex items-center justify-center h-9 w-9"
          title={labels.delete}
        >
          <Trash2 size={15} />
        </button>
      </div>
    </div>
  )
}

function VideoPlayerModal({
  video,
  onClose,
  onProcess,
  onDelete,
  expandedActorId,
  setExpandedActorId,
  labels,
  onRefreshVideo,
  actorsList,
}: {
  video: Video
  onClose: () => void
  onProcess: () => void
  onDelete: () => void
  expandedActorId: number | null
  setExpandedActorId: (id: number | null) => void
  labels: any
  onRefreshVideo: () => void
  actorsList: Actor[]
}) {
  const { language } = useUiPreferences()
  const videoRef = useRef<HTMLVideoElement | null>(null)

  // Local tabs & player adjustment states
  const [activeTab, setActiveTab] = useState<'detections' | 'filters'>('detections')
  const [brightness, setBrightness] = useState(100)
  const [contrast, setContrast] = useState(100)
  const [saturation, setSaturation] = useState(100)
  const [grayscale, setGrayscale] = useState(0)
  const [invert, setInvert] = useState(0)
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0)
  const [rotate, setRotate] = useState(0)
  const [mirror, setMirror] = useState(false)
  const [aspectRatio, setAspectRatio] = useState<'contain' | 'cover' | 'fill'>('contain')

  const [isMatchingStashdb, setIsMatchingStashdb] = useState(false)
  const [stashdbError, setStashdbError] = useState<string | null>(null)
  const [stashdbMatchInfo, setStashdbMatchInfo] = useState<{
    scene_id: string
    title: string
    studio: string | null
    cover_downloaded: boolean
    performers: string[]
  } | null>(null)

  const [isRenaming, setIsRenaming] = useState(false)
  const [renameError, setRenameError] = useState<string | null>(null)
  const [suggestedName, setSuggestedName] = useState('')
  const [isEditingName, setIsEditingName] = useState(false)
  const [manualRenameVal, setManualRenameVal] = useState(video.filename)
  const [manualSceneUrl, setManualSceneUrl] = useState('')
  const [isLinkingSceneUrl, setIsLinkingSceneUrl] = useState(false)
  const [actorSearchQuery, setActorSearchQuery] = useState('')
  const [actorSearchResults, setActorSearchResults] = useState<Actor[]>([])
  const [isActorSearchLoading, setIsActorSearchLoading] = useState(false)
  const [actorSearchError, setActorSearchError] = useState<string | null>(null)

  const [stashdbCandidates, setStashdbCandidates] = useState<Array<{
    scene_id: string
    title: string
    studio: string | null
    date: string | null
    cover_url: string | null
    performers: string[]
    score: number
  }> | null>(null)
  const [searchInfo, setSearchInfo] = useState<{
    filename: string
    detected_actors: string[]
    queries_used: Array<{ query: string; results: number; new: number }>
    total_unique_results: number
  } | null>(null)
  const [isSearchingCandidates, setIsSearchingCandidates] = useState(false)

  useEffect(() => {
    setManualRenameVal(video.filename)
    setSuggestedName('')
    setStashdbMatchInfo(null)
    setStashdbError(null)
    setRenameError(null)
    setManualSceneUrl('')
    setStashdbCandidates(null)
    setSearchInfo(null)
    setActorSearchQuery('')
    setActorSearchResults([])
    setActorSearchError(null)
  }, [video.id, video.filename])

  const handleSearchStashdb = async () => {
    setIsSearchingCandidates(true)
    setStashdbError(null)
    setStashdbCandidates(null)
    setSearchInfo(null)
    try {
      const raw = await searchStashdbCandidates(video.id)
      // Handle both new { candidates, search_info } and old flat array format
      const candidates = Array.isArray(raw) ? raw : (raw.candidates ?? [])
      const info = Array.isArray(raw) ? null : (raw.search_info ?? null)
      setStashdbCandidates(candidates)
      setSearchInfo(info)
      if (candidates.length === 0) {
        setStashdbError(language === 'ru' ? 'Сцены не найдены на StashDB' : 'No scenes found on StashDB')
      }
    } catch (err) {
      setStashdbError(err instanceof Error ? err.message : 'StashDB search failed')
    } finally {
      setIsSearchingCandidates(false)
    }
  }

  const applySuggestedName = (title: string | null, studio: string | null) => {
    if (!title) return
    const cleanTitle = title.replace(/[\\/:*?"<>|]/g, '')
    const cleanStudio = studio?.replace(/[\\/:*?"<>|]/g, '')
    const nextSuggestedName = cleanStudio ? `[${cleanStudio}] ${cleanTitle}` : cleanTitle
    setSuggestedName(nextSuggestedName)
    setManualRenameVal(nextSuggestedName)
    setIsEditingName(true)
  }

  const handleLinkCandidate = async (candidate: {
    scene_id: string
    title: string
    studio: string | null
    cover_url: string | null
    performers?: string[]
  }) => {
    setIsMatchingStashdb(true)
    setStashdbError(null)
    try {
      await linkStashdb(video.id, {
        scene_id: candidate.scene_id,
        title: candidate.title,
        studio: candidate.studio,
        cover_url: candidate.cover_url,
        performers: candidate.performers ?? [],
      })
      applySuggestedName(candidate.title, candidate.studio)
      setStashdbCandidates(null)
      setStashdbMatchInfo({
        scene_id: candidate.scene_id,
        title: candidate.title,
        studio: candidate.studio,
        cover_downloaded: true,
        performers: candidate.performers ?? []
      })
      onRefreshVideo()
    } catch (err) {
      setStashdbError(err instanceof Error ? err.message : 'Failed to link scene')
    } finally {
      setIsMatchingStashdb(false)
    }
  }

  const handleLinkSceneUrl = async () => {
    if (!manualSceneUrl.trim()) return
    setIsLinkingSceneUrl(true)
    setStashdbError(null)
    try {
      const scene = await linkStashdbByUrl(video.id, manualSceneUrl.trim())
      applySuggestedName(scene.title, scene.studio)
      setStashdbCandidates(null)
      setSearchInfo(null)
      setStashdbMatchInfo({
        scene_id: scene.scene_id,
        title: scene.title,
        studio: scene.studio,
        cover_downloaded: scene.cover_downloaded,
        performers: scene.performers,
      })
      setManualSceneUrl('')
      onRefreshVideo()
    } catch (err) {
      setStashdbError(err instanceof Error ? err.message : 'Failed to link scene URL')
    } finally {
      setIsLinkingSceneUrl(false)
    }
  }

  const handleRename = async () => {
    setIsRenaming(true)
    setRenameError(null)
    try {
      await renameVideo(video.id, manualRenameVal)
      onRefreshVideo()
      setIsEditingName(false)
    } catch (err) {
      setRenameError(err instanceof Error ? err.message : 'Rename failed')
    } finally {
      setIsRenaming(false)
    }
  }

  const handleAddActor = async (actorId: number) => {
    try {
      await addActorToVideo(video.id, actorId)
      setActorSearchQuery('')
      setActorSearchResults([])
      onRefreshVideo()
    } catch (err) {
      console.error('Failed to add actor', err)
    }
  }

  const handleRemoveActor = async (actorId: number) => {
    if (!confirm(language === 'ru' ? 'Вы уверены, что хотите удалить этого актера из видео?' : 'Are you sure you want to remove this actor from the video?')) return
    try {
      await removeActorFromVideo(video.id, actorId)
      onRefreshVideo()
    } catch (err) {
      console.error('Failed to remove actor', err)
    }
  }
  
  const formattedSize = formatSize(video.size_bytes)
  const formattedDuration = formatDuration(video.duration)

  // Group detections by actor
  const actorDetections = useMemo(() => {
    if (!video.detections) return {}
    const groups: Record<number, { name: string; timestamps: number[] }> = {}
    video.detections.forEach((d) => {
      if (!groups[d.actor_id]) {
        groups[d.actor_id] = { name: d.actor_name, timestamps: [] }
      }
      groups[d.actor_id].timestamps.push(d.timestamp)
    })
    return groups
  }, [video.detections])

  useEffect(() => {
    const query = actorSearchQuery.trim()
    setActorSearchError(null)

    if (query.length < 2) {
      setActorSearchResults([])
      setIsActorSearchLoading(false)
      return
    }

    let isCancelled = false
    setIsActorSearchLoading(true)

    const timer = window.setTimeout(async () => {
      try {
        const data = await getActors(1, 12, query)
        if (!isCancelled) {
          setActorSearchResults(data.actors.filter((actor) => !actorDetections[actor.id]))
        }
      } catch (err) {
        if (!isCancelled) {
          setActorSearchResults([])
          setActorSearchError(err instanceof Error ? err.message : 'Actor search failed')
        }
      } finally {
        if (!isCancelled) {
          setIsActorSearchLoading(false)
        }
      }
    }, 220)

    return () => {
      isCancelled = true
      window.clearTimeout(timer)
    }
  }, [actorSearchQuery, actorDetections])

  const confirmedPerformers = useMemo(() => {
    return new Set((video.stashdb_performers ?? []).map(normalizePersonName))
  }, [video.stashdb_performers])

  const seekTo = (seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds
      videoRef.current.play()
    }
  }

  // Apply playback speed to video element
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = playbackSpeed
    }
  }, [playbackSpeed])

  const handleVideoLoaded = () => {
    if (videoRef.current) {
      videoRef.current.playbackRate = playbackSpeed
    }
  }

  const videoStyle = {
    filter: `brightness(${brightness}%) contrast(${contrast}%) saturate(${saturation}%) grayscale(${grayscale}%) invert(${invert}%)`,
    transform: `rotate(${rotate}deg) ${mirror ? 'scaleX(-1)' : ''}`,
    objectFit: aspectRatio,
    transition: 'filter 0.15s ease, transform 0.15s ease',
  } as React.CSSProperties

  // Decides play support check
  const isVideoFormatSupported = video.filename.toLowerCase().endsWith('.mp4') || 
                                 video.filename.toLowerCase().endsWith('.webm')

  return (
    <div className="fixed inset-0 z-[100] bg-scrim flex items-center justify-center p-4 backdrop-blur-sm">
      <div className="md-card w-full max-w-5xl h-[calc(100vh-80px)] flex flex-col overflow-hidden bg-surface">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant bg-surface-container-low">
          <div className="min-w-0">
            <h3 className="text-title-large text-on-surface truncate break-all pr-4" title={video.filename}>
              {video.filename}
            </h3>
            <p className="text-xs text-on-surface-variant truncate font-medium mt-0.5">
              {video.filepath}
            </p>
          </div>
          <button
            onClick={onClose}
            className="md-state-layer rounded-2xl p-2 text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
            aria-label={labels.close}
          >
            <X size={24} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_360px] overflow-hidden">
          
          {/* Left Column: Player & Meta */}
          <div className="p-6 overflow-y-auto flex flex-col gap-4 border-r border-outline-variant">
            {isVideoFormatSupported ? (
              <div className="relative aspect-video rounded-2xl bg-surface-container-lowest overflow-hidden border border-outline-variant shadow-inner flex items-center justify-center">
                <video
                  ref={videoRef}
                  src={resolveMediaUrl(`/api/videos/${video.id}/stream`) || `/api/videos/${video.id}/stream`}
                  controls
                  className="w-full h-full"
                  style={videoStyle}
                  onLoadedMetadata={handleVideoLoaded}
                />
              </div>
            ) : (
              <div className="aspect-video rounded-2xl bg-surface-container-lowest border border-outline-variant border-dashed flex flex-col justify-center items-center p-8 text-center text-on-surface-variant gap-3">
                <AlertCircle size={40} className="text-warning" />
                <div>
                  <p className="font-bold text-sm">
                    {language === 'ru' ? 'Формат файла не поддерживается плеером' : 'Video format not supported by player'}
                  </p>
                  <p className="text-xs mt-1">
                    {language === 'ru' 
                      ? 'Данный видеокодек/контейнер (mkv, avi и др.) может не воспроизводиться напрямую в браузере. Вы можете использовать сторонний проигрыватель.' 
                      : 'This video format (MKV, AVI, etc.) may not play directly in standard browsers. You can play it using an external media player.'}
                  </p>
                </div>
              </div>
            )}

            {/* Video metadata row */}
            <div className="flex flex-wrap gap-4 items-center justify-between text-sm bg-surface-container-low p-4 rounded-2xl border border-outline-variant">
              <div className="flex items-center gap-6">
                <div>
                  <span className="text-[10px] font-bold text-on-surface-variant/80 uppercase tracking-wider block">
                    {labels.duration}
                  </span>
                  <span className="font-semibold">{formattedDuration}</span>
                </div>
                <div>
                  <span className="text-[10px] font-bold text-on-surface-variant/80 uppercase tracking-wider block">
                    {labels.size}
                  </span>
                  <span className="font-semibold">{formattedSize}</span>
                </div>
                <div>
                  <span className="text-[10px] font-bold text-on-surface-variant/80 uppercase tracking-wider block">
                    {labels.filterStatus}
                  </span>
                  <span className="font-semibold capitalize">{video.status}</span>
                </div>
              </div>

              <div className="flex gap-2">
                {(video.status === 'unprocessed' || video.status === 'failed' || video.status === 'completed') && (
                  <button
                    onClick={onProcess}
                    className="md-state-layer md-filled-button px-4 py-2 font-semibold flex items-center gap-1 text-xs"
                  >
                    <RefreshCw size={14} />
                    {video.status === 'completed' ? labels.reanalyze : labels.analyze}
                  </button>
                )}
                <button
                  onClick={onDelete}
                  className="md-state-layer md-tonal-button text-error hover:bg-error-container/30 px-4 py-2 font-semibold flex items-center gap-1 text-xs"
                >
                  <Trash2 size={14} />
                  {labels.delete}
                </button>
              </div>
            </div>
            
            {video.error_message && (
              <div className="flex items-start gap-2 rounded-2xl bg-error-container px-4 py-3 text-xs font-semibold text-on-error-container border border-error/20">
                <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />
                <span>{video.error_message}</span>
              </div>
            )}

            {/* StashDB & Renaming Integration Section */}
            <div className="md-tonal-card p-4 space-y-4 border border-outline-variant bg-surface-container-low/30 rounded-2xl mt-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <HardDrive size={18} className="text-primary-700" />
                  <h4 className="font-extrabold text-sm text-on-surface">
                    {language === 'ru' ? 'Связь со StashDB и Переименование' : 'StashDB & Renaming'}
                  </h4>
                </div>
                {video.stashdb_scene_id && (
                  <span className="rounded-chip bg-success-container px-2 py-0.5 text-[9px] font-bold text-on-success-container uppercase tracking-wider">
                    {language === 'ru' ? 'Связано' : 'Linked'}
                  </span>
                )}
              </div>

              {/* Error messages */}
              {stashdbError && (
                <div className="flex items-start gap-1.5 rounded-xl bg-error-container p-2.5 text-xs font-semibold text-on-error-container border border-error/20">
                  <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />
                  <span>{stashdbError}</span>
                </div>
              )}
              {renameError && (
                <div className="flex items-start gap-1.5 rounded-xl bg-error-container p-2.5 text-xs font-semibold text-on-error-container border border-error/20">
                  <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />
                  <span>{renameError}</span>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-2">
                <button
                  onClick={handleSearchStashdb}
                  disabled={isSearchingCandidates || isMatchingStashdb}
                  className="md-state-layer md-tonal-button text-xs py-2 px-3 font-semibold flex-1 flex items-center justify-center gap-1.5 disabled:opacity-50"
                >
                  <RefreshCw size={14} className={isSearchingCandidates || isMatchingStashdb ? 'animate-spin' : ''} />
                  <span>{isSearchingCandidates ? (language === 'ru' ? 'Поиск...' : 'Searching...') : (language === 'ru' ? 'Поиск в StashDB' : 'Match StashDB')}</span>
                </button>

                <button
                  onClick={() => setIsEditingName(!isEditingName)}
                  className="md-state-layer md-tonal-button text-xs py-2 px-3 font-semibold flex-1 flex items-center justify-center gap-1.5"
                >
                  <span>{language === 'ru' ? 'Переименовать' : 'Rename'}</span>
                </button>
              </div>

              <div className="space-y-1.5 rounded-xl border border-outline-variant/50 bg-surface/70 p-2.5">
                <label className="block text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
                  {language === 'ru' ? 'Ссылка на сцену StashDB' : 'Manual StashDB scene link'}
                </label>
                <div className="flex gap-2">
                  <input
                    type="url"
                    value={manualSceneUrl}
                    onChange={(event) => setManualSceneUrl(event.target.value)}
                    className="md-text-field min-w-0 flex-1 px-2.5 py-1.5 text-xs font-semibold"
                    placeholder="https://stashdb.org/scenes/..."
                  />
                  <button
                    onClick={handleLinkSceneUrl}
                    disabled={isLinkingSceneUrl || !manualSceneUrl.trim()}
                    className="md-state-layer rounded-chip border border-primary-500/60 bg-primary-600 px-3 py-1.5 text-[10px] font-extrabold text-white shadow-md shadow-primary-900/25 transition-colors hover:bg-primary-500 disabled:cursor-not-allowed disabled:border-outline-variant disabled:bg-surface-container-highest disabled:text-on-surface-variant disabled:shadow-none"
                  >
                    {isLinkingSceneUrl ? (language === 'ru' ? 'Связь...' : 'Linking...') : (language === 'ru' ? 'Связать' : 'Link')}
                  </button>
                </div>
              </div>

              {/* Search info + Candidates list */}
              {stashdbCandidates && stashdbCandidates.length > 0 && (
                <div className="space-y-2.5 max-h-80 overflow-y-auto p-1 bg-surface-container rounded-xl border border-outline-variant/60">
                  {/* Search info header */}
                  {searchInfo && (
                    <div className="px-2.5 pt-2 pb-1 space-y-1 border-b border-outline-variant/30">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold text-primary-700 uppercase tracking-wider">
                          {language === 'ru'
                            ? `Найдено ${searchInfo.total_unique_results} результат(ов) по ${searchInfo.queries_used.length} запрос(ам)`
                            : `Found ${searchInfo.total_unique_results} result(s) from ${searchInfo.queries_used.length} quer${searchInfo.queries_used.length === 1 ? 'y' : 'ies'}`}
                        </span>
                      </div>
                      {searchInfo.detected_actors.length > 0 && (
                        <p className="text-[9px] text-on-surface-variant">
                          <span className="font-bold">{language === 'ru' ? 'Актёры из видео: ' : 'Detected actors: '}</span>
                          {searchInfo.detected_actors.join(', ')}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-1">
                        {searchInfo.queries_used.map((q, i) => (
                          <span
                            key={i}
                            title={`${q.results} results (${q.new} new)`}
                            className={`inline-flex items-center gap-0.5 text-[8px] px-1.5 py-0.5 rounded-chip font-medium ${
                              q.new > 0
                                ? 'bg-primary-container text-primary-700'
                                : 'bg-surface-container-highest text-on-surface-variant/60'
                            }`}
                          >
                            <span className="max-w-[120px] truncate">"{q.query}"</span>
                            <span className="font-bold">→{q.new}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="text-[10px] font-bold text-primary-700 uppercase tracking-wider px-2 py-1">
                    {language === 'ru' ? 'Выберите подходящий вариант:' : 'Select matching scene:'}
                  </div>
                  {stashdbCandidates.map((cand) => (
                    <div key={cand.scene_id} className="p-2.5 bg-surface rounded-lg border border-outline-variant/40 hover:border-primary/50 transition-all flex gap-3 text-xs justify-between items-start animate-fade-in">
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex gap-2 items-center">
                          <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded-chip ${
                            cand.score >= 60 ? 'bg-success-container text-on-success-container' :
                            cand.score >= 30 ? 'bg-warning-container text-on-warning-container' :
                            'bg-surface-container-highest text-on-surface-variant'
                          }`}>
                            {cand.score}%
                          </span>
                          <span className="font-extrabold text-on-surface truncate block" title={cand.title}>
                            {cand.title}
                          </span>
                        </div>
                        <p className="text-[10px] text-on-surface-variant font-medium">
                          <span className="font-bold">{language === 'ru' ? 'Студия: ' : 'Studio: '}</span>{cand.studio || '-'} 
                          {cand.date && ` | ${cand.date}`}
                        </p>
                        {cand.performers.length > 0 && (
                          <p className="text-[9px] text-on-surface-variant/80 truncate">
                            <span className="font-bold">{language === 'ru' ? 'Актеры: ' : 'Actors: '}</span>{cand.performers.join(', ')}
                          </p>
                        )}
                      </div>
                      <button
                        onClick={() => handleLinkCandidate(cand)}
                        className="md-state-layer self-center whitespace-nowrap rounded-chip border border-primary-500/60 bg-primary-600 px-3 py-1.5 text-[10px] font-extrabold text-white shadow-md shadow-primary-900/25 transition-colors hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-300"
                      >
                        {language === 'ru' ? 'Связать' : 'Link'}
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* StashDB Match Info Card */}
              {stashdbMatchInfo && (
                <div className="bg-surface p-3 rounded-xl border border-outline-variant/60 space-y-2 text-xs">
                  <div className="font-bold text-primary-700 text-[11px] uppercase tracking-wider">
                    {language === 'ru' ? 'Информация о сцене' : 'Scene Details'}
                  </div>
                  <div className="space-y-1 text-on-surface-variant font-medium">
                    <p><span className="font-bold text-on-surface">{language === 'ru' ? 'Название: ' : 'Title: '}</span>{stashdbMatchInfo.title}</p>
                    {stashdbMatchInfo.studio && (
                      <p><span className="font-bold text-on-surface">{language === 'ru' ? 'Студия: ' : 'Studio: '}</span>{stashdbMatchInfo.studio}</p>
                    )}
                    {stashdbMatchInfo.performers.length > 0 && (
                      <p><span className="font-bold text-on-surface">{language === 'ru' ? 'Исполнители: ' : 'Performers: '}</span>{stashdbMatchInfo.performers.join(', ')}</p>
                    )}
                    <p className="flex items-center gap-1 text-[10px] text-green-700 font-bold">
                      <Download size={10} />
                      {language === 'ru' ? 'Обложка сцены успешно загружена' : 'Cover image downloaded successfully'}
                    </p>
                  </div>
                </div>
              )}

              {/* Inline Renaming Panel */}
              {isEditingName && (
                <div className="bg-surface p-3 rounded-xl border border-outline-variant/60 space-y-3">
                  {suggestedName && (
                    <div className="space-y-1.5">
                      <div className="text-[10px] font-bold text-primary-700 uppercase tracking-wider">
                        {language === 'ru' ? 'Рекомендованное имя (StashDB):' : 'Suggested Name (StashDB):'}
                      </div>
                      <div className="flex gap-1.5 items-center">
                        <span className="text-xs font-semibold bg-surface-container-low px-2 py-1 rounded border border-outline-variant break-all flex-1 text-on-surface font-semibold">
                          {suggestedName}
                        </span>
                        <button
                          onClick={() => setManualRenameVal(suggestedName)}
                          className="md-state-layer rounded-chip border border-primary-500/60 bg-primary-600 px-3 py-1.5 text-[10px] font-extrabold text-white shadow-md shadow-primary-900/25 transition-colors hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-300"
                        >
                          {language === 'ru' ? 'Вставить' : 'Use'}
                        </button>
                      </div>
                    </div>
                  )}

                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider block">
                      {language === 'ru' ? 'Новое имя файла:' : 'New Filename:'}
                    </label>
                    <input
                      type="text"
                      value={manualRenameVal}
                      onChange={(e) => setManualRenameVal(e.target.value)}
                      className="md-text-field w-full px-2.5 py-1.5 text-xs font-semibold"
                      placeholder="filename.mp4"
                    />
                  </div>

                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => setIsEditingName(false)}
                      className="text-[11px] font-bold text-on-surface-variant hover:bg-surface-container px-3 py-1.5 rounded-chip transition-colors"
                    >
                      {language === 'ru' ? 'Отмена' : 'Cancel'}
                    </button>
                    <button
                      onClick={handleRename}
                      disabled={isRenaming || !manualRenameVal || manualRenameVal === video.filename}
                      className="md-state-layer rounded-chip border border-primary-500/60 bg-primary-600 px-3 py-1.5 text-[11px] font-extrabold text-white shadow-md shadow-primary-900/25 transition-colors hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-300 disabled:cursor-not-allowed disabled:border-outline-variant disabled:bg-surface-container-highest disabled:text-on-surface-variant disabled:shadow-none"
                    >
                      {isRenaming ? (language === 'ru' ? 'Сохранение...' : 'Renaming...') : (language === 'ru' ? 'Применить' : 'Apply')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Timeline Detections & Player Settings Tabs */}
          <div className="flex flex-col overflow-hidden bg-surface-container-lowest">
            
            {/* Tabs Header */}
            <div className="grid grid-cols-2 border-b border-outline-variant bg-surface-container-low">
              <button
                onClick={() => setActiveTab('detections')}
                className={`py-3 text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 border-b-2 transition-all ${
                  activeTab === 'detections'
                    ? 'border-primary text-primary-700 bg-surface'
                    : 'border-transparent text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low'
                }`}
              >
                <Users size={14} />
                <span>{language === 'ru' ? 'Детекции' : 'Detections'}</span>
              </button>
              <button
                onClick={() => setActiveTab('filters')}
                className={`py-3 text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 border-b-2 transition-all ${
                  activeTab === 'filters'
                    ? 'border-primary text-primary-700 bg-surface'
                    : 'border-transparent text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low'
                }`}
              >
                <Sliders size={14} />
                <span>{language === 'ru' ? 'Фильтры' : 'Filters'}</span>
              </button>
            </div>

            {/* Tab contents */}
            {activeTab === 'detections' ? (
              <div className="flex-1 flex flex-col overflow-hidden">
                <div className="p-3 border-b border-outline-variant/30 bg-surface-container-low/50 flex flex-col gap-2">
                  <div className="flex items-center justify-between text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">
                    <span>{labels.detectedActors}</span>
                    <span className="rounded-chip bg-surface px-2 py-0.5 text-[10px]">
                      {Object.keys(actorDetections).length}
                    </span>
                  </div>
                  {/* Manual actor search */}
                  <div className="relative mt-1">
                    <Search
                      size={14}
                      className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant"
                      aria-hidden="true"
                    />
                    <input
                      type="search"
                      value={actorSearchQuery}
                      onChange={(e) => setActorSearchQuery(e.target.value)}
                      placeholder={language === 'ru' ? '+ Найти актера в базе...' : '+ Search actor database...'}
                      className="md-text-field w-full py-1.5 pl-8 pr-8 text-xs font-semibold text-on-surface bg-surface"
                    />
                    {isActorSearchLoading && (
                      <RefreshCw
                        size={13}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 animate-spin text-primary-700"
                        aria-hidden="true"
                      />
                    )}
                    {actorSearchQuery.trim().length >= 2 && (
                      <div className="absolute left-0 right-0 top-[calc(100%+6px)] z-20 max-h-72 overflow-y-auto rounded-2xl border border-outline-variant bg-surface-container-lowest p-1.5 shadow-xl animate-fade-in">
                        {actorSearchError ? (
                          <div className="px-3 py-2 text-xs font-semibold text-error">{actorSearchError}</div>
                        ) : actorSearchResults.length > 0 ? (
                          actorSearchResults.map((actor) => (
                            <button
                              key={actor.id}
                              type="button"
                              onClick={() => handleAddActor(actor.id)}
                              className="md-state-layer flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-xs font-bold text-on-surface transition-colors hover:bg-primary-container hover:text-primary-700"
                            >
                              <span className="min-w-0 truncate">{actor.name}</span>
                              <span className="flex-shrink-0 rounded-chip bg-surface-container px-2 py-0.5 text-[10px] font-semibold text-on-surface-variant">
                                {actor.scene_count ?? 0}
                              </span>
                            </button>
                          ))
                        ) : isActorSearchLoading ? (
                          <div className="px-3 py-2 text-xs font-semibold text-on-surface-variant">
                            {language === 'ru' ? 'Поиск...' : 'Searching...'}
                          </div>
                        ) : (
                          <div className="px-3 py-2 text-xs font-semibold text-on-surface-variant">
                            {language === 'ru' ? 'Ничего не найдено' : 'No actors found'}
                          </div>
                        )}
                      </div>
                    )}
                    {false && (
                    <select
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val) {
                          handleAddActor(Number(val));
                          e.target.value = '';
                        }
                      }}
                      className="md-text-field w-full py-1 px-2 text-xs font-semibold text-on-surface bg-surface"
                      defaultValue=""
                    >
                      <option value="" disabled>
                        {language === 'ru' ? '+ Добавить актера вручную...' : '+ Add actor manually...'}
                      </option>
                      {actorsList
                        .filter((act) => !actorDetections[act.id])
                        .map((act) => (
                          <option key={act.id} value={act.id}>
                            {act.name}
                          </option>
                        ))}
                    </select>
                    )}
                  </div>
                </div>
                
                <div className="flex-1 overflow-y-auto divide-y divide-outline-variant">
                  {Object.keys(actorDetections).length === 0 ? (
                    <div className="p-6 text-center text-xs text-on-surface-variant/80 font-medium">
                      {video.status === 'processing' 
                        ? labels.processing 
                        : video.status === 'completed' 
                          ? labels.noActors 
                          : labels.unprocessed}
                    </div>
                  ) : (
                    (Object.entries(actorDetections) as [string, { name: string; timestamps: number[] }][]).map(([actorId, data]) => {
                      const isExpanded = expandedActorId === Number(actorId)
                      const isConfirmedByStashdb = confirmedPerformers.has(normalizePersonName(data.name))
                      
                      return (
                        <div key={actorId} className="flex flex-col animate-fade-in">
                          <div className="flex items-center justify-between hover:bg-surface-container transition-colors pr-2">
                            <button
                              onClick={() => setExpandedActorId(isExpanded ? null : Number(actorId))}
                              className="flex-1 flex items-center justify-between p-3.5 text-left"
                            >
                              <span className="flex min-w-0 items-center gap-1.5 pr-4">
                                <span className="truncate text-sm font-extrabold text-on-surface">
                                  {data.name}
                                </span>
                                {isConfirmedByStashdb && (
                                  <CheckCircle2
                                    size={15}
                                    className="flex-shrink-0 text-success"
                                    aria-label={language === 'ru' ? 'Подтверждено StashDB' : 'Confirmed by StashDB'}
                                  />
                                )}
                              </span>
                              <div className="flex items-center gap-1.5 flex-shrink-0">
                                <span className="rounded-chip bg-primary-container px-2 py-0.5 text-[10px] font-bold text-primary-700">
                                  {data.timestamps.length}
                                </span>
                                {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                              </div>
                            </button>
                            <button
                              onClick={() => handleRemoveActor(Number(actorId))}
                              className="p-2 text-on-surface-variant hover:text-error rounded-xl hover:bg-error-container/30 transition-colors"
                              title={language === 'ru' ? 'Удалить актера из видео' : 'Remove actor from video'}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>

                          {isExpanded && (
                            <div className="bg-surface-container-low/50 px-4 py-3 border-t border-outline-variant/30">
                              <p className="text-[10px] font-bold text-on-surface-variant/80 uppercase tracking-wider mb-2">
                                {labels.timeline} ({labels.clickToJump}):
                              </p>
                              <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto p-0.5">
                                {data.timestamps.map((sec: number, idx: number) => (
                                  <button
                                    key={idx}
                                    onClick={() => seekTo(sec)}
                                    className="md-state-layer flex items-center gap-1 bg-surface hover:bg-primary-container hover:text-primary-700 transition-colors border border-outline-variant px-2.5 py-1 rounded-chip text-[11px] font-semibold text-on-surface-variant shadow-sm"
                                  >
                                    <span>{formatDuration(sec)}</span>
                                    <ExternalLink size={8} />
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                <div className="space-y-3.5">
                  <h5 className="text-[11px] font-bold text-primary-700 uppercase tracking-wider">
                    {language === 'ru' ? 'Эффекты изображения' : 'Image Effects'}
                  </h5>
                  
                  {/* Brightness */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs font-semibold text-on-surface">
                      <span>{language === 'ru' ? 'Яркость' : 'Brightness'}</span>
                      <span className="text-on-surface-variant font-bold">{brightness}%</span>
                    </div>
                    <input
                      type="range"
                      min="50"
                      max="200"
                      value={brightness}
                      onChange={(e) => setBrightness(Number(e.target.value))}
                      className="w-full h-1.5 bg-surface-container-high rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                  </div>

                  {/* Contrast */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs font-semibold text-on-surface">
                      <span>{language === 'ru' ? 'Контрастность' : 'Contrast'}</span>
                      <span className="text-on-surface-variant font-bold">{contrast}%</span>
                    </div>
                    <input
                      type="range"
                      min="50"
                      max="200"
                      value={contrast}
                      onChange={(e) => setContrast(Number(e.target.value))}
                      className="w-full h-1.5 bg-surface-container-high rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                  </div>

                  {/* Saturation */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs font-semibold text-on-surface">
                      <span>{language === 'ru' ? 'Насыщенность' : 'Saturation'}</span>
                      <span className="text-on-surface-variant font-bold">{saturation}%</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="200"
                      value={saturation}
                      onChange={(e) => setSaturation(Number(e.target.value))}
                      className="w-full h-1.5 bg-surface-container-high rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                  </div>

                  {/* Grayscale */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs font-semibold text-on-surface">
                      <span>{language === 'ru' ? 'ЧБ / Оттенки серого' : 'Grayscale'}</span>
                      <span className="text-on-surface-variant font-bold">{grayscale}%</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={grayscale}
                      onChange={(e) => setGrayscale(Number(e.target.value))}
                      className="w-full h-1.5 bg-surface-container-high rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                  </div>

                  {/* Invert */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs font-semibold text-on-surface">
                      <span>{language === 'ru' ? 'Инверсия цветов' : 'Invert'}</span>
                      <span className="text-on-surface-variant font-bold">{invert}%</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={invert}
                      onChange={(e) => setInvert(Number(e.target.value))}
                      className="w-full h-1.5 bg-surface-container-high rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                  </div>
                </div>

                <div className="border-t border-outline-variant/30 pt-3 space-y-3.5">
                  <h5 className="text-[11px] font-bold text-primary-700 uppercase tracking-wider">
                    {language === 'ru' ? 'Геометрия и масштаб' : 'Geometry & Aspect'}
                  </h5>

                  {/* Aspect Ratio / Fit */}
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-on-surface block mb-1">
                      {language === 'ru' ? 'Заполнение экрана' : 'Screen Fit'}
                    </label>
                    <div className="grid grid-cols-3 gap-1">
                      {(['contain', 'cover', 'fill'] as const).map((mode) => (
                        <button
                          key={mode}
                          onClick={() => setAspectRatio(mode)}
                          className={`py-1 text-[11px] font-semibold rounded-chip border transition-all ${
                            aspectRatio === mode
                              ? 'bg-primary-container border-primary text-primary-700'
                              : 'bg-surface border-outline-variant text-on-surface-variant hover:bg-surface-container'
                          }`}
                        >
                          {mode === 'contain' ? (language === 'ru' ? 'Вписать' : 'Contain') :
                           mode === 'cover' ? (language === 'ru' ? 'Заполнить' : 'Cover') :
                           (language === 'ru' ? 'Растянуть' : 'Stretch')}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Rotation & Mirror */}
                  <div className="flex gap-2 justify-between items-center">
                    <span className="text-xs font-semibold text-on-surface">
                      {language === 'ru' ? 'Отразить по горизонтали' : 'Flip Horizontally'}
                    </span>
                    <button
                      onClick={() => setMirror(!mirror)}
                      className={`px-3 py-1.5 text-xs font-semibold rounded-chip border transition-all ${
                        mirror
                          ? 'bg-primary-container border-primary text-primary-700'
                          : 'bg-surface border-outline-variant text-on-surface-variant hover:bg-surface-container'
                      }`}
                    >
                      {mirror ? (language === 'ru' ? 'Зеркально' : 'Mirrored') : (language === 'ru' ? 'Обычный' : 'Normal')}
                    </button>
                  </div>

                  <div className="flex gap-2 justify-between items-center">
                    <span className="text-xs font-semibold text-on-surface">
                      {language === 'ru' ? 'Повернуть видео' : 'Rotate Video'}
                    </span>
                    <button
                      onClick={() => setRotate((prev) => (prev + 90) % 360)}
                      className="md-state-layer md-tonal-button text-xs py-1.5 px-3 font-semibold flex items-center gap-1"
                    >
                      <RotateCw size={13} />
                      <span>{rotate}°</span>
                    </button>
                  </div>
                </div>

                <div className="border-t border-outline-variant/30 pt-3 space-y-3.5">
                  <h5 className="text-[11px] font-bold text-primary-700 uppercase tracking-wider">
                    {language === 'ru' ? 'Скорость воспроизведения' : 'Playback Speed'}
                  </h5>
                  <div className="grid grid-cols-4 gap-1">
                    {[0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0].map((speed) => (
                      <button
                        key={speed}
                        onClick={() => setPlaybackSpeed(speed)}
                        className={`py-1 text-[11px] font-semibold rounded-chip border transition-all ${
                          playbackSpeed === speed
                            ? 'bg-primary-container border-primary text-primary-700'
                            : 'bg-surface border-outline-variant text-on-surface-variant hover:bg-surface-container'
                        }`}
                      >
                        {speed === 1.0 ? 'Normal' : `${speed}x`}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="border-t border-outline-variant/30 pt-4">
                  <button
                    onClick={() => {
                      setBrightness(100)
                      setContrast(100)
                      setSaturation(100)
                      setGrayscale(0)
                      setInvert(0)
                      setPlaybackSpeed(1.0)
                      setRotate(0)
                      setMirror(false)
                      setAspectRatio('contain')
                    }}
                    className="w-full md-state-layer md-tonal-button py-2 text-xs font-bold text-error flex items-center justify-center gap-1.5 hover:bg-error-container/30"
                  >
                    {language === 'ru' ? 'Сбросить все настройки' : 'Reset All Settings'}
                  </button>
                </div>
              </div>
            )}
          </div>
          
        </div>
      </div>
    </div>
  )
}

function formatSize(bytes: number | null): string {
  if (!bytes) return 'N/A'
  const mb = bytes / (1024 * 1024)
  if (mb < 1024) return `${mb.toFixed(1)} MB`
  return `${(mb / 1024).toFixed(1)} GB`
}

function videoThumbnailSrc(video: Video): string {
  const url = `${video.thumbnail_url ?? `/api/thumbnails/${video.id}.jpg`}?t=${new Date(video.updated_at).getTime()}`
  return resolveMediaUrl(url) || url
}

function normalizePersonName(name: string): string {
  return name.toLowerCase().replace(/[^a-z]/g, '')
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return 'N/A'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const pad = (n: number) => String(n).padStart(2, '0')
  if (h > 0) return `${h}:${pad(m)}:${pad(s)}`
  return `${pad(m)}:${pad(s)}`
}

function videosLabels(language: 'en' | 'ru') {
  if (language === 'ru') {
    return {
      title: 'Медиа-центр',
      scanFolder: 'Сканировать папку',
      scannedMessage: (scanned: number, added: number) => `Найдено видео: ${scanned}, новых добавлено: ${added}`,
      videosCount: 'Всего видео',
      searchVideos: 'Поиск по имени файла...',
      filterStatus: 'Статус',
      filterActor: 'Исполнитель',
      all: 'Все',
      unprocessed: 'Не обработано',
      processing: 'Обработка...',
      completed: 'Завершено',
      failed: 'Ошибка',
      analyze: 'Анализировать',
      reanalyze: 'Переанализировать',
      delete: 'Удалить',
      confirmDelete: 'Вы действительно хотите удалить запись этого видео?',
      noVideos: 'Видео не найдены. Нажмите «Сканировать папку» для поиска в D:\\Videos.',
      duration: 'Длительность',
      size: 'Размер',
      detectedActors: 'Распознанные актеры',
      timeline: 'Таймлайн присутствия',
      play: 'Смотреть',
      noActors: 'Исполнители не обнаружены',
      clickToJump: 'нажмите для перехода',
      close: 'Закрыть',
    }
  }
  return {
    title: 'Media Center',
    scanFolder: 'Scan folder',
    scannedMessage: (scanned: number, added: number) => `Scanned: ${scanned}, added ${added} new videos`,
    videosCount: 'Total videos',
    searchVideos: 'Search by filename...',
    filterStatus: 'Status',
    filterActor: 'Actor',
    all: 'All',
    unprocessed: 'Unprocessed',
    processing: 'Processing...',
    completed: 'Completed',
    failed: 'Failed',
    analyze: 'Analyze',
    reanalyze: 'Reanalyze',
    delete: 'Delete',
    confirmDelete: 'Are you sure you want to delete this video record?',
    noVideos: 'No videos found. Click "Scan folder" to search in D:\\Videos.',
    duration: 'Duration',
    size: 'Size',
    detectedActors: 'Detected Actors',
    timeline: 'Timeline Presence',
    play: 'Play',
    noActors: 'No actors detected',
    clickToJump: 'click to jump',
    close: 'Close',
  }
}
