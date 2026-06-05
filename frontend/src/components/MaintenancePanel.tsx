import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Hammer,
  HardDrive,
  Loader2,
  Play,
  RefreshCw,
  ShieldAlert,
  Square,
  Server,
  Terminal,
  Wrench,
  XCircle,
} from 'lucide-react'
import {
  cancelToolJob,
  getApiBaseUrl,
  getSystemStatus,
  getToolJobLogs,
  getToolJobs,
  startToolJob,
} from '../lib/api'
import { useUiPreferences } from '../lib/useUiPreferences'
import type { SystemCheckStatus, SystemStatus, ToolJob, ToolJobStatus, ToolJobTypeInfo } from '../types'

interface ToolTask {
  type: string
  title: string
  description: string
  defaultArgs: string[]
  allowApply: boolean
  danger?: boolean
  writesWithoutApply?: boolean
}

const TOOL_TASKS: ToolTask[] = [
  {
    type: 'repair_empty_actor_photos',
    title: 'Repair Empty Actor Photos',
    description: 'Try StashDB photo re-downloads for actors with no local reference images.',
    defaultArgs: ['--limit', '10', '--delay', '0', '--build-index-args', '--min-images 4'],
    allowApply: true,
  },
  {
    type: 'build_index',
    title: 'Build FAISS Index',
    description: 'Rebuild the face vector index from existing local actor reference photos.',
    defaultArgs: ['--min-images', '4'],
    allowApply: false,
    writesWithoutApply: true,
  },
  {
    type: 'cleanup_actors',
    title: 'Cleanup Actors',
    description: 'Preview or delete actor rows that do not match selected metadata/photo filters.',
    defaultArgs: ['--require-image', '--include-unknown'],
    allowApply: true,
    danger: true,
  },
  {
    type: 'cleanup_empty_actor_dirs',
    title: 'Cleanup Empty Actor Folders',
    description: 'Remove empty actor folders or folders that contain no images.',
    defaultArgs: ['--without-images'],
    allowApply: true,
    danger: true,
  },
  {
    type: 'cleanup_images',
    title: 'Cleanup Bad Images',
    description: 'Find reference images with missing files or no usable face.',
    defaultArgs: ['--min-face-area-ratio', '0.01', '--delete-missing'],
    allowApply: true,
    danger: true,
  },
  {
    type: 'scrape_stashdb',
    title: 'Scrape StashDB',
    description: 'Run StashDB importer through the backend job runner.',
    defaultArgs: ['--limit', '20', '--require-image', '--image-count', '3'],
    allowApply: true,
  },
]

const RUNNING_STATUSES: ToolJobStatus[] = ['queued', 'running', 'cancelling']

