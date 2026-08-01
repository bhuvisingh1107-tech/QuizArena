/** Resolve API and WebSocket base URLs for dev, Docker, and production behind nginx. */

function trimTrailingSlash(value: string): string {
  return value.replace(/\/$/, '')
}

/**
 * REST API prefix. Defaults to same-origin `/api/v1` when unset (nginx or Vite proxy).
 * Set `VITE_API_BASE_URL=http://localhost:8000/api/v1` for direct backend access in local dev.
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
 * Set `VITE_WS_BASE_URL=ws://localhost:8000/ws` for direct backend access in local dev.
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
