/**
 * Single source for SPA absolute URLs (join, display, QR, share).
 *
 * Prefer optional `VITE_PUBLIC_APP_URL` (build-time override), otherwise the
 * browser origin so production on Vercel never inherits a backend localhost
 * `PUBLIC_APP_URL`.
 */

function trimTrailingSlash(value: string): string {
  return value.replace(/\/$/, '')
}

/** Public SPA origin — never hardcode a deploy host. */
export function getAppOrigin(
  originOverride?: string,
): string {
  if (originOverride != null && originOverride.trim() !== '') {
    return trimTrailingSlash(originOverride.trim())
  }

  const fromEnv = import.meta.env.VITE_PUBLIC_APP_URL
  if (typeof fromEnv === 'string' && fromEnv.trim() !== '') {
    return trimTrailingSlash(fromEnv.trim())
  }

  if (typeof window !== 'undefined' && window.location?.origin) {
    return trimTrailingSlash(window.location.origin)
  }

  return ''
}

export function getJoinPageUrl(
  roomCode: string,
  origin?: string,
): string {
  const code = roomCode.trim()
  if (!code) {
    throw new Error('Join room code is required')
  }
  const base = getAppOrigin(origin)
  return `${base}/join/${encodeURIComponent(code)}`
}

export function getDisplayPageUrl(
  secretToken: string,
  origin?: string,
): string {
  const token = secretToken.trim()
  if (!token) {
    throw new Error('Display secret token is required')
  }
  const base = getAppOrigin(origin)
  // Hex tokens need no encoding; encodeURIComponent keeps other tokens intact.
  return `${base}/display/${encodeURIComponent(token)}`
}

/** QR codes target the participant join page. */
export function getQrJoinUrl(roomCode: string, origin?: string): string {
  return getJoinPageUrl(roomCode, origin)
}

/** Extract the presentation token from a display URL or path. */
export function extractDisplaySecretToken(displayUrlOrPath: string): string | null {
  const raw = displayUrlOrPath.trim()
  if (!raw) return null
  try {
    const url = raw.includes('://') ? new URL(raw) : new URL(raw, 'http://local.invalid')
    const parts = url.pathname.split('/').filter(Boolean)
    const idx = parts.findIndex((part) => part.toLowerCase() === 'display')
    if (idx >= 0 && parts[idx + 1]) {
      return decodeURIComponent(parts[idx + 1])
    }
  } catch {
    return null
  }
  return null
}
