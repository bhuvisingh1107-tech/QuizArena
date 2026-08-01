import { getApiBaseUrl } from '@/lib/env'

export function mediaContentUrl(mediaId: string, token: string): string {
  const apiBase = getApiBaseUrl()
  const params = new URLSearchParams({ token })
  return `${apiBase}/media/${encodeURIComponent(mediaId)}/content?${params.toString()}`
}
