import { describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/env', () => ({
  getApiBaseUrl: () => 'https://api.example.com/api/v1',
}))

import {
  attachMediaAuthToken,
  extractMediaIdFromUrl,
  mediaContentUrl,
  preloadLiveMedia,
  resolveLiveMediaUrl,
} from '@/lib/media-url'

describe('extractMediaIdFromUrl', () => {
  it('extracts id from WS imageUrl path', () => {
    expect(extractMediaIdFromUrl('/api/v1/media/abc-123/content')).toBe('abc-123')
  })

  it('returns null for truncated content-only paths', () => {
    expect(extractMediaIdFromUrl('content')).toBeNull()
    expect(extractMediaIdFromUrl('/content')).toBeNull()
    expect(extractMediaIdFromUrl('content?token=x')).toBeNull()
  })
})

describe('resolveLiveMediaUrl', () => {
  it('prefers mediaFileId over imageUrl and builds canonical URL', () => {
    const url = resolveLiveMediaUrl({
      imageUrl: 'content', // corrupted / truncated should be ignored
      mediaFileId: 'media-9',
      token: 'tok-2',
    })
    expect(url).toBe('https://api.example.com/api/v1/media/media-9/content?token=tok-2')
  })

  it('rebuilds from imageUrl when mediaFileId missing', () => {
    const url = resolveLiveMediaUrl({
      imageUrl: '/api/v1/media/abc/content',
      mediaFileId: null,
      token: 'tok-1',
    })
    expect(url).toBe('https://api.example.com/api/v1/media/abc/content?token=tok-1')
  })

  it('returns null for truncated imageUrl without mediaFileId', () => {
    expect(
      resolveLiveMediaUrl({
        imageUrl: 'content?token=evil',
        mediaFileId: null,
        token: 'tok-1',
      }),
    ).toBeNull()
  })

  it('returns null without token', () => {
    expect(
      resolveLiveMediaUrl({
        imageUrl: '/api/v1/media/abc/content',
        token: '  ',
      }),
    ).toBeNull()
  })
})

describe('mediaContentUrl', () => {
  it('never emits a bare content path', () => {
    const url = mediaContentUrl('uuid-1', 't')
    expect(url).toContain('/media/uuid-1/content')
    expect(url.startsWith('content')).toBe(false)
    expect(url).toMatch(/^https:\/\/api\.example\.com\/api\/v1\/media\//)
  })
})

describe('attachMediaAuthToken', () => {
  it('sets token on absolute URLs', () => {
    expect(attachMediaAuthToken('https://cdn.example.com/x.png', 'abc')).toBe(
      'https://cdn.example.com/x.png?token=abc',
    )
  })

  it('rebuilds from media path even when given full WS path', () => {
    expect(attachMediaAuthToken('/api/v1/media/xyz/content', 'tok')).toBe(
      'https://api.example.com/api/v1/media/xyz/content?token=tok',
    )
  })
})

describe('preloadLiveMedia', () => {
  it('is a no-op for empty urls and does not throw', () => {
    expect(() => preloadLiveMedia(null)).not.toThrow()
    expect(() => preloadLiveMedia('')).not.toThrow()
  })

  it('creates an Image with the given src for cache warming', () => {
    const original = globalThis.Image
    const instances: { src: string }[] = []
    class FakeImage {
      decoding = ''
      src = ''
      constructor() {
        instances.push(this)
      }
    }
    // @ts-expect-error test double
    globalThis.Image = FakeImage
    try {
      preloadLiveMedia('https://api.example.com/api/v1/media/x/content?token=t')
      expect(instances).toHaveLength(1)
      expect(instances[0].src).toBe(
        'https://api.example.com/api/v1/media/x/content?token=t',
      )
    } finally {
      globalThis.Image = original
    }
  })
})
