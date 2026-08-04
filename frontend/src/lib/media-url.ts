import { getApiBaseUrl } from '@/lib/env'

function trimTrailingSlash(value: string): string {
  return value.replace(/\/$/, '')
}

/** Pull media id from a WS/API path like `/api/v1/media/{id}/content`. */
export function extractMediaIdFromUrl(imageUrl: string): string | null {
  const match = imageUrl.trim().match(/\/media\/([^/?#]+)\/content\/?/i)
  return match?.[1] ? decodeURIComponent(match[1]) : null
}

/**
 * Canonical live/admin media content URL.
 * Always builds `{apiBase}/media/{id}/content?token=...` — never a bare `content?token=...`.
 */
export function mediaContentUrl(mediaId: string, token: string): string {
  const apiBase = trimTrailingSlash(getApiBaseUrl())
  const id = encodeURIComponent(mediaId.trim())
  // Use URL() when apiBase is absolute so path joining cannot drop `/api/v1`.
  if (/^https?:\/\//i.test(apiBase)) {
    const url = new URL(`${apiBase}/media/${id}/content`)
    url.searchParams.set('token', token)
    return url.toString()
  }
  const params = new URLSearchParams({ token })
  return `${apiBase}/media/${id}/content?${params.toString()}`
}

/**
 * Prefer WS `mediaFileId` (rebuild canonical URL). Fall back to `imageUrl` path metadata.
 * Always attaches the auth token query param required by the media content endpoint.
 *
 * Note: Chrome DevTools Network "Name" shows the last path segment (`content?token=...`)
 * even when Request URL is the full `/api/v1/media/{id}/content?token=...`.
 */
export function resolveLiveMediaUrl(opts: {
  imageUrl?: string | null
  mediaFileId?: string | null
  token: string
}): string | null {
  const token = opts.token.trim()
  if (!token) return null

  const mediaFileId = opts.mediaFileId?.trim()
  if (mediaFileId) {
    return mediaContentUrl(mediaFileId, token)
  }

  const imageUrl = opts.imageUrl?.trim()
  if (!imageUrl) return null

  const extracted = extractMediaIdFromUrl(imageUrl)
  if (extracted) {
    return mediaContentUrl(extracted, token)
  }

  // Refuse truncated / non-media paths (e.g. bare "content") — never fetch those.
  if (!/^https?:\/\//i.test(imageUrl)) {
    return null
  }

  return attachMediaAuthToken(imageUrl, token)
}

export function attachMediaAuthToken(imageUrl: string, token: string): string {
  const extracted = extractMediaIdFromUrl(imageUrl)
  if (extracted) {
    return mediaContentUrl(extracted, token)
  }

  if (/^https?:\/\//i.test(imageUrl)) {
    const absolute = new URL(imageUrl)
    absolute.searchParams.set('token', token)
    return absolute.toString()
  }

  const apiBase = trimTrailingSlash(getApiBaseUrl())
  let path = imageUrl.startsWith('/') ? imageUrl : `/${imageUrl}`
  // Backend emits `/api/v1/media/...`; apiBase already includes `/api/v1`.
  if (path.startsWith('/api/v1/')) {
    path = path.slice('/api/v1'.length)
  }

  if (/^https?:\/\//i.test(apiBase)) {
    // new URL('/abs', base) replaces the entire path — join without a leading slash.
    const relative = path.replace(/^\//, '')
    const url = new URL(relative, `${apiBase}/`)
    url.searchParams.set('token', token)
    return url.toString()
  }

  const params = new URLSearchParams({ token })
  return `${apiBase}${path}?${params.toString()}`
}

/**
 * Warm the browser HTTP cache for a live media URL (never blocks quiz timing).
 * Safe to call fire-and-forget after a question starts.
 */
export function preloadLiveMedia(url: string | null | undefined): void {
  const href = url?.trim()
  if (!href || typeof window === 'undefined') return
  try {
    const img = new Image()
    img.decoding = 'async'
    img.src = href
  } catch {
    // Ignore preload failures — quiz must continue regardless.
  }
}
