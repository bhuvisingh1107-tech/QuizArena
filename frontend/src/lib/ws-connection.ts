/**
 * Ref-counted WebSocket pool that survives React StrictMode remounts.
 *
 * React 18 StrictMode mounts → cleans up → remounts synchronously. Closing the
 * socket in cleanup drops the backend connection and races reconnect. Instead we
 * retain sockets for a short window so the remount re-acquires the same instance.
 */

import { wsDebug } from '@/lib/ws-debug'

export type WsRole = 'admin' | 'participant' | 'display'

export interface WsHandlers {
  onOpen?: (ws: WebSocket) => void
  onMessage?: (event: MessageEvent, ws: WebSocket) => void
  onError?: (event: Event, ws: WebSocket) => void
  /** Fired for unexpected closes while this retainer still owns the socket. */
  onClose?: (event: CloseEvent, ws: WebSocket) => void
}

export interface WsConnectionHandle {
  key: string
  role: WsRole
  getSocket: () => WebSocket | null
  readyState: () => number
  send: (data: string) => boolean
  /** Drop this retainer. Pass immediate to close without StrictMode grace. */
  release: (options?: { immediate?: boolean }) => void
  /** Replace event handlers for this retainer (e.g. after reconnect). */
  setHandlers: (handlers: WsHandlers) => void
}

interface PoolEntry {
  key: string
  role: WsRole
  url: string
  ws: WebSocket
  retainers: number
  handlers: Set<WsHandlers>
  disposeTimer: ReturnType<typeof setTimeout> | null
  /** When true, socket was closed intentionally and must not auto-notify retainers as unexpected. */
  intentionalClose: boolean
}

const DISPOSE_GRACE_MS = 150

const pool = new Map<string, PoolEntry>()

function wireSocket(entry: PoolEntry): void {
  const { ws, role, key } = entry

  ws.onopen = () => {
    wsDebug(role, 'open', { key, readyState: ws.readyState })
    for (const h of [...entry.handlers]) {
      h.onOpen?.(ws)
    }
  }

  ws.onmessage = (event) => {
    for (const h of [...entry.handlers]) {
      h.onMessage?.(event, ws)
    }
  }

  ws.onerror = (event) => {
    wsDebug(role, 'error', { key, readyState: ws.readyState })
    for (const h of [...entry.handlers]) {
      h.onError?.(event, ws)
    }
  }

  ws.onclose = (event) => {
    wsDebug(role, 'close', {
      key,
      code: event.code,
      reason: event.reason,
      wasClean: event.wasClean,
      intentional: entry.intentionalClose,
      retainers: entry.retainers,
    })

    const handlers = [...entry.handlers]
    const intentional = entry.intentionalClose

    if (pool.get(key) === entry) {
      pool.delete(key)
    }
    if (entry.disposeTimer) {
      clearTimeout(entry.disposeTimer)
      entry.disposeTimer = null
    }
    entry.handlers.clear()
    entry.retainers = 0

    if (!intentional) {
      for (const h of handlers) {
        h.onClose?.(event, ws)
      }
    }
  }
}

function closeEntry(entry: PoolEntry, reason: string): void {
  wsDebug(entry.role, 'dispose', { key: entry.key, reason, readyState: entry.ws.readyState })
  entry.intentionalClose = true
  // Detach before close so we don't double-notify; onclose still removes from pool.
  entry.ws.onopen = null
  entry.ws.onmessage = null
  entry.ws.onerror = null
  const closing = entry.ws
  closing.onclose = () => {
    if (pool.get(entry.key) === entry) {
      pool.delete(entry.key)
    }
    wsDebug(entry.role, 'cleanup', { key: entry.key, reason })
  }
  try {
    if (
      closing.readyState === WebSocket.OPEN ||
      closing.readyState === WebSocket.CONNECTING
    ) {
      closing.close()
    } else if (pool.get(entry.key) === entry) {
      pool.delete(entry.key)
    }
  } catch {
    if (pool.get(entry.key) === entry) {
      pool.delete(entry.key)
    }
  }
}

/**
 * Build a stable pool key for a logical live connection.
 * Same key ⇒ same socket reused across StrictMode / brief remounts.
 */
export function makeWsKey(
  role: WsRole,
  parts: { token?: string; roomId?: string },
): string {
  const token = parts.token ?? ''
  const roomId = parts.roomId ?? ''
  return `${role}|${roomId}|${token}`
}

