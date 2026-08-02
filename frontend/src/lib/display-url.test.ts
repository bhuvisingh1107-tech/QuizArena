import { describe, expect, it } from 'vitest'

import { extractDisplaySecretToken, getDisplayPageUrl } from '@/lib/display-url'

describe('display-url', () => {
  it('builds a same-origin display path from the secret token', () => {
    const token = 'a'.repeat(64)
    expect(getDisplayPageUrl(token, 'https://quiz.example.com')).toBe(
      `https://quiz.example.com/display/${token}`,
    )
  })

  it('round-trips token through URL extraction', () => {
    const token = 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789'
    const url = getDisplayPageUrl(token, 'https://app.vercel.app')
    expect(extractDisplaySecretToken(url)).toBe(token)
  })

  it('extracts token from path-only strings', () => {
    expect(extractDisplaySecretToken('/display/tokensecret')).toBe('tokensecret')
  })
})
