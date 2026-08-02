/**
 * Display presentation links must use the SPA origin the host is on, plus the
 * exact `secretToken` from the API — never a mismatched PUBLIC_APP_URL host.
 */

export function getDisplayPageUrl(
  secretToken: string,
  origin: string = typeof window !== 'undefined' ? window.location.origin : '',
): string {
  const token = secretToken.trim()
  if (!token) {
    throw new Error('Display secret token is required')
  }
  const base = origin.replace(/\/$/, '') || ''
  // Hex tokens need no encoding; encodeURIComponent keeps url-safe tokens intact.
  return `${base}/display/${encodeURIComponent(token)}`
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