export function acquireWebSocket(
  role: WsRole,
  key: string,
  url: string,
  handlers: WsHandlers,
): WsConnectionHandle {
  let entry = pool.get(key)

  if (entry?.disposeTimer) {
    clearTimeout(entry.disposeTimer)
    entry.disposeTimer = null
    wsDebug(role, 'acquire', { key, action: 'cancel-dispose' })
  }

  const reusable =
    entry &&
    entry.url === url &&
    (entry.ws.readyState === WebSocket.OPEN ||
      entry.ws.readyState === WebSocket.CONNECTING)

  if (reusable && entry) {
    entry.retainers += 1
    entry.handlers.add(handlers)
    wsDebug(role, 'reuse', {
      key,
      retainers: entry.retainers,
      readyState: entry.ws.readyState,
    })
    // eslint-disable-next-line no-console -- required connection diagnostics
    console.info(
      `[ws:${role}] reusing`,
      entry.url.replace(/token=[^&]+/i, 'token=***'),
      `readyState=${entry.ws.readyState}`,
    )
    // Late subscriber: if already open, notify immediately.
    if (entry.ws.readyState === WebSocket.OPEN) {
      queueMicrotask(() => {
        if (entry && entry.handlers.has(handlers) && entry.ws.readyState === WebSocket.OPEN) {
          handlers.onOpen?.(entry.ws)
        }
      })
    }
  } else {
    if (entry) {
      // Stale / wrong URL — dispose without notifying old handlers as unexpected.
      closeEntry(entry, 'replace')
    }
    const redacted = url.replace(/token=[^&]+/i, 'token=***')
    wsDebug(role, 'create', { key, url: redacted })
    // Always log the exact dial URL (token redacted) so misconfigured
    // VITE_WS_BASE_URL / Vite-origin fallbacks are obvious in the console.
    // eslint-disable-next-line no-console -- required connection diagnostics
    console.info(`[ws:${role}] connecting`, redacted)
    const ws = new WebSocket(url)
    entry = {
      key,
      role,
      url,
      ws,
      retainers: 1,
      handlers: new Set([handlers]),
      disposeTimer: null,
      intentionalClose: false,
    }
    pool.set(key, entry)
    wireSocket(entry)
  }

  let activeHandlers = handlers

  const handle: WsConnectionHandle = {
    key,
    role,
    getSocket: () => {
      const current = pool.get(key)
      return current?.ws ?? null
    },
    readyState: () => {
      const current = pool.get(key)
      return current?.ws.readyState ?? WebSocket.CLOSED
    },
    send: (data: string) => {
      const current = pool.get(key)
      if (!current || current.ws.readyState !== WebSocket.OPEN) {
        wsDebug(role, 'send', { key, ok: false, readyState: current?.ws.readyState })
        return false
      }
      current.ws.send(data)
      return true
    },
    setHandlers: (next) => {
      const current = pool.get(key)
      if (!current) return
      current.handlers.delete(activeHandlers)
      activeHandlers = next
      current.handlers.add(activeHandlers)
    },
    release: (options) => {
      const current = pool.get(key)
      if (!current) {
        wsDebug(role, 'release', { key, action: 'missing' })
        return
      }
      current.handlers.delete(activeHandlers)
      current.retainers = Math.max(0, current.retainers - 1)
      wsDebug(role, 'release', {
        key,
        retainers: current.retainers,
        immediate: Boolean(options?.immediate),
      })

      if (current.retainers > 0) return

      if (options?.immediate) {
        if (current.disposeTimer) {
          clearTimeout(current.disposeTimer)
          current.disposeTimer = null
        }
        closeEntry(current, 'immediate-release')
        return
      }

      if (current.disposeTimer) clearTimeout(current.disposeTimer)
      current.disposeTimer = setTimeout(() => {
        current.disposeTimer = null
        if (current.retainers > 0) return
        if (pool.get(key) !== current) return
        closeEntry(current, 'grace-expired')
      }, DISPOSE_GRACE_MS)
    },
  }

  return handle
}

/** Test helper — drop all pooled sockets. */
export function resetWebSocketPool(): void {
  for (const entry of [...pool.values()]) {
    if (entry.disposeTimer) clearTimeout(entry.disposeTimer)
    closeEntry(entry, 'reset')
  }
  pool.clear()
}

export function webSocketPoolSize(): number {
  return pool.size
}
