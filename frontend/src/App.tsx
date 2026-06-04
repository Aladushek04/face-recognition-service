import { useState, useEffect } from 'react'
import { Upload, Users, Camera, Film } from 'lucide-react'
import { AppShell } from './components/AppShell'
import { UploadZone } from './components/UploadZone'
import { ResultsPanel } from './components/ResultsPanel'
import { ActorsPanel } from './components/ActorsPanel'
import { VideosPanel } from './components/VideosPanel'
import { useAppStore } from './hooks/useStore'
import { getHealth } from './lib/api'
import { useUiPreferences } from './lib/uiPreferences'
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
    getHealth().then(setHealth).catch(() => setHealth(null))
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
      )}

      {activeView === 'actors' && (
        <section className="md-card p-5 lg:p-6">
          <ActorsPanel onAddActor={() => {}} />
        </section>
      )}

      {activeView === 'videos' && (
        <section className="md-card p-5 lg:p-6">
          <VideosPanel />
        </section>
      )}
    </AppShell>
  )
}

export default App