export function MaintenancePanel() {
  const { language } = useUiPreferences()
  const [jobs, setJobs] = useState<ToolJob[]>([])
  const [jobTypes, setJobTypes] = useState<Record<string, ToolJobTypeInfo>>({})
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [selectedLogs, setSelectedLogs] = useState('')
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isStarting, setIsStarting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [argTextByType, setArgTextByType] = useState<Record<string, string>>(() =>
    Object.fromEntries(TOOL_TASKS.map((task) => [task.type, task.defaultArgs.join('\n')])),
  )

  const labels = useMemo(() => getLabels(language), [language])
  const selectedJob = jobs.find((job) => job.id === selectedJobId) ?? null
  const hasRunningJob = jobs.some((job) => RUNNING_STATUSES.includes(job.status))

  const loadDashboard = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [data, status] = await Promise.all([getToolJobs(), getSystemStatus()])
      setJobs(data.jobs)
      setJobTypes(data.job_types)
      setSystemStatus(status)
      if (!selectedJobId && data.jobs.length > 0) {
        setSelectedJobId(data.jobs[0].id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : labels.loadFailed)
    } finally {
      setIsLoading(false)
    }
  }, [labels.loadFailed, selectedJobId])

  const loadLogs = useCallback(async (jobId: string) => {
    try {
      const logs = await getToolJobLogs(jobId, 40000)
      setSelectedLogs(logs)
    } catch (err) {
      setSelectedLogs(err instanceof Error ? err.message : labels.logFailed)
    }
  }, [labels.logFailed])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  useEffect(() => {
    if (!selectedJobId) return
    loadLogs(selectedJobId)
  }, [loadLogs, selectedJobId])

  useEffect(() => {
    const hasActive = jobs.some((job) => RUNNING_STATUSES.includes(job.status))
    if (!hasActive && !selectedJobId) return

    const interval = window.setInterval(async () => {
      const previousSelected = selectedJobId
      try {
        const [data, status] = await Promise.all([getToolJobs(), getSystemStatus()])
        setJobs(data.jobs)
        setJobTypes(data.job_types)
        setSystemStatus(status)
        if (previousSelected) {
          const selectedStillExists = data.jobs.some((job) => job.id === previousSelected)
          if (selectedStillExists) {
            const logs = await getToolJobLogs(previousSelected, 40000)
            setSelectedLogs(logs)
          }
        }
      } catch {
        // Keep existing UI state during transient backend restarts.
      }
    }, hasActive ? 1500 : 5000)

    return () => window.clearInterval(interval)
  }, [jobs, selectedJobId])

  const runTask = async (task: ToolTask, apply: boolean) => {
    if (apply) {
      const ok = window.confirm(labels.applyConfirm(task.title))
      if (!ok) return
    }

    setIsStarting(`${task.type}:${apply ? 'apply' : 'dry'}`)
    setError(null)
    try {
      const args = argsFromText(argTextByType[task.type] ?? '')
      const result = await startToolJob(task.type, { apply, args })
      setSelectedJobId(result.job.id)
      await loadDashboard()
      await loadLogs(result.job.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : labels.startFailed)
    } finally {
      setIsStarting(null)
    }
  }

  const cancelSelectedJob = async () => {
    if (!selectedJob || !RUNNING_STATUSES.includes(selectedJob.status)) return
    const ok = window.confirm(labels.cancelConfirm)
    if (!ok) return
    try {
      await cancelToolJob(selectedJob.id)
      await loadDashboard()
    } catch (err) {
      setError(err instanceof Error ? err.message : labels.cancelFailed)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-headline-large text-on-surface">{labels.title}</h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-on-surface-variant">{labels.subtitle}</p>
        </div>
        <button
          type="button"
          onClick={loadDashboard}
          disabled={isLoading}
          className="md-state-layer inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 text-sm font-extrabold text-on-primary shadow-md transition-colors hover:bg-primary-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
          {labels.refresh}
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-error/50 bg-error-container px-4 py-3 text-sm font-semibold text-on-error-container">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      <SystemDiagnostics status={systemStatus} apiBaseUrl={getApiBaseUrl()} />

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(420px,0.9fr)]">
        <div className="grid min-w-0 gap-4 lg:grid-cols-2">
          {TOOL_TASKS.map((task) => (
            <TaskCard
              key={task.type}
              task={task}
              labels={labels}
              argsText={argTextByType[task.type] ?? ''}
              jobInfo={jobTypes[task.type]}
              disabled={hasRunningJob || Boolean(isStarting)}
              isStarting={isStarting}
              onArgsChange={(value) => setArgTextByType((prev) => ({ ...prev, [task.type]: value }))}
              onRunDry={() => runTask(task, false)}
              onRunApply={() => runTask(task, true)}
            />
          ))}
        </div>

        <div className="min-w-0 space-y-4">
          <section className="md-tonal-card p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Terminal size={18} className="text-primary-700" />
                <h3 className="text-title-large text-on-surface">{labels.jobs}</h3>
              </div>
              {selectedJob && RUNNING_STATUSES.includes(selectedJob.status) && (
                <button
                  type="button"
                  onClick={cancelSelectedJob}
                  className="md-state-layer inline-flex h-9 items-center gap-2 rounded-lg border border-error/50 px-3 text-xs font-bold text-error transition-colors hover:bg-error-container"
                >
                  <Square size={13} />
                  {labels.cancel}
                </button>
              )}
            </div>

            <div className="max-h-[280px] space-y-2 overflow-y-auto pr-1">
              {jobs.length === 0 ? (
                <div className="rounded-xl border border-dashed border-outline-variant p-4 text-sm text-on-surface-variant">
                  {labels.noJobs}
                </div>
              ) : (
                jobs.slice(0, 20).map((job) => (
                  <button
                    key={job.id}
                    type="button"
                    onClick={() => setSelectedJobId(job.id)}
                    className={`md-state-layer w-full rounded-xl border p-3 text-left transition-colors ${
                      selectedJobId === job.id
                        ? 'border-primary-500 bg-primary-container/60'
                        : 'border-outline-variant bg-surface-container-low hover:bg-surface-container'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <JobStatusIcon status={job.status} />
                          <span className="truncate text-sm font-extrabold text-on-surface">{formatJobType(job.type)}</span>
                        </div>
                        <div className="mt-1 truncate text-xs text-on-surface-variant">{job.id}</div>
                      </div>
                      <span className={`rounded-full px-2 py-1 text-[10px] font-extrabold uppercase ${statusClass(job.status)}`}>
                        {job.status}
                      </span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </section>

          <section className="md-tonal-card min-h-[420px] p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2">
                <FileText size={18} className="text-primary-700" />
                <h3 className="truncate text-title-large text-on-surface">{labels.logs}</h3>
              </div>
              {selectedJob && (
                <span className="rounded-full bg-surface-container-high px-2.5 py-1 text-[10px] font-bold text-on-surface-variant">
                  {selectedJob.dry_run ? labels.dryRun : labels.applyMode}
                </span>
              )}
            </div>
            {selectedJob ? (
              <pre className="h-[360px] overflow-auto rounded-xl border border-outline-variant bg-surface-container-lowest p-3 text-xs leading-5 text-on-surface-variant">
                {selectedLogs || labels.emptyLogs}
              </pre>
            ) : (
              <div className="flex h-[360px] items-center justify-center rounded-xl border border-dashed border-outline-variant text-sm text-on-surface-variant">
                {labels.selectJob}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}

function SystemDiagnostics({
  status,
  apiBaseUrl,
}: {
  status: SystemStatus | null
  apiBaseUrl: string
}) {
  const pathEntries = status
    ? [
        ['Base', status.paths.base_dir],
        ['Models', status.paths.models_dir],
        ['Actors', status.paths.actors_dir],
        ['Videos', status.paths.videos_dir],
        ['FAISS', status.paths.faiss_index],
        ['Jobs', status.paths.jobs_dir],
      ].filter((entry): entry is [string, NonNullable<SystemStatus['paths'][string]>] => Boolean(entry[1]))
    : []

  return (
    <section className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <div className="md-tonal-card min-w-0 p-4">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl ${statusTone(status?.status ?? 'warning')}`}>
              <Server size={20} />
            </div>
            <div className="min-w-0">
              <h3 className="text-title-large text-on-surface">Service Readiness</h3>
              <p className="mt-1 truncate text-xs text-on-surface-variant">API: {apiBaseUrl}</p>
            </div>
          </div>
          <span className={`rounded-full px-2.5 py-1 text-[10px] font-extrabold uppercase ${statusPill(status?.status ?? 'warning')}`}>
            {status?.status ?? 'loading'}
          </span>
        </div>

        {status ? (
          <div className="grid gap-2 sm:grid-cols-2">
            {status.checks.map((check) => (
              <div key={check.id} className="rounded-xl border border-outline-variant bg-surface-container-lowest p-3">
                <div className="flex items-center gap-2">
                  <CheckIcon status={check.status} />
                  <span className="truncate text-sm font-extrabold text-on-surface">{check.label}</span>
                </div>
                <p className="mt-1 text-xs leading-5 text-on-surface-variant">{check.message}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex min-h-[132px] items-center justify-center rounded-xl border border-dashed border-outline-variant text-sm text-on-surface-variant">
            Loading diagnostics...
          </div>
        )}
      </div>

      <div className="md-tonal-card min-w-0 p-4">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl bg-primary-container text-primary-700">
            <HardDrive size={20} />
          </div>
          <div className="min-w-0">
            <h3 className="text-title-large text-on-surface">Runtime Paths</h3>
            <p className="mt-1 text-xs text-on-surface-variant">
              Runtime paths are loaded from config.json. Edit them in Settings.
            </p>
          </div>
        </div>

        {status ? (
          <>
            <div className="mb-3 grid gap-2 sm:grid-cols-4">
              <Metric label="Actors" value={status.counts.actors.toLocaleString()} />
              <Metric label="Images" value={status.counts.actor_images.toLocaleString()} />
              <Metric label="Vectors" value={status.counts.faiss_vectors.toLocaleString()} />
              <Metric label="Models" value={status.counts.model_files.toLocaleString()} />
            </div>
            <div className="space-y-2">
              {pathEntries.map(([label, item]) => (
                <div key={label} className="grid gap-1 rounded-xl border border-outline-variant bg-surface-container-lowest p-3 sm:grid-cols-[92px_minmax(0,1fr)_auto] sm:items-center">
                  <span className="text-xs font-extrabold uppercase tracking-wider text-on-surface-variant">{label}</span>
                  <span className="min-w-0 break-all font-mono text-xs text-on-surface">{item.path}</span>
                  <span className={`w-fit rounded-full px-2 py-1 text-[10px] font-extrabold uppercase ${item.exists ? 'bg-success-container text-on-success-container' : 'bg-error-container text-on-error-container'}`}>
                    {item.exists ? 'exists' : 'missing'}
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="flex min-h-[178px] items-center justify-center rounded-xl border border-dashed border-outline-variant text-sm text-on-surface-variant">
            Waiting for backend diagnostics...
          </div>
        )}
      </div>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-lowest px-3 py-2">
      <div className="text-[10px] font-extrabold uppercase tracking-wider text-on-surface-variant">{label}</div>
      <div className="mt-1 truncate text-sm font-extrabold text-on-surface">{value}</div>
    </div>
  )
}

function CheckIcon({ status }: { status: SystemCheckStatus }) {
  if (status === 'ok') return <CheckCircle2 size={15} className="flex-shrink-0 text-success" />
  if (status === 'error') return <XCircle size={15} className="flex-shrink-0 text-error" />
  return <AlertTriangle size={15} className="flex-shrink-0 text-warning" />
}

function statusTone(status: SystemCheckStatus): string {
  if (status === 'ok') return 'bg-success-container text-success'
  if (status === 'error') return 'bg-error-container text-error'
  return 'bg-warning-container text-warning'
}

function statusPill(status: SystemCheckStatus): string {
  if (status === 'ok') return 'bg-success-container text-on-success-container'
  if (status === 'error') return 'bg-error-container text-on-error-container'
  return 'bg-warning-container text-on-warning-container'
}

function TaskCard({
  task,
  labels,
  argsText,
  jobInfo,
  disabled,
  isStarting,
  onArgsChange,
  onRunDry,
  onRunApply,
}: {
  task: ToolTask
  labels: ReturnType<typeof getLabels>
  argsText: string
  jobInfo?: ToolJobTypeInfo
  disabled: boolean
  isStarting: string | null
  onArgsChange: (value: string) => void
  onRunDry: () => void
  onRunApply: () => void
}) {
  const Icon = task.danger ? ShieldAlert : task.writesWithoutApply ? Hammer : Wrench
  const canApply = task.allowApply && jobInfo?.supports_apply !== false
  const dryStarting = isStarting === `${task.type}:dry`
  const applyStarting = isStarting === `${task.type}:apply`

  return (
    <section className="md-tonal-card flex min-h-[310px] min-w-0 flex-col p-4">
      <div className="flex items-start gap-3">
        <div className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl ${
          task.danger ? 'bg-error-container text-error' : 'bg-primary-container text-primary-700'
        }`}>
          <Icon size={20} />
        </div>
        <div className="min-w-0">
          <h3 className="text-title-large text-on-surface">{task.title}</h3>
          <p className="mt-1 text-sm leading-5 text-on-surface-variant">{task.description}</p>
        </div>
      </div>

      <label className="mt-4 block text-[11px] font-extrabold uppercase tracking-wider text-on-surface-variant">
        {labels.args}
      </label>
      <textarea
        value={argsText}
        onChange={(event) => onArgsChange(event.target.value)}
        spellCheck={false}
        className="mt-2 min-h-[104px] w-full min-w-0 resize-y rounded-xl border border-outline-variant bg-surface-container-lowest px-3 py-2 font-mono text-xs leading-5 text-on-surface outline-none transition-colors focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
      />

      <div className="mt-auto flex min-w-0 flex-wrap gap-2 pt-4">
        <button
          type="button"
          onClick={onRunDry}
          disabled={disabled || dryStarting}
          className="md-state-layer inline-flex h-10 min-w-[120px] flex-1 items-center justify-center gap-2 rounded-xl border border-primary-500/50 px-3 text-sm font-extrabold text-primary-700 transition-colors hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-50"
        >
          {dryStarting ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
          {task.writesWithoutApply ? labels.run : labels.dryRun}
        </button>
        {canApply && (
          <button
            type="button"
            onClick={onRunApply}
            disabled={disabled || applyStarting}
            className={`md-state-layer inline-flex h-10 min-w-[120px] flex-1 items-center justify-center gap-2 rounded-xl px-3 text-sm font-extrabold shadow-md transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
              task.danger
                ? 'bg-error text-on-error hover:bg-error/90'
                : 'bg-primary-600 text-on-primary hover:bg-primary-500'
            }`}
          >
            {applyStarting ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
            {labels.apply}
          </button>
        )}
      </div>
    </section>
  )
}

function argsFromText(value: string): string[] {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

function formatJobType(type: string): string {
  return type
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function JobStatusIcon({ status }: { status: ToolJobStatus }) {
  if (status === 'completed') return <CheckCircle2 size={15} className="text-success" />
  if (status === 'failed' || status === 'cancelled') return <XCircle size={15} className="text-error" />
  if (RUNNING_STATUSES.includes(status)) return <Loader2 size={15} className="animate-spin text-primary-700" />
  return <Terminal size={15} className="text-on-surface-variant" />
}

function statusClass(status: ToolJobStatus): string {
  if (status === 'completed') return 'bg-success-container text-on-success-container'
  if (status === 'failed' || status === 'cancelled') return 'bg-error-container text-on-error-container'
  if (RUNNING_STATUSES.includes(status)) return 'bg-primary-container text-primary-700'
  return 'bg-surface-container-high text-on-surface-variant'
}

function getLabels(language: string) {
  if (language === 'ru') {
    return {
      title: 'Maintenance Center',
      subtitle: 'Безопасная оболочка для долгих задач: dry-run, apply, история jobs и live logs.',
      refresh: 'Обновить',
      jobs: 'Jobs',
      logs: 'Logs',
      args: 'Аргументы, один на строку',
      dryRun: 'Dry-run',
      apply: 'Apply',
      run: 'Run',
      applyMode: 'Apply',
      cancel: 'Cancel',
      noJobs: 'Jobs пока нет.',
      emptyLogs: 'Логи пока пустые.',
      selectJob: 'Выберите job, чтобы посмотреть logs.',
      loadFailed: 'Не удалось загрузить jobs',
      logFailed: 'Не удалось загрузить logs',
      startFailed: 'Не удалось запустить job',
      cancelFailed: 'Не удалось отменить job',
      cancelConfirm: 'Остановить выбранную job?',
      applyConfirm: (title: string) => `Запустить "${title}" в apply mode? Это может изменить файлы или базу.`,
    }
  }
  return {
    title: 'Maintenance Center',
    subtitle: 'Safe control surface for long-running jobs: dry-run, apply, job history, and live logs.',
    refresh: 'Refresh',
    jobs: 'Jobs',
    logs: 'Logs',
    args: 'Arguments, one per line',
    dryRun: 'Dry-run',
    apply: 'Apply',
    run: 'Run',
    applyMode: 'Apply',
    cancel: 'Cancel',
    noJobs: 'No jobs yet.',
    emptyLogs: 'Logs are empty.',
    selectJob: 'Select a job to inspect logs.',
    loadFailed: 'Failed to load jobs',
    logFailed: 'Failed to load logs',
    startFailed: 'Failed to start job',
    cancelFailed: 'Failed to cancel job',
    cancelConfirm: 'Cancel the selected job?',
    applyConfirm: (title: string) => `Run "${title}" in apply mode? This may change files or the database.`,
  }
}
