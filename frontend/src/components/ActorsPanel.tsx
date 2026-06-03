import { useState, useEffect, useCallback, useRef } from 'react'
import type { ReactNode } from 'react'
import {
  Search,
  Users,
  ChevronLeft,
  ChevronRight,
  X,
  Trash2,
  Image as ImageIcon,
  Plus,
  Calendar,
  Camera,
  ExternalLink,
  Film,
  Twitter,
  Download,
  Loader2,
} from 'lucide-react'
import {
  getActors,
  getActor,
  createActor,
  deleteActor,
  addActorImage,
  searchStashdb,
  importStashdbPerformer,
} from '../lib/api'
import { useAppStore } from '../hooks/useStore'
import { useUiPreferences } from '../lib/uiPreferences'
import type { Actor } from '../types'

interface ActorsPanelProps {
  onAddActor: (actor: Actor) => void
}

export function ActorsPanel({ onAddActor }: ActorsPanelProps) {
  const { language, t } = useUiPreferences()
  const labels = actorLabelsFixed(language)
  const [showAddForm, setShowAddForm] = useState(false)
  const [selectedActor, setSelectedActor] = useState<Actor | null>(null)
  const detailTriggerRef = useRef<HTMLElement | null>(null)
  const [breastFilter, setBreastFilter] = useState<'all' | 'augmented' | 'natural'>('all')
  const [photoFilter, setPhotoFilter] = useState<'all' | 'withPhoto'>('all')
  const [minScenesFilter, setMinScenesFilter] = useState<'all' | '10' | '50'>('all')
  const [showImageUpload, setShowImageUpload] = useState(false)
  const [isAdding, setIsAdding] = useState(false)
  const [isDeleting, setIsDeleting] = useState<number | null>(null)
  const [isLoadingDetails, setIsLoadingDetails] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [newBirthYear, setNewBirthYear] = useState('')
  const [newGender, setNewGender] = useState('')
  const [newBio, setNewBio] = useState('')
  const [newFilmography, setNewFilmography] = useState('')
  const [newTags, setNewTags] = useState('')
  const [newActorImageFile, setNewActorImageFile] = useState<File | null>(null)
  const [imageFile, setImageFile] = useState<File | null>(null)

  // Simple import states
  const [isAdvancedMode, setIsAdvancedMode] = useState(false)
  const [stashQuery, setStashQuery] = useState('')
  const [stashPerformers, setStashPerformers] = useState<any[]>([])
  const [isSearchingStash, setIsSearchingStash] = useState(false)
  const [importingId, setImportingId] = useState<string | null>(null)
  const [imageCounts, setImageCounts] = useState<Record<string, number>>({})
  const [imageOrder, setImageOrder] = useState<'largest' | 'end' | 'start'>('largest')
  const [checkFace, setCheckFace] = useState(true)
  const [overwriteMetadata, setOverwriteMetadata] = useState(false)

  // Rebuild index states
  const [rebuildStatus, setRebuildStatus] = useState<string | null>(null)



  const actors = useAppStore((s) => s.actors)
  const totalActors = useAppStore((s) => s.totalActors)
  const currentPage = useAppStore((s) => s.currentPage)
  const searchQuery = useAppStore((s) => s.searchQuery)
  const setActors = useAppStore((s) => s.setActors)
  const setTotalActors = useAppStore((s) => s.setTotalActors)
  const setCurrentPage = useAppStore((s) => s.setCurrentPage)
  const setSearchQuery = useAppStore((s) => s.setSearchQuery)

  const PAGE_SIZE = 12
  const actorFilters = {
    breastType:
      breastFilter === 'augmented'
        ? ('FAKE' as const)
        : breastFilter === 'natural'
          ? ('NATURAL' as const)
          : undefined,
    hasPhoto: photoFilter === 'withPhoto' ? true : undefined,
    minScenes: minScenesFilter === 'all' ? undefined : Number(minScenesFilter),
  }

  const loadActors = useCallback(async (page: number = 1, search?: string) => {
    try {
      setError(null)
      const data = await getActors(page, PAGE_SIZE, search, actorFilters)
      const filteredActors = data.actors.filter((actor) => actorMatchesActiveFilters(actor, actorFilters))
      setActors(filteredActors)
      setTotalActors(filteredActors.length === data.actors.length ? data.total : filteredActors.length)
      setCurrentPage(page)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('failedLoadActors'))
    }
  }, [actorFilters.breastType, actorFilters.hasPhoto, actorFilters.minScenes, setActors, setTotalActors, setCurrentPage, t])

  useEffect(() => {
    loadActors(1, searchQuery)
  }, [loadActors, searchQuery])



  const handleStashSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!stashQuery.trim()) return

    setIsSearchingStash(true)
    setError(null)
    setRebuildStatus(null)
    try {
      const data = await searchStashdb(stashQuery.trim(), 1, 10)
      setStashPerformers(data.performers)

      // Initialize image counts
      const counts: Record<string, number> = {}
      data.performers.forEach((p) => {
        counts[p.id] = 3 // default to 3 images
      })
      setImageCounts(counts)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : language === 'ru'
            ? 'Не удалось выполнить поиск в StashDB. Проверьте STASHDB_API_KEY в файле .env.'
            : 'Failed to search StashDB. Check STASHDB_API_KEY in .env.'
      )
      setStashPerformers([])
    } finally {
      setIsSearchingStash(false)
    }
  }

  const handleSimpleImport = async (performerId: string) => {
    setImportingId(performerId)
    setError(null)
    setRebuildStatus(null)
    const imgCount = imageCounts[performerId] ?? 3

    try {
      // 1. Import performer (backend indexes faces incrementally — no full rebuild needed)
      const result = await importStashdbPerformer(performerId, {
        imageCount: imgCount,
        imageOrder,
        checkFace,
        overwriteMetadata,
      })

      // 2. Show success info
      const facesMsg = result.faces_indexed > 0
        ? (language === 'ru'
          ? `✓ Импортирован: ${result.images_downloaded} фото, ${result.faces_indexed} лиц проиндексировано`
          : `✓ Imported: ${result.images_downloaded} photos, ${result.faces_indexed} faces indexed`)
        : (language === 'ru'
          ? `✓ Импортирован: ${result.images_downloaded} фото (лица не найдены)`
          : `✓ Imported: ${result.images_downloaded} photos (no faces detected)`)
      setRebuildStatus(facesMsg)
      setTimeout(() => setRebuildStatus(null), 5000)

      // 3. Reset search form and candidates, reload actors
      setStashQuery('')
      setStashPerformers([])
      setShowAddForm(false)
      loadActors(1, searchQuery)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setImportingId(null)
    }
  }

  const handleAddActor = async () => {
    if (!newName.trim()) return
    setIsAdding(true)
    try {
      setError(null)
      const actor = await createActor({
        name: newName.trim(),
        birth_year: newBirthYear ? parseInt(newBirthYear) : undefined,
        gender: newGender || undefined,
        bio: newBio || undefined,
        filmography: newFilmography || undefined,
        tags: newTags,
      })
      if (newActorImageFile) {
        await addActorImage(actor.id, newActorImageFile)
      }
      onAddActor(actor)
      setShowAddForm(false)
      resetForm()
      loadActors(1, searchQuery)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('failedAddActor'))
    } finally {
      setIsAdding(false)
    }
  }

  const handleDeleteActor = async (id: number) => {
    if (!confirm(t('confirmDelete'))) return
    setIsDeleting(id)
    try {
      setError(null)
      await deleteActor(id)
      loadActors(currentPage, searchQuery)
      if (selectedActor?.id === id) setSelectedActor(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('failedDeleteActor'))
    } finally {
      setIsDeleting(null)
    }
  }

  const openActorDetails = async (actor: Actor, trigger?: HTMLElement | null) => {
    detailTriggerRef.current = trigger ?? null
    setIsLoadingDetails(actor.id)
    try {
      setError(null)
      const detailedActor = await getActor(actor.id)
      setSelectedActor(detailedActor)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('failedLoadActorDetails'))
      setSelectedActor(actor)
    } finally {
      setIsLoadingDetails(null)
    }
  }

  const handleAddImage = async () => {
    if (!imageFile || !selectedActor) return
    try {
      setError(null)
      await addActorImage(selectedActor.id, imageFile)
      setShowImageUpload(false)
      setImageFile(null)
      loadActors(currentPage, searchQuery)
      if (selectedActor) {
        const updated = await getActor(selectedActor.id)
        setSelectedActor(updated)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t('failedAddImage'))
    }
  }

  const resetForm = () => {
    setNewName('')
    setNewBirthYear('')
    setNewGender('')
    setNewBio('')
    setNewFilmography('')
    setNewTags('')
    setNewActorImageFile(null)
  }

  const totalPages = Math.ceil(totalActors / PAGE_SIZE)

  const closeActorDetails = () => {
    setSelectedActor(null)
    window.setTimeout(() => detailTriggerRef.current?.focus(), 0)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Users size={24} className="text-primary-700" />
          <h2 className="text-title-large text-on-surface">{t('actorDatabase')}</h2>
          <span className="rounded-chip bg-surface-container px-2.5 py-0.5 text-sm font-semibold text-on-surface-variant">
            {totalActors}
          </span>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="md-state-layer md-filled-button flex items-center gap-2 px-4 py-2 font-semibold"
        >
          <Plus size={18} />
          {t('addActor')}
        </button>
      </div>

      {error && (
        <div className="mb-4 flex items-start justify-between gap-3 rounded-2xl border border-error-container bg-error-container px-4 py-3 text-sm font-medium text-on-error-container">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="md-state-layer rounded-xl p-1 text-on-error-container hover:bg-surface" aria-label={t('cancel')}>
            <X size={16} aria-hidden="true" />
          </button>
        </div>
      )}

      {rebuildStatus && (
        <div className="mb-4 flex items-start justify-between gap-3 rounded-2xl border border-primary-container bg-primary-container/20 px-4 py-3 text-sm font-medium text-primary-700">
          <div className="flex items-center gap-2">
            <Loader2 size={18} className="animate-spin text-primary-700" />
            <span>{rebuildStatus}</span>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant" size={18} />
        <input
          type="text"
          placeholder={t('searchActors')}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="md-text-field w-full py-2.5 pl-10 pr-4"
        />
      </div>

      <div className="mb-4 flex flex-wrap gap-2" aria-label={labels.filters}>
        <FilterChip active={breastFilter === 'all'} onClick={() => setBreastFilter('all')}>
          {labels.all}
        </FilterChip>
        <FilterChip active={breastFilter === 'augmented'} onClick={() => setBreastFilter('augmented')}>
          {labels.augmented}
        </FilterChip>
        <FilterChip active={breastFilter === 'natural'} onClick={() => setBreastFilter('natural')}>
          {labels.natural}
        </FilterChip>
        <FilterChip active={photoFilter === 'withPhoto'} onClick={() => setPhotoFilter(photoFilter === 'withPhoto' ? 'all' : 'withPhoto')}>
          {labels.withPhoto}
        </FilterChip>
        <FilterChip active={minScenesFilter === '10'} onClick={() => setMinScenesFilter(minScenesFilter === '10' ? 'all' : '10')}>
          {labels.scenes10}
        </FilterChip>
        <FilterChip active={minScenesFilter === '50'} onClick={() => setMinScenesFilter(minScenesFilter === '50' ? 'all' : '50')}>
          {labels.scenes50}
        </FilterChip>
      </div>

      {/* Add Actor Form */}
      {showAddForm && (
        <div className="md-card mb-6 p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6 border-b border-outline-variant/60 pb-3">
            <h3 className="text-title-large text-on-surface">{t('addNewActor')}</h3>
            <label className="flex items-center gap-2 cursor-pointer text-sm font-semibold text-on-surface-variant select-none">
              <input
                type="checkbox"
                checked={isAdvancedMode}
                onChange={(e) => setIsAdvancedMode(e.target.checked)}
                className="rounded border-outline-variant text-primary-500 focus:ring-primary-500 h-4 w-4 bg-surface"
              />
              <span>{language === 'ru' ? 'Ручной ввод (Advanced)' : 'Manual Entry (Advanced)'}</span>
            </label>
          </div>

          {!isAdvancedMode ? (
            <div className="space-y-4">
              <form onSubmit={handleStashSearch} className="flex gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant" size={18} />
                  <input
                    type="text"
                    placeholder={
                      language === 'ru'
                        ? 'Введите имя актера для поиска в StashDB...'
                        : 'Enter actor name to search on StashDB...'
                    }
                    value={stashQuery}
                    onChange={(e) => setStashQuery(e.target.value)}
                    className="md-text-field w-full py-2.5 pl-10 pr-4"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSearchingStash || !stashQuery.trim()}
                  className="md-state-layer md-filled-button px-6 font-semibold flex items-center gap-2"
                >
                  {isSearchingStash ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
                  <span>{isSearchingStash ? t('processing') : t('search')}</span>
                </button>
              </form>

              {/* Import configurations */}
              <div className="md-tonal-card p-4 rounded-2xl bg-surface-container/40 border border-outline-variant/40 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div>
                  <label className="block text-[10px] uppercase font-bold text-on-surface-variant mb-1.5 select-none">
                    {language === 'ru' ? 'Порядок скачивания фото' : 'Photo Download Order'}
                  </label>
                  <select
                    value={imageOrder}
                    onChange={(e) => setImageOrder(e.target.value as any)}
                    className="md-text-field py-1 px-3 w-full text-xs"
                    style={{ minHeight: '36px', height: '36px' }}
                  >
                    <option value="largest">{language === 'ru' ? 'Сначала большие по разрешению' : 'Largest Resolution First'}</option>
                    <option value="end">{language === 'ru' ? 'С конца списка StashDB (новые)' : 'From End (newer)'}</option>
                    <option value="start">{language === 'ru' ? 'С начала списка StashDB' : 'From Start'}</option>
                  </select>
                </div>
                <div className="flex items-center sm:pt-4 select-none">
                  <label className="flex items-center gap-2 cursor-pointer font-semibold text-on-surface-variant">
                    <input
                      type="checkbox"
                      checked={checkFace}
                      onChange={(e) => setCheckFace(e.target.checked)}
                      className="rounded border-outline-variant text-primary-500 focus:ring-primary-500 h-4 w-4 bg-surface"
                    />
                    <span>{language === 'ru' ? 'Удалять фото без лица (Y/n)' : 'Delete photos with no face'}</span>
                  </label>
                </div>
                <div className="flex items-center sm:pt-4 select-none">
                  <label className="flex items-center gap-2 cursor-pointer font-semibold text-on-surface-variant">
                    <input
                      type="checkbox"
                      checked={overwriteMetadata}
                      onChange={(e) => setOverwriteMetadata(e.target.checked)}
                      className="rounded border-outline-variant text-primary-500 focus:ring-primary-500 h-4 w-4 bg-surface"
                    />
                    <span>{language === 'ru' ? 'Перезаписать существующие' : 'Overwrite existing actor'}</span>
                  </label>
                </div>
              </div>

              {stashPerformers.length > 0 && (
                <div className="mt-4 space-y-3">
                  <p className="text-xs uppercase font-bold text-on-surface-variant tracking-wider">
                    {language === 'ru' ? 'Найденные совпадения в StashDB' : 'StashDB Matches'}
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {stashPerformers.map((p) => {
                      const initials = p.name.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)
                      const isImporting = importingId === p.id
                      const imgCount = imageCounts[p.id] ?? 3

                      return (
                        <div key={p.id} className="md-tonal-card flex flex-col justify-between p-4 border border-outline-variant rounded-2xl bg-surface-container-low">
                          <div className="flex items-start gap-4">
                            <div className="h-24 w-18 flex-shrink-0 overflow-hidden rounded-xl bg-surface-container shadow-sm">
                              {p.image_url ? (
                                <img src={p.image_url} alt={p.name} className="h-full w-full object-cover" loading="lazy" />
                              ) : (
                                <div className="flex h-full w-full items-center justify-center font-bold text-base text-on-surface-variant">
                                  {initials}
                                </div>
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <h4 className="truncate font-bold text-on-surface text-sm">{p.name}</h4>
                              {p.disambiguation && (
                                <p className="text-[11px] text-primary-700 italic truncate mb-1">({p.disambiguation})</p>
                              )}
                              <div className="mt-1 space-y-0.5 text-xs text-on-surface-variant">
                                {p.birth_date && (
                                  <p className="flex items-center gap-1.5">
                                    <Calendar size={11} />
                                    <span>{p.birth_date}</span>
                                  </p>
                                )}
                                {p.scene_count > 0 && (
                                  <p className="flex items-center gap-1.5">
                                    <Film size={11} />
                                    <span>{p.scene_count} {t('scenes').toLowerCase()}</span>
                                  </p>
                                )}
                                {p.breast_type && (
                                  <p className="text-[11px]">
                                    <span className="font-semibold">{t('breastType')}:</span> {p.breast_type.replace('_', ' ').toLowerCase()}
                                  </p>
                                )}
                              </div>
                            </div>
                          </div>

                          <div className="mt-3 pt-2 border-t border-outline-variant/60 flex items-center justify-between gap-3">
                            <div className="flex items-center gap-2">
                              <label className="text-[10px] uppercase font-bold text-on-surface-variant">
                                {language === 'ru' ? 'Фото' : 'Photos'}
                              </label>
                              <select
                                value={imgCount}
                                onChange={(e) => setImageCounts({ ...imageCounts, [p.id]: Number(e.target.value) })}
                                disabled={isImporting}
                                className="md-text-field py-0.5 px-2 text-xs"
                                style={{ minHeight: '28px', height: '28px' }}
                              >
                                <option value="0">{language === 'ru' ? 'Все' : 'All'}</option>
                                <option value="1">1</option>
                                <option value="3">3</option>
                                <option value="5">5</option>
                                <option value="10">10</option>
                              </select>
                            </div>
                            <button
                              type="button"
                              onClick={() => handleSimpleImport(p.id)}
                              disabled={isImporting}
                              className="md-state-layer md-filled-button px-4 py-1.5 text-xs font-semibold flex items-center justify-center gap-1.5 disabled:opacity-50"
                              style={{ minHeight: '32px' }}
                            >
                              {isImporting ? (
                                <Loader2 size={12} className="animate-spin" />
                              ) : (
                                <Download size={12} />
                              )}
                              <span>{isImporting ? t('importing') : t('import')}</span>
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {stashPerformers.length === 0 && !isSearchingStash && stashQuery && (
                <p className="text-sm text-center text-on-surface-variant py-4">
                  {language === 'ru' ? 'Ничего не найдено в StashDB' : 'No matches found on StashDB'}
                </p>
              )}

              <div className="flex justify-end mt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddForm(false)
                    setStashQuery('')
                    setStashPerformers([])
                  }}
                  className="md-state-layer md-tonal-button px-4 py-2 font-semibold"
                >
                  {t('cancel')}
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-on-surface-variant">{t('name')} *</label>
                  <input
                    type="text"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder={t('fullName')}
                    className="md-text-field w-full px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-on-surface-variant">{t('birthYear')}</label>
                  <input
                    type="number"
                    value={newBirthYear}
                    onChange={(e) => setNewBirthYear(e.target.value)}
                    placeholder="e.g., 1980"
                    className="md-text-field w-full px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-on-surface-variant">{t('gender')}</label>
                  <select
                    value={newGender}
                    onChange={(e) => setNewGender(e.target.value)}
                    className="md-text-field w-full px-3 py-2"
                  >
                    <option value="">{t('select')}</option>
                    <option value="male">{t('male')}</option>
                    <option value="female">{t('female')}</option>
                    <option value="other">{t('other')}</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-on-surface-variant">{t('tagsComma')}</label>
                  <input
                    type="text"
                    value={newTags}
                    onChange={(e) => setNewTags(e.target.value)}
                    placeholder="e.g., actor, hollywood, drama"
                    className="md-text-field w-full px-3 py-2"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="mb-1 block text-sm font-medium text-on-surface-variant">{t('addReferencePhoto')}</label>
                  <div className="md-tonal-card border-dashed border-outline p-4">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => setNewActorImageFile(e.target.files?.[0] || null)}
                      className="block w-full text-sm text-on-surface-variant file:mr-4 file:rounded-button file:border-0 file:bg-primary-container file:px-4 file:py-2 file:text-sm file:font-semibold file:text-on-primary-container hover:file:bg-surface-container-high"
                    />
                    <p className="mt-2 text-xs text-on-surface-variant">{t('indexNotice')}</p>
                  </div>
                </div>
                <div className="md:col-span-2">
                  <label className="mb-1 block text-sm font-medium text-on-surface-variant">{t('biography')}</label>
                  <textarea
                    value={newBio}
                    onChange={(e) => setNewBio(e.target.value)}
                    rows={3}
                    placeholder={t('biography')}
                    className="md-text-field w-full resize-none px-3 py-2"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="mb-1 block text-sm font-medium text-on-surface-variant">{t('filmography')}</label>
                  <textarea
                    value={newFilmography}
                    onChange={(e) => setNewFilmography(e.target.value)}
                    rows={2}
                    placeholder={t('notableWorks')}
                    className="md-text-field w-full resize-none px-3 py-2"
                  />
                </div>
              </div>
              <div className="flex gap-3 mt-4">
                <button
                  type="button"
                  onClick={handleAddActor}
                  disabled={isAdding || !newName.trim()}
                  className="md-state-layer md-filled-button px-4 py-2 font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isAdding ? t('adding') : t('add')}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowAddForm(false)
                    resetForm()
                  }}
                  className="md-state-layer md-tonal-button px-4 py-2 font-semibold"
                >
                  {t('cancel')}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Actor Grid */}
      {actors.length === 0 ? (
        <div className="md-tonal-card py-12 text-center">
          <Users size={48} className="mx-auto mb-3 text-on-surface-variant" />
          <p className="text-on-surface-variant">
            {searchQuery || breastFilter !== 'all' || photoFilter !== 'all' || minScenesFilter !== 'all' ? t('noActorsSearch') : t('noActors')}
          </p>
          <p className="mt-1 text-sm text-on-surface-variant">
            {t('addActorHint')}
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {actors.map((actor) => (
              <ActorCard
                key={actor.id}
                actor={actor}
                onOpen={(trigger) => openActorDetails(actor, trigger)}
                onDelete={() => handleDeleteActor(actor.id)}
                isDeleting={isDeleting === actor.id}
                isLoading={isLoadingDetails === actor.id}
              />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-6">
              <button
                onClick={() => loadActors(currentPage - 1, searchQuery)}
                disabled={currentPage === 1}
                className="md-state-layer flex h-10 w-10 items-center justify-center rounded-2xl border border-outline-variant bg-surface hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Previous page"
              >
                <ChevronLeft size={18} aria-hidden="true" />
              </button>
              <span className="rounded-chip bg-surface-container px-3 py-1 text-sm font-semibold text-on-surface-variant">
                {currentPage} / {totalPages}
              </span>
              <button
                onClick={() => loadActors(currentPage + 1, searchQuery)}
                disabled={currentPage === totalPages}
                className="md-state-layer flex h-10 w-10 items-center justify-center rounded-2xl border border-outline-variant bg-surface hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Next page"
              >
                <ChevronRight size={18} aria-hidden="true" />
              </button>
            </div>
          )}
        </>
      )}

      {/* Actor Detail Modal */}
      {selectedActor && !showImageUpload && (
        <ActorDetailModal
          actor={selectedActor}
          onClose={closeActorDetails}
          onAddImage={() => setShowImageUpload(true)}
          onDelete={() => handleDeleteActor(selectedActor.id)}
          isDeleting={isDeleting === selectedActor.id}
        />
      )}

      {/* Image Upload Modal */}
      {showImageUpload && selectedActor && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-scrim p-4">
          <div className="md-card w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-title-large text-on-surface">{t('addReferencePhoto')}</h3>
              <button onClick={() => setShowImageUpload(false)} className="md-state-layer rounded-xl p-2 text-on-surface-variant hover:bg-surface-container hover:text-on-surface" aria-label={t('cancel')}>
                <X size={20} aria-hidden="true" />
              </button>
            </div>
            <div className="md-tonal-card border-2 border-dashed border-outline p-8 text-center">
              <ImageIcon size={32} className="mx-auto mb-2 text-on-surface-variant" />
              <p className="mb-4 text-sm text-on-surface-variant">
                {t('uploadClearPhoto')} {selectedActor.name}
              </p>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setImageFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-on-surface-variant file:mr-4 file:rounded-button file:border-0 file:bg-primary-container file:px-4 file:py-2 file:text-sm file:font-semibold file:text-on-primary-container hover:file:bg-surface-container-high"
              />
              <p className="mt-3 text-xs text-on-surface-variant">
                {t('indexNotice')}
              </p>
            </div>
            <div className="flex gap-3 mt-4">
              <button
                onClick={handleAddImage}
                disabled={!imageFile}
                className="md-state-layer md-filled-button flex-1 px-4 py-2 font-semibold disabled:cursor-not-allowed disabled:opacity-50"
              >
                {t('upload')}
              </button>
              <button
                onClick={() => setShowImageUpload(false)}
                className="md-state-layer md-tonal-button flex-1 px-4 py-2 font-semibold"
              >
                {t('cancel')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ActorCard({
  actor,
  onOpen,
  onDelete,
  isDeleting,
  isLoading,
}: {
  actor: Actor
  onOpen: (trigger: HTMLElement) => void
  onDelete: () => void
  isDeleting: boolean
  isLoading: boolean
}) {
  const { t } = useUiPreferences()
  const initials = actor.name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  const genderColor =
    actor.gender === 'female'
      ? 'bg-secondary-container text-on-secondary-container'
      : actor.gender === 'male'
        ? 'bg-primary-container text-on-primary-container'
        : 'bg-surface-container text-on-surface-variant'

  return (
    <div
      role="button"
      tabIndex={0}
      className="md-tonal-card group w-full p-3 text-left transition-all duration-short ease-standard hover:-translate-y-0.5 hover:shadow-lg"
      onClick={(event) => onOpen(event.currentTarget)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen(event.currentTarget)
        }
      }}
      aria-label={`${actor.name}. ${actor.reference_image_count} ${t('photos').toLowerCase()}`}
    >
      <div className="flex items-start gap-3">
        <div className={`relative h-24 w-20 flex-shrink-0 overflow-hidden rounded-2xl shadow-sm ${genderColor}`}>
          {actor.preview_image_url ? (
            <img
              src={actor.preview_image_url}
              alt={actor.name}
              className="h-full w-full object-cover"
              loading="lazy"
              data-private-media="true"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              <span className="font-bold text-lg">{initials}</span>
            </div>
          )}
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-surface/70 backdrop-blur">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" aria-hidden="true" />
            </div>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="truncate font-semibold text-on-surface">{actor.name}</h3>
          <div className="mt-1 space-y-1 text-sm text-on-surface-variant">
            {(actor.birthdate || actor.birth_year) && (
              <p className="flex items-center gap-1.5">
                <Calendar size={13} />
                {actor.birthdate ?? `${t('born')}: ${actor.birth_year}`}
              </p>
            )}
            {actor.scene_count !== null && (
              <p className="flex items-center gap-1.5">
                <Film size={13} />
                {actor.scene_count} {t('scenes').toLowerCase()}
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2 mt-2">
            <span className="rounded-chip bg-surface px-2 py-0.5 text-xs font-medium text-on-surface-variant">
                {actor.reference_image_count} {t('photos').toLowerCase()}
            </span>
            {actor.breast_type && (
              <span className="rounded-chip bg-secondary-container px-2 py-0.5 text-xs font-medium text-on-secondary-container">
                {formatBreastTypeFixed(actor.breast_type, t)}
              </span>
            )}
            {actor.tags && actor.tags.length > 0 && (
              <span className="rounded-chip bg-primary-container px-2 py-0.5 text-xs font-medium text-on-primary-container">
                {actor.tags[0]}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete() }}
          className="md-state-layer rounded-xl p-1.5 text-on-surface-variant opacity-0 transition-all hover:bg-error-container hover:text-error group-hover:opacity-100"
          disabled={isDeleting}
          aria-label={`${t('delete')}: ${actor.name}`}
        >
          {isDeleting ? (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-error border-t-transparent" />
          ) : (
            <Trash2 size={16} />
          )}
        </button>
      </div>
    </div>
  )
}

function ActorDetailModal({
  actor,
  onClose,
  onAddImage,
  onDelete,
  isDeleting,
}: {
  actor: Actor
  onClose: () => void
  onAddImage: () => void
  onDelete: () => void
  isDeleting: boolean
}) {
  const { t } = useUiPreferences()
  const [selectedImageIndex, setSelectedImageIndex] = useState(0)
  const closeButtonRef = useRef<HTMLButtonElement | null>(null)
  const sheetRef = useRef<HTMLElement | null>(null)
  const selectedImage = actor.reference_images[selectedImageIndex] ?? null
  const hasImages = actor.reference_images.length > 0
  const career = formatCareer(actor, t('active'), t('until'))
  const urls = actor.stashdb_urls?.length ? actor.stashdb_urls : extractUrls(actor.bio)
  const cleanBio = cleanBiography(actor.bio)

  useEffect(() => {
    closeButtonRef.current?.focus()

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
        return
      }

      if (event.key !== 'Tab' || !sheetRef.current) {
        return
      }

      const focusable = Array.from(
        sheetRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => element.offsetParent !== null)

      if (focusable.length === 0) {
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-[100] isolate flex justify-end bg-scrim backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <aside
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="actor-detail-title"
        className="relative z-[101] flex h-full w-full max-w-6xl flex-col overflow-hidden bg-[var(--md-sys-color-surface)] shadow-2xl lg:m-4 lg:h-[calc(100%-2rem)] lg:w-[min(1120px,calc(100vw-96px))] lg:rounded-[28px]"
      >
        <div className="md-glass flex items-center justify-between border-x-0 border-t-0 px-6 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 id="actor-detail-title" className="truncate text-2xl font-bold text-on-surface">{actor.name}</h2>
              {actor.gender && (
                <span className="rounded-chip bg-surface-container px-2.5 py-0.5 text-xs font-medium text-on-surface-variant">
                  {formatGender(actor.gender, t)}
                </span>
              )}
            </div>
            <p className="text-sm text-on-surface-variant">
              {actor.stashdb_id ? `${t('stashdbId')}: ${actor.stashdb_id}` : t('localActorRecord')}
            </p>
          </div>
          <button
            ref={closeButtonRef}
            onClick={onClose}
            className="md-state-layer rounded-2xl p-2 text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
            aria-label={t('cancel')}
          >
            <X size={24} aria-hidden="true" />
          </button>
        </div>

        <div className="grid flex-1 overflow-y-auto pr-2 lg:grid-cols-[minmax(0,1fr)_420px]">
          <div className="space-y-5 p-6">
            <div className="md-card overflow-hidden">
              <div className="flex h-[520px] items-center justify-center" data-private-media-container="true">
                {selectedImage ? (
                  <img
                    src={selectedImage.url}
                    alt={`${actor.name} reference ${selectedImageIndex + 1}`}
                    className="h-full w-full object-contain"
                    data-private-media="true"
                  />
                ) : (
                  <div className="flex flex-col items-center gap-3 text-on-surface-variant">
                    <Camera size={42} aria-hidden="true" />
                    <span>{t('noReferencePhotos')}</span>
                  </div>
                )}
              </div>
              {hasImages && (
                <div className="border-t border-outline-variant bg-surface-container-low/80 px-4 py-3 backdrop-blur">
                  <div className="mb-3 flex items-center justify-center text-sm font-semibold text-on-surface-variant">
                    <span>{selectedImageIndex + 1}/{actor.reference_images.length}</span>
                  </div>
                  <div className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                    {actor.reference_images.map((image, index) => (
                      <button
                        key={image.id}
                        type="button"
                        onClick={() => setSelectedImageIndex(index)}
                        aria-label={`${image.filename}, ${index + 1} ${t('of')} ${actor.reference_images.length}`}
                        className={`h-16 w-16 flex-shrink-0 overflow-hidden rounded-2xl border-2 ${
                          index === selectedImageIndex ? 'border-primary-500 shadow-sm' : 'border-transparent opacity-75 hover:opacity-100'
                        }`}
                        data-private-media-container="true"
                      >
                        <img
                          src={image.url}
                          alt={image.filename}
                          className="h-full w-full object-cover"
                          loading="lazy"
                          data-private-media="true"
                        />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {cleanBio && (
              <DetailSection title={t('biography')}>
                <p className="whitespace-pre-line text-sm leading-6 text-on-surface">{cleanBio}</p>
              </DetailSection>
            )}
          </div>

          <div className="border-t border-outline-variant bg-surface-container-low/80 p-6 lg:border-l lg:border-t-0">
            <div className="space-y-5">
              <InfoTable
                rows={[
                  [t('gender'), actor.gender ? formatGender(actor.gender, t) : null],
                  [t('birthdate'), actor.birthdate ?? (actor.birth_year ? String(actor.birth_year) : null)],
                  [t('career'), career],
                  [t('height'), actor.height_cm ? `${actor.height_cm} cm` : null],
                  [t('measurements'), actor.measurements],
                  [t('scenes'), actor.scene_count !== null ? String(actor.scene_count) : null],
                  [t('breastType'), actor.breast_type ? formatBreastTypeFixed(actor.breast_type, t) : null],
                  [t('country'), actor.country],
                  [t('ethnicity'), actor.ethnicity],
                  [t('eyeColor'), actor.eye_color],
                  [t('hairColor'), actor.hair_color],
                  [t('photos'), String(actor.reference_image_count)],
                  [t('tattoos'), actor.tattoos?.length ? actor.tattoos.join(', ') : null],
                  [t('piercings'), actor.piercings?.length ? actor.piercings.join(', ') : null],
                ]}
              />

              {actor.aliases && actor.aliases.length > 0 && (
                <DetailSection title={t('aliases')}>
                  <p className="text-sm leading-6 text-on-surface">{actor.aliases.join(', ')}</p>
                </DetailSection>
              )}

              {urls.length > 0 && (
                <DetailSection title={t('links')}>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {urls.map((url) => {
                      const platform = parsePlatformLink(url, t)
                      return (
                        <a
                          key={url}
                          href={platform.url}
                          target="_blank"
                          rel="noreferrer"
                          className="md-state-layer flex items-center gap-1.5 rounded-chip border border-outline-variant bg-surface px-3 py-1.5 text-xs font-semibold text-on-surface hover:bg-surface-container-high transition-colors max-w-[200px]"
                          title={url}
                        >
                          {platform.iconUrl ? (
                            <img
                              src={platform.iconUrl}
                              alt=""
                              className="w-4 h-4 object-contain flex-shrink-0"
                              onError={(e) => {
                                e.currentTarget.src = '/api/icons/no_icon.png'
                              }}
                            />
                          ) : (
                            platform.lucideIcon
                          )}
                          <span className="truncate">{platform.name}</span>
                          <ExternalLink size={10} className="text-on-surface-variant flex-shrink-0" />
                        </a>
                      )
                    })}
                  </div>
                </DetailSection>
              )}

              {actor.tags && actor.tags.length > 0 && (
                <DetailSection title={t('tags')}>
                  <div className="flex flex-wrap gap-2">
                    {actor.tags.map((tag) => (
                      <span key={tag} className="rounded-chip bg-primary-container px-3 py-1 text-sm text-primary-700">
                        {tag}
                      </span>
                    ))}
                  </div>
                </DetailSection>
              )}
            </div>

            <div className="mt-6 flex gap-3 border-t border-outline-variant pt-4">
              <button
                onClick={onAddImage}
                className="md-state-layer md-filled-button flex flex-1 items-center justify-center gap-2 px-4 py-2.5 font-semibold"
              >
                <Plus size={18} aria-hidden="true" />
                {t('addReferencePhoto')}
              </button>
              <button
                onClick={onDelete}
                disabled={isDeleting}
                className="md-state-layer md-tonal-button flex items-center justify-center gap-2 px-4 py-2.5 font-semibold text-error hover:bg-error-container disabled:opacity-50"
              >
                {isDeleting ? (
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-error border-t-transparent" />
                ) : (
                  <Trash2 size={18} aria-hidden="true" />
                )}
                {t('delete')}
              </button>
            </div>
          </div>
        </div>
      </aside>
    </div>
  )
}

function InfoTable({ rows }: { rows: Array<[string, string | null | undefined]> }) {
  const visibleRows = rows.filter(([, value]) => value)

  if (visibleRows.length === 0) return null

  return (
    <div className="overflow-hidden rounded-2xl border border-outline-variant bg-surface">
      {visibleRows.map(([label, value]) => (
        <div key={label} className="border-b border-outline-variant px-3 py-2 text-sm leading-6 last:border-b-0">
          <span className="font-semibold text-on-surface-variant">{label}: </span>
          <span className="text-on-surface">{value}</span>
        </div>
      ))}
    </div>
  )
}

function DetailSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">{title}</h4>
      <div className="rounded-2xl border border-outline-variant bg-surface p-3">{children}</div>
    </section>
  )
}

function FilterChip({
  active,
  children,
  onClick,
}: {
  active: boolean
  children: ReactNode
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      data-active={active}
      className="md-state-layer md-filter-chip px-3 py-1.5 text-sm font-semibold transition-colors duration-short ease-standard hover:bg-surface-container"
    >
      {children}
    </button>
  )
}

function actorLabels(language: 'en' | 'ru') {
  if (language === 'ru') {
    return {
      filters: 'Фильтры базы актеров',
      all: 'Все',
      withPhoto: 'С фото',
      scenes10: '10+ сцен',
      scenes50: '50+ сцен',
    }
  }

  return {
    filters: 'Actor database filters',
    all: 'All',
    withPhoto: 'Has photo',
    scenes10: '10+ scenes',
    scenes50: '50+ scenes',
  }
}

function formatCareer(actor: Actor, active: string, until: string): string | null {
  if (!actor.career_start_year && !actor.career_end_year) return null
  if (actor.career_start_year && actor.career_end_year) {
    return `${actor.career_start_year}-${actor.career_end_year}`
  }
  if (actor.career_start_year) return `${active} ${actor.career_start_year}-`
  return `${until} ${actor.career_end_year}`
}

function formatGender(value: string, t: (key: 'female' | 'male' | 'other') => string): string {
  const normalized = value.toLowerCase()
  if (normalized === 'female') return t('female')
  if (normalized === 'male') return t('male')
  return t('other')
}

function formatBreastType(value: string): string {
  if (value === 'FAKE') return 'Augmented'
  if (value === 'NATURAL') return 'Natural'
  if (value === 'NA') return 'N/A'
  return value
}

function extractUrls(text: string | null): string[] {
  if (!text) return []
  return Array.from(new Set(text.match(/https?:\/\/[^\s,]+/g) ?? []))
}

interface PlatformLink {
  url: string
  name: string
  iconUrl?: string
  lucideIcon?: ReactNode
}

function parsePlatformLink(url: string, t: (key: any) => string): PlatformLink {
  const lowercaseUrl = url.toLowerCase()
  
  if (lowercaseUrl.includes('onlyfans.com')) {
    return { url, name: 'OnlyFans', iconUrl: '/api/icons/Onlyfans.ico' }
  }
  if (lowercaseUrl.includes('fansly.com')) {
    return { url, name: 'Fansly', iconUrl: '/api/icons/fansly.png' }
  }
  if (lowercaseUrl.includes('instagram.com')) {
    return { url, name: 'Instagram', iconUrl: '/api/icons/instagram.ico' }
  }
  if (lowercaseUrl.includes('twitter.com') || lowercaseUrl.includes('x.com')) {
    return { url, name: 'Twitter/X', lucideIcon: <Twitter size={14} aria-hidden="true" /> }
  }
  if (lowercaseUrl.includes('facebook.com')) {
    return { url, name: 'Facebook', iconUrl: '/api/icons/facebook.ico' }
  }
  if (lowercaseUrl.includes('reddit.com')) {
    return { url, name: 'Reddit', iconUrl: '/api/icons/reddit.png' }
  }
  if (lowercaseUrl.includes('tiktok.com')) {
    return { url, name: 'TikTok', iconUrl: '/api/icons/tiktok.png' }
  }
  if (lowercaseUrl.includes('youtube.com') || lowercaseUrl.includes('youtu.be')) {
    return { url, name: 'YouTube', iconUrl: '/api/icons/youtube.ico' }
  }
  if (lowercaseUrl.includes('iafd.com')) {
    return { url, name: 'IAFD', iconUrl: '/api/icons/iafd.ico' }
  }
  if (lowercaseUrl.includes('indexxx.com')) {
    return { url, name: 'Indexxx', iconUrl: '/api/icons/indexxx.png' }
  }
  if (lowercaseUrl.includes('babepedia.com') || lowercaseUrl.includes('babesipedia.com')) {
    return { url, name: 'Babesipedia', iconUrl: '/api/icons/Babepedia.ico' }
  }
  if (lowercaseUrl.includes('adultfilmdatabase.com')) {
    return { url, name: 'Adult Film DB', iconUrl: '/api/icons/Adultfilmdatabase.png' }
  }
  if (lowercaseUrl.includes('boobpedia.com')) {
    return { url, name: 'Boobpedia', iconUrl: '/api/icons/Boobpedia.ico' }
  }
  if (lowercaseUrl.includes('data18.com')) {
    return { url, name: 'Data18', iconUrl: '/api/icons/data18.ico' }
  }
  if (lowercaseUrl.includes('eurobabeindex.com')) {
    return { url, name: 'EuroBabeIndex', iconUrl: '/api/icons/eurobabeindex.ico' }
  }
  if (lowercaseUrl.includes('europornstar.com')) {
    return { url, name: 'EuroPornstar', iconUrl: '/api/icons/europornstar.ico' }
  }
  if (lowercaseUrl.includes('manyvids.com')) {
    return { url, name: 'ManyVids', iconUrl: '/api/icons/manyvids.ico' }
  }
  if (lowercaseUrl.includes('pornhub.com')) {
    return { url, name: 'Pornhub', iconUrl: '/api/icons/pornhub.ico' }
  }
  if (lowercaseUrl.includes('xvideos.com')) {
    return { url, name: 'XVideos', iconUrl: '/api/icons/xvideos.ico' }
  }
  if (lowercaseUrl.includes('wikipedia.org')) {
    return { url, name: 'Wikipedia', iconUrl: '/api/icons/wikipedia.ico' }
  }
  if (lowercaseUrl.includes('wikidata.org')) {
    return { url, name: 'Wikidata', iconUrl: '/api/icons/wikidata.ico' }
  }
  if (lowercaseUrl.includes('imdb.com')) {
    return { url, name: 'IMDb', iconUrl: '/api/icons/imdb.png' }
  }
  if (lowercaseUrl.includes('theporndb.net') || lowercaseUrl.includes('theporndb.com')) {
    return { url, name: 'ThePornDB', iconUrl: '/api/icons/theporndb.png' }
  }
  if (lowercaseUrl.includes('thenude.com')) {
    return { url, name: 'TheNude', iconUrl: '/api/icons/thenude.png' }
  }
  if (lowercaseUrl.includes('themoviedb.org')) {
    return { url, name: 'TheMovieDB', iconUrl: '/api/icons/themoviedb.png' }
  }
  if (lowercaseUrl.includes('freeones.com')) {
    return { url, name: 'Freeones', iconUrl: '/api/icons/freeones.png' }
  }
  if (lowercaseUrl.includes('allmylinks.com')) {
    return { url, name: 'AllMyLinks', iconUrl: '/api/icons/Allmylinks.ico' }
  }
  if (lowercaseUrl.includes('chaturbate.com')) {
    return { url, name: 'Chaturbate', iconUrl: '/api/icons/chaturbate.ico' }
  }
  
  try {
    const domain = new URL(url).hostname.replace('www.', '')
    return { url, name: domain, iconUrl: '/api/icons/no_icon.png' }
  } catch {
    return { url, name: t('links') || 'Link', iconUrl: '/api/icons/no_icon.png' }
  }
}

function actorLabelsFixed(language: 'en' | 'ru') {
  if (language === 'ru') {
    return {
      filters: 'Фильтры базы актеров',
      all: 'Все',
      augmented: 'Увеличенная',
      natural: 'Натуральная',
      withPhoto: 'С фото',
      scenes10: '10+ сцен',
      scenes50: '50+ сцен',
    }
  }

  return {
    filters: 'Actor database filters',
    all: 'All',
    augmented: 'Augmented',
    natural: 'Natural',
    withPhoto: 'Has photo',
    scenes10: '10+ scenes',
    scenes50: '50+ scenes',
  }
}

function normalizeBreastType(value: string | null | undefined): 'FAKE' | 'NATURAL' | 'NA' | null {
  if (!value) return null
  const normalized = value.trim().toUpperCase()
  if (normalized === 'FAKE' || normalized === 'AUGMENTED') return 'FAKE'
  if (normalized === 'NATURAL') return 'NATURAL'
  if (normalized === 'NA' || normalized === 'N/A') return 'NA'
  return null
}

function formatBreastTypeFixed(value: string, t: (key: 'female' | 'male' | 'other') => string): string {
  const normalized = normalizeBreastType(value)
  const isRussian = t('female') !== 'Female'
  if (normalized === 'FAKE') return isRussian ? 'Увеличенная' : 'Augmented'
  if (normalized === 'NATURAL') return isRussian ? 'Натуральная' : 'Natural'
  if (normalized === 'NA') return 'N/A'
  return value
}

function actorMatchesActiveFilters(
  actor: Actor,
  filters: { breastType?: 'FAKE' | 'NATURAL' | 'NA'; minScenes?: number; hasPhoto?: boolean },
): boolean {
  if (filters.breastType && normalizeBreastType(actor.breast_type) !== filters.breastType) {
    return false
  }
  if (filters.minScenes !== undefined && (actor.scene_count ?? 0) < filters.minScenes) {
    return false
  }
  if (filters.hasPhoto === true && actor.reference_image_count <= 0) {
    return false
  }
  return true
}

function cleanBiography(text: string | null): string | null {
  if (!text) return null
  const cleaned = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !/^URLs?:/i.test(line) && !/^Career\s+(start|end):/i.test(line))
    .join('\n')
    .replace(/https?:\/\/[^\s,]+,?/g, '')
    .replace(/\s+,/g, ',')
    .replace(/[,\s]+$/g, '')
    .trim()
  return cleaned || null
}

void actorLabels
void formatBreastType
