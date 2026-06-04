import { useCallback, useRef, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  AlertCircle,
  CheckCircle2,
  Image as ImageIcon,
  Loader2,
  Trash2,
  Upload,
  XCircle,
} from 'lucide-react'
import type { FileRejection } from 'react-dropzone'
import { uploadImage } from '../lib/api'
import { useAppStore } from '../hooks/useStore'
import { useUiPreferences } from '../lib/useUiPreferences'
import type { UploadResponse } from '../types'

type QueueStatus = 'pending' | 'processing' | 'done' | 'error' | 'canceled'

interface UploadQueueItem {
  id: string
  file: File
  status: QueueStatus
  progress: number
  message?: string
}

interface UploadZoneProps {
  onResults: (results: UploadResponse[]) => void
}

export function UploadZone({ onResults }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [queue, setQueue] = useState<UploadQueueItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const cancelRequestedRef = useRef(false)
  const setUploading = useAppStore((s) => s.setUploading)
  const setUploadError = useAppStore((s) => s.setUploadError)
  const { language, t } = useUiPreferences()
  const labels = uploadLabels(language)

  const updateQueueItem = useCallback((id: string, patch: Partial<UploadQueueItem>) => {
    setQueue((items) => items.map((item) => (item.id === id ? { ...item, ...patch } : item)))
  }, [])

  const processQueue = useCallback(
    async (items: UploadQueueItem[]) => {
      const results: UploadResponse[] = []
      setIsUploading(true)
      setUploading(true)
      setError(null)
      cancelRequestedRef.current = false

      try {
        for (const item of items) {
          if (cancelRequestedRef.current) {
            updateQueueItem(item.id, { status: 'canceled', progress: 0, message: labels.canceled })
            continue
          }

          const controller = new AbortController()
          abortControllerRef.current = controller
          updateQueueItem(item.id, { status: 'processing', progress: 45, message: labels.processing })

          try {
            const response = await uploadImage(item.file, controller.signal)
            const result = { ...response, preview_url: URL.createObjectURL(item.file) }
            results.push(result)
            updateQueueItem(item.id, { status: 'done', progress: 100, message: labels.done })
          } catch (err) {
            if (controller.signal.aborted) {
              updateQueueItem(item.id, { status: 'canceled', progress: 0, message: labels.canceled })
              continue
            }

            const message = err instanceof Error ? err.message : t('uploadFailed')
            updateQueueItem(item.id, { status: 'error', progress: 100, message })
            setUploadError(message)
          } finally {
            abortControllerRef.current = null
          }
        }

        if (results.length > 0) {
          onResults(results)
        }
      } finally {
        setIsUploading(false)
        setUploading(false)
      }
    },
    [labels.canceled, labels.done, labels.processing, onResults, setUploadError, setUploading, t, updateQueueItem],
  )

  const onDrop = useCallback(
    async (acceptedFiles: File[], fileRejections: FileRejection[]) => {
      if (fileRejections.length > 0) {
        const message = t('rejectedFiles')
        setError(message)
        setQueue(
          fileRejections.map((rejection, index) => ({
            id: `${Date.now()}-rejected-${index}`,
            file: rejection.file,
            status: 'error',
            progress: 100,
            message,
          })),
        )
        return
      }

      if (acceptedFiles.length === 0) return

      const items = acceptedFiles.map((file, index) => ({
        id: `${file.name}-${file.lastModified}-${index}`,
        file,
        status: 'pending' as const,
        progress: 0,
        message: labels.pending,
      }))

      setQueue(items)
      await processQueue(items)
    },
    [labels.pending, processQueue, t],
  )

  const cancelUpload = () => {
    cancelRequestedRef.current = true
    abortControllerRef.current?.abort()
    setQueue((items) =>
      items.map((item) =>
        item.status === 'pending' || item.status === 'processing'
          ? { ...item, status: 'canceled', progress: 0, message: labels.canceled }
          : item,
      ),
    )
  }

  const removeQueueItem = (id: string) => {
    setQueue((items) => items.filter((item) => item.id !== id))
  }

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/webp': ['.webp'],
      'image/bmp': ['.bmp'],
    },
    maxFiles: 20,
    maxSize: 50 * 1024 * 1024,
    noClick: true,
    noKeyboard: true,
    onDragEnter: () => setIsDragging(true),
    onDragLeave: () => setIsDragging(false),
  })

  const queueDescriptionId = error ? 'upload-error' : 'upload-help'

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        role="button"
        tabIndex={0}
        aria-describedby={queueDescriptionId}
        onClick={open}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            open()
          }
        }}
        className={`
          md-tonal-card relative cursor-pointer border-2 border-dashed p-8 text-center
          transition-all duration-medium ease-standard md:p-10
          ${
            isDragActive || isDragging
              ? 'scale-[1.01] border-primary-500 bg-primary-container shadow-lg'
              : 'border-outline hover:border-primary-500 hover:bg-surface-container'
          }
          ${isUploading ? 'opacity-90' : ''}
        `}
      >
        <input {...getInputProps()} />

        <div className="flex flex-col items-center gap-4">
          {isUploading ? (
            <Loader2 className="h-12 w-12 animate-spin text-primary-500" aria-hidden="true" />
          ) : (
            <div
              className={`md-state-layer flex h-16 w-16 items-center justify-center rounded-[22px] shadow-sm transition-colors ${
                isDragActive ? 'bg-primary text-on-primary' : 'bg-primary-container text-on-primary-container'
              }`}
              aria-hidden="true"
            >
              <Upload size={32} />
            </div>
          )}

          <div>
            <p className="text-lg font-semibold text-on-surface">
              {isUploading ? t('processing') : isDragActive ? t('dropHere') : t('dragDrop')}
            </p>
            <p id="upload-help" className="mt-1 text-sm text-on-surface-variant">
              <span className="font-medium capitalize text-primary-700">{t('browseFiles')}</span>
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-3 text-xs text-on-surface-variant">
            <span className="flex items-center gap-1">
              <ImageIcon size={12} aria-hidden="true" />
              JPG, PNG, WebP, BMP
            </span>
            <span aria-hidden="true">&bull;</span>
            <span>{t('upToSize')}</span>
            <span aria-hidden="true">&bull;</span>
            <span>{t('maxFiles')}</span>
          </div>
        </div>

        {error && (
          <div
            id="upload-error"
            className="mt-5 flex items-center justify-center gap-2 rounded-2xl border border-error-container bg-error-container p-3 text-sm font-medium text-on-error-container"
            role="alert"
          >
            <AlertCircle size={16} aria-hidden="true" />
            {error}
          </div>
        )}
      </div>

      {queue.length > 0 && (
        <div className="md-card p-3">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-on-surface">{labels.queue}</h3>
            {isUploading && (
              <button
                type="button"
                onClick={cancelUpload}
                className="md-state-layer md-tonal-button px-3 py-1.5 text-sm font-semibold text-error hover:bg-error-container"
              >
                {labels.cancel}
              </button>
            )}
          </div>

          <div className="space-y-2" role="list" aria-label={labels.queue}>
            {queue.map((item) => (
              <QueueRow
                key={item.id}
                item={item}
                labels={labels}
                canRemove={!isUploading || item.status === 'pending' || item.status === 'error' || item.status === 'canceled'}
                onRemove={() => removeQueueItem(item.id)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function QueueRow({
  item,
  labels,
  canRemove,
  onRemove,
}: {
  item: UploadQueueItem
  labels: ReturnType<typeof uploadLabels>
  canRemove: boolean
  onRemove: () => void
}) {
  const statusIcon = {
    pending: <ImageIcon size={17} aria-hidden="true" />,
    processing: <Loader2 size={17} className="animate-spin" aria-hidden="true" />,
    done: <CheckCircle2 size={17} aria-hidden="true" />,
    error: <AlertCircle size={17} aria-hidden="true" />,
    canceled: <XCircle size={17} aria-hidden="true" />,
  }[item.status]

  const statusClass = {
    pending: 'text-on-surface-variant',
    processing: 'text-primary-700',
    done: 'text-success',
    error: 'text-error',
    canceled: 'text-on-surface-variant',
  }[item.status]
  const rowClass = {
    pending: 'md-tonal-card',
    processing: 'md-tonal-card',
    done: 'border-success-container bg-success-container text-on-success-container',
    error: 'border-error-container bg-error-container text-on-error-container',
    canceled: 'md-tonal-card opacity-80',
  }[item.status]

  return (
    <div
      className={`rounded-[24px] border p-3 ${rowClass}`}
      role="listitem"
      aria-label={`${item.file.name}: ${item.message ?? labels[item.status]}`}
    >
      <div className="grid grid-cols-[36px_minmax(0,1fr)_36px] items-center gap-3">
        <div className={`flex h-9 w-9 items-center justify-center rounded-2xl bg-surface/80 ${statusClass}`}>
          {statusIcon}
        </div>
        <div className="min-w-0 text-center">
          <div className="flex flex-col items-center justify-center gap-1 sm:grid sm:grid-cols-[minmax(0,1fr)_auto] sm:gap-3 sm:text-left">
            <p className="max-w-full truncate text-sm font-semibold">{item.file.name}</p>
            <span className={`flex-shrink-0 text-xs font-semibold ${statusClass}`}>
              {item.message ?? labels[item.status]}
            </span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-confidence-track">
            <div
              className={`h-full rounded-full transition-all duration-medium ease-standard ${
                item.status === 'error'
                  ? 'bg-confidence-low'
                  : item.status === 'done'
                    ? 'bg-confidence-high'
                    : 'bg-primary-500'
              }`}
              style={{ width: `${item.progress}%` }}
            />
          </div>
        </div>
        {canRemove ? (
          <button
            type="button"
            onClick={onRemove}
            className="md-state-layer flex h-9 w-9 items-center justify-center rounded-2xl text-on-surface-variant hover:bg-surface hover:text-error"
            aria-label={`${labels.remove}: ${item.file.name}`}
          >
            <Trash2 size={16} aria-hidden="true" />
          </button>
        ) : <div aria-hidden="true" />}
      </div>
    </div>
  )
}

function uploadLabels(language: 'en' | 'ru') {
  if (language === 'ru') {
    return {
      queue: 'Очередь загрузки',
      pending: 'Ожидает',
      processing: 'Обработка',
      done: 'Готово',
      error: 'Ошибка',
      canceled: 'Отменено',
      cancel: 'Отменить',
      remove: 'Убрать файл',
    }
  }

  return {
    queue: 'Upload queue',
    pending: 'Pending',
    processing: 'Processing',
    done: 'Done',
    error: 'Error',
    canceled: 'Canceled',
    cancel: 'Cancel',
    remove: 'Remove file',
  }
}
