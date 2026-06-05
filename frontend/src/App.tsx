import { useState, useEffect } from 'react'
import { Upload, Users, Camera, Film, Wrench, Settings } from 'lucide-react'
import { AppShell } from './components/AppShell'
import { UploadZone } from './components/UploadZone'
import { ResultsPanel } from './components/ResultsPanel'
import { ActorsPanel } from './components/ActorsPanel'
import { VideosPanel } from './components/VideosPanel'
import { MaintenancePanel } from './components/MaintenancePanel'
import { SettingsPanel } from './components/SettingsPanel'
import { useAppStore } from './hooks/useStore'
import { getHealth } from './lib/api'
import { useUiPreferences } from './lib/useUiPreferences'
import type { HealthStatus, UploadResponse } from './types'
import type { AppView } from './components/AppShell'

function App() {
  const [activeView, setActiveView] = useState<AppView>('upload')
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const { language, t } = useUiPreferences()

  const uploadResults = useAppStore((s) => s.uploadResults)
  const setUploadResults = useAppStore((s) => s.setUploadResults)
  const clearResults = useAppStore((s) => s.clearResults)

  useEffect(() => {
    let timeoutId: number
    let isSubscribed = true

    const fetchHealth = async () => {
      try {
        const result = await getHealth()
        if (isSubscribed) setHealth(result)

        if (!isSubscribed) return

        const isReady = result.model_loaded && result.actors_count > 0 && result.index_size > 0
        const delay = isReady ? 30000 : 3000
        timeoutId = window.setTimeout(fetchHealth, delay)
      } catch (err) {
        if (isSubscribed) {
          setHealth((prev) => prev)
          timeoutId = window.setTimeout(fetchHealth, 3000)
        }
      }
    }

    fetchHealth()

    return () => {
      isSubscribed = false
      if (timeoutId) window.clearTimeout(timeoutId)
    }
  }, [])

  const handleResults = (results: UploadResponse[]) => {
    uploadResults.forEach((result) => {
      if (result.preview_url) URL.revokeObjectURL(result.preview_url)
    })
    setUploadResults(results)
  }

  const handleClearResults = () => {
    uploadResults.forEach((result) => {
      if (result.preview_url) URL.revokeObjectURL(result.preview_url)
    })
    clearResults()
  }

  const navItems = [
    { id: 'upload' as const, label: language === 'ru' ? 'Поиск' : 'Upload', icon: Upload },
    { id: 'actors' as const, label: language === 'ru' ? 'База' : 'Actors', icon: Users },
    { id: 'videos' as const, label: language === 'ru' ? 'Видео' : 'Videos', icon: Film },
    { id: 'maintenance' as const, label: language === 'ru' ? 'Сервис' : 'Tools', icon: Wrench },
    { id: 'settings' as const, label: language === 'ru' ? 'Настройки' : 'Settings', icon: Settings },
  ]

  return (
    <AppShell
      activeView={activeView}
      health={health}
      navItems={navItems}
      onViewChange={setActiveView}
    >
      {activeView === 'upload' && (
        <section className="mx-auto grid w-full max-w-[1240px] gap-6 xl:min-h-[calc(100vh-11.5rem)] xl:grid-cols-2 xl:items-center">
          <div className="md-card flex min-h-[420px] flex-col p-5 lg:min-h-[470px] lg:p-6">
            <div className="mb-5">
              <h2 className="text-headline-large text-on-surface">{t('uploadTitle')}</h2>
              <p className="mt-2 max-w-2xl text-body-large text-on-surface-variant">
                {t('uploadSubtitle')}
              </p>
            </div>
            <div className="flex flex-1 flex-col justify-center">
              <UploadZone onResults={handleResults} />
            </div>
          </div>

          <div className="md-card flex min-h-[420px] flex-col p-5 lg:min-h-[470px] lg:p-6">
            <ResultsPanel results={uploadResults} onClear={handleClearResults} />
            {uploadResults.length === 0 && (
              <div className="md-tonal-card flex flex-1 min-h-[320px] flex-col items-center justify-center border-dashed px-6 text-center">
                <Camera size={34} className="mb-3 text-outline" aria-hidden="true" />
                <h3 className="text-title-large text-on-surface">{t('results')}</h3>
                <p className="mt-1 max-w-sm text-sm leading-6 text-on-surface-variant">{t('uploadSubtitle')}</p>
              </div>
            )}
          </div>
        </section>
      )}      {activeView === 'actors' && (
        (!health || health.status === 'config_required') ? (
          <ConfigRequiredMessage />
        ) : (
          <section className="md-card p-5 lg:p-6">
            <ActorsPanel onAddActor={() => {}} />
          </section>
        )
      )}      {activeView === 'videos' && (
        (!health || health.status === 'config_required') ? (
          <ConfigRequiredMessage />
        ) : (
          <section className="md-card p-5 lg:p-6">
            <VideosPanel />
          </section>
        )
      )}
      {activeView === 'maintenance' && (
        <section className="md-card p-5 lg:p-6">
          <MaintenancePanel />
        </section>
      )}
      {activeView === 'settings' && (
        <section className="md-card p-5 lg:p-6">
          <SettingsPanel />
        </section>
      )}
    </AppShell>
  )
}

function ConfigRequiredMessage() {
  const { language } = useUiPreferences()
  return (
    <div className="md-card flex min-h-[400px] flex-col items-center justify-center p-8 text-center">
      <div className="mb-4 rounded-full bg-error-container p-4 text-on-error-container">
        <Wrench size={48} />
      </div>
      <h2 className="text-headline-medium text-on-surface mb-2">
        {language === 'ru' ? 'Требуется настройка' : 'Configuration Required'}
      </h2>
      <p className="text-body-large text-on-surface-variant max-w-md">
        {language === 'ru' ? 'Данные среды выполнения не настроены. Откройте «Настройки» и укажите пути FaceService.' : 'Runtime data is not configured. Open Settings and set your FaceService paths.'}
      </p>
    </div>
  )
}

export default App


