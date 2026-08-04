import { getApiBaseUrl } from '@/lib/env'

function trimTrailingSlash(value: string): string {
  return value.replace(/\/$/, '')
}

export function mediaContentUrl(mediaId: string, token: string): string {
  const apiBase = getApiBaseUrl()
  const params = new URLSearchParams({ token })
  return `${apiBase}/media/${encodeURIComponent(mediaId)}/content?${params.toString()}`
}

/**
 * Prefer WS `imageUrl` (path/URL metadata only — never bytes). Fall back to mediaFileId.
 * Always attaches the auth token query param required by the media content endpoint.
 */
export function resolveLiveMediaUrl(opts: {
  imageUrl?: string | null
  mediaFileId?: string | null
  token: string
}): string | null {
  const token = opts.token.trim()
  if (!token) return null

  const imageUrl = opts.imageUrl?.trim()
  if (imageUrl) {
    return attachMediaAuthToken(imageUrl, token)
  }

  const mediaFileId = opts.mediaFileId?.trim()
  if (mediaFileId) {
    return mediaContentUrl(mediaFileId, token)
  }

  return null
}

export function attachMediaAuthToken(imageUrl: string, token: string): string {
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
