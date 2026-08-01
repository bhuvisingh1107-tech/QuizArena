import { useCallback, useEffect, useReducer, useRef } from 'react'

import {
  computeReconnectDelay,
  displayLiveReducer,
  initialDisplayLiveState,
  type WsConnectionStatus,
} from '@/hooks/displayLiveReducer'
import { getWsBaseUrl } from '@/lib/env'
import type { WsMessage } from '@/types/api'

export interface UseDisplayWebSocketOptions {
  secretToken: string | undefined
  enabled?: boolean
}

export function useDisplayWebSocket({
  secretToken,
  enabled = true,
}: UseDisplayWebSocketOptions) {
  const [state, dispatch] = useReducer(displayLiveReducer, initialDisplayLiveState)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttempt = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const intentionalClose = useRef(false)
  const authFailedRef = useRef(false)
  const connectRef = useRef<(() => void) | null>(null)

  const clearReconnectTimer = () => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }
  }

  const disconnect = useCallback(() => {
    intentionalClose.current = true
    clearReconnectTimer()
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    dispatch({ type: 'STATUS', status: 'disconnected' satisfies WsConnectionStatus })
  }, [])

  const reconnect = useCallback(() => {
    if (!enabled || authFailedRef.current || !secretToken?.trim()) return
    intentionalClose.current = false
    reconnectAttempt.current = 0
    clearReconnectTimer()
    dispatch({ type: 'CLEAR_ERROR' })
    // Prevent onclose from scheduling a delayed connect while we reconnect immediately.
    const existing = wsRef.current
    if (existing) {
      intentionalClose.current = true
      existing.close()
      wsRef.current = null
      intentionalClose.current = false
    }
    connectRef.current?.()
  }, [enabled, secretToken])

  useEffect(() => {
    const onOnline = () => {
      if (!enabled || authFailedRef.current) return
      reconnect()
    }
    window.addEventListener('online', onOnline)
    return () => window.removeEventListener('online', onOnline)
  }, [enabled, reconnect])

  useEffect(() => {
    authFailedRef.current = state.authFailed
  }, [state.authFailed])

  useEffect(() => {
    if (!enabled) {
      disconnect()
      dispatch({ type: 'RESET' })
      return
    }

    if (!secretToken?.trim()) {
      dispatch({
        type: 'AUTH_FAILED',
        message: 'Missing display token. Check the presentation link.',
      })
      return
    }

    intentionalClose.current = false
    authFailedRef.current = false
    let cancelled = false

    const connect = () => {
      if (cancelled || intentionalClose.current || authFailedRef.current) return

      const base = getWsBaseUrl()
      const url = `${base}?role=display&token=${encodeURIComponent(secretToken)}`

      dispatch({ type: 'STATUS', status: 'connecting' })
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        reconnectAttempt.current = 0
        dispatch({ type: 'STATUS', status: 'connected' })
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(String(event.data)) as WsMessage
          if (message.type === 'ping') {
            ws.send(
              JSON.stringify({
                type: 'pong',
                payload: message.payload ?? {},
                timestamp: new Date().toISOString(),
              }),
            )
          }

          if (message.type === 'error') {
            const payload =
              message.payload && typeof message.payload === 'object'
                ? (message.payload as Record<string, unknown>)
                : {}
            const code = String(payload.code ?? '')
            if (
              code === 'AUTH_ERROR' ||
              code === 'ROOM_CLOSED' ||
              code === 'FORBIDDEN' ||
              code === 'UNAUTHORIZED'
            ) {
              authFailedRef.current = true
              intentionalClose.current = true
              clearReconnectTimer()
            }
          }

          dispatch({ type: 'EVENT', message })
        } catch {
          dispatch({ type: 'ERROR', message: 'Failed to parse WebSocket message' })
        }
      }

      ws.onerror = () => {
        dispatch({ type: 'STATUS', status: 'error' })
      }

      ws.onclose = () => {
        wsRef.current = null
        if (cancelled || intentionalClose.current || authFailedRef.current) {
          if (!authFailedRef.current) {
            dispatch({ type: 'STATUS', status: 'disconnected' })
          }
          return
        }
        dispatch({ type: 'STATUS', status: 'disconnected' })
        const attempt = reconnectAttempt.current
        const delay = computeReconnectDelay(attempt)
        reconnectAttempt.current = attempt + 1
        clearReconnectTimer()
        reconnectTimer.current = setTimeout(connect, delay)
      }
    }

    connectRef.current = connect
    connect()

    return () => {
      cancelled = true
      intentionalClose.current = true
      connectRef.current = null
      clearReconnectTimer()
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [enabled, secretToken, disconnect])

  return {
    ...state,
    disconnect,
    reconnect,
    clearError: () => dispatch({ type: 'CLEAR_ERROR' }),
  }
}
