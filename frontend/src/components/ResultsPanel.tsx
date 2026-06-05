import { useMemo, useState, useEffect } from 'react'
import type { FaceMatch, UploadResponse, Actor } from '../types'
import { X, Clock, User, AlertCircle, ImageOff, Copy, Check, UserPlus, Loader2 } from 'lucide-react'
import { useUiPreferences } from '../lib/useUiPreferences'
import { assignFace, getActors, resolveMediaUrl } from '../lib/api'

interface ResultsPanelProps {
  results: UploadResponse[]
  onClear: () => void
}

export function ResultsPanel({ results, onClear }: ResultsPanelProps) {
  const { t } = useUiPreferences()
  if (results.length === 0) return null

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-title-large text-on-surface">{t('results')}</h2>
        <button
          onClick={onClear}
          className="md-state-layer flex items-center gap-2 rounded-button px-3 py-1.5 text-sm font-semibold text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
        >
          <X size={16} aria-hidden="true" />
          {t('clear')}
        </button>
      </div>

      <div className="grid gap-6">
        {results.map((result) => (
          <ResultCard key={result.image_id} result={result} />
        ))}
      </div>
    </div>
  )
}

function FaceThumbnail({ imageUrl, bbox, size = 60 }: { imageUrl: string; bbox: number[]; size?: number }) {
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null)
  
  const x1 = bbox[0]
  const y1 = bbox[1]
  const x2 = bbox[2]
  const y2 = bbox[3]
  
  const w = x2 - x1
  const h = y2 - y1
  
  // Add 25% padding around the face bounding box for a natural crop
  const padX = w * 0.25
  const padY = h * 0.25
  
  const px1 = Math.max(x1 - padX, 0)
  const py1 = Math.max(y1 - padY, 0)
  const px2 = dims ? Math.min(x2 + padX, dims.w) : (x2 + padX)
  
  const boxWidth = Math.max(px2 - px1, 1)
  const scale = size / boxWidth

  // Reset dims when imageUrl or bbox changes to avoid showing stale layouts
  useEffect(() => {
    setDims(null)
  }, [imageUrl, bbox.join(',')])

  return (
    <div
      className="relative overflow-hidden rounded-2xl bg-surface-container border border-outline-variant flex-shrink-0"
      style={{ width: `${size}px`, height: `${size}px` }}
    >
      <img
        src={imageUrl}
        alt="Face thumbnail"
        onLoad={(e) => {
          const img = e.currentTarget
          setDims({ w: img.naturalWidth, h: img.naturalHeight })
        }}
        style={
          dims
            ? {
                position: 'absolute',
                maxWidth: 'none',
                width: `${dims.w * scale}px`,
                height: `${dims.h * scale}px`,
                left: `${-px1 * scale}px`,
                top: `${-py1 * scale}px`,
              }
            : {
                position: 'absolute',
                opacity: 0,
              }
        }
        data-private-media="true"
      />
    </div>
  )
}

