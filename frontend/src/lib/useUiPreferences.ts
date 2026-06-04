import { useContext } from 'react'
import { UiPreferencesContext } from './uiPreferencesContext'

export function useUiPreferences() {
  const context = useContext(UiPreferencesContext)
  if (!context) {
    throw new Error('useUiPreferences must be used inside UiPreferencesProvider')
  }
  return context
}
