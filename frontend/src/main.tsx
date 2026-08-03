import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from '@/App'
import { initAdminTheme } from '@/lib/admin-theme'
import { warnIfVercelApiMisconfigured } from '@/lib/env'
import './index.css'

initAdminTheme()
warnIfVercelApiMisconfigured()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
