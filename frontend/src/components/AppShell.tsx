import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { Activity, Camera, Database, Eye, EyeOff, Moon, Sun } from 'lucide-react'
import { useUiPreferences } from '../lib/useUiPreferences'
import type { HealthStatus } from '../types'

export type AppView = 'upload' | 'actors' | 'videos' | 'maintenance'

export interface AppNavItem {
  id: AppView
  label: string
  icon: LucideIcon
}

interface AppShellProps {
  activeView: AppView
  navItems: AppNavItem[]
  health: HealthStatus | null
  children: ReactNode
  onViewChange: (view: AppView) => void
}

export function AppShell({
  activeView,
  navItems,
  health,
  children,
  onViewChange,
}: AppShellProps) {
  const { language, theme, privacyMode, setLanguage, setTheme, setPrivacyMode, t } = useUiPreferences()

  return (
    <div className="min-h-screen text-on-surface">
      <header className="md-glass sticky top-0 z-30 border-x-0 border-t-0">
        <div className="flex h-16 items-center gap-3 px-4 lg:px-6">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl bg-primary-600 text-on-primary shadow-md">
              <Camera size={22} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-lg font-bold leading-tight text-on-surface">{t('appTitle')}</h1>
              <p className="hidden truncate text-sm text-on-surface-variant sm:block">{t('appSubtitle')}</p>
            </div>
          </div>

          <div className="hidden items-center gap-2 lg:flex">
            <HealthPills health={health} />
          </div>

          <div className="flex items-center gap-2">
            <div className="md-glass flex h-11 items-center rounded-2xl p-1 shadow-none" aria-label={t('language')}>
              <button
                type="button"
                onClick={() => setLanguage('en')}
                className={`md-state-layer h-8 rounded-lg px-3 text-xs font-semibold ${
                  language === 'en'
                    ? 'bg-primary-container text-primary-700 shadow-sm'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
                aria-pressed={language === 'en'}
              >
                EN
              </button>
              <button
                type="button"
                onClick={() => setLanguage('ru')}
                className={`md-state-layer h-8 rounded-lg px-3 text-xs font-semibold ${
                  language === 'ru'
                    ? 'bg-primary-container text-primary-700 shadow-sm'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
                aria-pressed={language === 'ru'}
              >
                RU
              </button>
            </div>
            <div className="md-glass flex h-11 w-14 items-center justify-center rounded-2xl p-1 shadow-none">
              <button
                type="button"
                onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                className="md-state-layer md-icon-button flex items-center justify-center rounded-xl text-on-surface-variant transition-colors duration-short ease-standard hover:text-on-surface"
                aria-label={theme === 'dark' ? t('light') : t('dark')}
                aria-pressed={theme === 'dark'}
              >
                {theme === 'dark' ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
              </button>
            </div>
            <button
              type="button"
              onClick={() => setPrivacyMode(!privacyMode)}
              className="md-state-layer md-glass flex h-11 min-w-[150px] items-center justify-center gap-2 rounded-2xl px-3 text-on-surface-variant shadow-none transition-colors duration-short ease-standard hover:text-on-surface"
              aria-label={privacyMode ? t('privacyModeOff') : t('privacyModeOn')}
              aria-pressed={privacyMode}
            >
              {privacyMode ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
              <span className="hidden text-sm font-semibold xl:inline">
                {privacyMode ? t('privacyModeOff') : t('privacyModeOn')}
              </span>
            </button>
          </div>
        </div>
      </header>

      <div className="flex min-h-[calc(100vh-4rem)]">
        <NavigationRail activeView={activeView} navItems={navItems} onViewChange={onViewChange} />

        <main className="flex min-h-[calc(100vh-4rem)] w-full flex-col pb-24 md:pb-0">
          <div className="border-b border-outline-variant bg-surface-container-low/80 px-4 py-3 backdrop-blur lg:hidden">
            <div className="flex gap-2 overflow-x-auto">
              <HealthPills health={health} />
            </div>
          </div>

          <div className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 lg:px-8 lg:py-8">
            {children}
          </div>

          <footer className="border-t border-outline-variant bg-surface/70 backdrop-blur">
            <div className="mx-auto flex max-w-7xl flex-col gap-1 px-4 py-4 text-sm text-on-surface-variant sm:flex-row sm:items-center sm:justify-between lg:px-8">
              <span>{t('footerVersion')}</span>
              <span>{t('footerPrivacy')}</span>
            </div>
          </footer>
        </main>
      </div>

      <BottomNavigation activeView={activeView} navItems={navItems} onViewChange={onViewChange} />
    </div>
  )
}

function HealthPills({ health }: { health: HealthStatus | null }) {
  const { language, t } = useUiPreferences()
  const modelReady = Boolean(health?.model_loaded)
  const modelLabel = modelReady ? t('modelReady') : language === 'ru' ? 'Модель не готова' : 'Model Unready'

  return (
    <>
      <StatusPill>
        <div
          className="h-2.5 w-2.5 rounded-full shadow-[0_0_0_3px_color-mix(in_srgb,currentColor_18%,transparent)]"
          style={{
            backgroundColor: modelReady ? 'var(--md-sys-color-success)' : 'var(--md-sys-color-error)',
            color: modelReady ? 'var(--md-sys-color-success)' : 'var(--md-sys-color-error)',
          }}
          aria-hidden="true"
        />
        <span>{modelLabel}</span>
      </StatusPill>
      <StatusPill>
        <Database size={14} aria-hidden="true" />
        <span>{health?.actors_count ?? 0} {t('actors')}</span>
      </StatusPill>
      <StatusPill>
        <Activity size={14} aria-hidden="true" />
        <span>{health?.index_size ?? 0} {t('vectors')}</span>
      </StatusPill>
    </>
  )
}

function StatusPill({ children }: { children: ReactNode }) {
  return (
    <div className="md-glass flex h-9 min-w-[136px] w-auto flex-shrink-0 items-center justify-center gap-1.5 rounded-full px-4 text-sm text-on-surface-variant shadow-none whitespace-nowrap">
      {children}
    </div>
  )
}

function NavigationRail({
  activeView,
  navItems,
  onViewChange,
}: {
  activeView: AppView
  navItems: AppNavItem[]
  onViewChange: (view: AppView) => void
}) {
  return (
    <aside className="md-glass sticky top-16 hidden h-[calc(100vh-4rem)] w-24 flex-shrink-0 rounded-r-[28px] border-y-0 border-l-0 px-3 py-4 md:block">
      <nav className="flex flex-col items-center gap-2" aria-label="Primary">
        {navItems.map((item) => (
          <RailButton
            key={item.id}
            active={activeView === item.id}
            item={item}
            onClick={() => onViewChange(item.id)}
          />
        ))}
      </nav>
    </aside>
  )
}

function RailButton({
  active,
  item,
  onClick,
}: {
  active: boolean
  item: AppNavItem
  onClick: () => void
}) {
  const Icon = item.icon

  return (
    <button
      type="button"
      onClick={onClick}
      className={`md-state-layer flex h-[72px] w-full flex-col items-center justify-center gap-1 rounded-2xl px-1.5 py-2 text-xs font-semibold transition-colors duration-short ease-standard ${
        active
          ? 'bg-primary-container text-primary-700 shadow-sm'
          : 'text-on-surface-variant hover:bg-surface-container/70 hover:text-on-surface'
      }`}
      aria-current={active ? 'page' : undefined}
    >
      <Icon size={22} aria-hidden="true" />
      <span className="max-w-full truncate text-center leading-tight">{item.label}</span>
    </button>
  )
}

function BottomNavigation({
  activeView,
  navItems,
  onViewChange,
}: {
  activeView: AppView
  navItems: AppNavItem[]
  onViewChange: (view: AppView) => void
}) {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 px-3 pb-3 md:hidden" aria-label="Primary">
      <div className="md-glass mx-auto grid max-w-md grid-cols-4 gap-1 rounded-[28px] p-1">
        {navItems.map((item) => {
          const Icon = item.icon
          const active = activeView === item.id

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onViewChange(item.id)}
              className={`md-state-layer flex flex-col items-center justify-center gap-0.5 rounded-[20px] px-1 py-1 text-[10px] font-bold transition-colors duration-short ease-standard ${
                active
                  ? 'bg-primary-container text-primary-700 shadow-sm'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
              aria-current={active ? 'page' : undefined}
            >
              <Icon size={16} aria-hidden="true" />
              <span className="truncate max-w-full">{item.label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
