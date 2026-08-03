/** Resolve API and WebSocket base URLs for dev, Docker, and production behind nginx. */

function trimTrailingSlash(value: string): string {
  return value.replace(/\/$/, '')
}

/**
 * REST API prefix. Defaults to same-origin `/api/v1` when unset (nginx or Vite proxy).
 * Local direct: `VITE_API_BASE_URL=http://localhost:8000/api/v1`
 * Vercel → Render: `VITE_API_BASE_URL=https://<render-host>/api/v1` (build-time)
 *
 * Must be set for **Production and Preview** on Vercel — relative `/api/v1` has no
 * API proxy on Vercel and causes browser "Network Error" on login/signup.
 */
export function getApiBaseUrl(): string {
  const env = import.meta.env.VITE_API_BASE_URL
  if (env && env.trim() !== '') {
    return trimTrailingSlash(env)
  }
  return '/api/v1'
}

/** True when the API base is an absolute http(s) URL suitable for cross-origin Vercel. */
export function isAbsoluteHttpApiBase(url: string = getApiBaseUrl()): boolean {
  return /^https?:\/\//i.test(url)
}

/**
 * Log a clear misconfiguration when a Vercel host would call a relative API path
 * (no backend on that host → Network Error on auth).
 */
export function warnIfVercelApiMisconfigured(): void {
  if (typeof window === 'undefined') return
  const host = window.location.hostname
  if (!host.endsWith('.vercel.app')) return
  if (isAbsoluteHttpApiBase()) return
  console.error(
    '[QuizArena] VITE_API_BASE_URL is missing or relative on a Vercel deployment. ' +
      'Set Production AND Preview env vars to https://<your-render-host>/api/v1 ' +
      '(and VITE_WS_BASE_URL to wss://<your-render-host>/ws), then redeploy.',
  )
}

/**
 * WebSocket endpoint.
 *
 * Always prefer `VITE_WS_BASE_URL`. Never fall back to `window.location.host` —
 * that produces `ws://localhost:5173/ws` under Vite and is not the API.
 *
 * Local: `VITE_WS_BASE_URL=ws://localhost:8000/ws`
 * Production: `VITE_WS_BASE_URL=wss://<render-host>/ws`
 */
export function getWsBaseUrl(): string {
  const env = import.meta.env.VITE_WS_BASE_URL
  if (env && env.trim() !== '') {
    return trimTrailingSlash(env)
  }
  // Dev default when env is unset: backend port, never the Vite origin.
  return 'ws://localhost:8000/ws'
}
