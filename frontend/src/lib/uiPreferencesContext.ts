import { createContext } from 'react'

export type Language = 'en' | 'ru'
export type Theme = 'light' | 'dark'

export interface UiPreferences {
  language: Language
  theme: Theme
  privacyMode: boolean
  setLanguage: (language: Language) => void
  setTheme: (theme: Theme) => void
  setPrivacyMode: (enabled: boolean) => void
  t: (key: string) => string
}

export const UiPreferencesContext = createContext<UiPreferences | null>(null)
