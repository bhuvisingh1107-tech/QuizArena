/** Resolve API and WebSocket base URLs for dev, Docker, and production behind nginx. */

function trimTrailingSlash(value: string): string {
  return value.replace(/\/$/, '')
}

/**
 * REST API prefix. Defaults to same-origin `/api/v1` when unset (nginx or Vite proxy).
 * Local direct: `VITE_API_BASE_URL=http://localhost:8000/api/v1`
 * Vercel → Render: `VITE_API_BASE_URL=https://<render-host>/api/v1` (build-time)
 */
export function getApiBaseUrl(): string {
  const env = import.meta.env.VITE_API_BASE_URL
  if (env && env.trim() !== '') {
    return trimTrailingSlash(env)
  }
  return '/api/v1'
}

/**
 * WebSocket endpoint. Defaults to same-origin `/ws` when unset.
 * Local direct: `VITE_WS_BASE_URL=ws://localhost:8000/ws`
 * Vercel → Render: `VITE_WS_BASE_URL=wss://<render-host>/ws` (build-time, must be wss)
 */
export function getWsBaseUrl(): string {
  const env = import.meta.env.VITE_WS_BASE_URL
  if (env && env.trim() !== '') {
    return trimTrailingSlash(env)
  }
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${protocol}://${window.location.host}/ws`
  }
  return 'ws://localhost:8000/ws'
}
