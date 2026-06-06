import { useState, useEffect } from 'react'
import { Save, RefreshCw, CheckCircle, AlertTriangle, XCircle, RotateCcw, FolderSearch, Power } from 'lucide-react'
import { useUiPreferences } from '../lib/useUiPreferences'
import { getDesktopConfig, validateDesktopConfig, saveDesktopConfig } from '../lib/api'
import type { DesktopConfig, ValidationResponse } from '../lib/api'

const DEFAULT_CONFIG: DesktopConfig = {
  schemaVersion: 1,
  runtime: {
    baseDir: "D:\\FaceService",
    actorsDir: "D:\\FaceService\\actors",
    modelsDir: "D:\\FaceService\\models",
    faissIndexDir: "D:\\FaceService\\data\\faiss_index",
    videosDir: "D:\\Videos",
    jobsDir: "",
    logsDir: ""
  },
  backend: {
    host: "127.0.0.1",
    port: 0,
    desktopMode: true,
    corsOrigins: [
      "https://app.face.local",
      "http://127.0.0.1:3000",
      "http://localhost:3000"
    ]
  },
  ai: {
    faceExecutionProviders: [
      "CUDAExecutionProvider",
      "CPUExecutionProvider"
    ],
    faceModelName: "buffalo_l"
  }
}

