import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { UiPreferencesProvider } from './lib/uiPreferences'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <UiPreferencesProvider>
      <App />
    </UiPreferencesProvider>
  </React.StrictMode>,
)
