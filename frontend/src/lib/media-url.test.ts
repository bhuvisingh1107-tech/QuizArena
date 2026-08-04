import { describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/env', () => ({
  getApiBaseUrl: () => 'https://api.example.com/api/v1',
}))

import { attachMediaAuthToken, preloadLiveMedia, resolveLiveMediaUrl } from '@/lib/media-url'

describe('resolveLiveMediaUrl', () => {
  it('prefers imageUrl and attaches token', () => {
    const url = resolveLiveMediaUrl({
      imageUrl: '/api/v1/media/abc/content',
      mediaFileId: 'ignored',
      token: 'tok-1',
    })
    expect(url).toBe('https://api.example.com/api/v1/media/abc/content?token=tok-1')
  })

  it('falls back to mediaFileId when imageUrl missing', () => {
    const url = resolveLiveMediaUrl({
      imageUrl: null,
      mediaFileId: 'media-9',
      token: 'tok-2',
    })
    expect(url).toBe('https://api.example.com/api/v1/media/media-9/content?token=tok-2')
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

describe('attachMediaAuthToken', () => {
  it('sets token on absolute URLs', () => {
    expect(attachMediaAuthToken('https://cdn.example.com/x.png', 'abc')).toBe(
      'https://cdn.example.com/x.png?token=abc',
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
