import { afterEach, describe, expect, it, vi } from 'vitest'

import { getApiBaseUrl, getWsBaseUrl } from '@/lib/env'

describe('env URL helpers', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('uses VITE_WS_BASE_URL when set', () => {
    vi.stubEnv('VITE_WS_BASE_URL', 'wss://api.example.com/ws/')
    expect(getWsBaseUrl()).toBe('wss://api.example.com/ws')
  })

  it('defaults to backend port 8000, never the Vite origin', () => {
    vi.stubEnv('VITE_WS_BASE_URL', '')
    // Even if window looks like the Vite dev server, we must not dial :5173.
    expect(getWsBaseUrl()).toBe('ws://localhost:8000/ws')
    expect(getWsBaseUrl()).not.toContain(':5173')
  })

  it('uses VITE_API_BASE_URL when set', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com/api/v1/')
    expect(getApiBaseUrl()).toBe('https://api.example.com/api/v1')
  })
})