export function SettingsPanel() {
  const { language } = useUiPreferences()
  const [config, setConfig] = useState<DesktopConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [validation, setValidation] = useState<ValidationResponse | null>(null)
  const [restartRequired, setRestartRequired] = useState(false)

  useEffect(() => {
    loadConfig()

    const webview = (window as any).chrome?.webview
    if (!webview) return

    const handleMessage = (event: any) => {
      const data = event.data
      if (data && data.action === 'selectFolderResult' && !data.cancelled && data.path) {
        setConfig((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            runtime: {
              ...prev.runtime,
              [data.field]: data.path
            }
          }
        })
        setValidation(null)
      }
    }

    webview.addEventListener('message', handleMessage)
    return () => webview.removeEventListener('message', handleMessage)
  }, [])

  const loadConfig = async () => {
    try {
      setLoading(true)
      const data = await getDesktopConfig()
      setConfig(data)
      setValidation(null)
    } catch (err) {
      console.error('Failed to load config', err)
    } finally {
      setLoading(false)
    }
  }

  const handleValidate = async () => {
    if (!config) return
    try {
      const res = await validateDesktopConfig(config)
      setValidation(res)
    } catch (err) {
      setValidation({ status: 'error', errors: [String(err)], warnings: [], restartRequired: false })
    }
  }

  const handleSave = async () => {
    if (!config) return
    try {
      setSaving(true)
      const res = await saveDesktopConfig(config)
      setValidation(res)
      if (res.status !== 'error') {
        setRestartRequired(res.restartRequired)
      }
    } catch (err) {
      setValidation({ status: 'error', errors: [String(err)], warnings: [], restartRequired: false })
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    if (confirm(language === 'ru' ? 'РЎР±СЂРѕСЃРёС‚СЊ РЅР°СЃС‚СЂРѕР№РєРё РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ?' : 'Reset settings to defaults?')) {
      setConfig(JSON.parse(JSON.stringify(DEFAULT_CONFIG)))
      setValidation(null)
    }
  }

  const updateRuntime = (key: keyof DesktopConfig['runtime'], value: string) => {
    if (!config) return
    setConfig({ ...config, runtime: { ...config.runtime, [key]: value } })
    setValidation(null)
  }

  const handleBrowse = (field: keyof DesktopConfig['runtime']) => {
    const webview = (window as any).chrome?.webview
    const currentPath = config?.runtime[field] || ''
    console.log("[Settings] Browse clicked", field, currentPath)
    console.log("[Settings] WebView bridge available", !!webview)
    if (webview && config) {
      webview.postMessage({
        action: 'selectFolder',
        requestId: Date.now().toString(),
        field,
        currentPath
      })
    }
  }

  const handleCloseApp = () => {
    const webview = (window as any).chrome?.webview
    if (webview) {
      webview.postMessage({ action: 'closeApp' })
    }
  }

  const isDesktopApp = !!(window as any).chrome?.webview

  if (loading || !config) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="animate-spin text-outline" size={32} />
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-headline-medium text-on-surface">
          {language === 'ru' ? 'РќР°СЃС‚СЂРѕР№РєРё СЃСЂРµРґС‹' : 'Runtime Configuration'}
        </h2>
        <div className="flex gap-3">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 rounded-full border border-outline px-4 py-2 text-sm font-medium text-on-surface hover:bg-surface-variant transition-colors"
          >
            <RotateCcw size={16} />
            {language === 'ru' ? 'РЎР±СЂРѕСЃРёС‚СЊ' : 'Reset'}
          </button>
          <button
            onClick={handleValidate}
            className="flex items-center gap-2 rounded-full border border-outline px-4 py-2 text-sm font-medium text-on-surface hover:bg-surface-variant transition-colors"
          >
            <RefreshCw size={16} />
            {language === 'ru' ? 'РџСЂРѕРІРµСЂРёС‚СЊ' : 'Validate'}
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            <Save size={16} />
            {saving ? (language === 'ru' ? 'РЎРѕС…СЂР°РЅРµРЅРёРµ...' : 'Saving...') : (language === 'ru' ? 'РЎРѕС…СЂР°РЅРёС‚СЊ' : 'Save')}
          </button>
        </div>
      </div>

      {restartRequired && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-2xl bg-primary/20 p-4 text-on-surface border border-primary/30">
          <div className="flex items-start gap-3">
            <AlertTriangle className="text-primary mt-0.5 shrink-0" size={20} />
            <div>
              <h4 className="font-medium">
                {language === 'ru' ? 'РўСЂРµР±СѓРµС‚СЃСЏ РїРµСЂРµР·Р°РїСѓСЃРє' : 'Restart Required'}
              </h4>
              <p className="text-sm mt-1 opacity-90">
                {language === 'ru' 
                  ? 'РљРѕРЅС„РёРіСѓСЂР°С†РёСЏ СЃРѕС…СЂР°РЅРµРЅР°. РџРѕР¶Р°Р»СѓР№СЃС‚Р°, Р·Р°РєСЂРѕР№С‚Рµ Рё СЃРЅРѕРІР° РѕС‚РєСЂРѕР№С‚Рµ РїСЂРёР»РѕР¶РµРЅРёРµ РґР»СЏ РїСЂРёРјРµРЅРµРЅРёСЏ РёР·РјРµРЅРµРЅРёР№.' 
                  : 'Configuration saved. Please close and reopen the application to apply changes.'}
              </p>
            </div>
          </div>
          {isDesktopApp && (
            <button
              onClick={handleCloseApp}
              className="flex items-center gap-2 rounded-xl bg-error px-4 py-2 text-sm font-medium text-on-error hover:bg-error/90 transition-colors whitespace-nowrap"
            >
              <Power size={16} />
              {language === 'ru' ? 'Р—Р°РєСЂС‹С‚СЊ РїСЂРёР»РѕР¶РµРЅРёРµ' : 'Close App'}
            </button>
          )}
        </div>
      )}

      {validation && (
        <div className={`flex flex-col gap-2 rounded-2xl p-4 border ${
          validation.status === 'error' ? 'bg-error/10 border-error/20 text-error' :
          validation.status === 'warning' ? 'bg-orange-500/10 border-orange-500/20 text-orange-400' :
          'bg-green-500/10 border-green-500/20 text-green-400'
        }`}>
          <div className="flex items-center gap-2 font-medium">
            {validation.status === 'error' && <XCircle size={18} />}
            {validation.status === 'warning' && <AlertTriangle size={18} />}
            {validation.status === 'ok' && <CheckCircle size={18} />}
            <span>
              {validation.status === 'error' ? 'Validation Failed' :
               validation.status === 'warning' ? 'Validation Warnings' : 'Validation Successful'}
            </span>
          </div>
          {validation.errors.length > 0 && (
            <ul className="list-disc pl-6 text-sm">
              {validation.errors.map((err, i) => <li key={i}>{err}</li>)}
            </ul>
          )}
          {validation.warnings.length > 0 && (
            <ul className="list-disc pl-6 text-sm opacity-90">
              {validation.warnings.map((warn, i) => <li key={i}>{warn}</li>)}
            </ul>
          )}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <h3 className="text-title-medium font-medium text-on-surface">Runtime Paths</h3>
          
          {config.backend.desktopMode && !isDesktopApp && (
            <div className="rounded-xl bg-surface-variant/50 border border-outline p-3 text-sm text-on-surface-variant flex items-center gap-2">
              <AlertTriangle size={16} className="text-orange-400" />
              Native folder picker is unavailable. You can edit the path manually.
            </div>
          )}

          {[
            { key: 'baseDir', label: 'Base Directory' },
            { key: 'actorsDir', label: 'Actors Directory' },
            { key: 'modelsDir', label: 'Models Directory' },
            { key: 'faissIndexDir', label: 'FAISS Index Directory' },
            { key: 'videosDir', label: 'Videos Directory' },
          ].map((field) => (
            <div key={field.key} className="space-y-1.5">
              <label className="text-sm font-medium text-on-surface-variant">{field.label}</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={config.runtime[field.key as keyof DesktopConfig['runtime']]}
                  onChange={(e) => updateRuntime(field.key as keyof DesktopConfig['runtime'], e.target.value)}
                  className="flex-1 min-w-0 rounded-xl border border-outline bg-surface-variant/50 px-4 py-2.5 text-sm text-on-surface focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <button
                  onClick={() => handleBrowse(field.key as keyof DesktopConfig['runtime'])}
                  disabled={!isDesktopApp}
                  title={isDesktopApp ? 'Browse' : 'Available in desktop app only'}
                  className="flex-shrink-0 flex items-center justify-center rounded-xl bg-surface-variant/50 border border-outline px-4 text-on-surface hover:bg-surface-variant hover:text-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <FolderSearch size={18} />
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="space-y-6">
          <div className="space-y-4">
            <h3 className="text-title-medium font-medium text-on-surface">AI Settings</h3>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-on-surface-variant">Face Model Name</label>
              <input
                type="text"
                value={config.ai.faceModelName}
                onChange={(e) => {
                  setConfig({ ...config, ai: { ...config.ai, faceModelName: e.target.value } })
                  setValidation(null)
                }}
                className="w-full rounded-xl border border-outline bg-surface-variant/50 px-4 py-2.5 text-sm text-on-surface focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-on-surface-variant">Execution Providers</label>
              <div className="flex flex-col gap-2 rounded-xl border border-outline bg-surface-variant/30 p-3">
                {['CUDAExecutionProvider', 'CPUExecutionProvider'].map(provider => (
                  <label key={provider} className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={config.ai.faceExecutionProviders.includes(provider)}
                      onChange={(e) => {
                        let providers = [...config.ai.faceExecutionProviders]
                        if (e.target.checked && !providers.includes(provider)) {
                          providers.push(provider)
                        } else if (!e.target.checked) {
                          providers = providers.filter(p => p !== provider)
                        }
                        setConfig({ ...config, ai: { ...config.ai, faceExecutionProviders: providers } })
                        setValidation(null)
                      }}
                      className="h-4 w-4 rounded border-outline bg-surface text-primary focus:ring-primary focus:ring-offset-surface"
                    />
                    <span className="text-sm text-on-surface">{provider}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-title-medium font-medium text-on-surface flex items-center gap-2">
              Advanced <span className="text-xs bg-surface-variant px-2 py-0.5 rounded text-on-surface-variant">Read-only</span>
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-on-surface-variant">Host</label>
                <input
                  type="text"
                  disabled
                  value={config.backend.host}
                  className="w-full rounded-xl border border-outline/50 bg-surface-variant/20 px-4 py-2.5 text-sm text-on-surface/50 cursor-not-allowed"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-on-surface-variant">Port</label>
                <input
                  type="number"
                  disabled
                  value={config.backend.port}
                  className="w-full rounded-xl border border-outline/50 bg-surface-variant/20 px-4 py-2.5 text-sm text-on-surface/50 cursor-not-allowed"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-on-surface-variant">Desktop Mode</label>
              <input
                type="text"
                disabled
                value={config.backend.desktopMode ? 'Enabled' : 'Disabled'}
                className="w-full rounded-xl border border-outline/50 bg-surface-variant/20 px-4 py-2.5 text-sm text-on-surface/50 cursor-not-allowed"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-on-surface-variant">CORS Origins</label>
              <textarea
                disabled
                value={config.backend.corsOrigins.join('\n')}
                rows={3}
                className="w-full rounded-xl border border-outline/50 bg-surface-variant/20 px-4 py-2.5 text-sm text-on-surface/50 cursor-not-allowed resize-none"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
