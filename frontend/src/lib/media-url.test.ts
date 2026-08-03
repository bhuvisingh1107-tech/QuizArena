import { describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/env', () => ({
  getApiBaseUrl: () => 'https://api.example.com/api/v1',
}))

import { attachMediaAuthToken, resolveLiveMediaUrl } from '@/lib/media-url'

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
