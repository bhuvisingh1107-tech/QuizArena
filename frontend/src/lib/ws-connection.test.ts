import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  acquireWebSocket,
  makeWsKey,
  resetWebSocketPool,
  webSocketPoolSize,
} from '@/lib/ws-connection'

class FakeWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  readyState = FakeWebSocket.CONNECTING
  url: string
  onopen: ((ev?: Event) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null
  onclose: ((ev: CloseEvent) => void) | null = null

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
    queueMicrotask(() => {
      if (this.readyState === FakeWebSocket.CONNECTING) {
        this.readyState = FakeWebSocket.OPEN
        this.onopen?.(new Event('open'))
      }
    })
  }

  send = vi.fn()

  close() {
    if (this.readyState === FakeWebSocket.CLOSED) return
    this.readyState = FakeWebSocket.CLOSED
    this.onclose?.(new CloseEvent('close', { code: 1000, reason: 'test' }))
  }

  static instances: FakeWebSocket[] = []
  static reset() {
    FakeWebSocket.instances = []
  }
}

describe('ws-connection pool', () => {
  beforeEach(() => {
    FakeWebSocket.reset()
    resetWebSocketPool()
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket)
    vi.useFakeTimers()
  })

  afterEach(() => {
    resetWebSocketPool()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('reuses the same socket across release+acquire within grace (StrictMode)', async () => {
    const key = makeWsKey('participant', { token: 'tok-1' })
    const opens: number[] = []

    const first = acquireWebSocket('participant', key, 'ws://localhost/ws?t=1', {
      onOpen: () => opens.push(1),
    })

    await vi.runAllTimersAsync()
    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(webSocketPoolSize()).toBe(1)

    first.release()
    expect(webSocketPoolSize()).toBe(1)

    const second = acquireWebSocket('participant', key, 'ws://localhost/ws?t=1', {
      onOpen: () => opens.push(2),
    })

    await vi.runAllTimersAsync()
    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(webSocketPoolSize()).toBe(1)
    expect(second.getSocket()).toBe(first.getSocket())

    // Late open notification for reused OPEN socket
    expect(opens).toContain(1)
    expect(opens).toContain(2)

    second.release({ immediate: true })
    expect(webSocketPoolSize()).toBe(0)
  })

  it('disposes after grace when not re-acquired', async () => {
    const key = makeWsKey('admin', { token: 'a', roomId: 'r1' })
    const handle = acquireWebSocket('admin', key, 'ws://localhost/ws', {})
    await vi.runAllTimersAsync()

    handle.release()
    expect(webSocketPoolSize()).toBe(1)

    await vi.advanceTimersByTimeAsync(200)
    expect(webSocketPoolSize()).toBe(0)
    expect(FakeWebSocket.instances[0]?.readyState).toBe(FakeWebSocket.CLOSED)
  })

  it('notifies onClose only for unexpected closes', async () => {
    const key = makeWsKey('display', { token: 'disp' })
    const onClose = vi.fn()
    const handle = acquireWebSocket('display', key, 'ws://localhost/ws', { onClose })
    await vi.runAllTimersAsync()

    FakeWebSocket.instances[0]?.close()
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(webSocketPoolSize()).toBe(0)
    handle.release({ immediate: true })
  })
})
