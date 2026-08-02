import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  extractDisplaySecretToken,
  getAppOrigin,
  getDisplayPageUrl,
  getJoinPageUrl,
  getQrJoinUrl,
} from '@/lib/app-url'

describe('app-url', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('prefers an explicit origin override', () => {
    expect(getAppOrigin('https://quiz.example.com/')).toBe('https://quiz.example.com')
  })

  it('prefers VITE_PUBLIC_APP_URL over window origin', () => {
    vi.stubEnv('VITE_PUBLIC_APP_URL', 'https://from-env.example/')
    expect(getAppOrigin()).toBe('https://from-env.example')
  })

  it('falls back to window.location.origin when env is unset', () => {
    vi.stubEnv('VITE_PUBLIC_APP_URL', '')
    expect(getAppOrigin()).toBe(window.location.origin)
  })

  it('builds join, display, and QR URLs from APP_ORIGIN', () => {
    const origin = 'https://quiz-arena.example'
    expect(getJoinPageUrl('ABC123', origin)).toBe(`${origin}/join/ABC123`)
    expect(getQrJoinUrl('ABC123', origin)).toBe(`${origin}/join/ABC123`)

    const token = 'a'.repeat(64)
    expect(getDisplayPageUrl(token, origin)).toBe(`${origin}/display/${token}`)
  })

  it('round-trips display token extraction', () => {
    const token = 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789'
    const url = getDisplayPageUrl(token, 'https://app.vercel.app')
    expect(extractDisplaySecretToken(url)).toBe(token)
  })

  it('extracts token from path-only strings', () => {
    expect(extractDisplaySecretToken('/display/tokensecret')).toBe('tokensecret')
  })
})
