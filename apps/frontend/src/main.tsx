import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const blockRefreshKeys = (event: KeyboardEvent) => {
  const key = event.key.toLowerCase()
  const isReloadKey = event.key === 'F5' || (key === 'r' && (event.ctrlKey || event.metaKey))
  if (!isReloadKey) return
  event.preventDefault()
  event.stopPropagation()
}

window.addEventListener('keydown', blockRefreshKeys, { capture: true })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