function ResultCard({ result }: { result: UploadResponse }) {
  const { language, t } = useUiPreferences()
  
  // Assign modal state
  const [assignBbox, setAssignBbox] = useState<number[] | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  
  // Group results by unique faces detected
  const faces = useMemo(() => {
    // Unique coordinates key mapping
    const faceMap: Record<string, {
      bbox: number[]
      bestMatch: FaceMatch | null
      closeMatches: FaceMatch[]
    }> = {}

    // Initialize all bboxes from the backend (ensures we show faces even on empty DB)
    if (result.all_faces) {
      result.all_faces.forEach(bbox => {
        faceMap[bbox.join(',')] = { bbox, bestMatch: null, closeMatches: [] }
      })
    }

    // Map matches to face groups
    result.matches.forEach(m => {
      const key = m.face_bbox.join(',')
      if (!faceMap[key]) {
        faceMap[key] = { bbox: m.face_bbox, bestMatch: null, closeMatches: [] }
      }
      if (!faceMap[key].bestMatch || m.confidence > faceMap[key].bestMatch!.confidence) {
        faceMap[key].bestMatch = m
      }
    })

    // Map close matches to face groups
    result.closest_matches.forEach(m => {
      const key = m.face_bbox.join(',')
      if (!faceMap[key]) {
        faceMap[key] = { bbox: m.face_bbox, bestMatch: null, closeMatches: [] }
      }
      
      const isBest = faceMap[key].bestMatch?.actor_id === m.actor_id
      const alreadyInClose = faceMap[key].closeMatches.some(c => c.actor_id === m.actor_id)
      
      if (!isBest && !alreadyInClose) {
        faceMap[key].closeMatches.push(m)
      }
    })

    return Object.values(faceMap)
  }, [result])

  const [selectedBboxKey, setSelectedBboxKey] = useState<string>(
    faces[0]?.bbox.join(',') ?? ''
  )

  const selectedFace = useMemo(() => {
    return faces.find(f => f.bbox.join(',') === selectedBboxKey) ?? faces[0] ?? null
  }, [faces, selectedBboxKey])

  // Track copy states
  const [copiedActorId, setCopiedActorId] = useState<number | null>(null)
  
  const copyActorName = async (actorId: number, actorName: string) => {
    try {
      await navigator.clipboard.writeText(actorName)
      setCopiedActorId(actorId)
      window.setTimeout(() => setCopiedActorId(null), 1200)
    } catch {
      setCopiedActorId(null)
    }
  }

  const uploadedImageUrl = resolveMediaUrl(`/api/uploads/${result.image_id}`) || `/api/uploads/${result.image_id}`

  return (
    <div className="md-card overflow-hidden">
      <div className="border-b border-outline-variant bg-surface-container-low/80 p-4 backdrop-blur">
        <div className="flex items-center justify-between">
          <span className="max-w-[200px] truncate font-medium text-on-surface">
            {result.filename}
          </span>
          <div className="flex items-center gap-3 text-sm text-on-surface-variant">
            <span className="flex items-center gap-1">
              <User size={14} aria-hidden="true" />
              {result.faces_detected} {result.faces_detected === 1 ? t('faces') : t('facesPlural')}
            </span>
            <span className="flex items-center gap-1">
              <Clock size={14} aria-hidden="true" />
              {result.processing_time_ms.toFixed(0)}ms
            </span>
          </div>
        </div>
      </div>

      {successMsg && (
        <div className="m-4 flex items-center gap-2 rounded-2xl bg-green-50 px-4 py-3 text-sm font-semibold text-green-800 border border-green-200">
          <Check size={18} />
          <span>{successMsg}</span>
        </div>
      )}

      <div className="p-4 space-y-6">
        {/* Section 1: Detected Faces List (Only show if multiple faces are detected) */}
        {faces.length > 1 && (
          <div>
            <h3 className="text-xs font-bold text-on-surface-variant uppercase tracking-wider mb-3">
              {language === 'ru' ? 'Обнаруженные Лица' : 'Detected Faces'}
            </h3>
            <div className="space-y-3">
              {faces.map((f) => {
                const key = f.bbox.join(',')
                const isSelected = selectedBboxKey === key
                const match = f.bestMatch
                
                return (
                  <div
                    key={key}
                    onClick={() => setSelectedBboxKey(key)}
                    className={`flex items-center justify-between gap-3 p-3 rounded-2xl cursor-pointer border transition-all ${
                      isSelected 
                        ? 'bg-primary-container border-primary-500 shadow-md ring-2 ring-focus' 
                        : 'bg-surface-container-low border-outline-variant hover:bg-surface-container-high'
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <FaceThumbnail imageUrl={uploadedImageUrl} bbox={f.bbox} />
                      <div className="min-w-0">
                        {match ? (
                          <div>
                            <p className="font-bold text-on-surface truncate text-sm">{match.actor_name}</p>
                            <p className="text-xs text-primary-700 font-semibold mt-0.5">
                              {Math.round(match.confidence * 100)}% {t('results').toLowerCase()}
                            </p>
                          </div>
                        ) : (
                          <div>
                            <p className="font-semibold text-on-surface-variant text-sm">
                              {language === 'ru' ? 'Неизвестное лицо' : 'Unidentified Face'}
                            </p>
                            <p className="text-xs text-error font-medium mt-0.5">
                              {t('noConfidentMatches')}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>

                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setAssignBbox(f.bbox)
                      }}
                      className="md-state-layer md-tonal-button flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold"
                      title={t('assignFace')}
                    >
                      <UserPlus size={14} />
                      <span>{language === 'ru' ? 'Привязать' : 'Link'}</span>
                    </button>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Section 2: Selected Face Details */}
        {selectedFace && (
          <div className={`space-y-5 ${faces.length > 1 ? 'pt-5 border-t border-outline-variant' : ''}`}>
            <h3 className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">
              {language === 'ru' ? 'Детали совпадения' : 'Match Details'}
            </h3>

            {/* Best Match Card */}
            {selectedFace.bestMatch ? (
              <div className="md-card p-4 bg-surface-container-lowest">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-xs font-bold text-primary-700 uppercase tracking-wider">
                    {language === 'ru' ? 'Наилучшее совпадение' : 'Best Match'}
                  </h4>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setAssignBbox(selectedFace.bbox)
                      }}
                      className="md-state-layer md-tonal-button flex items-center gap-1.5 px-3 py-1 text-xs font-semibold h-8"
                      title={t('assignFace')}
                    >
                      <UserPlus size={14} />
                      <span>{language === 'ru' ? 'Привязать' : 'Link'}</span>
                    </button>
                    <button
                      onClick={() => copyActorName(selectedFace.bestMatch!.actor_id, selectedFace.bestMatch!.actor_name)}
                      className="md-state-layer rounded-xl p-1.5 text-on-surface-variant hover:bg-surface-container flex items-center justify-center"
                    >
                      {copiedActorId === selectedFace.bestMatch.actor_id ? <Check size={14} className="text-success" /> : <Copy size={14} />}
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="h-16 w-16 overflow-hidden rounded-2xl bg-surface-container border border-outline-variant flex-shrink-0">
                    {selectedFace.bestMatch.actor_image_url ? (
                      <img src={resolveMediaUrl(selectedFace.bestMatch.actor_image_url)} alt={selectedFace.bestMatch.actor_name} className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center font-bold text-lg">{selectedFace.bestMatch.actor_name[0]}</div>
                    )}
                  </div>
                  <div>
                    <p className="font-extrabold text-on-surface text-base">{selectedFace.bestMatch.actor_name}</p>
                    <p className="text-xs text-on-surface-variant mt-1">
                      Confidence: <span className="font-semibold text-primary-700">{Math.round(selectedFace.bestMatch.confidence * 100)}%</span>
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="md-card p-4 bg-error-container/30 border border-error-container text-on-error-container">
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold">{t('noConfidentMatches')}</p>
                    <p className="text-xs text-on-surface-variant mt-1">
                      {language === 'ru' ? 'Вы можете вручную привязать это лицо.' : 'You can manually link this face.'}
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setAssignBbox(selectedFace.bbox)
                    }}
                    className="md-state-layer md-tonal-button flex items-center gap-1.5 px-3 py-2 text-xs font-semibold flex-shrink-0"
                  >
                    <UserPlus size={14} />
                    <span>{language === 'ru' ? 'Привязать' : 'Link'}</span>
                  </button>
                </div>
              </div>
            )}

            {/* Unified Comparison Panel */}
            <div className="md-card p-5 bg-surface-container-low/40 border border-outline-variant">
              <h4 className="text-xs font-bold text-on-surface-variant uppercase tracking-wider mb-4">
                {language === 'ru' ? 'Сравнение лиц' : 'Face Comparison'}
              </h4>
              
              <div className="flex items-center justify-center gap-6 sm:gap-10">
                {/* Face crop */}
                <div className="flex flex-col items-center gap-2">
                  <FaceThumbnail imageUrl={uploadedImageUrl} bbox={selectedFace.bbox} size={150} />
                  <span className="text-xs font-bold text-on-surface-variant">
                    {language === 'ru' ? 'На фото' : 'In photo'}
                  </span>
                </div>

                {/* Match indicator */}
                <div className="flex flex-col items-center justify-center px-4 py-3 rounded-2xl bg-surface-container-high border border-outline-variant min-w-[90px] shadow-sm">
                  {selectedFace.bestMatch ? (
                    <>
                      <span className="text-xl font-black text-success">
                        {Math.round(selectedFace.bestMatch.confidence * 100)}%
                      </span>
                      <span className="text-[9px] text-on-surface-variant font-bold uppercase tracking-wider mt-0.5">
                        {language === 'ru' ? 'Матч' : 'Match'}
                      </span>
                    </>
                  ) : (
                    <span className="text-xs font-bold text-error">
                      {language === 'ru' ? 'Нет' : 'No Match'}
                    </span>
                  )}
                </div>

                {/* Database image */}
                <div className="flex flex-col items-center gap-2">
                  <div className="h-[150px] w-[150px] overflow-hidden rounded-2xl bg-surface-container border border-outline-variant shadow-sm">
                    {selectedFace.bestMatch?.actor_image_url ? (
                      <img src={resolveMediaUrl(selectedFace.bestMatch.actor_image_url)} alt="db ref" className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-on-surface-variant"><ImageOff size={32} /></div>
                    )}
                  </div>
                  <span className="text-xs font-bold text-on-surface-variant">
                    {language === 'ru' ? 'В базе' : 'In database'}
                  </span>
                </div>
              </div>
            </div>

            {/* Other close candidates */}
            {selectedFace.closeMatches.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">
                  {t('otherCloseCandidates')}
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {selectedFace.closeMatches.slice(0, 3).map((match) => (
                    <div key={match.actor_id} className="flex items-center gap-2 p-2 rounded-xl bg-surface-container-lowest text-xs border border-outline-variant/30">
                      <div className="h-8 w-8 overflow-hidden rounded-lg bg-surface-container flex-shrink-0">
                        {match.actor_image_url && <img src={resolveMediaUrl(match.actor_image_url)} alt={match.actor_name} className="h-full w-full object-cover" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold text-on-surface truncate">{match.actor_name}</p>
                        <p className="text-[10px] text-on-surface-variant font-bold">{Math.round(match.confidence * 100)}%</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Face Assignment Modal */}
      {assignBbox && (
        <AssignModal
          imageId={result.image_id}
          uploadedImageUrl={uploadedImageUrl}
          bbox={assignBbox}
          onClose={() => setAssignBbox(null)}
          onSuccess={(actorName) => {
            setAssignBbox(null)
            setSuccessMsg(
              language === 'ru'
                ? `Лицо успешно привязано к актеру: ${actorName}! Обновите поиск для пересчета совпадений.`
                : `Face linked to actor ${actorName} successfully! Refresh the search to recalculate matches.`
            )
            window.setTimeout(() => setSuccessMsg(null), 6000)
          }}
        />
      )}
    </div>
  )
}

interface AssignModalProps {
  imageId: string
  uploadedImageUrl: string
  bbox: number[]
  onClose: () => void
  onSuccess: (actorName: string) => void
}

function AssignModal({ imageId, uploadedImageUrl, bbox, onClose, onSuccess }: AssignModalProps) {
  const { language, t } = useUiPreferences()
  const [mode, setMode] = useState<'existing' | 'new'>('existing')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Existing actor selection
  const [searchTerm, setSearchTerm] = useState('')
  const [actors, setActors] = useState<Actor[]>([])
  const [selectedActorId, setSelectedActorId] = useState<number | null>(null)
  const [isSearching, setIsSearching] = useState(false)

  // New actor details
  const [newName, setNewName] = useState('')
  const [newGender, setNewGender] = useState('female')
  const [newBirthYear, setNewBirthYear] = useState('')

  // Search local database for existing actors
  useEffect(() => {
    if (mode !== 'existing') return
    const delayDebounce = setTimeout(async () => {
      setIsSearching(true)
      try {
        const res = await getActors(1, 15, searchTerm)
        setActors(res.actors)
      } catch (err) {
        console.error('Failed to search actors', err)
      } finally {
        setIsSearching(false)
      }
    }, 300)

    return () => clearTimeout(delayDebounce)
  }, [searchTerm, mode])

  const handleSave = async () => {
    setIsSaving(true)
    setError(null)
    try {
      if (mode === 'existing') {
        if (!selectedActorId) {
          setError(language === 'ru' ? 'Выберите актера из списка' : 'Select an actor from the list')
          setIsSaving(false)
          return
        }
        const actor = actors.find(a => a.id === selectedActorId)
        await assignFace(imageId, {
          actorId: selectedActorId,
          faceBbox: bbox
        })
        onSuccess(actor?.name ?? 'Actor')
      } else {
        if (!newName.trim()) {
          setError(language === 'ru' ? 'Введите имя актера' : 'Enter actor name')
          setIsSaving(false)
          return
        }
        const res = await assignFace(imageId, {
          faceBbox: bbox,
          newActorName: newName.trim(),
          newActorGender: newGender,
          newActorBirthYear: newBirthYear ? parseInt(newBirthYear) : undefined
        })
        onSuccess(res.actor_name)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to assign face')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-scrim p-4 backdrop-blur-sm">
      <div className="md-card w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-title-large text-on-surface">{t('assignFace')}</h3>
          <button onClick={onClose} className="md-state-layer rounded-xl p-2 text-on-surface-variant hover:bg-surface-container" aria-label={t('cancel')}>
            <X size={20} />
          </button>
        </div>

        {error && (
          <div className="mb-4 flex items-start gap-2 rounded-2xl bg-error-container px-4 py-3 text-sm font-semibold text-on-error-container border border-error">
            <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex gap-4 mb-4">
          <div className="flex justify-center items-center bg-surface-container-low rounded-2xl p-2">
            <FaceThumbnail imageUrl={uploadedImageUrl} bbox={bbox} size={80} />
          </div>
          <div className="flex-1 text-sm text-on-surface-variant flex items-center">
            {language === 'ru' 
              ? 'Выберите существующего актера или создайте новую карточку, чтобы привязать это лицо.' 
              : 'Choose an existing actor or create a new card to link this face.'}
          </div>
        </div>

        {/* Tab Selector */}
        <div className="flex border-b border-outline-variant mb-4">
          <button
            onClick={() => setMode('existing')}
            className={`flex-1 pb-2 text-sm font-bold border-b-2 transition-all ${
              mode === 'existing' ? 'border-primary-500 text-primary-700' : 'border-transparent text-on-surface-variant'
            }`}
          >
            {t('assignToExisting')}
          </button>
          <button
            onClick={() => setMode('new')}
            className={`flex-1 pb-2 text-sm font-bold border-b-2 transition-all ${
              mode === 'new' ? 'border-primary-500 text-primary-700' : 'border-transparent text-on-surface-variant'
            }`}
          >
            {t('assignToNew')}
          </button>
        </div>

        {/* Form Container */}
        <div className="min-h-[160px] mb-6">
          {mode === 'existing' ? (
            <div className="space-y-3">
              <input
                type="text"
                placeholder={t('findExistingActor')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="md-text-field w-full px-3 py-2 text-sm"
              />
              <div className="max-h-44 overflow-y-auto border border-outline-variant rounded-xl divide-y divide-outline-variant bg-surface-container-lowest">
                {isSearching ? (
                  <div className="p-4 text-center text-xs text-on-surface-variant flex items-center justify-center gap-2">
                    <Loader2 size={14} className="animate-spin" />
                    <span>Searching...</span>
                  </div>
                ) : actors.length === 0 ? (
                  <div className="p-4 text-center text-xs text-on-surface-variant">
                    {language === 'ru' ? 'Актеры не найдены' : 'No actors found'}
                  </div>
                ) : (
                  actors.map(actor => (
                    <div
                      key={actor.id}
                      onClick={() => setSelectedActorId(actor.id)}
                      className={`flex items-center gap-3 p-2.5 cursor-pointer text-sm transition-all ${
                        selectedActorId === actor.id ? 'bg-primary-container/75 font-semibold' : 'hover:bg-surface-container'
                      }`}
                    >
                      <div className="h-8 w-8 overflow-hidden rounded-lg bg-surface-container flex-shrink-0">
                        {actor.preview_image_url && <img src={resolveMediaUrl(actor.preview_image_url)} alt="" className="h-full w-full object-cover" />}
                      </div>
                      <span className="flex-1 truncate">{actor.name}</span>
                      {actor.birth_year && <span className="text-xs text-on-surface-variant">({actor.birth_year})</span>}
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-bold text-on-surface-variant uppercase mb-1">{t('name')} *</label>
                <input
                  type="text"
                  placeholder={t('fullName')}
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="md-text-field w-full px-3 py-2 text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-on-surface-variant uppercase mb-1">{t('gender')}</label>
                  <select
                    value={newGender}
                    onChange={(e) => setNewGender(e.target.value)}
                    className="md-text-field w-full px-3 py-2 text-sm"
                  >
                    <option value="female">{t('female')}</option>
                    <option value="male">{t('male')}</option>
                    <option value="other">{t('other')}</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-on-surface-variant uppercase mb-1">{t('birthYear')}</label>
                  <input
                    type="number"
                    placeholder="e.g., 1995"
                    value={newBirthYear}
                    onChange={(e) => setNewBirthYear(e.target.value)}
                    className="md-text-field w-full px-3 py-2 text-sm"
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="flex gap-3 pt-3 border-t border-outline-variant">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="md-state-layer md-filled-button flex-1 py-2 font-semibold flex items-center justify-center gap-1.5"
          >
            {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
            <span>{t('save')}</span>
          </button>
          <button
            onClick={onClose}
            disabled={isSaving}
            className="md-state-layer md-tonal-button flex-1 py-2 font-semibold"
          >
            {t('cancel')}
          </button>
        </div>
      </div>
    </div>
  )
}
